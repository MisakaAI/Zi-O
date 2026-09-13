# ZI/O v0.1 需求文档

状态：可进入开发  
产品类型：单用户、自托管的个人时间档案  
核心定义：以时间事件（Note）为中心，以档案对象（Item）为上下文，记录“某个时间，我做了什么、看了什么、读了什么、想了什么”。

## 1. 产品目标

ZI/O 将笔记、阅读、观影、游戏、项目和日记组织到同一条时间轴中。它不是社交信息流，也不是多个媒体追踪器的拼接。

首版需要做到：

- 访客可以浏览公开的 NOW、LOG、档案对象、标签和笔记详情。
- 管理员登录后可以管理时间事件、档案对象、分类和标签。
- 每条事件拥有真实发生时间，而不是只按录入时间排序。
- 图书、电影、游戏、项目等作为可长期积累的 Item，与多条 Note 关联。
- 私密数据在 API、页面和静态网页入口处均不可泄露。
- Markdown、HTML 和受保护的静态网页三种阅读方式可用。
- 形成原创、克制、可访问的 Temporal Interface。

## 2. 非目标（v0.1 不做）

- 多用户、注册、OAuth、社交、评论、点赞、关注。
- GitHub/GitLab 项目面板或第三方媒体元数据自动抓取。
- Obsidian/Memos 同步、全文搜索、高级附件管理、统计图表。
- Docker 或 Docker Compose 部署。
- JWT、ORM、前端状态库、UI/CSS 框架、图标库。
- 完整 CMS 页面搭建器或任意服务器端代码执行。

## 3. 用户与权限

### 3.1 角色

- 访客：只能读取有效公开内容。
- 管理员：唯一站点用户，可登录并管理全部内容。

初始用户名为 `misaka`，昵称可空；显示名使用 `nickname || username`。初始密码不得提交到仓库，应通过首次初始化命令或环境变量设置。

### 3.2 密码与会话

- 密码最低 6 个字符，且同时含英文字母和数字；界面建议使用至少 12 位。
- 使用 Python 标准库 `hashlib.pbkdf2_hmac` 加盐哈希，参数集中配置并可升级。
- 使用随机、不透明的服务端 session，不使用 JWT。
- 数据库只保存 session token 的哈希与过期时间。
- Cookie 必须为 `HttpOnly`、`SameSite=Lax`；生产环境启用 `Secure`。
- 登录、退出、鉴权失败和 session 过期都要有明确状态；写请求需要同源校验。

### 3.3 可见性

v0.1 仅有：

- `public`
- `private`

不擅自增加 `unlisted`。公开读取一条 Note 时必须同时满足：

1. Note 为 `public`；
2. 它关联的所有 Item 均为 `public`。

Item 从公开改为私密时，在同一数据库事务中将全部关联 Note 强制改为私密。Item 从私密改回公开时，不自动公开 Note；管理界面显示仍为私密的关联 Note 数量，并提供显式批量公开操作。

## 4. 核心领域模型

### 4.1 Note / Timeline Event

Note 是系统的核心事件，可仅有标题和时间，也可包含长篇正文。

必需字段：

- `id`
- `archive_no`：稳定、唯一、只增不改的档案编号，显示为 `LOG/000001`
- `title`：允许为空时，应由界面提供可理解的摘要占位
- `content_raw`：Markdown 或 HTML 原文，可空
- `content_format`：`markdown | html`
- `started_at`：UTC Unix milliseconds，默认当前时间
- `ended_at`：UTC Unix milliseconds，可空，且不得早于 `started_at`
- `visibility`：`public | private`
- `static_path`：相对于静态页面根目录的路径，可空
- `created_at`、`updated_at`：UTC Unix milliseconds

LOG 按 `started_at DESC, id DESC` 排序。补记旧事件不会改变其真实发生位置，但会获得新的 `archive_no`。

### 4.2 Category

首版预置根分类：

- `JOURNAL`
- `BOOK`
- `MOVIE`
- `GAME`
- `PROJECT`

根分类稳定；可创建子分类。一条 Note 可关联多个分类，其中恰好一个为主分类。未选择分类时，自动使用 `JOURNAL` 作为主分类。

推荐表：`categories` 与 `note_categories(note_id, category_id, is_primary)`。

### 4.3 Item

Item 是可长期存在的档案对象，例如一本书、一部电影、一个游戏或一个项目。不同类型统一存于 `items`，不为每种媒体建立独立业务表。

公共字段：

- `id`
- `category_id`：必须指向根分类
- `title`
- `subtitle`
- `creator`
- `poster_path`
- `visibility`
- `metadata_json`：类型特有且经过服务端校验的 JSON 对象
- `created_at`、`updated_at`

Item 的列表活动时间定义为关联 Note 的最大 `started_at`；无关联 Note 时回退到 Item 的 `created_at`。按该值倒序显示。

### 4.4 Note 与 Item

Note 与 Item 是多对多关系，推荐使用：

`note_items(note_id, item_id, context_label, progress_text)`

- `context_label`：章节、场次、版本等上下文。
- `progress_text`：百分比、游玩时长、观看次数等自由文本。
- 两字段均可空。

界面中 Item chip 固定显示在普通 Tag 之前，但 Item 不复制进 tags 表。

### 4.5 Tag

普通标签使用 `tags` 和 `note_tags` 多对多关系。标签名与 slug 唯一；slug 的生成和冲突策略必须确定且可测试。

### 4.6 建议的 SQLite 表

- `schema_version`
- `users`
- `sessions`
- `settings`
- `categories`
- `notes`
- `note_categories`
- `items`
- `note_items`
- `tags`
- `note_tags`

外键必须启用；迁移由有序 SQL 文件完成，启动时记录并应用版本，不引入 ORM 或 Alembic。

## 5. 内容渲染与静态网页

### 5.1 Markdown / HTML

- 数据库始终保存 `content_raw`，渲染结果不是唯一真源。
- Markdown 使用 `markdown-it-py` 渲染。
- Markdown 生成的 HTML 和用户输入的 HTML 均必须经过 `nh3` 白名单清理后再返回前端。
- 默认禁止脚本、事件处理属性、危险 URL scheme 和可触发跨站内容的标签/属性。
- 前端不得用未清理的数据调用 `v-html`。

### 5.2 静态网页高级模式

- `static_path` 不是第三种 `content_format`，而是 Note 的可选跳转目标。
- 有 `static_path` 时，点击 Note 导航到 `/page/{note_id}`；否则进入 `/n/{note_id}`。
- 静态页面目录不可由 Web Server 直接公开挂载。
- FastAPI 必须先执行与 Note 详情相同的权限判断，再读取文件。
- 仅允许静态根目录内的规范化相对路径；拒绝绝对路径、符号链接逃逸、`..` 穿越、目录和非 HTML 文件。
- v0.1 静态页以单个自包含 HTML 文件为准；默认 CSP 禁止脚本、插件和外部资源。若未来需要资源包或脚本能力，另立需求与安全方案。
- 路径不存在、越界或无权限时返回明确且不泄露文件系统信息的错误。

## 6. 页面与路由

### 6.1 公共页面

- `/`：进入 NOW 或直接呈现 NOW。
- `/now`：当前时间、简短状态、当前 signal 与当天/最近记录。
- `/log`：按日期分组的完整时间轨道，支持向过去加载。
- `/books`、`/movies`、`/games`、`/projects`、`/journal`：对应档案入口。
- `/items/{id}/{slug?}`：Item 详情及其关联事件时间线。
- `/n/{id}`：普通 Note 详情与 permalink。
- `/page/{id}`：鉴权后返回静态 HTML。
- `/tag/{slug}`：标签时间线。
- `/index`：分类、标签和档案索引。
- `/about`：站点说明。

URL 以稳定 ID 为主，slug 仅用于可读性，标题修改后仍可访问。

### 6.2 管理页面

- 登录/退出与当前用户状态。
- Note 新建、编辑、删除、查看。
- Item 新建、编辑、可见性变更与关联 Note 管理。
- Category、Tag 管理。
- Note 编辑器支持正文、起止时间、主/次分类、Item 关联及上下文、Tag、可见性、静态路径。
- 桌面端正文与属性并列；窄屏上属性区排到正文后。

删除必须有明确确认；关联数据删除规则使用外键约束并有测试，不能留下孤儿记录。

## 7. API 约定

公共与管理 API 使用不同前缀，防止通过遗漏过滤条件泄露私密数据。

公共 API：

- `GET /api/public/now`
- `GET /api/public/timeline`
- `GET /api/public/notes/{id}`
- `GET /api/public/items`
- `GET /api/public/items/{id}`
- `GET /api/public/tags/{slug}`

认证 API：

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

管理 API：

- `GET|POST /api/manage/notes`
- `GET|PATCH|DELETE /api/manage/notes/{id}`
- `GET|POST /api/manage/items`
- `GET|PATCH|DELETE /api/manage/items/{id}`
- `POST /api/manage/items/{id}/visibility`
- `POST /api/manage/items/{id}/notes/set-public`
- Category 与 Tag 的必要 CRUD 接口

具体请求/响应 schema 在实现前形成 `docs/API.md`，并以 FastAPI OpenAPI 输出为可执行契约。错误响应采用统一结构，至少包含稳定错误码和用户可读消息。

### 7.1 时间线分页

- 使用 cursor pagination，不使用页码分页。
- 排序键为 `(started_at, id)`，游标需不透明、可校验。
- 响应包含 `items` 和可空的 `next_cursor`。
- 单次数量有服务端上限。

## 8. Temporal Interface 设计规范

### 8.1 视觉语言

- 深石墨背景和层次明确的暗色表面。
- 银灰正文、低对比刻度；洋红只用于当前状态、交互、焦点和关键索引。
- Temporal Rail、timestamp、archive numbering、短横刻度构成主要图形语法。
- 正文使用系统无衬线字体，时间与编号使用系统等宽字体。
- 依靠字号、字重、间距建立秩序，不做拟物仪表盘。
- Logo 首版使用普通字形排版的 `ZI/O` wordmark。

建议起始 token（可做小幅可访问性调整）：

```css
--bg: #0b0c0f;
--surface: #111318;
--surface-2: #17191f;
--text: #d7d9dd;
--muted: #858a93;
--line: #2b2e35;
--signal: #e33b8c;
```

### 8.2 页面原则

- NOW 是当前切片，不是数据仪表盘。
- LOG 是发生时间优先的档案轨道，不采用制造沉迷感的社交 feed 设计。
- 每个事件使用语义化 `<time datetime="...">`，日期分组和 permalink 始终可见。
- Item 列表使用固定比例海报 + 响应式 CSS Grid，保持 row-major 时间顺序；不引入 masonry 库。
- 窄屏可收缩 Rail，但时间与正文对应关系不得丢失。
- loading、empty、error、success、focus、disabled 状态明确；颜色不是唯一信息载体。
- 键盘可完整操作，焦点清晰，语义标签合理；文本和关键控件满足 WCAG AA 对比度目标。

### 8.3 动效

- 常规时长约 120–180ms，短促克制。
- 可使用轻微淡入、最多 4px 位移和保存后的单次节点 pulse。
- 禁止循环发光、持续扫描线、背景粒子和干扰阅读的时钟闪烁。
- `prefers-reduced-motion: reduce` 下关闭非必要动画及位移。

### 8.4 原创边界

项目最初情绪来源可内部理解为“过去、现在、未来”和黑、银、洋红的时间主题，但最终产品必须完全原创。

用户可见页面严禁复刻或引用任何第三方作品的官方 Logo、头盔/眼睛轮廓、腰带、手表式道具、纹章、官方 UI、特有字体造型、角色、图像、音效、剧照或台词。有疑问时回到 timeline、index、signal、typography 和 motion。

## 9. 技术与工程约束

### 9.1 指定技术栈

- 前端：Node.js、Vue 3 Composition API、单文件组件、Vue Router、Vite。
- 后端：Python 3、FastAPI、标准库 `sqlite3`。
- 数据库：SQLite。
- 部署：systemd；开发阶段不使用 Docker。

### 9.2 已批准第三方依赖

- 栈内依赖：Vue 3、Vue Router、Vite、FastAPI。
- 本次新增批准：`uvicorn`、`markdown-it-py`、`nh3`。

除此以外，任何非标准库、npm 包或 Python 包，在加入前必须先获得用户确认。不得顺手加入 Pinia、Axios、Tailwind、组件库、日期库、ORM、迁移框架或测试框架。

优先使用：

- 前端 `fetch`、Composition API、原生 CSS、CSS Grid、`Intl.DateTimeFormat`、少量原创 inline SVG。
- 后端 `sqlite3`、`datetime`、`zoneinfo`、`hashlib`、`hmac`、`secrets`、`json`、`pathlib`。

### 9.3 建议目录

```text
frontend/
  src/{api,components,composables,router,styles,views}/
backend/
  app/{api,db,repositories,services}/
  app/main.py
  app/security.py
  app/rendering.py
migrations/
data/{covers,uploads,static-pages}/
deploy/zio.service
docs/
```

运行数据、数据库、上传文件、密钥和本地环境文件不得提交 Git。示例配置使用无秘密的 `.env.example` 或等效文档。

## 10. 运行、维护与安全

- 数据库连接启用 foreign keys、合理 busy timeout，并明确事务边界。
- 所有 SQL 使用参数绑定；动态排序字段使用固定白名单。
- 对标题、正文、标签、metadata、分页大小和上传/路径字段设服务端长度或尺寸上限。
- 错误日志不得包含密码、session token、私密正文或绝对静态文件路径。
- 提供健康检查接口，systemd unit 使用非 root 用户、明确工作目录、重启策略和环境文件。
- 提供 SQLite 一致性备份脚本或命令说明，优先使用 SQLite backup API；备份不能靠直接复制正在写入的数据库。
- API 响应时间统一为 UTC ISO 8601；数据库按需求保存 Unix milliseconds；前端按站点 `timezone` 显示。

## 11. v0.1 验收标准

以下条件全部满足才视为 v0.1 完成：

1. 全新环境按 README 可安装、初始化、构建并由 Uvicorn 启动。
2. 数据库迁移可从空库执行，多次启动不会重复破坏数据。
3. 管理员可登录、退出并在刷新后保持有效会话；错误密码和过期 session 行为正确。
4. 管理员可完整 CRUD Note 与 Item，并管理分类、标签和关联上下文。
5. LOG 严格按事件时间和 ID 稳定排序，按日期分组，cursor 不重不漏。
6. NOW 显示当前时间、当前/最近 signal，且无持续干扰动画。
7. Markdown 和 HTML 均能渲染；常见 XSS payload 不会执行。
8. 私密 Note 不出现在任何公共 API/页面；关联私密 Item 的 Note 即使状态异常也不会公开。
9. Item 私密化会事务性私密化关联 Note；再次公开 Item 不会隐式公开 Note。
10. 静态页面必须通过 `/page/{note_id}` 权限检查；路径穿越、符号链接逃逸、私密访问和缺失文件均被拒绝。
11. 桌面与窄屏的 NOW、LOG、Item 列表、详情和编辑页可用，时间与内容关系清晰。
12. 交互可用键盘完成，焦点/错误/加载/空状态明确，并尊重 reduced motion。
13. `npm run build` 成功；后端标准库测试成功；关键公开 API 经过可复现的冒烟测试。
14. systemd unit、生产配置说明、备份与恢复说明齐全。
15. 仓库中除明确批准项外没有新增第三方依赖，也没有受保护作品的视觉或文案素材。

## 12. 实施顺序

开始编码前先完成一次仓库检查和实现计划。建议里程碑：

1. 项目骨架、配置、迁移、领域模型与认证。
2. Note/Item/Category/Tag 管理 API 与隐私规则。
3. 公共 API、Markdown/HTML 渲染与静态页安全入口。
4. Vue 路由、基础视觉 token、NOW 与 LOG。
5. Item/Tag/管理页面、响应式与无障碍状态。
6. 测试、构建、systemd、备份恢复和 README。

每个里程碑完成后运行相关验证。若需求与现有仓库事实冲突，先记录冲突和建议，不要静默改写产品规则。

## 13. 后续候选方向

以下均不属于 v0.1，需另行确认优先级与依赖：媒体元数据 provider、GitHub/GitLab、Obsidian/Memos 导入同步、全文搜索、附件、统计、Docker Compose、多用户、OAuth、`unlisted` 可见性。
