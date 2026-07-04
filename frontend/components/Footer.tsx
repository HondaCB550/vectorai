import Link from "next/link";

export default function Footer() {
  return (
    <>
      {/* Footer */}
      <footer className="text-center py-10 text-sm text-gray-400 border-t border-gray-100">
        <div>
          <span className="font-bold text-[#1A2B4A]">Vectorai</span> · Buenos Aires, Argentina
        </div>
        <div className="mt-2 space-x-3">
          <Link href="/terminos" className="hover:text-gray-600 transition">Términos y Condiciones</Link>
          <span>·</span>
          <Link href="/privacidad" className="hover:text-gray-600 transition">Privacidad</Link>
        </div>
      </footer>

      {/* WhatsApp Button */}
      <a
        href="https://wa.me/5492241410393?text=Hola%20VectorAI%2C%20tengo%20una%20duda"
        target="_blank"
        rel="noopener noreferrer"
        className="fixed bottom-6 right-6 w-14 h-14 bg-green-500 text-white rounded-full flex items-center justify-center shadow-lg hover:bg-green-600 transition z-50 font-bold text-xl"
        title="Contactar por WhatsApp"
      >
        💬
      </a>
    </>
  );
}
