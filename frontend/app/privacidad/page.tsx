import LegalLayout from "@/components/LegalLayout";

export const metadata = { title: "Política de Privacidad — Vectorai" };

const TH = "text-left font-semibold text-gray-900 px-3 py-2 border-b border-gray-200";
const TD = "px-3 py-2 border-b border-gray-100 align-top";

export default function Privacidad() {
  return (
    <LegalLayout titulo="Política de Privacidad" actualizacion="17 de julio de 2026">
      <section>
        <h2>1. Responsable</h2>
        <p>
          Pablo Martín Bontempo, CUIT 20-26435985-7, con domicilio en Orzali 1035, UF 35, Chascomús, Provincia de Buenos
          Aires, Argentina, con contacto en <strong>hola@vectorai.com.ar</strong>, es responsable del tratamiento de los
          datos personales recolectados a través de vectorai.com.ar. Marco normativo: Ley 25.326 de Protección de Datos
          Personales.
        </p>
      </section>

      <section>
        <h2>2. Qué datos recolectamos</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className={TH}>Categoría</th>
                <th className={TH}>Datos</th>
                <th className={TH}>Finalidad</th>
              </tr>
            </thead>
            <tbody>
              <tr><td className={TD}>Cuenta</td><td className={TD}>Email, contraseña (hasheada)</td><td className={TD}>Autenticación y gestión de la cuenta</td></tr>
              <tr><td className={TD}>Uso</td><td className={TD}>Comparativas realizadas, plan contratado, contadores mensuales</td><td className={TD}>Prestación del servicio y límites de plan</td></tr>
              <tr><td className={TD}>Documentos</td><td className={TD}>Presupuestos subidos y los ítems extraídos de ellos</td><td className={TD}>Generación de comparativas</td></tr>
              <tr><td className={TD}>Precios</td><td className={TD}>Material, precio, unidad, proveedor, zona y fecha</td><td className={TD}>Históricos y estadísticas del servicio</td></tr>
              <tr><td className={TD}>Pago</td><td className={TD}>Se procesan en MercadoPago; Vectorai <strong>no accede ni almacena datos de tarjetas</strong></td><td className={TD}>Cobro de suscripciones</td></tr>
              <tr><td className={TD}>Técnicos</td><td className={TD}>Logs de acceso y errores</td><td className={TD}>Seguridad y diagnóstico</td></tr>
            </tbody>
          </table>
        </div>
        <p className="mt-3">No recolectamos datos sensibles (art. 2, Ley 25.326).</p>
      </section>

      <section>
        <h2>3. Cómo usamos los datos</h2>
        <ul>
          <li>Prestar el servicio: extraer, emparejar y comparar los presupuestos que subís.</li>
          <li>Mantener históricos de precios. Los datos de precios se usan — y pueden comercializarse en informes de mercado — únicamente en forma <strong>agregada y disociada</strong>: sin identificar al usuario, a su empresa ni a sus operaciones.</li>
          <li>Comunicaciones operativas (confirmación de cuenta, avisos de pago, cambios de términos).</li>
          <li><strong>Comunicaciones comerciales:</strong> con tu consentimiento, podremos enviarte por email novedades del producto, mejoras y promociones (propias o de materiales/proveedores). Todo envío incluye una opción de <strong>baja inmediata</strong>, y podés pedir la baja en cualquier momento escribiendo a hola@vectorai.com.ar.</li>
          <li>No vendemos ni cedemos datos personales a terceros.</li>
        </ul>
      </section>

      <section>
        <h2>4. Procesamiento por IA</h2>
        <p>
          La extracción de ítems desde fotos y documentos escaneados utiliza servicios de inteligencia artificial de
          terceros (Anthropic Claude y/o Google Cloud Vision). Los documentos se envían a esos proveedores únicamente para
          su procesamiento y conforme a sus políticas de datos empresariales; no se utilizan para entrenar modelos de
          terceros según los términos comerciales vigentes de dichos proveedores.
        </p>
      </section>

      <section>
        <h2>5. Dónde se almacenan</h2>
        <p>
          Los datos se alojan en proveedores de infraestructura internacional: Supabase (base de datos y autenticación),
          Railway (backend) y Vercel (frontend), con servidores ubicados principalmente en EE. UU. Al usar el servicio, el
          usuario consiente esta transferencia internacional en los términos del art. 12 de la Ley 25.326, con proveedores
          que ofrecen niveles adecuados de protección contractual.
        </p>
      </section>

      <section>
        <h2>6. Plazos de conservación</h2>
        <ul>
          <li><strong>Datos de cuenta:</strong> mientras la cuenta esté activa y hasta 12 meses después de su baja.</li>
          <li><strong>Archivos subidos:</strong> los archivos originales (PDF, fotos, planillas) se procesan y <strong>no se conservan</strong>, con una excepción: cuando el sistema no logra leer automáticamente un formato nuevo, el archivo se guarda temporalmente en un repositorio privado de acceso restringido, al solo efecto de desarrollar el soporte de ese formato, y se elimina una vez resuelto. Se conservan los ítems extraídos y las comparativas generadas, durante el plazo que corresponda al plan del usuario.</li>
          <li><strong>Precios históricos disociados:</strong> sin plazo, por su carácter estadístico.</li>
        </ul>
      </section>

      <section>
        <h2>7. Derechos del titular</h2>
        <p>
          Conforme a la Ley 25.326, el usuario puede ejercer los derechos de <strong>acceso, rectificación, actualización y
          supresión</strong> de sus datos escribiendo a hola@vectorai.com.ar. La AGENCIA DE ACCESO A LA INFORMACIÓN PÚBLICA,
          órgano de control de la Ley 25.326, tiene la atribución de atender denuncias y reclamos por incumplimiento de las
          normas de protección de datos personales.
        </p>
        <p>
          La baja de la cuenta puede solicitarse desde la plataforma o por correo; implica la supresión de los datos
          personales en los plazos del punto 6.
        </p>
      </section>

      <section>
        <h2>8. Cookies</h2>
        <p>
          Vectorai utiliza únicamente cookies técnicas, necesarias para mantener la sesión iniciada. No se usan cookies
          publicitarias ni de seguimiento de terceros.
        </p>
      </section>

      <section>
        <h2>9. Seguridad</h2>
        <p>
          Aplicamos medidas razonables de seguridad: cifrado en tránsito (HTTPS), contraseñas hasheadas, control de acceso
          por roles a la base de datos y registro de accesos. Ningún sistema es infalible; ante un incidente de seguridad
          que afecte datos personales, notificaremos a los usuarios afectados a la brevedad.
        </p>
      </section>

      <section>
        <h2>10. Cambios</h2>
        <p>
          Esta política puede actualizarse. Los cambios sustanciales se comunicarán por email o aviso en la plataforma.
        </p>
        <p><strong>Contacto:</strong> hola@vectorai.com.ar · WhatsApp +54 9 2241 41-0393</p>
      </section>
    </LegalLayout>
  );
}
