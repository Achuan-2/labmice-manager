Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "       课题组小鼠管理系统 - 快速启动" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "【本机浏览器访问网址】: http://localhost:8000" -ForegroundColor Yellow
Write-Host "【备用访问网址】:     http://127.0.0.1:8000" -ForegroundColor Yellow
Write-Host ""
Write-Host "【特别注意】: 请访问 http://localhost:8000" -ForegroundColor Red
Write-Host "             请勿在浏览器输入或点击 0.0.0.0 (Windows浏览器不支持直接访问0.0.0.0)" -ForegroundColor Red
Write-Host ""
Write-Host "默认管理员账号: admin / 密码: admin123" -ForegroundColor Yellow
Write-Host "系统支持设置领取人、换笼、基因鉴定关联、转鼠申请与审核等" -ForegroundColor Gray
Write-Host "========================================================" -ForegroundColor Cyan

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$pythonExe = Join-Path $scriptDir "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    Write-Error "未找到后端 Python 环境。请先运行: uv sync --project backend"
    exit 1
}

# 使用 Python 模块入口，避免 uvicorn.exe 在包含中文的项目路径下解析失败。
$server = Start-Process -FilePath $pythonExe -ArgumentList @(
    "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"
) -NoNewWindow -PassThru -ErrorAction Stop

Write-Host "正在等待服务启动..." -ForegroundColor Cyan
$healthUrl = "http://127.0.0.1:8000/api/health"
$deadline = (Get-Date).AddSeconds(60)
$ready = $false
try {
    while ((Get-Date) -lt $deadline) {
        if ($server.HasExited) {
            Write-Error "后端启动失败，退出码: $($server.ExitCode)"
            exit 1
        }

        try {
            $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
            # 服务尚未就绪，继续等待。
        }
        Start-Sleep -Milliseconds 500
    }

    if (-not $ready) {
        Write-Error "后端在 60 秒内未就绪，请检查上方启动日志。"
        exit 1
    }

    Start-Process "http://localhost:8000"
    $server.WaitForExit()
    exit $server.ExitCode
} finally {
    if (-not $server.HasExited) {
        Stop-Process -Id $server.Id -ErrorAction SilentlyContinue
    }
}
