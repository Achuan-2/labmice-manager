# 课题组小鼠管理系统

专为生物实验室/课题组定制的小鼠管理与流转联动系统。系统深度整合**小鼠档案**、**笼位分布**、**转鼠需求及反馈**、**基因型鉴定结果**、**课题组领取人**与**引物档案**，全站实施安全登录保护，支持群晖 NAS (Synology NAS) Docker 与 Cloudflare 在线部署。

---

## 🌟 核心功能特性

### 1. 安全访问保护与权限分级
- **强制全屏登录保护**：为了防止外界未经授权的人员随意浏览课题组数据，**游客与管理员均需登录后方可进入系统**。
- **登录凭证说明**：
  - 初始账号密码由部署时生成并保存在本机迁移输出目录，不再在页面或仓库中显示固定默认密码。
  - *(登录界面为专业生产级外观，彻底移除任何默认账号密码提示，保障实验数据私密性)*。
  - 管理员可在【管理员设置】中添加多个管理员账号并各自设置密码。
  - 系统名称默认为“课题组小鼠管理系统”；管理员可在【管理员设置】中填写自己的课题组/实验室名称，登录页、侧栏与浏览器标题会同步更新。

### 2. 转鼠需求及反馈表 (业务闭环流转)
- **访客/学生随时在线申请**：
  - 登录访客账号即可点击**【提交转鼠需求】**，登记需求者姓名、需求品系、期望年龄/性别（如“成年/雄鼠”）、期望转入鼠房（东四、东五、枫林等）及笼位数量。
- **管理员集中审批与自动联动**：
  - 管理员进入【转鼠需求及反馈】界面，可对申请进行审核，选择转出鼠房并**分配具体小鼠耳标编号**。
  - **核心联动**：管理员选择小鼠并保存“已转”审批后，系统自动将领取人设为需求者、小鼠状态设为“出笼”，解除笼位关联，并逐只记录原鼠房及笼位。编辑时移除已分配小鼠并保存，会恢复其分配前的笼位、状态和领取信息；清空全部编号会把需求恢复为“进行中”。取消或删除需求同样撤销分配。审批前记录持久化保存，重启后仍可恢复；原笼位已变更、小鼠信息被其他操作修改或历史分配缺少审批前记录时，会提示核对，不自动覆盖。

### 3. 小鼠基因鉴定结果记录与档案联动
- **独立基因鉴定中心**：专门界面集中管理 PCR 基因型鉴定记录
- **小鼠档案无缝联动**：
  - 在小鼠列表表格中直接展示基因型鉴定结果（如“阳性”、“野生型”、“Trap2-纯合子”等）。
  - 点击鉴定标签可拉出侧边抽屉，**完整查阅该小鼠历次基因鉴定的测试日期、父母系谱、Genotype 1/2/3 及测试人员记录**。
  - 支持管理员录入、修改与删除小鼠基因鉴定结果。


### 4. 小鼠 - 笼位 - 领取人 强力联动
- **批量指定领取人**：勾选任意 1 只或多只小鼠，一键批量分配给课题组成员，指定领用日期、实验目的，可选同步转移至新鼠房或笼位。
- **周龄/日龄动态推算**：根据出生日期（DOB）自动实时计算当前日龄与周龄（如 `12.5 周`）。
- **鼠架与笼位可视化看板**：真实鼠架卡片视图，展示笼号、品系、性别、在笼数量（如 `3/5`）、合笼日期与笼内小鼠芯片列表。

---

## 🚀 启动与使用

### 1. Windows 本地极速启动
- 直接双击项目根目录下的 **`start.bat`** 脚本，或在 PowerShell 中执行：
  ```powershell
  .\start.ps1
  ```
- 浏览器打开访问：**`http://localhost:8000`**。
- 输入账号密码登录：
  - 使用迁移输出目录 `credentials.txt` 中的账号登录。

### 2. 群晖 NAS (Synology NAS) Docker 部署
1. 在 Windows 项目目录中生成本地部署包：
   ```powershell
   .\build-nas.ps1
   ```
   脚本会重新创建项目下的 `build` 文件夹，并把 `backend`、`frontend`、Docker 配置、空的 `data` 目录及本地 `excel` 文件放进去。如不需要打包 Excel，请运行 `.\build-nas.ps1 -ExcludeExcel`。
2. 将 `build` 文件夹中的全部内容手动复制到群晖部署目录（例如 `/volume1/苏济雄个人/docker/mouse-manager`），再根据 `.env.example` 在群晖端创建 `.env`。
3. 在群晖 **Container Manager** 中点击“项目” -> “新增”，选择该目录并使用现有的 `docker-compose.yml` 启动。
4. 数据持久化存放在 `./data` 目录：`mouse-manager.db` 保存小鼠业务数据，`accounts.db` 单独保存账号和密码哈希。完整备份需同时保留这两个数据库，最简单的方式是备份整个 `data` 文件夹；网站内的数据库导出/恢复仅处理小鼠业务数据库，不会覆盖账号。
5. 在内网通过 `http://群晖IP:8000` 访问。

### 3. Cloudflare Workers + D1 部署

线上地址：<https://mouse.achuan-2.top>。Vue 静态资源由 Workers Assets 托管，API 使用 Hono，数据保存在 D1；本机无需持续开机。Docker 入口继续使用 FastAPI + SQLite。两套后端分别实现业务逻辑，修改接口时应同步检查两套实现。

#### 首次部署到自己的 Cloudflare 账号

安装 Node.js 和 pnpm，在项目根目录执行：

```powershell
pnpm install --frozen-lockfile
pnpm --dir frontend install --frozen-lockfile
pnpm exec wrangler login
pnpm exec wrangler d1 create mouse-lab
```

修改 `wrangler.jsonc`：填写新建数据库的 `database_id`；将 `routes` 中的域名改为自己在 Cloudflare 托管的域名，或删除 `routes` 使用 `workers.dev`。仓库中的数据库 ID 和域名属于当前线上实例，不适用于其他账号。

从本地 `data/mouse-manager.db` 生成迁移快照（需先按本地启动流程安装后端环境）：

```powershell
backend\.venv\Scripts\python.exe scripts/prepare_cloudflare_data.py
pnpm db:migrate:remote
pnpm exec wrangler d1 execute mouse-lab --remote --file migration-output/initial/initial-data.sql
pnpm exec wrangler secret put SECRET_KEY
pnpm run deploy:cloudflare
```

`SECRET_KEY` 交互输入一段随机长密钥。生成的账号凭据见 `migration-output/initial/credentials.txt`；原本已经自定义的密码保持原值。迁移输出和密钥文件不要提交到 Git。首次数据导入仅适用于空库。Workers 无法扫描本机 `excel` 文件夹，后续通过网站上传 Excel；大文件建议逐份上传，避免单次解析触发 CPU 限制。

#### 更新已部署网站的代码

在项目根目录更新代码并安装依赖后执行：

```powershell
pnpm install --frozen-lockfile
pnpm --dir frontend install --frozen-lockfile
pnpm test:cloudflare
pnpm run deploy:cloudflare
```

部署命令会重新构建前端并发布 Worker 和静态资源，也会沿用配置中的自定义域名。正常代码更新不会清空 D1，不要重新执行首次数据导入或数据重置；`SECRET_KEY` 也不必每次重设。

如果更新包含新增的 `cloudflare/migrations/*.sql`，先从网站导出数据库备份，再执行 `pnpm db:migrate:remote`，然后发布。Cloudflare 和 Docker 两套后端都修改时，还需运行 `uv run --project backend --no-sync python -m unittest discover -s backend/tests -v`。

发布后检查 <https://mouse.achuan-2.top/api/health>，再验证登录、小鼠列表与实际修改的功能。仅回退 Worker 代码可用 `pnpm exec wrangler rollback`；该命令不会回退数据库，需确认旧代码与当前表结构兼容。

Windows 如需使用本机 7890 代理，在当前 PowerShell 会话设置：

```powershell
$env:HTTP_PROXY = 'http://127.0.0.1:7890'
$env:HTTPS_PROXY = 'http://127.0.0.1:7890'
```

性能配置启用了 [Smart Placement](https://developers.cloudflare.com/workers/configuration/placement/)，由 Cloudflare 根据请求延迟决定 API 的执行位置；静态资源仍由边缘节点托管。笼位和小鼠列表使用只读数据索引，避免逐只扫描鉴定记录及复制整份查询数据。实际速度还受客户端网络和数据库访问延迟影响。更多迁移和 Docker 说明见 [CLOUDFLARE.md](./CLOUDFLARE.md)。

### 4. Cloudflare Tunnel 临时在线体验
在本地或服务器上执行：
```powershell
.\cloudflare_tunnel.ps1
```
终端将输出分配的临时安全公网链接（如 `https://xxxx.trycloudflare.com`），发送给导师或同学即可在手机/外网直接访问体验。
