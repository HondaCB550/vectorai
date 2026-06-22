# VectorAI v2 — Resumen Final de Arquitectura & Roadmap

**Fecha:** 21-22 de Junio 2026  
**Estado:** ✅ Arquitectura finalizada y documentada  
**Versión:** v2 - "Matching Inteligente con Data Warehouse"

---

## 📋 Índice de Documentos

| Documento | Contenido | Estado |
|-----------|-----------|--------|
| `arquitectura_v2_final.html` | Arquitectura completa, flujos, human-in-the-loop, flywheel | ✅ Listo |
| `SCHEMA_VECTORAI_v2.md` | Schema SQL, tablas, ejemplos, mapeo desde BD actual | ✅ Listo |
| `RESUMEN_FINAL_ARQUITECTURA_V2.md` | Este archivo. Resumen + roadmap | ✅ Listo |

---

## 🎯 Cambio Fundamental (v1 → v2)

### v1 (Lo que ESTABA mal)
```
Usuario carga PDFs
  ↓
Sistema compara proveedores A vs B vs C
  ↓
"Bonora tiene mejor precio"
  ✗ Ignora unidades
  ✗ No aprende de matches
  ✗ No soporta nuevos materiales
```

### v2 (Lo correcto)
```
Usuario carga PDFs
  ↓
Sistema matchea CONTRA BD interna de materiales
  ↓
"Esto es código 001-A, Baukraft cotiza en $150"
  ✓ Valida unidades (flags si mismatch)
  ✓ Aprende de cada match (equivalencias + precios)
  ✓ Nosotros alimentamos datos → mejora continua
  ✓ En 1-2 meses: 95% matching automático
```

---

## 🏗️ Arquitectura v2 — 6 Pilares

### Pilar 1: Dos Bases de Datos
```
materiales_validados (verificada)
  └─ 915 materiales iniciales (tuyos)
  └─ Crece con nuevos validados por nosotros
  └─ Fuente de verdad

materiales_pendientes (temporal)
  └─ Nuevos encontrados en PDFs
  └─ Nosotros los revisamos 1x/día
  └─ Validados → suben a materiales_validados
```

### Pilar 2: Códigos de Proveedores (95% confianza)
```
codigos_proveedores:
  ├─ Baukraft BK-4521 → código 001-A (Codo PVC)
  ├─ Bonora BON-0087 → código 001-A
  └─ Carosio CAR-789 → código 001-A

Cuando usuario sube PDF con "BK-4521":
  → Match automático, 95% confianza
  → Usuario ve: ✅ Confirmado
  → Sin revisión manual
```

### Pilar 3: Denominaciones con Alias
```
material_denominaciones:
  ├─ "Codo PVC 45-40mm" (principal)
  ├─ "Codo PVC A90 45"
  ├─ "Codo 45-40"
  └─ "Codo PVC rosca"

Todas apuntan al código 001-A
Fuzzy match permite encontrar incluso variantes mal escritas
```

### Pilar 4: Matching Multi-Nivel
```
NIVEL 1: Código de Proveedor (95%)
  └─ Búsqueda exacta en tabla codigos_proveedores
  └─ Si encuentra: ✅ Match automático

NIVEL 2: Denominación Fuzzy (70-90%)
  └─ Búsqueda en material_denominaciones
  └─ Si score > 85: ⚠️ Usuario revisa

NIVEL 3: Agrupamiento IA (60-85%)
  └─ IA agrupa pendientes entre sí
  └─ "¿Estos 3 ítems son lo mismo?" (91% confianza)

NIVEL 4: Sin Match (0%)
  └─ Va a materiales_pendientes
  └─ Nosotros decidimos mañana
```

### Pilar 5: Human in the Loop (Nosotros)
```
Diariamente:
  ├─ Revisamos materiales_pendientes
  ├─ IA ya los agrupó por categoría
  ├─ Para cada grupo: crear nuevo / linkear a existente / rechazar
  ├─ Validamos + subimos a materiales_validados
  └─ 15 min de trabajo

Proactivamente (cada semana):
  ├─ Pedimos presupuestos a otros corralones
  ├─ Los cargamos en nuestro sistema
  ├─ Descubrimos códigos nuevos
  ├─ Validamos y agregamos a BD
  └─ El sistema mejora sin esperar a usuarios
```

### Pilar 6: Flywheel de Mejora (1-2 meses bootstrapping)
```
SEMANA 1:
  Matching: ~70% automático

SEMANAS 2-4 (Nosotros alimentamos datos):
  Cargamos presupuestos de otros corralones
  Descubrimos 50-100 códigos nuevos
  Matching: ~85% automático

SEMANAS 5-8 (Refinamiento denominaciones):
  Alias mejora, pendientes se resuelven
  Matching: ~90% automático

SEMANAS 9-10 (Falsos positivos):
  Ajustes, validaciones
  Matching: ~95% automático

DESPUÉS (Operación normal):
  Usuarios + datos propios = ciclo positivo
  ~95% matching automático
```

---

## 📊 Tablas Supabase (5 Principales)

### 1. materiales_validados
```sql
codigo (PK)           -- 001-A, 002-B, etc.
categoria             -- Tubería PVC, Herrajes, etc.
denominacion_principal -- Codo PVC A90 45-40mm
descripcion           -- Detalle técnico
especificaciones      -- JSON: {norma, diametro, etc.}
marcas_disponibles    -- JSON array: ["Marca A", "Marca B"]
unidades_posibles     -- JSON array: [{unidad, descripcion, equivalencia}]
confianza_matching    -- 95 (confiable para auto-match)
validado_por          -- Email o "sistema"
created_at, updated_at
```

### 2. material_denominaciones
```sql
codigo_material       -- FK a materiales_validados
denominacion         -- Alias encontrado
origen                -- "usuario_baukraft", "pdf_bonora"
confianza             -- 98 (found 50 times), 87 (found 12 times)
frecuencia_encontrada -- Contador de apariciones
```

### 3. codigos_proveedores (LA MÁGICA)
```sql
proveedor             -- Baukraft, Bonora, Carosio
codigo_proveedor      -- BK-4521, BON-0087, CAR-789
codigo_material       -- FK a materiales_validados (001-A)
marca_asignada        -- Marca A, Marca B
confianza             -- 95 (validado)
UNIQUE (proveedor, codigo_proveedor)
```

### 4. materiales_pendientes
```sql
descripcion_original  -- Lo que encontramos en el PDF
codigo_proveedor      -- Si lo tiene
proveedor             -- Baukraft, Bonora, etc.
categoria_sugerida    -- Aislantes, Pinturas (IA)
confianza_ia          -- 78, 91, etc.
agrupado_con          -- JSON array de otros IDs similares
estado                -- PENDIENTE, VALIDADO, RECHAZADO
```

### 5. precios_historicos (DATA WAREHOUSE)
```sql
proveedor             -- Baukraft, Bonora, etc.
codigo_material       -- 001-A (si es validado)
marca                 -- Marca A, Marca B
unidad                -- UNIDAD, CAJA_1000, BOLSA_500
precio                -- 150.00, 2.50, 450.00
cantidad              -- Para unidades múltiples
pdf_origen            -- Referencia al PDF de origen
created_at            -- Fecha del cotización
```

**Nota:** precios_historicos crece indefinidamente. Es el "oro" para análisis futuros (tendencias, recomendaciones, trading floor).

---

## 🔧 Flujo del Usuario (En la Plataforma)

```
1. Usuario sube PDFs
   └─ "Baukraft.pdf", "Bonora.pdf", "Carosio.pdf"

2. Sistema procesa automáticamente
   ├─ Extrae items de cada PDF
   ├─ Matchea contra materiales_validados
   ├─ Items sin match → llama IA para agrupamiento
   └─ Genera vista interactiva

3. Usuario ve 3 grupos:
   
   ✅ MATCHES AUTOMÁTICOS (código de proveedor)
      "Baukraft BK-4521" → 001-A (Codo PVC)
      Confianza 95%, sin revisar
      
   ⚠️ MATCHES DUDOSOS (denominación similar)
      "Acero construcción 10mm" → ¿002-A, 002-B ó 002-C?
      Usuario elige o busca
      
   ❌ SIN MATCH (no está en base)
      "Aislante XYZ espuma 5cm" (Carosio)
      IA sugiere: ¿Agrupado con Bonora?
      [✓ Agrupar] [✗ Son distintos]

4. Usuario confirma
   └─ [Confirmar análisis]

5. Sistema guarda automáticamente
   ├─ Equivalencias (proveedor → material validado)
   ├─ Nuevos materiales a pendientes
   ├─ Precios en histórico
   └─ Comparativa completada
```

---

## 👥 Flujo Nuestro: Human in the Loop

```
CADA DÍA (15 min):

Dashboard Admin:
  "47 nuevos items en materiales_pendientes"
  
Agrupados por IA:
  • Grupo A: Tornillos (12 items, 91% confianza)
  • Grupo B: Aislantes (8 items, 78% confianza)
  • Sin agrupar: 24 items

Para cada grupo:
  [✓] Crear como nuevo
  [✓] Linkear a uno existente
  [✓] Rechazar
  [✓] Esperar más datos

Resultado:
  └─ Items validados suben a materiales_validados
  └─ Próximos usuarios: mejor matching
```

---

## 📈 Estrategia de Crecimiento (1-2 meses)

```
SEMANA 1: MVP Launch
├─ BD: 915 materiales (tuyos)
├─ Códigos: Baukraft, Bonora, Carosio (80% coverage)
└─ Usuarios: empiezan a subir PDFs
   Matching esperado: ~70% automático

SEMANAS 2-4: Data Feeding
├─ ACCIÓN: Pedimos presupuestos a otros corralones
│  ├─ Zona Norte, Zona Sur, Zona Oeste
│  └─ Cargamos nosotros en el sistema
├─ Descubrimos: códigos nuevos, denominaciones, patrones
├─ Validamos + agregamos a tabla codigos_proveedores
└─ Resultado: ~85% matching automático

SEMANAS 5-8: Refinamiento
├─ ACCIÓN: Analizamos denominaciones encontradas
│  └─ "Codo PVC", "Codo 45-40", "Codo A90" → todas 001-A
├─ Agregamos aliases a material_denominaciones
├─ Re-procesamos pendientes con nuevos aliases
└─ Resultado: ~90% matching automático

SEMANAS 9-10: Fixing
├─ ACCIÓN: Corregimos falsos positivos
├─ Ajustamos umbrales, validaciones
└─ Resultado: ~95% matching automático

DESPUÉS: Operación Normal
├─ Usuarios suben PDFs → sistema casi perfecto
├─ Nosotros suben datos → sistema mejora
├─ Nuevos proveedores → nuevos códigos
└─ Tabla codigos_proveedores crece exponencialmente
```

---

## 🚨 Riesgos Mitigados

| Riesgo | Mitigación |
|--------|-----------|
| Colisión de códigos | UNIQUE (proveedor, codigo_proveedor) |
| False positives en IA | Umbral alto (>85%), usuario revisa |
| Tabla denominaciones crece mucho | Índices, limpiar duplicados |
| Bootstrapping lento | Nosotros cargamos datos propios |
| PDF duplicado | Detectar hash del PDF |

---

## 📋 Endpoints (MVP)

### Para Usuarios
- `POST /analizar-pdf-con-codigos` — Procesa PDF, retorna análisis
- `POST /confirmar-analisis` — Guarda equivalencias + precios
- `POST /resolver-match-dudoso` — Usuario elige código
- `POST /confirmar-agrupamiento` — Agrupa ítems similares
- `GET /comparativas` — Lista análisis del usuario
- `GET /comparativas/{id}` — Detalle de uno

### Para Nosotros (Admin)
- `GET /admin/materiales-pendientes` — Items por revisar
- `POST /admin/procesar-pendiente` — Crear/linkear/rechazar
- `POST /admin/agregar-codigo-proveedor` — Mapear nuevo código
- `GET /admin/codigos-por-validar` — Códigos encontrados
- `GET /admin/analytics` — KPIs

---

## 🎬 Roadmap Implementación

### FASE 1: Schema + Datos (1-2 semanas)
```
1. Crear tablas en Supabase
2. Migrar 915 materiales desde tu BD actual
3. Mapear códigos Baukraft, Bonora, Carosio
4. Llenar material_denominaciones con aliases básicos
5. ✅ BD lista para procesar PDFs
```

### FASE 2: Backend (2-3 semanas)
```
1. Implementar /analizar-pdf-con-codigos
   ├─ Extracción de PDF
   ├─ Matching 4 niveles
   └─ Generación de vista interactiva
2. Implementar /confirmar-analisis
   ├─ Guardar equivalencias
   ├─ Guardar precios históricos
   └─ Limpieza de análisis >48h (trigger)
3. Endpoints admin (listados, procesamiento)
4. ✅ Backend listo
```

### FASE 3: Frontend (2-3 semanas)
```
1. Página de upload de PDFs
2. Vista interactiva con 3 grupos
3. Modales para resolver matches dudosos
4. Admin dashboard para revisar pendientes
5. ✅ Frontend listo
```

### FASE 4: Testing + Launch (1 semana)
```
1. Load testing (múltiples PDFs simultáneos)
2. Testing de matching accuracy
3. Validación de datos con algunos usuarios beta
4. ✅ MVP en producción
```

### FASE 5: Bootstrapping (1-2 meses)
```
1. Cargamos presupuestos propios
2. Descubrimos códigos nuevos
3. Refinamos denominaciones
4. Corregimos falsos positivos
5. ✅ Sistema robusto al 95%
```

---

## 📊 Configuración de IA

| Nivel | Herramienta | Uso | Confianza |
|-------|-------------|-----|-----------|
| 1 (Códigos) | FUSI (lo tienes) | Matching exacto | 95% |
| 2 (Denominaciones) | FUSI o Fuzzy | Similitud de texto | 70-90% |
| 3 (Agrupamiento) | Claude/GPT-4 | "¿Estos 3 son lo mismo?" | 60-85% |

**Prompt para Nivel 3:**
```
¿Estos 3 ítems describen el mismo producto?
- Item 1: {desc1}
- Item 2: {desc2}  
- Item 3: {desc3}

Responde: {si|no|probable} + confianza (0-100) + razón
```

---

## 🎯 Decisiones Clave Tomadas

1. **Usuario NO crea materiales** — Sistema agrega automáticamente a pendientes, nosotros validamos
2. **Codes de proveedores son "ancla"** — 95% confianza automática, sin revisar
3. **Data warehouse no negociable** — precios_historicos crece indefinidamente, base para futuros negocios
4. **Human in the Loop diario, no bloqueador** — Nosotros revisamos, pero no bloquea a usuarios
5. **Bootstrapping de 1-2 meses es normal** — Esperamos mejorar día a día, no es perfecto día 1
6. **Nosotros alimentamos datos propios** — No esperamos solo a usuarios
7. **Flywheel: más datos → mejor matching → más usuarios → más datos**

---

## 📌 Próximos Pasos Inmediatos

1. **Crear schema en Supabase**
   - Ejecutar SQL para las 5 tablas
   - Crear índices
   - RLS (si aplica)

2. **Migrar tus 915 materiales**
   - Script Python para importar desde Excel
   - Validar datos
   - Verificar conteos

3. **Mapear códigos de proveedores**
   - Baukraft: BK-4521 → 001-A, etc.
   - Bonora: BON-0087 → 001-A, etc.
   - Carosio: CAR-789 → 001-A, etc.

4. **Preparar primeros endpoints**
   - /analizar-pdf-con-codigos
   - /confirmar-analisis

5. **Testing interno**
   - Subir algunos PDFs tuyos
   - Verificar matching accuracy
   - Ajustar umbrales de confianza

---

## 📁 Archivos de Referencia

Todos en `C:\Pablo\presupuestor\`:
- `arquitectura_v2_final.html` — Arquitectura completa (visual)
- `SCHEMA_VECTORAI_v2.md` — Schema SQL + ejemplos + migración
- `RESUMEN_FINAL_ARQUITECTURA_V2.md` — Este archivo

---

## ✅ Estado Final

| Componente | Estado | Notas |
|-----------|--------|-------|
| Arquitectura | ✅ Finalizada | Documentada en HTML |
| Schema | ✅ Definido | Documentado en MD |
| Roadmap | ✅ Claro | 5 fases, 8-12 semanas |
| Decisiones clave | ✅ Tomadas | Sin volver atrás |
| Documentación | ✅ Completa | 3 archivos HTML + MD |
| Implementación | ⏳ Por hacer | Empezar con schema + migración |

---

## 🚀 Lanzamiento

**Cuando esté listo:**
1. Schema en Supabase ✓
2. 915 materiales migrados ✓
3. Códigos mapeados (80% coverage) ✓
4. Endpoints básicos funcionando ✓
5. Frontend de upload + vista interactiva ✓
6. Admin dashboard ✓

**Entonces:** MVP en producción, primeros usuarios, bootstrapping de 1-2 meses.

---

**Documento guardado:** 22 Junio 2026  
**Próxima revisión:** Después de implementar schema + primeros endpoints

