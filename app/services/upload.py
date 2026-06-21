"""Manejo de archivos de imagen para los backgrounds de categorías.

Los routers leen los bytes del `UploadFile` (concern HTTP/async) y pasan
`filename` + `content` aquí; el service valida y escribe en disco.
"""

import contextlib
import shutil
from pathlib import Path

from app.config import get_settings
from app.services import ServiceError


def user_upload_dir(user_id: int) -> Path:
    d = get_settings().upload_dir / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def delete_file_if_exists(ruta_relativa: str | None) -> None:
    if not ruta_relativa:
        return
    p = Path(ruta_relativa)
    if p.exists() and p.is_file():
        with contextlib.suppress(OSError):
            p.unlink()


def delete_user_dir(user_id: int) -> None:
    user_dir = get_settings().upload_dir / str(user_id)
    if user_dir.exists():
        shutil.rmtree(user_dir, ignore_errors=True)


def save_category_image(
    user_id: int,
    category_id: int,
    filename: str,
    content: bytes,
    previous_path: str | None,
) -> str:
    """Valida y persiste la imagen; devuelve el `background_path` relativo a guardar."""
    s = get_settings()
    ext = Path(filename or "").suffix.lower()
    if ext not in s.allowed_extensions:
        raise ServiceError("Formato no permitido (jpg/png/webp)")
    if len(content) > s.upload_max_bytes:
        raise ServiceError("Imagen demasiado grande (máx 5MB)")

    delete_file_if_exists(previous_path)

    dest_dir = user_upload_dir(user_id)
    nombre_archivo = f"cat_{category_id}{ext}"
    (dest_dir / nombre_archivo).write_bytes(content)
    return f"{s.upload_dir.as_posix()}/{user_id}/{nombre_archivo}"


def category_preview_path(user_id: int, category_id: int) -> str:
    s = get_settings()
    return f"{s.upload_dir.as_posix()}/{user_id}/cat_{category_id}__preview.png"


def save_category_preview(user_id: int, category_id: int, content: bytes) -> str:
    """Guarda el PNG de previsualización (fondo generado por IA, aún sin confirmar).

    Devuelve el path relativo. Valida tamaño con `upload_max_bytes`.
    """
    s = get_settings()
    if len(content) > s.upload_max_bytes:
        raise ServiceError("Imagen demasiado grande (máx 5MB)")
    rel = category_preview_path(user_id, category_id)
    user_upload_dir(user_id)  # asegura que el directorio exista
    Path(rel).write_bytes(content)
    return rel


def read_category_preview(user_id: int, category_id: int) -> bytes | None:
    """Lee los bytes del preview si existe, si no None."""
    p = Path(category_preview_path(user_id, category_id))
    return p.read_bytes() if p.is_file() else None


def delete_category_preview(user_id: int, category_id: int) -> None:
    delete_file_if_exists(category_preview_path(user_id, category_id))
