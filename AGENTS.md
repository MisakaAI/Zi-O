# AGENTS.md

本文件适用于整个 ZI/O 仓库。它保存长期工程上下文；具体产品行为与验收标准见 `docs/REQUIREMENTS.md`。

## 工作方式

1. 开始任务时先阅读本文件、`docs/REQUIREMENTS.md`、README 和相关模块，再检查当前工作树。
2. 对跨前后端、数据库迁移或安全边界的大改动，先给出简短计划，再执行。
3. 优先完成端到端的最小可验证切片；不要只搭大量空壳。
4. 不覆盖或撤销用户已有改动。发现不相关的脏工作树时保留它；发生重叠风险时停止并说明。
5. 遇到需求冲突、权限模型变化、数据丢失风险或需要新依赖时，停止并向用户确认。
6. 完成后报告改动、验证结果、未解决风险；不得把“未运行测试”描述为通过。

## 产品不变量

- Note 是时间事件，也是系统核心；Item 只是事件关联的长期档案对象。
- LOG 依据 `started_at DESC, id DESC`，不是 `created_at`。
- `archive_no` 稳定、唯一、只增不改。
- `content_raw` 是正文真源；`static_path` 可空，但不是内容格式。
- Item chip 和普通 Tag 数据分离。
- 根分类为 `JOURNAL / BOOK / MOVIE / GAME / CODE`；未选分类时以 JOURNAL 为主分类。
- v0.1 只有 `public` 与 `private`。
- Item 私密化必须在同一事务中私密化关联 Note；Item 公开化不得自动公开 Note。
- 公共 Note 查询还必须排除任何关联私密 Item 的 Note，作为纵深防御。
- 私密静态页不可通过猜测 URL 或直接静态目录访问。

## 技术边界

- 前端：Vue 3 Composition API、SFC、Vue Router、Vite。
- 后端：Python 3、FastAPI、标准库 `sqlite3`。
- 已批准依赖仅包括：Vue、Vue Router、Vite、FastAPI、`uvicorn`、`markdown-it-py`、`nh3`。
- 除以上项目外，加入任何第三方 Python/npm 依赖前必须获得用户明确批准。
- 禁止自行引入 ORM、Alembic、JWT 包、Axios、Pinia、Tailwind、UI 框架、日期库、图标库、masonry 或测试框架。
- 优先使用标准库、浏览器原生 API、`fetch`、原生 CSS 和 CSS Grid。
- 开发阶段不创建 Dockerfile 或 Compose 文件；部署目标是 systemd。

## 架构与代码约定

- 公共 API 放在 `/api/public/*`，管理 API 放在 `/api/manage/*`，认证放在 `/api/auth/*`。
- Router 只处理 HTTP 边界；业务规则进入 service；SQL 进入 repository/db 层。
- SQLite 查询必须参数化；启用 foreign keys；跨表隐私变更必须显式事务化。
- 使用有序 SQL migration 和 `schema_version`，不在应用代码中散落临时 DDL。
- 时间数据库值按 UTC Unix milliseconds 保存，API 使用 UTC ISO 8601，显示时使用站点 timezone。
- 列表分页使用 `(started_at, id)` cursor，游标不得信任客户端可篡改的排序参数。
- API 错误使用一致结构与稳定错误码；不向客户端泄露堆栈、绝对路径或 SQL。
- Python 模块、Vue 组件和 CSS 按职责拆分；避免无意义抽象和超大文件。
- 注释解释“为什么”，不要复述代码。

## 安全要求

- 密码使用带盐 PBKDF2；session token 使用 `secrets` 生成，数据库只存哈希。
- session Cookie 为 HttpOnly、SameSite=Lax；生产环境 Secure；写请求执行同源检查。
- Markdown 经 `markdown-it-py` 渲染后必须用 `nh3` 清理；原始 HTML 也必须清理。
- 任何传入前端 `v-html` 的值都必须来自后端已清理字段，并在命名上体现其已清理。
- `static_path` 仅接受静态根目录中的相对 HTML 文件。解析后验证仍在根目录内，拒绝符号链接逃逸和路径穿越。
- 静态目录不得公开 mount；`/page/{note_id}` 必须先查 Note 和关联 Item 权限。
- 默认静态页 CSP 禁止脚本、插件及外部资源；改变该策略前必须得到确认。
- 所有输入设置服务端上限，所有输出遵循最小必要字段原则。

## 前端与设计约定

- 阅读优先，装饰克制。采用深石墨、银灰、低对比刻度与少量 signal 洋红。
- 主要视觉语法是 Temporal Rail、timestamp、`LOG/000001`、index 和短横刻度。
- 不制作拟物仪表盘，不持续闪烁，不做背景粒子或循环扫描线。
- 时间与编号使用系统等宽字体，正文使用系统无衬线字体，不下载特殊字体。
- 动效一般为 120–180ms，并完整处理 `prefers-reduced-motion`。
- 所有页面必须有 loading、empty、error、focus、disabled 状态；颜色不得作为唯一提示。
- 使用语义化 `<time>`、键盘可操作控件、可见焦点和合理 heading 层级。
- 保持完全原创。不得使用或近似复刻任何受保护作品的 Logo、角色、道具、UI、字体、图像、音效、台词或特征轮廓。

## 数据与仓库卫生

- 不提交数据库、session、密码、密钥、上传内容、备份、构建输出或本地环境文件。
- 提供无秘密的示例配置。
- 测试数据不得包含真实私密内容。
- destructive migration、批量删除或不可逆格式变更必须先备份并获得用户确认。
- 不使用 `git reset --hard`、强制覆盖或删除未知文件来整理工作树。

## 验证要求

改动后运行与范围匹配的最小充分验证：

- 前端：至少运行 `npm run build`；若已有 lint/test 脚本，也运行相关脚本。
- 后端：运行已有测试；新后端核心逻辑优先使用标准库 `unittest` 编写测试。
- 数据库：验证空库迁移、重复启动和外键行为。
- 安全：覆盖 XSS 清理、公开查询隐私过滤、Item 隐私级联、静态路径穿越/符号链接逃逸。
- 时间线：覆盖相同时间戳、补记旧记录和 cursor 边界，确保不重不漏。
- UI：至少检查桌面和窄屏，以及键盘焦点、错误、加载、空状态和 reduced motion。

若受环境限制无法运行某项验证，在交付说明中明确写出未验证项、原因和可复现命令。

## 完成定义

- 行为符合 `docs/REQUIREMENTS.md` 的对应验收标准。
- 没有未经批准的新依赖。
- 数据迁移、配置示例和必要文档与代码同步。
- 关键安全规则由服务端实施，并有自动化或可复现验证，不能只依赖前端。
- 构建/测试结果真实记录，工作树中不包含生成垃圾或秘密。

