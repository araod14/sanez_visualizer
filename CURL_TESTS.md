# Pruebas de Endpoints con cURL

Guía completa para probar los endpoints de Sanez Visualizer usando `curl`.

## Inicio rápido

```bash
# 1. Iniciar el servidor
source venv/bin/activate
SUPER_ADMIN_EMAIL=admin@local SUPER_ADMIN_PASSWORD=admin \
  uvicorn main:app --host 0.0.0.0 --port 8000

# 2. En otra terminal, ejecutar las pruebas
cd /home/danel/proyects/sanez_visualizer
bash scripts/test_api.sh
```

## Variables de entorno

```bash
export BASE_URL="http://localhost:8000"
export ADMIN_EMAIL="admin"
export ADMIN_PASSWORD="admin"
```

---

## Pruebas por categoría

### 1️⃣ AUTENTICACIÓN

#### Login
```bash
curl -X POST "$BASE_URL/login" \
  -c cookies.txt \
  -d "usuario=$ADMIN_EMAIL&contrasena=$ADMIN_PASSWORD" \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 302 (Redirect a /super o /admin)
```

#### Logout
```bash
curl -X GET "$BASE_URL/logout" \
  -b cookies.txt \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 302 (Redirect a /login)
```

---

### 2️⃣ PANTALLA PÚBLICA

#### Obtener página del menú
```bash
curl -X GET "$BASE_URL/menu/super" \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 200 OK con HTML
```

#### Obtener datos JSON
```bash
curl -X GET "$BASE_URL/api/data/super" \
  -H "Content-Type: application/json" \
  -w "\nStatus: %{http_code}\n" | jq .

# Resultado esperado: 200 OK con JSON
# {
#   "tiempo_rotacion": 10,
#   "backgrounds": [...],
#   "pantallas": [...]
# }
```

---

### 3️⃣ PANEL DE USUARIO

#### Dashboard del usuario
```bash
curl -X GET "$BASE_URL/admin" \
  -b cookies.txt \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 200 OK
```

#### Actualizar tiempo de rotación
```bash
curl -X POST "$BASE_URL/admin/settings" \
  -b cookies.txt \
  -d "tiempo_rotacion=15" \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 302 (Redirect a /admin con ok parameter)
```

---

### 4️⃣ GESTIÓN DE CATEGORÍAS

#### Crear categoría
```bash
curl -X POST "$BASE_URL/admin/categories" \
  -b cookies.txt \
  -d "nombre=Bebidas" \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 302 (Redirect)
# Capturar category_id de la URL o verificar en BD
```

#### Editar categoría
```bash
curl -X POST "$BASE_URL/admin/categories/1/edit" \
  -b cookies.txt \
  -d "nombre=Bebidas Alcohólicas" \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 302
```

#### Mover categoría
```bash
curl -X POST "$BASE_URL/admin/categories/1/move" \
  -b cookies.txt \
  -d "direccion=abajo" \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 302
# direccion puede ser: "arriba" o "abajo"
```

#### Eliminar categoría
```bash
curl -X POST "$BASE_URL/admin/categories/1/delete" \
  -b cookies.txt \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 302
```

#### Subir imagen de fondo (multipart)
```bash
curl -X POST "$BASE_URL/admin/categories/1/background" \
  -b cookies.txt \
  -F "imagen=@/path/to/image.jpg" \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 302
# Formatos soportados: jpg, jpeg, png, webp (máx 5MB)
```

---

### 5️⃣ GESTIÓN DE PRODUCTOS

#### Agregar producto a categoría
```bash
curl -X POST "$BASE_URL/admin/items/add" \
  -b cookies.txt \
  -d "category_id=1&nombre=Cerveza%20IPA&precio=%248.50" \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 302
# Nota: precio se almacena como string
```

#### Editar producto
```bash
curl -X POST "$BASE_URL/admin/items/1/edit" \
  -b cookies.txt \
  -d "nombre=Cerveza%20Artesanal%20IPA&precio=%249.00" \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 302
```

#### Eliminar producto
```bash
curl -X POST "$BASE_URL/admin/items/1/delete" \
  -b cookies.txt \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 302
```

---

### 6️⃣ PANEL SUPER-ADMIN

#### Ver lista de usuarios
```bash
curl -X GET "$BASE_URL/super" \
  -b cookies.txt \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 200 OK
```

#### Formulario crear usuario
```bash
curl -X GET "$BASE_URL/super/users/new" \
  -b cookies.txt \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 200 OK (HTML form)
```

#### Crear usuario
```bash
curl -X POST "$BASE_URL/super/users" \
  -b cookies.txt \
  -d "email=user@example.com&slug=mi-negocio&nombre_negocio=Mi%20Negocio&password=pass123456" \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 302
# Validaciones:
# - Email: debe contener @
# - Slug: ^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$ y no reservado
# - Password: mínimo 6 caracteres
```

#### Editar usuario
```bash
curl -X POST "$BASE_URL/super/users/2/edit" \
  -b cookies.txt \
  -d "email=newemail@test.com&slug=nuevo-slug&nombre_negocio=Nuevo%20Nombre&is_active=on&password=newpass123" \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 302
# Nota: password es opcional (solo se actualiza si no está vacío)
```

#### Eliminar usuario
```bash
curl -X POST "$BASE_URL/super/users/2/delete" \
  -b cookies.txt \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 302
```

---

### 7️⃣ IMPERSONACIÓN

#### Suplantar usuario
```bash
curl -X POST "$BASE_URL/super/users/2/impersonate" \
  -b cookies.txt \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 302 (Redirect a /admin)
# Ahora la sesión es del usuario 2
```

#### Dejar de suplantar
```bash
curl -X POST "$BASE_URL/admin/stop-impersonating" \
  -b cookies.txt \
  -w "\nStatus: %{http_code}\n"

# Resultado esperado: 302 (Redirect a /super)
# Restaura la sesión del super-admin original
```

---

## Script de prueba automatizado

Crear `scripts/test_api.sh`:

```bash
#!/bin/bash
set -e

BASE_URL="http://localhost:8000"
COOKIES="/tmp/test_cookies.txt"

echo "🔐 Autenticando..."
curl -X POST "$BASE_URL/login" \
  -c "$COOKIES" \
  -d "usuario=admin&contrasena=admin" \
  -s -o /dev/null

echo "✓ Login exitoso"

echo "📁 Creando categorías..."
curl -X POST "$BASE_URL/admin/categories" \
  -b "$COOKIES" \
  -d "nombre=Bebidas" \
  -s -o /dev/null

echo "✓ Categoría creada"

echo "🍻 Agregando productos..."
curl -X POST "$BASE_URL/admin/items/add" \
  -b "$COOKIES" \
  -d "category_id=1&nombre=Cerveza&precio=8.50" \
  -s -o /dev/null

echo "✓ Producto agregado"

echo "📊 Verificando datos JSON..."
curl -X GET "$BASE_URL/api/data/super" \
  -s | jq . > /dev/null

echo "✓ Datos disponibles"

echo ""
echo "✅ TODAS LAS PRUEBAS PASARON"
```

---

## Notas importantes

- **Cookies de sesión**: Usar `-c` para guardar y `-b` para usar cookies en requests posteriores
- **IDs dinámicos**: Reemplazar `{cat_id}`, `{item_id}`, `{user_id}` con valores reales
- **Redirecciones**: Usar `-L` para seguir redirecciones automáticamente
- **JSON**: Usar `jq` para formatear respuestas: `curl ... | jq .`
- **Headers**: Algunos endpoints requieren `Content-Type: application/x-www-form-urlencoded`

---

## Troubleshooting

**Conexión rechazada**
```bash
# Verificar que el servidor esté corriendo
ps aux | grep uvicorn
# Si no, reiniciar con:
source venv/bin/activate && uvicorn main:app --port 8000
```

**Autenticación fallida (401)**
```bash
# Verificar credenciales en BD
python3 -c "import sqlite3; \
conn = sqlite3.connect('sanez.db'); \
cursor = conn.cursor(); \
cursor.execute('SELECT id, email, is_super_admin FROM users'); \
print(cursor.fetchall())"
```

**Error "no such column"**
```bash
# La BD vieja necesita migración
rm sanez.db
# Reiniciar servidor para crear BD nueva
```

---

## Variables de slugs reservadas

Estos slugs no pueden ser usados:
- `admin`
- `super`
- `api`
- `login`
- `logout`
- `static`
- `menu`
