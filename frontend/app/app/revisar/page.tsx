"use client";
import { useState } from "react";
import Link from "next/link";
import Logo from "@/components/Logo";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Esta página es el Human in the Loop:
// muestra los ítems SIN MATCH para que el usuario los ubique manualmente.
// Solo disponible en plan básico.

type ItemSinMatch = {
  cod_prov: string;
  desc_prov: string;
  proveedor: string;
  precio_sin_iva: number;
  alternativas: { cod: string; desc: string; score: number }[];
  comparativa_id: string;
};

function fmt(v: number) {
  return `$ ${Math.round(v).toLocaleString("es-AR")}`;
}

export default function Revisar() {
  const [items] = useState<ItemSinMatch[]>([
    // Demo — en producción viene de Supabase (comparativas pendientes)
    {
      cod_prov: "BK-03140423",
      desc_prov: "BANDA ACUSTICA TECNO 100MM X 25MTS",
      proveedor: "BAUKRAFT",
      precio_sin_iva: 14550,
      comparativa_id: "demo-001",
      alternativas: [
        { cod: "AISL008", desc: "BANDA ACUSTICA 100mm x 25m", score: 74 },
        { cod: "AISL009", desc: "CINTA ACUSTICA 100mm", score: 61 },
      ],
    },
    {
      cod_prov: "BK-09990001",
      desc_prov: "POLIETILENO 180MIC NEGRO FILM 4X50M",
      proveedor: "BAUKRAFT",
      precio_sin_iva: 8200,
      comparativa_id: "demo-001",
      alternativas: [
        { cod: "AISL110", desc: "FILM POLIETILENO 200 MIC", score: 68 },
        { cod: "AISL111", desc: "POLIETILENO 150MIC", score: 55 },
      ],
    },
  ]);

  const [decisiones, setDecisiones] = useState<Record<string, string>>({});
  const [codsCustom, setCodsCustom] = useState<Record<string, string>>({});
  const [guardados, setGuardados] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState<Set<string>>(new Set());

  async function confirmar(item: ItemSinMatch, cod_int: string) {
    if (!cod_int) return;
    setLoading((prev) => new Set([...prev, item.cod_prov]));
    try {
      await fetch(`${API_URL}/confirmar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cod_prov: item.cod_prov,
          desc_prov: item.desc_prov,
          cod_int,
          proveedor: item.proveedor,
          precio_sin_iva: item.precio_sin_iva,
          comparativa_id: item.comparativa_id,
        }),
      });
      setGuardados((prev) => new Set([...prev, item.cod_prov]));
    } finally {
      setLoading((prev) => { const s = new Set(prev); s.delete(item.cod_prov); return s; });
    }
  }

  const pendientes = items.filter((i) => !guardados.has(i.cod_prov));
  const completados = items.filter((i) => guardados.has(i.cod_prov));

  return (
    <main className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-4 sm:px-8 py-3 sm:py-4 flex items-center justify-between flex-wrap gap-y-2">
        <Link href="/" className="flex items-center gap-1.5">
          <Logo />
          <span className="text-xs font-semibold text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded-full align-middle">beta</span>
        </Link>
        <Link href="/app/comparar" className="text-sm text-blue-600 hover:underline">← Volver a comparativas</Link>
      </nav>

      <div className="max-w-3xl mx-auto px-6 py-10">
        <h1 className="text-2xl font-bold mb-2">Revisión manual</h1>
        <p className="text-gray-500 text-sm mb-8">
          Estos ítems no pudieron ser identificados automáticamente. Confirmá a qué material
          interno corresponde cada uno para completar la comparativa. Cada confirmación mejora
          el sistema para todos.
        </p>

        {pendientes.length === 0 && (
          <div className="bg-green-50 border border-green-200 rounded-xl p-6 text-center mb-6">
            <p className="text-green-700 font-medium">¡Todos los ítems revisados!</p>
            <Link href="/app/comparar" className="text-blue-600 text-sm hover:underline mt-2 inline-block">
              Ver la comparativa actualizada →
            </Link>
          </div>
        )}

        <div className="space-y-4">
          {pendientes.map((item) => {
            const seleccion = decisiones[item.cod_prov];
            const isLoading = loading.has(item.cod_prov);

            return (
              <div key={item.cod_prov} className="bg-white rounded-xl border border-gray-200 p-5">
                <div className="flex items-start gap-3 mb-4">
                  <span className="bg-amber-100 text-amber-700 text-xs font-bold px-2 py-1 rounded">{item.proveedor}</span>
                  <div className="flex-1">
                    <div className="font-medium text-gray-900">{item.desc_prov}</div>
                    <div className="text-xs text-gray-400 mt-0.5">
                      Cód. proveedor: {item.cod_prov} · {fmt(item.precio_sin_iva)} s/IVA
                    </div>
                  </div>
                </div>

                <p className="text-xs text-gray-500 mb-3 font-medium uppercase tracking-wide">
                  ¿A qué material corresponde?
                </p>

                {/* Alternativas propuestas */}
                <div className="space-y-2 mb-4">
                  {item.alternativas.map((alt) => (
                    <label key={alt.cod} className="flex items-center gap-3 cursor-pointer p-3 rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition">
                      <input
                        type="radio"
                        name={`item-${item.cod_prov}`}
                        value={alt.cod}
                        checked={seleccion === alt.cod}
                        onChange={() => setDecisiones((prev) => ({ ...prev, [item.cod_prov]: alt.cod }))}
                        className="w-4 h-4 text-blue-600"
                      />
                      <div className="flex-1">
                        <span className="font-medium text-gray-800 text-sm">{alt.desc}</span>
                        <span className="ml-2 text-xs text-gray-400">({alt.cod})</span>
                      </div>
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${alt.score >= 70 ? "bg-yellow-100 text-yellow-700" : "bg-gray-100 text-gray-500"}`}>
                        {alt.score}% similar
                      </span>
                    </label>
                  ))}

                  {/* Opción manual */}
                  <label className="flex items-center gap-3 cursor-pointer p-3 rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition">
                    <input
                      type="radio"
                      name={`item-${item.cod_prov}`}
                      value="manual"
                      checked={seleccion === "manual"}
                      onChange={() => setDecisiones((prev) => ({ ...prev, [item.cod_prov]: "manual" }))}
                      className="w-4 h-4 text-blue-600"
                    />
                    <span className="text-sm text-gray-600">Otro código (ingresar manualmente)</span>
                  </label>

                  {seleccion === "manual" && (
                    <input
                      type="text"
                      placeholder="Ej: EST001"
                      value={codsCustom[item.cod_prov] || ""}
                      onChange={(e) => setCodsCustom((prev) => ({ ...prev, [item.cod_prov]: e.target.value }))}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  )}

                  {/* Ignorar */}
                  <label className="flex items-center gap-3 cursor-pointer p-3 rounded-lg border border-gray-200 hover:border-gray-300 transition">
                    <input
                      type="radio"
                      name={`item-${item.cod_prov}`}
                      value="ignorar"
                      checked={seleccion === "ignorar"}
                      onChange={() => setDecisiones((prev) => ({ ...prev, [item.cod_prov]: "ignorar" }))}
                      className="w-4 h-4 text-gray-400"
                    />
                    <span className="text-sm text-gray-400">No incluir en la comparativa</span>
                  </label>
                </div>

                {seleccion && seleccion !== "ignorar" && (
                  <button
                    onClick={() => {
                      const cod = seleccion === "manual" ? codsCustom[item.cod_prov] : seleccion;
                      if (cod) confirmar(item, cod);
                    }}
                    disabled={isLoading || (seleccion === "manual" && !codsCustom[item.cod_prov])}
                    className="bg-blue-600 text-white text-sm font-medium px-5 py-2 rounded-lg hover:bg-blue-700 transition disabled:opacity-40"
                  >
                    {isLoading ? "Guardando…" : "✓ Confirmar"}
                  </button>
                )}
                {seleccion === "ignorar" && (
                  <button
                    onClick={() => setGuardados((prev) => new Set([...prev, item.cod_prov]))}
                    className="text-gray-500 text-sm font-medium px-5 py-2 rounded-lg border border-gray-300 hover:bg-gray-50 transition"
                  >
                    Ignorar este ítem
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {completados.length > 0 && (
          <div className="mt-8">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
              Revisados ({completados.length})
            </h2>
            {completados.map((item) => (
              <div key={item.cod_prov} className="flex items-center gap-2 py-2 text-sm text-gray-400">
                <span className="text-green-500">✓</span>
                {item.desc_prov}
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
