"use client";
import { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase";
import Footer from "@/components/Footer";
import UserMenu from "@/components/UserMenu";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Tipos ─────────────────────────────────────────────────────────────────────
type Alternativa = { codigo_material: string; denominacion: string; score: number };

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
};

type ItemDudoso = ItemAutomatico & { codigo_elegido?: string };

type ItemSinMatch = {
  desc_prov: string;
  cod_prov: string;
  precio_sin_iva: number;
  precio_con_iva: number;
  cant: number;
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
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(v: number) {
  return `$ ${Math.round(v).toLocaleString("es-AR")}`;
}

function aplicarFactores(v: number, conIva: boolean, descPct: number) {
  const iva  = conIva ? 1.105 : 1;
  const desc = descPct > 0 ? (1 - descPct / 100) : 1;
  return v * iva * desc;
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

// ── Componente principal ──────────────────────────────────────────────────────
export default function Comparar() {
  const [files, setFiles]       = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading]   = useState(false);
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [error, setError]       = useState("");
  const [tab, setTab]           = useState<"comparativa" | "dudosos" | "sin_match">("comparativa");
  const [filtroRubro, setFiltroRubro] = useState("Todos");
  const [soloComunes, setSoloComunes] = useState(true);
  const [confirmando, setConfirmando] = useState(false);
  const [confirmado, setConfirmado]   = useState(false);
  const [token, setToken]       = useState<string | null>(null);

  // Estado editable de dudosos: usuario puede elegir alternativa
  const [dudososEditados, setDudososEditados] = useState<
    Record<string, Record<number, string>>  // proveedor → idx → codigo_material elegido
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
    });
  }, []);

  // ── Upload ─────────────────────────────────────────────────────────────────
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const nuevos = Array.from(e.dataTransfer.files).filter((f) => f.type === "application/pdf");
    setFiles((prev) => [...prev, ...nuevos]);
  }, []);

  function removeFile(i: number) {
    setFiles((prev) => prev.filter((_, idx) => idx !== i));
  }

  // ── Analizar ───────────────────────────────────────────────────────────────
  async function analizar() {
    if (!files.length) return;
    setLoading(true);
    setError("");
    setResultado(null);
    setConfirmado(false);

    const form = new FormData();
    files.forEach((f) => form.append("files", f));

    try {
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`${API_URL}/analizar-v2`, { method: "POST", headers, body: form });
      const data = await res.json();

      if (!res.ok) {
        if (data?.detail?.error === "plan_limit") {
          setError("Plan gratuito: máximo 2 análisis por día. Pasate al plan Advance.");
        } else {
          setError(data?.detail?.mensaje || JSON.stringify(data?.detail) || "Error al analizar los PDFs");
        }
        return;
      }

      setResultado(data);
      setTab("comparativa");

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
        });
      }
      // Items dudosos con el código que el usuario eligió
      r.dudoso.forEach((item, idx) => {
        const codigoElegido = dudososEditados[prov]?.[idx] ?? item.codigo_material;
        confirmados.push({
          desc_prov:       item.desc_prov,
          proveedor:       prov,
          codigo_material: codigoElegido,
          precio_sin_iva:  item.precio_sin_iva,
          unidad:          "UN",
          cantidad:        item.cant,
        });
      });
      // Sin match
      for (const item of r.sin_match) {
        sin_match_items.push({
          desc_prov:      item.desc_prov,
          proveedor:      prov,
          precio_sin_iva: item.precio_sin_iva,
          unidad:         "UN",
        });
      }
    }

    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      await fetch(`${API_URL}/confirmar-v2`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          comparativa_id: resultado.comparativa_id,
          confirmados,
          sin_match: sin_match_items,
        }),
      });
      setConfirmado(true);
    } catch {
      // no bloqueante
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

  const ahorroTotal = filasFiltradas.reduce(
    (s, r) => s + aplicarFactores(r.ahorro || 0, conIva, descuentoPct), 0
  );

  const totalDudosos  = resultado ? Object.values(resultado.resultados).reduce((s, r) => s + r.dudoso.length, 0) : 0;
  const totalSinMatch = resultado ? Object.values(resultado.resultados).reduce((s, r) => s + r.sin_match.length, 0) : 0;
  const pctAuto       = resultado
    ? Math.round(100 * Object.values(resultado.resultados).reduce((s, r) => s + r.stats.automatico, 0) /
        Math.max(1, Object.values(resultado.resultados).reduce((s, r) => s + r.stats.total, 0)))
    : 0;

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <>
    <main className="min-h-screen bg-gray-50">
      {/* Nav */}
      <nav className="bg-white border-b border-gray-200 px-8 py-4 flex items-center justify-between">
        <Link href="/" className="text-lg font-bold text-gray-900">
          VectorAI <span className="text-xs font-semibold text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded-full align-middle">beta</span>
        </Link>
        <div className="flex gap-3 items-center">
          <Link href="/app/historial" className="text-sm text-gray-500 hover:text-gray-800 transition">Mis comparativas</Link>
          <Link href="/app/admin" className="text-sm text-gray-500 hover:text-gray-800 transition">Admin</Link>
          <a
            href="https://wa.me/5492241410393?text=Hola%2C%20tengo%20una%20consulta%20sobre%20VectorAI"
            target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-sm font-medium text-white bg-green-500 hover:bg-green-600 transition px-3 py-1.5 rounded-lg"
          >
            Consultas
          </a>
          <UserMenu />
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-10">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Nueva comparativa</h1>
        <p className="text-gray-500 text-sm mb-8">Subí los PDFs de tus proveedores para compararlos</p>

        {/* Upload zone */}
        {!resultado && (
          <>
            <div
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={`border-2 border-dashed rounded-2xl p-12 text-center transition cursor-pointer mb-6 ${
                dragging ? "border-blue-400 bg-blue-50" : "border-gray-300 bg-white hover:border-blue-300"
              }`}
              onClick={() => document.getElementById("file-input")?.click()}
            >
              <input
                id="file-input" type="file" accept="application/pdf,image/*,.tiff,.tif" multiple className="hidden"
                onChange={(e) => setFiles((prev) => [...prev, ...Array.from(e.target.files || [])])}
              />
              <div className="text-4xl mb-4">📄</div>
              <p className="text-gray-600 font-medium">Arrastrá los PDFs acá o hacé click para seleccionar</p>
              <p className="text-gray-400 text-sm mt-1">PDF, JPG, TIFF · Uno por proveedor</p>
            </div>

            {files.length > 0 && (
              <div className="bg-white rounded-xl border border-gray-200 mb-6 overflow-hidden">
                {files.map((f, i) => (
                  <div key={i} className="flex items-center gap-3 px-4 py-3 border-b border-gray-100 last:border-0">
                    <span className="text-gray-400">📄</span>
                    <span className="flex-1 text-sm text-gray-700">{f.name}</span>
                    <span className="text-xs text-gray-400">{(f.size / 1024).toFixed(0)} KB</span>
                    <button onClick={() => removeFile(i)} className="text-gray-400 hover:text-red-500 text-lg">×</button>
                  </div>
                ))}
              </div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-4 rounded-xl mb-6">{error}</div>
            )}

            <button
              onClick={analizar}
              disabled={!files.length || loading}
              className="bg-blue-600 text-white font-semibold px-8 py-3 rounded-xl hover:bg-blue-700 transition disabled:opacity-40"
            >
              {loading ? "Analizando…" : "⚡ Analizar"}
            </button>
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
                    ? "Usaste todos tus análisis gratuitos de hoy. Mañana se renueva."
                    : "Te queda 1 análisis gratuito hoy."}
                </span>
                {resultado.usos_restantes === 0 && (
                  <Link href="/suscribirse" className="ml-4 bg-blue-600 text-white text-xs font-semibold px-3 py-1.5 rounded-lg">
                    Ver Advance →
                  </Link>
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
              <button onClick={() => { setResultado(null); setFiles([]); setConfirmado(false); }}
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
                    className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400">
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
                      className="w-16 border border-gray-300 rounded-lg px-2 py-2 text-sm text-center focus:outline-none focus:ring-2 focus:ring-blue-400"
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
                            {row.cant > 1 ? `${row.cant} ${row.unidad}` : row.unidad}
                          </td>
                          {resultado.proveedores.map((p) => {
                            const precio = row.precios[p];
                            const esMejor = row.mejor_proveedor === p && row.en_varios;
                            const precioU = precio ? aplicarFactores(precio.precio_sin_iva, conIva, descuentoPct) : null;
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
                            {row.ahorro > 0 && (
                              <div className={granDif ? "text-amber-700 font-semibold" : "text-gray-400"}>
                                {fmt(aplicarFactores(row.ahorro, conIva, descuentoPct))}
                                {granDif && <div className="text-amber-500 font-bold">↕ {difPct}%</div>}
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
                                </div>
                                <ScoreBadge score={item.score} />
                              </div>

                              {/* Selector de alternativas */}
                              <div className="mt-3">
                                <div className="text-xs text-gray-500 mb-1.5">¿A qué material corresponde?</div>
                                <div className="flex flex-col gap-1.5">
                                  {/* La sugerida */}
                                  {[
                                    { codigo_material: item.codigo_material, denominacion: item.denominacion_principal || item.denominacion_matcheada, score: item.score },
                                    ...item.alternativas,
                                  ].map((alt) => {
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
                                        <span className="flex-1 truncate">{alt.denominacion}</span>
                                        <ScoreBadge score={alt.score} />
                                        <span className="text-xs text-gray-400 flex-shrink-0">{alt.codigo_material}</span>
                                      </button>
                                    );
                                  })}
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
