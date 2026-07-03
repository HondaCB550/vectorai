/* Logo oficial VectorAI: isotipo embudo + wordmark "Vectorai".
   Usalo en login, registro, el nav del comparador y el footer.
   - dark: para fondos oscuros (barras blancas en vez de navy).
   - El wordmark va TODO del mismo tono (navy, o blanco en dark): el "ai"
     no se diferencia por color (pedido de Pablo 03-07-2026; antes naranja). */
export default function Logo({
  dark = false,
  className = "",
}: {
  dark?: boolean;
  className?: string;
}) {
  const bars = dark ? "#ffffff" : "#1A2B4A";
  return (
    <span
      className={`inline-flex items-center gap-2 text-xl font-bold tracking-tight ${className}`}
      style={{ fontFamily: "var(--font-display), 'Space Grotesk', sans-serif" }}
    >
      <svg width="24" height="24" viewBox="0 0 100 100" fill="none" aria-hidden="true">
        <rect x="18" y="26" width="64" height="13" rx="6.5" fill={bars} />
        <rect x="30" y="48" width="40" height="13" rx="6.5" fill={bars} />
        <rect x="40" y="70" width="20" height="13" rx="6.5" fill="#E87022" />
      </svg>
      <span style={{ color: dark ? "#ffffff" : "#1A2B4A" }}>
        Vectorai
      </span>
    </span>
  );
}
