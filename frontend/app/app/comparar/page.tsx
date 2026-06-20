"use client";
import { useState, useCallback } from "react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Precio = { precio_sin_iva: number; score: number; origen: string };
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
type SinMatch = { cod_prov: string; desc_prov: string; precio: number };

function fmt(v: number) {
  return `$ ${Math.round(v).toLocaleString("es-AR")}`;
}

export default function Comparar() {
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resultado, setResultado] = useState<null | {
    comparativo: FilaComparativa[];
    proveedores: string[];
    sin_match: Record<string, SinMatch[]>;
    plan: string;
    comparativa_id: string;
  }>(null);
  const [error, setError] = useState("");
  const [filtroRubro, setFiltroRubro] = useState("Todos");
  const [soloComunes, setSoloComunes] = useState(false);
  const [generandoSheets, setGenerandoSheets] = useState(false);
  const [generandoPdf, setGenerandoPdf] = useState(false);
  const [generandoJpg, setGenerandoJpg] = useState(false);

  // Drag & drop
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const nuevos = Array.from(e.dataTransfer.files).filter((f) => f.type === "application/pdf");
    setFiles((prev) => [...prev, ...nuevos]);
  }, []);

  function removeFile(i: number) {
    setFiles((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function analizar() {
    if (!files.length) return;
    setLoading(true);
    setError("");
    setResultado(null);

    const form = new FormData();
    files.forEach((f) => form.append("files", f));

    try {
      const res = await fetch(`${API_URL}/analizar`, {
        method: "POST",
        body: form,
        // headers: { Authorization: `Bearer ${token}` }, // TODO: Supabase token
      });
      const data = await res.json();

      if (!res.ok) {
        if (data?.detail?.error === "plan_limit") {
          setError("Plan gratuito: máximo 2 PDFs. Pasate al plan Advance para analizar más presupuestos.");
        } else {
          const errores = data?.detail?.errores?.map((e: {archivo: string, error: string}) => `${e.archivo}: ${e.error}`).join(" | ");
          setError(errores || data?.detail?.mensaje || JSON.stringify(data?.detail) || "Error al analizar los PDFs");
        }
        return;
      }

      // Construir sin_match por proveedor
      const sin_match: Record<string, SinMatch[]> = {};
      for (const [prov, d] of Object.entries(data.resultados as Record<string, { sin_match: SinMatch[] }>)) {
        sin_match[prov] = d.sin_match || [];
      }

      setResultado({
        comparativo: data.comparativo,
        proveedores: data.proveedores,
        sin_match,
        plan: data.plan,
        comparativa_id: data.comparativa_id,
      });
    } catch {
      setError("No se pudo conectar con el servidor de análisis.");
    } finally {
      setLoading(false);
    }
  }

  async function descargar(endpoint: string, ext: string, setLoading: (v: boolean) => void) {
    if (!resultado) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          comparativa_id: resultado.comparativa_id,
          solo_comunes: soloComunes,
          filtro_rubro: filtroRubro !== "Todos" ? filtroRubro : null,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        alert(err.detail?.mensaje || "Error al generar el archivo");
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const fecha = new Date().toISOString().slice(0, 10);
      a.href = url;
      a.download = `VectorAI_Comparativa_${fecha}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setLoading(false);
    }
  }

  const descargarSheets = () => descargar("sheets", "xlsx", setGenerandoSheets);
  const descargarPdf    = () => descargar("pdf",    "pdf",  setGenerandoPdf);
  const descargarJpg    = () => descargar("imagen", "jpg",  setGenerandoJpg);

  const rubros = resultado
    ? ["Todos", ...Array.from(new Set(resultado.comparativo.map((r) => r.rubro))).sort()]
    : [];

  const filasFiltradas = resultado?.comparativo
    .filter((r) => filtroRubro === "Todos" || r.rubro === filtroRubro)
    .filter((r) => !soloComunes || r.en_varios) ?? [];

  const ahorroTotal = filasFiltradas.reduce((s, r) => s + (r.ahorro || 0), 0);

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Nav */}
      <nav className="bg-white border-b border-gray-200 px-8 py-4 flex items-center justify-between">
        <Link href="/" className="text-lg font-bold text-gray-900">VectorAI <span className="text-xs font-semibold text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded-full align-middle">beta</span></Link>
        <div className="flex gap-3 items-center">
          <Link href="/app/revisar" className="text-sm text-gray-500 hover:text-gray-800 transition">
            Revisar sin-match
          </Link>
          <a
            href="https://wa.me/5492241410393?text=Hola%2C%20tengo%20una%20consulta%20sobre%20VectorAI"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-sm font-medium text-white bg-green-500 hover:bg-green-600 transition px-3 py-1.5 rounded-lg"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
            Consultas
          </a>
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-10">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Nueva comparativa</h1>
        <p className="text-gray-500 text-sm mb-8">Subí los PDFs de tus proveedores para compararlos</p>

        {/* Upload zone */}
        {!resultado && (
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
              id="file-input"
              type="file"
              accept="application/pdf"
              multiple
              className="hidden"
              onChange={(e) => setFiles((prev) => [...prev, ...Array.from(e.target.files || [])])}
            />
            <div className="text-4xl mb-4">📄</div>
            <p className="text-gray-600 font-medium">Arrastrá los PDFs acá o hacé click para seleccionar</p>
            <p className="text-gray-400 text-sm mt-1">Solo PDFs · Plan gratuito: máximo 2 archivos</p>
          </div>
        )}

        {/* Lista de archivos */}
        {files.length > 0 && !resultado && (
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
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-4 rounded-xl mb-6">
            {error}
            {error.includes("básico") && (
              <Link href="/registro?plan=basico" className="ml-2 font-semibold underline">
                Ver plan básico →
              </Link>
            )}
          </div>
        )}

        {!resultado && (
          <button
            onClick={analizar}
            disabled={!files.length || loading}
            className="bg-blue-600 text-white font-semibold px-8 py-3 rounded-xl hover:bg-blue-700 transition disabled:opacity-40"
          >
            {loading ? "Analizando…" : "⚡ Analizar"}
          </button>
        )}

        {/* Resultados */}
        {resultado && (
          <>
            {/* KPIs */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {[
                { label: "Proveedores", value: resultado.proveedores.length },
                { label: "Materiales", value: resultado.comparativo.length },
                { label: "En común", value: resultado.comparativo.filter((r) => r.en_varios).length },
                { label: "Ahorro potencial", value: fmt(ahorroTotal) },
              ].map((k) => (
                <div key={k.label} className="bg-white rounded-xl border border-gray-200 px-5 py-4">
                  <div className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1">{k.label}</div>
                  <div className="text-2xl font-bold text-gray-900">{k.value}</div>
                </div>
              ))}
            </div>

            {/* Botones de acción */}
            <div className="flex gap-3 mb-6 flex-wrap">
              <button
                onClick={descargarSheets}
                disabled={generandoSheets}
                className="bg-green-600 text-white font-medium px-5 py-2.5 rounded-lg hover:bg-green-700 transition text-sm disabled:opacity-50"
              >
                {generandoSheets ? "Generando…" : "↓ Excel"}
              </button>
              <button
                onClick={descargarPdf}
                disabled={generandoPdf}
                className="bg-blue-600 text-white font-medium px-5 py-2.5 rounded-lg hover:bg-blue-700 transition text-sm disabled:opacity-50"
              >
                {generandoPdf ? "Generando…" : "↓ PDF"}
              </button>
              <button
                onClick={descargarJpg}
                disabled={generandoJpg}
                className="bg-purple-600 text-white font-medium px-5 py-2.5 rounded-lg hover:bg-purple-700 transition text-sm disabled:opacity-50"
              >
                {generandoJpg ? "Generando…" : "↓ JPG"}
              </button>
              <button
                onClick={() => { setResultado(null); setFiles([]); }}
                className="border border-gray-300 text-gray-600 font-medium px-5 py-2.5 rounded-lg hover:bg-gray-50 transition text-sm"
              >
                + Nueva comparativa
              </button>
            </div>

            {/* Filtros */}
            <div className="flex gap-3 items-center mb-4 flex-wrap">
              <select
                value={filtroRubro}
                onChange={(e) => setFiltroRubro(e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              >
                {rubros.map((r) => <option key={r}>{r}</option>)}
              </select>
              <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={soloComunes}
                  onChange={(e) => setSoloComunes(e.target.checked)}
                  className="w-4 h-4 text-blue-600 rounded"
                />
                Solo ítems en común entre proveedores
              </label>
            </div>

            {/* Tabla comparativa */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="text-left px-4 py-3 font-semibold text-gray-600 min-w-[240px]">Material</th>
                    <th className="px-3 py-3 font-semibold text-gray-600 text-xs uppercase">Cant.</th>
                    {resultado.proveedores.map((p) => (
                      <th key={p} className="px-4 py-3 font-semibold text-gray-700 text-center">{p}</th>
                    ))}
                    <th className="px-4 py-3 font-semibold text-gray-600 text-center">Mejor</th>
                    <th className="px-4 py-3 font-semibold text-gray-500 text-center text-xs">Ahorro</th>
                  </tr>
                </thead>
                <tbody>
                  {filasFiltradas.map((row, i) => (
                    <tr key={i} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
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
                        const total = precio ? precio.precio_sin_iva * (row.cant || 1) : null;
                        return (
                          <td
                            key={p}
                            className={`px-4 py-3 text-center ${esMejor ? "bg-green-50" : ""}`}
                          >
                            {precio ? (
                              <div>
                                <span className={`font-medium ${esMejor ? "text-green-700 font-bold" : "text-gray-700"}`}>
                                  {fmt(total!)}
                                </span>
                                <div className="text-xs text-gray-400">
                                  {fmt(precio.precio_sin_iva)}/u · {precio.origen === "EQUIV" ? "✓" : `${precio.score.toFixed(0)}%`}
                                </div>
                              </div>
                            ) : (
                              <span className="text-gray-300">—</span>
                            )}
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
                      <td className="px-4 py-3 text-center text-xs text-gray-400">
                        {row.ahorro > 0 ? fmt(row.ahorro) : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Sin match — Human in the Loop */}
            {Object.values(resultado.sin_match).some((arr) => arr.length > 0) && (
              <div className="mt-6 bg-amber-50 border border-amber-200 rounded-xl p-5">
                <h3 className="font-semibold text-amber-800 mb-2 flex items-center gap-2">
                  ⚠️ Ítems sin match automático
                </h3>
                <p className="text-sm text-amber-700 mb-3">
                  Estos ítems no pudieron ser identificados automáticamente y no aparecen en la comparativa.
                  {resultado.plan === "free"
                    ? " En el plan Advance podés revisarlos manualmente para completar la comparativa."
                    : " Podés revisarlos manualmente en la sección de revisión."}
                </p>
                {resultado.plan !== "free" ? (
                  <Link
                    href="/app/revisar"
                    className="inline-block bg-amber-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-amber-700 transition"
                  >
                    Revisar manualmente →
                  </Link>
                ) : (
                  <Link
                    href="/registro?plan=advance"
                    className="inline-block bg-blue-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-blue-700 transition"
                  >
                    Ver plan Advance →
                  </Link>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
