# ZI/O

[简体中文](README.zh-CN.md) | [English](README.md)

ZI/O 是一个单用户、自托管的时间档案。Note 是带时间的事件，Item 用于提供长期档案上下文。

## 环境要求

[uv](https://docs.astral.sh/uv/)、Python 3.11+、Node.js 20+（仓库已使用 Python 3.14 和 Node 25 验证）以及 SQLite 3.35+。

## 本地安装

```sh
uv sync
npm --prefix frontend install
```

Python 依赖统一声明在 `pyproject.toml` 中，并由 `uv.lock` 锁定以保证可复现安装；`uv sync` 会自动创建或更新本地 `.venv`。

在 shell 中设置配置（可复制 `backend/.env.example`，替换密钥并导出变量；应用不会自动加载 `.env` 文件）：

```sh
export ZIO_DATABASE_PATH="$PWD/data/zio.sqlite3"
export ZIO_STATIC_PAGES_ROOT="$PWD/data/static-pages"
export ZIO_COVERS_ROOT="$PWD/data/covers"
export ZIO_FRONTEND_DIST="$PWD/frontend/dist"
export ZIO_PUBLIC_ORIGIN="http://127.0.0.1:8000"
export ZIO_SECRET_KEY="$(uv run python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export ZIO_TIMEZONE="Asia/Shanghai"
```

首次初始化数据库和唯一管理员账户（用户名默认为 `misaka`）：

```sh
PYTHONPATH=backend uv run python -m app.cli migrate
PYTHONPATH=backend uv run python -m app.cli init-admin
```

构建并启动：

```sh
npm --prefix frontend run build
PYTHONPATH=backend uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000/now`。

## 开发模式

日常开发时使用 Vite 热更新，不需要在每次修改前端代码后运行 `npm --prefix frontend run build`。从仓库根目录打开两个终端，分别启动后端和前端。

终端 1——启动 API，并允许 Vite 开发服务器发起请求：

```sh
export ZIO_PUBLIC_ORIGIN="http://127.0.0.1:5173"
PYTHONPATH=backend uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

终端 2——启动 Vite：

```sh
npm --prefix frontend run dev
```

打开 `http://127.0.0.1:5173/now`。修改前端文件后，Vite 会自动更新页面，并将 `/api` 和 `/page` 代理到 8000 端口的后端；修改 Python 文件后，Uvicorn 的 `--reload` 会自动重启后端。只有通过 FastAPI 提供前端页面或进行最终验证前，才需要执行生产构建。

前端界面默认使用简体中文，可通过顶栏的语言按钮切换 English；选择会保存在当前浏览器中。

## 运维

服务启动时会自动应用待执行的迁移。使用 `GET /api/health` 进行健康检查。`deploy/zio.service` 提供了 systemd 示例：它以非 root 用户运行单个 Uvicorn worker，并假设由反向代理负责 TLS。将 `ZIO_SECRET_KEY` 和生产环境 Origin 保存在权限为 600 的 `/etc/zio/zio.env` 中。

静态页面必须是放在 `ZIO_STATIC_PAGES_ROOT` 下的自包含 UTF-8 HTML 文件。Note 的 `static_path` 必须是相对 `.html` 路径；`/page/{note_id}` 会执行与 Note 详情相同的公开/私密权限检查，并应用严格 CSP。管理端支持上传 JPEG、PNG 或 WebP 海报（最大 5 MiB），文件存放在 `ZIO_COVERS_ROOT` 下。

## 备份与恢复

服务运行期间使用 SQLite 在线备份 API：

```sh
PYTHONPATH=backend uv run python -m app.cli backup /var/backups/zio-$(date +%Y%m%d-%H%M%S).sqlite3
```

恢复时先停止服务，将已验证的备份复制到新文件，并使用 SQLite 执行 `PRAGMA integrity_check`。保留带日期的旧数据库作为回滚副本，然后原子替换 `ZIO_DATABASE_PATH` 并重启服务。不要使用 `cp` 直接复制正在写入的数据库作为备份方式。

当前系统结构和 ASCII 请求流程见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。完整的请求/响应契约和稳定错误码见 [`docs/API.md`](docs/API.md)，需求文档见 [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md)。

## 验证

```sh
uv run ruff check backend
PYTHONPATH=backend uv run python -m unittest discover -s backend/tests -v
npm --prefix frontend run build
```
