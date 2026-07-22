"use client";
import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";
import { esAdmin } from "@/lib/admin";
import { HORAS_PROYECTO } from "@/lib/horasProyecto";
import Logo from "@/components/Logo";
import UserMenu from "@/components/UserMenu";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Metrics = {
  usuarios: { total: number; por_plan: Record<string, number>; activos: number; pagos: number };
  mrr: number;
  arpu: number;
  conversion_pago_pct: number;
  comparativas_total: number;
  presupuestos_total: number;
  ahorro_generado: number;
  crecimiento_usuarios: { mes: string; nuevos: number; acumulado: number }[];
  usuarios_por_zona: { zona: string; usuarios: number }[];
  facturacion_por_mes: { mes: string; monto: number }[];
  ocr: { llamadas: number; costo_usd_estimado: number; por_mes: { mes: string; n: number }[] };
  catalogo: { maestro: number; aliases: number; precios_historicos: number; pendientes: number };
  catalogo_por_dia: { dia: string; maestro: number; aliases: number; precios: number }[];
  precios_plan: Record<string, number>;
};

const ars = (v: number) => `$ ${Math.round(v).toLocaleString("es-AR")}`;
const usd = (v: number) => `US$ ${v.toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const num = (v: number) => v.toLocaleString("es-AR");

function KPI({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: boolean }) {
  return (
    <div className={`rounded-xl border p-4 ${accent ? "bg-orange-50 border-orange-200" : "bg-white border-gray-200"}`}>
      <div className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide flex items-center gap-1.5">
        {accent && <span className="inline-block w-1.5 h-1.5 rounded-full bg-orange-500" />}
        {label}
      </div>
      <div className={`text-2xl font-bold mt-1 leading-tight ${accent ? "text-orange-700" : "text-gray-900"}`}>{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
    </div>
  );
}

const hs = (v: number) => `${v.toLocaleString("es-AR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} h`;

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold mb-4">{title}</h3>
      {children}
    </div>
  );
}

function BarsH({ data, fmt }: { data: { label: string; value: number }[]; fmt?: (v: number) => string }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  if (!data.length) return <p className="text-sm text-gray-400">Sin datos.</p>;
  return (
    <div className="space-y-2">
      {data.map((d) => (
        <div key={d.label} className="flex items-center gap-3 text-sm">
          <div className="w-32 shrink-0 text-gray-600 truncate" title={d.label}>{d.label}</div>
          <div className="flex-1 bg-gray-100 rounded h-6">
            <div className="h-6 rounded bg-blue-800" style={{ width: `${(d.value / max) * 100}%` }} />
          </div>
          <div className="w-20 text-right text-gray-800 font-medium">{fmt ? fmt(d.value) : num(d.value)}</div>
        </div>
      ))}
    </div>
  );
}

function LineChart({ points, labels }: { points: number[]; labels: string[] }) {
  const w = 560, h = 200, pad = 34;
  if (points.length === 0) return <p className="text-sm text-gray-400">Sin datos todavía.</p>;
  const max = Math.max(1, ...points);
  const xAt = (i: number) => pad + (points.length <= 1 ? (w - 2 * pad) / 2 : (i / (points.length - 1)) * (w - 2 * pad));
  const yAt = (v: number) => h - pad - (v / max) * (h - 2 * pad);
  const line = points.map((v, i) => `${i === 0 ? "M" : "L"} ${xAt(i).toFixed(1)} ${yAt(v).toFixed(1)}`).join(" ");
  const area = `${line} L ${xAt(points.length - 1).toFixed(1)} ${h - pad} L ${xAt(0).toFixed(1)} ${h - pad} Z`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img">
      <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="#e5e7eb" />
      <path d={area} fill="#1e40af" fillOpacity="0.08" />
      <path d={line} fill="none" stroke="#1e40af" strokeWidth="2.5" />
      {points.map((v, i) => (
        <g key={i}>
          <circle cx={xAt(i)} cy={yAt(v)} r="3.5" fill="#1e40af" />
          <text x={xAt(i)} y={yAt(v) - 8} textAnchor="middle" fontSize="11" fill="#374151">{num(v)}</text>
          <text x={xAt(i)} y={h - pad + 16} textAnchor="middle" fontSize="10" fill="#9ca3af">{labels[i]}</text>
        </g>
      ))}
    </svg>
  );
}

// Series del catálogo: color fijo por entidad (paleta validada CVD, no cambiar el orden)
const SERIES_CATALOGO = [
  { key: "aliases" as const, label: "Aliases aprendidos", color: "#E87022" },
  { key: "precios" as const, label: "Precios históricos", color: "#0D9488" },
  { key: "maestro" as const, label: "Catálogo maestro", color: "#2563EB" },
];

function MultiLineChart({ rows }: { rows: { dia: string; maestro: number; aliases: number; precios: number }[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const w = 560, h = 220, padL = 44, padR = 96, padY = 26;
  if (rows.length < 2) return <p className="text-sm text-gray-400">Sin datos todavía.</p>;
  const max = Math.max(1, ...rows.map((r) => Math.max(r.maestro, r.aliases, r.precios)));
  const xAt = (i: number) => padL + (i / (rows.length - 1)) * (w - padL - padR);
  const yAt = (v: number) => h - padY - (v / max) * (h - 2 * padY);
  const fecha = (d: string) => `${d.slice(8, 10)}/${d.slice(5, 7)}`;
  const cadaN = Math.max(1, Math.ceil(rows.length / 7));
  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * w;
    const i = Math.round(((x - padL) / (w - padL - padR)) * (rows.length - 1));
    setHover(Math.max(0, Math.min(rows.length - 1, i)));
  };
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img" onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
        {[0.5, 1].map((f) => (
          <g key={f}>
            <line x1={padL} y1={yAt(max * f)} x2={w - padR} y2={yAt(max * f)} stroke="#f3f4f6" />
            <text x={padL - 6} y={yAt(max * f) + 3} textAnchor="end" fontSize="9" fill="#9ca3af">{num(Math.round(max * f))}</text>
          </g>
        ))}
        <line x1={padL} y1={h - padY} x2={w - padR} y2={h - padY} stroke="#e5e7eb" />
        {rows.map((r, i) => (i % cadaN === 0 || i === rows.length - 1) && (
          <text key={r.dia} x={xAt(i)} y={h - padY + 14} textAnchor="middle" fontSize="9" fill="#9ca3af">{fecha(r.dia)}</text>
        ))}
        {SERIES_CATALOGO.map((s) => {
          const line = rows.map((r, i) => `${i === 0 ? "M" : "L"} ${xAt(i).toFixed(1)} ${yAt(r[s.key]).toFixed(1)}`).join(" ");
          const fin = rows[rows.length - 1][s.key];
          return (
            <g key={s.key}>
              <path d={line} fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round" />
              <circle cx={xAt(rows.length - 1)} cy={yAt(fin)} r="3" fill={s.color} stroke="#fff" strokeWidth="1.5" />
              <text x={xAt(rows.length - 1) + 8} y={yAt(fin) + 3} fontSize="10" fontWeight="600" fill="#374151">{num(fin)}</text>
            </g>
          );
        })}
        {hover !== null && (
          <g>
            <line x1={xAt(hover)} y1={padY - 8} x2={xAt(hover)} y2={h - padY} stroke="#9ca3af" strokeDasharray="3 3" />
            {SERIES_CATALOGO.map((s) => (
              <circle key={s.key} cx={xAt(hover)} cy={yAt(rows[hover][s.key])} r="3.5" fill={s.color} stroke="#fff" strokeWidth="1.5" />
            ))}
          </g>
        )}
      </svg>
      {hover !== null && (
        <div className="absolute top-0 left-2 bg-white border border-gray-200 rounded-lg shadow-sm px-3 py-2 text-xs pointer-events-none">
          <div className="font-semibold text-gray-700 mb-1">{fecha(rows[hover].dia)}</div>
          {SERIES_CATALOGO.map((s) => (
            <div key={s.key} className="flex items-center gap-1.5 text-gray-600">
              <span className="inline-block w-2 h-2 rounded-full" style={{ background: s.color }} />
              {s.label}: <span className="font-medium text-gray-800">{num(rows[hover][s.key])}</span>
            </div>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-4 mt-2 text-xs text-gray-600">
        {SERIES_CATALOGO.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-0.5 rounded" style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function BarsV({ data, fmt }: { data: { label: string; value: number }[]; fmt?: (v: number) => string }) {
  const w = 560, h = 200, pad = 34;
  if (!data.length) return <p className="text-sm text-gray-400">Sin datos todavía — se registran desde ahora.</p>;
  const max = Math.max(1, ...data.map((d) => d.value));
  const bw = (w - 2 * pad) / data.length;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img">
      <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="#e5e7eb" />
      {data.map((d, i) => {
        const bh = (d.value / max) * (h - 2 * pad);
        const x = pad + i * bw + bw * 0.15;
        return (
          <g key={d.label}>
            <rect x={x} y={h - pad - bh} width={bw * 0.7} height={bh} rx="3" fill="#1e40af" />
            <text x={x + bw * 0.35} y={h - pad - bh - 6} textAnchor="middle" fontSize="10" fill="#374151">
              {fmt ? fmt(d.value) : num(d.value)}
            </text>
            <text x={x + bw * 0.35} y={h - pad + 16} textAnchor="middle" fontSize="10" fill="#9ca3af">{d.label}</text>
          </g>
        );
      })}
    </svg>
  );
}

const NOMBRE_PLAN: Record<string, string> = { free: "Free", basico: "Inicial", advance: "Advance", pro: "Pro" };

export default function MetricasPage() {
  const [data, setData] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const router = useRouter();

  const cargar = useCallback((token: string) => {
    setLoading(true);
    fetch(`${API_URL}/admin/metrics`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : Promise.reject(r)))
      .then((d) => { setData(d); setError(""); })
      .catch(() => setError("No se pudieron cargar las métricas."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const sb = createClient();
    sb.auth.getSession().then(({ data: s }) => {
      const email = s.session?.user?.email;
      if (!esAdmin(email)) { router.replace("/app/comparar"); return; }
      const t = s.session?.access_token;
      if (!t) { router.replace("/login"); return; }
      cargar(t);
    });
  }, [router, cargar]);

  const recargar = () => {
    createClient().auth.getSession().then(({ data: s }) => {
      const t = s.session?.access_token;
      if (t) cargar(t);
    });
  };

  const planes = data
    ? Object.entries({ free: 0, basico: 0, advance: 0, pro: 0, ...data.usuarios.por_plan })
        .map(([k, v]) => ({ label: NOMBRE_PLAN[k] || k, value: v }))
        .sort((a, b) => b.value - a.value)
    : [];

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Logo />
            <span className="text-sm font-semibold text-gray-700">Métricas del negocio</span>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/app/admin" className="text-sm text-blue-800 hover:underline">← Panel admin</Link>
            <button onClick={recargar} className="text-sm text-gray-600 hover:text-gray-900">Recargar</button>
            <UserMenu />
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6">
        {loading && <p className="text-gray-500">Cargando métricas…</p>}
        {error && <p className="text-red-600">{error}</p>}

        {data && !loading && (
          <div className="space-y-6">
            {/* KPIs */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <KPI label="Usuarios" value={num(data.usuarios.total)} sub={`${num(data.usuarios.activos)} activos`} />
              <KPI label="Usuarios pagos" value={num(data.usuarios.pagos)} sub={`Conversión ${data.conversion_pago_pct}%`} />
              <KPI label="MRR" value={ars(data.mrr)} sub="ingreso recurrente / mes" />
              <KPI label="ARPU" value={ars(data.arpu)} sub="ingreso prom. / usuario" />
              <KPI label="Comparativas" value={num(data.comparativas_total)} sub="realizadas (histórico)" />
              <KPI label="Presupuestos" value={num(data.presupuestos_total)} sub="subidos" />
              <KPI label="Ahorro generado" value={ars(data.ahorro_generado)} sub="a los usuarios (vigente)" />
              <KPI label="Costo OCR" value={usd(data.ocr.costo_usd_estimado)} sub={`${num(data.ocr.llamadas)} llamadas de visión`} />
              <KPI label="Catálogo maestro" value={num(data.catalogo?.maestro ?? 0)} sub="materiales validados" />
              <KPI
                label="Aliases aprendidos"
                value={num(data.catalogo?.aliases ?? 0)}
                sub={`${num(data.catalogo?.pendientes ?? 0)} pendientes de revisión`}
              />
              <KPI label="Precios históricos" value={num(data.catalogo?.precios_historicos ?? 0)} sub="puntos material × proveedor" />
              <KPI
                label="Horas de desarrollo"
                value={hs(HORAS_PROYECTO.total)}
                sub={`${hs(HORAS_PROYECTO.semana)} última semana · act. ${HORAS_PROYECTO.actualizado}`}
                accent
              />
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              <Card title="Usuarios por plan">
                <BarsH data={planes} />
              </Card>
              <Card title="Usuarios por zona del país">
                <BarsH data={data.usuarios_por_zona.map((z) => ({ label: z.zona, value: z.usuarios }))} />
              </Card>
            </div>

            <Card title="Crecimiento de usuarios (acumulado)">
              <LineChart
                points={data.crecimiento_usuarios.map((c) => c.acumulado)}
                labels={data.crecimiento_usuarios.map((c) => c.mes)}
              />
            </Card>

            <Card title="Crecimiento del catálogo (acumulado por día)">
              <MultiLineChart rows={data.catalogo_por_dia ?? []} />
            </Card>

            <div className="grid md:grid-cols-2 gap-6">
              <Card title="Facturación por mes">
                <BarsV data={data.facturacion_por_mes.map((f) => ({ label: f.mes, value: f.monto }))} fmt={ars} />
              </Card>
              <Card title="Uso de OCR / visión por mes">
                <BarsV data={data.ocr.por_mes.map((o) => ({ label: o.mes, value: o.n }))} />
              </Card>
            </div>

            <Card title="Retención / churn (próximamente)">
              <p className="text-sm text-gray-500">
                La retención (usuarios que renuevan mes a mes) y el churn se calculan a partir del
                histórico de altas y bajas de suscripción, que empezó a registrarse ahora. Van a aparecer
                acá en cuanto haya al menos dos meses de datos de renovaciones.
              </p>
            </Card>

            <p className="text-xs text-gray-400">
              Precios usados para el MRR: {Object.entries(data.precios_plan).filter(([, v]) => v > 0).map(([k, v]) => `${NOMBRE_PLAN[k] || k} ${ars(v)}`).join(" · ") || "sin planes pagos con precio definido"}.
              El histórico de facturación y OCR arranca desde hoy.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
