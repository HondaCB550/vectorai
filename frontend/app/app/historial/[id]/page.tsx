"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { createClient } from "@/lib/supabase";

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

type ComparativaDetalle = {
  id: string;
  titulo: string;
  proveedores: string[];
  comparativo: FilaComparativa[];
  fecha: string;
};

function fmt(v: number) {
  return `$ ${Math.round(v).toLocaleString("es-AR")}`;
}

export default function ComparativaDetalle() {
  const params = useParams();
  const id = params?.id as string;

  const [comparativa, setComparativa] = useState<ComparativaDetalle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [filtroRubro, setFiltroRubro] = useState("Todos");
  const [soloComunes, setSoloComunes] = useState(false);
  const [generandoSheets, setGenerandoSheets] = useState(false);

  useEffect(() => {
    const sb = createClient();
    sb.auth.getSession().then(({ data }) => {
      setToken(data.session?.access_token ?? null);
    });
  }, []);

  useEffect(() => {
    if (!token || !id) return;

    const cargar = async () => {
      setLoading(true);
      setError("");
      try {
        const res = await fetch(`${API_URL}/comparativas/${id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
          setError("Comparativa no encontrada o expirada.");
          return;
        }
        const data = await res.json();
        setComparativa(data);
      } catch (e) {
        setError(`Error: ${e instanceof Error ? e.message : "Unknown error"}`);
      } finally {
        setLoading(false);
      }
    };

    cargar();
  }, [token, id]);

  if (loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
        <div className="max-w-7xl mx-auto text-center">
          <p className="text-gray-600">Cargando comparativa...</p>
        </div>
      </main>
    );
  }

  if (error || !comparativa) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
        <div className="max-w-7xl mx-auto">
          <Link href="/app/historial" className="text-blue-600 text-sm font-medium hover:underline mb-4 inline-block">
            ← Volver al historial
          </Link>
          <div className="bg-red-50 border border-red-200 rounded-xl p-8 text-center">
            <p className="text-red-700">{error || "Comparativa no encontrada."}</p>
          </div>
        </div>
      </main>
    );
  }

  if (!comparativa) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
        <div className="max-w-7xl mx-auto">
          <Link href="/app/historial" className="text-blue-600 text-sm font-medium hover:underline mb-4 inline-block">
            ← Volver al historial
          </Link>
          <div className="bg-red-50 border border-red-200 rounded-xl p-8 text-center">
            <p className="text-red-700">Comparativa no encontrada.</p>
          </div>
        </div>
      </main>
    );
  }

  const filas = comparativa.comparativo || [];
  const rubros = Array.from(new Set(filas.map((r) => r.rubro)));
  const filtradas =
    filtroRubro === "Todos" ? filas : filas.filter((r) => r.rubro === filtroRubro);
  const mostradas = soloComunes ? filtradas.filter((r) => r.en_varios) : filtradas;
  const totalAhorro = mostradas.reduce((s, r) => s + r.ahorro, 0);

  async function descargarExcel() {
    if (!token || !comparativa) return;
    setGenerandoSheets(true);
    try {
      const res = await fetch(`${API_URL}/sheets`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          comparativa_id: comparativa.id,
          titulo: comparativa.titulo,
          solo_comunes: soloComunes,
          filtro_rubro: filtroRubro,
        }),
      });
      if (!res.ok) throw new Error("Error descargando Excel");

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${comparativa.titulo}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(`Error: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setGenerandoSheets(false);
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
      <div className="max-w-7xl mx-auto">
        <Link href="/app/historial" className="text-blue-600 text-sm font-medium hover:underline mb-4 inline-block">
          ← Volver al historial
        </Link>

        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">{comparativa.titulo}</h1>
          <p className="text-gray-600 mt-1">{comparativa.proveedores.join(" • ")}</p>
        </div>

        {/* Filtros */}
        <div className="bg-white rounded-xl shadow-sm p-5 mb-6 border border-gray-200 flex gap-4 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Rubro</label>
            <select
              value={filtroRubro}
              onChange={(e) => setFiltroRubro(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-800"
            >
              <option>Todos</option>
              {rubros.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={soloComunes}
              onChange={(e) => setSoloComunes(e.target.checked)}
              className="w-4 h-4"
            />
            <span className="text-sm font-medium text-gray-700">Solo en varios proveedores</span>
          </label>
          <button
            onClick={descargarExcel}
            disabled={generandoSheets}
            className="ml-auto bg-blue-600 text-white font-medium px-4 py-2 rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
          >
            {generandoSheets ? "⏳ Generando..." : "📥 Descargar Excel"}
          </button>
        </div>

        {/* KPI */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-blue-500">
            <p className="text-gray-600 text-sm">Ítems</p>
            <p className="text-2xl font-bold text-gray-900">{mostradas.length}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-green-500">
            <p className="text-gray-600 text-sm">Ahorro potencial</p>
            <p className="text-2xl font-bold text-green-600">{fmt(totalAhorro)}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-purple-500">
            <p className="text-gray-600 text-sm">En varios proveedores</p>
            <p className="text-2xl font-bold text-gray-900">
              {mostradas.filter((r) => r.en_varios).length}
            </p>
          </div>
        </div>

        {/* Tabla */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden border border-gray-200">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-5 py-3 text-left font-semibold text-gray-900">Material</th>
                  <th className="px-5 py-3 text-left font-semibold text-gray-900">Rubro</th>
                  {comparativa.proveedores.map((p) => (
                    <th key={p} className="px-5 py-3 text-left font-semibold text-gray-900">
                      {p}
                    </th>
                  ))}
                  <th className="px-5 py-3 text-left font-semibold text-gray-900">Mejor</th>
                  <th className="px-5 py-3 text-right font-semibold text-gray-900">Ahorro</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {mostradas.map((row) => (
                  <tr key={row.cod_int} className="hover:bg-gray-50">
                    <td className="px-5 py-3 text-gray-900 font-medium">{row.material}</td>
                    <td className="px-5 py-3 text-gray-600">{row.rubro}</td>
                    {comparativa.proveedores.map((p) => {
                      const precio = row.precios[p];
                      return (
                        <td
                          key={p}
                          className={`px-5 py-3 ${
                            row.mejor_proveedor === p ? "bg-green-50 font-semibold text-green-700" : "text-gray-600"
                          }`}
                        >
                          {precio ? fmt(precio.precio_sin_iva) : "—"}
                        </td>
                      );
                    })}
                    <td className="px-5 py-3 text-gray-900 font-semibold">{row.mejor_proveedor}</td>
                    <td className="px-5 py-3 text-right">
                      <span className="text-green-600 font-semibold">{fmt(row.ahorro)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-gray-50 border-t-2 border-gray-200">
                <tr>
                  <td colSpan={2} className="px-5 py-3 font-semibold text-gray-900">
                    Total
                  </td>
                  <td colSpan={comparativa.proveedores.length + 2} className="px-5 py-3 text-right">
                    <span className="text-green-600 font-bold text-lg">{fmt(totalAhorro)}</span>
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      </div>
    </main>
  );
}
