@echo off
chcp 65001 > nul
echo ========================================================
echo        课题组小鼠管理系统 - 快速启动
echo ========================================================
echo 【本机浏览器访问网址】: http://localhost:8000
echo 【备用访问网址】:     http://127.0.0.1:8000
echo.
echo 【特别注意】: 请访问 http://localhost:8000
echo              请勿在浏览器访问 0.0.0.0 (Windows浏览器不支持直接访问0.0.0.0)
echo.
echo 默认管理员账号: admin / 密码: admin123
echo ========================================================

cd /d "%~dp0"
start http://localhost:8000
if not exist "backend\.venv\Scripts\python.exe" (
    echo 未找到后端 Python 环境。请先运行: uv sync --project backend
    pause
    exit /b 1
)
"backend\.venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
pause
