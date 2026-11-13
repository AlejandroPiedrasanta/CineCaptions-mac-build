# CineCaptions Ventas para Mac

La app de ventas también corre en Mac (desde la 2.9), Apple Silicon e Intel, macOS 12 o posterior.

## Qué cambia en Mac
- La clave de administrador va en el **Llavero** de macOS (no en el archivo). `config.json` vive en
  `~/Library/Application Support/CineCaptions Ventas/` y solo dice `"clave": "llavero"`.
- Instalar: abrir el `.dmg` y arrastrar **CineCaptions Ventas** a **Aplicaciones**. No está firmada por Apple: la primera
  vez, si macOS dice que no se puede abrir, ir a **Ajustes del Sistema › Privacidad y seguridad › Abrir de todos modos**.
- Todo lo demás es igual que en Windows.

## Cómo se arma
PyInstaller no compila para Mac desde Windows: se arma en una Mac de GitHub.

    powershell -File mac\Compilar_Ventas_Mac.ps1

1. Copia la app a `ventas/` del espejo de compilación (`AlejandroPiedrasanta/CineCaptions-mac-build`, **público**; el
   mismo clon que usa `Actualizar_Mac.ps1`) y el flujo `.github/workflows/ventas_mac.yml` del proyecto.
2. GitHub corre `mac/construir_ventas_mac.sh` en `macos-15` (Apple Silicon) y `macos-15-intel`: las pruebas de la app
   (`prueba_acciones.py`), arma la `.app` (`mac/ventas_mac.spec`, ícono de `mac/icono_mac.py`), la **prueba armada**
   (guarda la clave en el Llavero y saca capturas de cada página contra `servidor_prueba.py`) y arma el `.dmg`.
3. Baja `CineCaptions_Ventas_Mac_<AppleSilicon|Intel>_<versión>.dmg` a `programa/` y las capturas a `programa/capturas_mac/`.

`-SoloDescargar` baja lo de la última compilación buena sin volver a compilar.

## Pruebas
`prueba_acciones.py` corre igual en Windows y en Mac: usa `CC_VENTAS_CONFIG` (carpeta de configuración aparte) y
`CC_VENTAS_LLAVERO` (otra entrada del Llavero), así nunca toca la configuración ni la clave reales.
