"use client";
import { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase";
import { esAdmin } from "@/lib/admin";
import Footer from "@/components/Footer";
import UserMenu from "@/components/UserMenu";
import Logo from "@/components/Logo";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Tipos ─────────────────────────────────────────────────────────────────────
type Alternativa = { codigo_material: string; denominacion: string; descripcion?: string; score: number };

type ItemAutomatico = {
  desc_prov: string;
  cod_prov: string;
  precio_sin_iva: number;
  precio_con_iva: number;
  cant: number;
  codigo_material: string;
  denominacion_matcheada: string;
  score: number;
  categoria: string;
  denominacion_principal: string;
  descripcion: string;
  alternativas: Alternativa[];
  item_id?: string;
  precio_sospechoso?: boolean;
  conversion?: string;
  unidad_ambigua?: boolean;
};

type ItemDudoso = ItemAutomatico & { codigo_elegido?: string };

// Sentinela para "ninguna alternativa corresponde": el ítem se confirma como
// sin match (va a materiales_pendientes) en vez de aprender un código erróneo.
const SIN_MATCH = "__sin_match__";

type ItemSinMatch = {
  desc_prov: string;
  cod_prov: string;
  precio_sin_iva: number;
  precio_con_iva: number;
  cant: number;
  item_id?: string;
};

type StatsProveedor = {
  total: number;
  automatico: number;
  dudoso: number;
  sin_match: number;
  pct_automatico: number;
};

type ResultadoProveedor = {
  automatico: ItemAutomatico[];
  dudoso: ItemDudoso[];
  sin_match: ItemSinMatch[];
  stats: StatsProveedor;
  iva_detectado: boolean;
  metodo_extraccion: string;
  n_items_extraidos: number;
};

type Precio = { precio_sin_iva: number; score: number; origen: string; cant: number };
type FilaComparativa = {
  cod_int: string;
  rubro: string;
  material: string;
  unidad: string;
  cant: number;
  precios: Record<string, Precio>;
  mejor_proveedor: string;
  ahorro: number;
  en_varios: boolean;
};

type ConfigProveedor = {
  iva_incluido: boolean;
  factor_iva: number;
  descuento_pct: number;
};

type Resultado = {
  comparativa_id: string;
  proveedores: string[];
  resultados: Record<string, ResultadoProveedor>;
  comparativo: FilaComparativa[];
  plan: string;
  usos_restantes: number | null;
  aliases_en_bd: number;
  config_proveedores: Record<string, ConfigProveedor>;
  errores?: { archivo: string; error: string }[];
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(v: number) {
  return `$ ${Math.round(v).toLocaleString("es-AR")}`;
}

// Precio a mostrar: el neto siempre es la base; "Con IVA" reconstruye el
// precio con el factor PROPIO de cada proveedor (nunca un factor uniforme,
// si no a los que ya cotizaron con IVA se les suma de nuevo).
function precioMostrado(neto: number, factorIva: number, conIva: boolean, descPct: number) {
  const iva  = conIva ? (factorIva || 1.105) : 1;
  const desc = descPct > 0 ? (1 - descPct / 100) : 1;
  return neto * iva * desc;
}

function pctDiferencia(precios: Record<string, { precio_sin_iva: number }>, cant: number): number {
  const vals = Object.values(precios).map((p) => p.precio_sin_iva * cant);
  if (vals.length < 2) return 0;
  const mn = Math.min(...vals), mx = Math.max(...vals);
  return mn > 0 ? Math.round(((mx - mn) / mn) * 100) : 0;
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 85 ? "text-green-700 bg-green-100" : score >= 70 ? "text-amber-700 bg-amber-100" : "text-red-700 bg-red-100";
  return <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${color}`}>{score.toFixed(0)}%</span>;
}

// ── Bloque de proveedor ───────────────────────────────────────────────────────
type BloqueProveedor = {
  nombre:    string;
  con_iva:   boolean;
  descuento: number;
  files:     File[];
};

function bloqueVacio(): BloqueProveedor {
  return { nombre: "", con_iva: true, descuento: 0, files: [] };
}

// ── Componente principal ──────────────────────────────────────────────────────
export default function Comparar() {
  const [bloques, setBloques]         = useState<BloqueProveedor[]>([bloqueVacio()]);
  const [dragging, setDragging]       = useState<number | null>(null);  // índice del bloque activo
  const [loading, setLoading]         = useState(false);
  const [progreso, setProgreso]       = useState<{ idx: number; total: number; archivo: string; etapa: string } | null>(null);
  const [resultado, setResultado]     = useState<Resultado | null>(null);
  const [error, setError]             = useState("");
  const [tab, setTab]                 = useState<"comparativa" | "dudosos" | "sin_match">("comparativa");
  const [filtroRubro, setFiltroRubro] = useState("Todos");
  const [soloComunes, setSoloComunes] = useState(true);
  const [confirmando, setConfirmando] = useState(false);
  const [confirmado, setConfirmado]   = useState(false);
  const [token, setToken]             = useState<string | null>(null);
  const [soyAdmin, setSoyAdmin]       = useState(false);

  // Estado editable de dudosos: usuario puede elegir alternativa
  const [dudososEditados, setDudososEditados] = useState<
    Record<string, Record<number, string>>
  >({});

  const [generandoSheets, setGenerandoSheets] = useState(false);
  const [generandoPdf, setGenerandoPdf]       = useState(false);
  const [generandoJpg, setGenerandoJpg]       = useState(false);

  const [conIva, setConIva]           = useState(false);
  const [descuentoPct, setDescuentoPct] = useState(0);
  const [soloDifGrande, setSoloDifGrande] = useState(false);

  useEffect(() => {
    const sb = createClient();
    sb.auth.getSession().then(({ data }) => {
      setToken(data.session?.access_token ?? null);
      setSoyAdmin(esAdmin(data.session?.user?.email));
    });
  }, []);

  // ── Helpers de bloques ─────────────────────────────────────────────────────
  function addBloque() {
    setBloques((prev) => [...prev, bloqueVacio()]);
  }

  function removeBloque(bi: number) {
    setBloques((prev) => prev.length === 1 ? [bloqueVacio()] : prev.filter((_, i) => i !== bi));
  }

  function updateBloque(bi: number, patch: Partial<Omit<BloqueProveedor, "files">>) {
    setBloques((prev) => prev.map((b, i) => i === bi ? { ...b, ...patch } : b));
  }

  function addFilesToBloque(bi: number, nuevos: File[]) {
    setBloques((prev) => prev.map((b, i) => i === bi ? { ...b, files: [...b.files, ...nuevos] } : b));
  }

  function removeFileFromBloque(bi: number, fi: number) {
    setBloques((prev) => prev.map((b, i) => i === bi ? { ...b, files: b.files.filter((_, j) => j !== fi) } : b));
  }

  // Drop global: cada archivo arrastrado = un proveedor nuevo (1 PDF = 1 proveedor).
  // Para agrupar varios PDFs en un mismo proveedor, usar "Agregar PDF" dentro del bloque.
  const onDropGlobal = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(null);
    const nuevos = Array.from(e.dataTransfer.files);
    if (!nuevos.length) return;
    setBloques((prev) => {
      const usados = prev.filter((b) => b.files.length > 0 || b.nombre.trim());
      const nuevosBloques = nuevos.map((f) => ({ ...bloqueVacio(), files: [f] }));
      return [...usados, ...nuevosBloques];
    });
  }, []);

  // ── Analizar ───────────────────────────────────────────────────────────────
  async function analizar() {
    const hayFuentes = bloques.some((b) => b.files.length > 0);
    if (!hayFuentes) return;
    setLoading(true);
    setError("");
    setResultado(null);
    setConfirmado(false);

    const nTotal = bloques.reduce((s, b) => s + b.files.length, 0);
    setProgreso({ idx: 0, total: nTotal, archivo: "", etapa: "subiendo archivos" });

    const form = new FormData();
    const fileConfigs: object[] = [];
    const progresoId = crypto.randomUUID();
    form.append("progreso_id", progresoId);

    // Flatten: por cada bloque, por cada file → agrega al form en el mismo orden.
    // Se manda el índice de bloque para que el backend agrupe los archivos de un
    // mismo proveedor (varios PDFs en un bloque = un solo proveedor).
    bloques.forEach((b, bi) => {
      for (const f of b.files) {
        form.append("files", f);
        fileConfigs.push({
          bloque:           bi,
          nombre_proveedor: b.nombre.trim() || undefined,
          con_iva:          b.con_iva,
          descuento:        b.descuento,
        });
      }
    });
    form.append("file_configs", JSON.stringify(fileConfigs));

    // Polling de progreso mientras el análisis corre: qué archivo va y en qué
    // etapa (las fotos/escaneados tardan ~20s cada uno por la lectura con IA).
    const timer = setInterval(async () => {
      try {
        const r = await fetch(`${API_URL}/analizar-v2/progreso/${progresoId}`);
        const p = await r.json();
        if (p && p.estado === "procesando") {
          setProgreso({ idx: p.idx, total: p.total, archivo: p.archivo, etapa: p.etapa });
        }
      } catch { /* el polling nunca corta el análisis */ }
    }, 2000);

    try {
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`${API_URL}/analizar-v2`, { method: "POST", headers, body: form });
      const data = await res.json();

      if (!res.ok) {
        if (data?.detail?.error === "plan_limit") {
          setError("Plan gratuito: máximo 2 análisis por día. Pasate al plan Advance.");
        } else if (data?.detail?.error === "sin_resultados" && Array.isArray(data?.detail?.errores)) {
          const lineas = data.detail.errores
            .map((e: { archivo: string; error: string }) => `• ${e.archivo}: ${e.error}`)
            .join("\n");
          setError(`Ningún archivo se pudo procesar:\n${lineas}`);
        } else {
          setError(data?.detail?.mensaje || JSON.stringify(data?.detail) || "Error al analizar los PDFs");
        }
        return;
      }

      setResultado(data);
      setTab("comparativa");

      // Con un solo proveedor no hay ítems "en común": si el filtro
      // "Solo comparables" quedara activo, la tabla se vería vacía.
      if ((data.proveedores?.length ?? 0) < 2) {
        setSoloComunes(false);
      }

      // Inicializar dudosos con la primera alternativa como selección por defecto
      const init: Record<string, Record<number, string>> = {};
      for (const [prov, r] of Object.entries(data.resultados as Record<string, ResultadoProveedor>)) {
        init[prov] = {};
        r.dudoso.forEach((item: ItemDudoso, idx: number) => {
          init[prov][idx] = item.codigo_material; // la sugerida por defecto
        });
      }
      setDudososEditados(init);
    } catch {
      setError("No se pudo conectar con el servidor de análisis.");
    } finally {
      clearInterval(timer);
      setProgreso(null);
      setLoading(false);
    }
  }

  // ── Confirmar v2 ───────────────────────────────────────────────────────────
  async function confirmar() {
    if (!resultado) return;
    setConfirmando(true);

    const confirmados: object[] = [];
    const sin_match_items: object[] = [];

    for (const [prov, r] of Object.entries(resultado.resultados)) {
      // Items automáticos
      for (const item of r.automatico) {
        confirmados.push({
          desc_prov:       item.desc_prov,
          proveedor:       prov,
          codigo_material: item.codigo_material,
          precio_sin_iva:  item.precio_sin_iva,
          unidad:          "UN",
          cantidad:        item.cant,
          item_id:         item.item_id ?? null,
        });
      }
      // Items dudosos con el código que el usuario eligió; si marcó que
      // ninguno corresponde, va como sin match (cola de pendientes)
      r.dudoso.forEach((item, idx) => {
        const codigoElegido = dudososEditados[prov]?.[idx] ?? item.codigo_material;
        if (codigoElegido === SIN_MATCH) {
          sin_match_items.push({
            desc_prov:      item.desc_prov,
            proveedor:      prov,
            precio_sin_iva: item.precio_sin_iva,
            unidad:         "UN",
            item_id:        item.item_id ?? null,
          });
          return;
        }
        confirmados.push({
          desc_prov:       item.desc_prov,
          proveedor:       prov,
          codigo_material: codigoElegido,
          precio_sin_iva:  item.precio_sin_iva,
          unidad:          "UN",
          cantidad:        item.cant,
          item_id:         item.item_id ?? null,
        });
      });
      // Sin match
      for (const item of r.sin_match) {
        sin_match_items.push({
          desc_prov:      item.desc_prov,
          proveedor:      prov,
          precio_sin_iva: item.precio_sin_iva,
          unidad:         "UN",
          item_id:        item.item_id ?? null,
        });
      }
    }

    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`${API_URL}/confirmar-v2`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          comparativa_id: resultado.comparativa_id,
          confirmados,
          sin_match: sin_match_items,
        }),
      });
      if (!res.ok) {
        alert("No se pudo guardar la confirmación. Probá de nuevo.");
        return;
      }

      // Integrar en pantalla lo que el usuario resolvió: los dudosos
      // matcheados pasan a la comparativa (y desaparecen de Dudosos),
      // los marcados "ninguno corresponde" pasan a Sin match.
      setResultado((prev) => {
        if (!prev) return prev;
        const comparativo = prev.comparativo.map((r) => ({ ...r, precios: { ...r.precios } }));
        const idxPorCodigo = new Map(comparativo.map((r, i) => [r.cod_int, i] as const));
        const nuevosResultados: typeof prev.resultados = {};

        for (const [prov, r] of Object.entries(prev.resultados)) {
          const nuevosSinMatch = [...r.sin_match];
          let movidos = 0;
          r.dudoso.forEach((item, idx) => {
            const elegido = dudososEditados[prov]?.[idx] ?? item.codigo_material;
            if (elegido === SIN_MATCH) {
              nuevosSinMatch.push({
                desc_prov: item.desc_prov, cod_prov: item.cod_prov,
                precio_sin_iva: item.precio_sin_iva, precio_con_iva: item.precio_con_iva,
                cant: item.cant, item_id: item.item_id,
              });
              return;
            }
            movidos++;
            const opciones = [
              { codigo_material: item.codigo_material, denominacion: item.denominacion_principal || item.denominacion_matcheada, descripcion: item.descripcion },
              ...item.alternativas,
            ];
            const alt = opciones.find((a) => a.codigo_material === elegido);
            const material = alt
              ? `${alt.denominacion}${alt.descripcion ? " — " + alt.descripcion : ""}`
              : elegido;
            const precioNuevo = { precio_sin_iva: item.precio_sin_iva, score: item.score, origen: "usuario", cant: item.cant };
            const i = idxPorCodigo.get(elegido);
            if (i !== undefined) {
              comparativo[i].precios[prov] = precioNuevo;
            } else {
              idxPorCodigo.set(elegido, comparativo.length);
              comparativo.push({
                cod_int: elegido, rubro: item.categoria || "", material,
                unidad: "UN", cant: item.cant, precios: { [prov]: precioNuevo },
                mejor_proveedor: prov, ahorro: 0, en_varios: false,
              });
            }
          });
          const total = Math.max(1, r.stats.total);
          nuevosResultados[prov] = {
            ...r,
            dudoso: [],
            sin_match: nuevosSinMatch,
            stats: {
              ...r.stats,
              automatico: r.stats.automatico + movidos,
              dudoso: 0,
              sin_match: nuevosSinMatch.length,
              pct_automatico: Math.round(100 * (r.stats.automatico + movidos) / total),
            },
          };
        }

        // Recalcular mejor proveedor y en_varios con las filas nuevas
        for (const row of comparativo) {
          const provs = Object.keys(row.precios);
          row.en_varios = provs.length >= 2;
          if (provs.length) {
            row.mejor_proveedor = provs.reduce(
              (best, p) => (row.precios[p].precio_sin_iva < row.precios[best].precio_sin_iva ? p : best),
              provs[0]
            );
          }
        }

        return { ...prev, comparativo, resultados: nuevosResultados };
      });
      setDudososEditados({});
      setTab("comparativa");
      setConfirmado(true);
    } catch {
      alert("No se pudo guardar la confirmación. Revisá tu conexión y probá de nuevo.");
    } finally {
      setConfirmando(false);
    }
  }

  // ── Descargar ──────────────────────────────────────────────────────────────
  async function descargar(endpoint: string, ext: string, setGen: (v: boolean) => void) {
    if (!resultado) return;
    setGen(true);
    try {
      const res = await fetch(`${API_URL}/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          comparativa_id: resultado.comparativa_id,
          solo_comunes:   soloComunes,
          filtro_rubro:   filtroRubro !== "Todos" ? filtroRubro : null,
          incluir_iva:    conIva,
          descuento_pct:  descuentoPct,
        }),
      });
      if (!res.ok) { alert("Error al generar el archivo"); return; }
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href = url;
      a.download = `VectorAI_${new Date().toISOString().slice(0, 10)}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setGen(false);
    }
  }

  // ── Datos derivados ────────────────────────────────────────────────────────
  const rubros = resultado
    ? ["Todos", ...Array.from(new Set(resultado.comparativo.map((r) => r.rubro))).sort()]
    : [];

  const filasFiltradas = resultado?.comparativo
    .filter((r) => filtroRubro === "Todos" || r.rubro === filtroRubro)
    .filter((r) => !soloComunes || r.en_varios)
    .filter((r) => !soloDifGrande || pctDiferencia(r.precios, r.cant || 1) >= 25) ?? [];

  // Ahorro de una fila: diferencia entre el proveedor más caro y el más barato
  // con los precios TAL COMO SE MUESTRAN (IVA por proveedor + descuento).
  // Solo cuenta si el ítem está en varios proveedores — con un solo presupuesto
  // no hay ahorro comparable.
  function ahorroFila(row: FilaComparativa): number {
    if (!row.en_varios || !resultado) return 0;
    const totales = resultado.proveedores
      .map((p) => {
        const pr = row.precios[p];
        if (!pr) return null;
        const factor = resultado.config_proveedores?.[p]?.factor_iva || 1.105;
        return precioMostrado(pr.precio_sin_iva, factor, conIva, descuentoPct) * (row.cant || 1);
      })
      .filter((v): v is number => v !== null);
    if (totales.length < 2) return 0;
    return Math.max(...totales) - Math.min(...totales);
  }

  const ahorroTotal = filasFiltradas.reduce((s, r) => s + ahorroFila(r), 0);

  const totalDudosos  = resultado ? Object.values(resultado.resultados).reduce((s, r) => s + r.dudoso.length, 0) : 0;
  const totalSinMatch = resultado ? Object.values(resultado.resultados).reduce((s, r) => s + r.sin_match.length, 0) : 0;
  const pctAuto       = resultado
    ? Math.round(100 * Object.values(resultado.resultados).reduce((s, r) => s + r.stats.automatico, 0) /
        Math.max(1, Object.values(resultado.resultados).reduce((s, r) => s + r.stats.total, 0)))
    : 0;

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <>
    <main className="min-h-screen bg-[#F5F0E8]">
      {/* Nav */}
      <nav className="bg-white border-b border-gray-200 px-4 sm:px-8 py-3 sm:py-4 flex items-center justify-between flex-wrap gap-y-2">
        <Link href="/" className="flex items-center gap-1.5">
          <Logo />
          <span className="text-xs font-semibold text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded-full align-middle">beta</span>
        </Link>
        <div className="flex gap-2 sm:gap-3 items-center flex-wrap">
          <Link href="/" className="hidden sm:inline text-sm text-gray-500 hover:text-gray-800 transition">Inicio</Link>
          <Link href="/app/historial" className="text-sm text-gray-500 hover:text-gray-800 transition">Mis comparativas</Link>
          <Link href="/app/presupuestos" className="text-sm text-gray-500 hover:text-gray-800 transition">Mis presupuestos</Link>
          {soyAdmin && (
            <Link href="/app/admin" className="text-sm text-gray-500 hover:text-gray-800 transition">Admin</Link>
          )}
          <Link
            href="/suscribirse"
            className="text-xs sm:text-sm font-semibold text-blue-600 border border-blue-200 bg-blue-50 hover:bg-blue-100 transition px-2.5 sm:px-3 py-1.5 rounded-lg whitespace-nowrap"
          >
            Mejorar plan
          </Link>
          <a
            href="https://wa.me/5492241410393?text=Hola%2C%20tengo%20una%20consulta%20sobre%20VectorAI"
            target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs sm:text-sm font-medium text-white bg-green-500 hover:bg-green-600 transition px-2.5 sm:px-3 py-1.5 rounded-lg whitespace-nowrap"
          >
            Consultas
          </a>
          <UserMenu />
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-10 pb-24 sm:pb-10">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Nueva comparativa</h1>
        <p className="text-gray-500 text-sm mb-8">Subí PDFs, fotos o planillas de tus proveedores para compararlos</p>

        {/* Upload: bloques de proveedor */}
        {!resultado && (
          <>
            {/* Zona global de drop */}
            <div
              onDragOver={(e) => { e.preventDefault(); setDragging(-1); }}
              onDragLeave={() => setDragging(null)}
              onDrop={onDropGlobal}
              className={`border-2 border-dashed rounded-2xl px-8 py-6 text-center transition mb-6 ${
                dragging === -1 ? "border-blue-400 bg-blue-50" : "border-gray-200 bg-white"
              }`}
            >
              <div className="text-3xl mb-2">📄</div>
              <p className="text-gray-500 text-sm">Arrastrá PDFs acá — cada archivo se agrega como un proveedor nuevo</p>
            </div>

            {/* Bloques de proveedor */}
            <div className="space-y-4 mb-6">
              {bloques.map((b, bi) => (
                <div
                  key={bi}
                  onDragOver={(e) => { e.preventDefault(); setDragging(bi); }}
                  onDragLeave={() => setDragging(null)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragging(null);
                    addFilesToBloque(bi, Array.from(e.dataTransfer.files));
                  }}
                  className={`bg-white rounded-xl border transition ${
                    dragging === bi ? "border-blue-400 ring-2 ring-blue-100" : "border-gray-200"
                  }`}
                >
                  {/* Cabecera del bloque */}
                  <div className="flex flex-wrap items-center gap-2 sm:gap-3 px-4 py-3 border-b border-gray-100">
                    <span className="hidden sm:inline text-xs font-bold text-gray-400 uppercase tracking-wide w-20 shrink-0">Proveedor</span>
                    <input
                      type="text"
                      value={b.nombre}
                      onChange={(e) => updateBloque(bi, { nombre: e.target.value })}
                      placeholder={`Proveedor ${bi + 1}`}
                      className="flex-1 min-w-[140px] text-sm font-semibold text-gray-800 border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400 placeholder:font-normal placeholder:text-gray-400"
                    />

                    {/* Toggle IVA */}
                    <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden text-xs shrink-0">
                      <button
                        onClick={() => updateBloque(bi, { con_iva: false })}
                        className={`px-2.5 py-1.5 transition ${!b.con_iva ? "bg-blue-600 text-white font-semibold" : "text-gray-500 hover:bg-gray-50"}`}
                      >Sin IVA</button>
                      <button
                        onClick={() => updateBloque(bi, { con_iva: true })}
                        className={`px-2.5 py-1.5 transition ${b.con_iva ? "bg-blue-600 text-white font-semibold" : "text-gray-500 hover:bg-gray-50"}`}
                      >C/IVA</button>
                    </div>

                    {/* Descuento */}
                    <div className="flex items-center gap-1 shrink-0">
                      <input
                        type="number" min="0" max="100" step="1"
                        value={b.descuento || ""}
                        onChange={(e) => updateBloque(bi, { descuento: Number(e.target.value) || 0 })}
                        placeholder="0"
                        className="w-12 border border-gray-200 rounded-lg px-1.5 py-1.5 text-xs text-center text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-400"
                      />
                      <span className="text-xs text-gray-400">% desc.</span>
                    </div>

                    {/* Quitar bloque */}
                    <button
                      onClick={() => removeBloque(bi)}
                      className="text-gray-300 hover:text-red-400 text-xl leading-none ml-1 shrink-0"
                      title="Quitar proveedor"
                    >×</button>
                  </div>

                  {/* Archivos del bloque */}
                  {b.files.length > 0 && (
                    <div className="px-4 py-2 space-y-1">
                      {b.files.map((f, fi) => (
                        <div key={fi} className="flex items-center gap-2 text-sm py-1">
                          <span className="text-gray-400">📄</span>
                          <span className="flex-1 text-gray-700 truncate">{f.name}</span>
                          <span className="text-xs text-gray-400 shrink-0">{(f.size / 1024).toFixed(0)} KB</span>
                          <button
                            onClick={() => removeFileFromBloque(bi, fi)}
                            className="text-gray-300 hover:text-red-400 text-base leading-none shrink-0"
                          >×</button>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Agregar PDFs al bloque: label completo solo si está vacío */}
                  <div className="px-4 py-2.5">
                    <label className={`flex items-center gap-1.5 text-xs cursor-pointer w-fit ${b.files.length > 0 ? "text-gray-400 hover:text-blue-600" : "text-blue-600 hover:text-blue-800"}`}>
                      <span>＋</span>
                      <span>{b.files.length > 0 ? "Agregar otro archivo" : "Agregar PDF / foto / planilla"}</span>
                      <input
                        type="file" accept="application/pdf,image/*,.xlsx,.xls,.csv,.tiff,.tif" multiple className="hidden"
                        onChange={(e) => addFilesToBloque(bi, Array.from(e.target.files || []))}
                      />
                    </label>
                  </div>
                </div>
              ))}
            </div>

            {/* Agregar proveedor + Analizar */}
            <div className="flex items-center gap-3 flex-wrap">
              <button
                onClick={addBloque}
                className="border border-dashed border-gray-300 text-gray-500 text-sm font-medium px-5 py-2.5 rounded-xl hover:border-blue-400 hover:text-blue-600 transition"
              >
                ＋ Agregar proveedor
              </button>

              {error && (
                <div className="flex-1 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-2.5 rounded-xl whitespace-pre-line">{error}</div>
              )}

              <button
                onClick={analizar}
                disabled={!bloques.some((b) => b.files.length > 0) || loading}
                className="ml-auto bg-blue-600 text-white font-semibold px-8 py-2.5 rounded-xl hover:bg-blue-700 transition disabled:opacity-40"
              >
                {loading ? "Analizando…" : "⚡ Analizar"}
              </button>
            </div>

            {/* Progreso del análisis en curso: qué archivo va y en qué etapa */}
            {loading && progreso && (
              <div className="mt-4 bg-white border border-blue-200 rounded-xl p-5 shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-gray-800">
                    Analizando {progreso.total} archivo{progreso.total !== 1 ? "s" : ""}…
                  </span>
                  <span className="text-sm text-gray-500">
                    {Math.min(Math.max(progreso.idx, 1), progreso.total)} de {progreso.total}
                  </span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden">
                  <div
                    className="bg-blue-600 h-2.5 rounded-full transition-all duration-700"
                    style={{ width: `${Math.max(4, Math.round((Math.max(progreso.idx - 1, 0) / Math.max(progreso.total, 1)) * 100))}%` }}
                  />
                </div>
                {progreso.archivo && (
                  <p className="text-sm text-gray-600 mt-2 truncate">📄 {progreso.archivo} — {progreso.etapa}</p>
                )}
                <p className="text-xs text-amber-600 mt-2">
                  ⏳ Las fotos y documentos escaneados se leen con inteligencia artificial (≈20 segundos cada uno).
                  No cierres ni salgas de esta pantalla: el análisis se perdería.
                </p>
              </div>
            )}
          </>
        )}

        {/* Resultados */}
        {resultado && (
          <>
            {/* Aviso usos restantes */}
            {resultado.usos_restantes !== null && resultado.usos_restantes <= 1 && (
              <div className={`mb-4 px-4 py-3 rounded-xl text-sm font-medium flex items-center justify-between ${
                resultado.usos_restantes === 0
                  ? "bg-red-50 border border-red-200 text-red-700"
                  : "bg-amber-50 border border-amber-200 text-amber-700"
              }`}>
                <span>
                  {resultado.usos_restantes === 0
                    ? "Usaste todas tus comparativas del mes. Se renuevan el mes que viene."
                    : "Te queda 1 comparativa este mes."}
                </span>
                {resultado.usos_restantes === 0 && (
                  <Link href="/suscribirse" className="ml-4 bg-blue-600 text-white text-xs font-semibold px-3 py-1.5 rounded-lg">
                    Ver Advance →
                  </Link>
                )}
              </div>
            )}

            {/* Archivos que fallaron al procesarse (no llegaron a resultados) */}
            {(resultado.errores?.length ?? 0) > 0 && (
              <div className="mb-4 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-800 space-y-1">
                <div className="font-semibold">⚠️ Archivos que no se pudieron procesar:</div>
                {resultado.errores!.map((e, i) => (
                  <div key={i}>• <strong>{e.archivo}</strong>: {e.error}</div>
                ))}
              </div>
            )}

            {/* Alertas de extracción por proveedor */}
            {Object.entries(resultado.resultados).some(([, r]) => r.n_items_extraidos === 0) && (
              <div className="mb-4 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-800 space-y-1">
                <div className="font-semibold">⚠️ Algunos PDFs no pudieron ser leídos:</div>
                {Object.entries(resultado.resultados).map(([prov, r]) =>
                  r.n_items_extraidos === 0 ? (
                    <div key={prov}>• <strong>{prov}</strong>: 0 ítems extraídos. El PDF puede estar escaneado (imagen), protegido, o en un formato no reconocido. Intentá exportarlo desde el software del proveedor como PDF con texto.</div>
                  ) : null
                )}
              </div>
            )}

            {/* KPIs */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {[
                { label: "Proveedores",     value: resultado.proveedores.length },
                { label: "Match automático", value: `${pctAuto}%` },
                { label: "En común",        value: resultado.comparativo.filter((r) => r.en_varios).length },
                { label: "Ahorro potencial", value: fmt(ahorroTotal) },
              ].map((k) => (
                <div key={k.label} className="bg-white rounded-xl border border-gray-200 px-5 py-4">
                  <div className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1">{k.label}</div>
                  <div className="text-2xl font-bold text-gray-900">{k.value}</div>
                </div>
              ))}
            </div>

            {/* Acciones */}
            <div className="flex gap-3 mb-6 flex-wrap items-center">
              <button onClick={() => descargar("sheets", "xlsx", setGenerandoSheets)} disabled={generandoSheets}
                className="bg-green-600 text-white font-medium px-5 py-2.5 rounded-lg hover:bg-green-700 transition text-sm disabled:opacity-50">
                {generandoSheets ? "Generando…" : "↓ Excel"}
              </button>
              <button onClick={() => descargar("pdf", "pdf", setGenerandoPdf)} disabled={generandoPdf}
                className="bg-blue-600 text-white font-medium px-5 py-2.5 rounded-lg hover:bg-blue-700 transition text-sm disabled:opacity-50">
                {generandoPdf ? "Generando…" : "↓ PDF"}
              </button>
              <button onClick={() => descargar("imagen", "jpg", setGenerandoJpg)} disabled={generandoJpg}
                className="bg-purple-600 text-white font-medium px-5 py-2.5 rounded-lg hover:bg-purple-700 transition text-sm disabled:opacity-50">
                {generandoJpg ? "Generando…" : "↓ JPG"}
              </button>
              <button onClick={() => { setResultado(null); setBloques([bloqueVacio()]); setConfirmado(false); }}
                className="border border-gray-300 text-gray-600 font-medium px-5 py-2.5 rounded-lg hover:bg-gray-50 transition text-sm">
                + Nueva comparativa
              </button>

              {/* Confirmar aliases */}
              {!confirmado ? (
                <button onClick={confirmar} disabled={confirmando}
                  className="ml-auto bg-gray-900 text-white font-medium px-5 py-2.5 rounded-lg hover:bg-gray-700 transition text-sm disabled:opacity-50">
                  {confirmando ? "Guardando…" : "✓ Confirmar y aprender"}
                </button>
              ) : (
                <span className="ml-auto text-sm text-green-700 font-medium bg-green-50 px-4 py-2.5 rounded-lg border border-green-200">
                  ✓ Guardado — el sistema aprendió estos matches
                </span>
              )}
            </div>

            {/* Stats por proveedor */}
            <div className="bg-white rounded-xl border border-gray-200 mb-4 overflow-x-auto">
              <div className="min-w-[540px] grid grid-cols-[1fr_80px_80px_80px_80px] gap-x-4 px-4 py-2 bg-gray-50 border-b border-gray-100 text-xs font-semibold text-gray-400 uppercase tracking-wide">
                <span>Proveedor</span>
                <span className="text-center">Extraídos</span>
                <span className="text-center">Auto</span>
                <span className="text-center">Dudosos</span>
                <span className="text-center">Sin match</span>
              </div>
              {Object.entries(resultado.resultados).map(([prov, r]) => {
                const pct = r.stats.pct_automatico;
                const barColor = pct >= 80 ? "bg-green-500" : pct >= 60 ? "bg-amber-400" : "bg-red-400";
                return (
                  <div key={prov} className="min-w-[540px] grid grid-cols-[1fr_80px_80px_80px_80px] gap-x-4 px-4 py-3 border-b border-gray-100 last:border-0 items-center">
                    <div>
                      <div className="text-sm font-semibold text-gray-800">{prov}</div>
                      <div className="flex items-center gap-2 mt-1">
                        <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden max-w-[120px]">
                          <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-xs text-gray-500">{pct}% auto</span>
                      </div>
                    </div>
                    <span className="text-sm text-center text-gray-600">{r.n_items_extraidos}</span>
                    <span className="text-sm text-center font-medium text-green-700">{r.stats.automatico}</span>
                    <span className="text-sm text-center text-amber-600">{r.stats.dudoso}</span>
                    <span className="text-sm text-center text-red-500">{r.stats.sin_match}</span>
                  </div>
                );
              })}
            </div>

            {/* Tabs */}
            <div className="flex gap-1 mb-4 bg-gray-100 p-1 rounded-xl w-fit">
              {([
                ["comparativa", `Comparativa (${resultado.comparativo.length})`],
                ["dudosos",     `Dudosos (${totalDudosos})`],
                ["sin_match",   `Sin match (${totalSinMatch})`],
              ] as const).map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => setTab(id)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                    tab === id ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* ── TAB: Comparativa ─────────────────────────────────────────── */}
            {tab === "comparativa" && (
              <>
                <div className="flex gap-3 items-center mb-4 flex-wrap">
                  <select value={filtroRubro} onChange={(e) => setFiltroRubro(e.target.value)}
                    className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-400">
                    {rubros.map((r) => <option key={r}>{r}</option>)}
                  </select>
                  <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer" title="Mostrar solo ítems cotizados por más de un proveedor">
                    <input type="checkbox" checked={soloComunes} onChange={(e) => setSoloComunes(e.target.checked)}
                      className="w-4 h-4 text-blue-600 rounded" />
                    Solo comparables
                  </label>
                  <label className="flex items-center gap-2 text-sm text-amber-700 cursor-pointer">
                    <input type="checkbox" checked={soloDifGrande} onChange={(e) => setSoloDifGrande(e.target.checked)}
                      className="w-4 h-4 text-amber-500 rounded" />
                    Solo dif. &gt;25%
                  </label>

                  {/* IVA / Descuento */}
                  <div className="flex items-center gap-1 ml-auto border border-gray-200 rounded-lg overflow-hidden text-sm">
                    <button
                      onClick={() => setConIva(false)}
                      className={`px-3 py-2 transition ${!conIva ? "bg-blue-600 text-white font-semibold" : "text-gray-500 hover:bg-gray-50"}`}
                    >
                      Sin IVA
                    </button>
                    <button
                      onClick={() => setConIva(true)}
                      className={`px-3 py-2 transition ${conIva ? "bg-blue-600 text-white font-semibold" : "text-gray-500 hover:bg-gray-50"}`}
                    >
                      Con IVA
                    </button>
                  </div>
                  <div className="flex items-center gap-1.5 text-sm">
                    <span className="text-gray-500">Desc.</span>
                    <input
                      type="number" min="0" max="100" step="1" value={descuentoPct || ""}
                      onChange={(e) => setDescuentoPct(Number(e.target.value) || 0)}
                      placeholder="0"
                      className="w-16 border border-gray-300 rounded-lg px-2 py-2 text-sm text-center text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-400"
                    />
                    <span className="text-gray-500">%</span>
                  </div>
                </div>

                <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-gray-50 border-b border-gray-200">
                        <th className="text-left px-4 py-3 font-semibold text-gray-600 min-w-[240px]">Material</th>
                        <th className="px-3 py-3 font-semibold text-gray-600 text-xs uppercase">Cant.</th>
                        <th className="px-3 py-3 font-semibold text-gray-600 text-xs uppercase">Unidad</th>
                        {resultado.proveedores.map((p) => {
                          const cfg = resultado.config_proveedores?.[p];
                          return (
                            <th key={p} className="px-4 py-3 font-semibold text-gray-700 text-center">
                              <div>{p}</div>
                              {cfg && (
                                <div className="flex gap-1 justify-center mt-0.5 flex-wrap">
                                  {cfg.iva_incluido && (
                                    <span className="text-[10px] font-normal bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded">c/IVA</span>
                                  )}
                                  {cfg.descuento_pct > 0 && (
                                    <span className="text-[10px] font-normal bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">desc {cfg.descuento_pct}%</span>
                                  )}
                                </div>
                              )}
                            </th>
                          );
                        })}
                        <th className="px-4 py-3 font-semibold text-gray-600 text-center">Mejor</th>
                        <th className="px-4 py-3 font-semibold text-gray-500 text-center text-xs">Ahorro</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filasFiltradas.map((row, i) => {
                        const difPct = pctDiferencia(row.precios, row.cant || 1);
                        const granDif = difPct >= 25 && row.en_varios;
                        return (
                        <tr key={i} className={`border-b border-gray-100 last:border-0 hover:bg-gray-50 ${granDif ? "bg-amber-50/60" : ""}`}>
                          <td className="px-4 py-3">
                            <div className="font-medium text-gray-800 text-xs">{row.material}</div>
                            <div className="text-xs text-gray-400">{row.rubro}</div>
                          </td>
                          <td className="px-3 py-3 text-center text-xs text-gray-500">
                            {row.cant || 1}
                          </td>
                          <td className="px-3 py-3 text-center text-xs text-gray-500">
                            {row.unidad || "—"}
                          </td>
                          {resultado.proveedores.map((p) => {
                            const precio = row.precios[p];
                            const esMejor = row.mejor_proveedor === p && row.en_varios;
                            const factorProv = resultado.config_proveedores?.[p]?.factor_iva || 1.105;
                            const precioU = precio ? precioMostrado(precio.precio_sin_iva, factorProv, conIva, descuentoPct) : null;
                            const total   = precioU !== null ? precioU * (row.cant || 1) : null;
                            return (
                              <td key={p} className={`px-4 py-3 text-center ${esMejor ? "bg-green-50" : ""}`}>
                                {precioU !== null ? (
                                  <div>
                                    <span className={`font-medium ${esMejor ? "text-green-700 font-bold" : "text-gray-700"}`}>
                                      {fmt(total!)}
                                    </span>
                                    <div className="text-xs text-gray-400">{fmt(precioU)}/u</div>
                                  </div>
                                ) : <span className="text-gray-300">—</span>}
                              </td>
                            );
                          })}
                          <td className="px-4 py-3 text-center">
                            {row.en_varios && (
                              <span className="text-xs bg-green-100 text-green-700 font-semibold px-2 py-1 rounded-full">
                                {row.mejor_proveedor}
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-center text-xs">
                            {ahorroFila(row) > 0 && (
                              <div className={granDif ? "text-amber-700 font-semibold" : "text-gray-400"}>
                                {fmt(ahorroFila(row))}
                                {granDif && <div className="text-amber-500 font-bold">↕ {difPct}%</div>}
                                {difPct >= 200 && (
                                  <div className="text-red-500 font-semibold" title="Diferencia enorme: puede ser un problema de unidades (ej. caja vs unidad)">
                                    ⚠ ¿unidad?
                                  </div>
                                )}
                              </div>
                            )}
                          </td>
                        </tr>
                      );})}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {/* ── TAB: Dudosos ─────────────────────────────────────────────── */}
            {tab === "dudosos" && (
              <div className="space-y-3">
                {totalDudosos === 0 ? (
                  <div className="bg-white rounded-xl border border-gray-200 px-6 py-10 text-center text-gray-400">
                    No hay ítems dudosos — todos los matches fueron automáticos.
                  </div>
                ) : (
                  Object.entries(resultado.resultados).map(([prov, r]) =>
                    r.dudoso.length === 0 ? null : (
                      <div key={prov}>
                        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">{prov}</h3>
                        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                          {r.dudoso.map((item, idx) => (
                            <div key={idx} className="px-4 py-4 border-b border-gray-100 last:border-0">
                              <div className="flex items-start justify-between gap-4">
                                <div className="flex-1 min-w-0">
                                  <div className="text-sm font-medium text-gray-800 truncate">{item.desc_prov}</div>
                                  <div className="text-xs text-gray-400 mt-0.5">{fmt(item.precio_sin_iva)}/u · cant {item.cant}</div>
                                  {item.precio_sospechoso && (
                                    <div className="text-xs text-red-600 mt-1">
                                      ⚠ Precio unitario × cantidad no coincide con el total de la línea — verificá el precio antes de confirmar.
                                    </div>
                                  )}
                                  {item.conversion && (
                                    <div className="text-xs text-blue-600 mt-1">
                                      ↔ Precio {item.conversion} para comparar con otros proveedores.
                                    </div>
                                  )}
                                  {item.unidad_ambigua && (
                                    <div className="text-xs text-amber-600 mt-1">
                                      ⚠ Este material se vende por tira/rollo y el texto no aclara si el precio es por metro o por presentación completa — verificá la unidad.
                                    </div>
                                  )}
                                </div>
                                <ScoreBadge score={item.score} />
                              </div>

                              {/* Selector de alternativas */}
                              <div className="mt-3">
                                <div className="text-xs text-gray-500 mb-1.5">¿A qué material corresponde?</div>
                                <div className="flex flex-col gap-1.5">
                                  {/* La sugerida + alternativas, sin códigos repetidos */}
                                  {[
                                    { codigo_material: item.codigo_material, denominacion: item.denominacion_principal || item.denominacion_matcheada, descripcion: item.descripcion, score: item.score },
                                    ...item.alternativas,
                                  ].filter((alt, i, arr) =>
                                    arr.findIndex((a) => a.codigo_material === alt.codigo_material) === i
                                  ).map((alt) => {
                                    const elegido = dudososEditados[prov]?.[idx] ?? item.codigo_material;
                                    const isSelected = elegido === alt.codigo_material;
                                    return (
                                      <button
                                        key={alt.codigo_material}
                                        onClick={() => setDudososEditados((prev) => ({
                                          ...prev,
                                          [prov]: { ...prev[prov], [idx]: alt.codigo_material },
                                        }))}
                                        className={`flex items-center gap-2 text-left px-3 py-2 rounded-lg border text-sm transition ${
                                          isSelected
                                            ? "border-blue-500 bg-blue-50 text-blue-800"
                                            : "border-gray-200 hover:border-gray-300 text-gray-700"
                                        }`}
                                      >
                                        <span className={`w-4 h-4 rounded-full border-2 flex-shrink-0 ${
                                          isSelected ? "border-blue-500 bg-blue-500" : "border-gray-300"
                                        }`} />
                                        <span className="flex-1 truncate">
                                          {alt.denominacion}
                                          {alt.descripcion ? (
                                            <span className={isSelected ? "text-blue-500" : "text-gray-400"}> — {alt.descripcion}</span>
                                          ) : null}
                                        </span>
                                        <ScoreBadge score={alt.score} />
                                      </button>
                                    );
                                  })}
                                  {/* Ninguna alternativa corresponde → dejar sin match */}
                                  {(() => {
                                    const elegido = dudososEditados[prov]?.[idx] ?? item.codigo_material;
                                    const isSelected = elegido === SIN_MATCH;
                                    return (
                                      <button
                                        onClick={() => setDudososEditados((prev) => ({
                                          ...prev,
                                          [prov]: { ...prev[prov], [idx]: SIN_MATCH },
                                        }))}
                                        className={`flex items-center gap-2 text-left px-3 py-2 rounded-lg border text-sm transition ${
                                          isSelected
                                            ? "border-gray-500 bg-gray-100 text-gray-800"
                                            : "border-dashed border-gray-300 hover:border-gray-400 text-gray-500"
                                        }`}
                                      >
                                        <span className={`w-4 h-4 rounded-full border-2 flex-shrink-0 ${
                                          isSelected ? "border-gray-500 bg-gray-500" : "border-gray-300"
                                        }`} />
                                        <span className="flex-1">✕ Ninguno corresponde — dejar sin match</span>
                                      </button>
                                    );
                                  })()}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )
                  )
                )}
              </div>
            )}

            {/* ── TAB: Sin match ────────────────────────────────────────────── */}
            {tab === "sin_match" && (
              <div className="space-y-3">
                {totalSinMatch === 0 ? (
                  <div className="bg-white rounded-xl border border-gray-200 px-6 py-10 text-center text-gray-400">
                    Sin ítems sin match — todo fue identificado.
                  </div>
                ) : (
                  <>
                    <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800">
                      Estos ítems no están en la base de materiales todavía. Al confirmar se guardan como pendientes
                      y los revisamos para agregarlos — la próxima vez que aparezcan se van a matchear automáticamente.
                    </div>
                    {Object.entries(resultado.resultados).map(([prov, r]) =>
                      r.sin_match.length === 0 ? null : (
                        <div key={prov}>
                          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">{prov}</h3>
                          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                            {r.sin_match.map((item, idx) => (
                              <div key={idx} className="flex items-center gap-3 px-4 py-3 border-b border-gray-100 last:border-0">
                                <span className="w-2 h-2 rounded-full bg-red-400 flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                  <div className="text-sm text-gray-700 truncate">{item.desc_prov}</div>
                                </div>
                                <div className="text-xs text-gray-400 flex-shrink-0">{fmt(item.precio_sin_iva)}/u</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )
                    )}
                  </>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </main>
    <Footer />
    </>
  );
}
