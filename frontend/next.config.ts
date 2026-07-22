import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Headers de seguridad (auditoría CSO 22-07-2026). Antes solo salía HSTS.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          // Referrer-Policy es el que más importa acá: los ids de comparativa
          // viajan en la URL (/app/historial/<uuid>) y sin esto se filtraban en
          // el Referer hacia cualquier host externo al que el usuario navegara.
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // Nada de Vectorai se embebe en un iframe: corta clickjacking sobre
          // las acciones destructivas (borrar comparativa, cancelar plan).
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), interest-cohort=()" },
        ],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/carosio",
        destination: "/carosio.html",
      },
    ];
  },
};

export default nextConfig;
