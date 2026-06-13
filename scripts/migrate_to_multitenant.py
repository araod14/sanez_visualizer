"""Migración one-shot del esquema single-tenant al esquema multi-tenant.

Antes:
  - tablas `settings`, `backgrounds`, `categories` (PK `clave`), `product_items` (FK `categoria_clave`)
  - un único admin definido por ADMIN_USER / ADMIN_PASSWORD en env

Después:
  - tablas `users`, `categories` (PK `id`, FK `user_id`), `product_items` (FK `category_id`)
  - un super-admin + un usuario "legacy" que hereda todos los datos previos

Uso:
  Asegurate de tener `sanez.db` legacy en el cwd (o monta el volumen en Docker)
  y ejecuta:

      python scripts/migrate_to_multitenant.py

  Variables de entorno opcionales:
      LEGACY_SLUG          → slug del usuario legacy (default: "demo")
      LEGACY_EMAIL         → email del usuario legacy (default: "legacy@local")
      LEGACY_PASSWORD      → contraseña del usuario legacy (default: ADMIN_PASSWORD o "changeme")
      LEGACY_NEGOCIO       → nombre comercial (default: "Negocio (legacy)")
      SUPER_ADMIN_EMAIL    → email del super-admin (default: ADMIN_USER o "admin")
      SUPER_ADMIN_PASSWORD → contraseña del super-admin (default: ADMIN_PASSWORD o "admin")

El script es idempotente: si detecta que ya hay un usuario "legacy" o que las
tablas viejas no existen, no hace nada destructivo.
"""

import os
import shutil
import sys
from pathlib import Path

# Permite ejecutar el script como `python scripts/migrate_to_multitenant.py`
# desde la raíz del proyecto sin que falle el import de `database`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text

from app.bootstrap import init_db
from app.config import get_settings
from app.db import SessionLocal, create_all, engine
from app.models import Base, Category, ProductItem, User
from app.security.passwords import hash_password


def _detect_legacy(inspector) -> bool:
    tablas = set(inspector.get_table_names())
    if "categories" not in tablas:
        return False
    cols = {c["name"] for c in inspector.get_columns("categories")}
    return "clave" in cols and "user_id" not in cols


def main():
    inspector = inspect(engine)

    # ── 1. Si ya hay esquema nuevo y nada legacy, crear tablas + seed y salir
    if not _detect_legacy(inspector):
        create_all()
        init_db(get_settings())
        print("No se detectó esquema legacy. Nada que migrar.")
        return

    # ── 2. Leer toda la data vieja en memoria con SQL crudo ANTES de tocar el esquema
    print("Esquema legacy detectado. Leyendo datos viejos…")
    with engine.connect() as conn:
        settings_row = conn.execute(
            text("SELECT tiempo_rotacion_segundos FROM settings WHERE id = 1")
        ).first()
        tiempo_rotacion = int(settings_row[0]) if (settings_row and settings_row[0]) else 10

        backgrounds_rows = conn.execute(text("SELECT id, ruta_archivo FROM backgrounds")).fetchall()
        bg_por_id = {row[0]: row[1] for row in backgrounds_rows}

        cats_viejas = conn.execute(
            text("SELECT clave, nombre, orden FROM categories ORDER BY orden")
        ).fetchall()

        items_viejos = conn.execute(
            text("SELECT categoria_clave, nombre, precio, orden FROM product_items")
        ).fetchall()

    print(f"  · settings.tiempo_rotacion = {tiempo_rotacion}")
    print(
        f"  · {len(bg_por_id)} backgrounds, {len(cats_viejas)} categorías, {len(items_viejos)} productos"
    )

    # ── 3. Borrar las tablas viejas que entran en conflicto y crear el esquema nuevo
    print("Borrando tablas legacy y creando esquema nuevo…")
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS product_items"))
        conn.execute(text("DROP TABLE IF EXISTS categories"))
        conn.execute(text("DROP TABLE IF EXISTS backgrounds"))
        conn.execute(text("DROP TABLE IF EXISTS settings"))

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # ── 4. Bootstrap super-admin (idempotente)
        if not db.query(User).filter(User.is_super_admin.is_(True)).first():
            email = os.environ.get("SUPER_ADMIN_EMAIL") or os.environ.get("ADMIN_USER", "admin")
            password = os.environ.get("SUPER_ADMIN_PASSWORD") or os.environ.get(
                "ADMIN_PASSWORD", "admin"
            )
            db.add(
                User(
                    email=email,
                    slug="super",
                    nombre_negocio="Super Admin",
                    password_hash=hash_password(password),
                    is_active=True,
                    is_super_admin=True,
                )
            )
            db.commit()
            print(f"Super-admin creado: email={email}")

        # ── 5. Crear usuario legacy
        legacy_slug = os.environ.get("LEGACY_SLUG", "demo").lower()
        legacy_email = os.environ.get("LEGACY_EMAIL", "legacy@local").lower()
        legacy_pwd = (
            os.environ.get("LEGACY_PASSWORD") or os.environ.get("ADMIN_PASSWORD") or "changeme"
        )
        legacy_nombre = os.environ.get("LEGACY_NEGOCIO", "Negocio (legacy)")

        if db.query(User).filter(User.slug == legacy_slug).first():
            print(f"Usuario legacy '{legacy_slug}' ya existe — nada que reimportar.")
            return

        legacy_user = User(
            email=legacy_email,
            slug=legacy_slug,
            nombre_negocio=legacy_nombre,
            password_hash=hash_password(legacy_pwd),
            is_active=True,
            is_super_admin=False,
            tiempo_rotacion_segundos=tiempo_rotacion,
        )
        db.add(legacy_user)
        db.flush()
        print(f"Usuario legacy creado: id={legacy_user.id}, slug={legacy_slug}")

        # ── 6. Migrar categorías y backgrounds
        orden_categorias = ["ron", "whisky", "cerveza", "sangria"]  # mapeo posicional viejo
        user_upload_dir = Path("static/uploads") / str(legacy_user.id)
        user_upload_dir.mkdir(parents=True, exist_ok=True)

        clave_a_id_nuevo = {}
        for clave, nombre, orden in cats_viejas:
            nueva_cat = Category(
                user_id=legacy_user.id,
                nombre=nombre,
                orden=(orden - 1) if (orden and orden > 0) else 0,
            )
            db.add(nueva_cat)
            db.flush()
            clave_a_id_nuevo[clave] = nueva_cat.id

            try:
                idx = orden_categorias.index(clave)
            except ValueError:
                idx = -1
            slot_id = idx + 1
            ruta_vieja = bg_por_id.get(slot_id)
            if ruta_vieja:
                src = Path(ruta_vieja.lstrip("/"))
                if src.exists():
                    ext = src.suffix.lower() or ".png"
                    dst = user_upload_dir / f"cat_{nueva_cat.id}{ext}"
                    try:
                        shutil.copy2(src, dst)
                        nueva_cat.background_path = f"static/uploads/{legacy_user.id}/{dst.name}"
                        print(f"  background «{nombre}»: {src} → {dst}")
                    except OSError as e:
                        print(f"  ⚠ no pude copiar background de «{nombre}»: {e}")

            print(f"  categoría migrada: {clave} → id={nueva_cat.id} ({nombre})")

        # ── 7. Migrar productos
        n_items = 0
        for cat_clave, nombre, precio, orden in items_viejos:
            cat_id = clave_a_id_nuevo.get(cat_clave)
            if not cat_id:
                continue
            # precio venía como float; lo guardamos como string sin decimales si es entero
            if precio is None:
                precio_str = "0"
            elif float(precio) == int(precio):
                precio_str = str(int(precio))
            else:
                precio_str = str(precio)
            db.add(
                ProductItem(
                    category_id=cat_id,
                    nombre=nombre,
                    precio=precio_str,
                    orden=orden or 0,
                )
            )
            n_items += 1

        db.commit()
        print(f"\n✓ Migración completada: {len(cats_viejas)} categorías, {n_items} productos.")
        print("\nLogin del usuario legacy:")
        print(f"  email:    {legacy_email}")
        print(f"  password: {legacy_pwd}")
        print(f"  menú:     /menu/{legacy_slug}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
