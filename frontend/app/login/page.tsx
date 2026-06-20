"use client";
export const dynamic = "force-dynamic";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";

export default function Login() {
  const router = useRouter();
  const supabase = createClient();
  const [mail, setMail] = useState("");
  const [pass, setPass] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    const { error } = await supabase.auth.signInWithPassword({ email: mail, password: pass });
    if (error) {
      setError("Mail o contraseña incorrectos");
      setLoading(false);
    } else {
      router.push("/app/comparar");
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm w-full max-w-md p-10">
        <Link href="/" className="text-xl font-bold text-gray-900 block mb-8">
          VectorAI
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Iniciar sesión</h1>
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
            <input
              type="password"
              value={pass}
              onChange={(e) => setPass(e.target.value)}
              required
              className="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="••••••••"
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
            {loading ? "Ingresando…" : "Ingresar"}
          </button>
        </form>
      </div>
    </main>
  );
}
