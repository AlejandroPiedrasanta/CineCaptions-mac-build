#!/bin/bash
# CineCaptions · By Cinema Productions
# 7_mac/Construir_Instalador_Mac.sh — arma el .dmg (con el instalador .pkg) en una Mac; compila para la arquitectura de ESA Mac.
# ============================================================================
#   bash 7_mac/Construir_Instalador_Mac.sh            todo de principio a fin
#   bash 7_mac/Construir_Instalador_Mac.sh --solo-instalador   reusa la app ya compilada
#
# Hace: venv -> PyInstaller (CineCaptions.app) -> autoprueba -> .pkg -> .dmg
#   Apple Silicon (arm64):  Python 3.14, CineCaptions_Mac_AppleSilicon_<version>.dmg
#   Intel (x86_64):         Python 3.13 + onnxruntime 1.23.2 (la ultima con version Intel), CineCaptions_Mac_Intel_<version>.dmg
# Deja el .dmg en INSTALADORES/Mac (o en $CINECAPTIONS_SALIDA); 6_compilacion_mac/ se puede borrar.
#
# Variables opcionales:
#   CINECAPTIONS_PYTHON     interprete Python a usar (por defecto python3.14 / python3.13 segun la Mac)
#   CINECAPTIONS_SIN_PANTALLA=1   autoprueba con Qt "offscreen" (para CI sin sesion grafica)
#   FIRMA_APP    "Developer ID Application: Tu Nombre (TEAMID)"   firma la app (sin esto: firma ad-hoc)
#   FIRMA_PKG    "Developer ID Installer: Tu Nombre (TEAMID)"     firma el .pkg
#   NOTARIO_PERFIL  perfil de `xcrun notarytool store-credentials`  notariza y grapa (necesita las dos firmas)
# Sin firmas de Apple el programa funciona, pero la primera vez macOS pide abrirlo con clic derecho > Abrir.
# ============================================================================
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(dirname "$AQUI")"
CODIGO="$RAIZ/1_codigo"
RECURSOS="$RAIZ/2_recursos"
OBRA="$RAIZ/6_compilacion_mac"
DIST="$OBRA/dist"
APP="$DIST/CineCaptions.app"
VENV="$OBRA/venv314"
VPY="$VENV/bin/python"
SOLO_INSTALADOR=0
[ "${1:-}" = "--solo-instalador" ] && SOLO_INSTALADOR=1

paso() { printf '\n\033[36m== %s\033[0m\n' "$1"; }
falla() { printf '\033[31mERROR: %s\033[0m\n' "$1" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] || falla "Este script solo corre en una Mac (PyInstaller no compila para Mac desde Windows). Mira 7_mac/0_LEEME.txt: hay una via con GitHub Actions."
ARQ="$(uname -m)"
case "$ARQ" in
    arm64)  PYVER=3.14; NOMBRE_ARQ=AppleSilicon ;;
    x86_64) PYVER=3.13; NOMBRE_ARQ=Intel ;;
    *) falla "Arquitectura no soportada: $ARQ" ;;
esac
export PYTHONIOENCODING=utf-8 PIP_DISABLE_PIP_VERSION_CHECK=1

VERSION="$(sed -n "s/^APP_VERSION = '\([0-9.]*\)'.*/\1/p" "$CODIGO/version.py" | head -1)"
[ -n "$VERSION" ] || falla "No encontre APP_VERSION en 1_codigo/version.py"
echo "CineCaptions $VERSION"
# v5.3.2: una sola version: los scripts de Resolve y el Puente se ponen a la de version.py (si no, el programa avisa de "otra version instalada")
SYNC_PY="$VPY"; [ -x "$SYNC_PY" ] || SYNC_PY="${CINECAPTIONS_PYTHON:-python3}"      # (solo libreria estandar: vale cualquier Python 3, el venv aun puede no existir)
"$SYNC_PY" "$RAIZ/3_compilar/sincronizar_version.py" || falla "No pude poner la version en los scripts de Resolve"

if [ "$SOLO_INSTALADOR" = 0 ]; then
# 1) Python 3.14 y el entorno ------------------------------------------------------------
paso "Entorno de compilacion (Python $PYVER, $NOMBRE_ARQ)"
if [ ! -x "$VPY" ]; then
    PY="${CINECAPTIONS_PYTHON:-}"
    [ -n "$PY" ] || PY="$(command -v python$PYVER || true)"
    [ -n "$PY" ] || { [ -x /Library/Frameworks/Python.framework/Versions/$PYVER/bin/python$PYVER ] && PY=/Library/Frameworks/Python.framework/Versions/$PYVER/bin/python$PYVER; }
    if [ -z "$PY" ] && command -v brew >/dev/null 2>&1; then
        brew install python@$PYVER && PY="$(command -v python$PYVER)"
    fi
    [ -n "$PY" ] || falla "Falta Python $PYVER: instalalo desde python.org/downloads (o 'brew install python@$PYVER') y vuelve a correr esto."
    mkdir -p "$OBRA"
    "$PY" -m venv "$VENV"
fi
"$VPY" -c "import sys; assert '%d.%d' % sys.version_info[:2] == '$PYVER', sys.version" || falla "El venv no es Python $PYVER: borra 6_compilacion_mac y repite."
REQ="$RAIZ/3_compilar/requirements.txt"
if [ "$ARQ" = x86_64 ]; then
    # onnxruntime no publica version Intel de Mac para Python 3.14: la ultima con Intel es 1.23.2 (Python <= 3.13)
    REQ="$OBRA/requirements_intel.txt"
    sed 's/^onnxruntime==.*/onnxruntime==1.23.2/' "$RAIZ/3_compilar/requirements.txt" > "$REQ"
fi
"$VPY" -m pip install --progress-bar off -q -r "$REQ"
# argostranslate SIN dependencias (declara stanza+spacy, que arrastran torch): ver requirements.txt
"$VPY" -m pip install --progress-bar off -q --no-deps 'argostranslate==1.11.0'

# 2) fuentes preparadas ---------------------------------------------------------------------
paso "Codigo fuente"
rm -rf "$OBRA/fuentes"; mkdir -p "$OBRA/fuentes"
cp "$CODIGO"/*.py "$OBRA/fuentes/"
[ -f "$OBRA/fuentes/CineCaptions (script principal).py" ] || falla "Falta el script principal en 1_codigo"
"$VPY" -m compileall -q "$OBRA/fuentes" || falla "Hay errores de sintaxis en 1_codigo/*.py"

# 3) icono .icns (del logo de 1024x1024) -----------------------------------------------------------
paso "Icono"
ICONSET="$OBRA/icono.iconset"; rm -rf "$ICONSET"; mkdir -p "$ICONSET"
LOGO="$RECURSOS/logo_cinecaptions.png"
for s in 16 32 128 256 512; do
    sips -z $s $s "$LOGO" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
    sips -z $((s*2)) $((s*2)) "$LOGO" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$OBRA/CineCaptions.icns"

# 3b) Remotion (animaciones de la Edicion PRO): node + renderizador + Chrome sin ventana de ESTA Mac en 2_recursos ---------------------
paso "Remotion: animaciones de la Edicion PRO"
if command -v node >/dev/null 2>&1; then
    "$VPY" "$RAIZ/3_compilar/preparar_remotion.py" || falla "No pude preparar Remotion"
else
    echo "    AVISO: no hay Node en esta Mac: la Edicion PRO saldra sin las animaciones de Remotion"
fi

# 4) PyInstaller ----------------------------------------------------------------------------------
paso "Compilando CineCaptions.app (PyInstaller, 3-8 min)"
export CINECAPTIONS_FUENTES="$OBRA/fuentes" CINECAPTIONS_RECURSOS="$RECURSOS" CINECAPTIONS_VERSION="$VERSION"
export CINECAPTIONS_ARQ="$ARQ" CINECAPTIONS_ICONO="$OBRA/CineCaptions.icns" CINECAPTIONS_FIRMA="${FIRMA_APP:-}"
(cd "$AQUI" && "$VPY" -m PyInstaller --noconfirm --log-level ERROR --distpath "$DIST" --workpath "$OBRA/work" cinecaptions_mac.spec)
[ -d "$APP" ] || falla "PyInstaller no dejo CineCaptions.app"
# v5.4.52: el Chrome sin ventana de Remotion se copia TAL CUAL (PyInstaller no puede reescribir sus .dylib): en Contents/Resources (lo que no es
# codigo no puede ir en Frameworks sin romper la firma) con un enlace desde Frameworks, donde lo busca el programa; luego se vuelve a sellar la app
CHROME_ORG="$RECURSOS/edicion_pro/remotion/runtime/chrome"
if [ -d "$CHROME_ORG" ]; then
    REL="edicion_pro/remotion/runtime/chrome"
    rm -rf "$APP/Contents/Resources/$REL" "$APP/Contents/Frameworks/$REL"
    mkdir -p "$APP/Contents/Resources/$REL"
    ditto "$CHROME_ORG" "$APP/Contents/Resources/$REL"
    if [ ! -e "$APP/Contents/Frameworks/$REL" ]; then
        mkdir -p "$(dirname "$APP/Contents/Frameworks/$REL")"
        ln -s "../../../../Resources/$REL" "$APP/Contents/Frameworks/$REL"
    fi
    if [ -n "${FIRMA_APP:-}" ]; then
        codesign --force --options runtime --timestamp --entitlements "$AQUI/entitlements.plist" --sign "$FIRMA_APP" "$APP"
    else
        codesign --force --entitlements "$AQUI/entitlements.plist" --sign - "$APP"
    fi
    echo "    Chrome sin ventana de Remotion copiado en la app (y la app sellada de nuevo)"
fi

# 5) autoprueba del compilado (la misma que corre el instalador de Windows) ------------------------------
paso "Autoprueba del programa compilado"
ESTADO="$OBRA/autoprueba.txt"; : > "$ESTADO"
if [ "${CINECAPTIONS_SIN_PANTALLA:-0}" = 1 ]; then export QT_QPA_PLATFORM=offscreen; fi
set +e
"$APP/Contents/MacOS/CineCaptions" --tarea verificar "$ESTADO"
CODIGO_SALIDA=$?
set -e
grep -v '^PROGRESO' "$ESTADO" | sed 's/^/    /'
[ "$CODIGO_SALIDA" = 0 ] || falla "La autoprueba del compilado fallo: no se arma el instalador"
unset QT_QPA_PLATFORM

paso "Firma"
codesign --verify --deep --strict "$APP" && echo "    firma de la app valida ($( [ -n "${FIRMA_APP:-}" ] && echo 'Developer ID' || echo 'ad-hoc' ))"
fi

[ -d "$APP" ] || falla "No hay app compilada en 6_compilacion_mac/dist: corre el script sin --solo-instalador"

# 6) .pkg ---------------------------------------------------------------------------------------------
paso "Instalador .pkg"
PKGROOT="$OBRA/pkgroot"; rm -rf "$PKGROOT"; mkdir -p "$PKGROOT/Applications"
ditto "$APP" "$PKGROOT/Applications/CineCaptions.app"
chmod +x "$AQUI/pkg/scripts/postinstall"
cat > "$OBRA/componente.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><array><dict>
<key>RootRelativeBundlePath</key><string>Applications/CineCaptions.app</string>
<key>BundleIsRelocatable</key><false/>
<key>BundleIsVersionChecked</key><false/>
<key>BundleHasStrictIdentifier</key><false/>
<key>BundleOverwriteAction</key><string>upgrade</string>
</dict></array></plist>
PLIST
SELLO_PKG=(); [ -n "${FIRMA_PKG:-}" ] && SELLO_PKG=(--sign "$FIRMA_PKG")
pkgbuild --root "$PKGROOT" --component-plist "$OBRA/componente.plist" --identifier com.cinemaproductions.cinecaptions \
    --version "$VERSION" --install-location / --scripts "$AQUI/pkg/scripts" --ownership recommended \
    "$OBRA/CineCaptions-componente.pkg" >/dev/null
cat > "$OBRA/distribucion.xml" <<XML
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>CineCaptions $VERSION</title>
    <welcome file="welcome.html"/>
    <conclusion file="conclusion.html"/>
    <options customize="never" require-scripts="false" hostArchitectures="$ARQ"/>
    <allowed-os-versions><os-version min="12.0"/></allowed-os-versions>
    <domains enable_anywhere="false" enable_currentUserHome="false" enable_localSystem="true"/>
    <choices-outline><line choice="default"><line choice="com.cinemaproductions.cinecaptions"/></line></choices-outline>
    <choice id="default"/>
    <choice id="com.cinemaproductions.cinecaptions" visible="false"><pkg-ref id="com.cinemaproductions.cinecaptions"/></choice>
    <pkg-ref id="com.cinemaproductions.cinecaptions" version="$VERSION" onConclusion="none">CineCaptions-componente.pkg</pkg-ref>
</installer-gui-script>
XML
PKG="$OBRA/Instalar_CineCaptions.pkg"; rm -f "$PKG"
productbuild --distribution "$OBRA/distribucion.xml" --resources "$AQUI/pkg/recursos" --package-path "$OBRA" \
    ${SELLO_PKG[@]+"${SELLO_PKG[@]}"} "$PKG" >/dev/null

# 7) notarizar (opcional) ----------------------------------------------------------------------------------
if [ -n "${NOTARIO_PERFIL:-}" ] && [ -n "${FIRMA_PKG:-}" ]; then
    paso "Notarizando con Apple (puede tardar unos minutos)"
    xcrun notarytool submit "$PKG" --keychain-profile "$NOTARIO_PERFIL" --wait
    xcrun stapler staple "$PKG"
fi

# 8) .dmg -------------------------------------------------------------------------------------------------------
paso "Imagen de disco .dmg"
STAGE="$OBRA/dmg"; rm -rf "$STAGE"; mkdir -p "$STAGE"
cp "$PKG" "$STAGE/"
cp "$AQUI/Desinstalar_CineCaptions.command" "$STAGE/"; chmod +x "$STAGE/Desinstalar_CineCaptions.command"
cat > "$STAGE/LEEME.txt" <<TXT
CineCaptions $VERSION para Mac ($NOMBRE_ARQ) · By Cinema Productions

1. Abre "Instalar_CineCaptions.pkg" y sigue los pasos.
   Si macOS dice que no se puede abrir: clic derecho sobre el .pkg > Abrir > Abrir
   (o Ajustes del Sistema > Privacidad y seguridad > "Abrir de todos modos").
2. Abre CineCaptions desde Aplicaciones.
3. Para desinstalar: doble clic en "Desinstalar_CineCaptions.command".

En DaVinci Resolve: Preferencias > Sistema > General > Uso de scripting externo = Local.
TXT
SALIDA="${CINECAPTIONS_SALIDA:-$RAIZ/INSTALADORES/Mac}"; mkdir -p "$SALIDA"
rm -f "$SALIDA"/CineCaptions_Mac_${NOMBRE_ARQ}_*.dmg          # la version anterior de esta arquitectura se quita
DMG="$SALIDA/CineCaptions_Mac_${NOMBRE_ARQ}_$VERSION.dmg"
hdiutil create -volname "CineCaptions $VERSION" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
[ -n "${FIRMA_APP:-}" ] && codesign --sign "$FIRMA_APP" "$DMG"
if [ -n "${NOTARIO_PERFIL:-}" ] && [ -n "${FIRMA_APP:-}" ]; then
    xcrun notarytool submit "$DMG" --keychain-profile "$NOTARIO_PERFIL" --wait && xcrun stapler staple "$DMG"
fi
paso "LISTO  $DMG  ($(du -h "$DMG" | cut -f1))"
