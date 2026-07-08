// Horas de desarrollo del proyecto VectorAI, reconstruidas del tiempo ACTIVO de
// trabajo con Claude (tiempo entre mensajes de cada sesión; los huecos > 15 min
// no cuentan como trabajo). Incluye todo el proyecto: el SaaS (presupuestor/),
// el presupuestador previo (Cotizaciones) y Bonhaus / steel frame.
//
// PARA ACTUALIZAR: editar los números de abajo y hacer `git push origin main`.
// Vercel redeploya solo y el cuadradito de /app/admin/metricas queda online.
export const HORAS_PROYECTO = {
  total: 53.8, // horas totales del proyecto (acumuladas)
  semana: 27.7, // horas de la última semana medida
  previo: 26.1, // horas previas a esa semana (total = previo + semana)
  actualizado: "8 jul 2026", // fecha de la última actualización
};
