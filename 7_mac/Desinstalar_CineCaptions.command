#!/bin/bash
# CineCaptions · By Cinema Productions
# 7_mac/Desinstalar_CineCaptions.command — quita CineCaptions, su servicio de actualizaciones y sus scripts del menu de Resolve.
# Conserva ~/DaVinciSubtitles (proyectos, licencia y ajustes) y las tipografias instaladas.
# v5.91: desde que se instala arrastrando a Aplicaciones basta con tirar la app a la Papelera (su servicio del usuario se quita solo al no
# encontrarla); este script ademas limpia los scripts de Resolve y, en las Mac con la 5.87-5.90, el servicio de root (pide la contraseña).
APP="/Applications/CineCaptions.app"
ETIQUETA="com.cinemaproductions.cinecaptions.actualizar"
echo "Esto desinstala CineCaptions (tus proyectos y tu licencia se conservan)."
read -r -p "¿Continuar? (s/n) " R
[ "$R" = "s" ] || [ "$R" = "S" ] || exit 0
if [ -x "$APP/Contents/MacOS/CineCaptions" ]; then
    QT_QPA_PLATFORM=offscreen "$APP/Contents/MacOS/CineCaptions" --tarea quitar_scripts /tmp/cinecaptions_quitar.txt
    grep -v '^PROGRESO' /tmp/cinecaptions_quitar.txt 2>/dev/null; rm -f /tmp/cinecaptions_quitar.txt
fi
# v5.91: el servicio de actualizaciones del usuario (sin contraseña)
launchctl bootout "gui/$(id -u)/$ETIQUETA" 2>/dev/null
rm -f "$HOME/Library/LaunchAgents/$ETIQUETA.plist" "$HOME/Library/Logs/CineCaptions_actualizar.log"
rm -rf "$HOME/Library/Application Support/CineCaptions/pedidos" "$HOME/Library/Application Support/CineCaptions/actualizar"
# v5.87-5.90: el servicio de root que instalaba las versiones nuevas (lo ponía el .pkg)
if [ -e "/Library/LaunchDaemons/$ETIQUETA.plist" ] || [ -d /Users/Shared/CineCaptions ]; then
    echo "Se pedirá tu contraseña para quitar el servicio de las versiones anteriores."
    sudo launchctl bootout "system/$ETIQUETA" 2>/dev/null
    sudo rm -f "/Library/LaunchDaemons/$ETIQUETA.plist" /Library/Logs/CineCaptions_actualizar.log
    sudo rm -rf "/Library/Application Support/CineCaptions/actualizar" /Users/Shared/CineCaptions
    sudo rmdir "/Library/Application Support/CineCaptions" 2>/dev/null
    sudo pkgutil --forget com.cinemaproductions.cinecaptions >/dev/null 2>&1
fi
if [ -d "$APP" ]; then
    if [ "$(stat -f%u "$APP")" = "$(id -u)" ]; then rm -rf "$APP"; else echo "Se pedirá tu contraseña para borrar la app."; sudo rm -rf "$APP"; fi
fi
# v5.4.45: los audios temporales que renderiza Resolve para transcribir (carpeta interna, fuera de la vista)
rm -rf "$HOME/Library/Application Support/CineCaptions/audio"
rmdir "$HOME/Library/Application Support/CineCaptions" 2>/dev/null
echo "Listo: CineCaptions desinstalado."
