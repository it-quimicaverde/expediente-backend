from datetime import date, timedelta
from typing import List
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import asc

from . import models, schemas
from .database import engine, get_db, Base

# Crea las tablas si no existen (para desarrollo; en producción usar Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Expediente API")

# Ajusta esto al dominio real de tu frontend en Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://tu-frontend.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- Empresas cliente ----------
@app.get("/empresas", response_model=List[schemas.EmpresaClienteOut])
def listar_empresas(q: str = "", db: Session = Depends(get_db)):
    query = db.query(models.EmpresaCliente)
    if q:
        query = query.filter(models.EmpresaCliente.nombre.ilike(f"%{q}%"))
    return query.order_by(models.EmpresaCliente.nombre).limit(100).all()


@app.post("/empresas", response_model=schemas.EmpresaClienteOut)
def crear_empresa(empresa: schemas.EmpresaClienteCreate, db: Session = Depends(get_db)):
    # organizacion_id vendrá del usuario autenticado; se deja fijo aquí como placeholder
    nueva = models.EmpresaCliente(**empresa.model_dump())
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva


# ---------- Tipos de trámite (catálogo) ----------
@app.get("/tipos-tramite", response_model=List[schemas.TipoTramiteOut])
def listar_tipos_tramite(categoria: str = "", db: Session = Depends(get_db)):
    query = db.query(models.TipoTramite)
    if categoria:
        query = query.filter(models.TipoTramite.categoria == categoria)
    return query.all()


# ---------- Trámites ----------
@app.get("/dashboard/proximos-vencer", response_model=List[schemas.TramiteOut])
def proximos_a_vencer(dias: int = 30, db: Session = Depends(get_db)):
    limite = date.today() + timedelta(days=dias)
    return (
        db.query(models.Tramite)
        .filter(models.Tramite.fecha_vencimiento.isnot(None))
        .filter(models.Tramite.fecha_vencimiento <= limite)
        .order_by(asc(models.Tramite.fecha_vencimiento))
        .all()
    )


@app.post("/tramites", response_model=schemas.TramiteOut)
def crear_tramite(tramite: schemas.TramiteCreate, db: Session = Depends(get_db)):
    tipo = db.query(models.TipoTramite).filter(models.TipoTramite.id == tramite.tipo_tramite_id).first()
    if not tipo:
        raise HTTPException(status_code=404, detail="Tipo de trámite no encontrado")

    # Autocompleta fecha de vencimiento y checklist según el catálogo
    data = tramite.model_dump()
    if tipo.vigencia_meses and not data.get("fecha_vencimiento"):
        data["fecha_vencimiento"] = data["fecha_inicio"] + timedelta(days=tipo.vigencia_meses * 30)

    nuevo = models.Tramite(**data)
    nuevo.checklist = [{"item": doc, "completado": False} for doc in (tipo.checklist_default or [])]
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@app.get("/empresas/{empresa_id}/tramites", response_model=List[schemas.TramiteOut])
def tramites_de_empresa(empresa_id: UUID, db: Session = Depends(get_db)):
    return (
        db.query(models.Tramite)
        .filter(models.Tramite.empresa_cliente_id == empresa_id)
        .order_by(models.Tramite.fecha_vencimiento)
        .all()
    )
