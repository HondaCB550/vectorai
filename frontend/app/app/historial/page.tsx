"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Comparativa = {
  id: string;
  titulo: string;
  proveedores: string[];
  n_items: number;
  n_comunes: number;
  ahorro_total: number;
  fecha: string;
};

function fmt(v: number) {
  return `$ ${Math.round(v).toLocaleString("es-AR")}`;
}

function formatFecha(iso: string) {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("es-AR", { day: "2-digit", month: "short", year: "numeric" });
  } catch {
    return iso;
  }
}

export default function Historial() {
  const [comparativas, setComparativas] = useState<Comparativa[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    const sb = createClient();
    sb.auth.getSession().then(({ data }) => {
      const t = data.session?.access_token;
      setToken(t ?? null);
      if (!t) {
        setError("Debes iniciar sesión para ver tu historial.");
        setLoading(false);
      }
    });
  }, []);

  useEffect(() => {
    if (!token) return;

    const cargar = async () => {
      setLoading(true);
      setError("");
      try {
        const res = await fetch(`${API_URL}/comparativas`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await res.json();
        setComparativas(data.comparativas || []);
      } catch (e) {
        setError(`Error al cargar historial: ${e instanceof Error ? e.message : "Unknown error"}`);
      } finally {
        setLoading(false);
      }
    };

    cargar();
  }, [token]);

  async function eliminar(id: string) {
    if (!confirm("¿Eliminar esta comparativa?")) return;
    setDeletingId(id);
    try {
      const res = await fetch(`${API_URL}/comparativas/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token!}` },
      });
      if (res.ok) {
        setComparativas((prev) => prev.filter((c) => c.id !== id));
      } else {
        alert("Error al eliminar.");
      }
    } finally {
      setDeletingId(null);
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4 sm:p-8">
        <div className="max-w-5xl mx-auto text-center">
          <p className="text-gray-600">Cargando historial...</p>
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
          <h1 className="text-4xl font-bold text-gray-900">Mis Comparativas</h1>
          <p className="text-gray-600 mt-2">Historial de análisis guardados</p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-5 mb-6">
            <p className="text-red-700 text-sm">{error}</p>
          </div>
        )}

        {comparativas.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm p-12 text-center">
            <p className="text-gray-600 mb-4">No hay comparativas guardadas aún.</p>
            <Link
              href="/app/comparar"
              className="inline-block bg-blue-600 text-white font-medium px-6 py-2 rounded-lg hover:bg-blue-700 transition"
            >
              Crear tu primera comparativa →
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {comparativas.map((c) => (
              <div
                key={c.id}
                className="bg-white rounded-xl shadow-sm hover:shadow-md transition p-5 border border-gray-200"
              >
                <div className="flex justify-between items-start gap-4">
                  <div className="flex-1 cursor-pointer hover:opacity-75" onClick={() => setSelectedId(c.id)}>
                    <h2 className="font-semibold text-gray-900 text-lg">{c.titulo}</h2>
                    <p className="text-sm text-gray-600 mt-1">
                      {c.proveedores.join(" • ")} • {formatFecha(c.fecha)}
                    </p>
                    <div className="flex gap-4 mt-3 text-sm text-gray-700">
                      <span>📊 {c.n_items} ítems</span>
                      <span>🔗 {c.n_comunes} en varios</span>
                      <span className="font-semibold text-green-600">
                        💰 Ahorro: {fmt(c.ahorro_total)}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Link
                      href={`/app/historial/${c.id}`}
                      className="bg-blue-600 text-white text-sm font-medium px-3 py-2 rounded-lg hover:bg-blue-700 transition"
                    >
                      Ver
                    </Link>
                    <button
                      onClick={() => eliminar(c.id)}
                      disabled={deletingId === c.id}
                      className="bg-red-100 text-red-700 text-sm font-medium px-3 py-2 rounded-lg hover:bg-red-200 transition disabled:opacity-50"
                    >
                      {deletingId === c.id ? "⏳" : "✕"}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
