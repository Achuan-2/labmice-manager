// Generated from backend/app/models/models.py.
export const schema = {
  "users": {
    "id": {
      "type": "Integer",
      "default": null
    },
    "username": {
      "type": "String",
      "default": null
    },
    "hashed_password": {
      "type": "String",
      "default": null
    },
    "role": {
      "type": "String",
      "default": "guest"
    },
    "display_name": {
      "type": "String",
      "default": ""
    },
    "is_active": {
      "type": "Boolean",
      "default": true
    },
    "created_at": {
      "type": "DateTime",
      "default": "$now"
    }
  },
  "system_settings": {
    "id": {
      "type": "Integer",
      "default": null
    },
    "key": {
      "type": "String",
      "default": null
    },
    "value": {
      "type": "String",
      "default": null
    },
    "updated_at": {
      "type": "DateTime",
      "default": "$now"
    }
  },
  "claimers": {
    "id": {
      "type": "Integer",
      "default": null
    },
    "name": {
      "type": "String",
      "default": null
    },
    "role": {
      "type": "String",
      "default": "学生"
    },
    "email": {
      "type": "String",
      "default": null
    },
    "phone": {
      "type": "String",
      "default": null
    },
    "color": {
      "type": "String",
      "default": "#2563eb"
    },
    "default_room": {
      "type": "String",
      "default": null
    },
    "notes": {
      "type": "Text",
      "default": null
    },
    "created_at": {
      "type": "DateTime",
      "default": "$now"
    }
  },
  "rooms": {
    "id": {
      "type": "Integer",
      "default": null
    },
    "name": {
      "type": "String",
      "default": null
    },
    "description": {
      "type": "String",
      "default": null
    },
    "category": {
      "type": "String",
      "default": null
    },
    "created_at": {
      "type": "DateTime",
      "default": "$now"
    }
  },
  "cages": {
    "id": {
      "type": "Integer",
      "default": null
    },
    "cage_code": {
      "type": "String",
      "default": null
    },
    "room": {
      "type": "String",
      "default": "默认鼠房"
    },
    "strain": {
      "type": "String",
      "default": ""
    },
    "gender": {
      "type": "String",
      "default": "M"
    },
    "cage_type": {
      "type": "String",
      "default": "常规笼"
    },
    "capacity": {
      "type": "Integer",
      "default": 5
    },
    "mating_date": {
      "type": "String",
      "default": null
    },
    "litter_birth_date": {
      "type": "String",
      "default": null
    },
    "litter_birth_dates": {
      "type": "JSON",
      "default": null
    },
    "observation": {
      "type": "Text",
      "default": null
    },
    "notes": {
      "type": "Text",
      "default": null
    },
    "created_at": {
      "type": "DateTime",
      "default": "$now"
    },
    "updated_at": {
      "type": "DateTime",
      "default": "$now"
    }
  },
  "todo_reminders": {
    "id": {
      "type": "Integer",
      "default": null
    },
    "title": {
      "type": "String",
      "default": null
    },
    "due_at": {
      "type": "String",
      "default": null
    },
    "notes": {
      "type": "Text",
      "default": null
    },
    "cage_id": {
      "type": "Integer",
      "default": null
    },
    "mouse_id": {
      "type": "Integer",
      "default": null
    },
    "cage_ids": {
      "type": "JSON",
      "default": null
    },
    "mouse_ids": {
      "type": "JSON",
      "default": null
    },
    "source": {
      "type": "String",
      "default": "manual"
    },
    "auto_key": {
      "type": "String",
      "default": null
    },
    "status": {
      "type": "String",
      "default": "pending"
    },
    "completed_at": {
      "type": "DateTime",
      "default": null
    },
    "created_at": {
      "type": "DateTime",
      "default": "$now"
    },
    "updated_at": {
      "type": "DateTime",
      "default": "$now"
    }
  },
  "mouse_statuses": {
    "id": {
      "type": "Integer",
      "default": null
    },
    "name": {
      "type": "String",
      "default": null
    },
    "is_system": {
      "type": "Boolean",
      "default": false
    },
    "removes_from_cage": {
      "type": "Boolean",
      "default": false
    },
    "sort_order": {
      "type": "Integer",
      "default": 0
    },
    "created_at": {
      "type": "DateTime",
      "default": "$now"
    },
    "updated_at": {
      "type": "DateTime",
      "default": "$now"
    }
  },
  "mice": {
    "id": {
      "type": "Integer",
      "default": null
    },
    "mouse_code": {
      "type": "String",
      "default": null
    },
    "cage_id": {
      "type": "Integer",
      "default": null
    },
    "strain": {
      "type": "String",
      "default": ""
    },
    "gender": {
      "type": "String",
      "default": "未知"
    },
    "dob": {
      "type": "String",
      "default": null
    },
    "parents": {
      "type": "String",
      "default": null
    },
    "genotype_1": {
      "type": "String",
      "default": null
    },
    "genotype_2": {
      "type": "String",
      "default": null
    },
    "test_date": {
      "type": "String",
      "default": null
    },
    "owner_id": {
      "type": "Integer",
      "default": null
    },
    "owner_name": {
      "type": "String",
      "default": null
    },
    "status": {
      "type": "String",
      "default": "在笼"
    },
    "claim_date": {
      "type": "String",
      "default": null
    },
    "claim_purpose": {
      "type": "String",
      "default": null
    },
    "source_room": {
      "type": "String",
      "default": null
    },
    "notes": {
      "type": "Text",
      "default": null
    },
    "created_at": {
      "type": "DateTime",
      "default": "$now"
    },
    "updated_at": {
      "type": "DateTime",
      "default": "$now"
    }
  },
  "genotype_records": {
    "id": {
      "type": "Integer",
      "default": null
    },
    "mouse_code": {
      "type": "String",
      "default": null
    },
    "mouse_id": {
      "type": "Integer",
      "default": null
    },
    "test_date": {
      "type": "String",
      "default": null
    },
    "strain": {
      "type": "String",
      "default": ""
    },
    "dob": {
      "type": "String",
      "default": null
    },
    "gender": {
      "type": "String",
      "default": null
    },
    "parents": {
      "type": "String",
      "default": null
    },
    "genotype_1": {
      "type": "String",
      "default": null
    },
    "genotype_2": {
      "type": "String",
      "default": null
    },
    "genotype_3": {
      "type": "String",
      "default": null
    },
    "op_record": {
      "type": "String",
      "default": null
    },
    "notes": {
      "type": "Text",
      "default": null
    },
    "created_at": {
      "type": "DateTime",
      "default": "$now"
    }
  },
  "transfer_requests": {
    "id": {
      "type": "Integer",
      "default": null
    },
    "seq": {
      "type": "String",
      "default": null
    },
    "request_date": {
      "type": "String",
      "default": null
    },
    "demander": {
      "type": "String",
      "default": null
    },
    "strain": {
      "type": "String",
      "default": null
    },
    "age_gender_req": {
      "type": "String",
      "default": null
    },
    "target_room": {
      "type": "String",
      "default": null
    },
    "cage_count": {
      "type": "Integer",
      "default": 1
    },
    "source_room": {
      "type": "String",
      "default": null
    },
    "mouse_gender": {
      "type": "String",
      "default": null
    },
    "mouse_codes": {
      "type": "Text",
      "default": null
    },
    "status": {
      "type": "String",
      "default": "申请中"
    },
    "feedback": {
      "type": "Text",
      "default": null
    },
    "handler": {
      "type": "String",
      "default": null
    },
    "created_at": {
      "type": "DateTime",
      "default": "$now"
    },
    "updated_at": {
      "type": "DateTime",
      "default": "$now"
    }
  },
  "transfer_request_assignments": {
    "id": {
      "type": "Integer",
      "default": null
    },
    "request_id": {
      "type": "Integer",
      "default": null
    },
    "mouse_id": {
      "type": "Integer",
      "default": null
    },
    "original_state": {
      "type": "JSON",
      "default": null
    },
    "assigned_state": {
      "type": "JSON",
      "default": null
    },
    "source_room": {
      "type": "String",
      "default": null
    },
    "source_cage": {
      "type": "String",
      "default": null
    }
  },
  "transfer_logs": {
    "id": {
      "type": "Integer",
      "default": null
    },
    "action_type": {
      "type": "String",
      "default": "设置领取人"
    },
    "mouse_codes": {
      "type": "Text",
      "default": null
    },
    "mouse_count": {
      "type": "Integer",
      "default": 1
    },
    "claimer_name": {
      "type": "String",
      "default": null
    },
    "source_room": {
      "type": "String",
      "default": null
    },
    "target_room": {
      "type": "String",
      "default": null
    },
    "source_cage": {
      "type": "String",
      "default": null
    },
    "target_cage": {
      "type": "String",
      "default": null
    },
    "operator": {
      "type": "String",
      "default": "admin"
    },
    "date": {
      "type": "String",
      "default": ""
    },
    "status": {
      "type": "String",
      "default": "已完成"
    },
    "notes": {
      "type": "Text",
      "default": null
    },
    "created_at": {
      "type": "DateTime",
      "default": "$now"
    }
  },
  "primers": {
    "id": {
      "type": "Integer",
      "default": null
    },
    "primer_no": {
      "type": "Integer",
      "default": null
    },
    "strain_short": {
      "type": "String",
      "default": ""
    },
    "strain_full": {
      "type": "String",
      "default": null
    },
    "source": {
      "type": "String",
      "default": null
    },
    "gene_type": {
      "type": "String",
      "default": null
    },
    "sequence": {
      "type": "Text",
      "default": null
    },
    "band_size": {
      "type": "String",
      "default": null
    },
    "url": {
      "type": "String",
      "default": null
    },
    "notes": {
      "type": "Text",
      "default": null
    },
    "created_at": {
      "type": "DateTime",
      "default": "$now"
    }
  },
  "strains": {
    "id": {
      "type": "Integer",
      "default": null
    },
    "name": {
      "type": "String",
      "default": null
    },
    "notes": {
      "type": "Text",
      "default": null
    },
    "created_at": {
      "type": "DateTime",
      "default": "$now"
    },
    "updated_at": {
      "type": "DateTime",
      "default": "$now"
    }
  }
};
export const createSql = "CREATE TABLE IF NOT EXISTS \"users\" (\n  \"id\" INTEGER PRIMARY KEY,\n  \"username\" TEXT NOT NULL UNIQUE,\n  \"hashed_password\" TEXT NOT NULL,\n  \"role\" TEXT NOT NULL,\n  \"display_name\" TEXT,\n  \"is_active\" INTEGER,\n  \"created_at\" TEXT\n);\n\nCREATE TABLE IF NOT EXISTS \"system_settings\" (\n  \"id\" INTEGER PRIMARY KEY,\n  \"key\" TEXT NOT NULL UNIQUE,\n  \"value\" TEXT NOT NULL,\n  \"updated_at\" TEXT\n);\n\nCREATE TABLE IF NOT EXISTS \"claimers\" (\n  \"id\" INTEGER PRIMARY KEY,\n  \"name\" TEXT NOT NULL UNIQUE,\n  \"role\" TEXT,\n  \"email\" TEXT,\n  \"phone\" TEXT,\n  \"color\" TEXT,\n  \"default_room\" TEXT,\n  \"notes\" TEXT,\n  \"created_at\" TEXT\n);\n\nCREATE TABLE IF NOT EXISTS \"rooms\" (\n  \"id\" INTEGER PRIMARY KEY,\n  \"name\" TEXT NOT NULL UNIQUE,\n  \"description\" TEXT,\n  \"category\" TEXT,\n  \"created_at\" TEXT\n);\n\nCREATE TABLE IF NOT EXISTS \"cages\" (\n  \"id\" INTEGER PRIMARY KEY,\n  \"cage_code\" TEXT NOT NULL,\n  \"room\" TEXT,\n  \"strain\" TEXT,\n  \"gender\" TEXT,\n  \"cage_type\" TEXT,\n  \"capacity\" INTEGER,\n  \"mating_date\" TEXT,\n  \"litter_birth_date\" TEXT,\n  \"litter_birth_dates\" TEXT,\n  \"observation\" TEXT,\n  \"notes\" TEXT,\n  \"created_at\" TEXT,\n  \"updated_at\" TEXT\n);\n\nCREATE TABLE IF NOT EXISTS \"todo_reminders\" (\n  \"id\" INTEGER PRIMARY KEY,\n  \"title\" TEXT NOT NULL,\n  \"due_at\" TEXT,\n  \"notes\" TEXT,\n  \"cage_id\" INTEGER REFERENCES \"cages\"(\"id\") ON DELETE SET NULL,\n  \"mouse_id\" INTEGER REFERENCES \"mice\"(\"id\") ON DELETE SET NULL,\n  \"cage_ids\" TEXT,\n  \"mouse_ids\" TEXT,\n  \"source\" TEXT,\n  \"auto_key\" TEXT UNIQUE,\n  \"status\" TEXT,\n  \"completed_at\" TEXT,\n  \"created_at\" TEXT,\n  \"updated_at\" TEXT\n);\n\nCREATE TABLE IF NOT EXISTS \"mouse_statuses\" (\n  \"id\" INTEGER PRIMARY KEY,\n  \"name\" TEXT NOT NULL UNIQUE,\n  \"is_system\" INTEGER NOT NULL,\n  \"removes_from_cage\" INTEGER NOT NULL,\n  \"sort_order\" INTEGER NOT NULL,\n  \"created_at\" TEXT,\n  \"updated_at\" TEXT\n);\n\nCREATE TABLE IF NOT EXISTS \"mice\" (\n  \"id\" INTEGER PRIMARY KEY,\n  \"mouse_code\" TEXT NOT NULL UNIQUE,\n  \"cage_id\" INTEGER REFERENCES \"cages\"(\"id\") ON DELETE SET NULL,\n  \"strain\" TEXT,\n  \"gender\" TEXT,\n  \"dob\" TEXT,\n  \"parents\" TEXT,\n  \"genotype_1\" TEXT,\n  \"genotype_2\" TEXT,\n  \"test_date\" TEXT,\n  \"owner_id\" INTEGER REFERENCES \"claimers\"(\"id\") ON DELETE SET NULL,\n  \"owner_name\" TEXT,\n  \"status\" TEXT,\n  \"claim_date\" TEXT,\n  \"claim_purpose\" TEXT,\n  \"source_room\" TEXT,\n  \"notes\" TEXT,\n  \"created_at\" TEXT,\n  \"updated_at\" TEXT\n);\n\nCREATE TABLE IF NOT EXISTS \"genotype_records\" (\n  \"id\" INTEGER PRIMARY KEY,\n  \"mouse_code\" TEXT NOT NULL,\n  \"mouse_id\" INTEGER REFERENCES \"mice\"(\"id\") ON DELETE CASCADE,\n  \"test_date\" TEXT,\n  \"strain\" TEXT,\n  \"dob\" TEXT,\n  \"gender\" TEXT,\n  \"parents\" TEXT,\n  \"genotype_1\" TEXT,\n  \"genotype_2\" TEXT,\n  \"genotype_3\" TEXT,\n  \"op_record\" TEXT,\n  \"notes\" TEXT,\n  \"created_at\" TEXT\n);\n\nCREATE TABLE IF NOT EXISTS \"transfer_requests\" (\n  \"id\" INTEGER PRIMARY KEY,\n  \"seq\" TEXT,\n  \"request_date\" TEXT NOT NULL,\n  \"demander\" TEXT NOT NULL,\n  \"strain\" TEXT NOT NULL,\n  \"age_gender_req\" TEXT,\n  \"target_room\" TEXT,\n  \"cage_count\" INTEGER,\n  \"source_room\" TEXT,\n  \"mouse_gender\" TEXT,\n  \"mouse_codes\" TEXT,\n  \"status\" TEXT,\n  \"feedback\" TEXT,\n  \"handler\" TEXT,\n  \"created_at\" TEXT,\n  \"updated_at\" TEXT\n);\n\nCREATE TABLE IF NOT EXISTS \"transfer_request_assignments\" (\n  \"id\" INTEGER PRIMARY KEY,\n  \"request_id\" INTEGER NOT NULL REFERENCES \"transfer_requests\"(\"id\") ON DELETE CASCADE,\n  \"mouse_id\" INTEGER NOT NULL UNIQUE REFERENCES \"mice\"(\"id\") ON DELETE CASCADE,\n  \"original_state\" TEXT NOT NULL,\n  \"assigned_state\" TEXT NOT NULL,\n  \"source_room\" TEXT,\n  \"source_cage\" TEXT\n);\n\nCREATE TABLE IF NOT EXISTS \"transfer_logs\" (\n  \"id\" INTEGER PRIMARY KEY,\n  \"action_type\" TEXT,\n  \"mouse_codes\" TEXT NOT NULL,\n  \"mouse_count\" INTEGER,\n  \"claimer_name\" TEXT,\n  \"source_room\" TEXT,\n  \"target_room\" TEXT,\n  \"source_cage\" TEXT,\n  \"target_cage\" TEXT,\n  \"operator\" TEXT,\n  \"date\" TEXT,\n  \"status\" TEXT,\n  \"notes\" TEXT,\n  \"created_at\" TEXT\n);\n\nCREATE TABLE IF NOT EXISTS \"primers\" (\n  \"id\" INTEGER PRIMARY KEY,\n  \"primer_no\" INTEGER,\n  \"strain_short\" TEXT,\n  \"strain_full\" TEXT,\n  \"source\" TEXT,\n  \"gene_type\" TEXT,\n  \"sequence\" TEXT,\n  \"band_size\" TEXT,\n  \"url\" TEXT,\n  \"notes\" TEXT,\n  \"created_at\" TEXT\n);\n\nCREATE TABLE IF NOT EXISTS \"strains\" (\n  \"id\" INTEGER PRIMARY KEY,\n  \"name\" TEXT NOT NULL UNIQUE,\n  \"notes\" TEXT,\n  \"created_at\" TEXT,\n  \"updated_at\" TEXT\n);\n\nCREATE INDEX IF NOT EXISTS \"ix_users_username\" ON \"users\"(\"username\");\n\nCREATE INDEX IF NOT EXISTS \"ix_system_settings_key\" ON \"system_settings\"(\"key\");\n\nCREATE INDEX IF NOT EXISTS \"ix_claimers_name\" ON \"claimers\"(\"name\");\n\nCREATE INDEX IF NOT EXISTS \"ix_rooms_name\" ON \"rooms\"(\"name\");\n\nCREATE INDEX IF NOT EXISTS \"ix_cages_cage_code\" ON \"cages\"(\"cage_code\");\n\nCREATE INDEX IF NOT EXISTS \"ix_cages_room\" ON \"cages\"(\"room\");\n\nCREATE INDEX IF NOT EXISTS \"ix_todo_reminders_due_at\" ON \"todo_reminders\"(\"due_at\");\n\nCREATE INDEX IF NOT EXISTS \"ix_todo_reminders_cage_id\" ON \"todo_reminders\"(\"cage_id\");\n\nCREATE INDEX IF NOT EXISTS \"ix_todo_reminders_mouse_id\" ON \"todo_reminders\"(\"mouse_id\");\n\nCREATE INDEX IF NOT EXISTS \"ix_todo_reminders_source\" ON \"todo_reminders\"(\"source\");\n\nCREATE INDEX IF NOT EXISTS \"ix_todo_reminders_auto_key\" ON \"todo_reminders\"(\"auto_key\");\n\nCREATE INDEX IF NOT EXISTS \"ix_todo_reminders_status\" ON \"todo_reminders\"(\"status\");\n\nCREATE INDEX IF NOT EXISTS \"ix_mouse_statuses_name\" ON \"mouse_statuses\"(\"name\");\n\nCREATE INDEX IF NOT EXISTS \"ix_mice_mouse_code\" ON \"mice\"(\"mouse_code\");\n\nCREATE INDEX IF NOT EXISTS \"ix_mice_cage_id\" ON \"mice\"(\"cage_id\");\n\nCREATE INDEX IF NOT EXISTS \"ix_mice_strain\" ON \"mice\"(\"strain\");\n\nCREATE INDEX IF NOT EXISTS \"ix_mice_dob\" ON \"mice\"(\"dob\");\n\nCREATE INDEX IF NOT EXISTS \"ix_mice_owner_id\" ON \"mice\"(\"owner_id\");\n\nCREATE INDEX IF NOT EXISTS \"ix_mice_owner_name\" ON \"mice\"(\"owner_name\");\n\nCREATE INDEX IF NOT EXISTS \"ix_mice_status\" ON \"mice\"(\"status\");\n\nCREATE INDEX IF NOT EXISTS \"ix_mice_source_room\" ON \"mice\"(\"source_room\");\n\nCREATE INDEX IF NOT EXISTS \"ix_genotype_records_mouse_code\" ON \"genotype_records\"(\"mouse_code\");\n\nCREATE INDEX IF NOT EXISTS \"ix_genotype_records_mouse_id\" ON \"genotype_records\"(\"mouse_id\");\n\nCREATE INDEX IF NOT EXISTS \"ix_genotype_records_test_date\" ON \"genotype_records\"(\"test_date\");\n\nCREATE INDEX IF NOT EXISTS \"ix_genotype_records_strain\" ON \"genotype_records\"(\"strain\");\n\nCREATE INDEX IF NOT EXISTS \"ix_transfer_requests_seq\" ON \"transfer_requests\"(\"seq\");\n\nCREATE INDEX IF NOT EXISTS \"ix_transfer_requests_request_date\" ON \"transfer_requests\"(\"request_date\");\n\nCREATE INDEX IF NOT EXISTS \"ix_transfer_requests_demander\" ON \"transfer_requests\"(\"demander\");\n\nCREATE INDEX IF NOT EXISTS \"ix_transfer_requests_strain\" ON \"transfer_requests\"(\"strain\");\n\nCREATE INDEX IF NOT EXISTS \"ix_transfer_requests_target_room\" ON \"transfer_requests\"(\"target_room\");\n\nCREATE INDEX IF NOT EXISTS \"ix_transfer_requests_status\" ON \"transfer_requests\"(\"status\");\n\nCREATE INDEX IF NOT EXISTS \"ix_transfer_request_assignments_request_id\" ON \"transfer_request_assignments\"(\"request_id\");\n\nCREATE INDEX IF NOT EXISTS \"ix_transfer_logs_action_type\" ON \"transfer_logs\"(\"action_type\");\n\nCREATE INDEX IF NOT EXISTS \"ix_transfer_logs_claimer_name\" ON \"transfer_logs\"(\"claimer_name\");\n\nCREATE INDEX IF NOT EXISTS \"ix_transfer_logs_date\" ON \"transfer_logs\"(\"date\");\n\nCREATE INDEX IF NOT EXISTS \"ix_primers_strain_short\" ON \"primers\"(\"strain_short\");\n\nCREATE INDEX IF NOT EXISTS \"ix_strains_name\" ON \"strains\"(\"name\");";
