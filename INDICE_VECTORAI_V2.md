# 📚 VectorAI v2 — Índice Maestro de Documentación

**Última actualización:** 22 Junio 2026  
**Estado:** ✅ Arquitectura finalizada y documentada

---

## 🎯 ¿Por dónde empiezo?

### Para entender la arquitectura en 10 minutos
👉 Lee: [`RESUMEN_FINAL_ARQUITECTURA_V2.md`](RESUMEN_FINAL_ARQUITECTURA_V2.md)
- Cambio v1 → v2
- 6 pilares clave
- Flowcharts de usuario y admin
- Roadmap de implementación

### Para ver todo visualmente
👉 Abre: [`arquitectura_v2_final.html`](arquitectura_v2_final.html) (en navegador)
- Diagramas ASCII
- Explicaciones detalladas
- Casos de uso
- Flywheel de mejora

### Para implementar (developers)
👉 Lee: [`SCHEMA_VECTORAI_v2.md`](SCHEMA_VECTORAI_v2.md)
- SQL exacto para cada tabla
- Ejemplos de filas con datos reales
- Mapeo desde tu BD actual
- Script Python de migración
- Validaciones y índices

---

## 📋 Estructura de Documentos

```
presupuestor/
├── INDICE_VECTORAI_V2.md ← TÚ ESTÁS AQUÍ
├── RESUMEN_FINAL_ARQUITECTURA_V2.md (read-me ejecutivo)
├── arquitectura_v2_final.html (guía visual)
├── SCHEMA_VECTORAI_v2.md (implementación técnica)
└── pendientes_v2_arquitectura.html (versión anterior, solo referencia)
```

---

## 🎬 Roadmap de Lectura

### Día 1: Entender
```
1. RESUMEN_FINAL_ARQUITECTURA_V2.md (20 min)
2. arquitectura_v2_final.html (30 min)
3. SCHEMA_VECTORAI_v2.md - primeras secciones (15 min)
→ Ya entiendes qué es VectorAI v2
```

### Día 2-3: Implementación
```
1. SCHEMA_VECTORAI_v2.md - SQL completo (30 min)
2. Script de migración desde tu BD (15 min)
3. Crear tablas en Supabase (30 min)
→ Schema en Supabase listo
```

### Semana 1: Endpoints básicos
```
1. RESUMEN_FINAL_ARQUITECTURA_V2.md - sección Endpoints (10 min)
2. Implementar /analizar-pdf-con-codigos (8-12 horas)
3. Implementar /confirmar-analisis (4-6 horas)
→ Backend MVP funcional
```

### Semana 2-3: Frontend
```
1. Página de upload de PDFs
2. Vista interactiva con 3 grupos
3. Admin dashboard
→ MVP en producción
```

---

## 📌 Documentos Rápidos (Copy/Paste)

### SQL para crear todas las tablas
```sql
-- Ir a SCHEMA_VECTORAI_v2.md, sección "Tabla: materiales_validados"
-- Copiar bloques CREATE TABLE
-- Ejecutar en Supabase
```

### Script Python para migración
```python
# Ir a SCHEMA_VECTORAI_v2.md, sección "Cómo Migrar desde Tu Base Actual"
# Copiar script completo
# Ajustar rutas a tu CSV
# Ejecutar: python script.py
```

### Ejemplos de datos JSON
```json
// Ir a SCHEMA_VECTORAI_v2.md, sección "Campos Detallados"
// Buscar "especificaciones" o "unidades_posibles"
// Copy/paste estructura exacta
```

---

## 🎯 Las 5 Decisiones Clave

| Decisión | Por qué | Impacto |
|----------|---------|--------|
| **Usuario NO crea materiales** | Control de calidad, evita duplicados | Sistema más robusto |
| **Códigos de proveedores = 95% confianza** | No necesita revisión manual | Usuarios felices, matching rápido |
| **Data warehouse (precios_historicos)** | Base para futuros análisis | Escalabilidad a trading/consulting |
| **Human in the Loop diario** | Validamos pero no bloqueamos | Bootstrapping rápido de 1-2 meses |
| **Nosotros alimentamos datos** | No esperamos solo a usuarios | Sistema mejora incluso sin usuarios iniciales |

---

## 🏗️ Los 6 Pilares

### 1. Dos Bases de Datos
- `materiales_validados`: BD verificada (915 items iniciales)
- `materiales_pendientes`: Nuevos encontrados en PDFs

### 2. Códigos de Proveedores
- `codigos_proveedores`: Baukraft BK-4521 → 001-A
- Permite matching 95% automático

### 3. Denominaciones con Alias
- `material_denominaciones`: "Codo PVC", "Codo 45-40", "Codo A90" → todas 001-A
- Fuzzy match tolerante

### 4. Matching Multi-Nivel
- Nivel 1: Código (95%)
- Nivel 2: Denominación (70-90%)
- Nivel 3: IA agrupamiento (60-85%)
- Nivel 4: Sin match (0%)

### 5. Human in the Loop
- Nosotros revisamos pendientes 1x/día
- 15 min por día de trabajo
- Validamos y subimos a BD

### 6. Flywheel de Mejora
- Semana 1: 70% automático
- Mes 1: 85% automático
- Semana 6: 95% automático

---

## 🚀 Implementación (Orden)

```
FASE 1: Schema (1-2 semanas)
├─ Crear tablas en Supabase
├─ Migrar 915 materiales
├─ Mapear códigos (80% coverage)
└─ ✅ BD lista

FASE 2: Backend (2-3 semanas)
├─ POST /analizar-pdf-con-codigos
├─ POST /confirmar-analisis
├─ Endpoints admin
└─ ✅ APIs funcionales

FASE 3: Frontend (2-3 semanas)
├─ Upload PDFs
├─ Vista interactiva
├─ Admin dashboard
└─ ✅ UI completa

FASE 4: Testing (1 semana)
├─ Accuracy de matching
├─ Load testing
├─ Beta users
└─ ✅ MVP en producción

FASE 5: Bootstrapping (1-2 meses)
├─ Cargamos datos propios
├─ Descubrimos códigos nuevos
├─ Refinamos denominaciones
└─ ✅ Sistema robusto (95%)
```

---

## 🎬 Flujos Clave

### Flujo Usuario
```
1. Sube PDFs
2. Sistema matchea automáticamente
3. Revisa 3 grupos (automático, dudoso, sin match)
4. Confirma
5. Sistema guarda equivalencias + precios
```

### Flujo Nosotros (Diario)
```
1. Dashboard: "47 nuevos pendientes"
2. IA ya los agrupó por categoría
3. Para cada grupo: crear/linkear/rechazar
4. Validamos → suben a materiales_validados
5. Próximos usuarios: mejor matching
```

### Flujo Proactivo (Semanal)
```
1. Pedimos presupuestos a otros corralones
2. Los cargamos en nuestro sistema
3. Descubrimos códigos nuevos
4. Validamos → tabla codigos_proveedores
5. Sistema mejora sin usuarios iniciales
```

---

## 📊 Tablas Principales

| Tabla | Rows | Frecuencia | Rol |
|-------|------|-----------|-----|
| materiales_validados | ~915 | 1x/semana | BD central verificada |
| material_denominaciones | ~2000+ | Diaria | Aliases encontrados |
| codigos_proveedores | ~500+ | Continua | Mágica matching 95% |
| materiales_pendientes | ~100+ | Diaria | Nuevos temporales |
| precios_historicos | Millones | Continua | Data warehouse futuro |

---

## ✅ Checklist Pre-Implementación

- [ ] Leer RESUMEN_FINAL_ARQUITECTURA_V2.md completo
- [ ] Revisar arquitectura_v2_final.html (visual)
- [ ] Entender SCHEMA_VECTORAI_v2.md (tablas, campos, ejemplos)
- [ ] Exportar 915 materiales desde tu BD actual a CSV
- [ ] Preparar lista de códigos Baukraft/Bonora/Carosio
- [ ] Crear proyecto Supabase (o usar uno existente)
- [ ] Ejecutar SQL de tablas
- [ ] Correr script de migración
- [ ] Mapear códigos en tabla codigos_proveedores
- [ ] Verificar datos con queries
- [ ] Listo para implementar endpoints

---

## 🎓 Ejemplos Clave

### Ejemplo 1: Material con múltiples unidades
```json
{
  "codigo": "002-B",
  "categoria": "Herrajes",
  "denominacion_principal": "Tornillo #8x1\"",
  "marcas_disponibles": ["Marca A", "Marca B", "Marca China"],
  "unidades_posibles": [
    {"unidad": "UNIDAD", "descripcion": "1 tornillo", "equivalencia": 1},
    {"unidad": "CAJA_1000", "descripcion": "Caja 1000", "equivalencia": 1000},
    {"unidad": "BOLSA_500", "descripcion": "Bolsa 500", "equivalencia": 500}
  ]
}
```

### Ejemplo 2: Código de proveedor mágico
```
Baukraft PDF: "BK-4521" → $150
         ↓
System busca en codigos_proveedores
         ↓
Encuentra: proveedor=Baukraft, codigo_proveedor=BK-4521 → codigo_material=001-A
         ↓
✅ Match automático, 95% confianza
```

### Ejemplo 3: IA agrupando pendientes
```
Baukraft: "Tornillo #8x1 inox"
Bonora: "Tornillo #8x1"
Carosio: "Tornillo acero #8"
         ↓
IA: "Estos 3 probablemente sean lo mismo (91% confianza)"
         ↓
Usuario: [✓ Agrupar] o [✗ Son distintos]
```

---

## 🔧 Herramientas & Config

| Herramienta | Rol | Config |
|-------------|-----|--------|
| FUSI | Matching de código / denominación | Ya lo tienes |
| Claude/GPT-4 | IA agrupamiento de pendientes | Prompt incluido en SCHEMA |
| Supabase | BD central | Tablas + índices en SCHEMA |
| Python | Script migración | Copy/paste en SCHEMA |

---

## 📞 Support

Si hay duda:
1. Buscar en `RESUMEN_FINAL_ARQUITECTURA_V2.md` (más legible)
2. Buscar en `arquitectura_v2_final.html` (más visual)
3. Buscar en `SCHEMA_VECTORAI_v2.md` (más técnico)

Los 3 documentos cubren el 100% de VectorAI v2.

---

## 📌 Links Rápidos

- [📋 Resumen Ejecutivo](RESUMEN_FINAL_ARQUITECTURA_V2.md)
- [🎨 Arquitectura Visual](arquitectura_v2_final.html)
- [🛠️ Schema Técnico](SCHEMA_VECTORAI_v2.md)
- [📜 Documentación Anterior](pendientes_v2_arquitectura.html) (referencia)

---

## 🎯 Estado Actual

| Aspecto | Estado | Fecha |
|---------|--------|-------|
| Arquitectura | ✅ Finalizada | 21-22 Jun 2026 |
| Documentación | ✅ Completa | 22 Jun 2026 |
| Schema | ✅ Definido | 22 Jun 2026 |
| Roadmap | ✅ Claro | 22 Jun 2026 |
| Implementación | ⏳ Por empezar | Próximamente |

---

**Documento creado:** 22 de Junio de 2026  
**Versión:** 1.0  
**Siguientes pasos:** Crear schema en Supabase + migrar datos

