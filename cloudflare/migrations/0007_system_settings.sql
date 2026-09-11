CREATE TABLE IF NOT EXISTS system_settings (
  id INTEGER PRIMARY KEY,
  key TEXT NOT NULL UNIQUE,
  value TEXT NOT NULL,
  updated_at TEXT
);

CREATE INDEX IF NOT EXISTS ix_system_settings_key ON system_settings(key);

CREATE TRIGGER IF NOT EXISTS revision_system_settings_insert AFTER INSERT ON system_settings
BEGIN UPDATE _revision SET value=value+1 WHERE id=1; END;
CREATE TRIGGER IF NOT EXISTS revision_system_settings_update AFTER UPDATE ON system_settings
BEGIN UPDATE _revision SET value=value+1 WHERE id=1; END;
CREATE TRIGGER IF NOT EXISTS revision_system_settings_delete AFTER DELETE ON system_settings
BEGIN UPDATE _revision SET value=value+1 WHERE id=1; END;
