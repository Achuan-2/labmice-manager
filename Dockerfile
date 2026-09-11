# ==========================================
# 阶段 1: 构建 Vue 3 前端应用
# ==========================================
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

RUN corepack enable && corepack prepare pnpm@10.32.1 --activate

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build

# ==========================================
# 阶段 2: Python FastAPI 后端运行环境 (轻量极速)
# ==========================================
FROM python:3.13-slim AS runner
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# 安装基础依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv 高速包管理器
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /bin/uv

# 安装后端依赖
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --frozen --no-dev --no-install-project

# 拷贝后端代码
COPY backend/ ./backend/

# 拷贝已编译好的前端静态文件
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 挂载数据持久化目录 (SQLite 数据库及上传文件)
RUN groupadd --gid 10001 mouse && useradd --uid 10001 --gid mouse --no-create-home mouse \
    && mkdir -p /app/data && chown -R mouse:mouse /app/data
USER 10001:10001
VOLUME ["/app/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD ["/app/backend/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]

# 启动命令
CMD ["/app/backend/.venv/bin/uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
