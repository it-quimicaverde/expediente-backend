from datetime import date, timedelta
from typing import List
from uuid import UUID

from dateutil.relativedelta import relativedelta
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import asc

from . import models, schemas, auth
from .database import engine, get_db, Base

# Crea las tablas si no existen (para desarrollo; en producción usar Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Expediente API")

# CORS abierto: la seguridad real la da el token JWT en cada petición, no el origen.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- Autenticación ----------
@app.post("/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    token = auth.create_access_token(data={"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}


@app.get("/auth/me", response_model=schemas.UsuarioOut)
def me(current_user: models.Usuario = Depends(auth.get_current_user)):
    return current_user


# ---------- Empresas cliente ----------
@app.get("/empresas", response_model=List[schemas.EmpresaClienteOut])
def listar_empresas(
    q: str = "",
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_user),
):
    query = db.query(models.EmpresaCliente)
    if q:
        query = query.filter(models.EmpresaCliente.nombre.ilike(f"%{q}%"))
    return query.order_by(models.EmpresaCliente.nombre).limit(100).all()


@app.post("/empresas", response_model=schemas.EmpresaClienteOut)
def crear_empresa(
    empresa: schemas.EmpresaClienteCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.require_admin),
):
    org = db.query(models.Organizacion).first()
    if not org:
        raise HTTPException(status_code=500, detail="No hay ninguna organización creada todavía")

    nueva = models.EmpresaCliente(organizacion_id=org.id, **empresa.model_dump())
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva


@app.get("/empresas/{empresa_id}", response_model=schemas.EmpresaClienteOut)
def obtener_empresa(
    empresa_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_user),
):
    empresa = db.query(models.EmpresaCliente).filter(models.EmpresaCliente.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return empresa


# ---------- Tipos de trámite (catálogo) ----------
@app.get("/tipos-tramite", response_model=List[schemas.TipoTramiteOut])
def listar_tipos_tramite(
    categoria: str = "",
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_user),
):
    query = db.query(models.TipoTramite)
    if categoria:
        query = query.filter(models.TipoTramite.categoria == categoria.lower())
    return query.all()


# ---------- Trámites ----------
@app.get("/dashboard/proximos-vencer", response_model=List[schemas.TramiteDashboardOut])
def proximos_a_vencer(
    dias: int = 30,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_user),
):
    limite = date.today() + timedelta(days=dias)
    tramites = (
        db.query(models.Tramite)
        .options(
            joinedload(models.Tramite.empresa_cliente),
            joinedload(models.Tramite.tipo_tramite),
        )
        .filter(models.Tramite.fecha_vencimiento.isnot(None))
        .filter(models.Tramite.fecha_vencimiento <= limite)
        .order_by(asc(models.Tramite.fecha_vencimiento))
        .all()
    )
    return [
        schemas.TramiteDashboardOut(
            id=t.id,
            empresa_id=t.empresa_cliente_id,
            empresa_nombre=t.empresa_cliente.nombre,
            tramite_nombre=t.tipo_tramite.nombre,
            categoria=t.tipo_tramite.categoria,
            numero_expediente=t.numero_expediente,
            fecha_vencimiento=t.fecha_vencimiento,
            estado=t.estado,
        )
        for t in tramites
    ]


@app.post("/tramites", response_model=schemas.TramiteOut)
def crear_tramite(
    tramite: schemas.TramiteCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_user),
):
    tipo = db.query(models.TipoTramite).filter(models.TipoTramite.id == tramite.tipo_tramite_id).first()
    if not tipo:
        raise HTTPException(status_code=404, detail="Tipo de trámite no encontrado")

    # Autocompleta fecha de vencimiento y checklist según el catálogo
    data = tramite.model_dump()
    if tipo.vigencia_meses and not data.get("fecha_vencimiento"):
        data["fecha_vencimiento"] = data["fecha_inicio"] + relativedelta(months=tipo.vigencia_meses)

    nuevo = models.Tramite(**data)
    nuevo.checklist = [{"item": doc, "completado": False} for doc in (tipo.checklist_default or [])]
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@app.get("/empresas/{empresa_id}/tramites", response_model=List[schemas.TramiteEmpresaOut])
def tramites_de_empresa(
    empresa_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_user),
):
    tramites = (
        db.query(models.Tramite)
        .options(joinedload(models.Tramite.tipo_tramite))
        .filter(models.Tramite.empresa_cliente_id == empresa_id)
        .order_by(models.Tramite.fecha_vencimiento)
        .all()
    )
    return [
        schemas.TramiteEmpresaOut(
            id=t.id,
            tramite_nombre=t.tipo_tramite.nombre,
            categoria=t.tipo_tramite.categoria,
            numero_expediente=t.numero_expediente,
            fecha_inicio=t.fecha_inicio,
            fecha_vencimiento=t.fecha_vencimiento,
            estado=t.estado,
            checklist=t.checklist or [],
        )
        for t in tramites
    ]
