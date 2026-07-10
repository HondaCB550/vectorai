# Vectorai v2 — Schema de Base de Datos

**Decisión clave:** Sin tabla `codigos_proveedores`. El matching se hace 100% por texto (aliases).
Con 500+ proveedores del país, los códigos internos de cada uno son incompatibles entre sí.
Los aliases de texto son universales y escalan sin mantenimiento manual.

---

## Tabla: materiales_validados

**La BD central de Vectorai.** Contiene todos los materiales conocidos y verificados.
Inicialmente se importan desde `api/data/master_materiales.json` (915 materiales).

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
  validado_por TEXT DEFAULT 'sistema',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_mat_categoria ON materiales_validados(categoria);
CREATE INDEX idx_mat_denominacion ON materiales_validados(denominacion_principal);
```

### Ejemplos de Filas

```
┌─────────┬──────────────┬────────────────────────┬─────────────────────┐
│ codigo  │ categoria    │ denominacion_principal  │ descripcion         │
├─────────┼──────────────┼────────────────────────┼─────────────────────┤
│ 001-A   │ Tubería PVC  │ Codo PVC A90 45-40mm   │ Codo roscado PVC... │
│ 002-B   │ Herrajes     │ Tornillo #8x1"          │ Acero inoxidable... │
│ 003-C   │ Aislantes    │ Lana de vidrio 100mm    │ Aislante térmico... │
└─────────┴──────────────┴────────────────────────┴─────────────────────┘
```

### Mapeo desde master_materiales.json

El JSON actual tiene esta estructura por ítem:
```json
{
  "codigo": "001-A",
  "rubro": "Tubería PVC",
  "item": "Codo PVC",
  "detalle": "Codo PVC A90 45-40mm",
  "unidad": "UNIDAD",
  "marca": "Marca A"
}
```

Mapeo:
- `codigo` → `codigo` (PK)
- `rubro` → `categoria`
- `item` → `denominacion_principal`
- `detalle` → `descripcion`
- `unidad` → primer elemento de `unidades_posibles`
- `marca` → primer elemento de `marcas_disponibles`

---

## Tabla: material_denominaciones

**El corazón de Vectorai.** Guarda todas las formas en que los proveedores
nombran cada material. Crece con cada PDF procesado.

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

CREATE INDEX idx_den_codigo ON material_denominaciones(codigo_material);
CREATE INDEX idx_den_texto ON material_denominaciones(denominacion);
CREATE UNIQUE INDEX idx_den_unique ON material_denominaciones(codigo_material, denominacion);
```

### Ejemplos de Filas

```
┌─────────────────┬──────────────────────┬──────────────────────┬──────────┬────────────┐
│ codigo_material │ denominacion         │ origen               │ confianza│ frecuencia │
├─────────────────┼──────────────────────┼──────────────────────┼──────────┼────────────┤
│ 001-A           │ Codo PVC 45-40mm     │ pdf_baukraft         │ 98       │ 50         │
│ 001-A           │ Codo PVC A90 45      │ pdf_bonora           │ 94       │ 28         │
│ 001-A           │ Codo 45-40           │ pdf_carosio          │ 87       │ 12         │
│ 001-A           │ Codo PVC rosca       │ pdf_corralon_norte   │ 82       │ 5          │
├─────────────────┼──────────────────────┼──────────────────────┼──────────┼────────────┤
│ 002-B           │ Tornillo #8x1"       │ pdf_baukraft         │ 99       │ 120        │
│ 002-B           │ Tornillo #8          │ pdf_bonora           │ 95       │ 45         │
│ 002-B           │ Perno 8x1 inox       │ pdf_corralon_sur     │ 88       │ 8          │
└─────────────────┴──────────────────────┴──────────────────────┴──────────┴────────────┘
```

### Campos

- **codigo_material**: FK a materiales_validados
- **denominacion**: el texto exacto encontrado en el PDF (normalizado a lowercase sin espacios extra)
- **origen**: de dónde vino (`pdf_baukraft`, `usuario_confirmacion`, `admin_manual`)
- **confianza**: 0-100, sube cada vez que aparece el mismo texto y se confirma
- **frecuencia_encontrada**: cuántas veces apareció este texto exacto (para depurar falsos positivos)

### Carga inicial de aliases

Al migrar los 915 materiales, cargar también los aliases iniciales:
```python
# Para cada material, crear alias con item + detalle
for mat in materiales:
    aliases = set()
    if mat['item']:
        aliases.add(mat['item'].strip())
    if mat['detalle']:
        aliases.add(mat['detalle'].strip())
    
    for alias in aliases:
        sb.table('material_denominaciones').insert({
            'codigo_material': mat['codigo'],
            'denominacion': alias.lower(),
            'origen': 'migracion_inicial',
            'confianza': 90,
            'frecuencia_encontrada': 1
        }).execute()
```

---

## Tabla: materiales_pendientes

**Cola de revisión.** Textos de PDFs que no matchearon con ningún material conocido.

### Estructura SQL

```sql
CREATE TABLE materiales_pendientes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  descripcion_original TEXT NOT NULL,
  descripcion_normalizada TEXT,
  proveedor TEXT,
  categoria_sugerida TEXT,
  unidad_sugerida TEXT,
  precio_visto DECIMAL(12,2),
  agrupado_con JSONB DEFAULT '[]',
  estado TEXT DEFAULT 'PENDIENTE',  -- PENDIENTE, VALIDADO, RECHAZADO
  validado_por TEXT,
  codigo_asignado TEXT REFERENCES materiales_validados(codigo),
  pdf_origen TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_pend_estado ON materiales_pendientes(estado);
CREATE INDEX idx_pend_desc ON materiales_pendientes(descripcion_normalizada);
CREATE INDEX idx_pend_created ON materiales_pendientes(created_at);
```

### Ejemplo de Filas

```
┌─────────────────────────┬──────────────┬────────────┬────────────┬──────────────┐
│ descripcion_original    │ proveedor    │ precio…    │ agrupado…  │ estado       │
├─────────────────────────┼──────────────┼────────────┼────────────┼──────────────┤
│ Placa OSB 18mm E1 Finsa │ Baukraft     │ 8500.00    │ [id2, id3] │ PENDIENTE    │
│ OSB 18mm fenólico       │ Bonora       │ 8200.00    │ [id1, id3] │ PENDIENTE    │
│ Pintura blanca latex 20L│ Carosio      │ 12500.00   │ []         │ PENDIENTE    │
└─────────────────────────┴──────────────┴────────────┴────────────┴──────────────┘
```

### Flujo de validación admin

```
Admin ve: "Placa OSB 18mm E1 Finsa" (Baukraft) + "OSB 18mm fenólico" (Bonora)
Admin decide:
  → [Linkear ambos a OSB-003-A] 
     ↓
  sistema inserta:
    material_denominaciones: "placa osb 18mm e1 finsa" → OSB-003-A
    material_denominaciones: "osb 18mm fenólico" → OSB-003-A
  sistema actualiza materiales_pendientes.estado = 'VALIDADO'

Próximo PDF con "Placa OSB 18mm": match automático, score 100.
```

---

## Tabla: precios_historicos

**Data warehouse.** Cada precio que ve el sistema se guarda aquí indefinidamente.
Es el activo de largo plazo para análisis de tendencias e inteligencia de mercado.

### Estructura SQL

```sql
CREATE TABLE precios_historicos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  proveedor TEXT NOT NULL,
  codigo_material TEXT REFERENCES materiales_validados(codigo),
  codigo_pendiente UUID REFERENCES materiales_pendientes(id),
  marca TEXT,
  unidad TEXT NOT NULL,
  precio DECIMAL(12,2) NOT NULL,
  cantidad INTEGER DEFAULT 1,
  pdf_origen TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_prec_proveedor ON precios_historicos(proveedor, codigo_material);
CREATE INDEX idx_prec_fecha ON precios_historicos(created_at);
CREATE INDEX idx_prec_material ON precios_historicos(codigo_material);
```

### Ejemplos de Filas

```
┌──────────┬─────────────┬────────┬──────────┬────────────┐
│ proveedor│ codigo_mat  │ marca  │ precio   │ created_at │
├──────────┼─────────────┼────────┼──────────┼────────────┤
│ Baukraft │ 001-A       │ Marca A│ 150.00   │ 2026-06-21 │
│ Bonora   │ 001-A       │ Marca B│ 155.00   │ 2026-06-21 │
│ Carosio  │ 001-A       │ Marca C│ 160.00   │ 2026-06-21 │
│ Baukraft │ 002-B       │ Marca A│ 2.50     │ 2026-06-21 │
│ Baukraft │ NULL (pend.)│ —      │ 8500.00  │ 2026-06-22 │
└──────────┴─────────────┴────────┴──────────┴────────────┘
```

**Nota:** Si el ítem no matcheó aún (`codigo_material = NULL`), se guarda igual
referenciando `codigo_pendiente`. Una vez que se valida, se puede hacer UPDATE.

---

## Script de Migración Completo

```python
import json
from supabase import create_client

SUPABASE_URL = "..."
SUPABASE_KEY = "..."
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

with open('api/data/master_materiales.json', encoding='utf-8') as f:
    materiales = json.load(f)

# Paso 1: Insertar materiales
for mat in materiales:
    codigo = mat.get('codigo', '').strip()
    if not codigo:
        continue

    unidades = [{"unidad": mat.get('unidad', 'UNIDAD'), "descripcion": "unidad base", "equivalencia": 1}]
    marcas = [mat['marca']] if mat.get('marca') else []

    sb.table('materiales_validados').insert({
        'codigo': codigo,
        'categoria': mat.get('rubro', '').strip(),
        'denominacion_principal': mat.get('item', '').strip(),
        'descripcion': mat.get('detalle', '').strip(),
        'unidades_posibles': unidades,
        'marcas_disponibles': marcas,
        'validado_por': 'migracion_inicial'
    }).execute()

# Paso 2: Cargar aliases iniciales desde item + detalle
aliases_batch = []
seen = set()
for mat in materiales:
    codigo = mat.get('codigo', '').strip()
    if not codigo:
        continue
    
    textos = []
    if mat.get('item'):
        textos.append(mat['item'].strip().lower())
    if mat.get('detalle') and mat['detalle'].strip().lower() != mat.get('item', '').strip().lower():
        textos.append(mat['detalle'].strip().lower())

    for texto in textos:
        key = f"{codigo}|{texto}"
        if key not in seen and texto:
            seen.add(key)
            aliases_batch.append({
                'codigo_material': codigo,
                'denominacion': texto,
                'origen': 'migracion_inicial',
                'confianza': 90,
                'frecuencia_encontrada': 1
            })

# Insertar en lotes
batch_size = 100
for i in range(0, len(aliases_batch), batch_size):
    sb.table('material_denominaciones').insert(aliases_batch[i:i+batch_size]).execute()

print(f"✅ {len(materiales)} materiales migrados")
print(f"✅ {len(aliases_batch)} aliases iniciales cargados")
```

---

## Lógica de Matching (Python)

```python
from rapidfuzz import fuzz, process

def match_texto_a_material(texto_pdf: str, denominaciones: list[dict]) -> dict:
    """
    texto_pdf: descripción extraída del PDF
    denominaciones: lista de {id, codigo_material, denominacion}
    
    Retorna: {codigo_material, score, denominacion_matcheada, nivel}
    """
    texto_norm = texto_pdf.strip().lower()
    
    # Construir lista de textos para comparar
    textos = [d['denominacion'] for d in denominaciones]
    
    # Fuzzy match
    resultado = process.extractOne(
        texto_norm,
        textos,
        scorer=fuzz.token_set_ratio,
        score_cutoff=50
    )
    
    if not resultado:
        return {'nivel': 'sin_match', 'score': 0}
    
    texto_match, score, idx = resultado
    den = denominaciones[idx]
    
    if score >= 85:
        nivel = 'automatico'
    elif score >= 60:
        nivel = 'dudoso'
    else:
        nivel = 'sin_match'
    
    return {
        'codigo_material': den['codigo_material'],
        'score': score,
        'denominacion_matcheada': texto_match,
        'nivel': nivel
    }
```

---

## Verificación Post-Migración

```sql
-- Conteo de materiales
SELECT COUNT(*) FROM materiales_validados;
-- Esperado: ~915

-- Conteo de aliases
SELECT COUNT(*) FROM material_denominaciones;
-- Esperado: ~1500-2000 (al menos item + detalle por material)

-- Materiales sin alias (para detectar problemas)
SELECT codigo FROM materiales_validados
WHERE codigo NOT IN (SELECT DISTINCT codigo_material FROM material_denominaciones);

-- Top 10 materiales con más aliases (para verificar carga)
SELECT codigo_material, COUNT(*) as total_aliases
FROM material_denominaciones
GROUP BY codigo_material
ORDER BY total_aliases DESC
LIMIT 10;
```

---

## Resumen de Tablas

| Tabla | Rows iniciales | Crece | Propósito |
|-------|----------------|-------|-----------|
| materiales_validados | ~915 | 1x/semana (admin) | Fuente de verdad |
| material_denominaciones | ~1500-2000 | Diariamente | Aliases para matching |
| materiales_pendientes | 0 (se llena con uso) | Diariamente | Cola de revisión |
| precios_historicos | 0 (se llena con uso) | Continuamente | Data warehouse |

**Sin codigos_proveedores** — descartada porque con 500+ proveedores del país,
cada uno con su sistema de códigos, sería inmanejable de mantener.
Los aliases de texto escalan sin ese problema.
