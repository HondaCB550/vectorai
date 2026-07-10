"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Logo from "@/components/Logo";
import UserMenu from "@/components/UserMenu";
import WhatsAppIcon from "@/components/WhatsAppIcon";
import { createClient } from "@/lib/supabase";

// Fin de la promo de lanzamiento (30% OFF). Pablo: lunes 13/07 + 10 días → 23/07.
const LANZAMIENTO_FIN = new Date("2026-07-23T23:59:59-03:00");

// Barra de estadísticas del hero. OCULTA hasta tener números REALES (no inventar).
// Para volver a mostrarla: poner true y actualizar los valores en la sección "Stats bar".
const MOSTRAR_STATS = false;

function CountdownBadge() {
  const [txt, setTxt] = useState("");
  useEffect(() => {
    function update() {
      const diff = LANZAMIENTO_FIN.getTime() - Date.now();
      if (diff <= 0) { setTxt(""); return; }
      const d = Math.floor(diff / 86400000);
      const h = Math.floor((diff % 86400000) / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      setTxt(`${String(d).padStart(2, "0")}d ${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m`);
    }
    update();
    const id = setInterval(update, 60000);
    return () => clearInterval(id);
  }, []);
  if (!txt) return null;
  return <span className="font-bold text-[#E87022] tabular-nums">{txt}</span>;
}

function FaqItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-4 px-6 py-5 text-left font-semibold text-[#1A2B4A] hover:text-[#E87022] transition"
      >
        {q}
        <span
          className={`shrink-0 w-8 h-8 rounded-full bg-[#FBE4D2] text-[#E87022] text-xl font-bold flex items-center justify-center transition-transform duration-300 ${open ? "rotate-45" : ""}`}
        >
          +
        </span>
      </button>
      <div className={`grid transition-all duration-300 ${open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}>
        <div className="overflow-hidden">
          <p className="px-6 pb-5 text-sm leading-relaxed text-gray-600">{a}</p>
        </div>
      </div>
    </div>
  );
}

// Viñeta de marca (reemplaza los ✅/❌ — sin emojis en Vectorai).
function Bullet({ neg = false }: { neg?: boolean }) {
  return <span className={`mt-[7px] w-1.5 h-1.5 rounded-full shrink-0 ${neg ? "bg-gray-300" : "bg-[#E87022]"}`} />;
}

export default function Landing() {
  // Sesión viva → la landing lo reconoce: botón directo al comparador en vez
  // de "Entrar / Probar gratis" (antes parecía que el login se había perdido)
  const [logueado, setLogueado] = useState(false);
  useEffect(() => {
    createClient().auth.getUser().then(({ data }) => setLogueado(!!data.user));
    // Atribución de campaña: ?ref=grupo-fb → sobrevive hasta /registro via localStorage
    const ref = (new URLSearchParams(window.location.search).get("ref") || "")
      .toLowerCase().replace(/[^a-z0-9_-]/g, "").slice(0, 40);
    if (ref) { try { localStorage.setItem("va_ref", ref); } catch {} }
  }, []);
  return (
    <>
      <main className="min-h-screen bg-[#F5F0E8]">
        {/* Urgency bar */}
        <div className="fixed top-0 left-0 right-0 z-[60] bg-[#0F172A] text-white text-xs sm:text-sm font-medium text-center py-2 px-3 flex items-center justify-center gap-2 sm:gap-3 whitespace-nowrap overflow-hidden">
          <span><span className="hidden sm:inline">Precio de lanzamiento — </span><strong>30% OFF</strong></span>
          <CountdownBadge />
        </div>

        {/* Nav */}
        <nav className="fixed top-9 left-0 right-0 z-50 bg-white shadow-sm">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 h-[60px] sm:h-[68px] flex items-center justify-between gap-2">
            <Link href="/" className="flex items-center gap-2">
              <Logo />
              <span className="text-xs font-semibold text-[#E87022] bg-[#FBE4D2] px-2 py-0.5 rounded-full align-middle">beta</span>
            </Link>
            <ul className="hidden md:flex items-center gap-8 text-sm font-medium text-gray-500">
              <li><a href="#como-funciona" className="hover:text-[#1A2B4A] transition">¿Cómo funciona?</a></li>
              <li><a href="#features" className="hover:text-[#1A2B4A] transition">¿Qué hacemos?</a></li>
              <li><a href="#pricing" className="hover:text-[#1A2B4A] transition">Precios</a></li>
              <li><a href="#faq" className="hover:text-[#1A2B4A] transition">FAQ</a></li>
            </ul>
            <div className="flex items-center gap-3 sm:gap-4 shrink-0">
              <a
                href="https://wa.me/5492241410393?text=Hola%20Vectorai%2C%20tengo%20una%20consulta"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 bg-[#25D366] hover:bg-[#1EBE5D] text-white text-xs sm:text-sm font-bold px-3 sm:px-4 py-2 sm:py-2.5 rounded-full transition whitespace-nowrap"
                title="Consultas por WhatsApp"
              >
                <WhatsAppIcon className="w-4 h-4" />
                <span className="hidden sm:inline">Consultas</span>
              </a>
              {logueado ? (
                <>
                  <Link
                    href="/app/comparar"
                    className="bg-[#E87022] text-white text-xs sm:text-sm font-bold px-4 sm:px-6 py-2 sm:py-2.5 rounded-full hover:bg-[#CF5E15] hover:-translate-y-0.5 transition whitespace-nowrap"
                  >
                    Ir al comparador →
                  </Link>
                  <UserMenu />
                </>
              ) : (
                <>
                  <Link href="/login" className="text-sm font-semibold text-[#1A2B4A] hover:text-[#E87022] transition whitespace-nowrap">Entrar</Link>
                  <Link
                    href="/registro"
                    className="bg-[#E87022] text-white text-xs sm:text-sm font-bold px-4 sm:px-6 py-2 sm:py-2.5 rounded-full hover:bg-[#CF5E15] hover:-translate-y-0.5 transition whitespace-nowrap"
                  >
                    Probar gratis →
                  </Link>
                </>
              )}
            </div>
          </div>
        </nav>

        {/* Hero — una sola columna central (sin ventana de WhatsApp) */}
        <section className="pt-[150px] pb-20 px-6">
          <div className="max-w-2xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 text-sm font-bold px-4 py-2 rounded-full bg-[#1A2B4A] text-[#E87022] mb-6">
              Para arquitectos, constructores y contratistas
            </div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-[#1A2B4A] leading-[1.1] tracking-tight mb-6">
              ¿Otra vez comparando presupuestos <span className="relative inline-block">a mano<span className="absolute left-0 right-0 -bottom-0.5 h-1.5 bg-[#E87022]/30 rounded" /></span>?
            </h1>
            <p className="text-lg text-gray-600 leading-relaxed mb-8 max-w-lg mx-auto">
              Subís los PDFs de tu corralón a Vectorai y te cruza los precios, detecta quién te
              está cobrando de más y te devuelve una tabla lista para comparar. En 3 minutos.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-4 mb-6">
              <Link
                href="/registro"
                className="inline-flex items-center gap-2 bg-[#E87022] text-white text-lg font-bold px-10 py-4 rounded-full hover:bg-[#CF5E15] hover:-translate-y-0.5 transition"
              >
                Probar gratis →
              </Link>
              <a href="#como-funciona" className="inline-flex items-center gap-2 border-2 border-[#1A2B4A] text-[#1A2B4A] font-bold px-6 py-3.5 rounded-full hover:bg-[#1A2B4A] hover:text-white transition">
                Ver cómo funciona
              </a>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2 text-sm font-medium text-gray-600">
              <span>Sin tarjeta</span>
              <span className="text-gray-300">·</span>
              <span>Sin instalación</span>
              <span className="text-gray-300">·</span>
              <span>Descargable en Excel</span>
            </div>
          </div>
        </section>

        {/* Stats bar — oculta hasta tener números reales (flag MOSTRAR_STATS) */}
        {MOSTRAR_STATS && (
        <section className="bg-[#1A2B4A] py-12">
          <div className="max-w-6xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            {[
              { n: "+500", label: "constructores activos" },
              { n: "14.200", label: "presupuestos comparados" },
              { n: "$18.4M", label: "ahorrados a clientes" },
              { n: "3 min", label: "promedio por comparación" },
            ].map((s) => (
              <div key={s.n}>
                <div className="font-bold text-3xl sm:text-4xl text-[#E87022] tracking-tight">{s.n}</div>
                <div className="text-sm text-white/75 mt-2">{s.label}</div>
              </div>
            ))}
          </div>
        </section>
        )}

        {/* Caso real */}
        <section className="py-24 px-6">
          <div className="max-w-3xl mx-auto">
            <div className="text-center mb-12">
              <h2 className="text-3xl sm:text-4xl font-bold text-[#1A2B4A] tracking-tight mb-4">Un caso real, con números</h2>
              <p className="text-lg text-gray-600">Así le pasó a un contratista en Chascomús.</p>
            </div>
            <div className="bg-white border-l-4 border-[#E87022] rounded-r-2xl shadow-sm p-6">
              <div className="text-xs font-bold uppercase tracking-wide text-[#E87022] mb-3">Caso real — Chascomús, Buenos Aires</div>
              <p className="text-[#1A2B4A] font-medium leading-relaxed">
                Necesitaba 120 bolsas de cemento para una losa. Mandó 4 presupuestos de corralones
                distintos a Vectorai. En 2 minutos supo a quién debía comprarle las bolsas de cemento:
                un corralón le cobraba <strong>$7.579</strong> la bolsa y otro, a 15 cuadras, <strong>$6.827</strong>.
              </p>
              <div className="font-bold text-lg text-green-600 mt-3">Ahorro: $90.240 en una sola compra</div>
            </div>
          </div>
        </section>

        {/* Demo visual */}
        <section className="bg-white py-24 px-6" id="demo">
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-12">
              <h2 className="text-3xl sm:text-4xl font-bold text-[#1A2B4A] tracking-tight mb-4">Esto es lo que vas a ver</h2>
              <p className="text-lg text-gray-600">Mismos materiales, distintos nombres. Vectorai los une solo.</p>
            </div>
            <div className="overflow-x-auto rounded-2xl border border-gray-200 shadow-md">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left px-5 py-4 font-bold text-[#1A2B4A] bg-gray-50">Material</th>
                    <th className="px-5 py-4 font-bold text-center text-gray-600">Corralón Pérez</th>
                    <th className="px-5 py-4 font-bold text-center text-gray-600">Distribuidora Juan</th>
                    <th className="px-5 py-4 font-bold text-center bg-gray-50 text-[#1A2B4A]">Mejor precio</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { mat: "Perfil C galvanizado 70×35 e=0.9mm", a: "$1.620", b: "$1.850", mejor: "a" },
                    { mat: "Placa Durlock RH 12.5mm", a: "$19.100", b: "$18.500", mejor: "b" },
                    { mat: "OSB 9mm 1.22×2.44m", a: "$8.700", b: "$8.900", mejor: "a" },
                    { mat: "Lana de vidrio 50mm", a: "$9.200", b: "—", mejor: "a" },
                  ].map((row, i) => (
                    <tr key={i} className="border-b border-gray-100 last:border-0">
                      <td className="px-5 py-3.5 text-gray-700 font-medium">{row.mat}</td>
                      <td className={`px-5 py-3.5 text-center font-bold ${row.mejor === "a" ? "bg-green-50 text-green-700" : "text-gray-400"}`}>{row.a}</td>
                      <td className={`px-5 py-3.5 text-center font-bold ${row.mejor === "b" ? "bg-green-50 text-green-700" : "text-gray-400"}`}>{row.b}</td>
                      <td className="px-5 py-3.5 text-center">
                        <span className="bg-green-100 text-green-700 font-bold text-xs px-3 py-1.5 rounded-full">
                          {row.mejor === "a" ? "Pérez" : "Juan"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-center text-sm text-gray-400 mt-4">Verde = mejor precio · — = no cotiza ese ítem</p>
          </div>
        </section>

        {/* Cómo funciona */}
        <section className="py-24 px-6" id="como-funciona">
          <div className="max-w-5xl mx-auto">
            <div className="text-center mb-14">
              <h2 className="text-3xl sm:text-4xl font-bold text-[#1A2B4A] tracking-tight mb-4">Cuatro pasos. Eso es todo.</h2>
              <p className="text-lg text-gray-600">No hace falta saber nada de software ni de planillas complicadas.</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
              {[
                { n: "1", titulo: "Subís los PDFs", desc: "Arrastrás el presupuesto de cada proveedor, le ponés nombre y si va con IVA o algún descuento. Listo." },
                { n: "2", titulo: "Vectorai los lee", desc: "Extrae ítems, precios y unidades de forma automática. No tocás nada." },
                { n: "3", titulo: "Los cruza solo", desc: 'Entiende que "Perfil C 70" y "Perfil galvanizado 70" son lo mismo.' },
                { n: "4", titulo: "Comparativa lista", desc: "Tabla con el menor precio por ítem. Descargable en Excel al instante." },
              ].map((s) => (
                <div key={s.n} className="relative bg-white rounded-2xl shadow-sm p-8 overflow-hidden">
                  <div className="absolute -top-3 -right-2 text-8xl font-bold text-[#E87022]/[0.07] leading-none select-none pointer-events-none">
                    {s.n}
                  </div>
                  <div className="w-10 h-10 bg-[#E87022] text-white rounded-full flex items-center justify-center text-lg font-bold mb-5">
                    {s.n}
                  </div>
                  <h3 className="font-semibold text-[#1A2B4A] mb-2 text-base">{s.titulo}</h3>
                  <p className="text-sm text-gray-600 leading-relaxed">{s.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Features — ¿Qué hacemos? */}
        <section className="bg-white py-24 px-6" id="features">
          <div className="max-w-5xl mx-auto">
            <div className="text-center mb-14">
              <h2 className="text-3xl sm:text-4xl font-bold text-[#1A2B4A] tracking-tight mb-4">Lo que Vectorai hace por vos</h2>
              <p className="text-lg text-gray-600">Todo lo que necesitás para no pagar de más, en un solo lugar.</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[
                { titulo: "Entiende el IVA", desc: "Vos indicás si el precio viene con o sin IVA y aplica el factor correcto. Sin cálculos manuales." },
                { titulo: "Aplica descuentos", desc: "Cargás el % de descuento por proveedor y Vectorai lo aplica automáticamente al comparar." },
                { titulo: "Matching inteligente", desc: "Reconoce variantes de nombres, abreviaturas y errores de tipeo. Hormigón H-21 = Hormigón H21." },
                { titulo: "Todos los rubros", desc: "Albañilería, steel frame, eléctrico, sanitario, gas y pinturas. Todo en una sola comparativa." },
                { titulo: "Excel en un clic", desc: "Exportá la comparativa completa en Excel, lista para pasarle al cliente o archivar." },
                { titulo: "Todo desde la web", desc: "Subís los PDFs desde el navegador y se digitalizan automáticamente. Sin instalar nada." },
              ].map((f) => (
                <div key={f.titulo} className="bg-[#F5F0E8] rounded-2xl p-6 hover:-translate-y-1 transition">
                  <div className="w-2.5 h-2.5 rounded-full bg-[#E87022] mb-4" />
                  <h3 className="font-semibold text-[#1A2B4A] mb-2 text-lg">{f.titulo}</h3>
                  <p className="text-sm text-gray-600 leading-relaxed">{f.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Pricing */}
        <section className="py-24 px-6" id="pricing">
          <div className="max-w-5xl mx-auto">
            <div className="text-center mb-12">
              <h2 className="text-3xl sm:text-4xl font-bold text-[#1A2B4A] tracking-tight mb-4">Precios sin vueltas</h2>
              <p className="text-lg text-gray-600">Arrancás gratis. Si te sirve, te suscribís.</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Free */}
              <div className="bg-white rounded-3xl border-2 border-gray-200 p-8">
                <div className="text-xl font-semibold text-[#1A2B4A] mb-1">Gratis</div>
                <div className="text-4xl font-bold text-[#1A2B4A] mb-1">$0</div>
                <p className="text-gray-400 text-sm mb-8">Para probar</p>
                <ul className="space-y-3 text-sm text-gray-600 mb-8">
                  {[
                    "1 comparativa gratis",
                    "Hasta 3 proveedores",
                    "Comparativa en pantalla",
                    "Descarga en Excel",
                    "Sin historial ni obras",
                  ].map((f) => {
                    const neg = f.startsWith("Sin ");
                    return (
                      <li key={f} className="flex gap-2.5 leading-snug items-start">
                        <Bullet neg={neg} />
                        <span className={neg ? "text-gray-400" : ""}>{f}</span>
                      </li>
                    );
                  })}
                </ul>
                <Link href="/registro" className="block text-center border-2 border-[#1A2B4A] text-[#1A2B4A] font-bold py-3.5 rounded-full hover:bg-[#1A2B4A] hover:text-white transition">
                  Empezar gratis
                </Link>
              </div>

              {/* Inicial */}
              <div className="bg-white rounded-3xl border-2 border-[#E87022]/40 p-8">
                <div className="text-xl font-semibold text-[#1A2B4A] mb-1">Inicial</div>
                <div className="flex items-end gap-2 mb-1">
                  <span className="text-lg text-gray-400 line-through">$28.000</span>
                  <span className="text-4xl font-bold text-[#1A2B4A]">$19.600</span>
                  <span className="text-xl font-normal text-gray-400">/mes</span>
                </div>
                <p className="text-[#E87022] text-xs font-semibold mb-8">Precio de lanzamiento</p>
                <ul className="space-y-3 text-sm text-gray-600 mb-8">
                  {[
                    "6 comparativas por mes",
                    "2 más de regalo el primer mes",
                    "Hasta 5 proveedores por comparativa",
                    "Hasta 10 hojas por proveedor",
                    "Lista de compras por proveedor",
                    "Descarga en Excel y PDF",
                  ].map((f) => (
                    <li key={f} className="flex gap-2.5 leading-snug items-start">
                      <Bullet />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
                <Link href="/suscribirse" className="block text-center border-2 border-[#E87022] text-[#E87022] font-bold py-3.5 rounded-full hover:bg-[#E87022] hover:text-white transition">
                  Quiero el Inicial
                </Link>
              </div>

              {/* Advance */}
              <div className="bg-[#1A2B4A] rounded-3xl p-8 text-white relative overflow-hidden">
                <div className="absolute top-5 right-5 bg-[#E87022] text-xs font-bold px-3 py-1.5 rounded-full uppercase tracking-wide">
                  Más popular
                </div>
                <div className="text-xl font-semibold mb-1">Advance</div>
                <div className="text-4xl font-bold mb-1 text-[#E87022]">$48.000<span className="text-xl font-normal text-white/60">/mes</span></div>
                <p className="text-white/60 text-xs mb-8">Pesos argentinos · IVA incluido</p>
                <ul className="space-y-3 text-sm mb-8">
                  {[
                    "Mismas características que el plan Inicial",
                    "Comparativas ilimitadas",
                    "Hasta 10 proveedores por comparativa",
                    "Obras y precios recomendados por zona",
                    "Mis presupuestos y comparativas guardados 30 días, separados por obra",
                    "Soporte prioritario",
                  ].map((f) => (
                    <li key={f} className="flex gap-2.5 text-white/85 leading-snug items-start">
                      <Bullet />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
                <Link href="/suscribirse" className="block text-center bg-[#E87022] text-white font-bold py-3.5 rounded-full hover:bg-[#CF5E15] transition">
                  Quiero el Advance
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="bg-white py-24 px-6" id="faq">
          <div className="max-w-2xl mx-auto">
            <div className="text-center mb-14">
              <h2 className="text-3xl sm:text-4xl font-bold text-[#1A2B4A] tracking-tight">Preguntas frecuentes</h2>
            </div>
            <div className="flex flex-col gap-3">
              <FaqItem
                q="¿Qué tipos de presupuestos puedo comparar?"
                a="Cualquier presupuesto de corralón, ferretería o proveedor de materiales de obra. Funciona con PDFs y fotos de papel. Vectorai está entrenado para leer formatos argentinos."
              />
              <FaqItem
                q="¿Calcula el IVA correctamente?"
                a="Sí. Vectorai aplica IVA 21% o 10,5% según la alícuota que corresponda, y detecta si el presupuesto ya lo incluye o no."
              />
              <FaqItem
                q="¿Puedo mandar los PDFs?"
                a="Cargás los PDFs desde la web, sin instalar nada, y te devuelve la comparación lista para descargar en Excel, PDF o JPG."
              />
              <FaqItem
                q="¿Se guardan los presupuestos?"
                a="Sí. En el plan Advance se guardan 30 días: podés catalogarlos por obra y volver a comparar sin re-subir nada."
              />
              <FaqItem
                q="¿Mis datos están seguros?"
                a="Tus presupuestos se procesan de forma segura y no se comparten con terceros. Podés pedir la eliminación de tus datos en cualquier momento."
              />
              <FaqItem
                q="¿Puedo cancelar cuando quiera?"
                a="Sí, sin permanencia. Cancelás la suscripción cuando quieras, sin formularios ni llamadas."
              />
            </div>
          </div>
        </section>

        {/* CTA final */}
        <section className="bg-[#0F172A] py-32 px-6 text-center">
          <div className="max-w-xl mx-auto">
            <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight mb-6">
              Dejá de pagar de más.<br />En serio.
            </h2>
            <p className="text-lg text-white/70 mb-10">
              Un corralón le cobraba a un cliente $7.579 la bolsa de cemento. Otro, a 20 cuadras, $6.827.
              Vectorai lo encontró en 2 minutos.
            </p>
            <Link
              href="/registro"
              className="inline-flex items-center gap-2 bg-[#E87022] text-white text-lg font-bold px-10 py-4 rounded-full hover:bg-[#CF5E15] hover:-translate-y-0.5 transition"
            >
              Probar Vectorai gratis →
            </Link>
            <div className="flex flex-wrap items-center justify-center gap-4 mt-8 text-sm text-white/50">
              <span>Sin tarjeta</span><span>·</span><span>Sin instalación</span><span>·</span><span>Sin vueltas</span>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-[#0F172A] border-t border-white/10 py-10 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Logo dark />
            <span className="text-sm text-white/40">© 2026 · Hecho en Argentina</span>
          </div>
          <a
            href="mailto:hola@vectorai.com.ar"
            className="text-sm text-white/60 hover:text-white transition"
          >
            hola@vectorai.com.ar
          </a>
        </div>
      </footer>
    </>
  );
}
