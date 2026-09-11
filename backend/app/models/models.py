import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Date, JSON
from sqlalchemy.orm import relationship
from backend.app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    hashed_password = Column(String(256), nullable=False)
    role = Column(String(32), default="guest", nullable=False)  # "admin" or "guest"
    display_name = Column(String(64), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class SystemSetting(Base):
    """与账号一起保存的系统级配置。"""
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(64), unique=True, index=True, nullable=False)
    value = Column(String(256), nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Claimer(Base):
    """课题组成员/小鼠领取人"""
    __tablename__ = "claimers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), unique=True, index=True, nullable=False)
    role = Column(String(32), default="学生")  # 学生, 博士后, 实验助理, PI/导师, 管理员
    email = Column(String(128), nullable=True)
    phone = Column(String(64), nullable=True)
    color = Column(String(32), default="#2563eb")  # 专属标识色 HEX
    default_room = Column(String(64), nullable=True)  # 如 东四105, 枫林
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    mice = relationship("Mouse", back_populates="owner")

class Room(Base):
    """鼠房实体"""
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), unique=True, index=True, nullable=False)
    description = Column(String(256), nullable=True)
    category = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Cage(Base):
    """小鼠笼位"""
    __tablename__ = "cages"

    id = Column(Integer, primary_key=True, index=True)
    cage_code = Column(String(64), index=True, nullable=False)  # 如 7A, 05-1H, H9
    room = Column(String(64), index=True, default="默认鼠房")  # 如 江湾发育所, 东四105, 实验动物楼405B
    strain = Column(String(128), default="")  # 品系
    gender = Column(String(16), default="M")  # M, F, M/F, 混合
    cage_type = Column(String(32), default="常规笼")  # 仅兼容旧数据库，不再对外展示或编辑
    capacity = Column(Integer, default=5)  # 最大容量，通常5只
    mating_date = Column(String(32), nullable=True)  # 合笼日期
    litter_birth_date = Column(String(32), nullable=True)  # 生鼠日期 YYYY-MM-DD，用于21天断奶提醒
    litter_birth_dates = Column(JSON, nullable=True)  # 多批生鼠日期，保留旧字段用于兼容已有数据
    observation = Column(Text, nullable=True)  # 观察记录
    notes = Column(Text, nullable=True)  # 备注
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    mice = relationship("Mouse", back_populates="cage")


class TodoReminder(Base):
    """手动待办与系统自动生成的笼位提醒。"""
    __tablename__ = "todo_reminders"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(256), nullable=False)
    due_at = Column(String(32), index=True, nullable=True)  # YYYY-MM-DDTHH:MM
    notes = Column(Text, nullable=True)
    cage_id = Column(Integer, ForeignKey("cages.id", ondelete="SET NULL"), index=True, nullable=True)
    mouse_id = Column(Integer, ForeignKey("mice.id", ondelete="SET NULL"), index=True, nullable=True)
    cage_ids = Column(JSON, nullable=True)
    mouse_ids = Column(JSON, nullable=True)
    source = Column(String(32), index=True, default="manual")
    auto_key = Column(String(256), unique=True, index=True, nullable=True)
    status = Column(String(32), index=True, default="pending")
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class MouseStatus(Base):
    """可配置的小鼠档案状态。"""
    __tablename__ = "mouse_statuses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(32), unique=True, index=True, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
    removes_from_cage = Column(Boolean, default=False, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Mouse(Base):
    """小鼠档案实体"""
    __tablename__ = "mice"

    id = Column(Integer, primary_key=True, index=True)
    mouse_code = Column(String(64), unique=True, index=True, nullable=False)  # 耳标/编号 如 H233, E962, 503
    cage_id = Column(Integer, ForeignKey("cages.id", ondelete="SET NULL"), nullable=True, index=True)
    strain = Column(String(128), index=True, default="")  # 品系/基因型 如 5xFAD, Trap2/Ai9
    gender = Column(String(16), default="未知")  # M, F, 未知
    dob = Column(String(32), index=True, nullable=True)  # 出生日期 YYYY-MM-DD
    parents = Column(String(128), nullable=True)  # 父母编号或繁育来源
    genotype_1 = Column(String(64), nullable=True)  # 如 野生型, 杂合子, 纯合子, 阳性, 阴性
    genotype_2 = Column(String(64), nullable=True)
    test_date = Column(String(32), nullable=True)  # 基因检测日期

    # 领取人关联 (核心联动)
    owner_id = Column(Integer, ForeignKey("claimers.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_name = Column(String(64), index=True, nullable=True)  # 冗余姓名方便快速查询

    # 状态与领用信息
    status = Column(String(32), default="在笼", index=True)
    claim_date = Column(String(32), nullable=True)  # 领取日期 YYYY-MM-DD
    claim_purpose = Column(String(256), nullable=True)  # 领用目的或实验记录
    source_room = Column(String(64), index=True, nullable=True)  # 来源鼠房
    notes = Column(Text, nullable=True)  # 备注与操作记录

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    cage = relationship("Cage", back_populates="mice")
    owner = relationship("Claimer", back_populates="mice")
    genotype_records = relationship("GenotypeRecord", back_populates="mouse", cascade="all, delete-orphan")

class GenotypeRecord(Base):
    """小鼠基因型鉴定详细记录"""
    __tablename__ = "genotype_records"

    id = Column(Integer, primary_key=True, index=True)
    mouse_code = Column(String(64), index=True, nullable=False)  # 耳标编号
    mouse_id = Column(Integer, ForeignKey("mice.id", ondelete="CASCADE"), nullable=True, index=True)
    test_date = Column(String(32), index=True, nullable=True)  # 测试日期
    strain = Column(String(128), index=True, default="")  # 品系/基因型
    dob = Column(String(32), nullable=True)  # 出生日期
    gender = Column(String(16), nullable=True)  # 性别
    parents = Column(String(256), nullable=True)  # 父母 (如 B311M+B354F、B362F)
    genotype_1 = Column(String(64), nullable=True)  # 阳性, 阴性, 杂合子, 纯合子, 野生型, HET, WT
    genotype_2 = Column(String(64), nullable=True)
    genotype_3 = Column(String(64), nullable=True)
    op_record = Column(String(128), nullable=True)  # 操作记录/操作人
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    mouse = relationship("Mouse", back_populates="genotype_records")

class TransferRequest(Base):
    """转鼠需求及反馈表 (支持游客申请，管理员处理)"""
    __tablename__ = "transfer_requests"

    id = Column(Integer, primary_key=True, index=True)
    seq = Column(String(32), index=True, nullable=True)  # 序号
    request_date = Column(String(32), index=True, nullable=False)  # 申请日期
    demander = Column(String(64), index=True, nullable=False)  # 需求者 (学生/老师姓名)
    strain = Column(String(128), index=True, nullable=False)  # 小鼠品系
    age_gender_req = Column(String(128), nullable=True)  # 年龄/性别要求 (如 "成年/雄鼠")
    target_room = Column(String(64), index=True, nullable=True)  # 转入鼠房 (如 "东五", "东四")
    cage_count = Column(Integer, default=1)  # 笼位数量
    source_room = Column(String(64), nullable=True)  # 转出鼠房 (如 "枫林", "江湾")
    mouse_gender = Column(String(32), nullable=True)  # 小鼠实际性别 (M, F, M/F)
    mouse_codes = Column(Text, nullable=True)  # 分配的小鼠编号，逗号隔开 (如 "E962, E964")
    status = Column(String(32), default="申请中", index=True)  # "申请中", "进行中", "已转", "取消"
    feedback = Column(Text, nullable=True)  # 反馈说明/备注
    handler = Column(String(64), nullable=True)  # 经办管理员
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class TransferRequestAssignment(Base):
    """Active assignment and durable pre-approval state for exact reversal."""
    __tablename__ = "transfer_request_assignments"

    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey("transfer_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    mouse_id = Column(Integer, ForeignKey("mice.id", ondelete="CASCADE"), nullable=False, unique=True)
    original_state = Column(JSON, nullable=False)
    assigned_state = Column(JSON, nullable=False)
    source_room = Column(String(64), nullable=True)
    source_cage = Column(String(64), nullable=True)


class TransferLog(Base):
    """小鼠领用、转鼠、换笼流转日志"""
    __tablename__ = "transfer_logs"

    id = Column(Integer, primary_key=True, index=True)
    action_type = Column(String(32), index=True, default="设置领取人")  # 设置领取人, 转鼠, 换笼, 批量移入, 状态变更
    mouse_codes = Column(Text, nullable=False)  # 逗号分隔的耳标编号
    mouse_count = Column(Integer, default=1)
    claimer_name = Column(String(64), index=True, nullable=True)
    source_room = Column(String(64), nullable=True)
    target_room = Column(String(64), nullable=True)
    source_cage = Column(String(64), nullable=True)
    target_cage = Column(String(64), nullable=True)
    operator = Column(String(64), default="admin")
    date = Column(String(32), index=True, default="")
    status = Column(String(32), default="已完成")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Primer(Base):
    """引物信息表"""
    __tablename__ = "primers"

    id = Column(Integer, primary_key=True, index=True)
    primer_no = Column(Integer, nullable=True)
    strain_short = Column(String(128), index=True, default="")
    strain_full = Column(String(256), nullable=True)
    source = Column(String(128), nullable=True)
    gene_type = Column(String(128), nullable=True)
    sequence = Column(Text, nullable=True)
    band_size = Column(String(256), nullable=True)
    url = Column(String(512), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Strain(Base):
    """小鼠品系及备注背景信息"""
    __tablename__ = "strains"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), unique=True, index=True, nullable=False)  # 如 5xFAD, Trap2/Ai9
    notes = Column(Text, nullable=True)  # 品系背景/表型/繁育备注
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
