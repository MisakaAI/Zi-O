# ZI/O 当前架构

本文描述 v0.1 当前代码的运行结构、主要请求流程和数据边界。产品行为以
[`REQUIREMENTS.md`](REQUIREMENTS.md) 为准，接口字段以 [`API.md`](API.md) 为准。

## 1. 系统全景

ZI/O 是单进程 FastAPI 服务配合 SQLite 的单用户自托管应用。Vue 构建产物由
FastAPI 提供；浏览器通过公共、认证和管理三组 API 访问数据。静态 HTML 页面和
海报文件位于独立数据目录，只能经过后端鉴权和路径检查读取。

```text
                         HTTP / HTTPS
  +-------------+       (TLS at proxy)       +----------------------+
  |   Browser   | <------------------------> | Reverse proxy (prod) |
  | Vue 3 SPA   |                            +----------+-----------+
  +------+------+                                       |
         | development: Vite proxy                      |
         | production: same origin                      v
         |                                   +----------------------+
         +---------------------------------> | FastAPI / Uvicorn    |
                                             | app.main:create_app  |
                                             +----+------------+----+
                                                  |            |
                         parameterized SQL        |            | validated file access
                                                  v            v
                                           +-------------+  +------------------+
                                           |   SQLite    |  | data/            |
                                           | zio.sqlite3 |  | static-pages/    |
                                           +-------------+  | covers/          |
                                                            +------------------+
```

生产部署由 `systemd` 启动单个 Uvicorn worker。数据库、静态页、海报和环境配置均在
仓库之外作为运行数据管理；SQLite 使用 WAL、foreign keys 和 busy timeout。

## 2. 代码分层

```text
  frontend/src/
  +------------------+     +-------------------+     +------------------+
  | views/components | --> | api/client.js     | --> | fetch /api/*     |
  | Vue SFC + Router |     | JSON/error adapter|     | same-origin cookie|
  +------------------+     +-------------------+     +---------+--------+
                                                               |
                                                               v
  backend/app/
  +------------------+     +-------------------+     +------------------+
  | api/*.py         | --> | services/*.py     | --> | repositories/    |
  | HTTP boundary    |     | business rules    |     | SQL queries      |
  +--------+---------+     +---------+---------+     +---------+--------+
           |                         |                         |
           | Depends                 | validation/rendering    v
           v                         v                  +-------------+
  +------------------+     +-------------------+        | db/         |
  | api/deps.py      |     | domain.py         |        | sqlite3     |
  | db/session/origin|     | rendering.py      |        | migrations  |
  +------------------+     | files.py          |        +-------------+
                           | security.py       |
                           +-------------------+
```

- Router 负责解析 HTTP 输入、选择公共或管理边界以及形成响应。
- Service 执行 Note/Item 关联、可见性级联、内容渲染和字段校验等业务规则。
- Repository 集中可复用 SQL，尤其是时间线和公共可见性查询。
- `db/migrations.py` 按编号执行 `backend/migrations/*.sql`，并记录
  `schema_version`；应用启动和 CLI 都使用同一套迁移逻辑。
- 前端不保存独立的全局业务状态。各页面按路由加载 API，公共站点设置和登录用户
  由 `App.vue` 持有。

## 3. HTTP 路由边界

```text
  Incoming request
         |
         v
  +---------------------------+
  | Path classification       |
  +-----+-----------+---------+
        |           | \
        |           |  \ /page/{note_id}
        |           |   +--> public visibility check
        |           |        or valid admin session
        |           |        + path/symlink/size check
        |           |        + restrictive CSP
        |           |
        |           +----> /api/auth/*
        |                 login/logout/me
        |
        +----> /api/public/*        /api/manage/*
               public filters       session required
               sanitized output     write origin check
                      |                    |
                      +---------+----------+
                                |
                                v
                         service/repository

  Any remaining browser route --> frontend/dist/index.html --> Vue Router
  /assets/*                    --> frontend/dist/assets/*
```

公共和管理 API 使用不同 router，避免管理查询漏加过滤条件后意外成为公共接口。所有
管理接口需要有效 session；登录、退出及管理写请求还需要 `Origin` 或 `Referer` 与
`ZIO_PUBLIC_ORIGIN` 同源。

## 4. 认证与会话流程

```text
  Login form
      |
      | POST /api/auth/login + Origin
      v
  lookup user --> PBKDF2 verify --> random session token
                                      |
                           +----------+-----------+
                           |                      |
                           v                      v
                    browser cookie          SQLite sessions
                    HttpOnly/Lax            SHA-256(token), expiry

  Later /api/manage request
      |
      v
  cookie token --> SHA-256 --> active session lookup --> administrator
      |                                                   |
      +---------------- invalid/expired ----------------> 401
```

数据库不保存原始 session token。生产环境 Cookie 同时启用 `Secure`。密码使用带盐
PBKDF2，登录时可把旧迭代次数升级到当前配置。

## 5. Note 写入与时间线

Note 是核心时间事件。`archive_no` 由独立计数器分配，只增不改；列表始终按
`started_at DESC, id DESC` 排序。

```text
  Note editor
      |
      | local datetime -> UTC ISO 8601
      v
  NoteWrite / NotePatch validation
      |
      +--> category IDs exist; exactly one primary
      +--> Item IDs exist; public Note links only public Items
      +--> extract #标签 from body text; reuse or create Tag IDs
      +--> ended_at >= started_at; static_path is relative .html
      |
      v
  BEGIN IMMEDIATE
      |
      +--> create/update notes
      +--> replace note_categories
      +--> replace note_items (per-Item context/progress)
      +--> replace note_tags
      |
      v
  COMMIT --> sanitized management response

  Timeline read
      |
      v
  signed cursor(started_at,id,scope)
      |
      v
  WHERE (started_at,id) is older --> ORDER BY started_at DESC,id DESC
      |
      v
  items + next_cursor
```

公共时间线、Item 时间线、Tag 时间线及管理 Note 列表都使用稳定游标，避免同时间戳
事件重复或遗漏。公共游标包含查询范围，不能跨分类、Tag 或 Item 复用。

## 6. 隐私边界

公共 Note 必须自身为 `public`，且不能关联任何私密 Item。该条件由公共 SQL 重复执行，
即使数据库出现不一致状态也不会公开相关 Note。

```text
  Make Item private
          |
          v
  BEGIN IMMEDIATE
          |
          +--> items.visibility = private
          +--> every linked Note.visibility = private
          |
          v
       COMMIT

  Make Item public
          |
          +--> Item becomes public
          +--> linked Notes remain private
                         |
                         v
              explicit "publish Notes"
                         |
                         +--> no other private Item? --> public
                         +--> otherwise              --> blocked list
```

Note 正文统一保存 Tiptap 生成的 HTML；About 仍保存可选的 Markdown/HTML 原文。返回公共
页面前统一由 `nh3` 白名单清理，About 的 Markdown 会先渲染为 HTML。前端的 `v-html`
只使用命名为 `*_html_sanitized` 的字段。

## 7. 数据关系

```text
  users 1 --------< sessions

  settings -- current_note_id (optional) -------------------+
                                                             |
                                                             v
  categories 1 ----< items                    +------------ notes
      ^                 ^                     |              |
      |                 |                     |              |
      +----< note_categories >----------------+              |
                        |                                    |
                        +---- primary flag                    |
                                                             |
  items <-------------- note_items ------------------------> notes
                         context_label / progress_text

  tags  <-------------- note_tags -------------------------> notes
```

关联表使用外键并在 Note 删除时级联清理。Category 删除受限制；Item 删除会清理
`note_items` 关联，但不会删除 Note。`settings.current_note_id` 在目标 Note 删除后置空。

## 8. 静态页、海报与正文图片

```text
  GET /page/{note_id}
          |
          +--> Note public and all Items public?
          |         or authenticated administrator?
          |
          +--> static_path present?
          +--> relative path, .html, inside configured root?
          +--> no symlink component, regular file, within size limit?
          |
          +-- yes --> FileResponse + CSP sandbox
          +-- no  --> generic 404 without filesystem details
```

静态页目录不会通过 `StaticFiles` 挂载。公共海报接口只接受公开 Item；管理海报接口
需要 session。上传会限制请求大小并检查声明类型与文件签名，文件名由随机 UUID 生成。

正文图片保存在独立 `uploads` 根目录，`content_images` 记录随机文件名，`note_images` 在 Note 保存事务中从正文的站内图片 URL 同步。`/api/content-images/{id}` 对管理员开放；访客请求还必须存在引用该图片且满足公共 Note 纵深隐私条件的关联记录。

## 9. 关键配置和启动顺序

```text
  Environment variables
          |
          v
  Settings.from_env
          |
          +--> validate timezone / production secret
          +--> create data directories
          +--> apply ordered migrations
          +--> seed initial timezone when untouched
          |
          v
  register routers + error handlers + security headers
          |
          v
  Uvicorn serves API, protected files and built SPA
```

主要配置包括数据库路径、静态页根目录、海报根目录、前端构建目录、公开 Origin、
session 密钥、站点时区以及生产 Cookie 策略。配置读取集中在 `backend/app/config.py`。
