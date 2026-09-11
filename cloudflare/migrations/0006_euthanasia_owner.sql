INSERT INTO claimers (id, name, role, color, notes, created_at)
SELECT COALESCE(MAX(id), 0) + 1,
       '安乐死',
       '其他',
       '#6b7280',
       '系统默认领取人；选择后小鼠状态自动变为死亡',
       datetime('now')
FROM claimers
HAVING NOT EXISTS (SELECT 1 FROM claimers WHERE name = '安乐死');

UPDATE mice
SET owner_id = (SELECT id FROM claimers WHERE name = '安乐死'),
    owner_name = '安乐死',
    status = '死亡',
    cage_id = NULL
WHERE owner_name = '安乐死'
   OR owner_id = (SELECT id FROM claimers WHERE name = '安乐死');
