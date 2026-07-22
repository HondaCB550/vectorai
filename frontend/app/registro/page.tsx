"use client";
export const dynamic = "force-dynamic";
import { useState, useEffect, Suspense } from "react";
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

// Tiene que coincidir con Supabase → Authentication → Providers → Email →
// "Minimum password length" (y con actualizar-clave/page.tsx). Decía 6 cuando
// el servidor ya exigía 8.
const MIN_PASS = 12;
const REQUISITOS = `La contraseña debe tener al menos ${MIN_PASS} caracteres e incluir una minúscula, una mayúscula y un número.`;

// Dominios de mail temporal más comunes — aviso instantáneo al usuario. El
// bloqueo real (lista completa) está en la base de datos.
const DOMINIOS_TEMP = [
  "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
  "temp-mail.org", "temp-mail.io", "yopmail.com", "throwawaymail.com", "getnada.com",
  "trashmail.com", "maildrop.cc", "sharklasers.com", "grr.la", "dispostable.com",
  "fakeinbox.com", "mohmal.com", "1secmail.com", "emailfake.com", "burnermail.io",
];

// Normaliza el ?ref= de campaña: minúsculas, solo [a-z0-9_-], máx 40 chars
function refLimpio(v: string | null): string | null {
  if (!v) return null;
  const r = v.toLowerCase().replace(/[^a-z0-9_-]/g, "").slice(0, 40);
  return r || null;
}

function RegistroInner() {
  const router = useRouter();
  const params = useSearchParams();
  const planInicial = params.get("plan") || "free";
  const supabase = createClient();

  // Atribución de canal: ?ref= directo en /registro gana; si no, el guardado
  // por la landing (localStorage) cuando entró por / con ?ref=
  const [refOrigen, setRefOrigen] = useState<string | null>(null);
  useEffect(() => {
    const deUrl = refLimpio(params.get("ref"));
    if (deUrl) {
      setRefOrigen(deUrl);
      try { localStorage.setItem("va_ref", deUrl); } catch {}
    } else {
      try { setRefOrigen(refLimpio(localStorage.getItem("va_ref"))); } catch {}
    }
  }, [params]);

  // Si ya hay sesión VÁLIDA (validada contra el servidor, como el middleware),
  // directo al comparador — evita cuentas duplicadas y loops con sesión vencida
  useEffect(() => {
    createClient().auth.getUser().then(({ data }) => {
      if (data.user) router.replace("/app/comparar");
    });
  }, [router]);

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
  const [aceptaTerminos, setAceptaTerminos]   = useState(false);
  const [aceptaMarketing, setAceptaMarketing] = useState(true);

  const [error, setError]     = useState("");
  const [loading, setLoading] = useState(false);
  const [showPass, setShowPass] = useState(false);

  function paso1Valido() {
    return nombre.trim() && profesion && mail.includes("@") && pass.length >= MIN_PASS;
  }

  async function handleRegistro() {
    if (!localidad.trim() || !provincia) {
      setError("Completá la localidad y provincia.");
      return;
    }
    if (!aceptaTerminos) {
      setError("Para crear la cuenta tenés que aceptar los Términos y Condiciones.");
      return;
    }
    const dominioMail = (mail.split("@")[1] || "").toLowerCase().trim();
    if (DOMINIOS_TEMP.some((d) => dominioMail === d || dominioMail.endsWith("." + d))) {
      setError("No se permiten correos temporales o descartables. Usá un email real para poder confirmar tu cuenta.");
      return;
    }
    setLoading(true);
    setError("");

    try {
      const { data, error: signUpErr } = await supabase.auth.signUp({
        email: mail,
        password: pass,
        options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
      });

      if (signUpErr) {
        const msg = (signUpErr.message || signUpErr.name || "").toLowerCase();
        if (msg.includes("already registered") || msg.includes("already exists") || msg.includes("user already")) {
          setError("Ya existe una cuenta con ese mail. Iniciá sesión.");
        } else if (msg.includes("rate limit") || msg.includes("too many")) {
          setError("Demasiados intentos. Esperá unos minutos e intentá de nuevo.");
        } else if (msg.includes("password")) {
          setError(REQUISITOS);
        } else if ((msg.includes("email") && (msg.includes("invalid") || msg.includes("valid"))) || msg.includes("unable to validate email")) {
          setError("El email no es válido. Revisalo e intentá de nuevo.");
        } else if (msg.includes("database error") || msg.includes("saving new user") || msg.includes("temporal") || msg.includes("descartable")) {
          setError("No se pudo crear la cuenta con ese email. Usá un email real (no se permiten correos temporales o descartables).");
        } else {
          setError("No se pudo crear la cuenta. Revisá los datos e intentá de nuevo.");
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
        acepto_terminos_at: new Date().toISOString(),
        acepta_marketing: aceptaMarketing,
        ref_origen: refOrigen,
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
                    className={INPUT} placeholder={`Mínimo ${MIN_PASS} caracteres`} />
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

              <label className="flex items-start gap-2.5 text-sm text-gray-700 cursor-pointer">
                <input type="checkbox" checked={aceptaTerminos} onChange={(e) => setAceptaTerminos(e.target.checked)}
                  className="mt-0.5 w-4 h-4 accent-blue-600" />
                <span>
                  Acepto los{" "}
                  <Link href="/terminos" target="_blank" className="text-blue-600 font-medium hover:underline">Términos y Condiciones</Link>
                  {" "}y la{" "}
                  <Link href="/privacidad" target="_blank" className="text-blue-600 font-medium hover:underline">Política de Privacidad</Link>.
                </span>
              </label>

              <label className="flex items-start gap-2.5 text-sm text-gray-500 cursor-pointer">
                <input type="checkbox" checked={aceptaMarketing} onChange={(e) => setAceptaMarketing(e.target.checked)}
                  className="mt-0.5 w-4 h-4 accent-blue-600" />
                <span>Quiero recibir novedades, mejoras y promociones por email (opcional).</span>
              </label>

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
              <div className="mx-auto mb-5 w-16 h-16 rounded-full bg-[#E87022]/10 flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="#E87022" strokeWidth={1.8}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
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
