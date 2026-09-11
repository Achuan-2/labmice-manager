# Cloudflare Workers + D1 与群晖 Docker 部署

当前项目保留两套运行入口：Cloudflare Workers + D1 用于外网体验，`Dockerfile` + `docker-compose.yml` 用于群晖 Container Manager。两套入口共用 Vue 页面、接口路径、SQLite 数据模型和迁移数据格式。

## 首次生成数据迁移文件

```powershell
backend\.venv\Scripts\python.exe scripts\prepare_cloudflare_data.py
```

该命令只读打开 `data\mouse-manager.db`，先做 SQLite 完整性和外键检查，再生成：

- `migration-output\initial\initial-data.sql`：仅导入空 D1 数据库的 SQL；
- `migration-output\initial\sqlite-snapshot.db`：迁移前只读快照；
- `migration-output\initial\manifest.json`：每张表的数量和 SHA-256；
- `migration-output\initial\credentials.txt`：仅迁移副本中已知默认密码会被轮换，原始 SQLite 不会被修改。

不要把 `migration-output`、`.dev.vars` 或凭据文件提交到 Git。

## Workers / D1

首次部署需要 Cloudflare 账号登录：

```powershell
pnpm install
pnpm exec wrangler login
pnpm exec wrangler d1 create mouse-lab
```

把 Wrangler 输出的真实 `database_id` 写入 `wrangler.jsonc` 的 `d1_databases[0].database_id`，然后执行：

```powershell
pnpm db:migrate:remote
pnpm exec wrangler d1 execute mouse-lab --remote --file migration-output/initial/initial-data.sql
pnpm exec wrangler secret put SECRET_KEY
pnpm run deploy:cloudflare
```

`initial-data.sql` 自带空库保护，目标 D1 已有数据时会整体失败，不会把两套数据混在一起。部署后可以运行本地 smoke 测试：

```powershell
node scripts/smoke_cloudflare.mjs --url=https://<worker-subdomain>.workers.dev
```

Cloudflare D1 的 Free 计划有 500 MB 单库、每次 Worker 调用 50 次读取子请求、单行/字符串 2 MB 和 SQL 语句 100 KB 等限制；当前数据规模在容量上足够，但 Excel 单文件和单次批量操作仍按项目内限制执行。

## 群晖 Docker

在项目根目录创建 `.env`，至少设置一组随机 `SECRET_KEY`、管理员密码和访客密码：

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

把 `data` 映射到群晖共享文件夹，`excel` 映射到需要自动导入的只读文件夹。SQLite 数据库和备份均保存在 `/app/data`，容器使用非 root 用户运行并带健康检查。

## 已完成验证

```powershell
pnpm --dir frontend build
pnpm test:cloudflare
uv run --project backend --no-sync python -m unittest discover -s backend/tests -v
pnpm exec wrangler deploy --dry-run --outdir .wrangler/build
```

真实 Wrangler 本地运行时已验证鉴权、分页、笼位和鼠房、成员、转鼠审批与撤销、基因鉴定、状态、统计、Excel 导出、`.db` 备份恢复和 SPA 路由。
