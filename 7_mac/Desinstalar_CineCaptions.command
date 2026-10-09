#!/bin/bash
# CineCaptions · By Cinema Productions
# 7_mac/Desinstalar_CineCaptions.command — quita CineCaptions y sus scripts del menu de Resolve.
# Conserva ~/DaVinciSubtitles (proyectos, licencia y ajustes) y las tipografias instaladas.
APP="/Applications/CineCaptions.app"
echo "Esto desinstala CineCaptions (tus proyectos y tu licencia se conservan)."
read -r -p "¿Continuar? (s/n) " R
[ "$R" = "s" ] || [ "$R" = "S" ] || exit 0
if [ -x "$APP/Contents/MacOS/CineCaptions" ]; then
    QT_QPA_PLATFORM=offscreen "$APP/Contents/MacOS/CineCaptions" --tarea quitar_scripts /tmp/cinecaptions_quitar.txt
    grep -v '^PROGRESO' /tmp/cinecaptions_quitar.txt 2>/dev/null; rm -f /tmp/cinecaptions_quitar.txt
fi
echo "Se pedirá tu contraseña para borrar la app de Aplicaciones."
sudo rm -rf "$APP"
sudo pkgutil --forget com.cinemaproductions.cinecaptions >/dev/null 2>&1
echo "Listo: CineCaptions desinstalado."
