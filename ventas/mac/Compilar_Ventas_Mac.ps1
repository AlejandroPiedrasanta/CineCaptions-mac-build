# CineCaptions Ventas · By Cinema Productions
# programa/mac/Compilar_Ventas_Mac.ps1 — arma los .dmg de Mac (Apple Silicon e Intel) de la app de ventas en GitHub.
#   1) copia la app (ventas.py, pruebas, servidor de prueba, fuentes, mac/) a ventas/ del espejo de compilación de Mac
#      (el mismo clon que usa Actualizar_Mac.ps1, así sus subidas nunca chocan) y el flujo .github/workflows/ventas_mac.yml;
#   2) lanza «Ventas Mac» en GitHub (macos-15 y macos-15-intel), que prueba la app en esa Mac antes de armar el .dmg;
#   3) baja los .dmg a programa/ y las capturas de la app en Mac a programa/capturas_mac/.
# El espejo es PÚBLICO (decisión del dueño, 2026-11-13): el código de la app se puede leer; la clave nunca va en el código.
#   powershell -File mac\Compilar_Ventas_Mac.ps1                (sube, compila y baja; ~15 min)
#   powershell -File mac\Compilar_Ventas_Mac.ps1 -SoloDescargar (solo baja lo de la última compilación)
param([switch]$SoloDescargar)
$ErrorActionPreference = 'Stop'
$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path          # programa\mac
$programa = Split-Path -Parent $aqui                             # programa
$raiz = (Resolve-Path (Join-Path $programa '..\..')).Path        # CineCaptions
$repo = 'AlejandroPiedrasanta/CineCaptions-mac-build'
$espejo = Join-Path $env:USERPROFILE 'CineCaptions-mac-espejo'
$flujo = 'ventas_mac.yml'
function Paso($t) { Write-Host "`n==> $t" -ForegroundColor Cyan }
function Nativo([scriptblock]$b) { & $b; if ($LASTEXITCODE -ne 0) { throw "Falló: $b (código $LASTEXITCODE)" } }
$version = (Select-String -Path (Join-Path $programa 'ventas.py') -Pattern "^VERSION = '([0-9.]+)'").Matches[0].Groups[1].Value

if (-not $SoloDescargar) {
    Paso "Espejo de compilación ($repo)"
    if (-not (Test-Path (Join-Path $espejo '.git'))) {
        Nativo { gh repo clone $repo $espejo -- -q }
        $id = gh api user -q '.id'; $login = gh api user -q '.login'
        git -C $espejo config user.name $login
        git -C $espejo config user.email "$id+$login@users.noreply.github.com"
    }
    Nativo { git -C $espejo pull -q --rebase }
    $destino = Join-Path $espejo 'ventas'
    robocopy $programa $destino /MIR /XD build capturas capturas_mac instalador __pycache__ `
        /XF *.exe *.dmg 'CineCaptions Ventas.spec' construir_instalador.ps1 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy falló ($LASTEXITCODE)" }
    Set-Content -Path (Join-Path $destino '.gitattributes') -Value '*.sh text eol=lf' -Encoding ASCII
    New-Item -ItemType Directory -Force (Join-Path $espejo '.github\workflows') | Out-Null
    Copy-Item (Join-Path $raiz ".github\workflows\$flujo") (Join-Path $espejo ".github\workflows\$flujo") -Force
    git -C $espejo add -A ventas ".github/workflows/$flujo"
    git -C $espejo diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        Nativo { git -C $espejo commit -q -m "Ventas Mac $version`n`nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" }
        Nativo { git -C $espejo push -q origin HEAD }
    } else { Write-Host '    (el espejo ya tenía esta versión)' }
    $sha = (git -C $espejo rev-parse HEAD).Trim()

    # 2.10 (el dueño: «quita la contraseña»): la clave de administrador va DENTRO de la app de Mac. Nunca en el código (el espejo
    # es público): sube como secreto de GitHub desde CineCaptions_claves\admin_ventas.txt, y el .dmg vuelve cifrado con otra
    # contraseña (ventas_artefacto.txt, se crea la primera vez) que solo está en esta PC y en los secretos.
    Paso "Secretos de la compilación (la clave incluida y la del .dmg cifrado)"
    $claves = Join-Path $env:USERPROFILE 'CineCaptions_claves'
    $archivoClave = Join-Path $claves 'admin_ventas.txt'
    $archivoArtefacto = Join-Path $claves 'ventas_artefacto.txt'
    if (Test-Path $archivoClave) {
        if (-not (Test-Path $archivoArtefacto)) {
            $bytes = [byte[]]::new(36); [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
            [IO.File]::WriteAllText($archivoArtefacto, ([Convert]::ToBase64String($bytes) -replace '[+/=]', ''))
        }
        $clave = (python -c "import sys; sys.path.insert(0, sys.argv[1]); import ventas; print(ventas.extraer_clave(ventas.leer_texto(sys.argv[2])))" $programa $archivoClave 2>$null | Select-Object -Last 1)
        if (-not $clave) { throw "No pude leer la clave de $archivoClave" }
        Nativo { gh secret set VENTAS_CLAVE -R $repo --body $clave | Out-Null }
        Nativo { gh secret set VENTAS_ARTEFACTO -R $repo --body ([IO.File]::ReadAllText($archivoArtefacto).Trim()) | Out-Null }
        $clave = $null
        Write-Host '    (la app de Mac llevará la clave incluida; el .dmg vendrá cifrado)'
    } else {
        Write-Host "    (sin $archivoClave : la app pedirá la clave como antes)"
    }

    Paso "Compilando en GitHub (Apple Silicon e Intel)"
    # (recién subido, GitHub tarda unos segundos en conocer el flujo: «workflow not found» se reintenta)
    for ($i = 1; $i -le 12; $i++) {
        gh workflow run $flujo -R $repo --ref main 2>$null
        if ($LASTEXITCODE -eq 0) { break }
        if ($i -eq 12) { throw "GitHub no encontró el flujo $flujo" }
        Start-Sleep -Seconds 10
    }
    $id = $null
    for ($i = 0; $i -lt 30 -and -not $id; $i++) {
        Start-Sleep -Seconds 4
        $id = gh run list -R $repo --workflow $flujo --commit $sha --limit 1 --json databaseId -q '.[0].databaseId'
    }
    if (-not $id) { throw 'No encontré la compilación en GitHub' }
    Write-Host "    https://github.com/$repo/actions/runs/$id"
    gh run watch $id -R $repo --exit-status --interval 30 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "La compilación falló: gh run view $id -R $repo --log-failed" }
} else {
    $id = gh run list -R $repo --workflow $flujo --status success --limit 1 --json databaseId -q '.[0].databaseId'
    if (-not $id) { throw 'No hay ninguna compilación buena de Ventas Mac' }
}

Paso "Bajando los .dmg y las capturas"
$tmp = Join-Path ([IO.Path]::GetTempPath()) "ventas-mac-$id"
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
Nativo { gh run download $id -R $repo -D $tmp }
# Los .dmg con la clave incluida vienen cifrados (.dmg.cifrado): se descifran aquí con ventas_artefacto.txt
$cifrados = @(Get-ChildItem $tmp -Recurse -Filter '*.dmg.cifrado')
if ($cifrados) {
    $artefacto = Join-Path $env:USERPROFILE 'CineCaptions_claves\ventas_artefacto.txt'
    if (-not (Test-Path $artefacto)) { throw "Los .dmg vienen cifrados y falta $artefacto" }
    $ossl = (Get-Command openssl -ErrorAction SilentlyContinue).Source
    if (-not $ossl) { $ossl = @('C:\Program Files\Git\ucrt64\bin\openssl.exe', 'C:\Program Files\Git\usr\bin\openssl.exe', 'C:\Program Files\Git\mingw64\bin\openssl.exe') | Where-Object { Test-Path $_ } | Select-Object -First 1 }
    if (-not $ossl) { throw 'Falta openssl (viene con Git para Windows) para descifrar los .dmg' }
    foreach ($c in $cifrados) {
        $plano = $c.FullName -replace '\.cifrado$', ''
        & $ossl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -md sha256 -in $c.FullName -out $plano -pass "file:$artefacto"
        if ($LASTEXITCODE -ne 0) { throw "No pude descifrar $($c.Name)" }
        Remove-Item $c.FullName -Force
    }
}
Get-ChildItem $programa -Filter 'CineCaptions_Ventas_Mac_*.dmg' | Remove-Item -Force      # la versión anterior se quita
Get-ChildItem $tmp -Recurse -Filter '*.dmg' | ForEach-Object { Copy-Item $_.FullName $programa; Write-Host "    $($_.Name)" }
$capturas = Join-Path $programa 'capturas_mac'
if (Test-Path $capturas) { Remove-Item -Recurse -Force $capturas }
foreach ($n in 'AppleSilicon', 'Intel') {
    $origen = Get-ChildItem $tmp -Directory | Where-Object Name -like "*$n*" | Select-Object -First 1
    if ($origen) {
        New-Item -ItemType Directory -Force (Join-Path $capturas $n) | Out-Null
        Get-ChildItem $origen.FullName -Recurse -Filter '*.png' | Copy-Item -Destination (Join-Path $capturas $n)
    }
}
Remove-Item -Recurse -Force $tmp
Write-Host "`nListo: los .dmg en programa\ y las capturas de la app en Mac en programa\capturas_mac\" -ForegroundColor Green
