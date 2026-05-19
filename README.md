# Sanez Visualizer

Cartelera digital para mostrar precios de licores en un Smart TV.  
Panel de administración para gestionar imágenes, categorías y precios.

---

## Estructura del proyecto

```
sanez_visualizer/
├── main.py              # Aplicación FastAPI (rutas, auth, lógica)
├── database.py          # Modelos SQLAlchemy e inicialización de DB
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── templates/
│   ├── public.html      # Pantalla TV (pantalla completa)
│   ├── admin.html       # Panel de administración
│   └── login.html       # Formulario de login
└── static/uploads/      # Imágenes subidas (se crea automáticamente)
```

---

## Deploy con Docker (recomendado)

### 1. Requisitos

- [Docker](https://docs.docker.com/get-docker/) instalado
- [Docker Compose](https://docs.docker.com/compose/) (incluido en Docker Desktop)

### 2. Clonar el repositorio

```bash
git clone <url-del-repo>
cd sanez_visualizer
```

### 3. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto:

```bash
cp .env.example .env   # si existe, o créalo manualmente
```

Contenido del `.env`:

```env
ADMIN_USER=mi_usuario
ADMIN_PASSWORD=mi_password_seguro
SECRET_KEY=pegar_aqui_la_clave_generada
```

Para generar una `SECRET_KEY` segura:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

> El archivo `.env` está en `.gitignore` y nunca se sube al repositorio.

### 4. Construir y levantar

```bash
make build   # construye la imagen Docker
make up      # levanta el contenedor en background
```

La aplicación queda disponible en:

- **Pantalla TV:** `http://<IP-del-servidor>:8000/`
- **Panel admin:** `http://<IP-del-servidor>:8000/admin`

### 5. Comandos útiles

| Comando | Descripción |
|---------|-------------|
| `make up` | Levantar en background |
| `make down` | Detener y eliminar contenedores |
| `make restart` | Reiniciar el servicio |
| `make logs` | Ver logs en tiempo real |
| `make ps` | Estado de los contenedores |
| `make build` | Reconstruir la imagen (tras cambios en el código) |

### Persistencia de datos

Docker monta dos volúmenes locales para que los datos sobrevivan reinicios y actualizaciones:

| Volumen local | Contenido |
|---------------|-----------|
| `./sanez.db` | Base de datos SQLite (categorías, precios, configuración) |
| `./static/uploads/` | Imágenes de fondo subidas desde el admin |

---

## Desarrollo local (sin Docker)

### 1. Crear entorno virtual e instalar dependencias

```bash
python3 -m venv venv
source venv/bin/activate      # Linux/Mac
# venv\Scripts\activate       # Windows

make install                  # equivale a: pip install -r requirements.txt
```

### 2. Arrancar con recarga automática

```bash
make dev
# equivale a: venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Acceso al panel de administración

- **URL:** `http://localhost:8000/admin`
- **Usuario por defecto:** `admin`
- **Contraseña por defecto:** `admin`

> Cambia siempre las credenciales antes de exponer la aplicación en una red.

---

## Configurar el Smart TV

1. Conecta el TV a la misma red que el servidor.
2. Obtén la IP del servidor: `ip a` o `hostname -I`.
3. Abre el navegador del TV y navega a `http://<IP>:8000/`.
4. Activa pantalla completa (F11 o botón del navegador).
5. Los precios se actualizan automáticamente cada 30 segundos.

---

## Funcionalidades del admin

| Sección | Descripción |
|---------|-------------|
| Tiempo de rotación | Segundos que se muestra cada imagen (3–300 s) |
| Imágenes de fondo | 4 ranuras (JPG, PNG o WebP, máx. 5 MB) |
| Precios | Agregar, editar y eliminar productos por categoría |

### Mapeo ranura → categoría

Cada imagen de fondo muestra exclusivamente los productos de su categoría:

| Ranura | Categoría |
|--------|-----------|
| 1 | Ron |
| 2 | Whisky |
| 3 | Cerveza |
| 4 | Sangría |

---

## Actualizar el código en producción

```bash
git pull
make build
make restart
```
