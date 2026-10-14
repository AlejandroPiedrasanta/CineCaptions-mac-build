# CineCaptions - By Cinema Productions
# 3_compilar/Construir_Instalador.ps1 - arma el instalador de Windows de principio a fin (PyInstaller + autoprueba + C#).
# ============================================================================
# Construye Instalar_CineCaptions_<version>.exe a partir del codigo fuente (Actualizar_Windows.ps1 lo llama y sube la version si hace falta)
#   powershell -ExecutionPolicy Bypass -File 3_compilar\Construir_Instalador.ps1
#
# Usa (todo dentro de CineCaptions\):
#   1_codigo\*.py .................. el programa (el principal: "CineCaptions (script principal).py")
#   recursos\ .................... resolve_scripts, locales, plantillas_incluidas, fonts, sfx_library,
#                                  emojis, logo_cinecaptions.png / .ico
#   compilar\
#     requirements.txt ........... librerias con version FIJA (Python 3.14 + PySide6)
#     cinecaptions.spec + rthook_stanza_stub.py   PyInstaller
#     Instalador.cs + app.manifest            el instalador/desinstalador (csc.exe de .NET Framework 4, viene con Windows)
#     banner.jpg ................. la foto del banner del instalador (va dentro del .exe)
# Deja:
#   _compilacion\ ................ Python 3.14, venv314, build de PyInstaller (se puede borrar: se rehace)
#   INSTALADORES\Windows\Instalar_CineCaptions_<version>.exe  lo unico que se entrega (con la version en el nombre; los anteriores se borran)
# -SoloInstalador: reusa el programa ya compilado en 6_compilacion\dist (solo rehace el instalador)
# ============================================================================
param([switch]$SoloInstalador, [switch]$Limpio)
$ErrorActionPreference = 'Stop'
$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
$raiz = Split-Path -Parent $aqui
$codigo = Join-Path $raiz '1_codigo'
$recursos = Join-Path $raiz '2_recursos'
$obra = Join-Path $raiz '6_compilacion'
$utf8 = New-Object System.Text.UTF8Encoding($false)
$env:PYTHONIOENCODING = 'utf-8'
try { [Console]::OutputEncoding = $utf8 } catch {}
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
function Paso($t) { Write-Host ''; Write-Host "== $t" -ForegroundColor Cyan }
# Borra una carpeta aunque la sincronizacion de la nube o el Explorador la dejen en solo lectura (desktop.ini, .cf): quita los atributos de TODO, tambien de la carpeta raiz.
function BorrarCarpeta($ruta) {
    if (-not (Test-Path -LiteralPath $ruta)) { return }
    foreach ($i in Get-ChildItem -LiteralPath $ruta -Recurse -Force -ErrorAction SilentlyContinue) {
        try { $i.Attributes = $(if ($i.PSIsContainer) { 'Directory' } else { 'Normal' }) } catch {}
    }
    try { (Get-Item -LiteralPath $ruta -Force).Attributes = 'Directory' } catch {}
    [IO.Directory]::Delete($ruta, $true)
}

$dist = Join-Path $obra 'dist'
$app = Join-Path $dist 'CineCaptions'
$appExe = Join-Path $app 'CineCaptions.exe'
$venv = Join-Path $obra 'venv314'
$vpy = Join-Path $venv 'Scripts\python.exe'

# 0) documentacion y registro de cambios (3_compilar\encabezados.py + 3_compilar\documentar.py) ----------
#    encabezado de autor en cada archivo, indice y mapa del codigo del LEEME al dia, y en
#    REGISTRO_DE_CAMBIOS.txt los archivos que cambiaron desde la compilacion anterior
function Documentar {
    if (-not (Test-Path $vpy)) { return }
    Paso 'Documentacion y registro de cambios'
    & $vpy (Join-Path $aqui 'encabezados.py')
    & $vpy (Join-Path $aqui 'documentar.py')
    if ($LASTEXITCODE -ne 0) { Write-Host '    (no se pudo actualizar la documentacion: se sigue compilando)' -ForegroundColor Yellow }
}
# 0b) UNA sola version: version.py manda y los scripts de Resolve / el Puente se ponen a la misma (si no, el programa avisa de "otra version instalada") ----------
function SincronizarVersion {
    if (-not (Test-Path $vpy)) { return }
    Paso 'Version del programa y de los scripts de Resolve'
    & $vpy (Join-Path $aqui 'sincronizar_version.py')
    if ($LASTEXITCODE -ne 0) { throw 'No pude sincronizar la version de los scripts de Resolve' }
}
if ($SoloInstalador) {
    SincronizarVersion
    Documentar
    if (-not (Test-Path $appExe)) { throw 'No hay programa compilado en 6_compilacion\dist: corre el script sin -SoloInstalador' }
    $verPy = [IO.File]::ReadAllText((Join-Path $codigo 'version.py'), $utf8)
    if ($verPy -notmatch "APP_VERSION = '([\d.]+)'") { throw 'No encontre APP_VERSION en version.py' }
    $version = $matches[1]
} else {
# 1) Python 3.14 y el entorno de compilacion ----------------------------------------
#    El interprete vive en 6_compilacion\python-3.14.8 (lo deja ahi el Python Install
#    Manager con --target, sin tocar el sistema) y el venv en 6_compilacion\venv314.
Paso 'Entorno de compilacion (Python 3.14)'
# si la carpeta del proyecto se movio, el venv sigue apuntando a la ruta vieja: se corrige solo
$cfg = Join-Path $venv 'pyvenv.cfg'
$pyBase = Join-Path $obra 'python-3.14.8'
if ((Test-Path $cfg) -and (Test-Path (Join-Path $pyBase 'python.exe'))) {
    $txt = [IO.File]::ReadAllText($cfg, $utf8)
    if ($txt -notmatch [regex]::Escape("home = $pyBase")) {
        $txt = ($txt -replace '(?m)^home = .*$', "home = $pyBase") -replace '(?m)^executable = .*$', ("executable = " + (Join-Path $pyBase 'python.exe'))
        [IO.File]::WriteAllText($cfg, $txt, $utf8)
        Write-Host '    venv: ruta del interprete corregida (la carpeta del proyecto se movio)'
    }
}
if (-not (Test-Path $vpy)) {
    New-Item -ItemType Directory -Force -Path $obra | Out-Null
    $carpetaPy = Join-Path $obra 'python-3.14.8'
    $py314 = Join-Path $carpetaPy 'python.exe'
    if (-not (Test-Path $py314) -and (Get-Command pymanager -ErrorAction SilentlyContinue)) {
        & pymanager install -y "--target=$carpetaPy" 3.14.8
    }
    if (-not (Test-Path $py314)) {
        try { $py314 = (& py -V:3.14 -c "import sys;print(sys.executable)").Trim() } catch { $py314 = $null }
    }
    if (-not $py314 -or -not (Test-Path $py314)) { throw 'Falta Python 3.14 para compilar: instala el Python Install Manager de python.org y vuelve a correr este script' }
    & $py314 -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'No pude crear el venv de compilacion' }
}
& $vpy -m pip install --progress-bar off -q -r (Join-Path $aqui 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'pip install -r requirements.txt fallo' }
# argostranslate SIN dependencias: declara stanza y spacy, que arrastran torch (ver requirements.txt)
& $vpy -m pip install --progress-bar off -q --no-deps 'argostranslate==1.11.0'
if ($LASTEXITCODE -ne 0) { throw 'pip install argostranslate fallo' }
& $vpy -c "import sys; assert sys.version_info[:2] == (3, 14), sys.version"
if ($LASTEXITCODE -ne 0) { throw 'El venv de compilacion no es Python 3.14' }
SincronizarVersion
Documentar

# 2) fuentes preparadas ----------------------------------------------------------------
Paso 'Codigo fuente'
$fuentes = Join-Path $obra 'fuentes'
BorrarCarpeta $fuentes
New-Item -ItemType Directory -Force -Path $fuentes | Out-Null
foreach ($f in Get-ChildItem $codigo -Filter '*.py') {
    Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $fuentes $f.Name)
}
if (-not (Test-Path (Join-Path $fuentes 'CineCaptions (script principal).py'))) { throw 'Falta el script principal en codigo' }
& $vpy -m compileall -q $fuentes
if ($LASTEXITCODE -ne 0) { throw 'Hay errores de sintaxis en 1_codigo\*.py' }
$verPy = [IO.File]::ReadAllText((Join-Path $fuentes 'version.py'), $utf8)
if ($verPy -notmatch "APP_VERSION = '([\d.]+)'") { throw 'No encontre APP_VERSION en version.py' }
$version = $matches[1]
Write-Host "CineCaptions $version"

# 3) PyInstaller ------------------------------------------------------------------------
Paso 'Compilando el programa (PyInstaller, 3-6 min)'
$env:CINECAPTIONS_FUENTES = $fuentes
$env:CINECAPTIONS_RECURSOS = $recursos
$env:CINECAPTIONS_VERSION = $version
BorrarCarpeta (Join-Path $dist 'CineCaptions')      # (PyInstaller no puede borrar la salida anterior si la sincronizacion la dejo en solo lectura)
Push-Location $aqui
try {
    # v5.5: por defecto SIN --clean: PyInstaller reutiliza su analisis (lo que no cambio no se vuelve a mirar). -Limpio lo rehace todo.
    $opciones = @('--noconfirm', '--log-level', 'ERROR', '--distpath', $dist, '--workpath', (Join-Path $obra 'work'))
    if ($Limpio) { $opciones += '--clean' }
    & $vpy -m PyInstaller @opciones 'cinecaptions.spec'
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller fallo' }
} finally { Pop-Location }
if (-not (Test-Path $appExe)) { throw 'PyInstaller no dejo el .exe' }

# 4) autoprueba del compilado (la misma que corre el instalador en cada equipo) ------------------
Paso 'Autoprueba del programa compilado'
$estado = Join-Path $obra 'autoprueba.txt'
[IO.File]::WriteAllText($estado, '', $utf8)
$p = Start-Process -FilePath $appExe -ArgumentList '--tarea', 'verificar', ('"' + $estado + '"') -PassThru -Wait
Get-Content -LiteralPath $estado -Encoding UTF8 | Where-Object { $_ -notmatch '^PROGRESO' } | ForEach-Object { Write-Host "    $_" }
if ($p.ExitCode -ne 0) { throw 'La autoprueba del compilado fallo: no se arma el instalador' }
}

# 4b) firma digital (v5.5.7): Smart App Control de Windows 11 y los antivirus bloquean librerias SIN FIRMA (en un cliente: av\format.pyd y
#     numpy\random\_pcg64.pyd, "Bad Image" 0xc0e90002). Si existe 3_compilar\firma.json se firman todos los .exe/.dll/.pyd que no traen firma valida
#     (unos 140; los de Python y Qt ya vienen firmados). Sin firma.json no se toca nada. Formatos de firma.json:
#       {"tipo": "trusted_signing", "signtool": "C:\\...\\signtool.exe", "dlib": "C:\\...\\Azure.CodeSigning.Dlib.dll", "metadata": "C:\\...\\metadata.json"}
#       {"tipo": "pfx", "archivo": "C:\\...\\certificado.pfx", "clave_env": "CC_FIRMA_CLAVE"}       (la clave, en esa variable de entorno; nunca en el archivo)
function FirmarArchivos($rutas) {
    $cfgRuta = Join-Path $aqui 'firma.json'
    if (-not (Test-Path -LiteralPath $cfgRuta)) { return 0 }
    $cfg = Get-Content -LiteralPath $cfgRuta -Raw -Encoding UTF8 | ConvertFrom-Json
    $sinFirma = @($rutas | Where-Object { (Get-AuthenticodeSignature -FilePath $_).Status -ne 'Valid' })
    if ($sinFirma.Count -eq 0) { return 0 }
    if ($cfg.tipo -eq 'trusted_signing') {
        for ($i = 0; $i -lt $sinFirma.Count; $i += 50) {
            $lote = $sinFirma[$i..([Math]::Min($i + 49, $sinFirma.Count - 1))]
            & $cfg.signtool sign /fd SHA256 /tr 'http://timestamp.acs.microsoft.com' /td SHA256 /dlib $cfg.dlib /dmdf $cfg.metadata @lote | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'La firma (Trusted Signing) fallo' }
        }
    } elseif ($cfg.tipo -eq 'pfx') {
        $clave = [Environment]::GetEnvironmentVariable([string]$cfg.clave_env)
        $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($cfg.archivo, $clave)
        foreach ($f in $sinFirma) {
            $r = Set-AuthenticodeSignature -FilePath $f -Certificate $cert -HashAlgorithm SHA256 -TimestampServer 'http://timestamp.digicert.com'
            if ($r.Status -ne 'Valid') { throw "No se pudo firmar $f ($($r.StatusMessage))" }
        }
    } else { throw "firma.json: tipo desconocido ($($cfg.tipo))" }
    return $sinFirma.Count
}
if (Test-Path -LiteralPath (Join-Path $aqui 'firma.json')) {
    Paso 'Firmando el programa (firma digital)'
    $pe = @(Get-ChildItem -LiteralPath $app -Recurse -File -Include *.exe, *.dll, *.pyd | ForEach-Object { $_.FullName })
    Write-Host ("    firmados: {0} de {1}" -f (FirmarArchivos $pe), $pe.Count)
}

# 5) el instalador (C#) ----------------------------------------------------------------
Paso 'Compilando el instalador'
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) { $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe' }
$tmp = Join-Path $obra 'instalador'
BorrarCarpeta $tmp
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$partes = (($version.Split('.') + @('0', '0', '0', '0'))[0..3]) -join '.'
$cs = Join-Path $tmp 'Instalador.cs'
[IO.File]::WriteAllText($cs, [IO.File]::ReadAllText((Join-Path $aqui 'Instalador.cs'), $utf8).Replace('__VERSION_ENSAMBLADO__', $partes).Replace('__VERSION_APP__', $version), $utf8)
$base = Join-Path $tmp 'Desinstalar.exe'
$fw = Split-Path -Parent $csc
$logo = Join-Path $recursos 'logo_cinecaptions.png'
& $csc /nologo /optimize+ /target:winexe /platform:anycpu /codepage:65001 "/out:$base" `
    "/win32icon:$(Join-Path $recursos 'logo_cinecaptions.ico')" "/win32manifest:$(Join-Path $aqui 'app.manifest')" `
    "/resource:$logo,logo.png" "/resource:$(Join-Path $recursos 'logo_cinema_productions.png'),marca.png" "/resource:$(Join-Path $aqui 'banner.jpg'),banner.jpg"  `
    "/resource:$(Join-Path $aqui 'banner_capas\astro_runas.png'),astro_runas.png" "/resource:$(Join-Path $aqui 'banner_capas\astro_engr.png'),astro_engr.png" `
    "/resource:$(Join-Path $aqui 'banner_capas\astro_fili.png'),astro_fili.png" "/resource:$(Join-Path $aqui 'banner_capas\astro_nucleo.png'),astro_nucleo.png" "/reference:$fw\System.IO.Compression.dll" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll $cs
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $base)) { throw 'No se pudo compilar Instalador.cs' }
[void](FirmarArchivos @($base))          # v5.5.7: el desinstalador/instalador base tambien (si hay firma.json)

# 6) paquete: el programa compilado + el desinstalador, pegados al final del .exe ------------------
Paso 'Empaquetando (1-3 min)'
$zipRuta = Join-Path $tmp 'paquete.zip'
$zip = [IO.Compression.ZipFile]::Open($zipRuta, 'Create')
try {
    [void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $base, 'Desinstalar.exe', 'Optimal')
    $n = 0
    foreach ($f in (Get-ChildItem -LiteralPath $app -Recurse -File)) {
        $rel = 'programa/' + $f.FullName.Substring($app.Length + 1).Replace('\', '/')
        [void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $f.FullName, $rel, 'Optimal')
        $n++
    }
    Write-Host "    $n archivos"
} finally { $zip.Dispose() }
# v5.3.2: el instalador lleva la VERSION en el nombre (como los de Mac) y los anteriores se borran: asi se ve de un vistazo cual es el ultimo y nunca queda uno viejo
# haciendose pasar por el actual. Se arma con otro nombre y solo al verificarlo se quitan los demas.
$salida = Join-Path $raiz 'INSTALADORES\Windows'
New-Item -ItemType Directory -Force -Path $salida | Out-Null
$exe = Join-Path $salida ("Instalar_CineCaptions_{0}.exe" -f $version)
$parcial = $exe + '.parcial'
$sal = [IO.File]::Open($parcial, 'Create')
try {
    $b = [IO.File]::ReadAllBytes($base); $sal.Write($b, 0, $b.Length)
    $ini = [long]$sal.Position
    $z = [IO.File]::OpenRead($zipRuta); try { $z.CopyTo($sal) } finally { $z.Dispose() }
    $pie = [BitConverter]::GetBytes($ini) + [Text.Encoding]::ASCII.GetBytes('CINECAP1')
    $sal.Write($pie, 0, 16)
} finally { $sal.Dispose() }
[IO.File]::Delete($zipRuta)
# verificacion: la version del .exe es la de version.py y el paquete pegado se abre con todo dentro
$vi = (Get-Item $parcial).VersionInfo.FileVersion
if ($vi -ne $partes) { [IO.File]::Delete($parcial); throw "El instalador dice version $vi y version.py dice $version" }
try {
    $chk = [IO.File]::OpenRead($parcial)
    try {
        [void]$chk.Seek(-16, [IO.SeekOrigin]::End)
        $pieLeido = New-Object byte[] 16
        [void]$chk.Read($pieLeido, 0, 16)
        if ([Text.Encoding]::ASCII.GetString($pieLeido, 8, 8) -ne 'CINECAP1') { throw 'El instalador no trae la firma del paquete' }
        $posZip = [BitConverter]::ToInt64($pieLeido, 0)
        $largoZip = $chk.Length - 16 - $posZip
        [void]$chk.Seek($posZip, [IO.SeekOrigin]::Begin)
        $buf = New-Object byte[] $largoZip
        $leido = 0
        while ($leido -lt $largoZip) { $n = $chk.Read($buf, $leido, [int][Math]::Min(64MB, $largoZip - $leido)); if ($n -le 0) { break }; $leido += $n }
    } finally { $chk.Dispose() }
    $mem = New-Object IO.MemoryStream(, $buf)
    $sub = New-Object IO.Compression.ZipArchive($mem)
    $nombres = @($sub.Entries | ForEach-Object { $_.FullName })
    $sub.Dispose(); $mem.Dispose()
    foreach ($necesario in @('Desinstalar.exe', 'programa/CineCaptions.exe')) {
        if ($nombres -notcontains $necesario) { throw "El paquete no trae $necesario" }
    }
    Write-Host ("    paquete verificado: {0} archivos, version {1}" -f $nombres.Count, $vi)
} catch { [IO.File]::Delete($parcial); throw }
if (Test-Path -LiteralPath $exe) { [IO.File]::Delete($exe) }
[IO.File]::Move($parcial, $exe)
foreach ($viejo in (@(Get-ChildItem -LiteralPath $salida -Filter 'Instalar_CineCaptions*.exe' -File) + @(Get-ChildItem -LiteralPath $raiz -Filter 'Instalar_CineCaptions*.exe' -File))) {
    if ($viejo.FullName -ne $exe) { [IO.File]::Delete($viejo.FullName); Write-Host "    (version anterior quitada: $($viejo.Name))" }
}
$huella = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
[IO.File]::WriteAllText((Join-Path $obra 'ultima_compilacion.json'), ('{{"version": "{0}", "archivo": "{1}", "sha256": "{2}", "fecha": "{3}"}}' -f $version, (Split-Path $exe -Leaf), $huella, (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')), $utf8)
Paso ("LISTO  {0}  ({1:N1} MB)" -f $exe, ((Get-Item $exe).Length / 1MB))
