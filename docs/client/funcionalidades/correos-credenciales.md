# Correos de credenciales — textos para aprobación

**Estado:** implementado y en uso desde agosto de 2026 · textos publicados para revisión del Ministerio
**Origen:** análisis #236 (RN-C7) · task #244
**Fecha:** 20/08/2026

El sistema envía dos correos automáticos relacionados con el acceso al backoffice.
Este documento es el texto exacto que va a recibir la persona, para revisión y
aprobación antes de habilitar el envío real.

Ambos correos usan la marca DATAÑACH, el logo del Gobierno del Chaco y la franja
de color institucional. Se ven bien en computadora y en teléfono.

---

## 1. Alta de usuario

Se envía una sola vez, cuando un administrador crea el usuario.

**Asunto:** Tu usuario de DATAÑACH fue creado

**Cuerpo:**

> **Alta de usuario**
>
> # Tu usuario ya está activo
>
> Hola *[nombre de la persona]*,
>
> Se creó tu cuenta en el backoffice de DATAÑACH. Estos son tus datos de acceso.
>
> | | |
> |---|---|
> | **Usuario** | *[nombre de usuario]* |
> | **Rol** | *[rol asignado]* |
> | **Acceso** | *[dirección del sistema]* |
>
> **Contraseña provisoria**
> `[clave generada por el sistema]`
> El sistema te va a pedir que la cambies en tu primer ingreso.
>
> **[ Ingresar y cambiar la clave ]**
>
> No compartas esta contraseña con nadie. El equipo de DATAÑACH nunca te va a
> pedir tu clave por correo ni por teléfono.

**Cómo funciona:** la contraseña que viaja en el correo sirve para un único
ingreso. Al entrar, el sistema no deja usar ninguna pantalla hasta que la persona
define una contraseña propia.

---

## 2. Recuperación de contraseña

Se envía cuando la persona usa "¿Olvidaste tu contraseña?" en la pantalla de
ingreso. Aplica también a los territoriales que entran desde la app.

**Asunto:** Recuperación de contraseña de DATAÑACH

**Cuerpo:**

> **Seguridad de la cuenta**
>
> # Restablecé tu contraseña
>
> Hola *[nombre de la persona]*,
>
> Recibimos una solicitud para restablecer la contraseña de tu usuario en el
> backoffice de DATAÑACH. Creá una nueva contraseña desde el siguiente botón.
>
> **[ Definir contraseña nueva ]**
>
> El enlace es válido por **24 horas** y puede usarse una sola vez.
>
> Si el botón no funciona, copiá esta dirección en tu navegador: *[enlace]*
>
> Si no pediste este cambio, ignorá el mensaje: tu contraseña actual sigue
> vigente. Ante cualquier duda, escribinos a soporte.

**Cómo funciona:** el enlace vence a las 24 horas y muere en cuanto se usa. Si
alguien pide el recupero con un correo que no está en el sistema, la pantalla
responde exactamente lo mismo que si existiera — así no se puede averiguar qué
cuentas están dadas de alta.

---

## Pendientes de definición

Dos datos del pie de los correos quedaron a definir. Mientras no se definan, esas
líneas simplemente no aparecen en el mensaje: no hace falta tocar el sistema
después, se cargan por configuración.

| Dato | Para qué | Estado |
|---|---|---|
| Dirección postal | Pie del correo, junto a "Ministerio de Desarrollo Social · Resistencia, Chaco" | A definir |
| Casilla de soporte | Línea "Soporte: ..." y la referencia "escribinos a soporte" del correo de recupero | A definir |

## Remitente

Los correos salen desde **datanach@chaco.gob.ar**, con el nombre visible
"DATAÑACH". Es una casilla de solo envío: el pie aclara que no se responda a esa
dirección.

En el ambiente de pruebas (QA) el asunto viaja con el prefijo `[QA]`, para que un
correo de prueba no se confunda con uno real.
