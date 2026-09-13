# ZI/O v0.1 API 接口

所有 JSON 时间戳均使用 UTC ISO 8601（`2024-01-01T00:00:00.000Z`）；SQLite 存储 Unix 毫秒值。错误始终采用以下结构：

```json
{"error":{"code":"stable_code","message":"用户可读消息","details":{}}}
```

公共接口中未经授权或私密资源返回 `404`，且不会透露记录是否存在。JSON 请求体会拒绝未知字段。限制包括：标题 200、正文 1 MiB、静态路径 512、标签 64、元数据 16 KiB、时间线默认 20/最大 50、海报 5 MiB。

## 认证

- `POST /api/auth/login` 请求体为 `{username,password}`。设置 HttpOnly、SameSite=Lax 的 `zio_session` Cookie（生产环境启用 Secure）。
- `POST /api/auth/logout` 清除 Cookie。
- `GET /api/auth/me` 返回 `{user:null}` 或 `{user:{id,username,nickname,display_name}}`。

登录和所有改变状态的接口都要求 Origin/Referer 与 `ZIO_PUBLIC_ORIGIN` 匹配。

## 公共 API

- `GET /api/public/site` 返回站点标题、标语、时区、状态和经过清理的 About HTML。
- `GET /api/public/now` 返回服务器时间、时区、状态、可选的手动选中 `current_signal`，以及当天的公开 Note（没有当天记录时返回最近 5 条）。
- `GET /api/public/calendar?year=YYYY&month=MM` 返回站点时区下当月有公开事件的日期与数量：`{year,month,days:[{date,count}]}`。
- `GET /api/public/timeline?cursor=&limit=&category=&tag=&item_id=` 返回 `{items,next_cursor}`。排序为 `(started_at DESC,id DESC)`。游标经过签名处理、保持不透明且与查询条件绑定，不得编辑。
- `GET /api/public/notes/{id}` 返回经过清理的 Note 详情。
- `GET /api/public/items?category=` 返回公开 Item，并按可见的关联活动排序。
- `GET /api/public/items/{id}?cursor=&limit=` 返回一个 Item 及其公开 Note 时间线。
- `GET /api/public/items/{id}/poster` 仅在 Item 公开时返回海报。
- `GET /api/public/tags/{slug}?cursor=&limit=` 返回一个 Tag 及其公共时间线。
- `GET /api/public/index` 返回公开的分类、标签和 Item 索引。

Note 对公共接口可见必须同时满足 `notes.visibility='public'` 且所有关联 Item 均为公开。每个公共查询都应用这一条件，包括计数和活动时间戳查询。

## 管理 API

所有 `/api/manage/*` 接口都要求管理员会话。`GET /notes?cursor=&limit=` 按 `(started_at DESC,id DESC)` 的顺序返回 `{items,next_cursor}`；其签名游标保持不透明，可以在不改变排序的情况下继续获取更早的记录。`POST /notes` 和 `GET|PATCH|DELETE /notes/{id}` 使用 `NoteWrite`/`NotePatch`：

```json
{
  "title":"",
  "content_raw":"",
  "content_format":"markdown",
  "started_at":"2024-01-01T00:00:00Z",
  "ended_at":null,
  "visibility":"private",
  "static_path":null,
  "categories":[{"category_id":1,"is_primary":true}],
  "items":[{"item_id":2,"context_label":null,"progress_text":null}],
  "tag_ids":[]
}
```

创建时可以省略 `started_at`，此时使用当前 UTC 时间；如果提供，则必须包含时区。

执行 PATCH 时，只有在请求中出现的关联字段才会被替换；省略的字段保持不变。分类必须恰好包含一个主分类；省略分类或传入空分类时，选择 JOURNAL。公开 Note 不能关联私密 Item。

`GET|POST /items`、`GET|PATCH|DELETE /items/{id}` 用于管理 Item 字段。Item PATCH 不接受 visibility；请使用 `POST /items/{id}/visibility` 并传入 `{visibility:"public"|"private"}`。私密化转换具有事务性，并将所有关联 Note 设为私密。`POST /items/{id}/notes/set-public` 显式公开符合条件的关联 Note，并返回 `updated_count`、`blocked_count` 和 `blocked_note_ids`。海报上传/删除接口为 `PUT|DELETE /items/{id}/poster`；PUT 使用原始图片请求体，`Content-Type` 可以是 `image/png`、`image/jpeg` 或 `image/webp`。

`GET|POST /categories`、`PATCH|DELETE /categories/{id}` 以及 `GET|POST /tags`、`PATCH|DELETE /tags/{id}` 提供分类体系 CRUD。根分类不可变；自定义分类必须是根分类的直接子级。标签 slug 只生成一次，并保持稳定。

`GET|PATCH /settings` 用于管理站点标题/标语/时区、NOW 状态、About 源文/格式以及当前 Note ID。`GET /profile` 返回管理员信息。

## 渲染与静态页面

Markdown 由 `markdown-it-py` 渲染，Markdown 输出和 HTML 输入均由 `nh3` 清理。公共响应只暴露 `content_html_sanitized`；管理响应可以额外暴露 `content_raw`。静态页面绝不会以目录形式挂载，只有在完成 Note/Item 鉴权和路径校验后才会提供。
