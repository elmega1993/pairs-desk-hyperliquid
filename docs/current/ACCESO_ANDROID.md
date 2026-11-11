# Acceso desde Android fuera de casa

Configurado el 06/11/2026 en Ubuntu 24.04 mediante Tailscale Serve privado. HTTPS y API comprobados con HTTP 200 desde la PC; falta confirmar navegación en Android por datos móviles. La PC debe permanecer encendida, conectada y con Pair Desk funcionando.

## PC

Desde la carpeta del proyecto:

```bash
bash configurar_movil.sh
```

El script requiere interacción: contraseña de sudo, confirmación de instalación APT e inicio de sesión en Tailscale. Instala desde el repositorio oficial firmado para Ubuntu noble. Ante un repositorio preexistente distinto o un servicio HTTPS 443 ocupado, se detiene para no reemplazarlo. Descargas temporales quedan en `/tmp/pairs-desk-tailscale.*`.

Tras iniciar sesión, registra exclusivamente el DNS de esta PC en `~/.config/crypto-pairs-desk/remote_access.json` con permisos 0600. Usa `tailscale serve --bg --https=443 http://127.0.0.1:8510`. Puede requerir habilitar HTTPS en el enlace ofrecido por Tailscale. No usa Funnel ni abre el router; el acceso queda sujeto a los permisos de la red privada Tailscale.

Reiniciar Pair Desk con `iniciar_frontend.sh` después de configurar el nombre privado. El script muestra la URL `https://<nombre-de-esta-pc>.<red>.ts.net/react`; no usar `127.0.0.1` desde el teléfono.

## Android

1. Instalar Tailscale desde Google Play siguiendo https://tailscale.com/docs/install/android.
2. Iniciar sesión con la misma cuenta usada en la PC y aceptar el permiso de conexión VPN de Android.
3. Activar Tailscale y abrir la URL privada mostrada por el script en Chrome.
4. Desactivar Wi-Fi para comprobar el acceso con datos móviles. Comparar un dato reciente de la pantalla con la PC.

Se puede agregar esa dirección a la pantalla de inicio desde Chrome. La app sigue ejecutándose en la PC; suspender o apagar la PC interrumpe el acceso.

## Alcance y controles

El backend sigue escuchando únicamente en 127.0.0.1:8510. TrustedHost acepta localhost y, opcionalmente, ese único nombre privado explícito: no comodines `.ts.net`. Sin configuración válida, se limita a localhost. Las rutas de trading conservan sus restricciones locales de Host/Origin; este acceso móvil inicial es para consulta y no habilita órdenes remotas.

Comprobar con `tailscale status` y `sudo tailscale serve status`. Para detener solo esta publicación privada, `sudo tailscale serve --https=443 off` (validar antes que siga siendo la publicación de Pair Desk). No usar `serve reset`, que podría borrar otras publicaciones.

Fuentes oficiales: https://tailscale.com/docs/install/linux, https://pkgs.tailscale.com/stable/ubuntu/noble.tailscale-keyring.list y https://tailscale.com/docs/reference/tailscale-cli/serve.
