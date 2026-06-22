"use client";
export const dynamic = "force-dynamic";
import { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase";
import Footer from "@/components/Footer";

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

    const { data, error: signUpErr } = await supabase.auth.signUp({
      email: mail,
      password: pass,
    });

    if (signUpErr || !data.user) {
      setError(signUpErr?.message || "Error al registrarse. Intentá de nuevo.");
      setLoading(false);
      return;
    }

    await supabase.from("perfiles").upsert({
      id: data.user.id,
      nombre,
      profesion,
      empresa: empresa || null,
      localidad,
      provincia,
      plan: planInicial === "advance" ? "advance" : "free",
    });

    router.push("/app/comparar");
  }

  return (
    <>
    <main className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-10">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm w-full max-w-md p-10">
        <Link href="/" className="text-xl font-bold text-gray-900 block mb-8">VectorAI</Link>

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
                <input type="password" value={pass} onChange={(e) => setPass(e.target.value)}
                  className={INPUT} placeholder="Mínimo 6 caracteres" />
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
