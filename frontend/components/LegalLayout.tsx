import Link from "next/link";
import Footer from "@/components/Footer";
import Logo from "@/components/Logo";

export default function LegalLayout({ titulo, actualizacion, children }: {
  titulo: string;
  actualizacion: string;
  children: React.ReactNode;
}) {
  return (
    <>
      <main className="min-h-screen bg-[#F5F0E8] px-4 py-10">
        <div className="max-w-3xl mx-auto">
          <Link href="/" className="inline-flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-[#1A2B4A] transition mb-4">
            ← Volver al inicio
          </Link>
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-8 sm:p-12">
            <Link href="/" className="block mb-8"><Logo /></Link>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">{titulo}</h1>
            <p className="text-sm text-gray-400 mb-8">Última actualización: {actualizacion}</p>
            <div className="space-y-6 text-[15px] leading-relaxed text-gray-700 [&_h2]:text-lg [&_h2]:font-bold [&_h2]:text-gray-900 [&_h2]:mt-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1.5 [&_strong]:text-gray-900">
              {children}
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
