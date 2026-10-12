-- CineCaptions · By Cinema Productions
-- 2_recursos/resolve_scripts/CineCaptions_SfxMarcadores.lua — efectos de sonido en los marcadores por color (Resolve Free).
--[[
CineCaptions_SfxMarcadores.lua
---------------------
Coloca efectos de sonido en los MARCADORES del timeline, por COLOR.

El usuario configura una vez en el programa «rojo = Slams, azul =
Whoosh…» (se guarda en ~/DaVinciSubtitles/sfx_marcadores.json) y la app
deja la orden resuelta en ~/DaVinciSubtitles/sfx_marcadores_pendiente.json
con las rutas ABSOLUTAS de los sonidos de cada color (el patron de
sfx_pendiente.json: el 'datos' del job del Puente NO llega al Lua, el
input real viaja por archivo propio).

Que hace:
  1) lee la orden pendiente (sin orden: explica de donde sale)
  2) timeline:GetMarkers() — frameId RELATIVO a GetStartFrame()
  3) por cada marcador cuyo color este mapeado, un sonido de su carpeta
     (rotacion sin repetir pegados), importado una sola vez y colocado
     en su frame, en la primera pista de audio libre (o una nueva
     'SFX-Marcadores')
  4) los colores sin mapa se saltan Y SE DICE cuales
  5) borra la orden al terminar bien: correr dos veces no duplica

v3.1.9 (pedido literal: «que tambien se pueda reemplazar efectos en los
marcadores»): con "reemplazar" en la orden, los efectos NUESTROS que ya
suenan en el marcador (pistas SFX / SFX-Modificado / SFX-Marcadores, clips
cortos: las guardas de CineCaptions_SfxReemplazar) se quitan y el nuevo va en su
lugar; con "solo_reemplazar" (el modo Reemplazar del Lab) un marcador sin
efecto nuestro se deja como esta. Los efectos nuevos van SOLO a pistas
nuestras. Y corre en Free 21.1 sin io: la orden llega por su sidecar .lua y
el resultado por el registro de Resolve (el patron de CineCaptions_DetectarVideo).

Version en Lua para Resolve FREE (el Puente la corre con dofile); la
gemela de Studio es "CineCaptions - SFX Marcadores.py".
]]


-- v5.4: Resolve 21 deja VACIA la propiedad "Frames" de los clips de audio (solo da "Duration", HH:MM:SS:FF): sin esto
-- todo sonido se cortaba a 0,5 s (riser, boom, recortes).
function frames_de_audio(item, fps)
    local n = math.floor(tonumber(item:GetClipProperty("Frames")) or 0)
    if n >= 1 then return n end
    local tc = tostring(item:GetClipProperty("Duration") or "")
    local h, m, s, f = tc:match("^(%d+)[:;](%d+)[:;](%d+)[:;](%d+)$")
    if h then
        return (tonumber(h) * 3600 + tonumber(m) * 60 + tonumber(s)) * math.floor(fps + 0.5) + tonumber(f)
    end
    return 0
end

local VERSION = "5.4.47 (sfx marcadores)"

-- La ENTREGA del Puente (v1.0.43): ver CineCaptions_InsertarSFX.lua.
local ENTREGA_PUENTE = ({...})[1]
if type(ENTREGA_PUENTE) ~= "table" then ENTREGA_PUENTE = nil end
local NOMBRE_PISTA_NUEVA = "SFX-Marcadores"

-- Pistas que el producto considera SUYAS (mayusculas, sin espacios) y el
-- largo maximo de un efecto nuestro: las guardas de CineCaptions_SfxReemplazar
-- (v1.0.62). Fuera de ellas no se reemplaza NADA.
local PISTAS_NUESTRAS = {
    ["SFX"] = true, ["SFX-MODIFICADO"] = true, ["SFX-MARCADORES"] = true,
}
local DURACION_MAXIMA_SFX_SEGUNDOS = 20

-- Free 21.1 capo io en el menu de Scripts (medido el 16-09): sin io no se
-- escribe nada, la orden se lee de su sidecar .lua y el resultado viaja por
-- el registro de Resolve (ver el epilogo). Con io, todo como siempre.
local SIN_IO = (io == nil)

-- ---------------------------------------------------------------------
-- Utilidades (embebidas: cada script del menu es autocontenido)
-- ---------------------------------------------------------------------
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
    local sep = es_windows() and "\\" or "/"
    return home() .. sep .. "DaVinciSubtitles", sep
end

local NOMBRE_SCRIPT = "CineCaptions_SfxMarcadores"
local _salida = {}
local _print_original = print

local function escribir_archivo(ruta, texto)
    if SIN_IO then return false end
    local f = io.open(ruta, "w")
    if not f then return false end
    f:write(texto); f:close(); return true
end

-- v5.4.45: un caracter UTF-8 (2-4 bytes) como escape \uXXXX de json (par sustituto si pasa de U+FFFF); mal formado: "?".
local function json_u(c)
    local b1 = c:byte(1)
    local n = (b1 >= 240) and 4 or ((b1 >= 224) and 3 or 2)
    if #c ~= n then return "?" end
    local cp = b1 % ((n == 2) and 32 or ((n == 3) and 16 or 8))
    for k = 2, n do cp = cp * 64 + (c:byte(k) - 128) end
    if cp < 65536 then return string.format("\\u%04x", cp) end
    cp = cp - 65536
    return string.format("\\u%04x\\u%04x", 55296 + math.floor(cp / 1024), 56320 + cp % 1024)
end

local function json_escapar(s)
    s = tostring(s or "")
    s = s:gsub("\\", "\\\\"):gsub('"', '\\"')
    s = s:gsub("\r", " "):gsub("\n", "\\n"):gsub("\t", " ")
    -- v5.4.45: lo no ASCII viaja como \uXXXX (la app lo lee con json). En modo señales (Resolve Free sin io)
    -- este json pasa por el registro de Resolve, que cambia cada byte no ASCII por "?": «tamaño» llegaba «tama??o».
    return (s:gsub("[\192-\247][\128-\191]*", json_u))
end

print = function(...)
    local partes = {}
    for i = 1, select("#", ...) do
        partes[#partes + 1] = tostring((select(i, ...)))
    end
    _salida[#_salida + 1] = table.concat(partes, "\t")
    _print_original(...)
end

-- El MISMO json que lee resolve_bridge.ultimo_resultado(): al archivo con
-- io, y por el registro de Resolve sin io (v3.1.9, gemela de la de
-- CineCaptions_DetectarVideo). 'texto' va al FINAL: si el registro recortara la
-- linea, la cabecera sobrevive.
local function json_resultado(ok, mensaje, texto)
    local extra = ""
    if texto ~= nil then
        extra = string.format(', "texto": "%s"', json_escapar(texto))
    end
    return string.format(
        '{"script": "%s", "version": "%s", "ok": %s, "mensaje": "%s",'
        .. ' "cuando": %d%s}',
        NOMBRE_SCRIPT, json_escapar(VERSION),
        tostring(ok and true or false), json_escapar(mensaje), os.time(), extra)
end

local function guardar_resultado(ok, mensaje)
    local carpeta, sep = carpeta_compartida()
    escribir_archivo(carpeta .. sep .. "ultimo_resultado.txt",
                     table.concat(_salida, "\n"))
    escribir_archivo(carpeta .. sep .. "ultimo_resultado.json",
                     json_resultado(ok, mensaje))
end

-- Lo ultimo del registro, recortado, para el reporte sin io (como el de
-- CineCaptions_DetectarVideo).
local function texto_para_reporte()
    local inicio = math.max(1, #_salida - 24)
    local cola = {}
    for i = inicio, #_salida do
        cola[#cola + 1] = _salida[i]
    end
    local texto = table.concat(cola, "\n")
    if #texto > 1300 then texto = texto:sub(-1300) end
    return texto
end

local function lista_api(t)
    local salida = {}
    if type(t) ~= "table" then return salida end
    for _, v in ipairs(t) do
        if type(v) == "table" or type(v) == "userdata" then
            salida[#salida + 1] = v
        end
    end
    return salida
end

-- Conseguir 'resolve' validado (copia de CineCaptions_InsertarSFX.lua; ver alli la
-- explicacion de cada candidato y del orden).
local function obtener_resolve()
    local candidatos = {}
    local diag = {}

    if ENTREGA_PUENTE ~= nil and ENTREGA_PUENTE.resolve ~= nil then
        candidatos[#candidatos + 1] =
            { nombre = "entrega del Puente",
              traer = function() return ENTREGA_PUENTE.resolve end }
    end

    local ok_pu, pu = pcall(function() return CINECAPTIONS_RESOLVE_DEL_PUENTE end)
    if ok_pu and pu ~= nil then
        candidatos[#candidatos + 1] =
            { nombre = "resolve del Puente", traer = function() return pu end }
    end

    local ok_g, g = pcall(function() return resolve end)
    if not ok_g then g = nil end
    if g ~= nil then
        candidatos[#candidatos + 1] =
            { nombre = "resolve", traer = function() return g end }
    end

    local g2 = type(_G) == "table" and rawget(_G, "resolve") or nil
    if g2 ~= nil and g2 ~= g then
        candidatos[#candidatos + 1] =
            { nombre = "rawget(resolve)", traer = function() return g2 end }
    end

    local ok_R, R = pcall(function() return Resolve end)
    if ok_R and type(R) == "function" then
        candidatos[#candidatos + 1] =
            { nombre = "Resolve()", traer = function() return R() end }
    end

    local ok_b, b = pcall(function() return bmd end)
    if ok_b and type(b) == "table" and b.scriptapp ~= nil then
        candidatos[#candidatos + 1] =
            { nombre = "bmd.scriptapp",
              traer = function() return b.scriptapp("Resolve") end }
    end

    local _, mt = pcall(function() return getmetatable(_G) end)
    diag[#diag + 1] = "_G con metatable: " .. tostring(mt ~= nil)
    diag[#diag + 1] = "resolve normal: " .. type(g) .. ", rawget: " .. type(g2)

    local rechazados = 0
    for _, c in ipairs(candidatos) do
        local ok, r = pcall(c.traer)
        if ok and r ~= nil then
            local ok2, pm = pcall(function() return r:GetProjectManager() end)
            if ok2 and pm ~= nil then
                return r, table.concat(diag, " | "), 0
            end
            rechazados = rechazados + 1
            diag[#diag + 1] = c.nombre .. ": sin ProjectManager"
        else
            diag[#diag + 1] = c.nombre .. ": no devolvio nada"
        end
    end

    diag[#diag + 1] = string.format("candidatos: %d, rechazados: %d",
                                    #candidatos, rechazados)
    return nil, table.concat(diag, " | "), rechazados
end

local function leer_archivo(ruta)
    if SIN_IO then return nil end
    local f = io.open(ruta, "r")
    if not f then return nil end
    local contenido = f:read("*a")
    f:close()
    return contenido
end

-- Parser JSON minimo en Lua puro (copia verificada de CineCaptions_InsertarSFX).
local function parsear_json(texto)
    local pos = 1
    local parsear_valor
    local function saltar()
        while pos <= #texto and texto:sub(pos, pos):match("%s") do pos = pos + 1 end
    end
    local function p_string()
        pos = pos + 1
        local ini, partes = pos, {}
        while pos <= #texto do
            local c = texto:sub(pos, pos)
            if c == '"' then
                table.insert(partes, texto:sub(ini, pos - 1)); pos = pos + 1
                return table.concat(partes)
            elseif c == "\\" then
                table.insert(partes, texto:sub(ini, pos - 1))
                pos = pos + 1
                table.insert(partes, texto:sub(pos, pos))
                pos = pos + 1; ini = pos
            else
                pos = pos + 1
            end
        end
        error("string sin cerrar")
    end
    local function p_numero()
        local ini = pos
        while pos <= #texto and texto:sub(pos, pos):match("[%d%.%-%+eE]") do pos = pos + 1 end
        return tonumber(texto:sub(ini, pos - 1))
    end
    local function p_objeto()
        pos = pos + 1; local obj = {}; saltar()
        if texto:sub(pos, pos) == "}" then pos = pos + 1; return obj end
        while true do
            saltar(); local clave = p_string(); saltar()
            pos = pos + 1; saltar()  -- ':'
            obj[clave] = parsear_valor(); saltar()
            local c = texto:sub(pos, pos)
            if c == "," then pos = pos + 1
            elseif c == "}" then pos = pos + 1; break
            else error("objeto mal formado") end
        end
        return obj
    end
    local function p_array()
        pos = pos + 1; local arr = {}; saltar()
        if texto:sub(pos, pos) == "]" then pos = pos + 1; return arr end
        while true do
            saltar(); table.insert(arr, parsear_valor()); saltar()
            local c = texto:sub(pos, pos)
            if c == "," then pos = pos + 1
            elseif c == "]" then pos = pos + 1; break
            else error("array mal formado") end
        end
        return arr
    end
    parsear_valor = function()
        saltar(); local c = texto:sub(pos, pos)
        if c == '"' then return p_string()
        elseif c == "{" then return p_objeto()
        elseif c == "[" then return p_array()
        elseif texto:sub(pos, pos + 3) == "true" then pos = pos + 4; return true
        elseif texto:sub(pos, pos + 4) == "false" then pos = pos + 5; return false
        elseif texto:sub(pos, pos + 3) == "null" then pos = pos + 4; return nil
        else return p_numero() end
    end
    saltar(); return parsear_valor()
end

local function archivo_existe(ruta)
    if SIN_IO then
        -- Free 21.1: bmd.fileexists si esta en el menu (medido); sin el, se
        -- da por existente y decide ImportMedia (que falla bien).
        local ok, hay = pcall(function() return bmd.fileexists(ruta) end)
        if ok and type(hay) == "boolean" then return hay end
        return true
    end
    local f = io.open(ruta, "r")
    if f then f:close(); return true end
    return false
end

-- La orden: con io el .json de siempre; sin io, su sidecar "<ruta>.lua"
-- (sidecar_lua.escribir_par en la app). Devuelve (tabla, habia_orden).
local function cargar_tabla(ruta)
    if not SIN_IO then
        local txt = leer_archivo(ruta)
        if not txt then return nil, false end
        local ok, t = pcall(parsear_json, txt)
        return (ok and type(t) == "table") and t or nil, true
    end
    local chunk = loadfile(ruta .. ".lua")
    if not chunk then return nil, false end
    local ok, t = pcall(chunk)
    return (ok and type(t) == "table") and t or nil, true
end

local function nombre_de_archivo(ruta)
    return ruta:match("[^/\\]+$") or ruta
end

local function fail(msg)
    print("[SFX Marcadores] ERROR: " .. msg)
    guardar_resultado(false, msg)
    error(msg, 0)
end

-- ---------------------------------------------------------------------
-- Timeline: hueco libre (copias de CineCaptions_InsertarSFX)
-- ---------------------------------------------------------------------
local function hay_hueco(timeline, indice, frame_inicio, duracion)
    local items = timeline:GetItemListInTrack("audio", indice) or {}
    local fin = frame_inicio + duracion
    local margen = 2
    for _, it in ipairs(lista_api(items)) do
        local a = tonumber(it:GetStart())
        local b = tonumber(it:GetEnd())
        if a and b then
            if not (b - margen <= frame_inicio + margen) then
                if not (a + margen >= fin - margen) then
                    return false
                end
            end
        end
    end
    return true
end

local function es_pista_nuestra(nombre)
    nombre = tostring(nombre or ""):gsub("^%s+", ""):gsub("%s+$", ""):upper()
    return PISTAS_NUESTRAS[nombre] == true
end

local function nombre_de_pista(timeline, i)
    local nombre = ""
    pcall(function() nombre = timeline:GetTrackName("audio", i) or "" end)
    return nombre
end

local function pista_bloqueada(timeline, i)
    local ok, r = pcall(function() return timeline:GetIsTrackLocked("audio", i) end)
    return ok and r == true
end

-- v3.1.9: SOLO pistas nuestras. Hasta la v3.1.8 valia cualquier pista de
-- audio libre -tambien las del usuario- y un efecto puesto ahi ya no se
-- podia reemplazar (el reemplazo solo mira pistas nuestras, a proposito).
local function buscar_pista_vacia(timeline, frame_inicio, duracion)
    local cantidad = timeline:GetTrackCount("audio")
    for i = 1, cantidad do
        if es_pista_nuestra(nombre_de_pista(timeline, i))
                and not pista_bloqueada(timeline, i)
                and hay_hueco(timeline, i, frame_inicio, duracion) then
            return i
        end
    end
    return nil
end

-- Los efectos NUESTROS que suenan en 'frame' (las guardas de
-- item_bajo_el_cabezal de CineCaptions_SfxReemplazar, pero TODOS: re-colocar con la
-- v3.1.8 apilaba uno por corrida). Devuelve ({ {item, pista} }, intocables):
-- los de una pista con candado se cuentan y no se tocan (regla v3.0.3).
-- 'recien' ("pista:inicio") son los que ESTA corrida acaba de poner: con dos
-- marcadores mas juntos que un efecto, el segundo borraba el del primero.
local function efectos_nuestros_en(timeline, frame, fps, recien)
    local max_frames = math.floor(DURACION_MAXIMA_SFX_SEGUNDOS * fps)
    local efectos, intocables = {}, 0
    local cantidad = tonumber(timeline:GetTrackCount("audio")) or 0
    for i = 1, cantidad do
        if es_pista_nuestra(nombre_de_pista(timeline, i)) then
            local bloqueada = pista_bloqueada(timeline, i)
            local items = timeline:GetItemListInTrack("audio", i) or {}
            for _, it in ipairs(lista_api(items)) do
                local a = tonumber(it:GetStart())
                local b = tonumber(it:GetEnd())
                if a and b and a <= frame and frame < b
                        and b - a <= max_frames
                        and not recien[i .. ":" .. math.floor(a)] then
                    if bloqueada then
                        intocables = intocables + 1
                    else
                        efectos[#efectos + 1] = { item = it, pista = i }
                    end
                end
            end
        end
    end
    return efectos, intocables
end

local function crear_pista_sfx(timeline)
    local antes = timeline:GetTrackCount("audio")
    local ok = timeline:AddTrack("audio", "stereo")
    if not ok then ok = timeline:AddTrack("audio") end
    if not ok then return nil end
    local nueva = timeline:GetTrackCount("audio")
    if nueva == antes then nueva = antes + 1 end
    pcall(function() timeline:SetTrackName("audio", nueva, NOMBRE_PISTA_NUEVA) end)
    return nueva
end

-- v3.3.0: se reusa un clip del Media Pool solo si es la MISMA RUTA, no el
-- mismo nombre. Por nombre, un clip que quedo desconectado (su archivo vivia
-- dentro del programa, en una carpeta que ya no existe: el .exe de un solo
-- archivo o un Mac abierto desde Descargas) se reusaba para siempre y cada
-- efecto nuevo nacia desconectado. Otro clip con el mismo nombre en otra
-- ruta no estorba: se importa el nuestro al lado.
local function ruta_comparable(ruta)
    local r = tostring(ruta or ""):gsub("\\", "/")
    if es_windows() then r = r:lower() end
    return r
end

local function importar_una_vez(media_pool, ruta_wav)
    local buscada = ruta_comparable(ruta_wav)
    local root = media_pool:GetRootFolder()

    local function buscar(folder)
        for _, clip in ipairs(lista_api(folder:GetClipList())) do
            local ok, ruta = pcall(function()
                return clip:GetClipProperty("File Path")
            end)
            if ok and type(ruta) == "string" and ruta ~= ""
                    and ruta_comparable(ruta) == buscada then
                return clip
            end
        end
        for _, sub in ipairs(lista_api(folder:GetSubFolderList())) do
            local r = buscar(sub)
            if r then return r end
        end
        return nil
    end

    local existente = buscar(root)
    if existente then return existente end

    local nuevos = media_pool:ImportMedia({ ruta_wav })
    if nuevos and nuevos[1] then return nuevos[1] end
    return nil
end

-- ---------------------------------------------------------------------
-- Main
-- ---------------------------------------------------------------------
local function main()
    local r, diag, rechazados = obtener_resolve()
    if r == nil then
        local motivo
        local bajo_puente = ENTREGA_PUENTE ~= nil
        pcall(function()
            bajo_puente = bajo_puente or CINECAPTIONS_BAJO_PUENTE == true
        end)
        if rechazados > 0 and bajo_puente then
            motivo = "La conexion con Resolve caduco. Vuelve a lanzar "
                     .. "CineCaptions_Puente (Area de trabajo > Scripts > Utility): "
                     .. "el nuevo releva al viejo solo, y despues repite."
        elseif rechazados > 0 then
            motivo = "Encontre Resolve pero no me respondio. Si no hay un "
                     .. "proyecto abierto, abrelo; si lo hay, relanza "
                     .. "CineCaptions_Puente."
        else
            motivo = "No pude conectar con Resolve. Corre este script desde "
                     .. "Area de trabajo > Scripts > Utility > CineCaptions_SfxMarcadores"
        end
        fail(motivo .. "  |  Diagnostico: " .. tostring(diag))
    end
    resolve = r

    print("[SFX Marcadores] version " .. VERSION)
    print("[SFX Marcadores] entrega del Puente: "
        .. (ENTREGA_PUENTE and "recibida" or "no (corrida manual o Puente viejo)"))

    local carpeta, sep = carpeta_compartida()
    local ruta_pendiente = carpeta .. sep .. "sfx_marcadores_pendiente.json"
    local ruta_hecho = carpeta .. sep .. "sfx_marcadores_pendiente.hecho.json"

    local pendiente, habia_orden = cargar_tabla(ruta_pendiente)
    if not habia_orden then
        fail("No hay ninguna orden de marcadores pendiente.\n"
             .. "  Esto se lanza desde el SFX Lab del programa (boton "
             .. "«SFX en marcadores…»), donde eliges que carpeta va con "
             .. "cada color de marcador. El programa deja la orden y "
             .. "corre esto solo.")
    end
    if type(pendiente) ~= "table" or type(pendiente.mapa) ~= "table" then
        fail("La orden de marcadores esta dañada.")
    end
    -- v3.1.9: una orden vieja sin estas claves = la conducta de siempre.
    local reemplazar = pendiente.reemplazar == true
    local solo_reemplazar = reemplazar and pendiente.solo_reemplazar == true
    -- v1.0.69: la app manda el analisis de la onda de cada archivo
    -- ({ruta: {pico, dur}} en SEGUNDOS — el fps solo se conoce aqui).
    -- Una orden vieja sin 'ondas' degrada a la conducta de siempre.
    local ondas = type(pendiente.ondas) == "table" and pendiente.ondas or {}

    local project = resolve:GetProjectManager():GetCurrentProject()
    if not project then fail("No hay proyecto abierto en Resolve.") end
    local timeline = project:GetCurrentTimeline()
    if not timeline then fail("No hay timeline activo.") end

    local fps = tonumber(timeline:GetSetting("timelineFrameRate")) or 30
    local start_frame = math.floor(tonumber(timeline:GetStartFrame()) or 0)

    local ok_m, crudos = pcall(function() return timeline:GetMarkers() end)
    if not ok_m or type(crudos) ~= "table" then
        fail("Tu Resolve no me dio los marcadores (GetMarkers).")
    end

    -- GetMarkers: { [frameId] = {color=..., name=...}, ... } con el
    -- frameId RELATIVO al inicio del timeline. pairs() a proposito (las
    -- claves son los frames, no una lista) y despues se ORDENA: el orden
    -- de pairs es aleatorio y la rotacion de sonidos debe seguir el
    -- orden REAL de los marcadores en el tiempo.
    local marcadores = {}
    for frame_id, m in pairs(crudos) do
        local f = tonumber(frame_id)
        if f ~= nil and type(m) == "table" then
            marcadores[#marcadores + 1] =
                { frame = math.floor(f), color = tostring(m.color or "") }
        end
    end
    table.sort(marcadores, function(a, b) return a.frame < b.frame end)

    if #marcadores == 0 then
        fail("El timeline no tiene marcadores. Ponlos con la tecla M "
             .. "(y su color, con el panel del marcador) y repite.")
    end
    print(string.format("  Timeline: %s  |  marcadores: %d",
                        timeline:GetName(), #marcadores))

    local media_pool = project:GetMediaPool()
    local colocados, fallidos = 0, 0
    local reemplazados, sin_efecto, bloqueados, con_mapa = 0, 0, 0, 0
    local recien = {}          -- "pista:inicio" de lo puesto en esta corrida
    local usados = {}          -- rotacion por color
    local sin_mapa = {}
    local sin_mapa_orden = {}

    for _, m in ipairs(marcadores) do
        local fuente = pendiente.mapa[m.color]
        local archivos = fuente and fuente.archivos or nil
        local frame_absoluto = start_frame + m.frame
        local previos, intocables = {}, 0
        if type(archivos) == "table" and #archivos > 0 and reemplazar then
            previos, intocables = efectos_nuestros_en(timeline,
                                                      frame_absoluto, fps,
                                                      recien)
        end
        if type(archivos) ~= "table" or #archivos == 0 then
            if m.color ~= "" and not sin_mapa[m.color] then
                sin_mapa[m.color] = true
                sin_mapa_orden[#sin_mapa_orden + 1] = m.color
            end
        elseif intocables > 0 then
            -- Un efecto nuestro en una pista con CANDADO: se queda (v3.0.3)
            -- y no se apila otro encima.
            con_mapa = con_mapa + 1
            bloqueados = bloqueados + 1
            print(string.format("  %s @ %d: su efecto esta en una pista "
                .. "bloqueada; no lo toco ni pongo otro.", m.color, m.frame))
        elseif solo_reemplazar and #previos == 0 then
            con_mapa = con_mapa + 1
            sin_efecto = sin_efecto + 1
        else
            con_mapa = con_mapa + 1
            local k = usados[m.color] or 0
            local ruta = archivos[(k % #archivos) + 1]
            usados[m.color] = k + 1

            if not archivo_existe(ruta) then
                print(string.format("  Aviso: no encuentro '%s' (marcador "
                    .. "%s en %d); lo salto.", tostring(ruta), m.color,
                    m.frame))
                fallidos = fallidos + 1
            else
                local item = importar_una_vez(media_pool, ruta)
                if not item then
                    print(string.format("  Aviso: no pude importar '%s'; "
                        .. "salto ese marcador.", nombre_de_archivo(ruta)))
                    fallidos = fallidos + 1
                else
                    local info_onda = ondas[ruta]
                    if type(info_onda) ~= "table" then info_onda = nil end
                    local duracion = frames_de_audio(item, fps)
                    if duracion < 1 then
                        -- v1.0.69: el respaldo era 0.5 s FIJO y truncaba
                        -- los mp3 recien importados (Frames aun vacio) —
                        -- el «se corta antes de que suene» del reporte.
                        -- La duracion medida por la app manda.
                        local dur_s = info_onda
                            and tonumber(info_onda.dur) or 0
                        if dur_s and dur_s > 0 then
                            duracion = math.max(1,
                                math.floor(dur_s * fps + 0.5))
                        else
                            duracion = math.max(1,
                                math.floor(0.5 * fps + 0.5))
                        end
                    end

                    -- v1.0.69 (reporte literal: «donde esta mas alto
                    -- ponga junto en el marcador... quiza va a tener que
                    -- iniciar un poco antes»): el PICO de la onda cae en
                    -- el marcador — el clip arranca antes. Clamp doble:
                    -- dentro del clip y nunca antes del inicio del
                    -- timeline. Sin 'ondas': la conducta de siempre.
                    local desplaza = 0
                    if info_onda then
                        desplaza = math.floor((tonumber(info_onda.pico)
                                               or 0) * fps + 0.5)
                        if desplaza < 0 then desplaza = 0 end
                        if desplaza > duracion - 1 then
                            desplaza = duracion - 1
                        end
                    end
                    local record = frame_absoluto - desplaza
                    if record < start_frame then record = start_frame end

                    -- Reemplazar: el sonido nuevo YA esta importado; recien
                    -- ahora se quita lo viejo (import fallido = timeline
                    -- intacto, la regla de CineCaptions_SfxReemplazar). Si Resolve
                    -- no deja quitarlo, no se apila un duplicado.
                    local indice, quitados = nil, true
                    for _, p in ipairs(previos) do
                        local ok_b, borrado = pcall(function()
                            return timeline:DeleteClips({ p.item })
                        end)
                        if not (ok_b and borrado) then quitados = false end
                    end
                    if #previos > 0 and quitados
                            and hay_hueco(timeline, previos[1].pista,
                                          record, duracion) then
                        indice = previos[1].pista
                    end
                    if quitados and indice == nil then
                        indice = buscar_pista_vacia(timeline, record, duracion)
                    end
                    if quitados and indice == nil then
                        indice = crear_pista_sfx(timeline)
                    end
                    local puestos = nil
                    if not quitados then
                        bloqueados = bloqueados + 1
                        print(string.format("  %s @ %d: Resolve no me dejo "
                            .. "quitar su efecto; no pongo otro encima.",
                            m.color, m.frame))
                    elseif indice then
                        puestos = media_pool:AppendToTimeline({ {
                            mediaPoolItem = item,
                            startFrame = 0,
                            endFrame = duracion - 1,
                            trackIndex = indice,
                            mediaType = 2,
                            recordFrame = record,
                        } })
                    end
                    if not quitados then
                        -- ya dicho arriba
                    elseif puestos and puestos[1] then
                        recien[indice .. ":" .. math.floor(record)] = true
                        local extra = ""
                        if desplaza > 0 then
                            extra = string.format(", pico -%df", desplaza)
                        end
                        if #previos > 0 then
                            reemplazados = reemplazados + 1
                            extra = extra .. ", reemplaza"
                        else
                            colocados = colocados + 1
                        end
                        print(string.format("  %s @ %d -> '%s' (A%d%s)",
                            m.color, m.frame, nombre_de_archivo(ruta),
                            indice, extra))
                    else
                        fallidos = fallidos + 1
                        print(string.format("  Aviso: no pude colocar '%s' "
                            .. "en el frame %d.%s", nombre_de_archivo(ruta),
                            record, #previos > 0 and " Ya habia quitado el "
                            .. "efecto viejo: un Ctrl+Z en Resolve lo "
                            .. "recupera." or ""))
                    end
                end
            end
        end
    end

    -- En el modo Reemplazar del Lab (solo_reemplazar) la orden trae UN
    -- color a proposito: los demas no son «colores sin carpeta».
    if #sin_mapa_orden > 0 and not solo_reemplazar then
        print("  Colores sin carpeta asignada (se saltan): "
              .. table.concat(sin_mapa_orden, ", ")
              .. ". Se configuran en el SFX Lab, boton «SFX en marcadores…».")
    end
    if sin_efecto > 0 then
        print(string.format("  %d marcador(es) sin un efecto del programa "
            .. "debajo: los dejo como estan.", sin_efecto))
    end

    if colocados + reemplazados == 0 then
        if solo_reemplazar then
            fail(string.format("No reemplace nada: de %d marcador(es) de ese "
                .. "color, ninguno tenia debajo un efecto del programa (busco "
                .. "en las pistas SFX, SFX-Modificado y SFX-Marcadores; tus "
                .. "clips no los toco).", con_mapa))
        end
        fail(string.format("No coloque ningun sonido (%d marcadores, %d "
            .. "fallidos, %d bloqueados). Revisa el mapa de colores en el "
            .. "programa.", #marcadores, fallidos, bloqueados))
    end

    -- Sin io (Free 21.1) la orden la retira la app al ver el exito.
    if not SIN_IO then
        local out = io.open(ruta_hecho, "w")
        if out then
            out:write(string.format(
                '{"colocados": %d, "reemplazados": %d, "marcadores": %d,'
                .. ' "insertado_en": %d}',
                colocados, reemplazados, #marcadores, os.time()))
            out:close()
        end
        os.remove(ruta_pendiente)
    end

    if reemplazados > 0 then
        print(string.format("  LISTO: %d reemplazado(s) y %d sonido(s) "
            .. "nuevos en %d marcadores.", reemplazados, colocados,
            #marcadores))
    else
        print(string.format("  LISTO: %d sonido(s) colocados en %d "
            .. "marcadores.", colocados, #marcadores))
    end
end

local ok, err = pcall(main)
if not ok then
    print("[SFX Marcadores] termino con error: " .. tostring(err))
    guardar_resultado(false, tostring(err))
else
    guardar_resultado(true, "")
end

-- No dejar el wrapper de print puesto (el Puente comparte estado de Lua).
print = _print_original

-- Free 21.1, sin io (v3.1.9): el resultado viaja por el registro de Resolve
-- (ver el epilogo de CineCaptions_Subtitulos.lua). Bajo el Puente se DEVUELVE (el
-- Puente lo relata); a mano, un error() sin capturar lo deja en
-- ResolveDebug.txt. Con io NO: bajo el Puente se leeria como fallo.
if SIN_IO then
    local reporte = "CINECAPTIONS_REPORTE|" .. json_resultado(ok, ok and "" or tostring(err),
                                                     texto_para_reporte())
    if ENTREGA_PUENTE ~= nil then return reporte end
    error(reporte, 0)
end

-- Un script que falla tiene que fallar hacia afuera (el pcall(dofile) del
-- Puente daria el trabajo por bueno).
if not ok then
    error(err, 0)
end
