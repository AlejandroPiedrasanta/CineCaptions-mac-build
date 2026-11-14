#!/bin/bash
# CineCaptions Ventas · By Cinema Productions
# programa/mac/construir_ventas_mac.sh — arma «CineCaptions Ventas.app» y su .dmg en una Mac (la de GitHub Actions:
# .github/workflows/ventas_mac.yml) y la PRUEBA ahí mismo antes de entregarla:
#   1) prueba_acciones.py (todas las pruebas de la app) con el código, en macOS;
#   2) la .app ya armada: --comprobar-https (HTTPS real sin los certificados de esta Mac), --importar-clave (la clave al
#      Llavero de verdad, en una entrada de pruebas) y --captura de cada página contra servidor_prueba.py, sin pantalla;
#   3) el .dmg con su ventana «Arrástralo a Aplicaciones» (mac/dmg/), abierto y revisado. Si algo falla, no sale el .dmg.
# Salida: build/CineCaptions_Ventas_Mac_<AppleSilicon|Intel>_<versión>.dmg y build/capturas_mac/*.png
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
PROG="$(dirname "$AQUI")"
cd "$PROG"
paso() { echo; echo "==> $*"; }
falla() { echo "ERROR: $*" >&2; exit 1; }

case "$(uname -m)" in
    arm64) ARQ=AppleSilicon ;;
    x86_64) ARQ=Intel ;;
    *) falla "arquitectura desconocida: $(uname -m)" ;;
esac
VERSION=$(sed -nE "s/^VERSION = '([0-9.]+)'.*/\1/p" ventas.py)
[ -n "$VERSION" ] || falla "no encontré VERSION en ventas.py"
PY=${PYTHON:-python3}
export CC_VENTAS_LLAVERO='CineCaptions Ventas (pruebas)'     # nunca la entrada real del Llavero

paso "Dependencias ($($PY --version), $ARQ, versión $VERSION)"
$PY -m pip install -q --upgrade pip
$PY -m pip install -q -r mac/requirements_mac.txt

paso "Pruebas de la app en macOS (prueba_acciones.py)"
# Se juzga por lo que dice al final («TODO BIEN» / «N FALLAS»), no por el código de salida: al desarmar Qt, el proceso a
# veces se cae DESPUÉS de terminar (pasa también en Windows) y eso no es una falla de la app.
QT_QPA_PLATFORM=offscreen $PY prueba_acciones.py 2>&1 | tee /tmp/prueba_ventas.txt || true
grep -q '^TODO BIEN' /tmp/prueba_ventas.txt || falla "las pruebas de la app no pasaron en macOS (ver arriba)"

paso "Ícono de Mac"
QT_QPA_PLATFORM=offscreen $PY mac/icono_mac.py build/ventas.icns

paso "PyInstaller"
rm -rf build/dist_mac build/work_mac
# La clave de administrador incluida (2.10, el dueño: «quita la contraseña»): del secreto VENTAS_CLAVE, solo aquí. Como el
# espejo es público, si va la clave el .dmg SOLO sale cifrado (VENTAS_ARTEFACTO): sin esa contraseña no se compila con clave.
rm -f build/clave_incluida.txt
if [ -n "${VENTAS_CLAVE:-}" ]; then
    [ -n "${VENTAS_ARTEFACTO:-}" ] || falla "hay VENTAS_CLAVE pero no VENTAS_ARTEFACTO: el .dmg con la clave saldría sin cifrar"
    mkdir -p build
    ( umask 077; printf '%s\n' "$VENTAS_CLAVE" > build/clave_incluida.txt )
    echo "    (con la clave de administrador incluida)"
fi
trap 'rm -f build/clave_incluida.txt' EXIT
$PY -m PyInstaller --noconfirm --distpath build/dist_mac --workpath build/work_mac mac/ventas_mac.spec
APP="build/dist_mac/CineCaptions Ventas.app"
BIN="$APP/Contents/MacOS/CineCaptions Ventas"
[ -x "$BIN" ] || falla "no se armó la .app"

paso "HTTPS de verdad desde la .app armada (sin los certificados de esta Mac, como en la Mac del dueño)"
# El Python de la .app busca los certificados en carpetas de ESTA Mac de GitHub; en otra Mac no existen y la 2.10 no se
# conectaba («No se pudo comprobar la conexión segura»). Con SSL_CERT_FILE/DIR a la nada solo quedan los de certifi.
# (Primero, solo para el registro: el TLS de siempre, sin certifi, en esas condiciones; se espera que falle.)
SSL_CERT_FILE=/nada/cert.pem SSL_CERT_DIR=/nada $PY -c "import ssl, urllib.request as u; u.urlopen(u.Request('https://cinecaptions.shop/', method='HEAD'), context=ssl.create_default_context(), timeout=30); print('    (sin certifi también se conecta)')" 2>&1 | tail -1 || true
SSL_CERT_FILE=/nada/cert.pem SSL_CERT_DIR=/nada "$BIN" --comprobar-https https://cinecaptions.shop/ \
    || falla "la .app no pudo abrir https://cinecaptions.shop sin los certificados de esta Mac"
SSL_CERT_FILE=/nada/cert.pem SSL_CERT_DIR=/nada "$BIN" --comprobar-https https://github.com/ \
    || falla "la .app no pudo abrir https://github.com sin los certificados de esta Mac"
if [ -f build/clave_incluida.txt ]; then   # (una consulta de solo lectura al servidor de verdad; nunca imprime la clave)
    SSL_CERT_FILE=/nada/cert.pem SSL_CERT_DIR=/nada "$BIN" --comprobar-clave-incluida \
        || falla "la .app no trae la clave incluida o el servidor no la acepta (¿cambió la clave? Compilar_Ventas_Mac.ps1 la sube)"
fi

paso "Autoprueba de la .app armada (Llavero + capturas contra el servidor de prueba)"
$PY servidor_prueba.py --puerto 8799 > /tmp/servidor_ventas.log 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null || true; rm -f build/clave_incluida.txt' EXIT
for _ in $(seq 1 50); do
    curl -s -o /dev/null http://127.0.0.1:8799/ && break
    sleep 0.2
done
CONFIG=$(mktemp -d)
printf 'clave-de-prueba\n' > "$CONFIG/clave.txt"
CC_VENTAS_CONFIG="$CONFIG" "$BIN" --importar-clave "$CONFIG/clave.txt"
grep -q '"llavero:' "$CONFIG/config.json" || falla "la .app no dejó la clave en el Llavero"
rm -rf build/capturas_mac
CC_VENTAS_CONFIG="$CONFIG" QT_QPA_PLATFORM=offscreen "$BIN" --api http://127.0.0.1:8799 --captura build/capturas_mac || true
N=$(find build/capturas_mac -name '*.png' 2>/dev/null | wc -l | tr -d ' ')   # (se juzga por las capturas, como arriba)
[ "$N" -ge 5 ] || falla "la .app armada solo guardó $N capturas"
echo "    OK: la .app abre en macOS, lee la clave del Llavero y guardó $N capturas"
while security delete-generic-password -s "$CC_VENTAS_LLAVERO" > /dev/null 2>&1; do :; done   # (todas las de prueba)

paso "Imagen de disco («Arrástralo a Aplicaciones», con fondo: mac/dmg/)"
# 2.10 (el dueño, con la captura del de CineCaptions 5.90: «así hazlo»): la ventana con su fondo, el icono de la app a la izquierda,
# la flecha y Aplicaciones a la derecha. Lo arma dmgbuild (mac/dmg/ajustes_dmg.py) escribiendo el .DS_Store él mismo.
$PY -m pip install -q 'dmgbuild==1.6.7' || falla "no pude instalar dmgbuild (la ventana del .dmg)"
DMG="build/CineCaptions_Ventas_Mac_${ARQ}_${VERSION}.dmg"
FONDO=build/fondo_dmg.tiff
rm -f "$DMG" "$FONDO"
tiffutil -cathidpicheck mac/dmg/fondo.png mac/dmg/fondo@2x.png -out "$FONDO" > /dev/null || falla "no pude preparar el fondo del .dmg"
VMS=${VERSION%.0}   # (el volumen dice «2.10», como la versión que se muestra)
for intento in 1 2 3 4 5; do     # (en las Mac de GitHub hdiutil a veces dice «Resource busy»)
    $PY -m dmgbuild -s mac/dmg/ajustes_dmg.py -D app="$APP" -D fondo="$FONDO" -D icono=build/ventas.icns \
        "CineCaptions Ventas $VMS" "$DMG" > /dev/null && break
    [ "$intento" = 5 ] && falla "dmgbuild no pudo crear la imagen de disco"
    rm -f "$DMG"; sleep 15
done
# Que el .dmg traiga lo que se ve: la app, el acceso a Aplicaciones y el fondo; y que la app de dentro abra
VOL="/Volumes/CineCaptions Ventas $VMS"
hdiutil attach -nobrowse -readonly "$DMG" > /dev/null || falla "no pude abrir el .dmg recién hecho"
[ -d "$VOL" ] || falla "el .dmg no se montó en $VOL"
DENTRO="$VOL/CineCaptions Ventas.app/Contents/MacOS/CineCaptions Ventas"
[ -x "$DENTRO" ] || falla "el .dmg no trae la app"
[ "$(readlink "$VOL/Aplicaciones")" = /Applications ] || falla "el .dmg no trae el acceso a Aplicaciones"
[ -f "$VOL/.DS_Store" ] && ls -a "$VOL" | grep -q '^\.background' || falla "el .dmg no trae la ventana con fondo"
SSL_CERT_FILE=/nada/cert.pem SSL_CERT_DIR=/nada "$DENTRO" --comprobar-https https://cinecaptions.shop/ \
    || falla "la app del .dmg no se conecta a cinecaptions.shop"
echo "    OK: el .dmg trae la app, Aplicaciones y el fondo; la app de dentro se conecta"
# Doble clic en la app del .dmg (2.10, «que se cierre y abra»): se copia a Aplicaciones (aquí, a una carpeta de prueba) …
APPS=$(mktemp -d)
SALIDA=$(CC_VENTAS_APLICACIONES="$APPS" CC_VENTAS_NO_ABRIR=1 "$DENTRO" 2>&1) || falla "la app del .dmg falló al copiarse: $SALIDA"
echo "$SALIDA" | grep -q '^Instalada en' || falla "la app del .dmg no se copió sola a Aplicaciones: $SALIDA"
[ -x "$APPS/CineCaptions Ventas.app/Contents/MacOS/CineCaptions Ventas" ] || falla "la copia en Aplicaciones no trae la app"
[ -z "$(xattr -p com.apple.quarantine "$APPS/CineCaptions Ventas.app" 2>/dev/null)" ] || falla "la copia quedó en cuarentena"
# 2.11 (el dueño: «que muestre rápido el proceso … todo debe ser inmediato»): el doble clic de verdad, con la ventanita
# «Instalando…» y su avance (sin abrir la copia: hace como que su ventana ya se ve). Se mide cuánto tarda cada paso.
APPS2=$(mktemp -d)
CC_VENTAS_T0=$($PY -c 'import time; print(time.time())') CC_VENTAS_APLICACIONES="$APPS2" CC_VENTAS_PRUEBA_SIN_ABRIR=1 \
    "$DENTRO" > /tmp/instalar_ventana.txt 2>&1 &
PID_INST=$!
for _ in $(seq 1 120); do kill -0 $PID_INST 2>/dev/null || break; sleep 1; done
if kill -0 $PID_INST 2>/dev/null; then kill $PID_INST; falla "la ventanita «Instalando…» no terminó en 2 minutos"; fi
wait $PID_INST || falla "la ventanita «Instalando…» falló: $(cat /tmp/instalar_ventana.txt)"
sed 's/^/    /' /tmp/instalar_ventana.txt
grep -q 'Ventana «Instalando» a la vista' /tmp/instalar_ventana.txt || falla "la ventanita «Instalando…» no salió"
[ -x "$APPS2/CineCaptions Ventas.app/Contents/MacOS/CineCaptions Ventas" ] || falla "la ventanita no dejó la app en Aplicaciones"
rm -rf "$APPS2"
# … y la copia, al abrirse, expulsa el .dmg (con eso se cierra su ventana)
"$APPS/CineCaptions Ventas.app/Contents/MacOS/CineCaptions Ventas" --expulsar "$VOL" --comprobar-https https://cinecaptions.shop/ \
    > /dev/null || falla "la copia de Aplicaciones no abre"
for _ in $(seq 1 30); do [ -d "$VOL" ] || break; sleep 1; done
[ -d "$VOL" ] && { hdiutil detach "$VOL" -force -quiet || true; falla "la copia no expulsó el .dmg"; }
# La copia abierta de verdad (con la clave de prueba, contra el servidor de prueba): avisa cuando su ventana ya se ve,
# que es cuando la ventanita «Abriendo…» del .dmg se cierra
MARCA="$(mktemp -d)/lista"
T0=$($PY -c 'import time; print(time.time())')
CC_VENTAS_CONFIG="$CONFIG" "$APPS/CineCaptions Ventas.app/Contents/MacOS/CineCaptions Ventas" --api http://127.0.0.1:8799 \
    --avisar-lista "$MARCA" > /dev/null 2>&1 &
PID_APP=$!
for _ in $(seq 1 600); do [ -f "$MARCA" ] && break; sleep 0.1; done
kill $PID_APP 2>/dev/null || true
[ -f "$MARCA" ] || falla "la app copiada no avisó que su ventana ya se ve (--avisar-lista)"
echo "    La app copiada se ve a los $($PY -c "import time; print(f'{time.time() - $T0:.2f}')") s de abrirla"
rm -rf "$APPS"
echo "    OK: doble clic en la app del .dmg la copia a Aplicaciones y la copia expulsa el .dmg"
# Solo para mirarla: la pantalla de esta Mac con el .dmg abierto en el Finder (sin AppleScript). Si la Mac de GitHub no deja, nada.
(
    hdiutil attach "$DMG" > /dev/null 2>&1 || exit 0
    VOL="/Volumes/CineCaptions Ventas $VMS"
    open "$VOL" 2> /dev/null || true
    sleep 6
    screencapture -x build/capturas_mac/00_dmg_ventana.png 2> /dev/null && echo "    (captura de la ventana del .dmg guardada)"
    hdiutil detach "$VOL" -force -quiet 2> /dev/null || true
) || true
if [ -f build/clave_incluida.txt ]; then
    # Con la clave dentro, el .dmg sale de aquí SOLO cifrado (el espejo es público: cualquiera podría bajar el artefacto).
    # Compilar_Ventas_Mac.ps1 lo descifra en la PC del dueño con la misma contraseña (CineCaptions_claves/ventas_artefacto.txt).
    OSSL="$(brew --prefix openssl@3 2>/dev/null)/bin/openssl"; [ -x "$OSSL" ] || OSSL=openssl
    "$OSSL" enc -aes-256-cbc -pbkdf2 -iter 200000 -md sha256 -salt -in "$DMG" -out "$DMG.cifrado" -pass env:VENTAS_ARTEFACTO \
        || falla "no pude cifrar el .dmg"
    "$OSSL" enc -d -aes-256-cbc -pbkdf2 -iter 200000 -md sha256 -in "$DMG.cifrado" -out /tmp/vuelta.dmg -pass env:VENTAS_ARTEFACTO \
        && cmp -s "$DMG" /tmp/vuelta.dmg || falla "el .dmg cifrado no se descifra igual"
    rm -f "$DMG" /tmp/vuelta.dmg
    DMG="$DMG.cifrado"
    echo "    (el .dmg trae la clave: sale cifrado)"
fi
echo
echo "Listo: $DMG ($(du -h "$DMG" | cut -f1))"
