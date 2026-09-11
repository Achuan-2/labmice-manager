ALTER TABLE todo_reminders ADD COLUMN cage_ids TEXT;
ALTER TABLE todo_reminders ADD COLUMN mouse_ids TEXT;

UPDATE todo_reminders
SET cage_ids = json_array(cage_id)
WHERE cage_id IS NOT NULL AND (cage_ids IS NULL OR cage_ids = '');

UPDATE todo_reminders
SET mouse_ids = json_array(mouse_id)
WHERE mouse_id IS NOT NULL AND (mouse_ids IS NULL OR mouse_ids = '');
