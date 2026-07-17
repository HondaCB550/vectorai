"use client";

import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Punto = { fecha: string; proveedor: string; precio: number; moneda: string; unidad?: string | null };
type Data = { material: { denominacion?: string | null; descripcion?: string | null } | null; puntos: Punto[]; total: number };

const money = (v: number) => `$ ${Math.round(v).toLocaleString("es-AR")}`;

/**
 * Botón "Ver histórico de precios" para un material + modal con gráfico de
 * tendencia por proveedor. Autocontenido: maneja su propio estado y fetch a
 * GET /precios-historial/{codigo}. No renderiza nada para empalmes (emp_*).
 */
export default function HistorialPrecios({
  codInt,
  material,
  token,
}: {
  codInt: string;
  material: string;
  token: string | null;
}) {
  const [abierto, setAbierto] = useState(false);
  const [data, setData] = useState<Data | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!codInt || codInt.startsWith("emp_")) return null;

  async function abrir() {
    setAbierto(true); setData(null); setError(null); setCargando(true);
    try {
      const res = await fetch(`${API_URL}/precios-historial/${encodeURIComponent(codInt)}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(res.status === 401 ? "Iniciá sesión para ver el histórico." : "No pudimos cargar el histórico.");
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "No pudimos cargar el histórico.");
    } finally {
      setCargando(false);
    }
  }

  return (
    <>
      <button onClick={abrir} className="mt-1 text-[11px] text-[#E87022] hover:underline font-medium">
        Ver histórico de precios
      </button>

      {abierto && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center px-4" onClick={() => setAbierto(false)}>
          <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-4 mb-3">
              <div>
                <div className="text-xs font-bold text-[#E87022] uppercase tracking-wide mb-1">Histórico de precios</div>
                <h3 className="text-base font-bold text-[#1A2B4A] leading-tight">{material}</h3>
                {data?.material?.descripcion && <p className="text-xs text-gray-500">{data.material.descripcion}</p>}
              </div>
              <button onClick={() => setAbierto(false)} className="text-gray-400 hover:text-gray-700 text-2xl leading-none" aria-label="Cerrar">×</button>
            </div>

            {cargando && <p className="text-sm text-gray-500 py-12 text-center">Cargando…</p>}
            {error && <p className="text-sm text-red-600 py-12 text-center">{error}</p>}
            {data && !cargando && !error && (() => {
              const puntos = data.puntos.filter((p) => typeof p.precio === "number" && !!p.fecha);
              if (puntos.length === 0) {
                return <p className="text-sm text-gray-500 py-12 text-center">Todavía no hay precios históricos registrados para este material.</p>;
              }
              const COLORES = ["#E87022", "#1A2B4A", "#2E9E6B", "#C0392B", "#8E44AD", "#2980B9"];
              const t = (f: string) => new Date(f + "T00:00:00").getTime();
              const provs = Array.from(new Set(puntos.map((p) => p.proveedor || "—")));
              const ts = puntos.map((p) => t(p.fecha));
              const precios = puntos.map((p) => p.precio);
              const minT = Math.min(...ts), maxT = Math.max(...ts);
              const minP = Math.min(...precios), maxP = Math.max(...precios);
              const loP = minP * 0.96, hiP = (maxP * 1.04) || 1;
              const W = 620, H = 300, ml = 68, mr = 16, mt = 16, mb = 40;
              const iw = W - ml - mr, ih = H - mt - mb;
              const x = (tt: number) => (maxT === minT ? ml + iw / 2 : ml + ((tt - minT) / (maxT - minT)) * iw);
              const y = (pp: number) => (hiP === loP ? mt + ih / 2 : mt + (1 - (pp - loP) / (hiP - loP)) * ih);
              const fFecha = (f: string) => { const d = new Date(f + "T00:00:00"); return `${d.getDate()}/${d.getMonth() + 1}/${String(d.getFullYear()).slice(2)}`; };
              return (
                <div>
                  <div className="overflow-x-auto">
                    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ minWidth: 420 }}>
                      {[0, 0.5, 1].map((f, k) => {
                        const val = loP + (hiP - loP) * (1 - f);
                        const yy = mt + f * ih;
                        return (
                          <g key={k}>
                            <line x1={ml} y1={yy} x2={W - mr} y2={yy} stroke="#eee" strokeWidth={1} />
                            <text x={ml - 8} y={yy + 3} textAnchor="end" fontSize={10} fill="#999">{money(val)}</text>
                          </g>
                        );
                      })}
                      {provs.map((pv, pi) => {
                        const serie = puntos.filter((p) => (p.proveedor || "—") === pv).sort((a, b) => t(a.fecha) - t(b.fecha));
                        const col = COLORES[pi % COLORES.length];
                        const pts = serie.map((p) => `${x(t(p.fecha))},${y(p.precio)}`).join(" ");
                        return (
                          <g key={pv}>
                            {serie.length > 1 && <polyline points={pts} fill="none" stroke={col} strokeWidth={2} />}
                            {serie.map((p, j) => <circle key={j} cx={x(t(p.fecha))} cy={y(p.precio)} r={3.5} fill={col} />)}
                          </g>
                        );
                      })}
                      <text x={ml} y={H - 12} textAnchor="start" fontSize={10} fill="#999">{fFecha(puntos[0].fecha)}</text>
                      <text x={W - mr} y={H - 12} textAnchor="end" fontSize={10} fill="#999">{fFecha(puntos[puntos.length - 1].fecha)}</text>
                    </svg>
                  </div>
                  <div className="flex flex-wrap gap-3 mt-3">
                    {provs.map((pv, pi) => (
                      <div key={pv} className="flex items-center gap-1.5 text-xs text-gray-600">
                        <span className="inline-block w-3 h-3 rounded-sm" style={{ background: COLORES[pi % COLORES.length] }} />
                        {pv}
                      </div>
                    ))}
                  </div>
                  <p className="text-[11px] text-gray-400 mt-3">{puntos.length} registro{puntos.length === 1 ? "" : "s"} · precios sin IVA</p>
                </div>
              );
            })()}
          </div>
        </div>
      )}
    </>
  );
}
