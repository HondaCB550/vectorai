"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";
import { esAdmin } from "@/lib/admin";
import Logo from "@/components/Logo";
import UserMenu from "@/components/UserMenu";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Pendiente = {
  id: string;
  descripcion_original: string;
  descripcion_normalizada: string;
  proveedor: string;
  precio_visto: number;
  estado: string;
  created_at: string;
};

type AccionLocal = {
  tipo: "linkear" | "rechazar" | "crear";
  codigo?: string;
};

function fmt(v: number) {
  return `$ ${Math.round(v).toLocaleString("es-AR")}`;
}

function TimeSince({ iso }: { iso: string }) {
  const d = new Date(iso);
  const now = new Date();
  const diffH = Math.round((now.getTime() - d.getTime()) / 3600000);
  if (diffH < 24) return <span className="text-gray-400 text-xs">{diffH}h atrás</span>;
  const diffD = Math.round(diffH / 24);
  return <span className="text-gray-400 text-xs">{diffD}d atrás</span>;
}

export default function AdminPage() {
  const [pendientes, setPendientes] = useState<Pendiente[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState("");
  const [acciones, setAcciones]     = useState<Record<string, AccionLocal>>({});
  const [codigos, setCodigos]       = useState<Record<string, string>>({});
  const [procesando, setProcesando] = useState<Set<string>>(new Set());
  const [completados, setCompletados] = useState<Set<string>>(new Set());
  const [filtroEstado, setFiltroEstado] = useState<"PENDIENTE" | "VALIDADO" | "RECHAZADO">("PENDIENTE");
  const [busqueda, setBusqueda]     = useState("");
  // undefined = sesión todavía no resuelta (no disparar fetches aún)
  const [token, setToken]           = useState<string | null | undefined>(undefined);
  const reqSeq = useRef(0);
  const router = useRouter();

  useEffect(() => {
    const sb = createClient();
    sb.auth.getSession().then(({ data }) => {
      // Solo administradores: los usuarios normales vuelven al comparador
      if (!esAdmin(data.session?.user?.email)) {
        router.replace("/app/comparar");
        return;
      }
      setToken(data.session?.access_token ?? null);
    });
  }, [router]);

  const cargar = useCallback(async () => {
    // Esperar a que la sesión esté resuelta: si el primer fetch sale sin token
    // recibe 403, y si esa respuesta llega tarde pisa a la buena (banner de
    // "Acceso denegado" con la lista cargada abajo).
    if (token === undefined) return;
    const seq = ++reqSeq.current;
    setLoading(true);
    setError("");
    try {
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(`${API_URL}/admin/pendientes?estado=${filtroEstado}&limit=100`, { headers });
      if (!res.ok) {
        if (res.status === 403) throw new Error("Acceso denegado. Iniciá sesión para usar el panel admin.");
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      if (seq !== reqSeq.current) return;  // llegó tarde: hay un pedido más nuevo
      setPendientes(data.pendientes || []);
    } catch (e: unknown) {
      if (seq !== reqSeq.current) return;
      setError(e instanceof Error ? e.message : "Error cargando pendientes");
    } finally {
      if (seq === reqSeq.current) setLoading(false);
    }
  }, [filtroEstado, token]);

  useEffect(() => { cargar(); }, [cargar]);

  async function ejecutar(id: string) {
    const accion = acciones[id];
    if (!accion) return;
    if (accion.tipo === "linkear" && !codigos[id]?.trim()) return;

    setProcesando(prev => new Set([...prev, id]));
    try {
      const body: Record<string, unknown> = {
        pendiente_id: id,
        accion: accion.tipo,
      };
      if (accion.tipo === "linkear") body.codigo_material = codigos[id].trim().toUpperCase();

      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`${API_URL}/admin/validar-pendiente`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail?.error || `HTTP ${res.status}`);
      }
      setCompletados(prev => new Set([...prev, id]));
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Error al procesar");
    } finally {
      setProcesando(prev => { const s = new Set(prev); s.delete(id); return s; });
    }
  }

  const pendientesFiltrados = pendientes.filter(p => {
    if (completados.has(p.id)) return false;
    if (!busqueda) return true;
    const q = busqueda.toLowerCase();
    return p.descripcion_original.toLowerCase().includes(q) || p.proveedor.toLowerCase().includes(q);
  });

  const completadosItems = pendientes.filter(p => completados.has(p.id));

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Nav */}
      <nav className="bg-white border-b border-gray-200 px-4 sm:px-8 py-3 sm:py-4 flex items-center justify-between flex-wrap gap-y-2">
        <Link href="/" className="flex items-center gap-1.5">
          <Logo />
          <span className="text-xs font-semibold text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded-full align-middle">beta</span>
        </Link>
        <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
          <Link href="/" className="hidden sm:inline text-sm text-gray-500 hover:text-gray-800 transition">Inicio</Link>
          <Link href="/app/comparar" className="text-sm text-gray-500 hover:text-gray-900 transition">Comparar</Link>
          <Link href="/app/historial" className="text-sm text-gray-500 hover:text-gray-800 transition">Mis comparativas</Link>
          <span className="text-sm font-medium text-blue-600">Admin</span>
          <Link href="/app/admin/metricas" className="text-sm font-medium text-gray-600 hover:text-blue-700">
            Métricas
          </Link>
          <Link
            href="/suscribirse"
            className="text-sm font-semibold text-blue-600 border border-blue-200 bg-blue-50 hover:bg-blue-100 transition px-3 py-1.5 rounded-lg"
          >
            Mejorar plan
          </Link>
          <a
            href="https://wa.me/5492241410393?text=Hola%2C%20tengo%20una%20consulta%20sobre%20VectorAI"
            target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-sm font-medium text-white bg-green-500 hover:bg-green-600 transition px-3 py-1.5 rounded-lg"
          >
            Consultas
          </a>
          <UserMenu />
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-10">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-1">Panel de revisión</h1>
          <p className="text-gray-500 text-sm">
            Materiales sin match automático. Linkeá cada descripción al código interno correcto para que el sistema aprenda.
          </p>
        </div>

        {/* Controles */}
        <div className="flex items-center gap-3 mb-6 flex-wrap">
          {/* Tabs de estado */}
          <div className="flex bg-gray-100 rounded-lg p-1 gap-0.5">
            {(["PENDIENTE", "VALIDADO", "RECHAZADO"] as const).map(e => (
              <button
                key={e}
                onClick={() => { setFiltroEstado(e); setCompletados(new Set()); }}
                className={`px-4 py-1.5 text-sm font-medium rounded-md transition ${
                  filtroEstado === e ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {e === "PENDIENTE" ? "Pendientes" : e === "VALIDADO" ? "Validados" : "Rechazados"}
              </button>
            ))}
          </div>

          {/* Búsqueda */}
          <input
            type="text"
            placeholder="Buscar descripción o proveedor..."
            value={busqueda}
            onChange={e => setBusqueda(e.target.value)}
            className="flex-1 min-w-48 border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />

          <button
            onClick={cargar}
            className="px-4 py-2 text-sm border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition"
          >
            Recargar
          </button>
        </div>

        {/* Stats badge */}
        {!loading && (
          <div className="flex gap-3 mb-6">
            <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-2 text-sm">
              <span className="font-semibold text-amber-700">{pendientesFiltrados.length}</span>
              <span className="text-amber-600 ml-1">
                {filtroEstado === "PENDIENTE" ? "pendientes" : filtroEstado === "VALIDADO" ? "validados" : "rechazados"}
                {busqueda ? " (filtrados)" : ""}
              </span>
            </div>
            {completadosItems.length > 0 && (
              <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-2 text-sm">
                <span className="font-semibold text-green-700">{completadosItems.length}</span>
                <span className="text-green-600 ml-1">procesados en esta sesión</span>
              </div>
            )}
          </div>
        )}

        {/* Estado de carga */}
        {loading && (
          <div className="text-center py-16 text-gray-400">
            <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-3" />
            Cargando pendientes...
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 text-sm mb-6">{error}</div>
        )}

        {/* Lista */}
        {!loading && pendientesFiltrados.length === 0 && (
          <div className="bg-green-50 border border-green-200 rounded-xl p-10 text-center">
            <div className="text-3xl mb-3">✓</div>
            <p className="font-medium text-green-700">
              {filtroEstado === "PENDIENTE" ? "No hay pendientes." : "No hay items en este estado."}
            </p>
            {filtroEstado === "PENDIENTE" && (
              <p className="text-sm text-green-600 mt-1">
                El sistema identificó todos los materiales automáticamente.
              </p>
            )}
          </div>
        )}

        <div className="space-y-3">
          {pendientesFiltrados.map(item => {
            const accion = acciones[item.id];
            const isProcesando = procesando.has(item.id);

            return (
              <div key={item.id} className="bg-white rounded-xl border border-gray-200 p-5">
                {/* Encabezado del item */}
                <div className="flex items-start gap-3 mb-4">
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-900 text-sm leading-snug">
                      {item.descripcion_original}
                    </div>
                    <div className="flex items-center gap-3 mt-1 flex-wrap">
                      <span className="bg-slate-100 text-slate-600 text-xs font-semibold px-2 py-0.5 rounded">
                        {item.proveedor}
                      </span>
                      <span className="text-xs text-gray-500">{fmt(item.precio_visto)} s/IVA</span>
                      <TimeSince iso={item.created_at} />
                      {filtroEstado !== "PENDIENTE" && (
                        <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                          item.estado === "VALIDADO" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                        }`}>
                          {item.estado}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Acciones — solo para PENDIENTE */}
                {filtroEstado === "PENDIENTE" && (
                  <div className="border-t border-gray-100 pt-4">
                    <p className="text-xs text-gray-400 font-medium uppercase tracking-wide mb-3">
                      ¿Qué hacer con este item?
                    </p>

                    <div className="flex flex-wrap gap-2 mb-3">
                      {/* Linkear a código existente */}
                      <button
                        onClick={() => setAcciones(prev => ({ ...prev, [item.id]: { tipo: "linkear" } }))}
                        className={`px-3 py-1.5 text-sm rounded-lg border transition ${
                          accion?.tipo === "linkear"
                            ? "bg-blue-600 text-white border-blue-600"
                            : "border-gray-300 text-gray-600 hover:border-blue-400 hover:text-blue-600"
                        }`}
                      >
                        Linkear a material existente
                      </button>

                      {/* Crear nuevo */}
                      <button
                        onClick={() => setAcciones(prev => ({ ...prev, [item.id]: { tipo: "crear" } }))}
                        className={`px-3 py-1.5 text-sm rounded-lg border transition ${
                          accion?.tipo === "crear"
                            ? "bg-violet-600 text-white border-violet-600"
                            : "border-gray-300 text-gray-600 hover:border-violet-400 hover:text-violet-600"
                        }`}
                      >
                        Crear nuevo material
                      </button>

                      {/* Rechazar */}
                      <button
                        onClick={() => setAcciones(prev => ({ ...prev, [item.id]: { tipo: "rechazar" } }))}
                        className={`px-3 py-1.5 text-sm rounded-lg border transition ${
                          accion?.tipo === "rechazar"
                            ? "bg-red-500 text-white border-red-500"
                            : "border-gray-300 text-gray-400 hover:border-red-300 hover:text-red-500"
                        }`}
                      >
                        Rechazar (duplicado/irrelevante)
                      </button>
                    </div>

                    {/* Input código para linkear */}
                    {accion?.tipo === "linkear" && (
                      <div className="mb-3">
                        <label className="text-xs text-gray-500 mb-1 block">
                          Código interno del material (ej: EST001, INS032)
                        </label>
                        <input
                          type="text"
                          placeholder="Ej: AISL008"
                          value={codigos[item.id] || ""}
                          onChange={e => setCodigos(prev => ({ ...prev, [item.id]: e.target.value }))}
                          className="w-full max-w-xs border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-800 uppercase focus:outline-none focus:ring-2 focus:ring-blue-500"
                          autoFocus
                        />
                        <p className="text-xs text-gray-400 mt-1">
                          La descripción quedará como alias de ese código para futuros análisis.
                        </p>
                      </div>
                    )}

                    {accion?.tipo === "crear" && (
                      <div className="mb-3 bg-violet-50 border border-violet-200 rounded-lg p-3 text-xs text-violet-700">
                        Se marcará este item para crear un nuevo material. Luego agregalo manualmente
                        en <strong>BD_Materiales_VectorAI.xlsx</strong> y corrés <code>migrar_v2.py</code>.
                      </div>
                    )}

                    {/* Botón confirmar */}
                    {accion && (
                      <button
                        onClick={() => ejecutar(item.id)}
                        disabled={isProcesando || (accion.tipo === "linkear" && !codigos[item.id]?.trim())}
                        className="bg-gray-900 text-white text-sm font-medium px-5 py-2 rounded-lg hover:bg-gray-700 transition disabled:opacity-40"
                      >
                        {isProcesando ? "Procesando..." : "Confirmar"}
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Completados en sesión */}
        {completadosItems.length > 0 && (
          <div className="mt-8">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
              Procesados en esta sesión ({completadosItems.length})
            </h2>
            <div className="space-y-1">
              {completadosItems.map(item => (
                <div key={item.id} className="flex items-center gap-2 text-sm text-gray-400 py-1.5">
                  <span className="text-green-500 font-bold">✓</span>
                  <span className="text-gray-600 font-medium">{item.proveedor}</span>
                  <span className="truncate">{item.descripcion_original}</span>
                  <span className="text-gray-300">·</span>
                  <span>{acciones[item.id]?.tipo === "linkear" ? `→ ${codigos[item.id]}` : acciones[item.id]?.tipo === "rechazar" ? "rechazado" : "a crear"}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
