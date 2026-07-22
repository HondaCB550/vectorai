"use client";
export const dynamic = "force-dynamic";
import { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";
import Footer from "@/components/Footer";
import Logo from "@/components/Logo";

// Cae acá el link de confirmación de email (Confirm signup) con
// ?token_hash=...&type=signup. Verificamos el token con verifyOtp (mismo patrón
// que /actualizar-clave: sin PKCE / sin code verifier, que se pierde en el
// redirect del mail) y, si valida, dejamos la sesión y vamos al comparador.
function ConfirmarInner() {
  const router = useRouter();
  const [estado, setEstado] = useState<"verificando" | "ok" | "error">("verificando");

  useEffect(() => {
    const supa = createClient();
    const params = new URLSearchParams(window.location.search);
    const tokenHash = params.get("token_hash");
    const type = params.get("type");
    if (!tokenHash || !type) {
      setEstado("error");
      return;
    }
    supa.auth
      .verifyOtp({ token_hash: tokenHash, type: type as "signup" })
      .then(({ error }) => {
        if (error) {
          setEstado("error");
          return;
        }
        setEstado("ok");
        setTimeout(() => router.push("/app/comparar"), 1600);
      });
  }, [router]);

  return (
    <>
      <main className="min-h-screen bg-[#F5F0E8] flex items-center justify-center px-4">
        <div className="w-full max-w-md">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm w-full p-10 text-center">
            <Link href="/" className="inline-block mb-8">
              <Logo />
            </Link>

            {estado === "verificando" && (
              <>
                <h1 className="text-xl font-bold mb-2">Confirmando tu email…</h1>
                <p className="text-gray-700 text-sm">Un segundo, estamos activando tu cuenta.</p>
              </>
            )}

            {estado === "ok" && (
              <>
                <h1 className="text-xl font-bold mb-2">¡Email confirmado!</h1>
                <p className="text-gray-700 text-sm">Tu cuenta quedó activa. Te llevamos al comparador…</p>
              </>
            )}

            {estado === "error" && (
              <>
                <h1 className="text-xl font-bold mb-2">No pudimos confirmar el email</h1>
                <p className="text-gray-700 text-sm mb-6">
                  El link no es válido o ya expiró. Volvé a registrarte o iniciá sesión
                  si ya confirmaste tu cuenta.
                </p>
                <div className="flex items-center justify-center gap-4 text-sm font-medium">
                  <Link href="/registro" className="text-blue-600 hover:underline">Registrarme</Link>
                  <span className="text-gray-300">·</span>
                  <Link href="/login" className="text-blue-600 hover:underline">Iniciar sesión</Link>
                </div>
              </>
            )}
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}

export default function Confirmar() {
  return (
    <Suspense>
      <ConfirmarInner />
    </Suspense>
  );
}
