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
    </>
  );
}
