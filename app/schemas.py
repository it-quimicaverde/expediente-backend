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
    anticipo: Optional[str] = None
    complemento: Optional[str] = None
    fecha_emision_licencia: Optional[date] = None
    anios_licencia: Optional[int] = None
    nombre_producto: Optional[str] = None
    numero_registro: Optional[str] = None


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
    tipo_instrumento: Optional[str] = None
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
    activo: bool = True

    class Config:
        from_attributes = True


class UsuarioCreate(BaseModel):
    nombre: str
    email: EmailStr
    password: str
    rol: str = "gestor"


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = None
    rol: Optional[str] = None
    activo: Optional[bool] = None


class AsignacionEmpresas(BaseModel):
    usuario_ids: List[UUID]


class DashboardResumen(BaseModel):
    total_empresas: int
    empresas_sin_tramites: int


class TramiteDashboardOut(BaseModel):
    id: UUID
    empresa_id: UUID
    empresa_nombre: str
    tramite_nombre: str
    categoria: str
    numero_expediente: Optional[str] = None
    nombre_producto: Optional[str] = None
    fecha_vencimiento: Optional[date] = None
    estado: str
    creado_por_nombre: Optional[str] = None
    asignado_a_nombre: Optional[str] = None
    estatus_calculado: Optional[str] = None


class ImportacionError(BaseModel):
    fila: int
    motivo: str


class ImportacionResultado(BaseModel):
    total_filas: int
    creados: int
    empresas_creadas: int
    errores: List[ImportacionError]


class DocumentoOut(BaseModel):
    id: UUID
    tipo: str
    nombre_archivo: str
    tamano_bytes: Optional[int] = None
    subido_por_nombre: Optional[str] = None
    creado_en: datetime
    url_descarga: Optional[str] = None
    reparo_id: Optional[UUID] = None


class AuditoriaOut(BaseModel):
    campo: str
    valor_anterior: Optional[str] = None
    valor_nuevo: Optional[str] = None
    usuario_nombre: Optional[str] = None
    creado_en: datetime
    tramite_nombre: Optional[str] = None


class ReparoBase(BaseModel):
    fecha_emision: Optional[date] = None
    motivo_rechazo: Optional[str] = None
    fecha_vencimiento: Optional[date] = None
    fecha_paso_firma_respuesta: Optional[date] = None
    fecha_salida_mensajeria_respuesta: Optional[date] = None
    fecha_ingreso_respuesta: Optional[date] = None


class ReparoCreate(ReparoBase):
    numero: int


class ReparoUpdate(ReparoBase):
    pass


class ReparoOut(ReparoBase):
    id: UUID
    numero: int

    class Config:
        from_attributes = True


class TramiteUpdate(BaseModel):
    numero_expediente: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    estado: Optional[str] = None
    notas: Optional[str] = None
    checklist: Optional[List[dict]] = None
    asignado_a: Optional[UUID] = None
    fecha_paso_firma: Optional[date] = None
    fecha_salida_mensajeria: Optional[date] = None
    fecha_ingreso: Optional[date] = None
    resolucion_final: Optional[str] = None
    fecha_aprobacion: Optional[date] = None
    fecha_ingreso_instrumento: Optional[date] = None
    fecha_resolucion_aprobatoria: Optional[date] = None
    fecha_presentacion_solicitud: Optional[date] = None
    fecha_retiro_licencia: Optional[date] = None
    anticipo: Optional[str] = None
    complemento: Optional[str] = None
    fecha_emision_licencia: Optional[date] = None
    anios_licencia: Optional[int] = None
    nombre_producto: Optional[str] = None
    numero_registro: Optional[str] = None


class TramiteEmpresaOut(BaseModel):
    id: UUID
    tramite_nombre: str
    categoria: str
    numero_expediente: Optional[str] = None
    fecha_inicio: date
    fecha_vencimiento: Optional[date] = None
    estado: str
    checklist: List[dict] = []
    creado_por_nombre: Optional[str] = None
    asignado_a: Optional[UUID] = None
    asignado_a_nombre: Optional[str] = None
    fecha_paso_firma: Optional[date] = None
    fecha_salida_mensajeria: Optional[date] = None
    fecha_ingreso: Optional[date] = None
    resolucion_final: Optional[str] = None
    fecha_aprobacion: Optional[date] = None
    fecha_ingreso_instrumento: Optional[date] = None
    fecha_resolucion_aprobatoria: Optional[date] = None
    fecha_presentacion_solicitud: Optional[date] = None
    fecha_retiro_licencia: Optional[date] = None
    anticipo: Optional[str] = None
    complemento: Optional[str] = None
    fecha_emision_licencia: Optional[date] = None
    anios_licencia: Optional[int] = None
    nombre_producto: Optional[str] = None
    numero_registro: Optional[str] = None
    documentos: List[DocumentoOut] = []
    reparos: List[ReparoOut] = []
    estatus_calculado: Optional[str] = None
