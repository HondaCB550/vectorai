"use client";
export const dynamic = "force-dynamic";
import { useState, useEffect } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase";
import Footer from "@/components/Footer";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Plan = {
  id: "basico" | "advance";
  nombre: string;
  precio: number;
  precioLista?: number;
  bajada: string;
  features: string[];
  destacado?: boolean;
};

const PLANES: Plan[] = [
  {
    id: "basico",
    nombre: "Inicial",
    precio: 19600,
    precioLista: 28000,
    bajada: "Para una obra. Compará los precios de todos tus rubros sin cargar nada a mano.",
    features: [
      "6 comparativas por mes",
      "🎁 8 el primer mes (2 de regalo)",
      "Hasta 5 proveedores por comparativa",
      "Hasta 10 hojas por proveedor",
      "Lista de compras por proveedor",
      "Descarga Excel y PDF",
    ],
  },
  {
    id: "advance",
    nombre: "Advance",
    precio: 48000,
    bajada: "Para quien maneja varias obras y quiere el histórico de precios por zona.",
    destacado: true,
    features: [
      "Comparativas ilimitadas",
      "Hasta 5 proveedores · 10 hojas",
      "Obras y precios por zona",
      "Mis presupuestos guardados",
      "Lista de compras por proveedor",
      "Soporte directo por WhatsApp",
    ],
  },
];

const ars = (v: number) => `$${v.toLocaleString("es-AR")}`;

export default function Suscribirse() {
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [user, setUser] = useState<{ id: string; email: string } | null>(null);

  useEffect(() => {
    const sb = createClient();
    sb.auth.getUser().then(({ data }) => {
      if (data.user) setUser({ id: data.user.id, email: data.user.email ?? "" });
    });
  }, []);

  async function iniciarPago(plan: "basico" | "advance") {
    if (!user) return;
    setLoading(plan);
    setError("");
    try {
      const res = await fetch(`${API_URL}/mp/suscripcion`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: user.id, email: user.email, plan }),
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
      setLoading(null);
    }
  }

  return (
    <>
      <main className="min-h-screen bg-gray-50 px-4 py-12">
        <div className="max-w-4xl mx-auto">
          <Link href="/" className="text-xl font-bold text-gray-900 block mb-2">VectorAI</Link>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Elegí tu plan</h1>
          <p className="text-gray-600 mb-8">Empezá con lo que necesites. Cancelás cuando quieras desde MercadoPago.</p>

          {!user && (
            <div className="bg-amber-50 border border-amber-200 text-amber-700 text-sm px-4 py-3 rounded-xl mb-6">
              Tenés que{" "}
              <Link href="/login" className="font-semibold underline">iniciar sesión</Link>
              {" "}para suscribirte.
            </div>
          )}
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-xl mb-6">
              {error}
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-6">
            {PLANES.map((plan) => (
              <div
                key={plan.id}
                className={`bg-white rounded-2xl border p-7 flex flex-col ${
                  plan.destacado ? "border-blue-300 ring-2 ring-blue-100" : "border-gray-200"
                }`}
              >
                {plan.destacado && (
                  <span className="self-start text-xs font-semibold text-blue-700 bg-blue-50 px-2.5 py-1 rounded-full mb-3">
                    Recomendado
                  </span>
                )}
                <h2 className="text-xl font-bold text-gray-900">{plan.nombre}</h2>
                <p className="text-sm text-gray-500 mt-1 mb-4 min-h-[40px]">{plan.bajada}</p>

                <div className="mb-5">
                  {plan.precioLista && (
                    <span className="text-base text-gray-400 line-through mr-2">{ars(plan.precioLista)}</span>
                  )}
                  <span className="text-3xl font-bold text-gray-900">{ars(plan.precio)}</span>
                  <span className="text-base font-normal text-gray-500">/mes</span>
                  {plan.precioLista && (
                    <div className="text-xs font-semibold text-green-600 mt-1">Precio de lanzamiento</div>
                  )}
                </div>

                <ul className="space-y-2 text-sm text-gray-700 mb-6 flex-1">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2">
                      <span className="text-green-500 font-bold">✓</span> {f}
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => iniciarPago(plan.id)}
                  disabled={loading !== null || !user}
                  className={`w-full font-semibold py-3 rounded-xl transition disabled:opacity-50 ${
                    plan.destacado
                      ? "bg-blue-600 text-white hover:bg-blue-700"
                      : "bg-gray-900 text-white hover:bg-gray-800"
                  }`}
                >
                  {loading === plan.id ? "Redirigiendo a MercadoPago…" : `Suscribirme — ${ars(plan.precio)}/mes`}
                </button>
              </div>
            ))}
          </div>

          <p className="text-xs text-gray-400 text-center mt-6">
            ¿Sos nuevo? Probá gratis con 1 comparativa antes de suscribirte.
          </p>
        </div>
      </main>
      <Footer />
    </>
  );
}
