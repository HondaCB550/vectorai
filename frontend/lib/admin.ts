// Emails con acceso al panel de administración.
// Debe coincidir con ADMIN_EMAILS del backend (api/main.py).
export const ADMIN_EMAILS = ["bontempopablo@gmail.com"];

export function esAdmin(email?: string | null): boolean {
  return !!email && ADMIN_EMAILS.includes(email.toLowerCase());
}
