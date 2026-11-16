#!/bin/bash
# =============================================================================================================================
# CineCaptions · By Cinema Productions
# 7_mac/instalador/instalar.sh — los pasos del instalador de la Mac (Contents/Resources/instalar.sh de «Instalar CineCaptions.app»).
# v5.92 (el usuario: «necesito que funcione el instalador como el de CineSlide»): lo ejecuta la ventana (instalador_mac.swift), que
# muestra el avance que este script escribe en CINECAPTIONS_AVANCE: una línea por evento (PASO / OK / AVISO / DETALLE / FALLO / FIN,
# tabulador, texto). SIN contraseña NUNCA: la app se copia en /Applications (o en ~/Applications si la de /Applications no es de este
# usuario y no se puede cambiar sin contraseña, o si no puede escribir ahí) y todo lo demás (scripts de Resolve, tipografías, servicio de
# actualizaciones, Dock, motor de voz e IA) es de este usuario: lo hace la propia app ya copiada, en una sola pasada (`--tarea pasos_mac`,
# 1_codigo/instalar_mac.py). Solo copiar la app puede fallar la instalación; lo demás queda de aviso y CineCaptions lo reintenta al abrirse.
# FIN lleva la versión y la ruta instalada (la ventana abre ESA).
# Solo herramientas que trae macOS (sin Command Line Tools: `lipo`, por ejemplo, haría saltar «¿instalar las herramientas?»).
# Variables: CINECAPTIONS_ORIGEN (la app que trae el disco), CINECAPTIONS_VERSION, CINECAPTIONS_AVANCE, CINECAPTIONS_LOG,
#            CINECAPTIONS_IDIOMA (es | en).
# Compatible con el bash 3.2 de macOS.
# =============================================================================================================================
ORIGEN="${CINECAPTIONS_ORIGEN:-}"
VERSION="${CINECAPTIONS_VERSION:-}"
AVANCE="${CINECAPTIONS_AVANCE:-/dev/null}"
LOG="${CINECAPTIONS_LOG:-$HOME/DaVinciSubtitles/instalacion_mac.log}"
IDIOMA="${CINECAPTIONS_IDIOMA:-es}"
LSREG=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
PLB=/usr/libexec/PlistBuddy
DAEMON=/Library/LaunchDaemons/com.cinemaproductions.cinecaptions.actualizar.plist
ESTADO_ROOT="/Library/Application Support/CineCaptions/actualizar/estado.json"
PEDIDOS=/Users/Shared/CineCaptions/pedidos
SISTEMA=/Applications/CineCaptions.app
PROPIA="$HOME/Applications/CineCaptions.app"
YO=$(id -u)

mkdir -p "$(dirname "$LOG")" 2>/dev/null
exec >>"$LOG" 2>&1
echo "==== $(date '+%Y-%m-%d %H:%M:%S') · Instalar CineCaptions $VERSION · macOS $(sw_vers -productVersion 2>/dev/null) · $(uname -m) · uid $YO"
echo "origen: $ORIGEN"

t() { if [ "$IDIOMA" = es ]; then printf '%s' "$1"; else printf '%s' "$2"; fi; }
avance() { printf '%s\t%s\n' "$1" "$2" >> "$AVANCE" 2>/dev/null; echo "[$1] $2"; return 0; }
fallo() { avance FALLO "$1"; exit 1; }
# la versión de una app COMPLETA (binario e Info.plist) o nada. Sin la caché de cfprefsd (PlistBuddy). MEDIDO en Macs de GitHub: mientras el
# servicio de root cambia la app, esta no existe unos segundos y PlistBuddy escribe «File Doesn't Exist, Will Create…» en la salida normal:
# se tomaba por versión nueva y el instalador seguía con la app a medias. Solo cuenta un número de versión.
version_de() {
    [ -f "$1/Contents/Info.plist" ] && [ -x "$1/Contents/MacOS/CineCaptions" ] || return 0
    "$PLB" -c 'Print :CFBundleShortVersionString' "$1/Contents/Info.plist" 2>/dev/null | grep -E '^[0-9]+(\.[0-9]+)*$' | head -1
}
duenio() { stat -f %u "$1" 2>/dev/null; }
COPIA=""; PASOS=""; NUEVO=""; DMG_COMPARTIDO=""
# si cierran la ventana a mitad: nada a medias (la copia aún sin renombrar se borra; la instalada sigue como estaba)
trap '[ -n "$COPIA" ] && kill "$COPIA" 2>/dev/null; [ -n "$PASOS" ] && kill "$PASOS" 2>/dev/null; [ -n "$NUEVO" ] && rm -rf "$NUEVO";
      [ -n "$DMG_COMPARTIDO" ] && rm -f "$DMG_COMPARTIDO"; exit 1' TERM INT

cerrar_cineCaptions() {
    # el motor de voz que se estaba bajando aparte, con sus hijos (pip): todo su grupo de procesos; luego CineCaptions y sus tarjetas
    for p in $(pgrep -f -- "--tarea motor_fondo" 2>/dev/null); do kill -TERM -- "-$p" 2>/dev/null || kill -TERM "$p" 2>/dev/null; done
    if pgrep -f "/CineCaptions.app/Contents/MacOS/CineCaptions" >/dev/null 2>&1; then
        pkill -TERM -f "/CineCaptions.app/Contents/MacOS/CineCaptions" >/dev/null 2>&1
        for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16; do
            pgrep -f "/CineCaptions.app/Contents/MacOS/CineCaptions" >/dev/null 2>&1 || break
            sleep 0.5
        done
        pkill -KILL -f "/CineCaptions.app/Contents/MacOS/CineCaptions" >/dev/null 2>&1
        echo "CineCaptions estaba abierto: cerrado"
    fi
}

# ---------------------------------------------------------------------------------------------------- 0) preparar
avance PASO "0/7"
[ -x "$ORIGEN/Contents/MacOS/CineCaptions" ] || fallo "$(t 'No encuentro CineCaptions en el disco. Abre otra vez el .dmg que descargaste.' \
    'CineCaptions is not on the disk. Open the downloaded .dmg again.')"
MAYOR=$(sw_vers -productVersion 2>/dev/null | cut -d. -f1)
if [ -n "$MAYOR" ] && [ "$MAYOR" -lt 14 ]; then
    fallo "$(t "CineCaptions necesita macOS 14 (Sonoma) o más nuevo; este Mac tiene macOS $(sw_vers -productVersion)." \
        "CineCaptions needs macOS 14 (Sonoma) or newer; this Mac has macOS $(sw_vers -productVersion).")"
fi
# cada disco trae la app de UN tipo de Mac (Apple Silicon o Intel). Con `file` (de macOS) y no con `lipo` (de las Command Line Tools:
# en una Mac sin ellas saltaba «¿instalar las herramientas?» y la comprobación no se hacía)
TIPO_APP=$(file -b "$ORIGEN/Contents/MacOS/CineCaptions" 2>/dev/null)
if [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = 1 ]; then MAC=arm64; else MAC=x86_64; fi
case "$TIPO_APP" in
    *Mach-O*)
        case "$TIPO_APP" in
            *"$MAC"*) ;;
            *) if [ "$MAC" = arm64 ]; then
                   fallo "$(t 'Este instalador es para Mac con procesador Intel y tu Mac es Apple Silicon (M1-M4): descarga el de Apple Silicon.' \
                       'This installer is for Intel Macs and yours is Apple Silicon (M1-M4): download the Apple Silicon one.')"
               else
                   fallo "$(t 'Este instalador es para Mac con Apple Silicon (M1-M4) y tu Mac es Intel: descarga el de Intel.' \
                       'This installer is for Apple Silicon Macs (M1-M4) and yours is Intel: download the Intel one.')"
               fi ;;
        esac ;;
esac
echo "app del disco: $TIPO_APP"
cerrar_cineCaptions

# ---------------------------------------------------------------------------------------------------- 1) la app en Aplicaciones
avance PASO "1/7"
# dónde: la de /Applications si es de este usuario (o no hay ninguna y se puede escribir ahí); la de root de las 5.87-5.90, por SU servicio
# (más abajo); si la de /Applications es de otra cuenta o de root sin servicio (≤ 5.86), o hay servicio de root pero no su app (root
# ejecutaría una app que este usuario puede cambiar), en ~/Applications: sin contraseña, nunca falla por permisos
APP=""; RAZON=""
if [ -e "$SISTEMA" ]; then
    if [ "$(duenio "$SISTEMA")" = "$YO" ] && [ -w /Applications ]; then
        APP="$SISTEMA"
    elif [ "$(duenio "$SISTEMA")" = 0 ] && [ -f "$DAEMON" ] && [ -d "$PEDIDOS" ] && [ -w "$PEDIDOS" ]; then
        APP="$SISTEMA"; RAZON=root
    else
        APP="$PROPIA"; RAZON=ajena
    fi
elif [ -e "$PROPIA" ] || [ -f "$DAEMON" ] || [ ! -w /Applications ]; then
    APP="$PROPIA"
else
    APP="$SISTEMA"
fi
echo "destino: $APP ${RAZON:+($RAZON)} · /Applications/CineCaptions.app de uid $(duenio "$SISTEMA")"

# la app de root de las 5.87-5.90 (instalada con su .pkg) no se puede cambiar sin contraseña (MEDIDO en Macs de GitHub: ni apartarla): la
# cambia SU servicio de root con este mismo disco (pedido con el .dmg, que comprueba con el SHA-256 firmado y el paquete oculto). El .dmg se
# copia antes a /Users/Shared: el servicio (LaunchDaemon) no puede leer Descargas, Escritorio ni Documentos (privacidad de macOS). Si el
# servicio no responde, falla o tarda demasiado, se instala en ~/Applications (sin contraseña) en vez de dejar la ventana esperando.
if [ "$RAZON" = root ]; then
    ANTES=$(version_de "$SISTEMA")
    echo "la instalada ($ANTES) es de root: se la encargo a su servicio"
    avance DETALLE "$(t 'Preparando el disco para el servicio de CineCaptions…' 'Preparing the disk for the CineCaptions service…')"
    VOLUMEN=$(dirname "$ORIGEN")
    IMAGEN=$(hdiutil info 2>/dev/null | awk -v v="$VOLUMEN" '
        /^image-path/ { sub(/^image-path[ \t]*:[ \t]*/, ""); img = $0 }
        length($0) >= length(v) && substr($0, length($0) - length(v) + 1) == v { print img; exit }')
    echo "disco: $IMAGEN"
    if [ -n "$IMAGEN" ] && [ -f "$IMAGEN" ]; then
        DMG_COMPARTIDO="/Users/Shared/CineCaptions_instalar_$$_$(basename "$IMAGEN")"
        cp "$IMAGEN" "$DMG_COMPARTIDO" 2>/dev/null && chmod 644 "$DMG_COMPARTIDO" || DMG_COMPARTIDO=""
    fi
    PEDIDO="$PEDIDOS/pedido_instalador_$$.json"
    printf '{"reabrir": false, "dmg": "%s", "ts": %s}\n' "$(printf '%s' "${DMG_COMPARTIDO:-$IMAGEN}" | sed 's/\\/\\\\/g; s/"/\\"/g')" "$(date +%s)" \
        > "$PEDIDOS/.pedido_instalador_$$.tmp" && mv "$PEDIDOS/.pedido_instalador_$$.tmp" "$PEDIDO"
    T0=$(date +%s); HECHO=""; MOTIVO=""; VISTA=""; VISTA_T=0
    while :; do
        AHORA=$(version_de "$SISTEMA")
        PASADO=$(( $(date +%s) - T0 ))
        # terminada: el servicio lo dice en su estado («instalada») o la versión nueva sigue ahí, completa, 20 s seguidos (el servicio
        # aún puede estar cambiándola: la app desaparece un rato mientras tanto)
        if [ -n "$AHORA" ] && [ "$AHORA" != "$ANTES" ]; then
            if [ "$(plutil -extract instalada raw -o - "$ESTADO_ROOT" 2>/dev/null)" = "$AHORA" ]; then HECHO=1; break; fi
            if [ "$AHORA" != "$VISTA" ]; then VISTA="$AHORA"; VISTA_T=$(date +%s); fi
            if [ $(( $(date +%s) - VISTA_T )) -ge 20 ]; then HECHO=1; break; fi
        else
            VISTA=""
        fi
        if [ "$PASADO" -gt 90 ] && [ -e "$PEDIDO" ]; then MOTIVO="el servicio no recogió el pedido"; break; fi
        FALLO_TS=$(plutil -extract fallo_ts raw -o - "$ESTADO_ROOT" 2>/dev/null | cut -d. -f1)
        if [ -n "$FALLO_TS" ] && [ "$FALLO_TS" -ge "$T0" ] 2>/dev/null; then
            MOTIVO="el servicio falló: $(plutil -extract motivo raw -o - "$ESTADO_ROOT" 2>/dev/null)"; break
        fi
        if [ "$PASADO" -gt 600 ]; then MOTIVO="el servicio tardó más de 10 min"; break; fi
        avance DETALLE "$(t 'La instala el servicio de CineCaptions, sin contraseña…' 'The CineCaptions service is installing it, no password…')"
        sleep 2
    done
    rm -f "$PEDIDO" 2>/dev/null
    [ -n "$DMG_COMPARTIDO" ] && rm -f "$DMG_COMPARTIDO"; DMG_COMPARTIDO=""
    if [ -n "$HECHO" ]; then
        echo "el servicio de root la cambió: $ANTES → $AHORA"
        avance OK "$SISTEMA"
    else
        echo "$MOTIVO: la instalo en ~/Applications"
        cerrar_cineCaptions                                    # (si falla, el servicio viejo pudo abrir la versión vieja)
        APP="$PROPIA"; RAZON=ajena
    fi
fi

if [ "$RAZON" != root ]; then
DESTINO=$(dirname "$APP")
mkdir -p "$DESTINO"
NUEVO="$APP.nuevo"
rm -rf "$NUEVO" 2>/dev/null
TOTAL_KB=$(cat "$(dirname "$0")/tamano_kb" 2>/dev/null)
case "$TOTAL_KB" in ''|*[!0-9]*) TOTAL_KB=$(du -sk "$ORIGEN" 2>/dev/null | cut -f1) ;; esac
LIBRE_KB=$(df -k "$DESTINO" 2>/dev/null | awk 'NR==2 {print $4}')
if [ -n "$LIBRE_KB" ] && [ -n "$TOTAL_KB" ] && [ "$LIBRE_KB" -lt $((TOTAL_KB + 204800)) ]; then
    fallo "$(t "No hay espacio: CineCaptions necesita $((TOTAL_KB / 1024 + 200)) MB libres y quedan $((LIBRE_KB / 1024)) MB." \
        "Not enough space: CineCaptions needs $((TOTAL_KB / 1024 + 200)) MB free and there are $((LIBRE_KB / 1024)) MB.")"
fi
# ditto conserva la firma y los permisos; mientras copia, el avance en MB (la ventana lo enseña junto al paso)
ditto "$ORIGEN" "$NUEVO" &
COPIA=$!
while kill -0 "$COPIA" 2>/dev/null; do
    HECHO_KB=$(du -sk "$NUEVO" 2>/dev/null | cut -f1)
    if [ -n "$HECHO_KB" ] && [ -n "$TOTAL_KB" ] && [ "$TOTAL_KB" -gt 0 ]; then
        [ "$HECHO_KB" -gt "$TOTAL_KB" ] && HECHO_KB=$TOTAL_KB
        avance DETALLE "$(t "Copiando… $((HECHO_KB / 1024)) de $((TOTAL_KB / 1024)) MB" "Copying… $((HECHO_KB / 1024)) of $((TOTAL_KB / 1024)) MB")"
    fi
    sleep 0.5
done
wait "$COPIA" || { rm -rf "$NUEVO"; fallo "$(t 'No se pudo copiar CineCaptions en Aplicaciones. Vuelve a intentarlo; si se repite, envíanos el registro.' \
    'CineCaptions could not be copied to Applications. Try again; if it happens again, send us the log.')"; }
COPIA=""
[ -x "$NUEVO/Contents/MacOS/CineCaptions" ] || { rm -rf "$NUEVO"; fallo "$(t 'La copia de CineCaptions quedó incompleta.' 'The CineCaptions copy is incomplete.')"; }
# cambiar de nombre es al momento: nunca queda una app a medias. La de antes (de este usuario) se aparta y se borra
VIEJO=""
if [ -e "$APP" ]; then
    VIEJO="$DESTINO/.CineCaptions anterior $$.app"
    mv "$APP" "$VIEJO" || { rm -rf "$NUEVO"; fallo "$(t 'No se pudo cambiar la versión anterior de CineCaptions. Vuelve a intentarlo; si se repite, envíanos el registro.' \
        'The previous CineCaptions could not be replaced. Try again; if it happens again, send us the log.')"; }
fi
if ! mv "$NUEVO" "$APP"; then
    [ -n "$VIEJO" ] && mv "$VIEJO" "$APP"
    rm -rf "$NUEVO"
    fallo "$(t 'No se pudo poner CineCaptions en Aplicaciones.' 'CineCaptions could not be put in Applications.')"
fi
NUEVO=""
[ -n "$VIEJO" ] && { rm -rf "$VIEJO" 2>/dev/null || echo "no pude borrar $VIEJO"; }
avance OK "$APP"
if [ "$RAZON" = ajena ]; then
    # (la de /Applications es de otra cuenta o se instaló con contraseña: esta queda en la carpeta de Aplicaciones de este usuario)
    avance AVISO "$(t 'En tu carpeta de Aplicaciones' 'In your own Applications folder')"
fi
fi

# ---------------------------------------------------------------------------------------------------- 2) permiso para abrirla
avance PASO "2/7"
# sin cuarentena (Gatekeeper no vuelve a preguntar: ya se permitió este instalador) ni FinderInfo (rompe la firma estricta)
xattr -dr com.apple.quarantine "$APP" 2>/dev/null
xattr -d com.apple.FinderInfo "$APP" 2>/dev/null
touch "$APP" 2>/dev/null
[ -x "$LSREG" ] && "$LSREG" -f -R -trusted "$APP" >/dev/null 2>&1
avance OK "$(t 'Lista para abrir' 'Ready to open')"

# ---------------------------------------------------------------------------------------------------- 3-7) lo hace la app
# scripts de Resolve, tipografías, servicio, Dock y el motor de voz e IA (se queda bajando aparte) en UNA pasada de la app (cada vez que se
# abre tarda); escribe PASO/OK/AVISO ella misma
avance PASO "3/7"
ESTADO="${TMPDIR:-/tmp}/cinecaptions_pasos_$$.txt"; : > "$ESTADO"
CINECAPTIONS_AVANCE="$AVANCE" QT_QPA_PLATFORM=offscreen "$APP/Contents/MacOS/CineCaptions" --tarea pasos_mac "$ESTADO" "$IDIOMA" &
PASOS=$!
for _ in $(seq 1 360); do                     # (hasta 3 min: las tipografías y los scripts tardan segundos)
    kill -0 "$PASOS" 2>/dev/null || break
    sleep 0.5
done
if kill -0 "$PASOS" 2>/dev/null; then
    kill "$PASOS" 2>/dev/null
    echo "pasos_mac: no terminó en 3 min"
fi
wait "$PASOS"; CODIGO=$?; PASOS=""
sed 's/^/  pasos_mac: /' "$ESTADO"
rm -f "$ESTADO"
if [ "$CODIGO" != 0 ] || ! grep -q "7/7" "$AVANCE" 2>/dev/null; then
    # lo que falte lo hace CineCaptions al abrirse: no se detiene la instalación
    avance AVISO "$(t 'Se termina al abrir CineCaptions' 'It finishes when CineCaptions opens')"
fi

# las tarjetas del aviso de actualizaciones SON CineCaptions (`--tarea aviso_mac`): si hay una abierta, abrir CineCaptions solo la traería al
# frente (MEDIDO en el servicio). Se cierran antes de que la ventana lo abra
pkill -f -- "--tarea aviso_mac" >/dev/null 2>&1
avance FIN "$VERSION	$APP"
exit 0
