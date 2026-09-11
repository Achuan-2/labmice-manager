CREATE TABLE IF NOT EXISTS _login_attempts (
  key TEXT NOT NULL,
  window INTEGER NOT NULL,
  attempts INTEGER NOT NULL,
  PRIMARY KEY (key, window)
);
CREATE TABLE IF NOT EXISTS _backups (
  backup_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  table_name TEXT NOT NULL,
  chunk_no INTEGER NOT NULL,
  rows_json TEXT NOT NULL,
  PRIMARY KEY (backup_id, table_name, chunk_no)
);
