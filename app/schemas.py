from datetime import date, datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr


class EmpresaClienteBase(BaseModel):
    nombre: str
    nit: Optional[str] = None
    contacto_nombre: Optional[str] = None
    contacto_email: Optional[EmailStr] = None
    contacto_telefono: Optional[str] = None
    notas: Optional[str] = None


class EmpresaClienteCreate(EmpresaClienteBase):
    pass


class EmpresaClienteOut(EmpresaClienteBase):
    id: UUID
    creado_en: datetime

    class Config:
        from_attributes = True


class EmpresaClienteUpdate(BaseModel):
    nombre: Optional[str] = None
    nit: Optional[str] = None
    contacto_nombre: Optional[str] = None
    contacto_email: Optional[EmailStr] = None
    contacto_telefono: Optional[str] = None
    notas: Optional[str] = None


class TramiteBase(BaseModel):
    empresa_cliente_id: UUID
    tipo_tramite_id: UUID
    asignado_a: Optional[UUID] = None
    numero_expediente: Optional[str] = None
    fecha_inicio: date
    fecha_vencimiento: Optional[date] = None
    estado: str = "en_tramite"
    notas: Optional[str] = None


class TramiteCreate(TramiteBase):
    pass


class TramiteOut(TramiteBase):
    id: UUID
    checklist: List[dict] = []
    creado_en: datetime

    class Config:
        from_attributes = True


class TipoTramiteOut(BaseModel):
    id: UUID
    categoria: str
    nombre: str
    institucion: Optional[str]
    tipo_gestion: Optional[str]
    vigencia_meses: Optional[int]
    es_recurrente: bool
    checklist_default: List[str] = []

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UsuarioOut(BaseModel):
    id: UUID
    nombre: str
    email: EmailStr
    rol: str

    class Config:
        from_attributes = True


class TramiteDashboardOut(BaseModel):
    id: UUID
    empresa_id: UUID
    empresa_nombre: str
    tramite_nombre: str
    categoria: str
    numero_expediente: Optional[str] = None
    fecha_vencimiento: Optional[date] = None
    estado: str


class TramiteUpdate(BaseModel):
    numero_expediente: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    estado: Optional[str] = None
    notas: Optional[str] = None
    checklist: Optional[List[dict]] = None


class TramiteEmpresaOut(BaseModel):
    id: UUID
    tramite_nombre: str
    categoria: str
    numero_expediente: Optional[str] = None
    fecha_inicio: date
    fecha_vencimiento: Optional[date] = None
    estado: str
    checklist: List[dict] = []
