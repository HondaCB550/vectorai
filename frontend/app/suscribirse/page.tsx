"use client";
export const dynamic = "force-dynamic";
import { useState, useEffect } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Suscribirse() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [user, setUser] = useState<{ id: string; email: string } | null>(null);

  useEffect(() => {
    const sb = createClient();
    sb.auth.getUser().then(({ data }) => {
      if (data.user) setUser({ id: data.user.id, email: data.user.email ?? "" });
    });
  }, []);

  async function iniciarPago() {
    if (!user) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/mp/suscripcion`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: user.id, email: user.email }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError("No se pudo iniciar el pago. Intentá de nuevo.");
        return;
      }
      window.location.href = data.init_point;
    } catch {
      setError("Error de conexión. Intentá de nuevo.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm w-full max-w-md p-10">
        <Link href="/" className="text-xl font-bold text-gray-900 block mb-8">VectorAI</Link>

        <h1 className="text-2xl font-bold text-gray-900 mb-2">Plan Advance</h1>
        <p className="text-gray-700 text-sm mb-8">
          Accedé a PDFs ilimitados, revisión manual de sin-match y comparativas sin límite diario.
        </p>

        <div className="bg-blue-50 border border-blue-100 rounded-xl p-5 mb-6">
          <div className="text-3xl font-bold text-blue-700 mb-1">
            $48.000<span className="text-base font-normal text-blue-500">/mes</span>
          </div>
          <ul className="mt-3 space-y-1.5 text-sm text-gray-700">
            {["PDFs ilimitados por análisis", "Comparativas sin límite diario", "Revisión manual de sin-match", "Descarga Excel · PDF · JPG", "Soporte directo por WhatsApp"].map((f) => (
              <li key={f} className="flex items-center gap-2">
                <span className="text-green-500 font-bold">✓</span> {f}
              </li>
            ))}
          </ul>
        </div>

        {!user && (
          <div className="bg-amber-50 border border-amber-200 text-amber-700 text-sm px-4 py-3 rounded-xl mb-4">
            Tenés que{" "}
            <Link href="/login" className="font-semibold underline">iniciar sesión</Link>
            {" "}para suscribirte.
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-xl mb-4">
            {error}
          </div>
        )}

        <button
          onClick={iniciarPago}
          disabled={loading || !user}
          className="w-full bg-blue-600 text-white font-semibold py-3 rounded-xl hover:bg-blue-700 transition disabled:opacity-50"
        >
          {loading ? "Redirigiendo a MercadoPago…" : "Suscribirme — $48.000/mes"}
        </button>

        <p className="text-xs text-gray-400 text-center mt-4">
          Podés cancelar cuando quieras desde MercadoPago.
        </p>
      </div>
    </main>
  );
}
