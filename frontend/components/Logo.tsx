/* Logo oficial VectorAI: isotipo embudo + wordmark "Vectorai".
   Usalo en login, registro, el nav del comparador y el footer.
   - dark: para fondos oscuros (barras blancas en vez de navy).
   - El "ai" va en minúscula y naranja: destaca por color, no por tamaño. */
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
        Vector<span style={{ color: "#E87022" }}>ai</span>
      </span>
    </span>
  );
}
