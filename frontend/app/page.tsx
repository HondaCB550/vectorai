"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Logo from "@/components/Logo";
import UserMenu from "@/components/UserMenu";
import { createClient } from "@/lib/supabase";

const WA_NUMERO = "5492241410393";
const WA_CONSULTA = `https://wa.me/${WA_NUMERO}?text=${encodeURIComponent("Hola, tengo una consulta sobre VectorAI")}`;
const WA_CARGAR = `https://wa.me/${WA_NUMERO}?text=${encodeURIComponent("Hola! Te mando los PDFs de mis proveedores para comparar.")}`;

function WhatsAppIcon({ className = "w-5 h-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.297-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
    </svg>
  );
}

function CountdownBadge() {
  const [txt, setTxt] = useState("02d 14h 38m");
  useEffect(() => {
    const end = new Date();
    end.setDate(end.getDate() + 2);
    end.setHours(end.getHours() + 14);
    end.setMinutes(end.getMinutes() + 38);
    function update() {
      const diff = end.getTime() - Date.now();
      if (diff <= 0) return;
      const d = Math.floor(diff / 86400000);
      const h = Math.floor((diff % 86400000) / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      setTxt(`${String(d).padStart(2, "0")}d ${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m`);
    }
    update();
    const id = setInterval(update, 60000);
    return () => clearInterval(id);
  }, []);
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

export default function Landing() {
  // Sesión viva → la landing lo reconoce: botón directo al comparador en vez
  // de "Entrar / Probar gratis" (antes parecía que el login se había perdido)
  const [logueado, setLogueado] = useState(false);
  useEffect(() => {
    createClient().auth.getUser().then(({ data }) => setLogueado(!!data.user));
  }, []);
  return (
    <>
      <main className="min-h-screen bg-[#F5F0E8]">
        {/* Urgency bar */}
        <div className="fixed top-0 left-0 right-0 z-[60] bg-[#0F172A] text-white text-xs sm:text-sm font-medium text-center py-2 px-3 flex items-center justify-center gap-2 sm:gap-3 whitespace-nowrap overflow-hidden">
          <span>🔥 <span className="hidden sm:inline">Precio de lanzamiento — </span><strong>20% OFF</strong> este mes</span>
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
              <li><a href="#como-funciona" className="hover:text-[#1A2B4A] transition">Cómo funciona</a></li>
              <li><a href="#features" className="hover:text-[#1A2B4A] transition">Features</a></li>
              <li><a href="#pricing" className="hover:text-[#1A2B4A] transition">Precios</a></li>
              <li><a href="#faq" className="hover:text-[#1A2B4A] transition">FAQ</a></li>
            </ul>
            <div className="flex items-center gap-3 sm:gap-4 shrink-0">
              {logueado ? (
                <>
                  <Link
                    href="/app/comparar"
                    className="bg-[#E87022] text-white text-xs sm:text-sm font-bold px-4 sm:px-6 py-2 sm:py-2.5 rounded-full hover:bg-[#CF5E15] hover:-translate-y-0.5 transition shadow-[0_4px_16px_rgba(232,112,34,.35)] whitespace-nowrap"
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
                    className="bg-[#E87022] text-white text-xs sm:text-sm font-bold px-4 sm:px-6 py-2 sm:py-2.5 rounded-full hover:bg-[#CF5E15] hover:-translate-y-0.5 transition shadow-[0_4px_16px_rgba(232,112,34,.35)] whitespace-nowrap"
                  >
                    Probar gratis →
                  </Link>
                </>
              )}
            </div>
          </div>
        </nav>

        {/* Hero */}
        <section className="pt-[164px] pb-20 px-6">
          <div className="max-w-6xl mx-auto grid lg:grid-cols-2 gap-16 items-center">
            <div className="max-w-xl">
              <div className="inline-flex items-center gap-2 text-sm font-bold px-4 py-2 rounded-full bg-[#1A2B4A] text-[#E87022] mb-6">
                Para constructores y contratistas
              </div>
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-[#1A2B4A] leading-[1.1] tracking-tight mb-6">
                ¿Otra vez comparando presupuestos <span className="relative inline-block">a mano<span className="absolute left-0 right-0 -bottom-0.5 h-1.5 bg-[#E87022]/30 rounded" /></span>?
              </h1>
              <p className="text-lg text-gray-600 leading-relaxed mb-8 max-w-md">
                Subís los PDFs de tu corralón a VectorAI y te cruza los precios, detecta quién te
                está cobrando de más y te devuelve una tabla lista para comparar. En 3 minutos.
              </p>
              <div className="flex flex-wrap items-center gap-4 mb-6">
                <Link
                  href="/registro"
                  className="inline-flex items-center gap-2 bg-[#E87022] text-white text-lg font-bold px-10 py-4 rounded-full hover:bg-[#CF5E15] hover:-translate-y-0.5 transition shadow-[0_4px_16px_rgba(232,112,34,.35)]"
                >
                  Probar gratis →
                </Link>
                <a href="#como-funciona" className="inline-flex items-center gap-2 border-2 border-[#1A2B4A] text-[#1A2B4A] font-bold px-6 py-3.5 rounded-full hover:bg-[#1A2B4A] hover:text-white transition">
                  Ver cómo funciona
                </a>
              </div>
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm font-medium text-gray-600">
                <span>✅ Sin tarjeta</span>
                <span>✅ Sin instalación</span>
                <span>✅ 30 segundos al primer resultado</span>
              </div>
              <p className="text-sm text-gray-400 mt-4">
                ¿Preferís mandar los PDFs por WhatsApp?{" "}
                <a href={WA_CARGAR} target="_blank" rel="noopener noreferrer" className="text-[#E87022] font-semibold hover:underline">
                  También podés cargarlos así →
                </a>
              </p>
            </div>

            {/* WhatsApp mockup — muestra el canal alternativo de carga */}
            <div className="lg:order-last">
              <div className="max-w-[380px] mx-auto bg-[#E5E7EB] rounded-3xl shadow-xl overflow-hidden border border-black/5">
                <div className="bg-[#075E54] text-white px-4 py-3 flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-[#E87022] flex items-center justify-center">
                    <svg width="20" height="20" viewBox="0 0 100 100" fill="none">
                      <rect x="18" y="26" width="64" height="13" rx="6.5" fill="#fff" />
                      <rect x="30" y="48" width="40" height="13" rx="6.5" fill="#fff" />
                      <rect x="40" y="70" width="20" height="13" rx="6.5" fill="#1A2B4A" />
                    </svg>
                  </div>
                  <div>
                    <div className="text-sm font-bold">Vectorai</div>
                    <div className="text-xs opacity-70">en línea</div>
                  </div>
                </div>
                <div className="bg-[#ECE5DD] p-4 min-h-[360px] flex flex-col gap-3">
                  <div className="max-w-[85%] self-end bg-[#DCF8C6] rounded-lg rounded-tr-none px-3 py-2 text-[13px] leading-relaxed">
                    Te mando 3 presupuestos de cemento 🏗️
                    <div className="text-[11px] text-gray-400 text-right mt-1">10:42</div>
                  </div>
                  <div className="max-w-[85%] self-start bg-white rounded-lg rounded-tl-none px-3 py-2 text-[13px] leading-relaxed shadow-sm">
                    📊 Listo, comparé los 3 presupuestos. Mirá:
                    <table className="w-full text-[11px] mt-2">
                      <tbody>
                        <tr>
                          <th className="bg-[#1A2B4A] text-white text-left px-1.5 py-1 font-semibold">Material</th>
                          <th className="bg-[#1A2B4A] text-white px-1.5 py-1 font-semibold">A</th>
                          <th className="bg-[#1A2B4A] text-white px-1.5 py-1 font-semibold">B</th>
                          <th className="bg-[#1A2B4A] text-white px-1.5 py-1 font-semibold">C</th>
                        </tr>
                        <tr className="bg-white">
                          <td className="px-1.5 py-1 border-b border-gray-100">Cemento (bolsa)</td>
                          <td className="px-1.5 py-1 border-b border-gray-100 text-center text-red-600">$47.200</td>
                          <td className="px-1.5 py-1 border-b border-gray-100 text-center">$42.500</td>
                          <td className="px-1.5 py-1 border-b border-gray-100 text-center text-green-600 font-bold">$38.900 ✓</td>
                        </tr>
                        <tr className="bg-white">
                          <td className="px-1.5 py-1 border-b border-gray-100">Cal (bolsa)</td>
                          <td className="px-1.5 py-1 border-b border-gray-100 text-center">$18.400</td>
                          <td className="px-1.5 py-1 border-b border-gray-100 text-center text-green-600 font-bold">$15.800 ✓</td>
                          <td className="px-1.5 py-1 border-b border-gray-100 text-center">$16.100</td>
                        </tr>
                        <tr className="bg-white">
                          <td className="px-1.5 py-1">Ladrillo (millar)</td>
                          <td className="px-1.5 py-1 text-center text-red-600">$125.000</td>
                          <td className="px-1.5 py-1 text-center">$108.500</td>
                          <td className="px-1.5 py-1 text-center text-green-600 font-bold">$102.000 ✓</td>
                        </tr>
                      </tbody>
                    </table>
                    <div className="text-[11px] text-gray-400 text-right mt-1">10:42</div>
                  </div>
                  <div className="max-w-[85%] self-start bg-white rounded-lg rounded-tl-none px-3 py-2 text-[13px] leading-relaxed shadow-sm">
                    <strong className="text-green-600">💰 Te ahorrás $148.200</strong> comprando el cemento y el ladrillo en Corralón C.
                    <br /><br />
                    ⚠️ Corralón A te está cobrando un <strong>21% más</strong> en cemento.
                    <div className="text-[11px] text-gray-400 text-right mt-1">10:42</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Stats bar */}
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

        {/* Caso real */}
        <section className="py-24 px-6">
          <div className="max-w-3xl mx-auto">
            <div className="text-center mb-12">
              <h2 className="text-3xl sm:text-4xl font-bold text-[#1A2B4A] tracking-tight mb-4">Un caso real, con números</h2>
              <p className="text-lg text-gray-600">Así le pasó a un contratista en Rosario.</p>
            </div>
            <div className="bg-white border-l-4 border-[#E87022] rounded-r-2xl shadow-sm p-6">
              <div className="text-xs font-bold uppercase tracking-wide text-[#E87022] mb-3">Caso real — Rosario, Santa Fe</div>
              <p className="text-[#1A2B4A] font-medium leading-relaxed">
                Necesitaba 120 bolsas de cemento para una losa. Mandó 4 presupuestos de corralones
                distintos a VectorAI. En 2 minutos supo que un corralón le cobraba{" "}
                <strong>$47.200</strong> la bolsa y otro, a 15 cuadras, <strong>$38.900</strong>.
              </p>
              <div className="font-bold text-lg text-green-600 mt-3">Ahorro: $996.000 en una sola compra</div>
            </div>
          </div>
        </section>

        {/* Demo visual */}
        <section className="bg-white py-24 px-6" id="demo">
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-12">
              <h2 className="text-3xl sm:text-4xl font-bold text-[#1A2B4A] tracking-tight mb-4">Esto es lo que vas a ver 👀</h2>
              <p className="text-lg text-gray-600">Mismos materiales, distintos nombres. VectorAI los une solo.</p>
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
                          {row.mejor === "a" ? "✓ Pérez" : "✓ Juan"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-center text-sm text-gray-400 mt-4">🟢 Verde = mejor precio · — = no cotiza ese ítem</p>
          </div>
        </section>

        {/* Cómo funciona */}
        <section className="py-24 px-6" id="como-funciona">
          <div className="max-w-5xl mx-auto">
            <div className="text-center mb-14">
              <h2 className="text-3xl sm:text-4xl font-bold text-[#1A2B4A] tracking-tight mb-4">Cuatro pasos. Eso es todo. 🙌</h2>
              <p className="text-lg text-gray-600">No hace falta saber nada de software ni de planillas complicadas.</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
              {[
                { n: "1", titulo: "Subís los PDFs", desc: "Arrastrás el presupuesto de cada proveedor en la web, o se los mandás a nuestro WhatsApp." },
                { n: "2", titulo: "La IA los lee", desc: "Extrae ítems, precios y unidades de forma automática. No tocás nada." },
                { n: "3", titulo: "Los cruza solo", desc: 'Entiende que "Perfil C 70" y "Perfil galv. 70x35" son lo mismo.' },
                { n: "4", titulo: "Comparativa lista", desc: "Tabla con el mejor precio por ítem. Descargable en Excel al instante." },
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

        {/* Features */}
        <section className="bg-white py-24 px-6" id="features">
          <div className="max-w-5xl mx-auto">
            <div className="text-center mb-14">
              <h2 className="text-3xl sm:text-4xl font-bold text-[#1A2B4A] tracking-tight mb-4">Lo que VectorAI hace por vos</h2>
              <p className="text-lg text-gray-600">Todo lo que necesitás para no pagar de más, en un solo lugar.</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[
                { titulo: "Entiende el IVA", desc: "Detecta si el precio viene con o sin IVA y aplica el factor correcto por proveedor. Sin cálculos manuales." },
                { titulo: "Aplica descuentos", desc: "Cargás el % de descuento por proveedor y VectorAI lo aplica automáticamente al comparar." },
                { titulo: "Matching inteligente", desc: "Reconoce variantes de nombres, abreviaturas y errores de tipeo. Hormigón H-21 = Hormigón H21." },
                { titulo: "Todos los rubros", desc: "Albañilería, steel frame, eléctrico, sanitario, pinturas. Todo en una sola comparativa." },
                { titulo: "Excel en un clic", desc: "Exportá la comparativa completa en Excel, lista para pasarle al cliente o archivar." },
                { titulo: "Web o WhatsApp", desc: "Subís los PDFs desde la web o se los mandás a nuestro WhatsApp, como te quede más cómodo." },
              ].map((f) => (
                <div key={f.titulo} className="bg-[#F5F0E8] rounded-2xl p-6 hover:-translate-y-1 transition">
                  <div className="text-[#E87022] font-bold text-2xl mb-3">✱</div>
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
                <div className="text-xl font-semibold text-[#1A2B4A] mb-1">Gratis 🙌</div>
                <div className="text-4xl font-bold text-[#1A2B4A] mb-1">$0</div>
                <p className="text-gray-400 text-sm mb-8">Para siempre</p>
                <ul className="space-y-3 text-sm text-gray-600 mb-8">
                  {[
                    "✅ Subís PDFs ilimitados",
                    "✅ Comparativa en pantalla",
                    "✅ Descarga en Excel",
                    "✅ Matching automático",
                    "❌ Sin revisión de ítems sin match",
                    "❌ Sin historial de comparativas",
                  ].map((f) => (
                    <li key={f} className="flex gap-2 leading-snug">{f}</li>
                  ))}
                </ul>
                <Link href="/registro" className="block text-center border-2 border-[#1A2B4A] text-[#1A2B4A] font-bold py-3.5 rounded-full hover:bg-[#1A2B4A] hover:text-white transition">
                  Empezar gratis
                </Link>
              </div>

              {/* Inicial — contenido provisorio, Pablo define el detalle */}
              <div className="bg-white rounded-3xl border-2 border-[#E87022]/40 p-8">
                <div className="text-xl font-semibold text-[#1A2B4A] mb-1">Inicial 🧰</div>
                <div className="text-4xl font-bold text-[#1A2B4A] mb-1">$18.000<span className="text-xl font-normal text-gray-400">/mes</span></div>
                <p className="text-gray-400 text-xs mb-8">Pesos argentinos · IVA incluido</p>
                <ul className="space-y-3 text-sm text-gray-600 mb-8">
                  {[
                    "✅ Todo lo del plan gratis",
                    "✅ Más comparativas por mes",
                    "✅ Historial de comparativas",
                    "✅ Revisión de ítems dudosos",
                    "❌ Sin funcionalidades avanzadas",
                  ].map((f) => (
                    <li key={f} className="flex gap-2 leading-snug">{f}</li>
                  ))}
                </ul>
                <Link href="/suscribirse" className="block text-center border-2 border-[#E87022] text-[#E87022] font-bold py-3.5 rounded-full hover:bg-[#E87022] hover:text-white transition">
                  Quiero el Inicial
                </Link>
              </div>

              {/* Advance */}
              <div className="bg-[#1A2B4A] rounded-3xl p-8 text-white relative overflow-hidden">
                <div className="absolute top-5 right-5 bg-[#E87022] text-xs font-bold px-3 py-1.5 rounded-full uppercase tracking-wide">
                  ⭐ Más popular
                </div>
                <div className="text-xl font-semibold mb-1">Advance 🚀</div>
                <div className="text-4xl font-bold mb-1 text-[#E87022]">$48.000<span className="text-xl font-normal text-white/60">/mes</span></div>
                <p className="text-white/60 text-xs mb-8">Pesos argentinos · IVA incluido</p>
                <ul className="space-y-3 text-sm mb-8">
                  {[
                    "✅ Todo lo del plan gratis",
                    "✅ Revisión de ítems sin match",
                    "✅ Historial de comparativas",
                    "✅ Eléctrico, sanitario, steel frame…",
                    "✅ Filtros y funcionalidades avanzadas",
                    "✅ Precio promedio de tu zona (próx.)",
                  ].map((f) => (
                    <li key={f} className="flex gap-2 text-white/85 leading-snug">{f}</li>
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
                a="Cualquier presupuesto de corralón, ferretería o proveedor de materiales de obra. Funciona con PDFs y fotos de papel. VectorAI está entrenado para leer formatos argentinos."
              />
              <FaqItem
                q="¿Calcula el IVA correctamente?"
                a="Sí. VectorAI aplica IVA 21% (o la alícuota que corresponda) y detecta si el presupuesto ya lo incluye o no. También aplica descuentos por proveedor."
              />
              <FaqItem
                q="¿Necesito instalar algo?"
                a="No. VectorAI funciona desde el navegador, sin instalar nada. Si preferís, también podés mandar los PDFs por WhatsApp y te devolvemos la comparación ahí."
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
        <section className="relative bg-[#0F172A] py-32 px-6 text-center overflow-hidden">
          <div
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] pointer-events-none"
            style={{ background: "radial-gradient(circle, rgba(232,112,34,.12) 0%, transparent 70%)" }}
          />
          <div className="relative max-w-xl mx-auto">
            <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight mb-6">
              Dejá de pagar de más.<br />En serio.
            </h2>
            <p className="text-lg text-white/70 mb-10">
              Un corralón le cobraba a un cliente $47.200 la bolsa de cemento. Otro, a 20 cuadras, $38.900.
              VectorAI lo encontró en 2 minutos.
            </p>
            <Link
              href="/registro"
              className="inline-flex items-center gap-2 bg-[#E87022] text-white text-lg font-bold px-10 py-4 rounded-full hover:bg-[#CF5E15] hover:-translate-y-0.5 transition shadow-[0_4px_16px_rgba(232,112,34,.35)]"
            >
              Probar VectorAI gratis →
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
            <span className="text-sm text-white/40">© 2026 · Hecho en Argentina 🇦🇷</span>
          </div>
          <a
            href={WA_CONSULTA}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-sm text-white/60 hover:text-white transition"
          >
            <WhatsAppIcon className="w-4 h-4" />
            Consultas por WhatsApp
          </a>
        </div>
      </footer>

      {/* Botón flotante WhatsApp */}
      <a
        href={WA_CONSULTA}
        target="_blank"
        rel="noopener noreferrer"
        className="fixed bottom-6 right-6 w-14 h-14 bg-green-500 text-white rounded-full flex items-center justify-center shadow-lg hover:bg-green-600 transition z-50"
        title="Consultas por WhatsApp"
      >
        <WhatsAppIcon className="w-6 h-6" />
      </a>
    </>
  );
}
