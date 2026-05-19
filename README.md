# Sanez Visualizer

Cartelera digital para mostrar precios de licores en un Smart TV.

## Instalación

```bash
# Activar el entorno virtual (si existe)
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Ejecutar

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

La aplicación queda disponible en:
- **Pantalla TV:** `http://<IP-del-servidor>:8000/`
- **Panel admin:** `http://<IP-del-servidor>:8000/admin`

## Acceso al panel de administración

- **URL:** `http://localhost:8000/admin`
- **Usuario por defecto:** `admin`
- **Contraseña por defecto:** `admin`

> **Importante:** cambia las credenciales en producción usando variables de entorno:

```bash
export ADMIN_USER=mi_usuario
export ADMIN_PASSWORD=mi_contraseña_segura
export SECRET_KEY=clave_secreta_larga_aleatoria
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Configurar el Smart TV

1. Conecta el TV a la misma red local que el servidor.
2. Abre el navegador del TV y navega a `http://<IP-del-servidor>:8000/`.
3. Usa el modo pantalla completa (F11 o botón del navegador).
4. La pantalla actualiza los precios automáticamente cada 30 segundos.

## Funcionalidades del admin

| Sección | Descripción |
|---------|-------------|
| Tiempo de rotación | Segundos que se muestra cada imagen de fondo (3–300 s) |
| Imágenes de fondo | 4 ranuras; sube JPG, PNG o WebP (máx. 5 MB) |
| Precios | Edita nombre y precio de Ron, Whisky, Cerveza y Sangría |
