import os
import uuid

import boto3
from botocore.client import Config

B2_KEY_ID = os.getenv("B2_KEY_ID", "")
B2_APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY", "")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME", "")
B2_ENDPOINT_URL = os.getenv("B2_ENDPOINT_URL", "")  # ej. https://s3.us-west-004.backblazeb2.com

EXTENSIONES_PERMITIDAS = {".pdf", ".jpg", ".jpeg", ".png"}
TAMANO_MAXIMO_BYTES = 15 * 1024 * 1024  # 15 MB


def _cliente():
    if not (B2_KEY_ID and B2_APPLICATION_KEY and B2_ENDPOINT_URL):
        raise RuntimeError("Almacenamiento de documentos no configurado (faltan variables B2_*)")
    return boto3.client(
        "s3",
        endpoint_url=B2_ENDPOINT_URL,
        aws_access_key_id=B2_KEY_ID,
        aws_secret_access_key=B2_APPLICATION_KEY,
        config=Config(signature_version="s3v4"),
    )


def validar_archivo(nombre_archivo: str, tamano_bytes: int) -> str | None:
    ext = os.path.splitext(nombre_archivo)[1].lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        return f"Tipo de archivo no permitido ({ext}). Solo PDF, JPG o PNG."
    if tamano_bytes > TAMANO_MAXIMO_BYTES:
        return "El archivo pesa más de 15 MB."
    return None


def subir_archivo(contenido: bytes, nombre_original: str, content_type: str) -> str:
    """Sube el archivo y devuelve la clave (key) con la que quedó guardado."""
    ext = os.path.splitext(nombre_original)[1].lower()
    clave = f"documentos/{uuid.uuid4()}{ext}"
    cliente = _cliente()
    cliente.put_object(
        Bucket=B2_BUCKET_NAME,
        Key=clave,
        Body=contenido,
        ContentType=content_type or "application/octet-stream",
    )
    return clave


def generar_url_descarga(clave: str, expira_segundos: int = 3600) -> str:
    """URL temporal (1 hora por defecto) para descargar el archivo, sin hacerlo público."""
    cliente = _cliente()
    return cliente.generate_presigned_url(
        "get_object",
        Params={"Bucket": B2_BUCKET_NAME, "Key": clave},
        ExpiresIn=expira_segundos,
    )


def borrar_archivo(clave: str):
    cliente = _cliente()
    cliente.delete_object(Bucket=B2_BUCKET_NAME, Key=clave)
