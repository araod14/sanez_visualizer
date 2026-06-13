"""Hashing de contraseñas con bcrypt (truncado a 72 bytes)."""

import bcrypt


def _coerce_password(plain: str) -> bytes:
    # bcrypt impone un máximo de 72 bytes — truncamos en el borde para evitar ValueError.
    return (plain or "").encode("utf-8")[:72]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_coerce_password(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(_coerce_password(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False
