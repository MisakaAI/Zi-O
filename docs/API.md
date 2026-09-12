# ZI/O v0.1 API

All JSON timestamps are UTC ISO 8601 (`2024-01-01T00:00:00.000Z`); SQLite stores Unix milliseconds. Errors always have this shape:

```json
{"error":{"code":"stable_code","message":"human-readable message","details":{}}}
```

Public unauthorized/private resources return `404` without revealing whether a record exists. JSON request bodies reject unknown fields. Limits include title 200, body 1 MiB, static path 512, tags 64, metadata 16 KiB, timeline default 20/max 50, poster 5 MiB.

## Authentication

- `POST /api/auth/login` body `{username,password}`. Sets an HttpOnly, SameSite=Lax `zio_session` cookie (Secure in production).
- `POST /api/auth/logout` clears the cookie.
- `GET /api/auth/me` returns `{user:null}` or `{user:{id,username,nickname,display_name}}`.

Login and all state-changing endpoints require an Origin/Referer matching `ZIO_PUBLIC_ORIGIN`.

## Public API

- `GET /api/public/site` returns title, tagline, timezone, status and sanitized About HTML.
- `GET /api/public/now` returns server time, timezone, status, optional manually selected `current_signal`, and today's (or five most recent) public notes.
- `GET /api/public/timeline?cursor=&limit=&category=&tag=&item_id=` returns `{items,next_cursor}`. Ordering is `(started_at DESC,id DESC)`. Cursor is signed, opaque, query-scoped, and must not be edited.
- `GET /api/public/notes/{id}` returns a sanitized Note detail.
- `GET /api/public/items?category=` returns public Items ordered by visible associated activity.
- `GET /api/public/items/{id}?cursor=&limit=` returns an Item and its public Note timeline.
- `GET /api/public/items/{id}/poster` returns a poster only for a public Item.
- `GET /api/public/tags/{slug}?cursor=&limit=` returns a Tag and its public timeline.
- `GET /api/public/index` returns public category, tag and Item indexes.

Public Note visibility requires both `notes.visibility='public'` and every associated Item to be public. This condition is applied to every public query, including counts and activity timestamps.

## Management API

All `/api/manage/*` endpoints require the administrator session. `GET /notes?cursor=&limit=` returns `{items,next_cursor}` in `(started_at DESC,id DESC)` order; its signed cursor is opaque and reaches older records without changing sort order. `POST /notes` and `GET|PATCH|DELETE /notes/{id}` use `NoteWrite`/`NotePatch`:

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

`started_at` may be omitted on create to use the current UTC time; when supplied it must include a timezone.

On PATCH, an association field is replaced only when present; omitted fields remain unchanged. Categories must contain exactly one primary; omitted/empty categories select JOURNAL. A public Note cannot be linked to a private Item.

`GET|POST /items`, `GET|PATCH|DELETE /items/{id}` manage Item fields. Item PATCH does not accept visibility; use `POST /items/{id}/visibility` with `{visibility:"public"|"private"}`. Private transition is transactional and privatizes all linked Notes. `POST /items/{id}/notes/set-public` explicitly publishes eligible linked Notes and reports `updated_count`, `blocked_count`, and `blocked_note_ids`. Poster upload/delete are `PUT|DELETE /items/{id}/poster`; PUT sends a raw image body with `Content-Type: image/png`, `image/jpeg`, or `image/webp`.

`GET|POST /categories`, `PATCH|DELETE /categories/{id}` and `GET|POST /tags`, `PATCH|DELETE /tags/{id}` provide taxonomy CRUD. Root categories are immutable; custom categories must be direct children of a root. Tag slugs are generated once and remain stable.

`GET|PATCH /settings` manages site title/tagline/timezone, NOW status, About source/format and current Note ID. `GET /profile` returns the administrator.

## Rendering and static pages

Markdown is rendered by `markdown-it-py` and both Markdown output and HTML input are cleaned by `nh3`. Public responses expose only `content_html_sanitized`; management responses may additionally expose `content_raw`. Static pages are never mounted as a directory and are served only after Note/Item authorization and path validation.
