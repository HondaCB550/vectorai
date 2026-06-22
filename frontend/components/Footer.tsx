export default function Footer() {
  return (
    <>
      {/* Footer */}
      <footer className="text-center py-10 text-sm text-gray-400 border-t border-gray-100">
        VectorAI · Buenos Aires, Argentina
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
