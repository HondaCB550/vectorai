"use client";
export const dynamic = "force-dynamic";
import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";
import Footer from "@/components/Footer";
import Logo from "@/components/Logo";

const INPUT = "w-full border border-gray-300 rounded-lg px-4 py-3 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500";
const LABEL = "block text-sm font-semibold text-gray-800 mb-1";

// Tiene que coincidir con Supabase → Authentication → Providers → Email →
// "Minimum password length". Estaba en 6 acá y en 8 allá: quien ponía 7
// caracteres pasaba el chequeo del cliente y le rebotaba el servidor con un
// mensaje genérico. Si cambiás el valor en el Dashboard, cambialo acá también.
const MIN_PASS = 12;
const REQUISITOS = `La contraseña debe tener al menos ${MIN_PASS} caracteres e incluir una minúscula, una mayúscula y un número.`;

function ActualizarClaveInner() {
  const router = useRouter();
  const supabase = createClient();

  // El link del mail trae ?token_hash=...&type=recovery. Verificamos ese token
  // directamente con verifyOtp: crea la sesión de recuperación en el cliente SIN
  // depender del "code verifier" de PKCE (que se pierde en el redirect del mail).
  const [sesionOk, setSesionOk] = useState<boolean | null>(null);
  useEffect(() => {
    const supa = createClient();
    const params = new URLSearchParams(window.location.search);
    const tokenHash = params.get("token_hash");
    const type = params.get("type");
    if (tokenHash && type) {
      supa.auth
        .verifyOtp({ token_hash: tokenHash, type: type as "recovery" })
        .then(({ error }) => setSesionOk(!error));
    } else {
      // Fallback: quizás ya hay una sesión de recuperación activa.
      supa.auth.getSession().then(({ data }) => setSesionOk(!!data.session));
    }
  }, []);

  const [pass, setPass] = useState("");
  const [pass2, setPass2] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [listo, setListo] = useState(false);

  async function handleActualizar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (pass.length < MIN_PASS) {
      setError(REQUISITOS);
      return;
    }
    if (pass !== pass2) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setLoading(true);
    const { error } = await supabase.auth.updateUser({ password: pass });
    setLoading(false);
    if (error) {
      const msg = (error.message || "").toLowerCase();
      if (msg.includes("should be different") || msg.includes("same")) {
        setError("La contraseña nueva tiene que ser distinta a la anterior.");
      } else if (msg.includes("reauthentication") || msg.includes("recently")) {
        // "Secure password change" activo y la sesión no es reciente: pasa si
        // alguien entra directo a /actualizar-clave estando logueado, en vez de
        // venir por el link del mail.
        setError("Por seguridad necesitás un link nuevo para cambiar la contraseña. Pedilo desde “Olvidé mi contraseña”.");
      } else if (msg.includes("password")) {
        setError(REQUISITOS);
      } else {
        setError("No se pudo actualizar la contraseña. Pedí un nuevo link e intentá de nuevo.");
      }
      return;
    }
    setListo(true);
    setTimeout(() => router.push("/app/comparar"), 1800);
  }

  return (
    <>
      <main className="min-h-screen bg-[#F5F0E8] flex items-center justify-center px-4">
        <div className="w-full max-w-md">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm w-full p-10">
            <Link href="/" className="block mb-8">
              <Logo />
            </Link>

            {sesionOk === false ? (
              <div className="text-center py-4">
                <h1 className="text-xl font-bold mb-2">El link venció</h1>
                <p className="text-gray-700 text-sm mb-6">
                  El link de recuperación no es válido o ya expiró. Pedí uno nuevo
                  para continuar.
                </p>
                <Link href="/recuperar" className="text-blue-600 text-sm font-medium hover:underline">
                  Pedir un nuevo link
                </Link>
              </div>
            ) : listo ? (
              <div className="text-center py-4">
                <h1 className="text-xl font-bold mb-2">¡Contraseña actualizada!</h1>
                <p className="text-gray-700 text-sm">
                  Listo. Te estamos llevando al comparador…
                </p>
              </div>
            ) : (
              <>
                <h1 className="text-2xl font-bold mb-2">Nueva contraseña</h1>
                <p className="text-gray-700 text-sm mb-8">
                  Elegí una contraseña nueva para tu cuenta.
                </p>

                <form onSubmit={handleActualizar} className="space-y-4">
                  <div>
                    <label className={LABEL}>Contraseña nueva</label>
                    <div className="relative">
                      <input
                        type={showPass ? "text" : "password"}
                        value={pass}
                        onChange={(e) => setPass(e.target.value)}
                        required
                        className={INPUT}
                        placeholder={`Mínimo ${MIN_PASS} caracteres`}
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
                  </div>

                  <div>
                    <label className={LABEL}>Repetir contraseña</label>
                    <input
                      type={showPass ? "text" : "password"}
                      value={pass2}
                      onChange={(e) => setPass2(e.target.value)}
                      required
                      className={INPUT}
                      placeholder="Repetí la contraseña"
                    />
                  </div>

                  {error && (
                    <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg">{error}</div>
                  )}

                  <button
                    type="submit"
                    disabled={loading || sesionOk === null}
                    className="w-full bg-blue-600 text-white font-semibold py-3 rounded-xl hover:bg-blue-700 transition disabled:opacity-50"
                  >
                    {loading ? "Guardando…" : "Guardar contraseña"}
                  </button>
                </form>
              </>
            )}
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}

export default function ActualizarClave() {
  return (
    <Suspense>
      <ActualizarClaveInner />
    </Suspense>
  );
}
