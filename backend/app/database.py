import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

# Path to database file inside data/ directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data"))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "mouse-manager.db")
LEGACY_DB_PATH = os.path.join(DATA_DIR, "mouse_lab.db")

# Keep existing Docker/NAS installations intact when upgrading from the old
# database filename. This runs before SQLAlchemy opens the database.
if not os.path.exists(DB_PATH) and os.path.exists(LEGACY_DB_PATH):
    os.replace(LEGACY_DB_PATH, DB_PATH)
    for suffix in ("-wal", "-shm"):
        legacy_sidecar = LEGACY_DB_PATH + suffix
        if os.path.exists(legacy_sidecar):
            os.replace(legacy_sidecar, DB_PATH + suffix)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# Enable SQLite WAL mode and foreign key constraints
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA cache_size=-64000")  # 64MB memory page cache
    cursor.execute("PRAGMA temp_store=MEMORY")  # Store temporary tables & indices in RAM
    cursor.execute("PRAGMA mmap_size=268435456")  # 256MB memory-mapped I/O
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

AUTH_TABLE_NAMES = frozenset({'users', 'system_settings'})


def get_business_tables():
    """Return tables stored in the mouse business database."""
    return [
        table for table in Base.metadata.sorted_tables
        if table.name not in AUTH_TABLE_NAMES
    ]


def create_business_tables():
    Base.metadata.create_all(bind=engine, tables=get_business_tables())


def migrate_room_category():
    with engine.begin() as connection:
        columns = connection.exec_driver_sql("PRAGMA table_info(rooms)").fetchall()
        if columns and not any(column[1] == "category" for column in columns):
            connection.exec_driver_sql("ALTER TABLE rooms ADD COLUMN category VARCHAR(32)")


def migrate_todo_fields():
    with engine.begin() as connection:
        cage_columns = connection.exec_driver_sql("PRAGMA table_info(cages)").fetchall()
        if cage_columns and not any(column[1] == "litter_birth_date" for column in cage_columns):
            connection.exec_driver_sql("ALTER TABLE cages ADD COLUMN litter_birth_date VARCHAR(32)")
        cage_columns = connection.exec_driver_sql("PRAGMA table_info(cages)").fetchall()
        if cage_columns and not any(column[1] == "litter_birth_dates" for column in cage_columns):
            connection.exec_driver_sql("ALTER TABLE cages ADD COLUMN litter_birth_dates JSON")
        connection.exec_driver_sql(
            "UPDATE cages SET litter_birth_dates=json_array(litter_birth_date) "
            "WHERE litter_birth_date IS NOT NULL AND litter_birth_date!='' "
            "AND (litter_birth_dates IS NULL OR litter_birth_dates='')"
        )
        todo_columns = connection.exec_driver_sql("PRAGMA table_info(todo_reminders)").fetchall()
        if todo_columns and not any(column[1] == "cage_ids" for column in todo_columns):
            connection.exec_driver_sql("ALTER TABLE todo_reminders ADD COLUMN cage_ids JSON")
        todo_columns = connection.exec_driver_sql("PRAGMA table_info(todo_reminders)").fetchall()
        if todo_columns and not any(column[1] == "mouse_ids" for column in todo_columns):
            connection.exec_driver_sql("ALTER TABLE todo_reminders ADD COLUMN mouse_ids JSON")
        connection.exec_driver_sql(
            "UPDATE todo_reminders SET cage_ids=json_array(cage_id) "
            "WHERE cage_id IS NOT NULL AND (cage_ids IS NULL OR cage_ids='')"
        )
        connection.exec_driver_sql(
            "UPDATE todo_reminders SET mouse_ids=json_array(mouse_id) "
            "WHERE mouse_id IS NOT NULL AND (mouse_ids IS NULL OR mouse_ids='')"
        )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
