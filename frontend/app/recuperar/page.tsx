"use client";
export const dynamic = "force-dynamic";
import { useState, Suspense } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase";
import Footer from "@/components/Footer";
import Logo from "@/components/Logo";

const INPUT = "w-full border border-gray-300 rounded-lg px-4 py-3 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500";
const LABEL = "block text-sm font-semibold text-gray-800 mb-1";

function RecuperarInner() {
  const supabase = createClient();
  const [mail, setMail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [enviado, setEnviado] = useState(false);

  async function handleEnviar(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    // El link del mail cae DIRECTO en /actualizar-clave: el cliente Supabase
    // detecta ahí la sesión de recuperación (el code verifier del flujo PKCE
    // vive en este navegador). Enrutarlo por el callback del servidor no sirve:
    // el verifier/hash no está disponible del lado del servidor.
    const { error } = await supabase.auth.resetPasswordForEmail(mail.trim(), {
      redirectTo: `${window.location.origin}/actualizar-clave`,
    });
    setLoading(false);
    if (error) {
      const msg = (error.message || "").toLowerCase();
      if (msg.includes("rate limit") || msg.includes("too many") || msg.includes("after")) {
        setError("Esperá un minuto antes de pedir otro mail de recuperación.");
      } else {
        setError("No se pudo enviar el mail. Revisá la dirección e intentá de nuevo.");
      }
      return;
    }
    // Por privacidad, mostramos éxito exista o no la cuenta (Supabase no revela
    // si el mail está registrado).
    setEnviado(true);
  }

  return (
    <>
      <main className="min-h-screen bg-[#F5F0E8] flex items-center justify-center px-4">
        <div className="w-full max-w-md">
          <Link href="/login" className="inline-flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-[#1A2B4A] transition mb-4">
            ← Volver a iniciar sesión
          </Link>
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm w-full p-10">
            <Link href="/" className="block mb-8">
              <Logo />
            </Link>

            {!enviado ? (
              <>
                <h1 className="text-2xl font-bold mb-2">Recuperar contraseña</h1>
                <p className="text-gray-700 text-sm mb-8">
                  Ingresá el mail de tu cuenta y te enviamos un link para elegir una
                  contraseña nueva.
                </p>

                <form onSubmit={handleEnviar} className="space-y-4">
                  <div>
                    <label className={LABEL}>Mail</label>
                    <input
                      type="email"
                      value={mail}
                      onChange={(e) => setMail(e.target.value)}
                      required
                      className={INPUT}
                      placeholder="tu@mail.com"
                    />
                  </div>

                  {error && (
                    <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg">{error}</div>
                  )}

                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-blue-600 text-white font-semibold py-3 rounded-xl hover:bg-blue-700 transition disabled:opacity-50"
                  >
                    {loading ? "Enviando…" : "Enviar link de recuperación"}
                  </button>
                </form>
              </>
            ) : (
              <div className="text-center py-4">
                <h1 className="text-xl font-bold mb-2">Revisá tu mail</h1>
                <p className="text-gray-700 text-sm mb-6">
                  Si hay una cuenta asociada a <strong>{mail}</strong>, te enviamos un
                  link para crear una contraseña nueva. Revisá también la carpeta de
                  spam o promociones.
                </p>
                <Link href="/login" className="text-blue-600 text-sm font-medium hover:underline">
                  Volver a iniciar sesión
                </Link>
              </div>
            )}
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}

export default function Recuperar() {
  return (
    <Suspense>
      <RecuperarInner />
    </Suspense>
  );
}
