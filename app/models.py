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
    numero_expediente = Column(String(100))
    fecha_inicio = Column(Date, nullable=False, default=date.today)
    fecha_vencimiento = Column(Date, nullable=True)
    estado = Column(String(20), default="en_tramite")
    checklist = Column(JSON, default=list)
    notas = Column(Text)
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)
    actualizado_en = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa_cliente = relationship("EmpresaCliente", back_populates="tramites")
    tipo_tramite = relationship("TipoTramite")


class UsuarioEmpresaCliente(Base):
    __tablename__ = "usuario_empresa_cliente"
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuario.id"), primary_key=True)
    empresa_cliente_id = Column(UUID(as_uuid=True), ForeignKey("empresa_cliente.id"), primary_key=True)


class Alerta(Base):
    __tablename__ = "alerta"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tramite_id = Column(UUID(as_uuid=True), ForeignKey("tramite.id"), nullable=False)
    dias_previos = Column(Integer, nullable=False)
    fecha_programada = Column(Date, nullable=False)
    enviada = Column(Boolean, default=False)
    enviada_en = Column(DateTime(timezone=True), nullable=True)
    canal = Column(String(20), default="email")
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)
