from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

# --- Auth & User ---
class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "admin"
    display_name: Optional[str] = ""

class UserUpdatePassword(BaseModel):
    old_password: Optional[str] = None
    new_password: str

class UserUpdateDisplayName(BaseModel):
    display_name: str

class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    display_name: Optional[str] = ""
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# --- Genotype Records ---
class GenotypeRecordBase(BaseModel):
    mouse_code: str
    mouse_id: Optional[int] = None
    test_date: Optional[str] = None
    strain: Optional[str] = ""
    dob: Optional[str] = None
    gender: Optional[str] = None
    parents: Optional[str] = None
    genotype_1: Optional[str] = None
    genotype_2: Optional[str] = None
    genotype_3: Optional[str] = None
    op_record: Optional[str] = None
    notes: Optional[str] = None

class GenotypeRecordCreate(GenotypeRecordBase):
    pass

class GenotypeRecordUpdate(BaseModel):
    test_date: Optional[str] = None
    strain: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    parents: Optional[str] = None
    genotype_1: Optional[str] = None
    genotype_2: Optional[str] = None
    genotype_3: Optional[str] = None
    op_record: Optional[str] = None
    notes: Optional[str] = None

class GenotypeRecordResponse(GenotypeRecordBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- Claimer / Member ---
class ClaimerBase(BaseModel):
    name: str
    role: Optional[str] = "学生"
    email: Optional[str] = None
    phone: Optional[str] = None
    color: Optional[str] = "#2563eb"
    default_room: Optional[str] = None
    notes: Optional[str] = None

class ClaimerCreate(ClaimerBase):
    pass

class ClaimerUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    color: Optional[str] = None
    default_room: Optional[str] = None
    notes: Optional[str] = None

class ClaimerResponse(ClaimerBase):
    id: int
    created_at: Optional[datetime] = None
    mouse_count: Optional[int] = 0

    class Config:
        from_attributes = True

# --- Mouse ---
class MouseBase(BaseModel):
    mouse_code: str
    strain: Optional[str] = ""
    gender: Optional[str] = "未知"
    dob: Optional[str] = None
    parents: Optional[str] = None
    genotype_1: Optional[str] = None
    genotype_2: Optional[str] = None
    test_date: Optional[str] = None
    cage_id: Optional[int] = None
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    status: Optional[str] = "在笼"
    claim_date: Optional[str] = None
    claim_purpose: Optional[str] = None
    source_room: Optional[str] = None
    notes: Optional[str] = None

class MouseCreate(MouseBase):
    cage_code: Optional[str] = None

class MouseUpdate(BaseModel):
    mouse_code: Optional[str] = None
    strain: Optional[str] = None
    gender: Optional[str] = None
    dob: Optional[str] = None
    parents: Optional[str] = None
    genotype_1: Optional[str] = None
    genotype_2: Optional[str] = None
    test_date: Optional[str] = None
    cage_id: Optional[int] = None
    cage_code: Optional[str] = None
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    status: Optional[str] = None
    claim_date: Optional[str] = None
    claim_purpose: Optional[str] = None
    source_room: Optional[str] = None
    notes: Optional[str] = None

class MouseResponse(MouseBase):
    id: int
    cage_code: Optional[str] = None
    cage_room: Optional[str] = None
    age_days: Optional[int] = None
    age_weeks: Optional[float] = None
    genotypes: List[GenotypeRecordResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ParentsParseRequest(BaseModel):
    parents: str

# Batch Operations
class MouseBatchSetOwner(BaseModel):
    mouse_ids: Optional[List[int]] = None
    mouse_codes: Optional[List[str]] = None
    owner_name: str
    claim_date: Optional[str] = None
    claim_purpose: Optional[str] = None
    target_room: Optional[str] = None
    target_cage_code: Optional[str] = None
    status: Optional[str] = "已领用"

class MouseBatchTransfer(BaseModel):
    mouse_ids: Optional[List[int]] = None
    mouse_codes: Optional[List[str]] = None
    target_room: str
    target_cage_code: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class MouseSplitTransferGroup(BaseModel):
    mouse_ids: List[int]
    target_room: str
    target_cage_code: str


class MouseBatchSplitTransfer(BaseModel):
    groups: List[MouseSplitTransferGroup]
    notes: Optional[str] = None

class MouseBatchUpdateStatus(BaseModel):
    mouse_ids: List[int]
    status: str
    notes: Optional[str] = None

class MouseBatchUpdateFields(BaseModel):
    mouse_ids: List[int]
    dob: Optional[str] = None
    gender: Optional[str] = None
    strain: Optional[str] = None

class MouseStatusCreate(BaseModel):
    name: str

class MouseStatusUpdate(BaseModel):
    name: str

class MouseStatusDelete(BaseModel):
    replacement_status: Optional[str] = None

class MouseBatchCreate(BaseModel):
    mouse_codes: List[str]
    strain: Optional[str] = ""
    gender: Optional[str] = "M"
    dob: Optional[str] = None
    parents: Optional[str] = None
    genotype_1: Optional[str] = None
    source_room: Optional[str] = None
    cage_code: Optional[str] = None
    owner_name: Optional[str] = None
    status: Optional[str] = "在笼"
    notes: Optional[str] = None

# --- Cage ---
class CageBase(BaseModel):
    cage_code: str
    room: Optional[str] = "默认鼠房"
    strain: Optional[str] = ""
    gender: Optional[str] = "M"
    capacity: Optional[int] = 5
    mating_date: Optional[str] = None
    litter_birth_date: Optional[str] = None
    litter_birth_dates: Optional[List[str]] = None
    observation: Optional[str] = None
    notes: Optional[str] = None

class CageCreate(CageBase):
    pass


class CageBatchCreate(BaseModel):
    cage_codes: List[str]
    room: Optional[str] = "默认鼠房"
    strain: Optional[str] = ""
    gender: Optional[str] = "M"
    capacity: Optional[int] = 5
    mating_date: Optional[str] = None
    litter_birth_date: Optional[str] = None
    litter_birth_dates: Optional[List[str]] = None
    observation: Optional[str] = None
    notes: Optional[str] = None

class CageUpdate(BaseModel):
    cage_code: Optional[str] = None
    room: Optional[str] = None
    strain: Optional[str] = None
    gender: Optional[str] = None
    capacity: Optional[int] = None
    mating_date: Optional[str] = None
    litter_birth_date: Optional[str] = None
    litter_birth_dates: Optional[List[str]] = None
    observation: Optional[str] = None
    notes: Optional[str] = None
    merge_existing: bool = False

class CageResponse(CageBase):
    id: int
    mouse_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class CageDetailResponse(CageResponse):
    mice: List[MouseResponse] = []


# --- Todo reminders ---
class TodoReminderCreate(BaseModel):
    title: str
    due_at: Optional[str] = None
    notes: Optional[str] = None
    cage_id: Optional[int] = None
    mouse_id: Optional[int] = None
    cage_ids: Optional[List[int]] = None
    mouse_ids: Optional[List[int]] = None


class TodoReminderUpdate(BaseModel):
    title: Optional[str] = None
    due_at: Optional[str] = None
    notes: Optional[str] = None
    cage_id: Optional[int] = None
    mouse_id: Optional[int] = None
    cage_ids: Optional[List[int]] = None
    mouse_ids: Optional[List[int]] = None
    status: Optional[str] = None


class TodoReminderResponse(TodoReminderCreate):
    id: int
    source: str
    auto_key: Optional[str] = None
    status: str
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    cage: Optional[Dict[str, Any]] = None
    mouse: Optional[Dict[str, Any]] = None
    cages: List[Dict[str, Any]] = []
    mice: List[Dict[str, Any]] = []

# --- Transfer Request (转鼠需求及反馈表) ---
class TransferRequestBase(BaseModel):
    demander: str
    strain: str
    request_date: Optional[str] = None
    age_gender_req: Optional[str] = "成年/无要求"
    target_room: Optional[str] = "东五"
    cage_count: Optional[int] = 1
    source_room: Optional[str] = None
    mouse_gender: Optional[str] = None
    mouse_codes: Optional[str] = None
    status: Optional[str] = "申请中"
    feedback: Optional[str] = None

class TransferRequestCreate(TransferRequestBase):
    pass

class TransferRequestUpdate(BaseModel):
    demander: Optional[str] = None
    strain: Optional[str] = None
    request_date: Optional[str] = None
    age_gender_req: Optional[str] = None
    target_room: Optional[str] = None
    cage_count: Optional[int] = None
    source_room: Optional[str] = None
    mouse_gender: Optional[str] = None
    mouse_codes: Optional[str] = None
    status: Optional[str] = None
    feedback: Optional[str] = None
    handler: Optional[str] = None

class TransferRequestResponse(TransferRequestBase):
    id: int
    seq: Optional[str] = None
    handler: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- TransferLog ---
class TransferLogCreate(BaseModel):
    action_type: str
    mouse_codes: str
    mouse_count: Optional[int] = 1
    claimer_name: Optional[str] = None
    source_room: Optional[str] = None
    target_room: Optional[str] = None
    source_cage: Optional[str] = None
    target_cage: Optional[str] = None
    operator: Optional[str] = "admin"
    date: Optional[str] = None
    status: Optional[str] = "已完成"
    notes: Optional[str] = None

class TransferLogResponse(TransferLogCreate):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- Primer ---
class PrimerBase(BaseModel):
    primer_no: Optional[int] = None
    strain_short: str
    strain_full: Optional[str] = None
    source: Optional[str] = None
    gene_type: Optional[str] = None
    sequence: Optional[str] = None
    band_size: Optional[str] = None
    url: Optional[str] = None
    notes: Optional[str] = None

class PrimerCreate(PrimerBase):
    pass

class PrimerUpdate(BaseModel):
    primer_no: Optional[int] = None
    strain_short: Optional[str] = None
    strain_full: Optional[str] = None
    source: Optional[str] = None
    gene_type: Optional[str] = None
    sequence: Optional[str] = None
    band_size: Optional[str] = None
    url: Optional[str] = None
    notes: Optional[str] = None

class PrimerResponse(PrimerBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- Dashboard Stats ---
class DashboardStats(BaseModel):
    total_mice: int
    in_cage_mice: int
    claimed_mice: int
    total_cages: int
    total_claimers: int
    total_primers: int
    pending_requests_count: int = 0
    total_genotypes: int = 0
    rooms: List[Dict[str, Any]]
    strain_distribution: List[Dict[str, Any]]
    claimer_distribution: List[Dict[str, Any]]
    recent_logs: List[TransferLogResponse]

# --- Room ---
class RoomCreate(BaseModel):
    category: Optional[str] = None
    name: str
    description: Optional[str] = None

class RoomResponse(BaseModel):
    id: Optional[int] = None
    name: str
    description: Optional[str] = None

# --- Strain ---
class StrainCreate(BaseModel):
    name: str
    notes: Optional[str] = None

class StrainUpdate(BaseModel):
    notes: Optional[str] = None

class StrainResponse(BaseModel):
    id: Optional[int] = None
    name: str
    notes: Optional[str] = None
    mouse_count: Optional[int] = 0
