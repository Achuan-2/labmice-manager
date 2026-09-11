Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "     Cloudflare Tunnel 极速公网在线体验穿透" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "此脚本利用 Cloudflare Tunnel 为本地小鼠管理系统生成安全 HTTPS 公网链接" -ForegroundColor Gray
Write-Host "无需公网 IP，无需路由器设置端口映射，手机与异地设备皆可直接访问" -ForegroundColor Gray
Write-Host "========================================================" -ForegroundColor Cyan

# 检查 cloudflared 是否已安装
if (-not (Get-Command "cloudflared" -ErrorAction SilentlyContinue)) {
    Write-Host "未检测到 cloudflared 命令行工具。" -ForegroundColor Yellow
    Write-Host "推荐通过以下方式极速安装：" -ForegroundColor White
    Write-Host "  方式 1 (PowerShell): winget install --id Cloudflare.cloudflared" -ForegroundColor Cyan
    Write-Host "  方式 2 (官网下载): https://github.com/cloudflare/cloudflared/releases" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "安装完成后，重新运行本脚本即可获得免费公网体验域名！" -ForegroundColor Green
    Pause
    Exit
}

Write-Host "正在启动 Cloudflare 免费隧道穿透至本地端口 8000..." -ForegroundColor Cyan
Write-Host "请注意下方输出中的类似 https://xxxx.trycloudflare.com 的公网地址！" -ForegroundColor Yellow
Write-Host ""

cloudflared tunnel --url http://localhost:8000
