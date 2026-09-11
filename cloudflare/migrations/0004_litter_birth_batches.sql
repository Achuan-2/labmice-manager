ALTER TABLE cages ADD COLUMN litter_birth_dates TEXT;

UPDATE cages
SET litter_birth_dates = json_array(litter_birth_date)
WHERE litter_birth_date IS NOT NULL
  AND litter_birth_date != ''
  AND (litter_birth_dates IS NULL OR litter_birth_dates = '');
