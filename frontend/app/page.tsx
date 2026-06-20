import Link from "next/link";

export default function Landing() {
  return (
    <main className="min-h-screen bg-white">
      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-5 border-b border-gray-100">
        <span className="text-xl font-bold text-gray-900 tracking-tight">VectorAI <span className="text-xs font-semibold text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded-full align-middle">beta</span></span>
        <div className="flex gap-4 items-center">
          <Link href="/login" className="text-sm text-gray-500 hover:text-gray-800 transition">
            Iniciar sesión
          </Link>
          <Link
            href="/registro"
            className="bg-blue-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-blue-700 transition"
          >
            Probalo gratis
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-4xl mx-auto px-8 py-24 text-center">
        <span className="inline-block bg-blue-50 text-blue-700 text-xs font-semibold tracking-widest uppercase px-3 py-1 rounded-full mb-6">
          Para constructores
        </span>
        <h1 className="text-5xl font-bold text-gray-900 leading-tight mb-6">
          Compará presupuestos<br />de distintos proveedores
        </h1>
        <p className="text-xl text-gray-500 mb-10 max-w-2xl mx-auto leading-relaxed">
          Subís los PDFs de tus corralones y proveedores. El sistema los lee, normaliza los
          materiales y genera la comparativa en segundos. Descargable en múltiples formatos.
        </p>
        <Link
          href="/registro"
          className="inline-block bg-blue-600 text-white text-base font-semibold px-8 py-4 rounded-xl hover:bg-blue-700 transition shadow-sm"
        >
          Probalo gratis
        </Link>
        <p className="text-sm text-gray-400 mt-4">Gratis: 2 PDFs · 1 comparativa · descarga Excel</p>
      </section>

      {/* Cómo funciona */}
      <section className="bg-gray-50 py-20 px-8">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-12">Cómo funciona</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            {[
              { n: "1", titulo: "Subís los PDFs", desc: "PDF, JPG o imagen del presupuesto de cada proveedor" },
              { n: "2", titulo: "La IA lo lee", desc: "Extrae ítems, precios y cantidades automáticamente" },
              { n: "3", titulo: "Normaliza materiales", desc: 'Entiende que "Placa verde Durlock" = "Placa RH 12.5mm"' },
              { n: "4", titulo: "Comparativa lista", desc: "Tabla con mejor precio por ítem. Descargá en Excel, PDF o JPG." },
            ].map((s) => (
              <div key={s.n} className="text-center">
                <div className="w-10 h-10 bg-blue-600 text-white rounded-full flex items-center justify-center text-lg font-bold mx-auto mb-4">
                  {s.n}
                </div>
                <h3 className="font-semibold text-gray-800 mb-2">{s.titulo}</h3>
                <p className="text-sm text-gray-500">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Tabla de ejemplo */}
      <section className="max-w-4xl mx-auto px-8 py-20">
        <h2 className="text-2xl font-bold text-gray-900 text-center mb-4">El resultado</h2>
        <p className="text-gray-500 text-center mb-10">
          Mismos materiales, distintos nombres. El sistema los une automáticamente.
        </p>
        <div className="overflow-x-auto rounded-xl border border-gray-200 shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Material</th>
                <th className="px-4 py-3 font-semibold text-gray-600">Distribuidor Juan</th>
                <th className="px-4 py-3 font-semibold text-gray-600">Corralón Pérez</th>
                <th className="px-4 py-3 font-semibold text-gray-600">Mejor</th>
              </tr>
            </thead>
            <tbody>
              {[
                { mat: "Perfil C galv. 70x35 0.9mm", a: "$1.850", b: "$1.620", mejor: "b" },
                { mat: "Placa RH 12.5mm", a: "$18.500", b: "$19.100", mejor: "a" },
                { mat: "OSB 9mm 1.22×2.44m", a: "$8.900", b: "$8.700", mejor: "b" },
                { mat: "Lana mineral 50mm", a: "$9.200", b: "—", mejor: "a" },
              ].map((row, i) => (
                <tr key={i} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-700">{row.mat}</td>
                  <td className={`px-4 py-3 text-center font-medium ${row.mejor === "a" ? "bg-green-50 text-green-700 font-semibold" : "text-gray-600"}`}>{row.a}</td>
                  <td className={`px-4 py-3 text-center font-medium ${row.mejor === "b" ? "bg-green-50 text-green-700 font-semibold" : "text-gray-600"}`}>{row.b}</td>
                  <td className="px-4 py-3 text-center">
                    <span className="text-xs bg-green-100 text-green-700 font-semibold px-2 py-1 rounded-full">
                      {row.mejor === "a" ? "Distribuidor Juan" : "Pérez"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Planes */}
      <section className="bg-gray-50 py-20 px-8">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-12">Planes</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-2xl border border-gray-200 p-8">
              <div className="text-lg font-bold text-gray-900 mb-1">Gratuito</div>
              <div className="text-3xl font-bold text-gray-900 mb-6">$0</div>
              <ul className="space-y-3 text-sm text-gray-600 mb-8">
                {["2 PDFs (1 por proveedor)", "Comparativa en pantalla", "Descarga Excel · PDF · JPG", "Matching automático"].map((f) => (
                  <li key={f} className="flex gap-2"><span className="text-green-500">✓</span>{f}</li>
                ))}
                <li className="flex gap-2 text-gray-400"><span>✗</span>Revisión manual de sin-match</li>
                <li className="flex gap-2 text-gray-400"><span>✗</span>Múltiples rubros y proveedores</li>
              </ul>
              <Link href="/registro" className="block text-center border border-gray-300 text-gray-700 font-medium py-3 rounded-xl hover:bg-gray-50 transition">
                Probalo gratis
              </Link>
            </div>

            <div className="bg-blue-600 rounded-2xl p-8 text-white relative">
              <div className="absolute top-4 right-4 bg-white/20 text-xs font-bold px-2 py-1 rounded-full">Más popular</div>
              <div className="text-lg font-bold mb-1">Advance</div>
              <div className="text-3xl font-bold mb-1">$48.000<span className="text-lg font-normal opacity-70">/mes</span></div>
              <p className="text-blue-100 text-xs mb-6">Pesos argentinos · IVA incluido</p>
              <ul className="space-y-3 text-sm mb-8">
                {[
                  "PDFs ilimitados",
                  "Todos los rubros (eléctrico, sanitario, steel frame…)",
                  "Revisión manual de ítems sin match",
                  "Historial de comparativas",
                  "Filtros y funcionalidades avanzadas",
                  "Precio promedio de tu zona (próximamente)",
                ].map((f) => (
                  <li key={f} className="flex gap-2"><span className="text-blue-200">✓</span>{f}</li>
                ))}
              </ul>
              <Link href="/registro?plan=advance" className="block text-center bg-white text-blue-600 font-semibold py-3 rounded-xl hover:bg-blue-50 transition">
                Suscribirme
              </Link>
            </div>
          </div>
        </div>
      </section>

      <footer className="text-center py-10 text-sm text-gray-400 border-t border-gray-100">
        VectorAI · Bonhaus · Buenos Aires, Argentina
      </footer>
    </main>
  );
}
