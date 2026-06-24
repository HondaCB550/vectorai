import Link from "next/link";
import Footer from "@/components/Footer";

export default function Landing() {
  return (
    <>
    <main className="min-h-screen bg-white">

      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-4 border-b border-gray-100 sticky top-0 bg-white/95 backdrop-blur-sm z-50">
        <span className="text-xl font-black text-gray-900 tracking-tight">
          Vector<span className="text-blue-600">AI</span>
          <span className="ml-2 text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full align-middle">beta</span>
        </span>
        <div className="flex gap-3 items-center">
          <Link href="/login" className="text-sm text-gray-500 hover:text-gray-800 transition font-medium">
            Entrar
          </Link>
          <Link
            href="/registro"
            className="bg-blue-600 text-white text-sm font-bold px-5 py-2.5 rounded-xl hover:bg-blue-700 transition shadow-sm"
          >
            Empezar gratis 🚀
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-6 pt-20 pb-16 text-center">
        <div className="inline-flex items-center gap-2 bg-blue-50 text-blue-700 text-sm font-semibold px-4 py-2 rounded-full mb-8">
          <span>⚡</span> Compará presupuestos en segundos
        </div>
        <h1 className="text-5xl md:text-6xl font-black text-gray-900 leading-tight mb-6">
          Subís los PDFs.<br />
          <span className="text-blue-600">La IA hace el resto.</span>
        </h1>
        <p className="text-xl text-gray-500 mb-10 max-w-2xl mx-auto leading-relaxed">
          Cargás los presupuestos de cada corralón o proveedor, y VectorAI los cruza automáticamente.
          Sabés al instante quién cobra menos por cada material.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center items-center">
          <Link
            href="/registro"
            className="bg-blue-600 text-white text-lg font-bold px-10 py-4 rounded-2xl hover:bg-blue-700 transition shadow-md"
          >
            Probalo gratis 👇
          </Link>
          <Link
            href="/login"
            className="text-gray-500 text-base font-medium hover:text-gray-800 transition"
          >
            Ya tengo cuenta →
          </Link>
        </div>
        <p className="text-sm text-gray-400 mt-5">Sin tarjeta. Sin instalación. Funciona desde el celular.</p>

        {/* Métricas */}
        <div className="mt-16 grid grid-cols-3 gap-6 max-w-xl mx-auto">
          {[
            { n: "3 min", label: "de la primera carga a la comparativa" },
            { n: "80%", label: "de ítems matchean automáticamente" },
            { n: "100%", label: "argentino, hecho para constructoras locales" },
          ].map((m) => (
            <div key={m.n} className="text-center">
              <div className="text-3xl font-black text-blue-600">{m.n}</div>
              <div className="text-xs text-gray-500 mt-1 leading-snug">{m.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Demo visual */}
      <section className="bg-gray-50 py-16 px-6">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-black text-gray-900 text-center mb-3">
            Esto es lo que vas a ver 👀
          </h2>
          <p className="text-gray-500 text-center mb-10 text-lg">
            Mismos materiales, distintos nombres. VectorAI los une solo.
          </p>
          <div className="overflow-x-auto rounded-2xl border border-gray-200 shadow-lg bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left px-5 py-4 font-bold text-gray-700 bg-gray-50">Material</th>
                  <th className="px-5 py-4 font-bold text-center" style={{color:'#3373C2'}}>Corralón Pérez</th>
                  <th className="px-5 py-4 font-bold text-center" style={{color:'#D45C00'}}>Distribuidora Juan</th>
                  <th className="px-5 py-4 font-bold text-center bg-gray-50 text-gray-700">Mejor precio</th>
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
                    <td className={`px-5 py-3.5 text-center font-bold ${row.mejor === "a" ? "bg-green-50 text-green-700" : "text-gray-500"}`}>{row.a}</td>
                    <td className={`px-5 py-3.5 text-center font-bold ${row.mejor === "b" ? "bg-green-50 text-green-700" : "text-gray-500"}`}>{row.b}</td>
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
          <p className="text-center text-sm text-gray-400 mt-4">
            🟢 Verde = mejor precio · — = no cotiza ese ítem
          </p>
        </div>
      </section>

      {/* Cómo funciona */}
      <section className="max-w-5xl mx-auto px-6 py-20">
        <h2 className="text-3xl font-black text-gray-900 text-center mb-3">
          Cuatro pasos. Eso es todo. 🙌
        </h2>
        <p className="text-gray-500 text-center mb-14 text-lg">
          No hace falta saber nada de software ni de planillas complicadas.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {[
            { emoji: "📎", n: "1", titulo: "Subís los PDFs", desc: "Arrastrás el presupuesto de cada proveedor. PDF, JPG, imagen, lo que tengas." },
            { emoji: "🤖", n: "2", titulo: "La IA los lee", desc: "Extrae ítems, precios y unidades de forma automática. No tocás nada." },
            { emoji: "🔗", n: "3", titulo: "Los cruza solo", desc: 'Entiende que "Perfil C 70" y "Perfil galv. 70x35" son lo mismo.' },
            { emoji: "📊", n: "4", titulo: "Comparativa lista", desc: "Tabla con el mejor precio por ítem. Descargable en Excel al instante." },
          ].map((s) => (
            <div key={s.n} className="text-center">
              <div className="text-4xl mb-3">{s.emoji}</div>
              <div className="w-7 h-7 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-black mx-auto mb-3">
                {s.n}
              </div>
              <h3 className="font-bold text-gray-800 mb-2 text-base">{s.titulo}</h3>
              <p className="text-sm text-gray-500 leading-relaxed">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="bg-blue-600 py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-black text-white text-center mb-3">
            Hecho para la construcción argentina 🏗️
          </h2>
          <p className="text-blue-100 text-center mb-14 text-lg">
            No es una herramienta genérica. Está pensada para tu trabajo diario.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                emoji: "🧾",
                titulo: "Entiende el IVA",
                desc: "Detecta si el precio viene con o sin IVA y aplica el factor correcto por proveedor. Sin cálculos manuales.",
              },
              {
                emoji: "💸",
                titulo: "Aplica descuentos",
                desc: "Sauce tiene 8% de descuento, Maderera 10%. VectorAI los aplica automáticamente al comparar.",
              },
              {
                emoji: "🔍",
                titulo: "Matching inteligente",
                desc: "Reconoce variantes de nombres, abreviaturas y errores de tipeo. Hormigón H-21 = Hormigón H21.",
              },
              {
                emoji: "📐",
                titulo: "Todos los rubros",
                desc: "Albañilería, steel frame, eléctrico, sanitario, pinturas. Todo en una sola comparativa.",
              },
              {
                emoji: "⚡",
                titulo: "Excel en un clic",
                desc: "Exportá la comparativa completa en Excel con colores, totales y el mejor precio marcado.",
              },
              {
                emoji: "📱",
                titulo: "Desde el celular",
                desc: "Sacás foto al presupuesto del proveedor y listo. No necesitás la PC.",
              },
            ].map((f) => (
              <div key={f.titulo} className="bg-white/10 rounded-2xl p-6 text-white">
                <div className="text-3xl mb-3">{f.emoji}</div>
                <h3 className="font-bold text-lg mb-2">{f.titulo}</h3>
                <p className="text-blue-100 text-sm leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Planes */}
      <section className="max-w-3xl mx-auto px-6 py-20">
        <h2 className="text-3xl font-black text-gray-900 text-center mb-3">
          Precios sin vueltas 💰
        </h2>
        <p className="text-gray-500 text-center mb-12 text-lg">
          Arrancás gratis. Si te sirve, te suscribís.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Free */}
          <div className="bg-white rounded-3xl border-2 border-gray-200 p-8">
            <div className="text-2xl font-black text-gray-900 mb-1">Gratis 🙌</div>
            <div className="text-4xl font-black text-gray-900 mb-1">$0</div>
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
            <Link href="/registro" className="block text-center border-2 border-gray-300 text-gray-700 font-bold py-3.5 rounded-2xl hover:bg-gray-50 transition">
              Empezar gratis
            </Link>
          </div>

          {/* Pro */}
          <div className="bg-blue-600 rounded-3xl p-8 text-white relative overflow-hidden">
            <div className="absolute top-5 right-5 bg-white/20 text-xs font-black px-3 py-1.5 rounded-full">
              ⭐ Más popular
            </div>
            <div className="text-2xl font-black mb-1">Advance 🚀</div>
            <div className="text-4xl font-black mb-1">$48.000<span className="text-xl font-normal opacity-70">/mes</span></div>
            <p className="text-blue-200 text-xs mb-8">Pesos argentinos · IVA incluido</p>
            <ul className="space-y-3 text-sm mb-8">
              {[
                "✅ Todo lo del plan gratis",
                "✅ Revisión de ítems sin match",
                "✅ Historial de comparativas",
                "✅ Eléctrico, sanitario, steel frame…",
                "✅ Filtros y funcionalidades avanzadas",
                "✅ Precio promedio de tu zona (próx.)",
              ].map((f) => (
                <li key={f} className="flex gap-2 text-blue-50 leading-snug">{f}</li>
              ))}
            </ul>
            <Link href="/suscribirse" className="block text-center bg-white text-blue-600 font-black py-3.5 rounded-2xl hover:bg-blue-50 transition">
              Quiero el Advance
            </Link>
          </div>
        </div>
      </section>

      {/* CTA final */}
      <section className="bg-gray-50 py-20 px-6 text-center">
        <h2 className="text-4xl font-black text-gray-900 mb-4">
          ¿Cuánto estás pagando de más? 🤔
        </h2>
        <p className="text-xl text-gray-500 mb-10 max-w-xl mx-auto">
          Con VectorAI lo sabés en minutos. Probalo gratis, sin necesidad de tarjeta.
        </p>
        <Link
          href="/registro"
          className="inline-block bg-blue-600 text-white text-xl font-black px-12 py-5 rounded-2xl hover:bg-blue-700 transition shadow-lg"
        >
          Empezar ahora 🚀
        </Link>
        <p className="text-sm text-gray-400 mt-5">
          Sin instalación · Funciona en el celular · 100% argentino
        </p>
      </section>

    </main>
    <Footer />
    </>
  );
}
