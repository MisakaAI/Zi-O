CREATE TABLE content_images (
  id TEXT PRIMARY KEY,
  storage_path TEXT NOT NULL UNIQUE,
  media_type TEXT NOT NULL CHECK (media_type IN ('image/png', 'image/jpeg', 'image/webp')),
  created_at INTEGER NOT NULL
);

CREATE TABLE note_images (
  note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
  image_id TEXT NOT NULL REFERENCES content_images(id) ON DELETE CASCADE,
  PRIMARY KEY(note_id, image_id)
);
CREATE INDEX note_images_image_idx ON note_images(image_id, note_id);
