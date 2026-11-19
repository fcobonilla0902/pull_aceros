from __future__ import annotations
import os
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, event, Column, Integer, String, Float, ForeignKey, DateTime, Boolean, Text, JSON, UniqueConstraint, CheckConstraint, Table, Index, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from settings import DATABASE_URL

Base = declarative_base()
URL = DATABASE_URL
engine = create_engine(URL, connect_args={'check_same_thread': False, 'timeout': 30} if URL.startswith('sqlite') else {'connect_timeout':10,'application_name':'Meta-Ride'}, pool_pre_ping=True)
if URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def configure_sqlite(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA journal_mode=WAL')
Session = sessionmaker(bind=engine, expire_on_commit=False)
def now(): return datetime.now(timezone.utc).replace(tzinfo=None)
role_permissions = Table('role_permissions', Base.metadata, Column('role_id', ForeignKey('roles.id'), primary_key=True), Column('permission_id', ForeignKey('permissions.id'), primary_key=True))
class Role(Base):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True)
    name = Column(String(40), unique=True, nullable=False)
    permissions = relationship('Permission', secondary=role_permissions)
class Permission(Base):
    __tablename__ = 'permissions'
    id = Column(Integer, primary_key=True)
    name = Column(String(40), unique=True, nullable=False)
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role_id = Column(ForeignKey('roles.id'), nullable=False, index=True)
    active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
    role = relationship(Role)
class SessionToken(Base):
    __tablename__ = 'sessions'
    id = Column(Integer, primary_key=True)
    digest = Column(String(64), unique=True, nullable=False)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    expires = Column(DateTime, nullable=False, index=True)
class Process(Base):
    __tablename__ = 'processes'
    id = Column(Integer, primary_key=True)
    name = Column(String(40), nullable=False, unique=True)
    active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
class Press(Base):
    __tablename__ = 'presses'
    id = Column(Integer, primary_key=True)
    name = Column(String(40), nullable=False, unique=True)
    active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
class Part(Base):
    __tablename__ = 'parts'
    id = Column(Integer, primary_key=True)
    code = Column(String(80), nullable=False, unique=True)
    specification = Column(String(200), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
class Location(Base):
    __tablename__ = 'locations'
    id = Column(Integer, primary_key=True)
    code = Column(String(40), nullable=False, unique=True)
    active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
class Forklift(Base):
    __tablename__ = 'forklifts'
    id = Column(Integer, primary_key=True)
    code = Column(String(40), nullable=False, unique=True)
    available = Column(Boolean, nullable=False, default=True)
    active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
class Request(Base):
    __tablename__ = 'requests'
    id = Column(Integer, primary_key=True)
    key = Column(String(80), nullable=False, unique=True)
    press_id = Column(ForeignKey('presses.id'), nullable=False, index=True)
    process_id = Column(ForeignKey('processes.id'), nullable=False)
    requester_id = Column(ForeignKey('users.id'), nullable=False)
    operator_id = Column(ForeignKey('users.id'), index=True)
    forklift_id = Column(ForeignKey('forklifts.id'), index=True)
    priority = Column(String(20), nullable=False)
    state = Column(String(40), nullable=False, default='Solicitado', index=True)
    required_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=now, index=True)
    delivered_at = Column(DateTime)
    receiver = Column(String(100))
    notes = Column(Text, nullable=False, default='')
    destination = Column(String(200), nullable=False, default='')
    risk = Column(String(30), nullable=False, default='Sin riesgo')
    version = Column(Integer, nullable=False, default=1)
    items = relationship('RequestItem', cascade='all, delete-orphan')
    __table_args__ = (CheckConstraint("priority IN ('Normal','Alta','Urgente')"),)

for _field in ['operator_id','forklift_id']:
    _predicate=text(f"{_field} IS NOT NULL AND state NOT IN ('Entregado','Cancelado')")
    Index('uq_requests_active_'+_field,getattr(Request,_field),unique=True,sqlite_where=_predicate,postgresql_where=_predicate)

class RequestItem(Base):
    __tablename__ = 'request_items'
    id = Column(Integer, primary_key=True)
    request_id = Column(ForeignKey('requests.id'), nullable=False, index=True)
    part_id = Column(ForeignKey('parts.id'), nullable=False)
    preferred_roll_id = Column(ForeignKey('rolls.id', name='fk_request_item_preferred_roll'))
    quantity = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint('request_id', 'part_id'), CheckConstraint('quantity > 0',name='ck_item_quantity_positive'))
class Roll(Base):
    __tablename__ = 'rolls'
    id = Column(Integer, primary_key=True)
    code = Column(String(80), nullable=False, unique=True)
    part_id = Column(ForeignKey('parts.id'), nullable=False, index=True)
    location_id = Column(ForeignKey('locations.id'), nullable=False, index=True)
    kg = Column(Float, nullable=False)
    source_data = Column(JSON)
    status = Column(String(20), nullable=False, default='DISP', index=True)
    request_id = Column(ForeignKey('requests.id'), index=True)
    version = Column(Integer, nullable=False, default=1)
    __table_args__ = (CheckConstraint('kg > 0'), CheckConstraint("status IN ('DISP','RESERVADO','ENTREGADO','BLOQUEADO')"))
class Incident(Base):
    __tablename__ = 'incidents'
    id = Column(Integer, primary_key=True)
    request_id = Column(ForeignKey('requests.id'), nullable=False, index=True)
    description = Column(Text, nullable=False)
    cause = Column(String(40), nullable=False, default='Otro')
    production_stopped = Column(Boolean, nullable=False, default=False)
    previous_state = Column(String(40), nullable=False)
    created_at = Column(DateTime, nullable=False, default=now)
    resolved_at = Column(DateTime)
    resolution = Column(Text)
class Audit(Base):
    __tablename__ = 'audit'
    id = Column(Integer, primary_key=True)
    request_id = Column(ForeignKey('requests.id'), index=True)
    user_id = Column(ForeignKey('users.id'), nullable=False)
    action = Column(String(80), nullable=False)
    detail = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=now, index=True)
class Handover(Base):
    __tablename__ = 'handovers'
    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False)
    incoming_shift = Column(String(8), nullable=False)
    receiving_user_id = Column(ForeignKey('users.id'), index=True)
    accepted_by_id = Column(ForeignKey('users.id'), index=True)
    accepted_at = Column(DateTime)
    acceptance_notes = Column(Text)
    notes = Column(Text, nullable=False)
    pending = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=now)
class HandoverItem(Base):
    __tablename__ = 'handover_items'
    id = Column(Integer, primary_key=True)
    handover_id = Column(ForeignKey('handovers.id'), nullable=False, index=True)
    request_id = Column(ForeignKey('requests.id'), nullable=False, index=True)
    snapshot = Column(Text, nullable=False)
    __table_args__ = (UniqueConstraint('handover_id', 'request_id'),)
class SimulationRun(Base):
    __tablename__ = 'simulation_runs'
    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False)
    parameters = Column(Text, nullable=False)
    result = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=now)

class InventoryImport(Base):
    __tablename__ = 'inventory_imports'
    id = Column(Integer, primary_key=True)
    token_digest = Column(String(64), nullable=False, unique=True)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    filename = Column(String(200), nullable=False)
    payload = Column(Text, nullable=False)
    update_existing = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=now)
    expires_at = Column(DateTime, nullable=False, index=True)
    committed_at = Column(DateTime)
