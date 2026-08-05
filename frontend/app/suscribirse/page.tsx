"use client";
export const dynamic = "force-dynamic";
import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase";
import Footer from "@/components/Footer";
import Logo from "@/components/Logo";

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
      "8 el primer mes (2 de regalo)",
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
      "Hasta 10 proveedores · 10 hojas",
      "Obras y precios por zona",
      "Mis presupuestos y comparativas guardados 30 días, separados por obra",
      "Lista de compras por proveedor",
      "Soporte prioritario por WhatsApp",
    ],
  },
];

const ars = (v: number) => `$${v.toLocaleString("es-AR")}`;

function SuscribirseInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [user, setUser] = useState<{ id: string; email: string } | null>(null);

  // Código promocional: viene por URL (?codigo=X, link de influencer) o quedó
  // guardado en localStorage desde /registro. Se canjea logueado.
  const [codigo, setCodigo] = useState("");
  const [promoMsg, setPromoMsg] = useState("");
  const [promoErr, setPromoErr] = useState("");
  const [canjeando, setCanjeando] = useState(false);

  useEffect(() => {
    const deUrl = (params.get("codigo") || "").trim().toUpperCase();
    if (deUrl) {
      setCodigo(deUrl);
      try { localStorage.setItem("va_promo", deUrl); } catch {}
    } else {
      try { setCodigo((localStorage.getItem("va_promo") || "").toUpperCase()); } catch {}
    }
  }, [params]);

  useEffect(() => {
    const sb = createClient();
    sb.auth.getUser().then(({ data }) => {
      if (data.user) setUser({ id: data.user.id, email: data.user.email ?? "" });
    });
  }, []);

  async function canjearCodigo() {
    const cod = codigo.trim().toUpperCase();
    if (!cod || canjeando) return;
    setCanjeando(true);
    setPromoErr("");
    setPromoMsg("");
    try {
      const sb = createClient();
      const { data: sess } = await sb.auth.getSession();
      if (!sess.session) {
        router.push(`/login?from=${encodeURIComponent(`/suscribirse?codigo=${cod}`)}`);
        return;
      }
      const res = await fetch(`${API_URL}/promo/canjear`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${sess.session.access_token}`,
        },
        body: JSON.stringify({ codigo: cod }),
      });
      const data = await res.json();
      if (!res.ok) {
        setPromoErr(data?.detail?.mensaje || "No se pudo canjear el código. Revisalo e intentá de nuevo.");
        return;
      }
      try { localStorage.removeItem("va_promo"); } catch {}
      const hasta = data.hasta ? new Date(data.hasta).toLocaleDateString("es-AR") : "";
      setPromoMsg(
        `Listo: tenés el plan ${data.plan === "basico" ? "Inicial" : "Advance"} gratis por ${data.meses === 1 ? "1 mes" : `${data.meses} meses`}${hasta ? ` (hasta el ${hasta})` : ""}. Te llevamos al comparador…`
      );
      setTimeout(() => router.push("/app/comparar"), 2500);
    } catch {
      setPromoErr("Error de conexión. Intentá de nuevo.");
    } finally {
      setCanjeando(false);
    }
  }

  async function iniciarPago(plan: "basico" | "advance") {
    if (!user) return;
    setLoading(plan);
    setError("");
    try {
      // El API saca el user_id y el email del token, no del body: el endpoint
      // era anónimo y se podían crear suscripciones a nombre de terceros.
      const sb = createClient();
      const { data: sess } = await sb.auth.getSession();
      const res = await fetch(`${API_URL}/mp/suscripcion`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(sess.session?.access_token
            ? { Authorization: `Bearer ${sess.session.access_token}` }
            : {}),
        },
        body: JSON.stringify({ plan }),
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
          <Link href="/" className="inline-block mb-3"><Logo /></Link>
          <h1 className="text-3xl font-bold mb-2">Elegí tu plan</h1>
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

          {/* Código promocional */}
          <div className="bg-white border border-gray-200 rounded-2xl p-5 mb-8">
            <h2 className="text-sm font-semibold text-gray-800 mb-1">¿Tenés un código?</h2>
            <p className="text-xs text-gray-500 mb-3">
              Canjealo y usá Vectorai gratis durante el período del código. Sin tarjeta.
            </p>
            {promoMsg ? (
              <div className="bg-green-50 border border-green-200 text-green-700 text-sm px-4 py-3 rounded-xl">
                {promoMsg}
              </div>
            ) : (
              <>
                <div className="flex gap-2 flex-wrap">
                  <input
                    type="text"
                    value={codigo}
                    onChange={(e) => setCodigo(e.target.value.toUpperCase())}
                    placeholder="Ej: AMIGOS2026"
                    className="flex-1 min-w-48 border border-gray-300 rounded-xl px-4 py-2.5 text-sm text-gray-900 uppercase tracking-wide placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    onClick={canjearCodigo}
                    disabled={!codigo.trim() || canjeando}
                    className="bg-gray-900 text-white text-sm font-semibold px-5 py-2.5 rounded-xl hover:bg-gray-800 transition disabled:opacity-50"
                  >
                    {canjeando ? "Canjeando…" : user ? "Canjear" : "Iniciar sesión y canjear"}
                  </button>
                </div>
                {promoErr && (
                  <div className="text-red-600 text-sm mt-2">{promoErr}</div>
                )}
              </>
            )}
          </div>

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
                <h2 className="text-xl font-bold">{plan.nombre}</h2>
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
                      <span style={{ color: "#E87022" }} className="font-bold leading-6">•</span> {f}
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

export default function Suscribirse() {
  return (
    <Suspense>
      <SuscribirseInner />
    </Suspense>
  );
}
