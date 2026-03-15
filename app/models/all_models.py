# Path: app/models/all_models.py
from app.extensions import db
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import Enum, Numeric, Text, Date, ForeignKey, Float, Boolean, Interval, DateTime
from sqlalchemy.types import Interval as SQLInterval
from sqlalchemy.dialects.postgresql import JSONB
import enum

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

class RequestMode(enum.Enum):
    on_way = "on_way"
    in_progress = "in_progress"
    waiting = "waiting"
    completed = "completed"
    normal = "normal"

# Many-to-many таблица для заявок и мастеров
request_workers = db.Table('request_workers',
    db.Column('request_id', db.Integer, ForeignKey('requests.id'), primary_key=True),
    db.Column('worker_id', db.Integer, ForeignKey('workers.id'), primary_key=True)
)

class Users(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)

    telegram_bot_users = db.relationship('TelegramBotUsers', back_populates='user', lazy=True)
    created_media = db.relationship('Media', back_populates='created_by', lazy=True)
    created_requests = db.relationship('Request', foreign_keys='Request.created_by_user_id', back_populates='created_by', lazy=True)
    updated_requests = db.relationship('Request', foreign_keys='Request.updated_by_user_id', back_populates='updated_by', lazy=True)
    created_reworks = db.relationship('ReworkRequest', back_populates='created_by', lazy=True)

class TelegramBotUsers(db.Model):
    __tablename__ = 'telegram_bot_users'
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, ForeignKey('users.id'), nullable=True)
    full_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('Users', back_populates='telegram_bot_users')

class SystemLogs(db.Model):
    __tablename__ = 'system_logs'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    level = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=False)

class Client(db.Model):
    __tablename__ = 'clients'
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
    access_token = db.Column(db.String(255), nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    created_by_user_id = db.Column(db.Integer, nullable=True)
    updated_by_user_id = db.Column(db.Integer, nullable=True)
    password_hash = db.Column(db.Text, nullable=True)

    requests = db.relationship('Request', back_populates='client', lazy=True, cascade="all, delete-orphan")
    contracts = db.relationship('Contract', back_populates='client', lazy=True, cascade="all, delete-orphan")
    media = db.relationship('Media', back_populates='client', lazy=True, cascade="all, delete-orphan")
    payments = db.relationship('Payment', back_populates='client', lazy=True, cascade="all, delete-orphan")
    equipments = db.relationship('Equipment', back_populates='client', lazy=True, cascade="all, delete-orphan")
    equipment_templates = db.relationship('EquipmentTemplate', back_populates='client', lazy=True, cascade="all, delete-orphan")
    work_orders = db.relationship('WorkOrder', back_populates='client', lazy=True, cascade="all, delete-orphan")
    feedback = db.relationship('ClientFeedback', back_populates='client', lazy=True, cascade="all, delete-orphan")
    portal_media = db.relationship('ClientPortalMedia', back_populates='client', lazy=True, cascade="all, delete-orphan")
    portal_payments = db.relationship('ClientPortalPayments', back_populates='client', lazy=True, cascade="all, delete-orphan")
    portal_requests = db.relationship('ClientPortalRequests', back_populates='client', lazy=True, cascade="all, delete-orphan")

class Request(db.Model):
    __tablename__ = 'requests'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=True)
    contract_id = db.Column(db.Integer, ForeignKey('contracts.id'), nullable=True)
    equipment_id = db.Column(db.Integer, ForeignKey('equipment.id'), nullable=True)
    created_by_user_id = db.Column(db.Integer, ForeignKey('users.id'), nullable=True)
    updated_by_user_id = db.Column(db.Integer, ForeignKey('users.id'), nullable=True)
    request_number = db.Column(db.String, nullable=True)
    description = db.Column(db.Text, nullable=True)
    service_type = db.Column(Enum(ServiceType, name='service_type'), nullable=True)
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
    status = db.Column(Enum(RequestStatus, name='request_status'), default='pending', nullable=False)
    mode = db.Column(Enum(RequestMode, name='request_mode'), default='normal', nullable=False)
    status_date = db.Column(db.DateTime, nullable=True)
    additional_resources_needed = db.Column(db.Boolean, nullable=True)
    additional_resources_reason = db.Column(db.Text, nullable=True)
    workers_count = db.Column(db.Integer, nullable=True)
    debt = db.Column(db.Numeric, nullable=True)
    comment = db.Column(db.Text, nullable=True)
    author_name = db.Column(db.Text, nullable=True)
    type = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)
    full_name = db.Column(db.String, nullable=True)
    address = db.Column(db.String, nullable=True)
    phone = db.Column(db.String, nullable=True)

    client = db.relationship('Client', back_populates='requests')
    contract = db.relationship('Contract', backref='requests', lazy=True)
    equipment = db.relationship('Equipment', backref='requests', lazy=True)
    created_by = db.relationship('Users', foreign_keys=[created_by_user_id], back_populates='created_requests')
    updated_by = db.relationship('Users', foreign_keys=[updated_by_user_id], back_populates='updated_requests')
    media = db.relationship('Media', back_populates='request', lazy=True)
    service_history = db.relationship('EquipmentServiceHistory', back_populates='request', lazy=True)
    work_orders = db.relationship('WorkOrder', back_populates='request', lazy=True)
    workers = db.relationship('Worker', secondary=request_workers, back_populates='requests', lazy=True)
    rework_original = db.relationship('ReworkRequest', foreign_keys='ReworkRequest.original_request_id', back_populates='original_request', lazy=True)
    rework_new = db.relationship('ReworkRequest', foreign_keys='ReworkRequest.new_request_id', back_populates='new_request', lazy=True)

class Contract(db.Model):
    __tablename__ = 'contracts'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    contract_type = db.Column(db.String, nullable=True)
    total_price = db.Column(db.Float, nullable=True)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)

    client = db.relationship('Client', back_populates='contracts')
    equipments = db.relationship('Equipment', back_populates='contract', lazy=True)

class Media(db.Model):
    __tablename__ = 'media'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=True)
    file_path = db.Column(db.String, nullable=True)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    file_type = db.Column(db.String, nullable=True)
    request_id = db.Column(db.Integer, ForeignKey('requests.id'), nullable=True)
    equipment_id = db.Column(db.Integer, ForeignKey('equipment.id'), nullable=True)
    author_name = db.Column(db.String, nullable=True)
    description = db.Column(db.String, nullable=True)
    equipment_type = db.Column(db.String, nullable=True)
    chat_id = db.Column(db.String, nullable=True)
    category = db.Column(db.String, nullable=True)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    content_type = db.Column(db.String, nullable=True)
    created_by_user_id = db.Column(db.Integer, ForeignKey('users.id'), nullable=True)

    client = db.relationship('Client', back_populates='media')
    request = db.relationship('Request', back_populates='media')
    equipment = db.relationship('Equipment', back_populates='media', lazy=True)
    created_by = db.relationship('Users', back_populates='created_media')

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Float, nullable=True)
    payment_date = db.Column(db.DateTime, nullable=True)
    payment_method = db.Column(db.String, nullable=True)
    status = db.Column(db.String, nullable=True)

    client = db.relationship('Client', back_populates='payments')

class Nomenclature(db.Model):
    __tablename__ = 'nomenclature'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=True)
    price = db.Column(db.Float, nullable=True)

class Worker(db.Model):
    __tablename__ = 'workers'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String, nullable=False)
    phone = db.Column(db.String, nullable=True)
    role = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)

    requests = db.relationship('Request', secondary=request_workers, back_populates='workers', lazy=True)
    service_history = db.relationship('EquipmentServiceHistory', back_populates='executor', lazy=True)

class WorkOrder(db.Model):
    __tablename__ = 'work_orders'
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, ForeignKey('requests.id'), nullable=True)
    client_id = db.Column(db.Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=True)
    description = db.Column(Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)

    request = db.relationship('Request', back_populates='work_orders')
    client = db.relationship('Client', back_populates='work_orders')
    service_history = db.relationship('EquipmentServiceHistory', back_populates='work_order', lazy=True)

class Equipment(db.Model):
    __tablename__ = 'equipment'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=True)
    parent_id = db.Column(db.Integer, ForeignKey('equipment.id'), nullable=True)
    serial_number = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    kind = db.Column(db.String(50), nullable=True)
    brand = db.Column(db.String(50), nullable=True)
    model = db.Column(db.String(50), nullable=True)
    power = db.Column(db.Float, nullable=True)
    depth = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    width = db.Column(db.Integer, nullable=True)
    installation_type = db.Column(Enum(InstallationType, name='installation_type'), nullable=True)
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
    contract_id = db.Column(db.Integer, ForeignKey('contracts.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    client = db.relationship('Client', back_populates='equipments')
    contract = db.relationship('Contract', back_populates='equipments', lazy=True)
    parent = db.relationship('Equipment', remote_side=[id], back_populates='sub_equipments')
    sub_equipments = db.relationship('Equipment', back_populates='parent', lazy='dynamic')
    service_history = db.relationship('EquipmentServiceHistory', back_populates='equipment')
    regulations = db.relationship('EquipmentServiceRegulation', back_populates='equipment')
    media = db.relationship('Media', back_populates='equipment', lazy=True)

    def annual_service_time(self):
        freq_map = {'monthly': 12, 'quarterly': 4, 'annually': 1, 'biannually': 2}
        if self.regulations and self.regulations.frequency in freq_map:
            return freq_map[self.regulations.frequency] * (self.regulations.service_duration.total_seconds() / 3600 if self.regulations.service_duration else 0)
        return 0

class EquipmentTemplate(db.Model):
    __tablename__ = 'equipment_templates'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=True)
    parent_id = db.Column(db.Integer, ForeignKey('equipment_templates.id'), nullable=True)
    serial_number = db.Column(db.String(50), nullable=True)
    type = db.Column(db.String(50), nullable=False)
    kind = db.Column(db.String(50), nullable=True)
    brand = db.Column(db.String(50), nullable=True)
    model = db.Column(db.String(50), nullable=True)
    power = db.Column(db.Float, nullable=True)
    depth = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    width = db.Column(db.Integer, nullable=True)
    installation_type = db.Column(Enum(InstallationType, name='installation_type'), nullable=True)
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

    client = db.relationship('Client', back_populates='equipment_templates')
    parent = db.relationship('EquipmentTemplate', remote_side=[id], back_populates='sub_templates')
    sub_templates = db.relationship('EquipmentTemplate', back_populates='parent', lazy='dynamic')
    regulations = db.relationship('EquipmentServiceRegulation', back_populates='template')

class EquipmentServiceHistory(db.Model):
    __tablename__ = 'equipment_service_history'
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, ForeignKey('equipment.id'), nullable=True)
    executor_id = db.Column(db.Integer, ForeignKey('workers.id'), nullable=True)
    request_id = db.Column(db.Integer, ForeignKey('requests.id'), nullable=True)
    work_order_id = db.Column(db.Integer, ForeignKey('work_orders.id'), nullable=True)
    service_date = db.Column(Date, nullable=True)
    service_type = db.Column(Enum(ServiceType, name='service_type'), nullable=True)
    description = db.Column(Text, nullable=True)
    cost = db.Column(Numeric(10, 2), nullable=True)
    materials_used = db.Column(JSONB, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    equipment = db.relationship('Equipment', back_populates='service_history')
    executor = db.relationship('Worker', back_populates='service_history')
    request = db.relationship('Request', back_populates='service_history')
    work_order = db.relationship('WorkOrder', back_populates='service_history')

class EquipmentServiceRegulation(db.Model):
    __tablename__ = 'equipment_service_regulations'
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, ForeignKey('equipment.id'), nullable=True)
    template_id = db.Column(db.Integer, ForeignKey('equipment_templates.id'), nullable=True)
    service_type = db.Column(db.String(50), nullable=True)
    frequency = db.Column(db.String(20), nullable=True)
    service_duration = db.Column(Interval, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    equipment = db.relationship('Equipment', back_populates='regulations')
    template = db.relationship('EquipmentTemplate', back_populates='regulations')

class ReworkRequest(db.Model):
    __tablename__ = 'rework_requests'
    id = db.Column(db.Integer, primary_key=True)
    original_request_id = db.Column(db.Integer, ForeignKey('requests.id'), nullable=False)
    new_request_id = db.Column(db.Integer, ForeignKey('requests.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    created_by_user_id = db.Column(db.Integer, ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)

    original_request = db.relationship('Request', foreign_keys=[original_request_id], back_populates='rework_original')
    new_request = db.relationship('Request', foreign_keys=[new_request_id], back_populates='rework_new')
    created_by = db.relationship('Users', back_populates='created_reworks')
    
class RegulationsLink(db.Model):
    __tablename__ = 'regulations_link'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(200), nullable=False)

# Добавленные модели для каскадного удаления
class ClientFeedback(db.Model):
    __tablename__ = 'client_feedback'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    request_id = db.Column(db.Integer, ForeignKey('requests.id'), nullable=True)
    work_order_id = db.Column(db.Integer, ForeignKey('work_orders.id'), nullable=True)
    rating = db.Column(db.Integer, nullable=True)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    client = db.relationship('Client', back_populates='feedback')
    request = db.relationship('Request', backref='feedback', lazy=True)
    work_order = db.relationship('WorkOrder', backref='feedback', lazy=True)

class ClientPortalMedia(db.Model):
    __tablename__ = 'client_portal_media'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    file_path = db.Column(db.Text, nullable=False)
    file_type = db.Column(db.Enum('photo', 'video', name='portal_media_type'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    client = db.relationship('Client', back_populates='portal_media')

class ClientPortalPayments(db.Model):
    __tablename__ = 'client_portal_payments'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Numeric, nullable=True)
    status = db.Column(db.Enum('pending', 'completed', name='payment_status'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    client = db.relationship('Client', back_populates='portal_payments')

class ClientPortalRequests(db.Model):
    __tablename__ = 'client_portal_requests'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.Enum('new', 'in_progress', 'closed', name='portal_request_status'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)

    client = db.relationship('Client', back_populates='portal_requests')