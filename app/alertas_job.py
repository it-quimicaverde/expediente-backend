from datetime import date, timedelta

from sqlalchemy.orm import Session, joinedload

from . import models
from .database import SessionLocal
from .emailing import enviar_correo

DIAS_ALERTA = [60, 30, 15]
DIAS_ALERTA_REPARO = [89, 60, 30, 10]
CATEGORIAS_CON_REPARO = {"alimentos", "farma", "otros"}


def destinatarios_para_empresa(db: Session, empresa_id) -> list:
    """Correos de los gestores asignados a la empresa; si no hay ninguno, los admins."""
    gestores = (
        db.query(models.Usuario.email)
        .join(models.UsuarioEmpresaCliente, models.UsuarioEmpresaCliente.usuario_id == models.Usuario.id)
        .filter(models.UsuarioEmpresaCliente.empresa_cliente_id == empresa_id)
        .filter(models.Usuario.activo.is_(True))
        .all()
    )
    correos = [g[0] for g in gestores]
    if correos:
        return correos

    admins = db.query(models.Usuario.email).filter(models.Usuario.rol == "admin").filter(models.Usuario.activo.is_(True)).all()
    return [a[0] for a in admins]


def ya_fue_enviada(db: Session, tramite_id, dias_previos: int, reparo_id=None) -> bool:
    query = (
        db.query(models.Alerta)
        .filter(models.Alerta.tramite_id == tramite_id)
        .filter(models.Alerta.dias_previos == dias_previos)
        .filter(models.Alerta.enviada.is_(True))
    )
    if reparo_id:
        query = query.filter(models.Alerta.reparo_id == reparo_id)
    else:
        query = query.filter(models.Alerta.reparo_id.is_(None))
    return query.first() is not None


def registrar_envio(db: Session, tramite_id, dias_previos: int, fecha_programada: date, ok: bool, reparo_id=None):
    alerta = models.Alerta(
        tramite_id=tramite_id,
        reparo_id=reparo_id,
        dias_previos=dias_previos,
        fecha_programada=fecha_programada,
        enviada=ok,
        enviada_en=None,
        canal="email",
    )
    if ok:
        from datetime import datetime

        alerta.enviada_en = datetime.utcnow()
    db.add(alerta)
    db.commit()


def construir_html(empresa_nombre, tramite_nombre, categoria, numero_expediente, fecha_vencimiento, dias):
    return f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color:#182821;">Vencimiento en {dias} días</h2>
      <p><strong>Empresa:</strong> {empresa_nombre}</p>
      <p><strong>Trámite:</strong> {tramite_nombre} ({categoria})</p>
      <p><strong>N° expediente:</strong> {numero_expediente or "—"}</p>
      <p><strong>Fecha de vencimiento:</strong> {fecha_vencimiento}</p>
      <p style="color:#4b5a50; font-size: 13px; margin-top: 24px;">
        Enviado automáticamente por Expediente.
      </p>
    </div>
    """


def construir_html_reparo(empresa_nombre, tramite_nombre, categoria, numero_expediente, numero_reparo, motivo, fecha_vencimiento, dias):
    return f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color:#a23328;">Reparo N° {numero_reparo} — vence en {dias} días</h2>
      <p><strong>Empresa:</strong> {empresa_nombre}</p>
      <p><strong>Trámite:</strong> {tramite_nombre} ({categoria})</p>
      <p><strong>N° expediente:</strong> {numero_expediente or "—"}</p>
      <p><strong>Motivo del rechazo:</strong> {motivo or "—"}</p>
      <p><strong>Fecha límite para responder:</strong> {fecha_vencimiento}</p>
      <p style="color:#4b5a50; font-size: 13px; margin-top: 24px;">
        Enviado automáticamente por Expediente.
      </p>
    </div>
    """


def ejecutar_revision_alertas() -> dict:
    db = SessionLocal()
    enviadas = 0
    revisadas = 0
    try:
        # --- Vencimientos normales del trámite (licencias, registros) ---
        for dias in DIAS_ALERTA:
            fecha_objetivo = date.today() + timedelta(days=dias)
            tramites = (
                db.query(models.Tramite)
                .options(joinedload(models.Tramite.empresa_cliente), joinedload(models.Tramite.tipo_tramite))
                .filter(models.Tramite.fecha_vencimiento == fecha_objetivo)
                .all()
            )
            for t in tramites:
                revisadas += 1
                if ya_fue_enviada(db, t.id, dias):
                    continue

                destinatarios = destinatarios_para_empresa(db, t.empresa_cliente_id)
                html = construir_html(
                    t.empresa_cliente.nombre,
                    t.tipo_tramite.nombre,
                    t.tipo_tramite.categoria,
                    t.numero_expediente,
                    t.fecha_vencimiento,
                    dias,
                )
                ok = enviar_correo(
                    destinatarios,
                    f"Vence en {dias} días: {t.tipo_tramite.nombre} — {t.empresa_cliente.nombre}",
                    html,
                )
                registrar_envio(db, t.id, dias, fecha_objetivo, ok)
                if ok:
                    enviadas += 1

        # --- Plazos de respuesta a reparos (Alimentos, Farma, Otros) ---
        for dias in DIAS_ALERTA_REPARO:
            fecha_objetivo = date.today() + timedelta(days=dias)
            reparos = (
                db.query(models.Reparo)
                .join(models.Tramite, models.Reparo.tramite_id == models.Tramite.id)
                .join(models.TipoTramite, models.Tramite.tipo_tramite_id == models.TipoTramite.id)
                .options(
                    joinedload(models.Reparo.tramite).joinedload(models.Tramite.empresa_cliente),
                    joinedload(models.Reparo.tramite).joinedload(models.Tramite.tipo_tramite),
                )
                .filter(models.Reparo.fecha_vencimiento == fecha_objetivo)
                .filter(models.TipoTramite.categoria.in_(CATEGORIAS_CON_REPARO))
                .all()
            )
            for r in reparos:
                revisadas += 1
                if ya_fue_enviada(db, r.tramite_id, dias, reparo_id=r.id):
                    continue

                t = r.tramite
                destinatarios = destinatarios_para_empresa(db, t.empresa_cliente_id)
                html = construir_html_reparo(
                    t.empresa_cliente.nombre,
                    t.tipo_tramite.nombre,
                    t.tipo_tramite.categoria,
                    t.numero_expediente,
                    r.numero,
                    r.motivo_rechazo,
                    r.fecha_vencimiento,
                    dias,
                )
                ok = enviar_correo(
                    destinatarios,
                    f"Reparo N° {r.numero} vence en {dias} días: {t.tipo_tramite.nombre} — {t.empresa_cliente.nombre}",
                    html,
                )
                registrar_envio(db, t.id, dias, fecha_objetivo, ok, reparo_id=r.id)
                if ok:
                    enviadas += 1
    finally:
        db.close()

    return {"revisadas": revisadas, "enviadas": enviadas}


if __name__ == "__main__":
    resultado = ejecutar_revision_alertas()
    print("Revisión de alertas completada:", resultado)
