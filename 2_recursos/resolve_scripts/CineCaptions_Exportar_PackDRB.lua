-- CineCaptions · By Cinema Productions
-- 2_recursos/resolve_scripts/CineCaptions_Exportar_PackDRB.lua — herramienta de desarrollo: exporta un pack como .drb.
--[[
CineCaptions_Exportar_PackDRB.lua
------------------------
HERRAMIENTA de una sola vez, no es parte del programa instalado.

Para que sirve
==============
El unico mecanismo de la API que mete los Text+ de un pack DIRECTO al Media
Pool en cualquier edicion (Free incluida) es importar un BIN EXPORTADO
(.drb) con ImportFolderFromFile. Pero un .drb solo se puede generar desde
adentro de Resolve, con el bin ya armado. Este script hace exactamente eso:

  1. Busca en el proyecto abierto los bins del pack ya preparados
     (los que empiezan por "RCS · ", uno por formato).
  2. Exporta cada uno a ~/DaVinciSubtitles/pack_<h|v|c>.drb.
  3. Escribe un informe en ~/DaVinciSubtitles/exportar_drb.txt.

Los tres archivos pack_h.drb / pack_v.drb / pack_c.drb se mandan al
desarrollador y la version siguiente los incrusta junto a los .drt: desde
ahi, Free importa el bin directo, con posicion, color y tipografia.

COMO SE CORRE (una vez, en un Resolve donde el pack YA se preparo — el Mac
con Studio es el seguro; se nota porque el Media Pool tiene los bins
"RCS · Base títulos dinámicos · v" con los 31 clips adentro)
============================================================
1. Abre el proyecto donde generaste subtitulos con el diseño automatico.
   Si solo tienes el bin de UN formato, genera una vez en un timeline de
   cada formato (vertical, horizontal, cuadrado) para tener los tres bins.
2. Copia este archivo a la carpeta de Scripts de Resolve:
     Windows: %APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility
     macOS:   ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility
3. Area de trabajo > Scripts > Utility > CineCaptions_Exportar_PackDRB
4. Manda los pack_*.drb y el exportar_drb.txt que deja en ~/DaVinciSubtitles/

NO borra nada, NO toca timelines y NO modifica los bins: solo exporta.
]]

local VERSION = "1.1"

-- Sin 'package': Resolve 21.1 no lo da a los scripts del menu (medido el
-- 16-09 en ResolveDebug.txt: "attempt to index global 'package' (a nil
-- value)" en la linea de SEP -o sea al CARGAR, antes del banner y de
-- cualquier escritura: los nueve .lua morian mudos y ninguno corria-).
-- SystemRoot/windir las pone Windows en TODO proceso y no existen fuera;
-- os.getenv es lo que ya usa home() y lo que usan los ejemplos Lua de
-- Blackmagic. Vale igual en 21.0.x: sirve a los que actualizan y a los
-- anteriores.
local function es_windows()
    return (os.getenv("SystemRoot") or os.getenv("windir")) ~= nil
end
local SEP = es_windows() and "\\" or "/"

-- La carpeta del usuario, con la MISMA regla que Path.home() de Python, que
-- es quien manda porque es donde la app deja los trabajos: en Windows
-- USERPROFILE (y HOMEDRIVE+HOMEPATH de respaldo) y NUNCA HOME —
-- ntpath.expanduser ni siquiera la mira. Mirar HOME primero fue el bug del
-- 15-09: en un Windows con HOME puesta (Git, MSYS, herramientas de
-- pipeline) el Puente vigilaba %HOME%\DaVinciSubtitles mientras la app
-- dejaba los trabajos en %USERPROFILE%\DaVinciSubtitles. El Puente latia
-- perfecto en una carpeta que la app no mira nunca: «no conecta el Puente»,
-- sin un solo error y sin una linea en ningun registro. Fuera de Windows
-- manda HOME, que ahi es la buena.
local function home()
    if es_windows() then
        local perfil = os.getenv("USERPROFILE")
        if perfil and perfil ~= "" then return perfil end
        local unidad = os.getenv("HOMEDRIVE") or ""
        local ruta = os.getenv("HOMEPATH")
        if ruta and ruta ~= "" then return unidad .. ruta end
    end
    return os.getenv("HOME") or os.getenv("USERPROFILE") or "."
end

local function carpeta_compartida()
    return home() .. SEP .. "DaVinciSubtitles"
end

local lineas = {}
local function apuntar(texto)
    lineas[#lineas + 1] = tostring(texto)
    print(texto)
end

-- Las listas de la API traen una clave extra 'n': ipairs + filtro, como en
-- todos los scripts del proyecto.
local function lista_api(lista)
    local fuera = {}
    if type(lista) ~= "table" then return fuera end
    for i = 1, (#lista or 0) do
        if lista[i] ~= nil then fuera[#fuera + 1] = lista[i] end
    end
    return fuera
end

local function obtener_resolve()
    local candidatos = {}
    if type(_G) == "table" and rawget(_G, "CINECAPTIONS_RESOLVE_DEL_PUENTE") ~= nil then
        candidatos[#candidatos + 1] = CINECAPTIONS_RESOLVE_DEL_PUENTE
    end
    if resolve ~= nil then candidatos[#candidatos + 1] = resolve end
    local ok, r = pcall(function() return Resolve() end)
    if ok and r then candidatos[#candidatos + 1] = r end
    ok, r = pcall(function() return bmd.scriptapp("Resolve") end)
    if ok and r then candidatos[#candidatos + 1] = r end
    for _, cand in ipairs(candidatos) do
        local vivo = false
        pcall(function() vivo = cand:GetProjectManager() ~= nil end)
        if vivo then return cand end
    end
    return nil
end

local function archivo_existe(ruta)
    local f = io.open(ruta, "rb")
    if f then
        local tam = f:seek("end")
        f:close()
        return true, tam or 0
    end
    return false, 0
end

-- El formato de un bin "RCS · <pack> · <h|v|c>": la ultima letra.
-- Copia IDENTICA del slug_pack de CineCaptions_Subtitulos.lua (un test compara
-- las tres copias byte a byte de comportamiento).
local function slug_pack(nombre)
    nombre = tostring(nombre or "")
    local suma = 0
    for i = 1, #nombre do suma = (suma + nombre:byte(i)) % 100000 end
    local limpio = nombre:lower():gsub("[^a-z0-9]", "_"):sub(1, 40)
    if limpio == "" then limpio = "pack" end
    return limpio .. "-" .. tostring(suma)
end

local function formato_del_bin(nombre)
    local f = nombre:match("·%s*([hvc])%s*$")
    return f
end

-- Tabla de plegado de tildes + nombre legible (v1.0.55): copias IDENTICAS
-- de las de CineCaptions_Subtitulos.lua y el gemelo .py (un test las compara).
-- El legible es el nombre que los gemelos leen como fuente 3 y el que se
-- le pide teclear al usuario; el slug con checksum queda como fuente 4.
local PLEGADO = {
    { "\195\161", "a" }, { "\195\169", "e" }, { "\195\173", "i" },
    { "\195\179", "o" }, { "\195\186", "u" }, { "\195\177", "n" },
    { "\195\188", "u" }, { "\195\129", "a" }, { "\195\137", "e" },
    { "\195\141", "i" }, { "\195\147", "o" }, { "\195\154", "u" },
    { "\195\145", "n" }, { "\195\156", "u" },
}

local NOMBRE_FORMATO = { h = "horizontal", v = "vertical", c = "cuadrado" }

local function nombre_legible(nombre)
    nombre = tostring(nombre or "")
    for _, par in ipairs(PLEGADO) do
        nombre = nombre:gsub(par[1], par[2])
    end
    local limpio = nombre:lower():gsub("[^a-z0-9]", "-")
        :gsub("%-+", "-"):gsub("^%-+", ""):gsub("%-+$", "")
    limpio = limpio:sub(1, 40):gsub("%-+$", "")
    if limpio == "" then limpio = "pack" end
    return limpio
end

local function ruta_respaldo_manual(pack, formato)
    local palabra = NOMBRE_FORMATO[formato] or tostring(formato)
    return carpeta_compartida() .. SEP .. "respaldo_"
        .. nombre_legible(pack) .. "_" .. palabra .. ".drb"
end

local function main()
    apuntar("CineCaptions_Exportar_PackDRB " .. VERSION)
    apuntar(string.rep("=", 58))

    local res = obtener_resolve()
    if not res then
        apuntar("NO pude hablar con Resolve. Si estas en Free, lanza primero "
                .. "CineCaptions_Puente y vuelve a correr esta herramienta.")
        return
    end
    local pm, proyecto, media_pool
    pcall(function() pm = res:GetProjectManager() end)
    pcall(function() proyecto = pm:GetCurrentProject() end)
    if not proyecto then
        apuntar("Hay Resolve pero no hay proyecto abierto.")
        return
    end
    pcall(function() media_pool = proyecto:GetMediaPool() end)
    if not media_pool then
        apuntar("No pude leer el Media Pool.")
        return
    end

    -- Buscar los bins RCS · en todo el arbol.
    local bins = {}
    local function recorrer(folder)
        for _, sub in ipairs(lista_api(folder:GetSubFolderList())) do
            local ok, nom = pcall(function() return sub:GetName() end)
            if ok and nom and nom:sub(1, 4) == "RCS " then
                local cuantos = 0
                pcall(function()
                    cuantos = #lista_api(sub:GetClipList())
                end)
                bins[#bins + 1] = { carpeta = sub, nombre = nom,
                                    clips = cuantos }
            end
            recorrer(sub)
        end
    end
    local ok_r, raiz = pcall(function() return media_pool:GetRootFolder() end)
    if not ok_r or not raiz then
        apuntar("No pude leer la raiz del Media Pool.")
        return
    end
    recorrer(raiz)

    if #bins == 0 then
        apuntar("No encontre ningun bin 'RCS · ...' en este proyecto.")
        apuntar("Genera primero subtitulos con el diseño automatico (asi se")
        apuntar("prepara el bin del pack) y vuelve a correr esta herramienta.")
        return
    end

    apuntar(string.format("Bins del pack encontrados: %d", #bins))
    for _, b in ipairs(bins) do
        apuntar(string.format("  '%s'  (%d clips)", b.nombre, b.clips))
    end
    apuntar("")

    local exportados = 0
    for _, b in ipairs(bins) do
        local formato = formato_del_bin(b.nombre) or "x"
        local destino = carpeta_compartida() .. SEP
            .. "pack_" .. formato .. ".drb"
        if b.clips == 0 then
            apuntar(string.format("  Salto '%s': esta vacio.", b.nombre))
            apuntar("     (llenalo primero: genera con el diseño "
                    .. "automatico y haz el arrastre que pide el cartel; "
                    .. "despues re-corre esta herramienta)")
        else
            -- Se prueban las firmas conocidas de exportacion de bins, bajo
            -- pcall, y se COMPRUEBA que el archivo quedo escrito: que la
            -- llamada no reviente no prueba nada (la leccion del fundido).
            -- BORRAR el destino antes de intentar: 'logrado' se decide
            -- mirando si el archivo existe DESPUES, y un pack_<f>.drb
            -- rancio (de otra sesion, o de OTRO bin del mismo formato en
            -- esta misma corrida) fingia exito y sus bytes ajenos se
            -- clonaban bajo el slug del pack actual (hallazgo de la
            -- revision de la v1.0.47).
            pcall(function() os.remove(destino) end)
            local intentos = {
                function() return media_pool:ExportFolder(b.carpeta, destino) end,
                function() return b.carpeta:Export(destino) end,
            }
            local logrado, via = false, nil
            for i, intento in ipairs(intentos) do
                pcall(intento)
                local existe, tam = archivo_existe(destino)
                if existe and tam > 0 then
                    logrado, via = true, i
                    break
                end
            end
            if logrado then
                local _, tam = archivo_existe(destino)
                apuntar(string.format("  '%s' -> %s  (%d bytes, via %d)",
                        b.nombre, destino, tam, via))
                exportados = exportados + 1
                -- Copias con IDENTIDAD de pack: el nombre LEGIBLE
                -- (v1.0.55, la fuente 3 de los gemelos) y el slug viejo
                -- (fuente 4, por si el programa instalado es anterior).
                -- El pack_<f>.drb generico no lleva identidad y los
                -- gemelos no lo leen. Asi, correr esta herramienta una
                -- vez deja el automatico funcionando sin mas pasos.
                pcall(function()
                    -- Captura CODICIOSA: con la perezosa, un pack con
                    -- ' · ' en el nombre producia un nombre que los
                    -- gemelos jamas leerian (y podia pisar el respaldo
                    -- de otro).
                    local pack = b.nombre:match("^RCS · (.*) · ")
                    if pack then
                        local fe = io.open(destino, "rb")
                        if fe then
                            local datos = fe:read("*a")
                            fe:close()
                            local copias = {
                                { ruta_respaldo_manual(pack, formato),
                                  " (el que usan los gemelos)" },
                                { carpeta_compartida() .. SEP
                                      .. "respaldo_bin_" .. slug_pack(pack)
                                      .. "_" .. formato .. ".drb",
                                  " (compatibilidad con versiones viejas)" },
                            }
                            for _, par in ipairs(copias) do
                                local fs = io.open(par[1], "wb")
                                if fs then
                                    fs:write(datos)
                                    fs:close()
                                    apuntar("     y como " .. par[1]
                                            .. par[2])
                                end
                            end
                        end
                    end
                end)
            else
                -- La sonda del 03-09 (Resolve 21.0.4.5) midio que
                -- ExportFolder ya NI EXISTE en la API. La salida real es
                -- la GUI, y hay que dar el NOMBRE EXACTO que los gemelos
                -- leen: el LEGIBLE (v1.0.55) — el usuario valido este flujo
                -- en su Mac y pidio un nombre que se pueda teclear.
                apuntar(string.format("  '%s' -> la API de tu Resolve no "
                        .. "exporta bandejas (ni ExportFolder ni "
                        .. "Folder:Export).", b.nombre))
                local pack = b.nombre:match("^RCS · (.*) · ")
                if pack then
                    apuntar("     HAZLO A MANO (una vez): clic derecho "
                            .. "sobre ese bin en el Media Pool ->")
                    apuntar("     Exportar bandeja... -> guarda EXACTO "
                            .. "como:")
                    apuntar("       " .. ruta_respaldo_manual(pack, formato))
                    apuntar("     Con ese archivo, el automatico queda "
                            .. "permanente en esta maquina; si me lo "
                            .. "mandas, lo embebo para todos.")
                end
            end
        end
    end

    apuntar("")
    if exportados > 0 then
        apuntar(string.format("Listo: %d bin(es) exportado(s). Manda los "
                .. "pack_*.drb junto con este informe.", exportados))
    else
        apuntar("La API no exporto ninguno: sigue la instruccion de "
                .. "arriba (clic derecho -> Exportar bandeja...) con el "
                .. "nombre exacto, y manda este informe igual.")
    end
end

local ok_main, err = pcall(main)
if not ok_main then
    apuntar("La herramienta se corto: " .. tostring(err))
end

local destino = carpeta_compartida() .. SEP .. "exportar_drb.txt"
local salida = io.open(destino, "w")
if salida then
    salida:write(table.concat(lineas, "\n"))
    salida:close()
    print("Informe escrito en: " .. destino)
else
    print("No pude escribir el informe en: " .. destino)
end
