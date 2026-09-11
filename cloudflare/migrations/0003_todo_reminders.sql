ALTER TABLE cages ADD COLUMN litter_birth_date TEXT;

CREATE TABLE IF NOT EXISTS todo_reminders (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  due_at TEXT,
  notes TEXT,
  cage_id INTEGER REFERENCES cages(id) ON DELETE SET NULL,
  mouse_id INTEGER REFERENCES mice(id) ON DELETE SET NULL,
  source TEXT,
  auto_key TEXT UNIQUE,
  status TEXT,
  completed_at TEXT,
  created_at TEXT,
  updated_at TEXT
);

CREATE INDEX IF NOT EXISTS ix_todo_reminders_due_at ON todo_reminders(due_at);
CREATE INDEX IF NOT EXISTS ix_todo_reminders_cage_id ON todo_reminders(cage_id);
CREATE INDEX IF NOT EXISTS ix_todo_reminders_mouse_id ON todo_reminders(mouse_id);
CREATE INDEX IF NOT EXISTS ix_todo_reminders_source ON todo_reminders(source);
CREATE INDEX IF NOT EXISTS ix_todo_reminders_auto_key ON todo_reminders(auto_key);
CREATE INDEX IF NOT EXISTS ix_todo_reminders_status ON todo_reminders(status);

CREATE TRIGGER IF NOT EXISTS revision_todo_reminders_insert AFTER INSERT ON todo_reminders BEGIN UPDATE _revision SET value=value+1 WHERE id=1; END;
CREATE TRIGGER IF NOT EXISTS revision_todo_reminders_update AFTER UPDATE ON todo_reminders BEGIN UPDATE _revision SET value=value+1 WHERE id=1; END;
CREATE TRIGGER IF NOT EXISTS revision_todo_reminders_delete AFTER DELETE ON todo_reminders BEGIN UPDATE _revision SET value=value+1 WHERE id=1; END;
