import csv
import io
from datetime import date, timedelta
from typing import List
from uuid import UUID

from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import asc

from . import models, schemas, auth
from .database import engine, get_db, Base
from .alertas_job import ejecutar_revision_alertas

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


def empresas_asignadas_ids(db: Session, usuario_id) -> list:
    filas = (
        db.query(models.UsuarioEmpresaCliente.empresa_cliente_id)
        .filter(models.UsuarioEmpresaCliente.usuario_id == usuario_id)
        .all()
    )
    return [f[0] for f in filas]


def verificar_acceso_empresa(db: Session, current_user: models.Usuario, empresa_id) -> None:
    """Lanza 403 si un gestor intenta acceder a una empresa que no tiene asignada."""
    if current_user.rol == "admin":
        return
    asignadas = empresas_asignadas_ids(db, current_user.id)
    if empresa_id not in asignadas:
        raise HTTPException(status_code=403, detail="No tienes esta empresa asignada")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/admin/enviar-alertas")
def enviar_alertas_manual(current_user: models.Usuario = Depends(auth.require_admin)):
    return ejecutar_revision_alertas()


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
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_user),
):
    query = db.query(models.EmpresaCliente)
    if current_user.rol != "admin":
        asignadas = empresas_asignadas_ids(db, current_user.id)
        query = query.filter(models.EmpresaCliente.id.in_(asignadas))
    if q:
        query = query.filter(models.EmpresaCliente.nombre.ilike(f"%{q}%"))
    return query.order_by(models.EmpresaCliente.nombre).offset(offset).limit(min(limit, 200)).all()


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
    verificar_acceso_empresa(db, current_user, empresa_id)
    empresa = db.query(models.EmpresaCliente).filter(models.EmpresaCliente.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return empresa


@app.patch("/empresas/{empresa_id}", response_model=schemas.EmpresaClienteOut)
def editar_empresa(
    empresa_id: UUID,
    cambios: schemas.EmpresaClienteUpdate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.require_admin),
):
    empresa = db.query(models.EmpresaCliente).filter(models.EmpresaCliente.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    for campo, valor in cambios.model_dump(exclude_unset=True).items():
        setattr(empresa, campo, valor)

    db.commit()
    db.refresh(empresa)
    return empresa


# ---------- Usuarios (gestión de cuentas, solo admin) ----------
@app.get("/gestores", response_model=List[schemas.UsuarioOut])
def listar_gestores_disponibles(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_user),
):
    return (
        db.query(models.Usuario)
        .filter(models.Usuario.activo.is_(True))
        .order_by(models.Usuario.nombre)
        .all()
    )


@app.get("/usuarios", response_model=List[schemas.UsuarioOut])
def listar_usuarios(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.require_admin),
):
    return db.query(models.Usuario).order_by(models.Usuario.nombre).all()


@app.post("/usuarios", response_model=schemas.UsuarioOut)
def crear_usuario(
    datos: schemas.UsuarioCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.require_admin),
):
    existente = db.query(models.Usuario).filter(models.Usuario.email == datos.email).first()
    if existente:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese correo")

    org = db.query(models.Organizacion).first()
    nuevo = models.Usuario(
        organizacion_id=org.id,
        nombre=datos.nombre,
        email=datos.email,
        password_hash=auth.hash_password(datos.password),
        rol=datos.rol,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@app.patch("/usuarios/{usuario_id}", response_model=schemas.UsuarioOut)
def editar_usuario(
    usuario_id: UUID,
    cambios: schemas.UsuarioUpdate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.require_admin),
):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if usuario.id == current_user.id and cambios.rol and cambios.rol != "admin":
        raise HTTPException(status_code=400, detail="No puedes quitarte a ti mismo el rol de admin")

    for campo, valor in cambios.model_dump(exclude_unset=True).items():
        setattr(usuario, campo, valor)

    db.commit()
    db.refresh(usuario)
    return usuario


@app.get("/empresas/{empresa_id}/gestores", response_model=List[schemas.UsuarioOut])
def listar_gestores_de_empresa(
    empresa_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.require_admin),
):
    return (
        db.query(models.Usuario)
        .join(models.UsuarioEmpresaCliente, models.UsuarioEmpresaCliente.usuario_id == models.Usuario.id)
        .filter(models.UsuarioEmpresaCliente.empresa_cliente_id == empresa_id)
        .all()
    )


@app.put("/empresas/{empresa_id}/gestores")
def asignar_gestores(
    empresa_id: UUID,
    datos: schemas.AsignacionEmpresas,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.require_admin),
):
    db.query(models.UsuarioEmpresaCliente).filter(
        models.UsuarioEmpresaCliente.empresa_cliente_id == empresa_id
    ).delete()
    for usuario_id in datos.usuario_ids:
        db.add(models.UsuarioEmpresaCliente(usuario_id=usuario_id, empresa_cliente_id=empresa_id))
    db.commit()
    return {"status": "ok"}


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
@app.post("/tramites/importar-csv", response_model=schemas.ImportacionResultado)
def importar_tramites_csv(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.require_admin),
):
    """
    Columnas esperadas en el CSV (con encabezados exactos):
    empresa_nombre, categoria, tipo_tramite_nombre, tipo_gestion (opcional),
    fecha_inicio, numero_expediente (opcional), fecha_vencimiento (opcional)
    """
    org = db.query(models.Organizacion).first()

    contenido = archivo.file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(contenido))

    errores = []
    creados = 0
    empresas_creadas = 0
    empresas_cache = {}
    total_filas = 0

    for i, fila in enumerate(reader, start=2):  # fila 1 es el encabezado
        total_filas += 1
        try:
            empresa_nombre = (fila.get("empresa_nombre") or "").strip()
            categoria = (fila.get("categoria") or "").strip().lower()
            tipo_nombre = (fila.get("tipo_tramite_nombre") or "").strip()
            tipo_gestion = (fila.get("tipo_gestion") or "").strip()
            fecha_inicio_raw = (fila.get("fecha_inicio") or "").strip()
            numero_expediente = (fila.get("numero_expediente") or "").strip() or None
            fecha_vencimiento_raw = (fila.get("fecha_vencimiento") or "").strip()

            if not empresa_nombre or not categoria or not tipo_nombre or not fecha_inicio_raw:
                errores.append(schemas.ImportacionError(
                    fila=i, motivo="Faltan datos obligatorios (empresa, categoría, tipo de trámite o fecha de inicio)"
                ))
                continue

            fecha_inicio = date_parser.parse(fecha_inicio_raw, dayfirst=True).date()
            fecha_vencimiento = None
            if fecha_vencimiento_raw:
                fecha_vencimiento = date_parser.parse(fecha_vencimiento_raw, dayfirst=True).date()

            # Buscar o crear la empresa
            clave_empresa = empresa_nombre.lower()
            if clave_empresa in empresas_cache:
                empresa = empresas_cache[clave_empresa]
            else:
                empresa = (
                    db.query(models.EmpresaCliente)
                    .filter(models.EmpresaCliente.nombre.ilike(empresa_nombre))
                    .first()
                )
                if not empresa:
                    empresa = models.EmpresaCliente(organizacion_id=org.id, nombre=empresa_nombre)
                    db.add(empresa)
                    db.flush()
                    empresas_creadas += 1
                empresas_cache[clave_empresa] = empresa

            # Buscar el tipo de trámite en el catálogo
            tipo_query = db.query(models.TipoTramite).filter(
                models.TipoTramite.categoria == categoria,
                models.TipoTramite.nombre.ilike(tipo_nombre),
            )
            if tipo_gestion:
                tipo_query = tipo_query.filter(models.TipoTramite.tipo_gestion.ilike(tipo_gestion))
            tipo = tipo_query.first()

            if not tipo:
                errores.append(schemas.ImportacionError(
                    fila=i,
                    motivo=f"No se encontró en el catálogo: categoría '{categoria}', trámite '{tipo_nombre}'"
                    + (f", gestión '{tipo_gestion}'" if tipo_gestion else ""),
                ))
                continue

            if not fecha_vencimiento and tipo.vigencia_meses:
                fecha_vencimiento = fecha_inicio + relativedelta(months=tipo.vigencia_meses)

            nuevo = models.Tramite(
                empresa_cliente_id=empresa.id,
                tipo_tramite_id=tipo.id,
                numero_expediente=numero_expediente,
                fecha_inicio=fecha_inicio,
                fecha_vencimiento=fecha_vencimiento,
                creado_por_id=current_user.id,
                checklist=[{"item": doc, "completado": False} for doc in (tipo.checklist_default or [])],
            )
            db.add(nuevo)
            creados += 1

        except Exception as e:
            errores.append(schemas.ImportacionError(fila=i, motivo=f"Error inesperado: {str(e)}"))

    db.commit()

    return schemas.ImportacionResultado(
        total_filas=total_filas,
        creados=creados,
        empresas_creadas=empresas_creadas,
        errores=errores,
    )


@app.get("/tramites/buscar", response_model=List[schemas.TramiteDashboardOut])
def buscar_tramites(
    q: str = "",
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_user),
):
    if not q or len(q) < 2:
        return []

    query = (
        db.query(models.Tramite)
        .options(
            joinedload(models.Tramite.empresa_cliente),
            joinedload(models.Tramite.tipo_tramite),
            joinedload(models.Tramite.creado_por),
            joinedload(models.Tramite.asignado_a_usuario),
        )
        .filter(models.Tramite.numero_expediente.ilike(f"%{q}%"))
    )
    if current_user.rol != "admin":
        asignadas = empresas_asignadas_ids(db, current_user.id)
        query = query.filter(models.Tramite.empresa_cliente_id.in_(asignadas))

    tramites = query.limit(20).all()
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
            creado_por_nombre=t.creado_por.nombre if t.creado_por else None,
            asignado_a_nombre=t.asignado_a_usuario.nombre if t.asignado_a_usuario else None,
        )
        for t in tramites
    ]


@app.get("/dashboard/resumen", response_model=schemas.DashboardResumen)
def resumen_dashboard(
    gestor_id: str = "",
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_user),
):
    query = db.query(models.EmpresaCliente)
    if current_user.rol != "admin":
        asignadas = empresas_asignadas_ids(db, current_user.id)
        query = query.filter(models.EmpresaCliente.id.in_(asignadas))
    elif gestor_id:
        asignadas = empresas_asignadas_ids(db, gestor_id)
        query = query.filter(models.EmpresaCliente.id.in_(asignadas))

    empresas = query.all()
    total = len(empresas)
    sin_tramites = sum(1 for e in empresas if len(e.tramites) == 0)
    return schemas.DashboardResumen(total_empresas=total, empresas_sin_tramites=sin_tramites)


@app.get("/dashboard/proximos-vencer", response_model=List[schemas.TramiteDashboardOut])
def proximos_a_vencer(
    dias: int = 30,
    gestor_id: str = "",
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_user),
):
    limite = date.today() + timedelta(days=dias)
    query = (
        db.query(models.Tramite)
        .options(
            joinedload(models.Tramite.empresa_cliente),
            joinedload(models.Tramite.tipo_tramite),
            joinedload(models.Tramite.creado_por),
            joinedload(models.Tramite.asignado_a_usuario),
        )
        .filter(models.Tramite.fecha_vencimiento.isnot(None))
        .filter(models.Tramite.fecha_vencimiento <= limite)
    )
    if current_user.rol != "admin":
        asignadas = empresas_asignadas_ids(db, current_user.id)
        query = query.filter(models.Tramite.empresa_cliente_id.in_(asignadas))
    elif gestor_id:
        asignadas = empresas_asignadas_ids(db, gestor_id)
        query = query.filter(models.Tramite.empresa_cliente_id.in_(asignadas))

    tramites = query.order_by(asc(models.Tramite.fecha_vencimiento)).all()
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
            creado_por_nombre=t.creado_por.nombre if t.creado_por else None,
            asignado_a_nombre=t.asignado_a_usuario.nombre if t.asignado_a_usuario else None,
        )
        for t in tramites
    ]


@app.post("/tramites", response_model=schemas.TramiteOut)
def crear_tramite(
    tramite: schemas.TramiteCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_user),
):
    verificar_acceso_empresa(db, current_user, tramite.empresa_cliente_id)

    tipo = db.query(models.TipoTramite).filter(models.TipoTramite.id == tramite.tipo_tramite_id).first()
    if not tipo:
        raise HTTPException(status_code=404, detail="Tipo de trámite no encontrado")

    # Autocompleta fecha de vencimiento y checklist según el catálogo
    data = tramite.model_dump()
    if tipo.vigencia_meses and not data.get("fecha_vencimiento"):
        data["fecha_vencimiento"] = data["fecha_inicio"] + relativedelta(months=tipo.vigencia_meses)

    nuevo = models.Tramite(**data)
    nuevo.creado_por_id = current_user.id
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
    verificar_acceso_empresa(db, current_user, empresa_id)
    tramites = (
        db.query(models.Tramite)
        .options(joinedload(models.Tramite.tipo_tramite), joinedload(models.Tramite.creado_por), joinedload(models.Tramite.asignado_a_usuario))
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
            creado_por_nombre=t.creado_por.nombre if t.creado_por else None,
            asignado_a=t.asignado_a,
            asignado_a_nombre=t.asignado_a_usuario.nombre if t.asignado_a_usuario else None,
        )
        for t in tramites
    ]


@app.patch("/tramites/{tramite_id}", response_model=schemas.TramiteEmpresaOut)
def editar_tramite(
    tramite_id: UUID,
    cambios: schemas.TramiteUpdate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_user),
):
    tramite = (
        db.query(models.Tramite)
        .options(
            joinedload(models.Tramite.tipo_tramite),
            joinedload(models.Tramite.creado_por),
            joinedload(models.Tramite.asignado_a_usuario),
            joinedload(models.Tramite.empresa_cliente),
        )
        .filter(models.Tramite.id == tramite_id)
        .first()
    )
    if not tramite:
        raise HTTPException(status_code=404, detail="Trámite no encontrado")

    CAMPOS_AUDITABLES = {"numero_expediente", "fecha_inicio", "fecha_vencimiento", "estado", "asignado_a", "notas"}
    cambios_dict = cambios.model_dump(exclude_unset=True)
    for campo, valor_nuevo in cambios_dict.items():
        if campo not in CAMPOS_AUDITABLES:
            continue
        valor_anterior = getattr(tramite, campo)
        if str(valor_anterior) != str(valor_nuevo):
            db.add(models.AuditoriaTramite(
                tramite_id=tramite.id,
                empresa_id=tramite.empresa_cliente_id,
                empresa_nombre=tramite.empresa_cliente.nombre,
                tramite_nombre=tramite.tipo_tramite.nombre,
                usuario_id=current_user.id,
                campo=campo,
                valor_anterior=str(valor_anterior) if valor_anterior is not None else None,
                valor_nuevo=str(valor_nuevo) if valor_nuevo is not None else None,
            ))

    for campo, valor in cambios_dict.items():
        setattr(tramite, campo, valor)

    db.commit()
    db.refresh(tramite)
    return schemas.TramiteEmpresaOut(
        id=tramite.id,
        tramite_nombre=tramite.tipo_tramite.nombre,
        categoria=tramite.tipo_tramite.categoria,
        numero_expediente=tramite.numero_expediente,
        fecha_inicio=tramite.fecha_inicio,
        creado_por_nombre=tramite.creado_por.nombre if tramite.creado_por else None,
        asignado_a=tramite.asignado_a,
        asignado_a_nombre=tramite.asignado_a_usuario.nombre if tramite.asignado_a_usuario else None,
        fecha_vencimiento=tramite.fecha_vencimiento,
        estado=tramite.estado,
        checklist=tramite.checklist or [],
    )


@app.get("/empresas/{empresa_id}/auditoria", response_model=List[schemas.AuditoriaOut])
def historial_empresa(
    empresa_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_user),
):
    verificar_acceso_empresa(db, current_user, empresa_id)
    entradas = (
        db.query(models.AuditoriaTramite)
        .options(joinedload(models.AuditoriaTramite.usuario))
        .filter(models.AuditoriaTramite.empresa_id == empresa_id)
        .order_by(models.AuditoriaTramite.creado_en.desc())
        .limit(200)
        .all()
    )
    return [
        schemas.AuditoriaOut(
            campo=e.campo,
            valor_anterior=e.valor_anterior,
            valor_nuevo=e.valor_nuevo,
            usuario_nombre=e.usuario.nombre if e.usuario else None,
            creado_en=e.creado_en,
            tramite_nombre=e.tramite_nombre,
        )
        for e in entradas
    ]


@app.get("/tramites/{tramite_id}/auditoria", response_model=List[schemas.AuditoriaOut])
def historial_tramite(
    tramite_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_user),
):
    tramite = db.query(models.Tramite).filter(models.Tramite.id == tramite_id).first()
    if not tramite:
        raise HTTPException(status_code=404, detail="Trámite no encontrado")
    verificar_acceso_empresa(db, current_user, tramite.empresa_cliente_id)

    entradas = (
        db.query(models.AuditoriaTramite)
        .options(joinedload(models.AuditoriaTramite.usuario))
        .filter(models.AuditoriaTramite.tramite_id == tramite_id)
        .order_by(models.AuditoriaTramite.creado_en.desc())
        .all()
    )
    return [
        schemas.AuditoriaOut(
            campo=e.campo,
            valor_anterior=e.valor_anterior,
            valor_nuevo=e.valor_nuevo,
            usuario_nombre=e.usuario.nombre if e.usuario else None,
            creado_en=e.creado_en,
        )
        for e in entradas
    ]


@app.delete("/tramites/{tramite_id}", status_code=204)
def borrar_tramite(
    tramite_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.require_admin),
):
    tramite = (
        db.query(models.Tramite)
        .options(joinedload(models.Tramite.tipo_tramite), joinedload(models.Tramite.empresa_cliente))
        .filter(models.Tramite.id == tramite_id)
        .first()
    )
    if not tramite:
        raise HTTPException(status_code=404, detail="Trámite no encontrado")

    db.add(models.AuditoriaTramite(
        tramite_id=tramite.id,
        empresa_id=tramite.empresa_cliente_id,
        empresa_nombre=tramite.empresa_cliente.nombre,
        tramite_nombre=tramite.tipo_tramite.nombre,
        usuario_id=current_user.id,
        campo="eliminado",
        valor_anterior="activo",
        valor_nuevo="trámite eliminado",
    ))
    db.delete(tramite)
    db.commit()
    return None
