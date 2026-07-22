"use client";
export const dynamic = "force-dynamic";
import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase";
import Footer from "@/components/Footer";
import Logo from "@/components/Logo";

function LoginInner() {
  const router = useRouter();
  const params = useSearchParams();
  const supabase = createClient();
  // Si ya hay sesión VÁLIDA, no pedir credenciales de nuevo. getUser() valida
  // contra el servidor — la misma fuente de verdad que el middleware que
  // protege /app/*. Con getSession() (lectura local) una sesión vencida
  // generaba un loop infinito login ↔ /app/comparar.
  useEffect(() => {
    createClient().auth.getUser().then(({ data }) => {
      if (data.user) router.replace(params.get("from") || "/app/comparar");
    });
  }, [router, params]);
  const [mail, setMail] = useState("");
  const [pass, setPass] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPass, setShowPass] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    const { error } = await supabase.auth.signInWithPassword({ email: mail, password: pass });
    if (error) {
      setError("Mail o contraseña incorrectos");
      setLoading(false);
    } else {
      const from = params.get("from") || "/app/comparar";
      router.push(from);
    }
  }

  return (
    <Suspense>
    <>
      <main className="min-h-screen bg-[#F5F0E8] flex items-center justify-center px-4">
        <div className="w-full max-w-md">
        <Link href="/" className="inline-flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-[#1A2B4A] transition mb-4">
          ← Volver al inicio
        </Link>
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm w-full p-10">
          <Link href="/" className="block mb-8">
            <Logo />
          </Link>
          <h1 className="text-2xl font-bold mb-2">Iniciar sesión</h1>
          <p className="text-gray-700 text-sm mb-8">
            ¿No tenés cuenta?{" "}
            <Link href="/registro" className="text-blue-600 font-medium hover:underline">
              Registrate gratis
            </Link>
          </p>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm font-semibold text-gray-800 mb-1">Mail</label>
              <input
                type="email"
                value={mail}
                onChange={(e) => setMail(e.target.value)}
                required
                className="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="tu@mail.com"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-800 mb-1">Contraseña</label>
              <div className="relative">
                <input
                  type={showPass ? "text" : "password"}
                  value={pass}
                  onChange={(e) => setPass(e.target.value)}
                  required
                  className="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="••••••••"
                />
                <button type="button" onClick={() => setShowPass(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 select-none">
                  {showPass ? (
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
                  ) : (
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                  )}
                </button>
              </div>
              <div className="mt-1.5 text-right">
                <Link href="/recuperar" className="text-sm text-blue-600 font-medium hover:underline">
                  ¿Olvidaste tu contraseña?
                </Link>
              </div>
            </div>

            {error && (
              <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg">{error}</div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white font-semibold py-3 rounded-xl hover:bg-blue-700 transition disabled:opacity-50"
            >
              {loading ? "Ingresando…" : "Ingresar"}
            </button>
          </form>
        </div>
        </div>
      </main>
      <Footer />
    </>
    </Suspense>
  );
}

export default function Login() {
  return (
    <Suspense>
      <LoginInner />
    </Suspense>
  );
}
