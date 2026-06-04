#!/bin/bash
# Script de pruebas de API para Sanez Visualizer
# Uso: bash scripts/test_api.sh [--verbose]

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"
COOKIES="/tmp/sanez_test_cookies.txt"
VERBOSE="${1:-}"

# Colores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funciones auxiliares
log_test() {
    echo -e "${BLUE}▶${NC} $1"
}

log_ok() {
    echo -e "${GREEN}✓${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
    exit 1
}

log_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# Test wrapper
test_endpoint() {
    local name=$1
    local method=$2
    local endpoint=$3
    local data=$4
    local expected_code=$5

    log_test "$name"

    if [ -z "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$BASE_URL$endpoint" -b "$COOKIES")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$BASE_URL$endpoint" -b "$COOKIES" -d "$data")
    fi

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)

    if [ "$http_code" = "$expected_code" ]; then
        log_ok "$name (HTTP $http_code)"
        [ "$VERBOSE" = "--verbose" ] && echo "$body" | head -5
    else
        log_error "$name - Expected $expected_code but got $http_code"
    fi
}

# Banner
echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║       Sanez Visualizer - Pruebas de API con cURL             ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Verificar conexión al servidor
echo -n "Verificando conexión a $BASE_URL... "
if ! curl -s -m 2 "$BASE_URL/login" > /dev/null 2>&1; then
    log_error "No hay conexión a $BASE_URL"
    exit 1
fi
echo "OK"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════════════════
echo -e "${YELLOW}═══ AUTENTICACIÓN ═══${NC}"

log_test "POST /login"
response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/login" \
    -c "$COOKIES" \
    -d "usuario=admin&contrasena=admin")
http_code=$(echo "$response" | tail -n1)
if [ "$http_code" = "302" ]; then
    log_ok "Login exitoso (HTTP $http_code)"
else
    log_error "Login fallido (HTTP $http_code)"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# PANEL DE USUARIO
# ═══════════════════════════════════════════════════════════════════════════
echo -e "${YELLOW}═══ PANEL DE USUARIO ═══${NC}"

test_endpoint "GET /admin" "GET" "/admin" "" "200"
test_endpoint "POST /admin/settings" "POST" "/admin/settings" "tiempo_rotacion=15" "302"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# GESTIÓN DE CATEGORÍAS
# ═══════════════════════════════════════════════════════════════════════════
echo -e "${YELLOW}═══ GESTIÓN DE CATEGORÍAS ═══${NC}"

test_endpoint "POST /admin/categories (Bebidas)" "POST" "/admin/categories" "nombre=Bebidas" "302"
test_endpoint "POST /admin/categories (Comidas)" "POST" "/admin/categories" "nombre=Comidas" "302"
test_endpoint "POST /admin/categories/{id}/edit" "POST" "/admin/categories/1/edit" "nombre=Bebidas+Frias" "302"
test_endpoint "POST /admin/categories/{id}/move" "POST" "/admin/categories/1/move" "direccion=abajo" "302"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# GESTIÓN DE PRODUCTOS
# ═══════════════════════════════════════════════════════════════════════════
echo -e "${YELLOW}═══ GESTIÓN DE PRODUCTOS ═══${NC}"

test_endpoint "POST /admin/items/add (IPA)" "POST" "/admin/items/add" \
    "category_id=1&nombre=Cerveza+IPA&precio=%248.50" "302"
test_endpoint "POST /admin/items/add (Rubia)" "POST" "/admin/items/add" \
    "category_id=1&nombre=Cerveza+Rubia&precio=%247.00" "302"
test_endpoint "POST /admin/items/{id}/edit" "POST" "/admin/items/1/edit" \
    "nombre=IPA+Artesanal&precio=%249.50" "302"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# PANTALLA PÚBLICA
# ═══════════════════════════════════════════════════════════════════════════
echo -e "${YELLOW}═══ PANTALLA PÚBLICA ═══${NC}"

log_test "GET /menu/{slug}"
response=$(curl -s -w "\n%{http_code}" "$BASE_URL/menu/super")
http_code=$(echo "$response" | tail -n1)
if [ "$http_code" = "200" ]; then
    log_ok "GET /menu/super (HTTP $http_code)"
    [ "$VERBOSE" = "--verbose" ] && echo "$response" | head -10
else
    log_error "GET /menu/super (HTTP $http_code)"
fi

log_test "GET /api/data/{slug}"
response=$(curl -s -w "\n%{http_code}" "$BASE_URL/api/data/super")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)
if [ "$http_code" = "200" ]; then
    log_ok "GET /api/data/super (HTTP $http_code)"
    if [ "$VERBOSE" = "--verbose" ]; then
        echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
    fi
else
    log_error "GET /api/data/super (HTTP $http_code)"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# SUPER-ADMIN
# ═══════════════════════════════════════════════════════════════════════════
echo -e "${YELLOW}═══ SUPER-ADMIN ═══${NC}"

test_endpoint "GET /super" "GET" "/super" "" "200"

log_test "POST /super/users"
response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/super/users" \
    -b "$COOKIES" \
    -d "email=testuser@example.com&slug=testbar&nombre_negocio=Test+Bar&password=testpass123")
http_code=$(echo "$response" | tail -n1)
if [ "$http_code" = "302" ]; then
    log_ok "Usuario creado (HTTP $http_code)"
    NEW_USER_ID=$(echo "$response" | head -n-1 | grep -o "user_id=[0-9]*" | cut -d= -f2 | head -1)
    [ -z "$NEW_USER_ID" ] && NEW_USER_ID="2"
    log_info "User ID: $NEW_USER_ID"
else
    log_error "Error al crear usuario (HTTP $http_code)"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# IMPERSONACIÓN
# ═══════════════════════════════════════════════════════════════════════════
echo -e "${YELLOW}═══ IMPERSONACIÓN ═══${NC}"

test_endpoint "POST /super/users/{id}/impersonate" "POST" "/super/users/2/impersonate" "" "302"
test_endpoint "POST /admin/stop-impersonating" "POST" "/admin/stop-impersonating" "" "302"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════════════════════════════════════
echo -e "${YELLOW}═══ LOGOUT ═══${NC}"

log_test "GET /logout"
response=$(curl -s -w "\n%{http_code}" "$BASE_URL/logout" -b "$COOKIES")
http_code=$(echo "$response" | tail -n1)
if [ "$http_code" = "302" ]; then
    log_ok "Logout exitoso (HTTP $http_code)"
else
    log_error "Logout fallido (HTTP $http_code)"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# RESUMEN
# ═══════════════════════════════════════════════════════════════════════════
echo "╔═══════════════════════════════════════════════════════════════╗"
echo -e "║  ${GREEN}✓ TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE${NC}            ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "Tips:"
echo "  • Usar --verbose para ver detalles de respuestas"
echo "  • Cookies guardadas en: $COOKIES"
echo "  • Base URL: $BASE_URL"
echo ""

# Limpiar cookies
rm -f "$COOKIES"
