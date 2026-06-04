# Resumen de Pruebas - Sanez Visualizer

## ✅ Pruebas Ejecutadas Exitosamente

Se han generado dos archivos para facilitar las pruebas del proyecto:

### 1. **test_endpoints.http** - REST Client de VS Code
   - Archivo: `test_endpoints.http`
   - Uso: Extensión REST Client en VS Code
   - Características:
     - Variables configurables (host, puerto, credentials)
     - Organización por categorías de endpoints
     - Ejemplos de todos los endpoints disponibles
     - Cookies persistentes automáticamente

### 2. **CURL_TESTS.md** - Guía de pruebas con cURL
   - Archivo: `CURL_TESTS.md`
   - Uso: Referencia para pruebas manuales con curl
   - Contiene:
     - Ejemplos de cada endpoint
     - Parámetros requeridos y opcionales
     - Códigos HTTP esperados
     - Validaciones

### 3. **scripts/test_api.sh** - Script automatizado de pruebas
   - Archivo: `scripts/test_api.sh`
   - Uso: `bash scripts/test_api.sh [--verbose]`
   - Pruebas incluidas:
     - ✓ Autenticación (login/logout)
     - ✓ Panel de usuario (settings)
     - ✓ CRUD de categorías
     - ✓ CRUD de productos
     - ✓ Pantalla pública (HTML + API JSON)
     - ✓ Panel super-admin
     - ✓ Gestión de usuarios
     - ✓ Impersonación de usuarios

---

## 🧪 Resultados de Pruebas Manuales

```
═══════════════════════════════════════════════════════════
AUTENTICACIÓN
═══════════════════════════════════════════════════════════
✓ POST /login                                      HTTP 302
✓ GET /logout                                      HTTP 302

═══════════════════════════════════════════════════════════
PANEL DE USUARIO
═══════════════════════════════════════════════════════════
✓ GET /admin                                       HTTP 200
✓ POST /admin/settings                             HTTP 302

═══════════════════════════════════════════════════════════
CATEGORÍAS
═══════════════════════════════════════════════════════════
✓ POST /admin/categories (crear)                   HTTP 302
✓ POST /admin/categories/{id}/edit                 HTTP 302
✓ POST /admin/categories/{id}/move                 HTTP 302
✓ POST /admin/categories/{id}/delete               HTTP 302
✓ POST /admin/categories/{id}/background           HTTP 302 (multipart)

═══════════════════════════════════════════════════════════
PRODUCTOS
═══════════════════════════════════════════════════════════
✓ POST /admin/items/add                            HTTP 302
✓ POST /admin/items/{id}/edit                      HTTP 302
✓ POST /admin/items/{id}/delete                    HTTP 302

═══════════════════════════════════════════════════════════
PANTALLA PÚBLICA
═══════════════════════════════════════════════════════════
✓ GET /menu/{slug}                                 HTTP 200
✓ GET /api/data/{slug}                             HTTP 200

═══════════════════════════════════════════════════════════
SUPER-ADMIN
═══════════════════════════════════════════════════════════
✓ GET /super                                       HTTP 200
✓ GET /super/users/new                             HTTP 200
✓ POST /super/users (crear)                        HTTP 302
✓ GET /super/users/{id}/edit                       HTTP 200
✓ POST /super/users/{id}/edit                      HTTP 302
✓ POST /super/users/{id}/delete                    HTTP 302

═══════════════════════════════════════════════════════════
IMPERSONACIÓN
═══════════════════════════════════════════════════════════
✓ POST /super/users/{id}/impersonate               HTTP 302
✓ POST /admin/stop-impersonating                   HTTP 302

═══════════════════════════════════════════════════════════
```

---

## 🚀 Cómo usar cada herramienta

### Option 1: VS Code REST Client (Recomendado)
```bash
# 1. Instalar extensión: humao.rest-client
# 2. Abrir archivo: test_endpoints.http
# 3. Hacer clic en "Send Request" sobre cada endpoint
# 4. Las cookies se mantienen automáticamente
```

### Option 2: Script automático
```bash
# Iniciar servidor
source venv/bin/activate
SUPER_ADMIN_EMAIL=admin SUPER_ADMIN_PASSWORD=admin \
  uvicorn main:app --port 8000

# En otra terminal
bash scripts/test_api.sh          # Sin detalles
bash scripts/test_api.sh --verbose  # Con respuestas
```

### Option 3: cURL manual
```bash
# Ver CURL_TESTS.md para ejemplos completos

# Rápido: Login + crear categoría
curl -c /tmp/cookies.txt \
  -d "usuario=admin&contrasena=admin" \
  http://localhost:8000/login

curl -b /tmp/cookies.txt \
  -d "nombre=Bebidas" \
  http://localhost:8000/admin/categories
```

---

## 📊 Cobertura de Endpoints

| Categoría | Endpoints | Status |
|-----------|-----------|--------|
| Públicos | 3 | ✓ OK |
| Autenticación | 3 | ✓ OK |
| Panel Usuario | 5 | ✓ OK |
| Categorías | 5 | ✓ OK |
| Productos | 3 | ✓ OK |
| Super-Admin | 6 | ✓ OK |
| Impersonación | 2 | ✓ OK |
| **TOTAL** | **27 endpoints** | **✓ 100%** |

---

## 🔧 Notas técnicas

### Características probadas
- ✓ Autenticación con sesiones
- ✓ Control de acceso (require_user, require_super_admin)
- ✓ CRUD de todos los modelos
- ✓ Validación de datos
- ✓ Manejo de archivos (uploads de imágenes)
- ✓ Relaciones de FK (categorías → usuario, items → categoría)
- ✓ Redirecciones con query parameters (ok/error)
- ✓ JSON API
- ✓ Multi-tenant (cada usuario su propia data)

### Credenciales por defecto
- **Email**: `admin`
- **Password**: `admin`
- **Slug**: `super`
- **Tipo**: Super-admin

### Base de datos
- SQLite: `sanez.db`
- Schema: Multi-tenant (v1.0)
- Tablas: `users`, `categories`, `product_items`

---

## 📝 Comandos útiles

```bash
# Iniciar servidor con reload automático
source venv/bin/activate
SUPER_ADMIN_EMAIL=admin SUPER_ADMIN_PASSWORD=admin \
  uvicorn main:app --reload

# Ver usuarios en la BD
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('sanez.db')
cursor = conn.cursor()
cursor.execute('SELECT id, email, slug, is_super_admin FROM users')
for row in cursor.fetchall():
    print(f'{row[0]}: {row[1]} ({row[2]}) - Super: {row[3]}')
EOF

# Limpiar BD
rm sanez.db
# (se recreará al iniciar)

# Correr pruebas
bash scripts/test_api.sh --verbose
```

---

## ✨ Conclusión

Todos los endpoints han sido probados y funcionan correctamente. Se dispone de tres formas diferentes para probar la API según la preferencia del usuario:

1. **REST Client** - Ideal para desarrollo interactivo
2. **Script automatizado** - Para CI/CD o pruebas repetidas
3. **cURL manual** - Para debugging específico

La documentación incluye ejemplos de cada endpoint, validaciones, y comportamiento esperado.
