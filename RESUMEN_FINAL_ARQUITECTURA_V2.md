# VectorAI v2 — Resumen Final de Arquitectura & Roadmap

**Fecha:** 22 de Junio 2026  
**Actualizado:** 22 de Junio 2026 — decisión: sin codigos_proveedores, solo texto  
**Versión:** v2 - "Matching por Alias de Texto"

---

## 📋 Índice de Documentos

| Documento | Contenido | Estado |
|-----------|-----------|--------|
| `SCHEMA_VECTORAI_v2.md` | Schema SQL, tablas, ejemplos, migración | ✅ Listo |
| `RESUMEN_FINAL_ARQUITECTURA_V2.md` | Este archivo. Resumen + roadmap | ✅ Listo |
| `INDICE_VECTORAI_V2.md` | Índice maestro y roadmap de lectura | ✅ Listo |

---

## 🎯 Cambio Fundamental (v1 → v2)

### v1 (Lo que ESTABA mal)
```
Usuario carga PDFs
  ↓
Sistema compara proveedores A vs B vs C texto-a-texto
  ↓
"Bonora tiene mejor precio"
  ✗ No hay BD central de materiales
  ✗ No aprende de matches anteriores
  ✗ No escala con nuevos proveedores
```

### v2 (Lo correcto)
```
Usuario carga PDFs
  ↓
Sistema matchea texto del PDF contra BD interna de aliases
  ↓
"Esto es Codo PVC 45-40mm (001-A), Baukraft cotiza en $150"
  ✓ Una sola BD central para todos los proveedores del país
  ✓ Aprende alias nuevos con cada PDF que procesa
  ✓ En 1-2 meses: 90%+ matching automático
```

---

## 🏗️ Arquitectura v2 — 4 Pilares

### Pilar 1: BD Central Verificada
```
materiales_validados (la fuente de verdad)
  └─ 915 materiales iniciales
  └─ denominacion_principal: nombre canónico
  └─ Crece con nuevos validados por nosotros
  └─ Una sola BD para TODOS los proveedores del país

materiales_pendientes (cola de revisión)
  └─ Descripciones de PDFs que no matchearon
  └─ Nosotros las revisamos 1x/día
  └─ Validadas → suben a materiales_validados + nuevo alias
```

### Pilar 2: Aliases de Texto (El Corazón)
```
material_denominaciones:
  ├─ "Codo PVC 45-40mm"    → 001-A  (bautizado por Baukraft)
  ├─ "Codo PVC A90 45"     → 001-A  (lo llama Bonora)
  ├─ "Codo 45-40"          → 001-A  (versión corta de Carosio)
  └─ "Codo PVC rosca"      → 001-A  (corralón local del interior)

Cada vez que un usuario confirma un match → ese texto queda como alias.
La próxima vez que aparece en cualquier PDF de cualquier proveedor → match automático.
```

**Por qué no usamos códigos de proveedor:**
Con 500+ proveedores de todo el país, cada uno tiene su propio sistema de códigos.
Mantener una tabla `codigos_proveedores` sería enorme y de difícil mantenimiento.
Los aliases de texto son universales: sirven para cualquier proveedor que use
esa descripción, sin importar sus códigos internos.

### Pilar 3: Matching de Texto (2 Niveles)
```
NIVEL 1: Match exacto o fuzzy alto (score ≥ 85)
  └─ Texto del PDF → fuzzy contra material_denominaciones
  └─ Si score ≥ 85: ✅ Match automático
  └─ Usuario ve el resultado, puede corregir

NIVEL 2: Sin Match (score < 60)
  └─ Va a materiales_pendientes
  └─ Nosotros revisamos y agregamos alias correcto
  └─ Próximo PDF con esa descripción: match automático

ZONA GRIS (score 60-84): ⚠️ Usuario elige
  └─ Sistema muestra top 3 candidatos
  └─ Usuario confirma → queda como alias
```

### Pilar 4: Human in the Loop + Flywheel
```
Diariamente (15 min):
  ├─ Revisamos materiales_pendientes
  ├─ Para cada pendiente: linkear a existente / crear nuevo
  ├─ Validado → sube a materiales_validados
  └─ Ese alias queda disponible para todos

Proactivamente (1x/semana):
  ├─ Cargamos presupuestos de otros corralones
  ├─ El sistema descubre nuevas formas de nombrar materiales
  └─ Sistema mejora sin esperar a que lleguen usuarios

FLYWHEEL:
  Más PDFs procesados → más aliases en la BD → mejor matching automático
  → menos trabajo manual → más usuarios → más PDFs → ...
```

---

## 📊 Tablas Supabase (4 Tablas)

### 1. materiales_validados
```sql
codigo (PK)              -- 001-A, 002-B, etc.
categoria                -- Tubería PVC, Herrajes, etc.
denominacion_principal   -- Nombre canónico
descripcion              -- Detalle técnico opcional
especificaciones         -- JSON: norma, diámetro, etc.
marcas_disponibles       -- JSON array: ["Marca A", "Marca B"]
unidades_posibles        -- JSON array: [{unidad, descripcion, equivalencia}]
validado_por             -- Email o "sistema"
created_at, updated_at
```

### 2. material_denominaciones
```sql
codigo_material          -- FK a materiales_validados
denominacion             -- Texto exacto encontrado en PDF
origen                   -- "pdf_baukraft", "usuario_confirmacion", "admin"
confianza                -- 0-100 (sube con cada aparición)
frecuencia_encontrada    -- Contador: cuántas veces apareció
created_at
```
**UNIQUE (codigo_material, denominacion)** — un texto → un material.

### 3. materiales_pendientes
```sql
descripcion_original     -- Lo que encontramos en el PDF
proveedor                -- Baukraft, Bonora, corralon_norte_neuquen, etc.
categoria_sugerida       -- Aislantes, Pinturas (sugerido por el sistema)
agrupado_con             -- JSON array de IDs similares (misma descripción en otros PDFs)
estado                   -- PENDIENTE, VALIDADO, RECHAZADO
pdf_origen               -- Referencia al PDF
created_at
```

### 4. precios_historicos (DATA WAREHOUSE)
```sql
proveedor                -- Nombre del proveedor
codigo_material          -- FK materiales_validados (si hay match)
codigo_pendiente         -- FK materiales_pendientes (si no hay match aún)
marca                    -- Marca del ítem
unidad                   -- UNIDAD, CAJA_1000, METRO, etc.
precio                   -- Precio sin IVA
pdf_origen               -- Hash o referencia al PDF original
created_at               -- Fecha de la cotización
```
**Nota:** precios_historicos crece indefinidamente. Es el activo de largo plazo
(análisis de tendencias, comparativas históricas, inteligencia de mercado).

---

## 🔧 Flujo del Usuario

```
1. Usuario sube PDFs
   └─ "Baukraft_junio.pdf", "Bonora_junio.pdf", "Carosio_junio.pdf"

2. Sistema procesa automáticamente
   ├─ Extrae ítems de cada PDF (texto + precio + unidad)
   ├─ Para cada ítem: fuzzy match contra material_denominaciones
   └─ Genera vista interactiva con 3 grupos

3. Usuario ve 3 grupos:

   ✅ MATCHES AUTOMÁTICOS (score ≥ 85)
      "Codo PVC 45-40mm"  →  001-A  (alias conocido, confianza 97)
      Sin acción requerida, confirmado automáticamente

   ⚠️ MATCHES DUDOSOS (score 60-84)
      "Codo presión 45mm" →  ¿001-A ó 001-B?  (score 71)
      Sistema muestra top 3 candidatos, usuario elige

   ❌ SIN MATCH (score < 60)
      "Placa OSB 18mm E1 Finsa"
      El sistema pregunta: ¿querés agregar al sistema o saltear?

4. Usuario confirma
   └─ [Confirmar análisis]

5. Sistema guarda:
   ├─ Alias nuevo por cada match confirmado → material_denominaciones
   ├─ Ítems sin match → materiales_pendientes
   ├─ Todos los precios → precios_historicos
   └─ Comparativa completada para el usuario
```

---

## 👥 Flujo Admin: Human in the Loop

```
CADA DÍA (15 min):

Dashboard Admin muestra:
  "23 nuevos ítems en materiales_pendientes"
  "8 agrupados por descripción similar"

Para cada pendiente:
  ┌──────────────────────────────────────────┐
  │ "Placa OSB 18mm E1 Finsa" (Baukraft)    │
  │ Similar a: "OSB 18mm" (Bonora, 3 veces) │
  │                                          │
  │ [Linkear a OSB-003-A]                    │
  │ [Crear material nuevo]                   │
  │ [Rechazar - es duplicado]                │
  └──────────────────────────────────────────┘

Al linkear:
  → Se agrega "Placa OSB 18mm E1 Finsa" como alias de OSB-003-A
  → Próxima vez que aparezca: match automático (score 100)
```

---

## 📈 Flywheel de Mejora (Estimado)

```
SEMANA 1 (lanzamiento):
  BD inicial: 915 materiales, aliases básicos
  Matching esperado: ~60% automático (solo aliases que tenemos)

SEMANAS 2-4 (primeros usuarios + carga propia):
  Cada PDF que entra descubre nuevos aliases
  Nosotros revisamos pendientes 15 min/día
  Matching: ~75% automático

SEMANAS 5-8 (refinamiento):
  Aliases crecieron: las variantes más comunes ya están
  Re-procesamos pendientes viejos con nuevos aliases
  Matching: ~85% automático

SEMANAS 9-12 (madurez):
  Los proveedores grandes están casi cubiertos
  Matching: ~90%+ automático

LARGO PLAZO:
  Nuevos proveedores = nuevos alias → se aprende en 1 PDF
  Sistema prácticamente autónomo
```

---

## 🚨 Riesgos y Mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| False positives (match incorrecto) | Zona gris 60-84 siempre la revisa el usuario |
| Alias ambiguos (misma descripción, distinto material) | Detección por UNIQUE constraint; se marca para revisión |
| Tabla denominaciones crece mucho | Índice de texto + limpiar aliases con frecuencia_encontrada = 1 |
| Bootstrapping lento | Nosotros cargamos PDFs propios proactivamente |
| PDF duplicado | Hash del PDF antes de procesar |

---

## 📋 Endpoints (MVP)

### Para Usuarios
- `POST /analizar-pdf` — Procesa PDF, retorna análisis con 3 grupos
- `POST /confirmar-analisis` — Guarda aliases + precios históricos
- `POST /resolver-match-dudoso` — Usuario elige el material correcto
- `GET /comparativas` — Lista análisis del usuario
- `GET /comparativas/{id}` — Detalle de uno

### Para Admin
- `GET /admin/pendientes` — Ítems pendientes de validación
- `POST /admin/validar-pendiente` — Linkear a existente / crear nuevo / rechazar
- `GET /admin/analytics` — KPIs: % automático, pendientes, aliases totales

---

## 🎬 Roadmap de Implementación

### FASE 1: Schema + Datos (1 semana)
```
1. Crear 4 tablas en Supabase (SQL en SCHEMA_VECTORAI_v2.md)
2. Migrar 915 materiales desde master_materiales.json
3. Cargar aliases iniciales (ITEM + DETALLE de cada material como primer alias)
4. ✅ BD lista para procesar PDFs
```

### FASE 2: Backend (2-3 semanas)
```
1. POST /analizar-pdf
   ├─ Extracción de texto del PDF
   ├─ Fuzzy match contra material_denominaciones
   └─ Clasificar en 3 grupos (auto / dudoso / sin match)
2. POST /confirmar-analisis
   ├─ Insertar alias confirmados
   ├─ Mover sin-match a materiales_pendientes
   └─ Guardar precios en precios_historicos
3. Endpoints admin (listado pendientes + validar)
4. ✅ Backend listo
```

### FASE 3: Frontend (2-3 semanas)
```
1. Vista upload de PDFs
2. Vista de 3 grupos con acciones por ítem
3. Admin dashboard (revisar pendientes)
4. ✅ Frontend listo
```

### FASE 4: Testing + Launch (1 semana)
```
1. Accuracy de matching con PDFs reales de Baukraft/Bonora/Carosio
2. Ajustar umbrales (85 auto / 60-84 dudoso / <60 sin match)
3. Beta con algunos usuarios
4. ✅ MVP en producción
```

### FASE 5: Bootstrapping (1-2 meses)
```
1. Cargar PDFs propios proactivamente cada semana
2. Revisar pendientes 15 min/día
3. Meta: 90%+ matching automático
```

---

## 🎯 Decisiones Clave

1. **Sin codigos_proveedores** — Con 500+ proveedores del país, cada uno con su sistema de códigos, sería inmanejable. Los aliases de texto son universales.
2. **Alias de texto son el corazón** — Cada descripción confirmada queda para siempre en la BD y sirve para cualquier proveedor.
3. **Data warehouse no negociable** — precios_historicos crece indefinidamente; es la base para análisis futuros.
4. **Human in the Loop no bloquea** — Pendientes se procesan a la mañana, no bloquean al usuario.
5. **Bootstrapping activo** — Nosotros cargamos datos propios, no esperamos solo a usuarios.
6. **Usuario NO crea materiales** — Solo confirma matches. Nosotros validamos los pendientes.

---

## 📌 Próximos Pasos Inmediatos

1. **Crear schema en Supabase** — Ejecutar SQL para las 4 tablas (ver SCHEMA_VECTORAI_v2.md)
2. **Migrar materiales** — Script Python desde master_materiales.json → materiales_validados
3. **Cargar aliases iniciales** — Para cada material, el ITEM y DETALLE como primer alias
4. **Implementar /analizar-pdf** — Fuzzy match texto del PDF contra material_denominaciones
5. **Testing con PDFs reales** — Ajustar umbral de confianza

---

**Documento guardado:** 22 Junio 2026  
**Próxima revisión:** Después de implementar schema + primer endpoint
