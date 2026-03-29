# Path: app/models/all_models.py
import enum
from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import Date, Enum, Float, ForeignKey, Interval, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import Interval as SQLInterval

from app.extensions import db


class InstallationType(enum.Enum):
    wall = "wall"
    floor = "floor"


class ServiceType(enum.Enum):
    standard = "standard"
    warranty = "warranty"
    emergency = "emergency"


class RequestStatus(enum.Enum):
    pending = "pending"
    assigned = "assigned"
    closed = "closed"
    overdue = "overdue"
    cancelled = "cancelled"


class RequestMode(enum.Enum):
    on_way = "on_way"
    arrived = "arrived"  # «Прибытие» (между «В пути» и «В работе»)
    in_progress = "in_progress"
    waiting = "waiting"
    completed = "completed"
    normal = "normal"


class VisitType(enum.Enum):
    """Цель выезда (отдельно от «типа заявки»: аварийная/ремонтная/плановая)."""

    repair = "repair"  # ремонтный выезд, выполнение работ
    survey = "survey"  # обследование, преддоговорной контур


# Many-to-many таблица для заявок и мастеров
request_workers = db.Table(
    "request_workers",
    db.Column("request_id", db.Integer, ForeignKey("requests.id"), primary_key=True),
    db.Column("worker_id", db.Integer, ForeignKey("workers.id"), primary_key=True),
)


class Users(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    worker_id = db.Column(
        db.Integer, ForeignKey("workers.id", ondelete="SET NULL"), nullable=True, index=True
    )

    telegram_bot_users = db.relationship("TelegramBotUsers", back_populates="user", lazy=True)
    created_media = db.relationship("Media", back_populates="created_by", lazy=True)
    created_requests = db.relationship(
        "Request", foreign_keys="Request.created_by_user_id", back_populates="created_by", lazy=True
    )
    updated_requests = db.relationship(
        "Request", foreign_keys="Request.updated_by_user_id", back_populates="updated_by", lazy=True
    )
    created_reworks = db.relationship("ReworkRequest", back_populates="created_by", lazy=True)
    refresh_tokens = db.relationship(
        "RefreshToken", back_populates="user", lazy=True, cascade="all, delete-orphan"
    )
    linked_worker = db.relationship(
        "Worker", foreign_keys=[worker_id], back_populates="linked_user", uselist=False
    )
    created_request_items = db.relationship(
        "RequestItem", foreign_keys="RequestItem.created_by_user_id", lazy=True
    )
    received_request_payments = db.relationship(
        "RequestPayment", foreign_keys="RequestPayment.received_by_user_id", lazy=True
    )
    created_chat_threads = db.relationship(
        "ChatThread", foreign_keys="ChatThread.created_by_user_id", lazy=True
    )
    authored_chat_messages = db.relationship(
        "ChatMessage", foreign_keys="ChatMessage.author_user_id", lazy=True
    )


class RefreshToken(db.Model):
    """Refresh JWT: хранение jti для отзыва при logout и при ротации."""

    __tablename__ = "refresh_tokens"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    jti = db.Column(db.String(64), unique=True, nullable=False, index=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("Users", back_populates="refresh_tokens")


class TelegramBotUsers(db.Model):
    __tablename__ = "telegram_bot_users"
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, ForeignKey("users.id"), nullable=True)
    full_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("Users", back_populates="telegram_bot_users")


class TelegramChat(db.Model):
    """Чаты/каналы Telegram, из которых бот может забирать медиа."""

    __tablename__ = "telegram_chats"
    chat_id = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(255), nullable=True)
    download_enabled = db.Column(db.Boolean, default=False, nullable=False)
    is_favorite = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)


class TelegramMessage(db.Model):
    """Текстовые сообщения из Telegram (для журнала; не путать с удалённым чатом приложения)."""

    __tablename__ = "telegram_messages"
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(255), nullable=True)
    message_text = db.Column(db.Text, nullable=True)
    message_date = db.Column(db.DateTime, nullable=True)
    telegram_message_id = db.Column(db.BigInteger, nullable=False)
    chat_id = db.Column(db.String(50), nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint("telegram_message_id", "chat_id", name="uq_telegram_message_id_chat"),
    )


class SystemLogs(db.Model):
    __tablename__ = "system_logs"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    level = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=False)


class Client(db.Model):
    __tablename__ = "clients"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=True)
    address = db.Column(db.Text, nullable=False)
    phone = db.Column(db.String(255), nullable=False)
    representative_name = db.Column(db.String(255), nullable=True)
    representative_phone = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)
    counterparty = db.Column(db.String(255), nullable=True)
    client_kind = db.Column(
        db.String(32), nullable=True
    )  # individual, legal_entity, commercial_household, government
    access_token = db.Column(db.String(255), nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    created_by_user_id = db.Column(db.Integer, nullable=True)
    updated_by_user_id = db.Column(db.Integer, nullable=True)
    password_hash = db.Column(db.Text, nullable=True)

    requests = db.relationship(
        "Request", back_populates="client", lazy=True, cascade="all, delete-orphan"
    )
    contracts = db.relationship(
        "Contract", back_populates="client", lazy=True, cascade="all, delete-orphan"
    )
    media = db.relationship(
        "Media", back_populates="client", lazy=True, cascade="all, delete-orphan"
    )
    payments = db.relationship(
        "Payment", back_populates="client", lazy=True, cascade="all, delete-orphan"
    )
    equipments = db.relationship(
        "Equipment", back_populates="client", lazy=True, cascade="all, delete-orphan"
    )
    equipment_templates = db.relationship(
        "EquipmentTemplate", back_populates="client", lazy=True, cascade="all, delete-orphan"
    )
    work_orders = db.relationship(
        "WorkOrder", back_populates="client", lazy=True, cascade="all, delete-orphan"
    )
    feedback = db.relationship(
        "ClientFeedback", back_populates="client", lazy=True, cascade="all, delete-orphan"
    )
    portal_media = db.relationship(
        "ClientPortalMedia", back_populates="client", lazy=True, cascade="all, delete-orphan"
    )
    portal_payments = db.relationship(
        "ClientPortalPayments", back_populates="client", lazy=True, cascade="all, delete-orphan"
    )
    portal_requests = db.relationship(
        "ClientPortalRequests", back_populates="client", lazy=True, cascade="all, delete-orphan"
    )


class Request(db.Model):
    __tablename__ = "requests"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=True)
    contract_id = db.Column(db.Integer, ForeignKey("contracts.id"), nullable=True)
    contract_scope_uid = db.Column(db.String(64), nullable=True, index=True, unique=True)
    equipment_id = db.Column(db.Integer, ForeignKey("equipment.id"), nullable=True)
    checklist_template_id = db.Column(
        db.Integer, ForeignKey("checklist_templates.id"), nullable=True, index=True
    )
    created_by_user_id = db.Column(db.Integer, ForeignKey("users.id"), nullable=True)
    updated_by_user_id = db.Column(db.Integer, ForeignKey("users.id"), nullable=True)
    request_number = db.Column(db.String, nullable=True)
    description = db.Column(db.Text, nullable=True)
    service_type = db.Column(Enum(ServiceType, name="service_type"), nullable=True)
    warranty_reason = db.Column(db.Text, nullable=True)
    urgent_price = db.Column(db.Numeric, nullable=True)
    contract_regulated_price = db.Column(db.Numeric, nullable=True)
    materials_cost = db.Column(db.Numeric, nullable=True)
    total_price = db.Column(db.Numeric, nullable=True)
    estimated_time = db.Column(db.Integer, nullable=True)
    planned_date = db.Column(db.Date, nullable=True)
    planned_start_time = db.Column(db.DateTime, nullable=True)
    planned_end_time = db.Column(db.DateTime, nullable=True)
    actual_start_time = db.Column(db.DateTime, nullable=True)
    actual_end_time = db.Column(db.DateTime, nullable=True)
    travel_time = db.Column(SQLInterval, nullable=True)
    work_time = db.Column(SQLInterval, nullable=True)
    waiting_time = db.Column(SQLInterval, nullable=True)
    status = db.Column(
        Enum(RequestStatus, name="request_status"), default="assigned", nullable=False
    )
    mode = db.Column(Enum(RequestMode, name="request_mode"), default="normal", nullable=False)
    status_date = db.Column(db.DateTime, nullable=True)
    additional_resources_needed = db.Column(db.Boolean, nullable=True)
    additional_resources_reason = db.Column(db.Text, nullable=True)
    workers_count = db.Column(db.Integer, nullable=True)
    debt = db.Column(db.Numeric, nullable=True)
    comment = db.Column(db.Text, nullable=True)
    author_name = db.Column(db.Text, nullable=True)
    type = db.Column(db.String, nullable=True)
    visit_type = db.Column(
        Enum(
            VisitType,
            name="visit_type",
            values_callable=lambda x: [e.value for e in x],
            native_enum=False,
        ),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)
    full_name = db.Column(db.String, nullable=True)
    address = db.Column(db.String, nullable=True)
    phone = db.Column(db.String, nullable=True)

    client = db.relationship("Client", back_populates="requests")
    contract = db.relationship("Contract", backref="requests", lazy=True)
    equipment = db.relationship("Equipment", backref="requests", lazy=True)
    checklist_template = db.relationship(
        "ChecklistTemplate", foreign_keys=[checklist_template_id], lazy=True
    )
    created_by = db.relationship(
        "Users", foreign_keys=[created_by_user_id], back_populates="created_requests"
    )
    updated_by = db.relationship(
        "Users", foreign_keys=[updated_by_user_id], back_populates="updated_requests"
    )
    media = db.relationship("Media", back_populates="request", lazy=True)
    service_history = db.relationship(
        "EquipmentServiceHistory", back_populates="request", lazy=True
    )
    work_orders = db.relationship("WorkOrder", back_populates="request", lazy=True)
    workers = db.relationship(
        "Worker", secondary=request_workers, back_populates="requests", lazy=True
    )
    rework_original = db.relationship(
        "ReworkRequest",
        foreign_keys="ReworkRequest.original_request_id",
        back_populates="original_request",
        lazy=True,
    )
    rework_new = db.relationship(
        "ReworkRequest",
        foreign_keys="ReworkRequest.new_request_id",
        back_populates="new_request",
        lazy=True,
    )
    action_logs = db.relationship(
        "RequestActionLog",
        back_populates="request",
        lazy=True,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    items = db.relationship(
        "RequestItem", back_populates="request", lazy=True, cascade="all, delete-orphan"
    )
    request_payments = db.relationship(
        "RequestPayment", back_populates="request", lazy=True, cascade="all, delete-orphan"
    )
    chat_threads = db.relationship(
        "ChatThread", back_populates="request", lazy=True, cascade="all, delete-orphan"
    )
    checklist_answers = db.relationship(
        "RequestChecklistAnswer", back_populates="request", lazy=True, cascade="all, delete-orphan"
    )
    defects = db.relationship(
        "RequestDefect", back_populates="request", lazy=True, cascade="all, delete-orphan"
    )


class RequestDefect(db.Model):
    """Зафиксированный дефект по заявке (оборудование / материал), опционально с фото."""

    __tablename__ = "request_defects"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind = db.Column(db.String(16), nullable=False)  # equipment | material
    description = db.Column(db.Text, nullable=False)
    media_id = db.Column(
        db.Integer, ForeignKey("media.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_user_id = db.Column(
        db.Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    request = db.relationship("Request", back_populates="defects")
    media = db.relationship("Media", foreign_keys=[media_id], lazy=True)


class RequestActionLog(db.Model):
    """Журнал действий по заявке (API / мобилка): смена статуса, режима, закрытие."""

    __tablename__ = "request_action_logs"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action = db.Column(db.String(32), nullable=False)
    old_status = db.Column(db.String(32), nullable=True)
    new_status = db.Column(db.String(32), nullable=True)
    old_mode = db.Column(db.String(32), nullable=True)
    new_mode = db.Column(db.String(32), nullable=True)
    extra = db.Column(JSONB, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    request = db.relationship("Request", back_populates="action_logs")
    user = db.relationship("Users", foreign_keys=[user_id], lazy=True)


class RequestClientOperation(db.Model):
    """Идемпотентность клиентских offline-операций (mobile outbox)."""

    __tablename__ = "request_client_operations"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    operation_type = db.Column(db.String(32), nullable=False)
    client_operation_id = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "request_id",
            "user_id",
            "operation_type",
            "client_operation_id",
            name="uq_request_client_operation",
        ),
    )


class ChecklistTemplate(db.Model):
    __tablename__ = "checklist_templates"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    equipment_type = db.Column(db.String(100), nullable=True, index=True)
    equipment_id = db.Column(
        db.Integer, ForeignKey("equipment.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_by_user_id = db.Column(db.Integer, ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    items = db.relationship(
        "ChecklistTemplateItem", back_populates="template", lazy=True, cascade="all, delete-orphan"
    )
    equipment = db.relationship("Equipment", foreign_keys=[equipment_id], lazy=True)


class ChecklistTemplateItem(db.Model):
    __tablename__ = "checklist_template_items"
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(
        db.Integer,
        ForeignKey("checklist_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(255), nullable=False)
    item_order = db.Column(db.Integer, nullable=False, default=0)
    is_required = db.Column(db.Boolean, default=True, nullable=False)
    item_type = db.Column(db.String(32), nullable=False, default="boolean")  # boolean/text/number
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)

    template = db.relationship("ChecklistTemplate", back_populates="items")
    answers = db.relationship(
        "RequestChecklistAnswer",
        back_populates="template_item",
        lazy=True,
        cascade="all, delete-orphan",
    )


class RequestChecklistAnswer(db.Model):
    __tablename__ = "request_checklist_answers"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_item_id = db.Column(
        db.Integer,
        ForeignKey("checklist_template_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    checked = db.Column(db.Boolean, nullable=True)
    value_text = db.Column(db.Text, nullable=True)
    value_number = db.Column(Numeric(12, 2), nullable=True)
    media_id = db.Column(db.Integer, ForeignKey("media.id", ondelete="SET NULL"), nullable=True)
    answered_by_user_id = db.Column(
        db.Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    answered_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    request = db.relationship("Request", back_populates="checklist_answers")
    template_item = db.relationship("ChecklistTemplateItem", back_populates="answers")
    media = db.relationship("Media", lazy=True)
    answered_by = db.relationship("Users", lazy=True)

    __table_args__ = (
        db.UniqueConstraint("request_id", "template_item_id", name="uq_request_checklist_answer"),
    )


class RequestItem(db.Model):
    __tablename__ = "request_items"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_type = db.Column(db.String(16), nullable=False, default="material")
    name = db.Column(db.String(255), nullable=False)
    quantity = db.Column(Numeric(10, 2), nullable=False, default=1)
    unit_price = db.Column(Numeric(12, 2), nullable=False, default=0)
    line_total = db.Column(Numeric(12, 2), nullable=True)
    source = db.Column(db.String(32), nullable=True)  # client_ordered / master_recommended / other
    comment = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.Integer, ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)

    request = db.relationship("Request", back_populates="items")
    created_by = db.relationship(
        "Users", foreign_keys=[created_by_user_id], back_populates="created_request_items"
    )


class RequestPayment(db.Model):
    __tablename__ = "request_payments"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id = db.Column(
        db.Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=True, index=True
    )
    amount = db.Column(Numeric(12, 2), nullable=False, default=0)
    payment_method = db.Column(db.String(32), nullable=True)  # cash / online / transfer
    is_cash = db.Column(db.Boolean, default=False, nullable=False)
    note = db.Column(db.Text, nullable=True)
    received_by_user_id = db.Column(db.Integer, ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)

    request = db.relationship("Request", back_populates="request_payments")
    client = db.relationship("Client", lazy=True)
    received_by = db.relationship(
        "Users", foreign_keys=[received_by_user_id], back_populates="received_request_payments"
    )


class ChatThread(db.Model):
    __tablename__ = "chat_threads"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_by_user_id = db.Column(db.Integer, ForeignKey("users.id"), nullable=True)
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)

    request = db.relationship("Request", back_populates="chat_threads")
    created_by = db.relationship(
        "Users", foreign_keys=[created_by_user_id], back_populates="created_chat_threads"
    )
    participants = db.relationship(
        "ChatParticipant", back_populates="thread", lazy=True, cascade="all, delete-orphan"
    )
    messages = db.relationship(
        "ChatMessage", back_populates="thread", lazy=True, cascade="all, delete-orphan"
    )


class ChatParticipant(db.Model):
    __tablename__ = "chat_participants"
    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(
        db.Integer, ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    last_read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)

    thread = db.relationship("ChatThread", back_populates="participants")
    user = db.relationship("Users", lazy=True)

    __table_args__ = (db.UniqueConstraint("thread_id", "user_id", name="uq_chat_thread_user"),)


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(
        db.Integer, ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id = db.Column(db.Integer, ForeignKey("users.id"), nullable=True)
    message_text = db.Column(db.Text, nullable=False)
    is_edited = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True, index=True)
    updated_at = db.Column(db.DateTime, nullable=True)

    thread = db.relationship("ChatThread", back_populates="messages")
    author = db.relationship(
        "Users", foreign_keys=[author_user_id], back_populates="authored_chat_messages"
    )


class Contract(db.Model):
    __tablename__ = "contracts"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    created_by_user_id = db.Column(db.Integer, ForeignKey("users.id"), nullable=True)
    contract_type = db.Column(db.String, nullable=True)
    total_price = db.Column(db.Float, nullable=True)
    emergency_included_count = db.Column(db.Integer, nullable=True)
    emergency_included_cost = db.Column(Numeric(12, 2), nullable=True)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    # Договор обслуживания инженерных систем: вид контрагента, сроки, периодичность, перечень
    counterparty_kind = db.Column(
        db.String(32), nullable=True
    )  # individual, legal_entity, commercial_household, government
    conclusion_date = db.Column(Date, nullable=True)
    term_note = db.Column(db.Text, nullable=True)
    service_periodicity = db.Column(db.Text, nullable=True)
    equipment_scope = db.Column(db.Text, nullable=True)
    # Номер для документов/переписки (не обязан совпадать с внутренним id)
    document_number = db.Column(db.String(128), nullable=True)
    # manual — сумма из поля total_price; from_scope — из суммы строк перечня (JSON)
    price_mode = db.Column(db.String(16), nullable=False, default="manual")
    # Полный снимок мастера создания договора (оборудование, виды работ, реквизиты для печати)
    maintenance_wizard_json = db.Column(db.Text, nullable=True)

    client = db.relationship("Client", back_populates="contracts")
    equipments = db.relationship("Equipment", back_populates="contract", lazy=True)
    created_by = db.relationship("Users", foreign_keys=[created_by_user_id], lazy=True)
    documents = db.relationship(
        "ContractDocument", back_populates="contract", lazy=True, cascade="all, delete-orphan"
    )


class ContractDocument(db.Model):
    __tablename__ = "contract_documents"
    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(
        db.Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = db.Column(db.String(255), nullable=True)
    document_kind = db.Column(db.String(32), nullable=True)
    file_path = db.Column(db.String(500), nullable=False)
    content_type = db.Column(db.String(100), nullable=True)
    uploaded_by_user_id = db.Column(db.Integer, ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)

    contract = db.relationship("Contract", back_populates="documents")
    uploaded_by = db.relationship("Users", foreign_keys=[uploaded_by_user_id], lazy=True)


class Media(db.Model):
    __tablename__ = "media"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=True)
    file_path = db.Column(db.String, nullable=True)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    file_type = db.Column(db.String, nullable=True)
    request_id = db.Column(db.Integer, ForeignKey("requests.id"), nullable=True)
    equipment_id = db.Column(db.Integer, ForeignKey("equipment.id"), nullable=True)
    author_name = db.Column(db.String, nullable=True)
    description = db.Column(db.String, nullable=True)
    equipment_type = db.Column(db.String, nullable=True)
    chat_id = db.Column(db.String, nullable=True)
    telegram_message_id = db.Column(db.BigInteger, nullable=True)
    category = db.Column(db.String, nullable=True)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    content_type = db.Column(db.String, nullable=True)
    created_by_user_id = db.Column(db.Integer, ForeignKey("users.id"), nullable=True)

    client = db.relationship("Client", back_populates="media")
    request = db.relationship("Request", back_populates="media")
    equipment = db.relationship("Equipment", back_populates="media", lazy=True)
    created_by = db.relationship("Users", back_populates="created_media")


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    amount = db.Column(db.Float, nullable=True)
    payment_date = db.Column(db.DateTime, nullable=True)
    payment_method = db.Column(db.String, nullable=True)
    status = db.Column(db.String, nullable=True)

    client = db.relationship("Client", back_populates="payments")


class Nomenclature(db.Model):
    __tablename__ = "nomenclature"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=True)
    price = db.Column(db.Float, nullable=True)


class Worker(db.Model):
    __tablename__ = "workers"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String, nullable=False)
    phone = db.Column(db.String, nullable=True)
    role = db.Column(db.String, nullable=True)
    # Цвет в план-графике (#RRGGBB); если NULL — вычисляется по id
    color = db.Column(db.String(32), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    inactive_at = db.Column(db.DateTime, nullable=True)

    requests = db.relationship(
        "Request", secondary=request_workers, back_populates="workers", lazy=True
    )
    service_history = db.relationship(
        "EquipmentServiceHistory", back_populates="executor", lazy=True
    )
    shifts = db.relationship(
        "WorkerShift", back_populates="worker", lazy=True, cascade="all, delete-orphan"
    )
    linked_user = db.relationship("Users", back_populates="linked_worker", uselist=False)


class WorkerShift(db.Model):
    """Смена исполнителя по календарным дням, независимо от заявок."""

    __tablename__ = "worker_shifts"
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(
        db.Integer, ForeignKey("workers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shift_date = db.Column(db.Date, nullable=False, index=True)
    time_start = db.Column(db.Time, nullable=False)
    time_end = db.Column(db.Time, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)

    worker = db.relationship("Worker", back_populates="shifts")

    __table_args__ = (db.UniqueConstraint("worker_id", "shift_date", name="uq_worker_shift_day"),)


class WorkOrder(db.Model):
    __tablename__ = "work_orders"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, ForeignKey("requests.id"), nullable=True)
    client_id = db.Column(db.Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=True)
    description = db.Column(Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)

    request = db.relationship("Request", back_populates="work_orders")
    client = db.relationship("Client", back_populates="work_orders")
    service_history = db.relationship(
        "EquipmentServiceHistory", back_populates="work_order", lazy=True
    )


class Equipment(db.Model):
    __tablename__ = "equipment"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=True)
    parent_id = db.Column(db.Integer, ForeignKey("equipment.id"), nullable=True)
    serial_number = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    kind = db.Column(db.String(50), nullable=True)
    brand = db.Column(db.String(50), nullable=True)
    model = db.Column(db.String(50), nullable=True)
    power = db.Column(db.Float, nullable=True)
    depth = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    width = db.Column(db.Integer, nullable=True)
    installation_type = db.Column(Enum(InstallationType, name="installation_type"), nullable=True)
    production_year = db.Column(db.Integer, nullable=True)
    service_interval = db.Column(db.Integer, nullable=True)
    service_life = db.Column(db.Integer, nullable=True)
    service_price = db.Column(Numeric(10, 2), nullable=True)
    last_service_date = db.Column(Date, nullable=True)
    next_service_date = db.Column(Date, nullable=True)
    warranty_start_date = db.Column(Date, nullable=True)
    warranty_end_date = db.Column(Date, nullable=True)
    warranty_conditions = db.Column(Text, nullable=True)
    photo_path = db.Column(Text, nullable=True)
    document_path = db.Column(db.Text, nullable=True)
    latitude = db.Column(Float, nullable=True)
    longitude = db.Column(Float, nullable=True)
    contract_id = db.Column(db.Integer, ForeignKey("contracts.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    client = db.relationship("Client", back_populates="equipments")
    contract = db.relationship("Contract", back_populates="equipments", lazy=True)
    parent = db.relationship("Equipment", remote_side=[id], back_populates="sub_equipments")
    sub_equipments = db.relationship("Equipment", back_populates="parent", lazy="dynamic")
    service_history = db.relationship("EquipmentServiceHistory", back_populates="equipment")
    regulations = db.relationship("EquipmentServiceRegulation", back_populates="equipment")
    media = db.relationship("Media", back_populates="equipment", lazy=True)

    def annual_service_time(self):
        freq_map = {"monthly": 12, "quarterly": 4, "annually": 1, "biannually": 2}
        if self.regulations and self.regulations.frequency in freq_map:
            return freq_map[self.regulations.frequency] * (
                self.regulations.service_duration.total_seconds() / 3600
                if self.regulations.service_duration
                else 0
            )
        return 0


class EquipmentTemplate(db.Model):
    __tablename__ = "equipment_templates"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=True)
    parent_id = db.Column(db.Integer, ForeignKey("equipment_templates.id"), nullable=True)
    serial_number = db.Column(db.String(50), nullable=True)
    type = db.Column(db.String(50), nullable=False)
    kind = db.Column(db.String(50), nullable=True)
    brand = db.Column(db.String(50), nullable=True)
    model = db.Column(db.String(50), nullable=True)
    power = db.Column(db.Float, nullable=True)
    depth = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    width = db.Column(db.Integer, nullable=True)
    installation_type = db.Column(Enum(InstallationType, name="installation_type"), nullable=True)
    production_year = db.Column(db.Integer, nullable=True)
    service_interval = db.Column(db.Integer, nullable=True)
    service_life = db.Column(db.Integer, nullable=True)
    service_price = db.Column(Numeric(10, 2), nullable=True)
    last_service_date = db.Column(Date, nullable=True)
    next_service_date = db.Column(Date, nullable=True)
    warranty_start_date = db.Column(Date, nullable=True)
    warranty_end_date = db.Column(Date, nullable=True)
    warranty_conditions = db.Column(Text, nullable=True)
    photo_path = db.Column(Text, nullable=True)
    document_path = db.Column(Text, nullable=True)
    latitude = db.Column(Float, nullable=True)
    longitude = db.Column(Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    client = db.relationship("Client", back_populates="equipment_templates")
    parent = db.relationship("EquipmentTemplate", remote_side=[id], back_populates="sub_templates")
    sub_templates = db.relationship("EquipmentTemplate", back_populates="parent", lazy="dynamic")
    regulations = db.relationship("EquipmentServiceRegulation", back_populates="template")


class EquipmentServiceHistory(db.Model):
    __tablename__ = "equipment_service_history"
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, ForeignKey("equipment.id"), nullable=True)
    executor_id = db.Column(db.Integer, ForeignKey("workers.id"), nullable=True)
    request_id = db.Column(db.Integer, ForeignKey("requests.id"), nullable=True)
    work_order_id = db.Column(db.Integer, ForeignKey("work_orders.id"), nullable=True)
    service_date = db.Column(Date, nullable=True)
    service_type = db.Column(Enum(ServiceType, name="service_type"), nullable=True)
    description = db.Column(Text, nullable=True)
    cost = db.Column(Numeric(10, 2), nullable=True)
    materials_used = db.Column(JSONB, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    equipment = db.relationship("Equipment", back_populates="service_history")
    executor = db.relationship("Worker", back_populates="service_history")
    request = db.relationship("Request", back_populates="service_history")
    work_order = db.relationship("WorkOrder", back_populates="service_history")


class EquipmentServiceRegulation(db.Model):
    __tablename__ = "equipment_service_regulations"
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, ForeignKey("equipment.id"), nullable=True)
    template_id = db.Column(db.Integer, ForeignKey("equipment_templates.id"), nullable=True)
    service_type = db.Column(db.String(50), nullable=True)
    frequency = db.Column(db.String(20), nullable=True)
    service_duration = db.Column(Interval, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    equipment = db.relationship("Equipment", back_populates="regulations")
    template = db.relationship("EquipmentTemplate", back_populates="regulations")


class ReworkRequest(db.Model):
    __tablename__ = "rework_requests"
    id = db.Column(db.Integer, primary_key=True)
    original_request_id = db.Column(db.Integer, ForeignKey("requests.id"), nullable=False)
    new_request_id = db.Column(db.Integer, ForeignKey("requests.id"), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    created_by_user_id = db.Column(db.Integer, ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)

    original_request = db.relationship(
        "Request", foreign_keys=[original_request_id], back_populates="rework_original"
    )
    new_request = db.relationship(
        "Request", foreign_keys=[new_request_id], back_populates="rework_new"
    )
    created_by = db.relationship("Users", back_populates="created_reworks")


class RegulationsLink(db.Model):
    __tablename__ = "regulations_link"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(200), nullable=False)


# Добавленные модели для каскадного удаления
class ClientFeedback(db.Model):
    __tablename__ = "client_feedback"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    request_id = db.Column(db.Integer, ForeignKey("requests.id"), nullable=True)
    work_order_id = db.Column(db.Integer, ForeignKey("work_orders.id"), nullable=True)
    rating = db.Column(db.Integer, nullable=True)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    client = db.relationship("Client", back_populates="feedback")
    request = db.relationship("Request", backref="feedback", lazy=True)
    work_order = db.relationship("WorkOrder", backref="feedback", lazy=True)


class ClientPortalMedia(db.Model):
    __tablename__ = "client_portal_media"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    file_path = db.Column(db.Text, nullable=False)
    file_type = db.Column(db.Enum("photo", "video", name="portal_media_type"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    client = db.relationship("Client", back_populates="portal_media")


class ClientPortalPayments(db.Model):
    __tablename__ = "client_portal_payments"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    amount = db.Column(db.Numeric, nullable=True)
    status = db.Column(db.Enum("pending", "completed", name="payment_status"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    client = db.relationship("Client", back_populates="portal_payments")


class ClientPortalRequests(db.Model):
    __tablename__ = "client_portal_requests"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.Enum("new", "in_progress", "closed", name="portal_request_status"), nullable=True
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    client = db.relationship("Client", back_populates="portal_requests")
