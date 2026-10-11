# Aplica la partición YA VERIFICADA del script principal (v5.4.44): copia los 6 módulos nuevos a 1_codigo y reemplaza "CineCaptions (script principal).py".
# Antes guarda el original en 3_compilar\partido_listo\original\ (y git también lo tiene). Deshacer: copiar ese original de vuelta y borrar los 6 módulos nuevos.
$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$codigo = Join-Path $raiz '1_codigo'
$respaldo = Join-Path $PSScriptRoot 'original'
New-Item -ItemType Directory -Force $respaldo | Out-Null
Copy-Item -LiteralPath (Join-Path $codigo 'CineCaptions (script principal).py') -Destination $respaldo -Force
foreach ($n in 'ui_comun', 'ventanas_idioma', 'selector_emojis', 'ventana_composicion', 'ventana_plantillas', 'editor_palabras') {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "$n.py") -Destination $codigo -Force
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'CineCaptions (script principal).py') -Destination $codigo -Force
Write-Host 'Aplicado. Comprueba con: 6_compilacion\venv314\Scripts\python.exe 1_codigo\herramientas_dev\probar_ventanas_humo.py salida.txt'
