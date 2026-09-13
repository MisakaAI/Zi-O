-- 初始数据库结构：建立单用户认证、站点设置、Note/Item 领域及多对多关联。

-- 管理员账户和服务端会话；数据库只保存密码材料和会话令牌哈希。
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  nickname TEXT NOT NULL DEFAULT '',
  password_hash BLOB NOT NULL,
  password_salt BLOB NOT NULL,
  password_iterations INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token_hash BLOB NOT NULL UNIQUE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX sessions_expiry_idx ON sessions(expires_at);

-- 单行站点设置；current_note_id 用于 NOW 页面展示当前 signal。
CREATE TABLE settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  site_title TEXT NOT NULL DEFAULT 'ZI/O',
  site_tagline TEXT NOT NULL DEFAULT '',
  timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
  now_status TEXT NOT NULL DEFAULT '',
  about_raw TEXT NOT NULL DEFAULT '',
  about_format TEXT NOT NULL DEFAULT 'markdown' CHECK (about_format IN ('markdown', 'html')),
  current_note_id INTEGER REFERENCES notes(id) ON DELETE SET NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE counters (
  name TEXT PRIMARY KEY,
  value INTEGER NOT NULL CHECK (value >= 0)
);
INSERT INTO counters(name, value) VALUES ('archive_no', 0);

-- 分类树：五个根分类稳定，用户只能在根分类下增加子分类。
CREATE TABLE categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  parent_id INTEGER REFERENCES categories(id) ON DELETE RESTRICT,
  is_root INTEGER NOT NULL DEFAULT 0 CHECK (is_root IN (0, 1)),
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  archive_no INTEGER NOT NULL UNIQUE,
  title TEXT NOT NULL DEFAULT '',
  content_raw TEXT NOT NULL DEFAULT '',
  content_format TEXT NOT NULL CHECK (content_format IN ('markdown', 'html')),
  started_at INTEGER NOT NULL,
  ended_at INTEGER,
  visibility TEXT NOT NULL CHECK (visibility IN ('public', 'private')),
  static_path TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  CHECK (ended_at IS NULL OR ended_at >= started_at)
);
CREATE INDEX notes_timeline_idx ON notes(started_at DESC, id DESC);

-- Note 的分类关联；is_primary 保证业务层可以明确主分类。
CREATE TABLE note_categories (
  note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
  category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
  is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
  PRIMARY KEY(note_id, category_id)
);
CREATE INDEX note_categories_category_idx ON note_categories(category_id, note_id);

-- 长期档案 Item 及其分类专属 JSON 元数据。
CREATE TABLE items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
  title TEXT NOT NULL,
  subtitle TEXT NOT NULL DEFAULT '',
  creator TEXT NOT NULL DEFAULT '',
  poster_path TEXT,
  visibility TEXT NOT NULL CHECK (visibility IN ('public', 'private')),
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX items_category_idx ON items(category_id, updated_at DESC);

-- Note 与 Item 的多对多关联，并保存章节、版本、进度等上下文。
CREATE TABLE note_items (
  note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
  item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  context_label TEXT,
  progress_text TEXT,
  PRIMARY KEY(note_id, item_id)
);
CREATE INDEX note_items_item_idx ON note_items(item_id, note_id);

-- 普通标签及 Note-Tag 多对多关联；name_key 和 slug 都必须唯一。
CREATE TABLE tags (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  name_key TEXT NOT NULL UNIQUE,
  slug TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE note_tags (
  note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
  tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY(note_id, tag_id)
);
CREATE INDEX note_tags_tag_idx ON note_tags(tag_id, note_id);

INSERT INTO categories(code, name, is_root, sort_order, created_at, updated_at)
VALUES
  ('JOURNAL', 'Journal', 1, 0, 0, 0),
  ('BOOK', 'Books', 1, 1, 0, 0),
  ('MOVIE', 'Movies', 1, 2, 0, 0),
  ('GAME', 'Games', 1, 3, 0, 0),
  ('PROJECT', 'Project', 1, 4, 0, 0);

INSERT INTO settings(id, updated_at) VALUES (1, 0);
