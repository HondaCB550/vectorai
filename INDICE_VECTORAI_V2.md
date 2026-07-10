# Vectorai v2 — Índice Maestro de Documentación

**Última actualización:** 22 Junio 2026  
**Decisión clave:** Sin codigos_proveedores — matching 100% por texto (aliases)  
**Estado:** ✅ Arquitectura finalizada y documentada

---

## ¿Por dónde empiezo?

### Para entender la arquitectura en 10 minutos
→ Lee: [`RESUMEN_FINAL_ARQUITECTURA_V2.md`](RESUMEN_FINAL_ARQUITECTURA_V2.md)
- Por qué v2 vs v1
- Los 4 pilares
- Flujo de usuario y flujo admin
- Roadmap de implementación

### Para implementar (SQL + código)
→ Lee: [`SCHEMA_VECTORAI_v2.md`](SCHEMA_VECTORAI_v2.md)
- SQL exacto para las 4 tablas
- Script de migración completo
- Lógica de matching en Python
- Queries de verificación

---

## Estructura de Documentos

```
presupuestor/
├── INDICE_VECTORAI_V2.md           ← TÚ ESTÁS AQUÍ
├── RESUMEN_FINAL_ARQUITECTURA_V2.md (arquitectura + roadmap)
└── SCHEMA_VECTORAI_v2.md           (implementación técnica)
```

---

## Roadmap de Implementación

### Esta semana: Schema + Datos
```
1. Ejecutar SQL en Supabase (4 tablas) — 30 min
2. Correr script de migración (915 materiales) — 15 min
3. Verificar con queries — 15 min
→ BD lista para procesar PDFs
```

### Semana 1-2: Backend
```
1. POST /analizar-pdf (fuzzy match texto → material_denominaciones)
2. POST /confirmar-analisis (guarda aliases + precios)
3. GET/POST /admin/pendientes (revisar sin-match)
→ API funcional
```

### Semana 2-4: Frontend
```
1. Vista upload de PDFs
2. Vista 3 grupos: automático / dudoso / sin match
3. Admin dashboard (revisar pendientes)
→ MVP en producción
```

### Mes 1-2: Bootstrapping
```
Nosotros cargamos PDFs propios proactivamente
Revisamos pendientes 15 min/día
Meta: 90%+ matching automático
```

---

## Los 4 Pilares (resumen rápido)

### 1. BD Central Verificada
- `materiales_validados`: 915 materiales iniciales, fuente de verdad
- `materiales_pendientes`: textos sin match, cola de revisión diaria

### 2. Aliases de Texto (el corazón)
- `material_denominaciones`: todas las formas de decir lo mismo
- "Codo PVC 45-40mm", "Codo A90 45", "Codo 45-40" → todos 001-A
- Crece con cada PDF procesado
- Una sola tabla para todos los proveedores del país

### 3. Matching de Texto (2 niveles)
- Score ≥ 85 → automático
- Score 60-84 → usuario elige
- Score < 60 → sin match, va a pendientes

### 4. Human in the Loop + Flywheel
- 15 min/día revisando pendientes
- Cada alias validado mejora el sistema para siempre
- Más PDFs → más aliases → mejor matching → menos trabajo

---

## Decisiones Clave

| Decisión | Por qué |
|----------|---------|
| Sin codigos_proveedores | 500+ proveedores, cada uno con sus propios códigos → inmanejable. Los aliases de texto son universales. |
| Aliases como fuente de matching | Un texto confirmado sirve para cualquier proveedor del país que lo use. |
| Data warehouse de precios | precios_historicos crece indefinidamente — activo de largo plazo. |
| Human in the Loop no bloquea | Pendientes se procesan a la mañana; el usuario ya terminó su análisis. |
| Nosotros alimentamos datos | No esperamos solo a usuarios — cargamos PDFs propios proactivamente. |

---

## Tablas

| Tabla | Rows iniciales | Propósito |
|-------|----------------|-----------|
| materiales_validados | ~915 | Fuente de verdad |
| material_denominaciones | ~1500 | Aliases para matching (el corazón) |
| materiales_pendientes | 0 | Cola de revisión diaria |
| precios_historicos | 0 | Data warehouse (crece para siempre) |

---

## Checklist de Implementación

- [ ] Leer RESUMEN_FINAL_ARQUITECTURA_V2.md completo
- [ ] Leer SCHEMA_VECTORAI_v2.md (SQL + script de migración)
- [ ] Ejecutar SQL de las 4 tablas en Supabase
- [ ] Correr script de migración desde master_materiales.json
- [ ] Verificar conteos (915 materiales, ~1500 aliases)
- [ ] Implementar POST /analizar-pdf
- [ ] Implementar POST /confirmar-analisis
- [ ] Implementar endpoints admin
- [ ] Construir vista frontend 3 grupos
- [ ] Testing con PDFs reales de Baukraft/Bonora/Carosio
- [ ] Ajustar umbrales de confianza
- [ ] MVP en producción

---

## Ejemplo: cómo crece el sistema

**Semana 1 — PDF de Baukraft:**
```
PDF dice: "Codo PVC 45-40mm"
No hay alias aún → va a dudoso (score 72 contra denominacion_principal)
Usuario confirma → se agrega alias "codo pvc 45-40mm" → 001-A
```

**Semana 1 — PDF de Bonora (mismo día):**
```
PDF dice: "Codo PVC A90 45"
Fuzzy match contra aliases conocidos: score 81 (dudoso)
Usuario confirma → se agrega alias "codo pvc a90 45" → 001-A
```

**Semana 2 — PDF de corralón del interior:**
```
PDF dice: "Codo 45-40"
Fuzzy match: "codo pvc 45-40mm" score 88 → automático
Sin revisión manual necesaria.
```

**Mes 2 — cualquier PDF del país:**
```
"Codo PVC 45-40mm" → match instantáneo, score 100
"Codo 45-40"       → match automático, score 88
"Codo A90 45"      → match automático, score 91
```

---

**Documento creado:** 22 de Junio de 2026  
**Versión:** 2.0 — sin codigos_proveedores
