import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.database import SessionLocal, BASE_DIR, create_business_tables, migrate_room_category, migrate_todo_fields
from backend.app.auth_database import AuthSessionLocal, initialize_auth_database
from backend.app.models.models import Mouse, User, SystemSetting, Claimer, Room
from backend.app.auth import init_default_admin
from backend.app.services.database_backup import DatabaseMaintenanceMiddleware
from backend.app.services.importer import (
    cleanup_synthetic_room_imports,
    cleanup_invalid_genotype_mice,
    import_local_excel_folder,
    remove_inferred_parent_placeholders,
)

from backend.app.routers import (
    auth,
    mice,
    cages,
    claimers,
    transfers,
    primers,
    stats,
    import_export,
    transfer_requests,
    genotypes,
    strains,
    mouse_statuses,
    todos,
    settings,
)
from backend.app.services.strain_service import sync_and_normalize_all_strains
from backend.app.services.mouse_status_service import sync_mouse_statuses
from backend.app.services.owner_service import sync_euthanasia_owner
from backend.app.services.settings_service import get_public_settings

# Create database tables
create_business_tables()
initialize_auth_database(User.__table__, (SystemSetting.__table__,))
migrate_room_category()
migrate_todo_fields()

app = FastAPI(
    title="课题组小鼠管理系统",
    description="支持小鼠笼位、小鼠信息、领取人、基因型鉴定与转鼠需求联动管理",
    version="1.1.0",
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enable automatic GZip response compression for JSON payloads and assets > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(DatabaseMaintenanceMiddleware)

# Startup event: ensure the default admin and auto-seed Excel data if empty
@app.on_event("startup")
def startup_event():
    auth_db = AuthSessionLocal()
    db = SessionLocal()
    try:
        init_default_admin(auth_db)
        
        mouse_count = db.query(Mouse).count()
        if mouse_count == 0:
            excel_dir = os.path.join(BASE_DIR, "excel")
            if os.path.exists(excel_dir):
                print("Database is empty. Automatically importing from excel/ folder...")
                res = import_local_excel_folder(db, excel_dir)
                print(f"Auto-import finished: {res}")

        removed_placeholders = remove_inferred_parent_placeholders(db)
        if removed_placeholders:
            print(f"Removed {removed_placeholders} inferred parent placeholder mouse records.")

        synthetic_cleanup = cleanup_synthetic_room_imports(db)
        if any(synthetic_cleanup.values()):
            print(f"Cleaned synthetic historical room imports: {synthetic_cleanup}")

        invalid_mice_cleanup = cleanup_invalid_genotype_mice(db)
        if any(invalid_mice_cleanup.values()):
            print(f"Cleaned invalid genotype mice: {invalid_mice_cleanup}")
        
        # Merge case discrepancies for existing strains
        sync_and_normalize_all_strains(db)
        sync_mouse_statuses(db)
        sync_euthanasia_owner(db)
        db.query(Room).filter(Room.category == "使用鼠房").update(
            {"category": "实验鼠房"}, synchronize_session=False
        )
        db.query(Claimer).filter(Claimer.role == "实验管家").update({"role": "管家"})
        db.commit()
        
        print("\n" + "=" * 60)
        print(f"🚀 {get_public_settings(auth_db)['system_name']}已准备就绪！")
        print("👉 本机浏览器访问地址: http://localhost:8000  (或 http://127.0.0.1:8000)")
        print("⚠️ 提示: Windows浏览器不支持访问 0.0.0.0，请勿在浏览器输入 http://0.0.0.0:8000")
        print("=" * 60 + "\n")
    finally:
        db.close()
        auth_db.close()

# Register API Routers
app.include_router(auth.router)
app.include_router(settings.router)
app.include_router(mice.router)
app.include_router(strains.router)
app.include_router(mouse_statuses.router)
app.include_router(todos.router)
app.include_router(cages.router)
app.include_router(claimers.router, prefix="/api/members", tags=["Members"])
app.include_router(claimers.router, prefix="/api/claimers", tags=["Claimers"])
app.include_router(transfers.router)
app.include_router(transfer_requests.router)
app.include_router(genotypes.router)
app.include_router(primers.router)
app.include_router(stats.router)
app.include_router(import_export.router)

@app.get("/api/health")
def health_check():
    with AuthSessionLocal() as db:
        system_name = get_public_settings(db)["system_name"]
    return {"status": "ok", "system": system_name, "version": "1.1.0"}

# Mount frontend static distribution if built
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")
if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API 接口未找到")
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            if full_path.startswith("assets/"):
                return FileResponse(
                    file_path,
                    headers={"Cache-Control": "public, max-age=31536000, immutable"}
                )
            return FileResponse(file_path)
        return FileResponse(
            os.path.join(FRONTEND_DIST, "index.html"),
            headers={"Cache-Control": "no-cache"}
        )
