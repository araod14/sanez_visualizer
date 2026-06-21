"""Generación de imágenes de fondo por IA (texto → imagen).

El usuario escribe una palabra o frase y un proveedor de IA genera una imagen
apta como fondo de cartelera (landscape, de buen gusto, sin texto). El proveedor
es intercambiable vía `IMAGE_PROVIDER`; arranca con Google Gemini.

Sigue el patrón del scraper BCV (`scrapers/bcv.py`): `requests` síncrono y errores
traducidos a `ServiceError` para que el router los muestre con `back_to`.
"""

import base64
import binascii
import logging

import requests

from app.config import get_settings
from app.services import ServiceError

log = logging.getLogger(__name__)

# Prefijo de "buen gusto" que envuelve la frase del usuario. Pensado para fondos
# de cartelera: landscape, elegante, sin texto y que no compita con el menú.
BASE_PROMPT = (
    "Imagen de fondo para una cartelera de menú digital. "
    "Composición landscape amplia (panorámica 16:9), elegante y de buen gusto, "
    "alta calidad, atmósfera agradable. Sin texto, sin letras, sin números, "
    "sin logos ni marcas de agua. Tonos suaves y algo oscuros en el centro para "
    "que el texto del menú se lea con claridad encima. "
    "Tema: «{frase}»."
)

_MAX_FRASE_LEN = 200
_TIMEOUT_SECONDS = 60


def build_prompt(frase: str) -> str:
    """Combina `BASE_PROMPT` con la frase saneada del usuario."""
    frase = (frase or "").strip()
    if not frase:
        raise ServiceError("Escribe una palabra o frase para generar la imagen")
    if len(frase) > _MAX_FRASE_LEN:
        frase = frase[:_MAX_FRASE_LEN]
    return BASE_PROMPT.format(frase=frase)


def generate_background_image(prompt: str) -> bytes:
    """Genera la imagen y devuelve sus bytes (PNG). Despacha según el proveedor.

    Lanza `ServiceError` si no hay API key, el proveedor no se reconoce o la API
    falla / no devuelve imagen.
    """
    s = get_settings()
    if not s.image_api_key:
        raise ServiceError("Generación por IA no configurada (falta IMAGE_API_KEY en el entorno)")
    provider = (s.image_provider or "").strip().lower()
    if provider == "gemini":
        return _generate_gemini(prompt, s.image_api_key, s.image_model)
    raise ServiceError(f"Proveedor de imágenes no soportado: {provider!r}")


def _generate_gemini(prompt: str, api_key: str, model: str) -> bytes:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("Fallo al llamar a Gemini: %s", e)
        raise ServiceError(f"Error al generar la imagen: {e}") from e

    try:
        data = resp.json()
    except ValueError as e:
        raise ServiceError("Respuesta inválida del generador de imágenes") from e

    b64 = _extract_inline_image(data)
    if not b64:
        raise ServiceError("El generador no devolvió ninguna imagen. Probá con otra frase.")
    try:
        return base64.b64decode(b64)
    except (binascii.Error, ValueError) as e:
        raise ServiceError("No se pudo decodificar la imagen generada") from e


def _extract_inline_image(data: dict) -> str | None:
    """Devuelve el base64 de la primera imagen inline en la respuesta de Gemini.

    Tolera camelCase (`inlineData`) y snake_case (`inline_data`).
    """
    for candidate in data.get("candidates", []) or []:
        parts = (candidate.get("content") or {}).get("parts", []) or []
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return inline["data"]
    return None
