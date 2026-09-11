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

Start-Process "http://localhost:8000"
$pythonExe = Join-Path $scriptDir "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    Write-Error "未找到后端 Python 环境。请先运行: uv sync --project backend"
    exit 1
}

# 使用 Python 模块入口，避免 uvicorn.exe 在包含中文的项目路径下解析失败。
& $pythonExe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
