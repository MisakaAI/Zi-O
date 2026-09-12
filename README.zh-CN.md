# ZI/O

[简体中文](README.zh-CN.md) | [English](README.md)

ZI/O 是一个单用户、自托管的时间档案。Note 是带时间的事件，Item 用于提供长期档案上下文。

## 环境要求

Python 3.11+、Node.js 20+（仓库已使用 Python 3.14 和 Node 25 验证）以及 SQLite 3.35+。

## 本地安装

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.txt
npm --prefix frontend install
```

在 shell 中设置配置（可复制 `backend/.env.example`，替换密钥并导出变量；应用不会自动加载 `.env` 文件）：

```sh
export ZIO_DATABASE_PATH="$PWD/data/zio.sqlite3"
export ZIO_STATIC_PAGES_ROOT="$PWD/data/static-pages"
export ZIO_COVERS_ROOT="$PWD/data/covers"
export ZIO_FRONTEND_DIST="$PWD/frontend/dist"
export ZIO_PUBLIC_ORIGIN="http://127.0.0.1:8000"
export ZIO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export ZIO_TIMEZONE="Asia/Shanghai"
```

首次初始化数据库和唯一管理员账户（用户名默认为 `misaka`）：

```sh
PYTHONPATH=backend .venv/bin/python -m app.cli migrate
PYTHONPATH=backend .venv/bin/python -m app.cli init-admin
```

构建并启动：

```sh
npm --prefix frontend run build
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000/now`。前端开发时，让 API 运行在 8000 端口并设置 `ZIO_PUBLIC_ORIGIN=http://127.0.0.1:5173`，然后运行 `npm --prefix frontend run dev`；Vite 会代理 `/api` 和 `/page`。

## 运维

服务启动时会自动应用待执行的迁移。使用 `GET /api/health` 进行健康检查。`deploy/zio.service` 提供了 systemd 示例：它以非 root 用户运行单个 Uvicorn worker，并假设由反向代理负责 TLS。将 `ZIO_SECRET_KEY` 和生产环境 Origin 保存在权限为 600 的 `/etc/zio/zio.env` 中。

静态页面必须是放在 `ZIO_STATIC_PAGES_ROOT` 下的自包含 UTF-8 HTML 文件。Note 的 `static_path` 必须是相对 `.html` 路径；`/page/{note_id}` 会执行与 Note 详情相同的公开/私密权限检查，并应用严格 CSP。管理端支持上传 JPEG、PNG 或 WebP 海报（最大 5 MiB），文件存放在 `ZIO_COVERS_ROOT` 下。

## 备份与恢复

服务运行期间使用 SQLite 在线备份 API：

```sh
PYTHONPATH=backend .venv/bin/python -m app.cli backup /var/backups/zio-$(date +%Y%m%d-%H%M%S).sqlite3
```

恢复时先停止服务，将已验证的备份复制到新文件，并使用 SQLite 执行 `PRAGMA integrity_check`。保留带日期的旧数据库作为回滚副本，然后原子替换 `ZIO_DATABASE_PATH` 并重启服务。不要使用 `cp` 直接复制正在写入的数据库作为备份方式。

当前系统结构和 ASCII 请求流程见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。完整的请求/响应契约和稳定错误码见 [`docs/API.md`](docs/API.md)，需求文档见 [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md)。

## 验证

```sh
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v
npm --prefix frontend run build
```
