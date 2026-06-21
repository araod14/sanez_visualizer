"""Configuración tipada de la aplicación (pydantic-settings).

Centraliza la lectura de variables de entorno que antes vivía dispersa en
`main.py`. Un único objeto `Settings` validado, cacheado vía `get_settings()`.
"""

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Modo / sesión ---
    dev_mode: bool = Field(False, alias="DEV_MODE")
    secret_key: str = Field("", alias="SECRET_KEY")
    # Sentinel None → se resuelve a `not dev_mode` en el validador.
    session_https_only: bool | None = Field(None, alias="SESSION_HTTPS_ONLY")
    session_same_site: str = Field("lax", alias="SESSION_SAME_SITE")

    # --- Rate limit de login (ventana en memoria por IP) ---
    login_max_attempts: int = Field(5, alias="LOGIN_MAX_ATTEMPTS")
    login_window_seconds: int = Field(300, alias="LOGIN_WINDOW_SECONDS")

    # --- Bootstrap del super-admin (con fallback a los nombres viejos ADMIN_*) ---
    super_admin_email: str = Field("", alias="SUPER_ADMIN_EMAIL")
    super_admin_password: str = Field("", alias="SUPER_ADMIN_PASSWORD")
    admin_user: str = Field("admin", alias="ADMIN_USER")
    admin_password: str = Field("admin", alias="ADMIN_PASSWORD")

    # --- Base de datos ---
    database_url: str = Field("sqlite:///./sanez.db", alias="DATABASE_URL")

    # --- Scheduler BCV ---
    scheduler_enabled: bool = Field(True, alias="SCHEDULER_ENABLED")
    scheduler_hour: int = Field(14, alias="SCHEDULER_HOUR")
    scheduler_minute: int = Field(0, alias="SCHEDULER_MINUTE")
    scheduler_tz: str = Field("America/Caracas", alias="SCHEDULER_TZ")

    # --- Uploads ---
    upload_dir: Path = Field(Path("static/uploads"), alias="UPLOAD_DIR")
    upload_max_bytes: int = Field(5 * 1024 * 1024, alias="UPLOAD_MAX_BYTES")
    allowed_extensions: set[str] = {".jpg", ".jpeg", ".png", ".webp"}

    # --- Generación de fondos por IA (texto → imagen) ---
    image_provider: str = Field("gemini", alias="IMAGE_PROVIDER")
    image_api_key: str = Field("", alias="IMAGE_API_KEY")
    image_model: str = Field("gemini-2.5-flash-image", alias="IMAGE_MODEL")
    image_aspect_ratio: str = Field("16:9", alias="IMAGE_ASPECT_RATIO")

    @property
    def effective_super_admin_email(self) -> str:
        return self.super_admin_email or self.admin_user

    @property
    def effective_super_admin_password(self) -> str:
        return self.super_admin_password or self.admin_password

    @model_validator(mode="after")
    def _finalize(self) -> "Settings":
        if not self.secret_key:
            if self.dev_mode:
                # Clave efímera: las sesiones no persisten entre reinicios.
                self.secret_key = secrets.token_hex(32)
            else:
                raise ValueError(
                    "SECRET_KEY no configurada. Define SECRET_KEY en el entorno "
                    "(o DEV_MODE=1 para desarrollo local con clave efímera)."
                )
        if self.session_https_only is None:
            self.session_https_only = not self.dev_mode
        self.session_same_site = self.session_same_site.strip().lower()
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
