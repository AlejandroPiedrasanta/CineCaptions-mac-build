# CineCaptions · By Cinema Productions
# 1_codigo/tts_prueba.ps1 — voz de prueba (Windows SAPI) → WAV: para probar los captions con un video SIN audio útil.
# Uso: powershell -ExecutionPolicy Bypass -File tts_prueba.ps1 -Salida voz.wav [-Voz "Microsoft Sabina Desktop"] [-Velocidad 0] [-Texto "…"] [-Archivo guion.txt]
param([Parameter(Mandatory = $true)][string]$Salida, [string]$Voz = 'Microsoft Sabina Desktop', [int]$Velocidad = 0, [string]$Texto = '', [string]$Archivo = '')
Add-Type -AssemblyName System.Speech
if ($Archivo -ne '') { $Texto = [IO.File]::ReadAllText($Archivo, [Text.Encoding]::UTF8) }
if ($Texto -eq '') { throw 'Falta el texto (-Texto o -Archivo)' }
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try { $s.SelectVoice($Voz) } catch { Write-Host ('Voz no encontrada, uso la de por defecto: ' + $s.Voice.Name) }
$s.Rate = $Velocidad
$s.SetOutputToWaveFile($Salida)
$s.Speak($Texto)
$s.Dispose()
Write-Host ('Listo: ' + $Salida + ' (' + [math]::Round((Get-Item $Salida).Length / 1MB, 2) + ' MB)')
