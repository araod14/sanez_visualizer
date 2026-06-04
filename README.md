# Sanez Visualizer

Cartelera digital **multi-tenant** para mostrar precios en un Smart TV.
Un super-admin crea cuentas; cada cliente gestiona sus categorías, productos
e imágenes y comparte su menú público en `/menu/<slug>`.

---

## Estructura del proyecto

```
sanez_visualizer/
├── main.py                 # Aplicación FastAPI (auth, rutas, lógica)
├── database.py             # Modelos SQLAlchemy + init_db (bootstrap super-admin)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── scripts/
│   └── migrate_to_multitenant.py   # Migración one-shot desde el esquema viejo
├── templates/
│   ├── login.html          # Login (para todos los usuarios)
│   ├── public.html         # Pantalla TV (consume /api/data/<slug>)
│   ├── admin/
│   │   └── dashboard.html  # Panel del usuario
│   └── super/
│       ├── users_list.html # Listado de usuarios (super-admin)
│       └── user_form.html  # Alta/edición de usuario
└── static/uploads/         # Imágenes subidas (subcarpeta por user_id)
```

---

## Modelo multi-tenant

- **Super-admin**: cuenta única (creada al primer arranque desde
  `SUPER_ADMIN_EMAIL` / `SUPER_ADMIN_PASSWORD`). Da de alta usuarios desde `/super`.
- **Usuario** (cliente): inicia sesión en `/login`, gestiona sus categorías
  (totalmente personalizables), sus productos y un background por categoría.
- **Público**: cualquiera abre `https://tu-dominio/menu/<slug>` para ver la
  cartelera de un cliente concreto.

El super-admin puede *impersonar* a cualquier usuario para depurar.

---

## Deploy con Docker

### 1. Variables de entorno (`.env`)

```env
SUPER_ADMIN_EMAIL=admin@tudominio.com
SUPER_ADMIN_PASSWORD=cambia-esto-ya
SECRET_KEY=pegar_aqui_64_chars_hex
```

Generar `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

> Si vienes de la versión vieja, las variables `ADMIN_USER` / `ADMIN_PASSWORD`
> también funcionan como fallback para crear el super-admin.

### 2. Levantar

```bash
make build
make up
```

App disponible en `http://<IP>:8001` (mapeado desde el 8000 interno).

- `/` → redirige a `/login` (o al panel si ya iniciaste sesión).
- `/login` → acceso para super-admin y usuarios.
- `/super` → panel del super-admin (CRUD de usuarios + impersonate).
- `/admin` → panel de cualquier usuario autenticado.
- `/menu/<slug>` → cartelera pública del usuario `<slug>`.

### 3. Migrar datos viejos (single-tenant → multi-tenant)

Si tenías la versión anterior con `sanez.db`, antes del primer `make up` con el
nuevo código:

```bash
make up                 # arranca el contenedor (crea tablas nuevas vacías)
make migrate            # crea un usuario "legacy" con todos los datos previos
```

Variables opcionales (puedes ponerlas en el `.env` antes del migrate):

| Var | Default | Para qué |
|---|---|---|
| `LEGACY_SLUG` | `demo` | Slug del usuario legacy (su URL será `/menu/demo`) |
| `LEGACY_EMAIL` | `legacy@local` | Email para iniciar sesión |
| `LEGACY_PASSWORD` | el `ADMIN_PASSWORD` viejo o `changeme` | Contraseña inicial |
| `LEGACY_NEGOCIO` | `Negocio (legacy)` | Nombre comercial mostrado |

El script es **idempotente**: si ya existe el usuario legacy o no detecta
esquema viejo, no toca nada.

### 4. Comandos del Makefile

| Comando | Descripción |
|---|---|
| `make build` | Reconstruir la imagen Docker |
| `make up` | Levantar en background |
| `make down` | Bajar el servicio |
| `make restart` | Bajar + subir |
| `make logs` | Tail de logs |
| `make migrate` | Migración one-shot single-tenant → multi-tenant |

### Persistencia

| Volumen local | Contenido |
|---|---|
| `./sanez.db` | SQLite con usuarios, categorías y productos |
| `./static/uploads/<user_id>/` | Imágenes de cada usuario (segregadas) |

---

## Desarrollo local (sin Docker)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

export SUPER_ADMIN_EMAIL=admin@local
export SUPER_ADMIN_PASSWORD=admin
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Configurar el Smart TV

1. Conectar el TV a la misma red.
2. Obtener la URL pública del cliente: `http://<IP>:8001/menu/<slug>`.
3. Abrir el navegador del TV en esa URL y poner pantalla completa.
4. La cartelera se actualiza automáticamente cada 30 s.

---

## Actualizar el código en producción

```bash
git pull
make build
make restart
```
