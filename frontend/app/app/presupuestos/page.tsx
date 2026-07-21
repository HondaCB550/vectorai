"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Presupuesto = {
  id: string;
  proveedor: string;
  archivo: string;
  estado: string;
  fecha: string;
  n_items: number;
  total_sin_iva: number;
  obra?: { nombre: string; localidad?: string | null; provincia?: string | null } | null;
  con_iva: boolean;
  descuento: number;
};

type CfgSel = { con_iva: boolean; descuento: number };

type ItemDetalle = {
  texto: string;
  cantidad: number | null;
  precio: number | null;
  codigo: string | null;
  material: string;
  score: number | null;
  estado: string;
};

function fmt(v: number) {
  return `$ ${Math.round(v).toLocaleString("es-AR")}`;
}

function formatFecha(iso: string) {
  try {
    return new Date(iso).toLocaleDateString("es-AR", { day: "2-digit", month: "short", year: "numeric" });
  } catch {
    return iso;
  }
}

const BADGE: Record<string, string> = {
  MATCH:     "bg-green-100 text-green-700",
  REVISAR:   "bg-amber-100 text-amber-700",
  SIN_MATCH: "bg-red-100 text-red-700",
  CONFIRMADO: "bg-green-100 text-green-700",
};

export default function MisPresupuestos() {
  const [presupuestos, setPresupuestos] = useState<Presupuesto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [abierto, setAbierto] = useState<string | null>(null);
  const [detalle, setDetalle] = useState<Record<string, ItemDetalle[]>>({});
  const [cargandoDetalle, setCargandoDetalle] = useState<string | null>(null);
  // Selección para re-comparar: cada seleccionado lleva su config RECORDADA
  // (IVA/descuento del análisis original), editable antes de comparar
  const [sel, setSel] = useState<Record<string, CfgSel>>({});
  const [comparando, setComparando] = useState(false);
  const [borrando, setBorrando] = useState<string | null>(null);
  const router = useRouter();

  function toggleSel(p: Presupuesto) {
    setSel((prev) => {
      const next = { ...prev };
      if (next[p.id]) delete next[p.id];
      else next[p.id] = { con_iva: p.con_iva, descuento: p.descuento };
      return next;
    });
  }

  async function eliminar(p: Presupuesto) {
    if (!confirm(`¿Eliminar "${p.archivo}" de ${p.proveedor}?`)) return;
    setBorrando(p.id);
    try {
      const res = await fetch(`${API_URL}/mis-presupuestos/${p.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token!}` },
      });
      if (res.ok) {
        setPresupuestos((prev) => prev.filter((x) => x.id !== p.id));
        setSel((prev) => { const n = { ...prev }; delete n[p.id]; return n; });
      } else {
        alert("No se pudo eliminar.");
      }
    } finally {
      setBorrando(null);
    }
  }

  async function compararSeleccionados() {
    const ids = Object.keys(sel);
    if (ids.length < 1 || !token) return;
    setComparando(true);
    try {
      const res = await fetch(`${API_URL}/comparar-guardados`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ presupuesto_ids: ids, overrides: sel }),
      });
      const data = await res.json();
      if (res.ok && data.comparativa_id) {
        router.push(`/app/historial/${data.comparativa_id}`);
      } else {
        alert(data?.detail?.mensaje || "No se pudo generar la comparativa.");
      }
    } catch {
      alert("No se pudo conectar con el servidor.");
    } finally {
      setComparando(false);
    }
  }

  useEffect(() => {
    const sb = createClient();
    sb.auth.getSession().then(({ data }) => {
      const t = data.session?.access_token;
      setToken(t ?? null);
      if (!t) {
        setError("Iniciá sesión para ver tus presupuestos.");
        setLoading(false);
      }
    });
  }, []);

  useEffect(() => {
    if (!token) return;
    (async () => {
      setLoading(true);
      setError("");
      try {
        const res = await fetch(`${API_URL}/mis-presupuestos`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await res.json();
        setPresupuestos(data.presupuestos || []);
      } catch (e) {
        setError(`Error al cargar: ${e instanceof Error ? e.message : "desconocido"}`);
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  async function toggleDetalle(id: string) {
    if (abierto === id) {
      setAbierto(null);
      return;
    }
    setAbierto(id);
    if (detalle[id]) return;
    setCargandoDetalle(id);
    try {
      const res = await fetch(`${API_URL}/mis-presupuestos/${id}`, {
        headers: { Authorization: `Bearer ${token!}` },
      });
      const data = await res.json();
      setDetalle((prev) => ({ ...prev, [id]: data.items || [] }));
    } catch {
      setDetalle((prev) => ({ ...prev, [id]: [] }));
    } finally {
      setCargandoDetalle(null);
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4 sm:p-8">
        <div className="max-w-5xl mx-auto text-center">
          <p className="text-gray-600">Cargando presupuestos...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4 sm:p-8">
      <div className="max-w-5xl mx-auto">
        <div className="mb-8">
          <Link href="/app/comparar" className="text-blue-600 text-sm font-medium hover:underline mb-4 inline-block">
            ← Volver a Análisis
          </Link>
          <h1 className="text-4xl font-bold text-gray-900">Mis Presupuestos</h1>
          <p className="text-gray-600 mt-2">
            Los documentos que procesaste, con sus ítems — sin volver a subirlos.
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-5 mb-6">
            <p className="text-red-700 text-sm">{error}</p>
          </div>
        )}

        {presupuestos.length === 0 && !error ? (
          <div className="bg-white rounded-xl shadow-sm p-12 text-center">
            <p className="text-gray-600 mb-4">Todavía no procesaste ningún presupuesto.</p>
            <Link
              href="/app/comparar"
              className="inline-block bg-blue-600 text-white font-medium px-6 py-2 rounded-lg hover:bg-blue-700 transition"
            >
              Subir presupuestos →
            </Link>
          </div>
        ) : (
          <div className="space-y-8">
            {Object.entries(
              presupuestos.reduce<Record<string, Presupuesto[]>>((acc, p) => {
                const key = p.obra
                  ? `🏗️ ${p.obra.nombre}${p.obra.localidad ? ` — ${p.obra.localidad}` : ""}${p.obra.provincia ? `, ${p.obra.provincia}` : ""}`
                  : "Sin obra asignada";
                (acc[key] = acc[key] || []).push(p);
                return acc;
              }, {})
            )
              .sort(([a], [b]) => (a === "Sin obra asignada" ? 1 : b === "Sin obra asignada" ? -1 : a.localeCompare(b)))
              .map(([grupo, lista]) => (
            <div key={grupo}>
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
                {grupo} <span className="text-gray-400 font-normal normal-case">({lista.length})</span>
              </h2>
              <div className="space-y-3">
            {lista.map((p) => (
              <div key={p.id} className={`bg-white rounded-xl shadow-sm hover:shadow-md transition border ${sel[p.id] ? "border-blue-400 ring-1 ring-blue-200" : "border-gray-200"}`}>
                <div className="p-5 cursor-pointer" onClick={() => toggleDetalle(p.id)}>
                  <div className="flex justify-between items-start gap-4">
                    <input
                      type="checkbox"
                      checked={!!sel[p.id]}
                      onChange={() => toggleSel(p)}
                      onClick={(e) => e.stopPropagation()}
                      title="Seleccionar para comparar"
                      className="mt-1.5 w-5 h-5 accent-blue-600 shrink-0 cursor-pointer"
                    />
                    <div className="flex-1 min-w-0">
                      <h2 className="font-semibold text-gray-900 text-lg">{p.proveedor}</h2>
                      <p className="text-sm text-gray-600 mt-1 truncate">
                        {p.archivo} • {formatFecha(p.fecha)}
                      </p>
                      <div className="flex gap-4 mt-3 text-sm text-gray-700 flex-wrap">
                        <span>{p.n_items} ítems</span>
                        {p.total_sin_iva > 0 && <span className="font-semibold">💰 {fmt(p.total_sin_iva)} s/IVA</span>}
                        <span className="text-gray-400">
                          {p.con_iva ? "cotizó c/IVA" : "cotizó s/IVA"}{p.descuento > 0 ? ` · desc ${p.descuento}%` : ""}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        onClick={(e) => { e.stopPropagation(); eliminar(p); }}
                        disabled={borrando === p.id}
                        title="Eliminar este presupuesto"
                        className="bg-red-50 text-red-600 text-sm font-medium px-2.5 py-1.5 rounded-lg hover:bg-red-100 transition disabled:opacity-50"
                      >
                        {borrando === p.id ? "⏳" : "✕"}
                      </button>
                      <span className="text-gray-400 text-xl select-none">{abierto === p.id ? "▾" : "▸"}</span>
                    </div>
                  </div>
                </div>

                {abierto === p.id && (
                  <div className="border-t border-gray-100 px-5 pb-5">
                    {cargandoDetalle === p.id ? (
                      <p className="text-sm text-gray-500 py-4">Cargando ítems…</p>
                    ) : (
                      <div className="overflow-x-auto mt-3">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-left text-xs text-gray-400 uppercase">
                              <th className="py-1.5 pr-3">Ítem del proveedor</th>
                              <th className="py-1.5 pr-3">Material</th>
                              <th className="py-1.5 pr-3 text-right">Cant.</th>
                              <th className="py-1.5 pr-3 text-right">Precio s/IVA</th>
                              <th className="py-1.5">Estado</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(detalle[p.id] || []).map((it, i) => (
                              <tr key={i} className="border-t border-gray-50">
                                <td className="py-1.5 pr-3 text-gray-800">{it.texto}</td>
                                <td className="py-1.5 pr-3 text-gray-500">{it.material || "—"}</td>
                                <td className="py-1.5 pr-3 text-right text-gray-600">{it.cantidad ?? ""}</td>
                                <td className="py-1.5 pr-3 text-right text-gray-800">{it.precio != null ? fmt(Number(it.precio)) : ""}</td>
                                <td className="py-1.5">
                                  <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${BADGE[it.estado] || "bg-gray-100 text-gray-500"}`}>
                                    {it.estado}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
              </div>
            </div>
              ))}
          </div>
        )}
      </div>

      {/* Barra de comparación: config recordada de cada seleccionado, editable */}
      {Object.keys(sel).length > 0 && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-[0_-4px_20px_rgba(0,0,0,.08)] z-40">
          <div className="max-w-5xl mx-auto px-4 py-3">
            <div className="flex items-center gap-4 flex-wrap">
              {presupuestos.filter((p) => sel[p.id]).map((p) => (
                <div key={p.id} className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5 text-sm">
                  <span className="font-medium text-gray-800 max-w-[140px] truncate">{p.proveedor}</span>
                  <button
                    onClick={() => setSel((prev) => ({ ...prev, [p.id]: { ...prev[p.id], con_iva: !prev[p.id].con_iva } }))}
                    className={`text-xs font-semibold px-2 py-0.5 rounded-full transition ${sel[p.id].con_iva ? "bg-blue-100 text-blue-700" : "bg-gray-200 text-gray-600"}`}
                    title="El documento ¿incluía IVA?"
                  >
                    {sel[p.id].con_iva ? "c/IVA" : "s/IVA"}
                  </button>
                  <label className="flex items-center gap-1 text-xs text-gray-500">
                    desc
                    <input
                      type="number" min="0" max="99" step="0.5"
                      value={sel[p.id].descuento || ""}
                      placeholder="0"
                      onChange={(e) => setSel((prev) => ({ ...prev, [p.id]: { ...prev[p.id], descuento: Number(e.target.value) || 0 } }))}
                      className="w-14 border border-gray-300 rounded px-1.5 py-0.5 text-center"
                    />%
                  </label>
                </div>
              ))}
              <button
                onClick={compararSeleccionados}
                disabled={comparando}
                className="ml-auto bg-blue-600 text-white font-semibold px-6 py-2.5 rounded-xl hover:bg-blue-700 transition disabled:opacity-50 whitespace-nowrap"
              >
                {comparando ? "Comparando…" : `Comparar (${Object.keys(sel).length})`}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
