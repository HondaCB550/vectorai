# VectorAI v2 — Schema de Base de Datos

## Tabla: materiales_validados

**Descripción:** La BD central de VectorAI. Contiene todos los materiales conocidos y verificados.
Inicialmente se importan de tu Base de Presupuestos (915 materiales).

### Estructura SQL

```sql
CREATE TABLE materiales_validados (
  codigo TEXT PRIMARY KEY,
  categoria TEXT NOT NULL,
  denominacion_principal TEXT NOT NULL,
  descripcion TEXT,
  especificaciones JSONB DEFAULT '{}',
  marcas_disponibles JSONB DEFAULT '[]',
  unidades_posibles JSONB DEFAULT '[]',
  confianza_matching INTEGER DEFAULT 95,
  validado_por TEXT DEFAULT 'sistema',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_categoria ON materiales_validados(categoria);
CREATE INDEX idx_denominacion ON materiales_validados(denominacion_principal);
```

### Filas y Columnas (Ejemplos Reales)

```
┌─────────┬──────────────┬────────────────────────┬─────────────────────┬──────────────────┬──────────────────┬────────────────────┬──────────────────┬─────────────┐
│ codigo  │ categoria    │ denominacion_principal │ descripcion         │ especificaciones │ marcas_disponibles│ unidades_posibles  │ confianza_matching│ validado_por│
├─────────┼──────────────┼────────────────────────┼─────────────────────┼──────────────────┼──────────────────┼────────────────────┼──────────────────┼─────────────┤
│ 001-A   │ Tubería PVC  │ Codo PVC A90 45-40mm   │ Codo roscado PVC... │ {...}            │ [...]             │ [...]              │ 95                 │ sistema     │
│ 002-B   │ Herrajes    │ Tornillo #8x1"         │ Acero inoxidable... │ {...}            │ [...]             │ [...]              │ 95                 │ sistema     │
│ 003-C   │ Aislantes   │ Lana de vidrio 100mm   │ Aislante térmica... │ {...}            │ [...]             │ [...]              │ 95                 │ sistema     │
└─────────┴──────────────┴────────────────────────┴─────────────────────┴──────────────────┴──────────────────┴────────────────────┴──────────────────┴─────────────┘
```

### Mapeo desde tu Base Actual

Tu tabla actual (Base de Presupuestos - Hoja Materiales):

```
┌────────┬────────┬──────────┬──────────────┬────────┬────────┐
│ CÓDIGO │ RUBRO  │ ITEM     │ DETALLE      │ UNIDAD │ MARCA  │
├────────┼────────┼──────────┼──────────────┼────────┼────────┤
│ 001-A  │ Tuber… │ Codo PVC │ Codo 45-40mm │ UNIDAD │ Marca A│
│ 002-B  │ Herr…  │ Tornillo │ #8x1 inox    │ UNIDAD │ Marca B│
└────────┴────────┴──────────┴──────────────┴────────┴────────┘
```

**Mapeo:**
- `CÓDIGO` → `codigo` (PK)
- `RUBRO` → `categoria`
- `ITEM` → `denominacion_principal`
- `DETALLE` → `descripcion`
- `UNIDAD` → parte de `unidades_posibles` (JSON)
- `MARCA` → parte de `marcas_disponibles` (JSON)

---

## Campos Detallados

### 1. codigo (TEXT, PK)

**Formato:** `NNN-L` donde NNN es número (001-999) y L es letra (A-Z)

```
Ejemplos válidos:
  001-A, 001-B, 001-Z
  002-A, 002-B, etc.
  999-Z (máximo)
```

**Validación:** Unique, no nulo

---

### 2. categoria (TEXT)

**Descripción:** Agrupación del material (corresponde a RUBRO en tu BD actual)

```
Ejemplos:
  "Tubería PVC"
  "Herrajes"
  "Aislantes"
  "Pinturas"
  "Aceros"
  "Maderas"
  "Cementos"
  "Vidrios"
```

**Nota:** Usa categorías consistentes. No mezcles "Tuber" con "Tubería".

---

### 3. denominacion_principal (TEXT)

**Descripción:** El nombre principal del material. Versión "canonical" (la más común).

```
Ejemplos:
  "Codo PVC A90 45-40mm"
  "Tornillo #8x1\""
  "Lana de vidrio 100mm"
  "Pintura blanca latex 20L"
```

**Nota:** Este es el alias que usamos como "referencia". Los otros aliases van en `material_denominaciones` table.

---

### 4. descripcion (TEXT, NULL ok)

**Descripción:** Detalle técnico adicional.

```
Ejemplos:
  "Codo roscado PVC normalizado IRAM 2080"
  "Tornillo acero inoxidable de cabeza hexagonal"
  "Aislante térmico de lana de vidrio, densidad 32kg/m³"
```

**Nota:** Puede ser NULL. Sirve para búsqueda y especificaciones.

---

### 5. especificaciones (JSONB, DEFAULT '{}')

**Descripción:** Datos técnicos estructurados. Formato libre pero consistente.

```json
Ejemplo 1 (Codo PVC):
{
  "norma": "IRAM 2080",
  "material": "PVC",
  "tipo": "roscado",
  "angulo": 90,
  "diametro_entrada_mm": 45,
  "diametro_salida_mm": 40,
  "presion_trabajo_bar": 10
}

Ejemplo 2 (Tornillo):
{
  "material": "Acero inoxidable",
  "tipo": "hexagonal",
  "norma": "DIN 933",
  "diametro_mm": 8,
  "largo_mm": 25,
  "rosca": "métrica M8x1.25",
  "grado_resistencia": 8.8
}

Ejemplo 3 (Aislante):
{
  "material": "Lana de vidrio",
  "densidad_kg_m3": 32,
  "espesor_mm": 100,
  "conductividad_W_mK": 0.045,
  "reaccion_fuego": "A1"
}
```

**Reglas:**
- Las claves deben ser lowercase + snake_case
- Los valores pueden ser string, number, boolean
- No incluir arrays (usar campos separados para eso)
- Documentar el esquema de cada categoría

---

### 6. marcas_disponibles (JSONB ARRAY)

**Descripción:** Lista de marcas que fabrican este material.

```json
Ejemplos:

["Marca A", "Marca B", "Marca China"]

["Baukraft Private", "Bonora Importada", "Marca Genérica"]

["Atlas", "Argos", "Avellaneda"]

["Osram", "Siemens", "Fenos"]
```

**Reglas:**
- Array de strings
- Cada string = nombre de marca
- Puede estar vacío si no hay marca definida
- Consistencia: usa "Marca A" o "Osram", no "Marca A" y "marca a"

---

### 7. unidades_posibles (JSONB ARRAY OF OBJECTS)

**Descripción:** Las unidades en que se puede comprar este material.

```json
Ejemplo 1 (Codo PVC - solo por unidad):
[
  {
    "unidad": "UNIDAD",
    "descripcion": "1 codo",
    "equivalencia": 1
  }
]

Ejemplo 2 (Tornillo - múltiples unidades):
[
  {
    "unidad": "UNIDAD",
    "descripcion": "Tornillo individual",
    "equivalencia": 1
  },
  {
    "unidad": "CAJA_1000",
    "descripcion": "Caja de 1000 tornillos",
    "equivalencia": 1000
  },
  {
    "unidad": "BOLSA_500",
    "descripcion": "Bolsa de 500 tornillos",
    "equivalencia": 500
  }
]

Ejemplo 3 (Cable - por metro o rollo):
[
  {
    "unidad": "METRO",
    "descripcion": "1 metro de cable",
    "equivalencia": 1
  },
  {
    "unidad": "ROLLO_100M",
    "descripcion": "Rollo de 100 metros",
    "equivalencia": 100
  }
]

Ejemplo 4 (Bolsas de cemento):
[
  {
    "unidad": "BOLSA",
    "descripcion": "Bolsa de 50kg",
    "equivalencia": 50
  }
]
```

**Estructura:**
- `unidad`: código único (UNIDAD, CAJA_1000, BOLSA, METRO, ROLLO_100M, etc.)
- `descripcion`: para humanos
- `equivalencia`: número de unidades básicas (para normalizar precios)

**Regla importante:** La primera unidad en el array es la "unidad básica" (base para cálculos).

---

### 8. confianza_matching (INTEGER 0-100)

**Descripción:** Qué tan confiable es este material para matching automático.

```
Valores:
  95 = Validado por nosotros, códigos de proveedores mapeados
  90 = Validado pero sin códigos aún
  85 = Encontrado en múltiples PDFs, patrones consistentes
  75 = Nuevo pero con especificaciones claras
```

**Regla:** Inicialmente todos en 95 (tu BD es verificada).

---

### 9. validado_por (TEXT, DEFAULT 'sistema')

**Descripción:** Quién validó este material.

```
Ejemplos:
  "sistema" (inicial)
  "team@vectorai.com"
  "usuario_baukraft"
```

---

### 10. created_at, updated_at (TIMESTAMP)

**Descripción:** Auditoría.

```
Auto-generados:
  created_at: TIMESTAMP DEFAULT NOW()
  updated_at: TIMESTAMP DEFAULT NOW()
```

---

## Tabla: material_denominaciones

**Descripción:** Alias y variaciones de nombres. Crece continuamente.

### Estructura SQL

```sql
CREATE TABLE material_denominaciones (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo_material TEXT NOT NULL REFERENCES materiales_validados(codigo),
  denominacion TEXT NOT NULL,
  origen TEXT,
  confianza INTEGER DEFAULT 80,
  frecuencia_encontrada INTEGER DEFAULT 1,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_codigo_material ON material_denominaciones(codigo_material);
CREATE INDEX idx_denominacion ON material_denominaciones(denominacion);
CREATE UNIQUE INDEX idx_codigo_denominacion ON material_denominaciones(codigo_material, denominacion);
```

### Ejemplos de Filas

```
┌─────────────────────┬──────────────────┬─────────────────────┬──────────┬────────────┬──────────────────┐
│ codigo_material     │ denominacion     │ origen              │ confianza│ frecuencia │ created_at       │
├─────────────────────┼──────────────────┼─────────────────────┼──────────┼────────────┼──────────────────┤
│ 001-A               │ Codo PVC 45-40mm │ usuario_baukraft    │ 98       │ 50         │ 2026-06-21       │
│ 001-A               │ Codo PVC A90 45  │ usuario_bonora      │ 94       │ 28         │ 2026-06-21       │
│ 001-A               │ Codo 45-40       │ pdf_carosio         │ 87       │ 12         │ 2026-06-21       │
│ 001-A               │ Codo PVC rosca   │ usuario_local       │ 82       │ 5          │ 2026-06-22       │
├─────────────────────┼──────────────────┼─────────────────────┼──────────┼────────────┼──────────────────┤
│ 002-B               │ Tornillo #8x1"   │ usuario_baukraft    │ 99       │ 120        │ 2026-06-21       │
│ 002-B               │ Tornillo #8      │ pdf_bonora          │ 95       │ 45         │ 2026-06-21       │
│ 002-B               │ Perno 8x1 inox   │ usuario_local       │ 88       │ 8          │ 2026-06-22       │
└─────────────────────┴──────────────────┴─────────────────────┴──────────┴────────────┴──────────────────┘
```

---

## Tabla: codigos_proveedores

**Descripción:** La tabla "mágica" que permite matching 95% automático.

### Estructura SQL

```sql
CREATE TABLE codigos_proveedores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  proveedor TEXT NOT NULL,
  codigo_proveedor TEXT NOT NULL,
  codigo_material TEXT NOT NULL REFERENCES materiales_validados(codigo),
  marca_asignada TEXT,
  confianza INTEGER DEFAULT 95,
  validado_por TEXT DEFAULT 'sistema',
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(proveedor, codigo_proveedor)
);

CREATE INDEX idx_proveedor ON codigos_proveedores(proveedor);
CREATE INDEX idx_codigo_proveedor ON codigos_proveedores(codigo_proveedor);
CREATE INDEX idx_codigo_material ON codigos_proveedores(codigo_material);
```

### Ejemplos de Filas

```
┌─────────────┬──────────────────┬─────────────────┬──────────────────┬──────────────┬───────────┐
│ proveedor   │ codigo_proveedor │ codigo_material │ marca_asignada   │ confianza    │ validado…│
├─────────────┼──────────────────┼─────────────────┼──────────────────┼──────────────┼───────────┤
│ Baukraft    │ BK-4521          │ 001-A           │ Marca A          │ 95           │ sistema   │
│ Bonora      │ BON-0087         │ 001-A           │ Marca B          │ 95           │ sistema   │
│ Carosio     │ CAR-789          │ 001-A           │ Marca C          │ 95           │ sistema   │
│             │                  │                 │                  │              │           │
│ Baukraft    │ BK-8888          │ 002-B           │ Marca A          │ 95           │ sistema   │
│ Bonora      │ BON-0042         │ 002-B           │ Marca D          │ 95           │ sistema   │
│ Carosio     │ CAR-321          │ 002-B           │ Marca A          │ 95           │ sistema   │
│             │                  │                 │                  │              │           │
│ Corralon_Z  │ COR-Z-1234       │ 001-A           │ Marca E          │ 85           │ team@v…   │
└─────────────┴──────────────────┴─────────────────┴──────────────────┴──────────────┴───────────┘

UNIQUE constraint: (proveedor, codigo_proveedor)
  ✓ Baukraft BK-4521 → 001-A
  ✓ Bonora BON-0087 → 001-A  (distinto código)
  ✓ Baukraft BK-8888 → 002-B (distinto código)
  ✗ No puede haber dos Baukraft BK-4521 con distintos códigos_material
```

---

## Tabla: materiales_pendientes

**Descripción:** Nuevos encontrados en PDFs. Nosotros los revisamos.

### Estructura SQL

```sql
CREATE TABLE materiales_pendientes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  descripcion_original TEXT NOT NULL,
  codigo_proveedor TEXT,
  proveedor TEXT,
  categoria_sugerida TEXT,
  unidad_sugerida TEXT,
  confianza_ia INTEGER DEFAULT 0,
  agrupado_con JSONB DEFAULT '[]',
  razon_agrupamiento TEXT,
  estado TEXT DEFAULT 'PENDIENTE',
  validado_por TEXT,
  pdf_origen TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_estado ON materiales_pendientes(estado);
CREATE INDEX idx_proveedor ON materiales_pendientes(proveedor);
CREATE INDEX idx_created_at ON materiales_pendientes(created_at);
```

### Ejemplo de Filas

```
┌─────────────────────────┬──────────┬────────────┬───────────────────┬───────────────┐
│ descripcion_original    │ proveedor│ confianza… │ agrupado_con      │ estado        │
├─────────────────────────┼──────────┼────────────┼───────────────────┼───────────────┤
│ Aislante XYZ espuma 5cm │ Carosio  │ 78         │ [id_bonora_item]  │ PENDIENTE     │
│ Aislante XYZ espuma 5cm │ Bonora   │ 78         │ [id_carosio_item] │ PENDIENTE     │
│ Pintura blanca latex 20 │ Baukraft │ 65         │ []                │ PENDIENTE     │
│ Malla galv. 1x2m        │ Carosio  │ 71         │ []                │ PENDIENTE     │
└─────────────────────────┴──────────┴────────────┴───────────────────┴───────────────┘
```

---

## Tabla: precios_historicos

**Descripción:** Data warehouse. Cada precio que ve el sistema se guarda aquí.

### Estructura SQL

```sql
CREATE TABLE precios_historicos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  proveedor TEXT NOT NULL,
  codigo_material TEXT,
  codigo_pendiente UUID,
  marca TEXT,
  unidad TEXT NOT NULL,
  precio DECIMAL(12,2) NOT NULL,
  cantidad INTEGER,
  pdf_origen TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_proveedor_codigo ON precios_historicos(proveedor, codigo_material);
CREATE INDEX idx_created_at ON precios_historicos(created_at);
```

### Ejemplos de Filas

```
┌──────────┬─────────────┬────────┬──────────┬────────────────┐
│ proveedor│ codigo_mat… │ marca  │ precio   │ created_at     │
├──────────┼─────────────┼────────┼──────────┼────────────────┤
│ Baukraft │ 001-A       │ Marca A│ 150.00   │ 2026-06-21     │
│ Bonora   │ 001-A       │ Marca B│ 155.00   │ 2026-06-21     │
│ Carosio  │ 001-A       │ Marca C│ 160.00   │ 2026-06-21     │
│ Baukraft │ 002-B       │ Marca A│ 2.50     │ 2026-06-21     │
│ Bonora   │ 002-B       │ Marca D│ 3.00     │ 2026-06-21     │
│ Baukraft │ NULL        │ Marca X│ 450.00   │ 2026-06-22     │
│          │ (pendiente) │        │          │                │
└──────────┴─────────────┴────────┴──────────┴────────────────┘
```

---

## Cómo Migrar desde Tu Base Actual

### Paso 1: Exportar desde Excel

Tu archivo actual: `Base de Presupuestos_2026_macro.xlsm`
Hoja: `Materiales`

Exportar a CSV:
```
CÓDIGO,RUBRO,ITEM,DETALLE,UNIDAD,MARCA
001-A,Tubería PVC,Codo PVC,Codo PVC A90 45-40mm,UNIDAD,Marca A
002-B,Herrajes,Tornillo,Tornillo #8x1" acero inox,UNIDAD,Marca B
...
```

### Paso 2: Script de Importación (Python)

```python
import csv
import json
from supabase import create_client

SUPABASE_URL = "..."
SUPABASE_KEY = "..."
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

with open('materiales.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Parsear datos
        codigo = row['CÓDIGO'].strip()
        categoria = row['RUBRO'].strip()
        denominacion = row['ITEM'].strip()
        descripcion = row['DETALLE'].strip()
        unidad = row['UNIDAD'].strip()
        marca = row['MARCA'].strip()
        
        # Construir JSON para unidades
        unidades_posibles = [
            {
                "unidad": unidad.upper(),
                "descripcion": f"1 {denominacion}",
                "equivalencia": 1
            }
        ]
        
        # Construir JSON para marcas
        marcas_disponibles = [marca] if marca else []
        
        # Insertar en Supabase
        sb.table('materiales_validados').insert({
            'codigo': codigo,
            'categoria': categoria,
            'denominacion_principal': denominacion,
            'descripcion': descripcion,
            'unidades_posibles': unidades_posibles,
            'marcas_disponibles': marcas_disponibles,
            'confianza_matching': 95,
            'validado_por': 'sistema'
        }).execute()

print("✅ Migración completada")
```

### Paso 3: Verificación

```sql
-- Verificar conteo
SELECT COUNT(*) FROM materiales_validados;
-- Debería ser ~915

-- Ver ejemplos
SELECT codigo, denominacion_principal, marcas_disponibles, unidades_posibles
FROM materiales_validados
LIMIT 5;
```

---

## Índices Recomendados

```sql
-- materiales_validados
CREATE INDEX idx_materiales_categoria ON materiales_validados(categoria);
CREATE INDEX idx_materiales_denominacion ON materiales_validados(denominacion_principal);

-- material_denominaciones
CREATE INDEX idx_denoms_codigo ON material_denominaciones(codigo_material);
CREATE UNIQUE INDEX idx_denoms_unique ON material_denominaciones(codigo_material, denominacion);

-- codigos_proveedores
CREATE INDEX idx_codprov_proveedor ON codigos_proveedores(proveedor);
CREATE UNIQUE INDEX idx_codprov_unique ON codigos_proveedores(proveedor, codigo_proveedor);

-- precios_historicos
CREATE INDEX idx_precios_proveedor ON precios_historicos(proveedor);
CREATE INDEX idx_precios_fecha ON precios_historicos(created_at);
```

---

## RLS (Row Level Security)

Para MVP: **NO necesitas RLS** en estas tablas (son datos públicos del sistema, no datos de usuario).

Las tablas de usuario (comparativas, equivalencias) sí necesitan RLS.

---

## Validaciones

```python
# Validar código
def validar_codigo(codigo):
    import re
    patron = r'^\d{3}-[A-Z]$'
    return bool(re.match(patron, codigo))

# Validar que unidad_principal sea la primera
def validar_unidades(unidades_posibles):
    assert len(unidades_posibles) > 0, "Al menos una unidad"
    assert unidades_posibles[0]['equivalencia'] == 1, "Primera unidad debe ser base"
```

---

## Resumen Rápido

| Tabla | Rows | Frecuencia | Notas |
|-------|------|-----------|-------|
| materiales_validados | ~915 | Actualizado 1x/semana (nosotros) | Base central |
| material_denominaciones | ~2000 | Crece diariamente | Aliases encontrados |
| codigos_proveedores | ~500+ | Crece continuamente | Mágica para matching |
| materiales_pendientes | ~100+ | Crece diariamente | Temporal, se procesa |
| precios_historicos | Millones | Crece continuamente | Data warehouse |

