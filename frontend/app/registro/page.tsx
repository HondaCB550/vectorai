"use client";
export const dynamic = "force-dynamic";
import { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase";
import Footer from "@/components/Footer";
import Logo from "@/components/Logo";

const PROVINCIAS = [
  "Buenos Aires", "CABA", "Córdoba", "Santa Fe", "Mendoza", "Entre Ríos",
  "Tucumán", "Salta", "Misiones", "Chaco", "Corrientes", "Santiago del Estero",
  "San Juan", "Jujuy", "Río Negro", "Neuquén", "Formosa", "Chubut",
  "San Luis", "Catamarca", "La Pampa", "La Rioja", "Santa Cruz", "Tierra del Fuego",
];

const PROFESIONES = [
  "Arquitecto/a",
  "Ingeniero/a civil",
  "Maestro mayor de obras",
  "Constructor/a",
  "Director/a de obra",
  "Desarrollador/a inmobiliario",
  "Comprador/a de materiales",
  "Otro",
];

const INPUT = "w-full border border-gray-300 rounded-lg px-4 py-3 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500";
const LABEL = "block text-sm font-semibold text-gray-800 mb-1";

function RegistroInner() {
  const router = useRouter();
  const params = useSearchParams();
  const planInicial = params.get("plan") || "free";
  const supabase = createClient();

  const [paso, setPaso] = useState(1);

  // Paso 1
  const [nombre, setNombre]       = useState("");
  const [profesion, setProfesion] = useState("");
  const [mail, setMail]           = useState("");
  const [pass, setPass]           = useState("");
  const [empresa, setEmpresa]     = useState("");

  // Paso 2
  const [localidad, setLocalidad] = useState("");
  const [provincia, setProvincia] = useState("");

  const [error, setError]     = useState("");
  const [loading, setLoading] = useState(false);
  const [showPass, setShowPass] = useState(false);

  function paso1Valido() {
    return nombre.trim() && profesion && mail.includes("@") && pass.length >= 6;
  }

  async function handleRegistro() {
    if (!localidad.trim() || !provincia) {
      setError("Completá la localidad y provincia.");
      return;
    }
    setLoading(true);
    setError("");

    try {
      const { data, error: signUpErr } = await supabase.auth.signUp({
        email: mail,
        password: pass,
      });

      if (signUpErr) {
        const msg = signUpErr.message || signUpErr.name || JSON.stringify(signUpErr);
        if (msg.toLowerCase().includes("already registered") || msg.toLowerCase().includes("already exists") || msg.toLowerCase().includes("user already")) {
          setError("Ya existe una cuenta con ese mail. Iniciá sesión.");
        } else if (msg.toLowerCase().includes("rate limit") || msg.toLowerCase().includes("too many")) {
          setError("Demasiados intentos. Esperá unos minutos e intentá de nuevo.");
        } else if (msg && msg !== "{}") {
          setError(msg);
        } else {
          setError(`Error al registrarse (${JSON.stringify(signUpErr)})`);
        }
        setLoading(false);
        return;
      }

      if (!data.user) {
        setError("No se pudo crear la cuenta. Intentá de nuevo.");
        setLoading(false);
        return;
      }

      // Guardar perfil (no bloqueante si falla)
      await supabase.from("perfiles").upsert({
        id: data.user.id,
        nombre,
        profesion,
        empresa: empresa || null,
        localidad,
        provincia,
        plan: planInicial === "advance" ? "advance" : "free",
      });

      // Si Supabase requiere confirmación de email, data.session es null
      if (!data.session) {
        setError("");
        setLoading(false);
        // Mostrar mensaje de "chequeá tu email"
        setPaso(3 as never);
        return;
      }

      router.push("/app/comparar");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Error inesperado. Intentá de nuevo.";
      setError(msg);
      setLoading(false);
    }
  }

  return (
    <>
    <main className="min-h-screen bg-[#F5F0E8] flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
      <Link href="/" className="inline-flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-[#1A2B4A] transition mb-4">
        ← Volver al inicio
      </Link>
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm w-full p-10">
        <Link href="/" className="block mb-8"><Logo /></Link>

        {/* Indicador de pasos */}
        <div className="flex gap-2 mb-8">
          {[1, 2].map((n) => (
            <div key={n} className={`flex-1 h-1 rounded-full transition-colors ${paso >= n ? "bg-blue-600" : "bg-gray-200"}`} />
          ))}
        </div>

        {/* ── Paso 1: Tu perfil ─────────────────────────────────── */}
        {paso === 1 && (
          <>
            <h1 className="text-2xl font-bold text-gray-900 mb-1">Crear cuenta</h1>
            <p className="text-gray-700 text-sm mb-7">
              ¿Ya tenés cuenta?{" "}
              <Link href="/login" className="text-blue-600 font-medium hover:underline">Iniciá sesión</Link>
            </p>

            <div className="space-y-4">
              <div>
                <label className={LABEL}>Nombre completo</label>
                <input type="text" value={nombre} onChange={(e) => setNombre(e.target.value)}
                  className={INPUT} placeholder="Juan García" />
              </div>

              <div>
                <label className={LABEL}>Profesión</label>
                <select value={profesion} onChange={(e) => setProfesion(e.target.value)} className={INPUT}>
                  <option value="">Seleccioná…</option>
                  {PROFESIONES.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>

              <div>
                <label className={LABEL}>
                  Empresa o estudio{" "}
                  <span className="text-gray-500 font-normal">(opcional)</span>
                </label>
                <input type="text" value={empresa} onChange={(e) => setEmpresa(e.target.value)}
                  className={INPUT} placeholder="Estudio García Arquitectura" />
              </div>

              <div>
                <label className={LABEL}>Mail</label>
                <input type="email" value={mail} onChange={(e) => setMail(e.target.value)}
                  className={INPUT} placeholder="tu@mail.com" />
              </div>

              <div>
                <label className={LABEL}>Contraseña</label>
                <div className="relative">
                  <input type={showPass ? "text" : "password"} value={pass} onChange={(e) => setPass(e.target.value)}
                    className={INPUT} placeholder="Mínimo 6 caracteres" />
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

              <button
                onClick={() => { if (paso1Valido()) { setError(""); setPaso(2); } else setError("Completá todos los campos obligatorios."); }}
                className="w-full bg-blue-600 text-white font-semibold py-3 rounded-xl hover:bg-blue-700 transition mt-2"
              >
                Continuar →
              </button>

              {error && <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg">{error}</div>}
            </div>
          </>
        )}

        {/* ── Paso 2: Tu zona ───────────────────────────────────── */}
        {paso === 2 && (
          <>
            <h1 className="text-2xl font-bold text-gray-900 mb-1">Tu zona</h1>
            <p className="text-gray-700 text-sm mb-7">
              Usamos esta info para mostrarte precios de tu zona y comparativas más precisas.
            </p>

            <div className="space-y-4">
              <div>
                <label className={LABEL}>Localidad</label>
                <input type="text" value={localidad} onChange={(e) => setLocalidad(e.target.value)}
                  className={INPUT} placeholder="Ej: San Isidro, Rosario, Córdoba…" />
              </div>

              <div>
                <label className={LABEL}>Provincia</label>
                <select value={provincia} onChange={(e) => setProvincia(e.target.value)} className={INPUT}>
                  <option value="">Seleccioná…</option>
                  {PROVINCIAS.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>

              {error && <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg">{error}</div>}

              <button
                onClick={handleRegistro}
                disabled={loading}
                className="w-full bg-blue-600 text-white font-semibold py-3 rounded-xl hover:bg-blue-700 transition disabled:opacity-50 mt-2"
              >
                {loading ? "Creando cuenta…" : "Crear cuenta gratis"}
              </button>

              <button
                onClick={() => { setError(""); setPaso(1); }}
                className="w-full text-gray-400 text-sm hover:text-gray-600 transition py-1"
              >
                ← Volver
              </button>
            </div>
          </>
        )}

        {/* ── Paso 3: Confirmar email ───────────────────────────── */}
        {paso === (3 as never) && (
          <>
            <div className="text-center py-4">
              <div className="text-5xl mb-4">📬</div>
              <h1 className="text-xl font-bold text-gray-900 mb-2">Revisá tu mail</h1>
              <p className="text-gray-500 text-sm mb-6">
                Te mandamos un link de confirmación a <strong>{mail}</strong>.
                Hacé click en el link para activar tu cuenta.
              </p>
              <Link href="/login" className="text-blue-600 text-sm font-medium hover:underline">
                Ya confirmé → Iniciar sesión
              </Link>
            </div>
          </>
        )}
      </div>
      </div>
    </main>
    <Footer />
    </>
  );
}

export default function Registro() {
  return (
    <Suspense>
      <RegistroInner />
    </Suspense>
  );
}
