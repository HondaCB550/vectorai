"use client";
import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";
import { esAdmin } from "@/lib/admin";
import Logo from "@/components/Logo";
import UserMenu from "@/components/UserMenu";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Codigo = {
  codigo: string;
  plan: string;
  meses: number;
  max_canjes: number | null;
  canjes: number;
  activo: boolean;
  vence: string | null;
  nota: string | null;
  creado_en: string;
};

type Canje = {
  codigo: string;
  user_id: string;
  nombre: string;
  plan: string;
  meses: number;
  canjeado_en: string;
};

const INPUT = "border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500";

function fecha(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("es-AR");
}

export default function AdminCodigosPage() {
  const [codigos, setCodigos] = useState<Codigo[]>([]);
  const [canjes, setCanjes] = useState<Canje[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [token, setToken] = useState<string | null | undefined>(undefined);
  const router = useRouter();

  // Form de alta
  const [nuevoCodigo, setNuevoCodigo] = useState("");
  const [nuevoPlan, setNuevoPlan] = useState<"advance" | "basico">("advance");
  const [nuevoMeses, setNuevoMeses] = useState(1);
  const [nuevoMax, setNuevoMax] = useState("");
  const [nuevoVence, setNuevoVence] = useState("");
  const [nuevaNota, setNuevaNota] = useState("");
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    const sb = createClient();
    sb.auth.getSession().then(({ data }) => {
      if (!esAdmin(data.session?.user?.email)) {
        router.replace("/app/comparar");
        return;
      }
      setToken(data.session?.access_token ?? null);
    });
  }, [router]);

  const cargar = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/admin/codigos`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(res.status === 403 ? "Acceso denegado." : `HTTP ${res.status}`);
      const data = await res.json();
      setCodigos(data.codigos || []);
      setCanjes(data.canjes || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error cargando códigos");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { cargar(); }, [cargar]);

  async function guardar(body: Record<string, unknown>) {
    if (!token) return;
    setGuardando(true);
    setError("");
    setOk("");
    try {
      const res = await fetch(`${API_URL}/admin/codigos`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail?.mensaje || data?.detail?.error || `HTTP ${res.status}`);
      setOk(`Código ${data.codigo} guardado.`);
      await cargar();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error guardando");
    } finally {
      setGuardando(false);
    }
  }

  async function crear() {
    const cod = nuevoCodigo.trim().toUpperCase();
    if (!cod) return;
    await guardar({
      codigo: cod,
      plan: nuevoPlan,
      meses: nuevoMeses,
      max_canjes: nuevoMax.trim() ? Number(nuevoMax) : null,
      vence: nuevoVence ? new Date(`${nuevoVence}T23:59:59`).toISOString() : null,
      nota: nuevaNota.trim() || null,
      activo: true,
    });
    setNuevoCodigo("");
    setNuevoMax("");
    setNuevoVence("");
    setNuevaNota("");
  }

  async function toggleActivo(c: Codigo) {
    await guardar({
      codigo: c.codigo,
      plan: c.plan,
      meses: c.meses,
      max_canjes: c.max_canjes,
      vence: c.vence,
      nota: c.nota,
      activo: !c.activo,
    });
  }

  function linkCanje(codigo: string) {
    return `https://www.vectorai.com.ar/registro?codigo=${codigo}`;
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-4 sm:px-8 py-3 sm:py-4 flex items-center justify-between flex-wrap gap-y-2">
        <Link href="/" className="flex items-center gap-1.5">
          <Logo />
          <span className="text-xs font-semibold text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded-full align-middle">beta</span>
        </Link>
        <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
          <Link href="/app/comparar" className="text-sm text-gray-500 hover:text-gray-900 transition">Comparar</Link>
          <Link href="/app/admin" className="text-sm font-medium text-gray-600 hover:text-blue-700">Admin</Link>
          <Link href="/app/admin/metricas" className="text-sm font-medium text-gray-600 hover:text-blue-700">Métricas</Link>
          <span className="text-sm font-medium text-blue-600">Códigos</span>
          <UserMenu />
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-bold mb-1">Códigos promocionales</h1>
          <p className="text-gray-500 text-sm">
            Regalan meses de un plan. Compartí el link de canje o el código pelado — el usuario lo canjea en /suscribirse.
          </p>
        </div>

        {/* Alta */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-8">
          <h2 className="text-sm font-semibold text-gray-800 mb-4">Nuevo código</h2>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3 items-end">
            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-1">Código</label>
              <input type="text" value={nuevoCodigo} onChange={(e) => setNuevoCodigo(e.target.value.toUpperCase())}
                placeholder="AMIGOS2026" className={`${INPUT} w-full uppercase`} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Plan</label>
              <select value={nuevoPlan} onChange={(e) => setNuevoPlan(e.target.value as "advance" | "basico")} className={`${INPUT} w-full`}>
                <option value="advance">Advance</option>
                <option value="basico">Inicial</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Meses gratis</label>
              <select value={nuevoMeses} onChange={(e) => setNuevoMeses(Number(e.target.value))} className={`${INPUT} w-full`}>
                {[1, 2, 3, 6, 12].map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Máx. canjes</label>
              <input type="number" min={1} value={nuevoMax} onChange={(e) => setNuevoMax(e.target.value)}
                placeholder="Sin tope" className={`${INPUT} w-full`} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Canjeable hasta</label>
              <input type="date" value={nuevoVence} onChange={(e) => setNuevoVence(e.target.value)} className={`${INPUT} w-full`} />
            </div>
            <div className="col-span-2 md:col-span-4">
              <label className="block text-xs text-gray-500 mb-1">Nota (para quién es)</label>
              <input type="text" value={nuevaNota} onChange={(e) => setNuevaNota(e.target.value)}
                placeholder="Ej: influencer Juan — campaña agosto" className={`${INPUT} w-full`} />
            </div>
            <div className="col-span-2">
              <button onClick={crear} disabled={guardando || !nuevoCodigo.trim()}
                className="w-full bg-gray-900 text-white text-sm font-semibold px-5 py-2.5 rounded-lg hover:bg-gray-700 transition disabled:opacity-40">
                {guardando ? "Guardando…" : "Crear código"}
              </button>
            </div>
          </div>
          {ok && <div className="text-green-600 text-sm mt-3">{ok}</div>}
          {error && <div className="text-red-600 text-sm mt-3">{error}</div>}
        </div>

        {/* Lista de códigos */}
        {loading ? (
          <div className="text-center py-16 text-gray-400">
            <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-3" />
            Cargando…
          </div>
        ) : (
          <>
            <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto mb-8">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-400 uppercase tracking-wide border-b border-gray-100">
                    <th className="px-4 py-3">Código</th>
                    <th className="px-4 py-3">Plan</th>
                    <th className="px-4 py-3">Meses</th>
                    <th className="px-4 py-3">Canjes</th>
                    <th className="px-4 py-3">Vence</th>
                    <th className="px-4 py-3">Nota</th>
                    <th className="px-4 py-3">Estado</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {codigos.length === 0 && (
                    <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">Todavía no hay códigos.</td></tr>
                  )}
                  {codigos.map((c) => (
                    <tr key={c.codigo} className="border-b border-gray-50 last:border-0">
                      <td className="px-4 py-3">
                        <span className="font-mono font-semibold text-gray-900">{c.codigo}</span>
                        <button
                          onClick={() => { navigator.clipboard?.writeText(linkCanje(c.codigo)); setOk(`Link de ${c.codigo} copiado.`); }}
                          className="ml-2 text-xs text-blue-600 hover:underline"
                          title={linkCanje(c.codigo)}
                        >
                          copiar link
                        </button>
                      </td>
                      <td className="px-4 py-3 text-gray-700">{c.plan === "basico" ? "Inicial" : "Advance"}</td>
                      <td className="px-4 py-3 text-gray-700">{c.meses}</td>
                      <td className="px-4 py-3 text-gray-700">{c.canjes}{c.max_canjes ? ` / ${c.max_canjes}` : ""}</td>
                      <td className="px-4 py-3 text-gray-500">{fecha(c.vence)}</td>
                      <td className="px-4 py-3 text-gray-500 max-w-48 truncate" title={c.nota || ""}>{c.nota || "—"}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded ${c.activo ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                          {c.activo ? "Activo" : "Inactivo"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <button onClick={() => toggleActivo(c)} disabled={guardando}
                          className="text-xs text-gray-500 hover:text-gray-900 underline disabled:opacity-40">
                          {c.activo ? "Desactivar" : "Activar"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Canjes */}
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
              Últimos canjes ({canjes.length})
            </h2>
            <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-400 uppercase tracking-wide border-b border-gray-100">
                    <th className="px-4 py-3">Fecha</th>
                    <th className="px-4 py-3">Código</th>
                    <th className="px-4 py-3">Usuario</th>
                    <th className="px-4 py-3">Plan</th>
                    <th className="px-4 py-3">Meses</th>
                  </tr>
                </thead>
                <tbody>
                  {canjes.length === 0 && (
                    <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">Todavía no hubo canjes.</td></tr>
                  )}
                  {canjes.map((c) => (
                    <tr key={`${c.codigo}-${c.user_id}`} className="border-b border-gray-50 last:border-0">
                      <td className="px-4 py-3 text-gray-500">{fecha(c.canjeado_en)}</td>
                      <td className="px-4 py-3 font-mono text-gray-900">{c.codigo}</td>
                      <td className="px-4 py-3 text-gray-700">{c.nombre || c.user_id.slice(0, 8)}</td>
                      <td className="px-4 py-3 text-gray-700">{c.plan === "basico" ? "Inicial" : "Advance"}</td>
                      <td className="px-4 py-3 text-gray-700">{c.meses}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
