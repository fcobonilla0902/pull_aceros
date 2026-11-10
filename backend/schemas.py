from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
class Login(Strict):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)
class UserInput(Strict):
    username: str = Field(min_length=3, max_length=80, pattern=r'^[a-zA-Z0-9_.-]+$')
    password: str = Field(min_length=12, max_length=200)
    role_id: int
class ItemInput(Strict):
    preferred_roll_id: int | None = None
    part_id: int
    quantity: int = Field(ge=1, le=100)
class RequestFields(Strict):
    press_id: int
    process_id: int
    priority: Literal['Normal','Alta','Urgente'] = 'Normal'
    risk: Literal['Sin riesgo','Riesgo de paro','Línea detenida'] = 'Sin riesgo'
    destination: str = Field('', max_length=200)
    required_at: datetime
    notes: str = Field('', max_length=2000)
    items: list[ItemInput] = Field(min_length=1, max_length=50)
    @field_validator('required_at')
    @classmethod
    def utc_date(cls, value):
        from datetime import timezone
        if value.tzinfo is None: raise ValueError('Incluye zona horaria')
        return value.astimezone(timezone.utc).replace(tzinfo=None)
class RequestInput(RequestFields):
    key: str = Field(min_length=16, max_length=80)
class RequestRevision(RequestFields):
    version: int = Field(ge=1)
    justification: str = Field(min_length=3, max_length=2000)
class UserUpdate(Strict):
    version: int = Field(ge=1)
    username: str = Field(min_length=3, max_length=80, pattern=r'^[a-zA-Z0-9_.-]+$')
    role_id: int
    active: bool
class PasswordChange(Strict):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)
class PasswordReset(Strict):
    new_password: str = Field(min_length=12, max_length=200)
class CatalogUpdate(Strict):
    version: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=80)
    specification: str = Field('',max_length=200)
    active: bool = True
class ImportCommit(Strict):
    token: str = Field(min_length=32, max_length=128)
class ActionInput(Strict):
    version: int = Field(ge=1)
    action: Literal['validate','assign','prepare','ready','transport','deliver','incident','resolve','edit','cancel']
    operator_id: int | None = None
    forklift_id: int | None = None
    roll_ids: list[int] | None = Field(None, min_length=1, max_length=100)
    receiver: str = Field('', max_length=100)
    notes: str = Field('', max_length=2000)
    cause: Literal['Material no disponible','Rollo no localizado','Especificación incorrecta','Falta de personal','Equipo no disponible','Pasillo obstruido','Otro'] = 'Otro'
    production_stopped: bool = False
    priority: Literal['Normal','Alta','Urgente'] | None = None
class RollInput(Strict):
    code: str = Field(min_length=1, max_length=80)
    part_id: int
    location_id: int
    kg: float = Field(gt=0, le=1000000, allow_inf_nan=False)
class CatalogInput(Strict):
    name: str = Field(min_length=1, max_length=80)
    specification: str = Field('', max_length=200)
    available: bool = True
class HandoverInput(Strict):
    incoming_shift: Literal['T1','T2','T3']
    notes: str = Field(min_length=3, max_length=4000)
    receiving_user_id: int | None = None
class HandoverAcceptance(Strict):
    notes: str = Field(min_length=3, max_length=2000)
