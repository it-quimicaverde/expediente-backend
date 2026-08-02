import uuid
from datetime import date, datetime

from sqlalchemy import (
    Column, String, Boolean, Integer, Date, DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base


class Organizacion(Base):
    __tablename__ = "organizacion"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(200), nullable=False)
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)

    usuarios = relationship("Usuario", back_populates="organizacion")
    empresas = relationship("EmpresaCliente", back_populates="organizacion")


class Usuario(Base):
    __tablename__ = "usuario"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organizacion_id = Column(UUID(as_uuid=True), ForeignKey("organizacion.id"), nullable=False)
    nombre = Column(String(150), nullable=False)
    email = Column(String(200), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    rol = Column(String(20), nullable=False)  # 'admin' | 'gestor'
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)

    organizacion = relationship("Organizacion", back_populates="usuarios")


class EmpresaCliente(Base):
    __tablename__ = "empresa_cliente"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organizacion_id = Column(UUID(as_uuid=True), ForeignKey("organizacion.id"), nullable=False)
    nombre = Column(String(250), nullable=False)
    nit = Column(String(30))
    contacto_nombre = Column(String(150))
    contacto_email = Column(String(200))
    contacto_telefono = Column(String(30))
    notas = Column(Text)
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)

    organizacion = relationship("Organizacion", back_populates="empresas")
    tramites = relationship("Tramite", back_populates="empresa_cliente")


class TipoTramite(Base):
    __tablename__ = "tipo_tramite"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    categoria = Column(String(20), nullable=False)  # ambiente | farma | alimentos | sso | otros
    nombre = Column(String(250), nullable=False)
    institucion = Column(String(100))
    tipo_gestion = Column(String(100))
    tipo_instrumento = Column(String(10), nullable=True)  # EAI | DABI | EIA | DA | FAR | FACR (solo Ambiente)
    vigencia_meses = Column(Integer, nullable=True)
    es_recurrente = Column(Boolean, default=False)
    frecuencia_dias = Column(Integer, nullable=True)
    checklist_default = Column(JSON, default=list)
    notas = Column(Text)


class Tramite(Base):
    __tablename__ = "tramite"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empresa_cliente_id = Column(UUID(as_uuid=True), ForeignKey("empresa_cliente.id"), nullable=False)
    tipo_tramite_id = Column(UUID(as_uuid=True), ForeignKey("tipo_tramite.id"), nullable=False)
    asignado_a = Column(UUID(as_uuid=True), ForeignKey("usuario.id"), nullable=True)
    creado_por_id = Column(UUID(as_uuid=True), ForeignKey("usuario.id"), nullable=True)
    numero_expediente = Column(String(100))
    fecha_inicio = Column(Date, nullable=False, default=date.today)
    fecha_vencimiento = Column(Date, nullable=True)
    estado = Column(String(20), default="en_tramite")
    checklist = Column(JSON, default=list)
    notas = Column(Text)

    # Flujo interno de gestión (aplica sobre todo a Alimentos, Farma, Otros)
    fecha_paso_firma = Column(Date, nullable=True)          # se lleva a firma con la jefatura
    fecha_salida_mensajeria = Column(Date, nullable=True)   # sale hacia el ministerio
    fecha_ingreso = Column(Date, nullable=True)              # el ministerio lo recibe/registra
    resolucion_final = Column(String(20), nullable=True)     # aprobado | baja | finalizado | pendiente

    # Flujo propio de Ambiente (licencias/instrumentos ante el MARN)
    fecha_ingreso_instrumento = Column(Date, nullable=True)       # ingreso del instrumento a MARN
    fecha_resolucion_aprobatoria = Column(Date, nullable=True)    # resolución aprobatoria del instrumento
    fecha_presentacion_solicitud = Column(Date, nullable=True)    # presentación de solicitud de licencia
    fecha_retiro_licencia = Column(Date, nullable=True)           # retiro de licencia ambiental
    fecha_emision_licencia = Column(Date, nullable=True)          # fecha de emisión de la licencia ambiental
    anios_licencia = Column(Integer, nullable=True)                # años pagados; decide el usuario caso por caso
    # (el vencimiento de la licencia usa el fecha_vencimiento general que ya existe)

    # Seguimiento de pagos (aplica a cualquier categoría)
    anticipo = Column(Text, nullable=True)
    complemento = Column(Text, nullable=True)

    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)
    actualizado_en = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa_cliente = relationship("EmpresaCliente", back_populates="tramites")
    tipo_tramite = relationship("TipoTramite")
    creado_por = relationship("Usuario", foreign_keys=[creado_por_id])
    asignado_a_usuario = relationship("Usuario", foreign_keys=[asignado_a])
    reparos = relationship("Reparo", back_populates="tramite", order_by="Reparo.numero", cascade="all, delete-orphan")


class Reparo(Base):
    __tablename__ = "reparo"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tramite_id = Column(UUID(as_uuid=True), ForeignKey("tramite.id", ondelete="CASCADE"), nullable=False)
    numero = Column(Integer, nullable=False)  # 1, 2 o 3

    fecha_emision = Column(Date, nullable=True)
    motivo_rechazo = Column(Text, nullable=True)
    fecha_vencimiento = Column(Date, nullable=True)  # plazo para responder — aquí aplican las alertas 89/60/30/10

    fecha_paso_firma_respuesta = Column(Date, nullable=True)
    fecha_salida_mensajeria_respuesta = Column(Date, nullable=True)
    fecha_ingreso_respuesta = Column(Date, nullable=True)

    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)

    tramite = relationship("Tramite", back_populates="reparos")


class UsuarioEmpresaCliente(Base):
    __tablename__ = "usuario_empresa_cliente"
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuario.id"), primary_key=True)
    empresa_cliente_id = Column(UUID(as_uuid=True), ForeignKey("empresa_cliente.id"), primary_key=True)


class AuditoriaTramite(Base):
    __tablename__ = "auditoria_tramite"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tramite_id = Column(UUID(as_uuid=True), nullable=False)  # sin FK: debe sobrevivir al borrado del trámite
    empresa_id = Column(UUID(as_uuid=True), nullable=True)
    empresa_nombre = Column(Text, nullable=True)
    tramite_nombre = Column(Text, nullable=True)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuario.id"), nullable=True)
    campo = Column(String(50), nullable=False)
    valor_anterior = Column(Text, nullable=True)
    valor_nuevo = Column(Text, nullable=True)
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)

    usuario = relationship("Usuario")


class Alerta(Base):
    __tablename__ = "alerta"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tramite_id = Column(UUID(as_uuid=True), ForeignKey("tramite.id"), nullable=False)
    reparo_id = Column(UUID(as_uuid=True), ForeignKey("reparo.id", ondelete="CASCADE"), nullable=True)
    dias_previos = Column(Integer, nullable=False)
    fecha_programada = Column(Date, nullable=False)
    enviada = Column(Boolean, default=False)
    enviada_en = Column(DateTime(timezone=True), nullable=True)
    canal = Column(String(20), default="email")
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)
