-- CineCaptions · By Cinema Productions
-- 2_recursos/resolve_scripts/CineCaptions_SfxReemplazar.lua — reemplaza el efecto bajo el cabezal (Resolve Free).
--[[
CineCaptions_SfxReemplazar.lua
---------------------
Sustituye el efecto de sonido que esta BAJO EL CABEZAL por el sonido que
el usuario eligio en el SFX Lab (modo «Reemplazar», v1.0.62 — el flujo
de SickSFX que pidio el usuario: aparcas el cabezal sobre un clip y picas el
sonido nuevo).

La app deja la orden resuelta en
    ~/DaVinciSubtitles/sfx_reemplazo_pendiente.json   ({"wav": ruta})
(el patron de sfx_pendiente.json: el 'datos' del job del Puente NO llega
al Lua, el input real viaja por archivo propio). Que hace:
  1) lee la orden (sin orden: explica de donde sale)
  2) localiza el item de audio bajo el cabezal SOLO en pistas nuestras
     (SFX / SFX-Modificado / SFX-Marcadores) y SOLO si dura menos de
     DURACION_MAXIMA_SFX_SEGUNDOS — la regla suprema del producto es no
     destruir trabajo del usuario: un clip largo o en otra pista es, con
     altisima probabilidad, material suyo y NO SE TOCA (se dice)
  3) importa el sonido nuevo ANTES de borrar nada (si el import falla,
     el timeline queda intacto)
  4) borra el viejo y coloca el nuevo en el MISMO frame y MISMA pista
  5) borra la orden al terminar bien: correr dos veces no duplica

Version en Lua para Resolve FREE (el Puente la corre con dofile); la
gemela de Studio es "CineCaptions - SFX Reemplazar.py".
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

local VERSION = "5.4.42 (sfx reemplazar)"

-- La ENTREGA del Puente (v1.0.43): ver CineCaptions_InsertarSFX.lua.
local ENTREGA_PUENTE = ({...})[1]
if type(ENTREGA_PUENTE) ~= "table" then ENTREGA_PUENTE = nil end

-- Pistas que el producto considera SUYAS (comparadas en mayusculas y
-- sin espacios). Fuera de ellas no se reemplaza NADA.
local PISTAS_NUESTRAS = {
    ["SFX"] = true, ["SFX-MODIFICADO"] = true, ["SFX-MARCADORES"] = true,
}

-- Un efecto nuestro nunca dura mas que esto (misma constante que los
-- gemelos de subtitulos): un clip mas largo es, con altisima
-- probabilidad, contenido del usuario. Sin duracion confirmable,
-- tampoco se arriesga.
local DURACION_MAXIMA_SFX_SEGUNDOS = 20

-- Free 21.1 capo io en el menu de Scripts (medido el 16-09): sin io no se
-- escribe nada, la orden se lee de su sidecar .lua y el resultado viaja por
-- el registro de Resolve (ver el epilogo). Con io, todo como siempre (v3.1.9).
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

local NOMBRE_SCRIPT = "CineCaptions_SfxReemplazar"
local _salida = {}
local _print_original = print

local function escribir_archivo(ruta, texto)
    if SIN_IO then return false end
    local f = io.open(ruta, "w")
    if not f then return false end
    f:write(texto); f:close(); return true
end

local function json_escapar(s)
    s = tostring(s or "")
    s = s:gsub("\\", "\\\\"):gsub('"', '\\"')
    s = s:gsub("\r", " "):gsub("\n", "\\n"):gsub("\t", " ")
    return s
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
    print("[SFX Reemplazar] ERROR: " .. msg)
    guardar_resultado(false, msg)
    error(msg, 0)
end

-- ---------------------------------------------------------------------
-- Timeline: cabezal e item nuestro debajo
-- ---------------------------------------------------------------------
local function tc_a_frames(tc, fps)
    -- Acepta ';' (drop-frame): con ':' fijo el parseo daba 0 en silencio
    -- y el cabezal "estaba" al inicio del timeline (leccion v1.0.62).
    local h, m, s, f = tostring(tc):match("(%d+)[:;](%d+)[:;](%d+)[:;](%d+)")
    if not h then return 0 end
    return math.floor(((h * 3600 + m * 60 + s) * fps) + f + 0.5)
end

local function es_pista_nuestra(nombre)
    nombre = tostring(nombre or ""):gsub("^%s+", ""):gsub("%s+$", ""):upper()
    return PISTAS_NUESTRAS[nombre] == true
end

local function item_bajo_el_cabezal(timeline, frame, fps)
    -- (item, pista, inicio, descartados): el SFX nuestro bajo el
    -- cabezal, o nil. Recorre SOLO las pistas nuestras; un clip largo o
    -- sin duracion confirmable se descarta Y SE DICE.
    local max_frames = math.floor(DURACION_MAXIMA_SFX_SEGUNDOS * fps)
    local descartados = {}
    local cantidad = tonumber(timeline:GetTrackCount("audio")) or 0
    for i = 1, cantidad do
        local nombre = ""
        pcall(function() nombre = timeline:GetTrackName("audio", i) or "" end)
        if es_pista_nuestra(nombre) then
            local items = timeline:GetItemListInTrack("audio", i) or {}
            for _, it in ipairs(lista_api(items)) do
                local a = tonumber(it:GetStart())
                local b = tonumber(it:GetEnd())
                if a and b and a <= frame and frame < b then
                    if b - a > max_frames then
                        descartados[#descartados + 1] = string.format(
                            "%s (clip de %.1f s)", tostring(nombre),
                            (b - a) / fps)
                    else
                        return it, i, math.floor(a), descartados
                    end
                end
            end
        end
    end
    return nil, nil, nil, descartados
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
                     .. "Area de trabajo > Scripts > Utility > CineCaptions_SfxReemplazar"
        end
        fail(motivo .. "  |  Diagnostico: " .. tostring(diag))
    end
    resolve = r

    print("[SFX Reemplazar] version " .. VERSION)
    print("[SFX Reemplazar] entrega del Puente: "
        .. (ENTREGA_PUENTE and "recibida" or "no (corrida manual o Puente viejo)"))

    local carpeta, sep = carpeta_compartida()
    local ruta_pendiente = carpeta .. sep .. "sfx_reemplazo_pendiente.json"
    local ruta_hecho = carpeta .. sep .. "sfx_reemplazo_pendiente.hecho.json"

    local pendiente, habia_orden = cargar_tabla(ruta_pendiente)
    if not habia_orden then
        fail("No hay ninguna orden de reemplazo pendiente.\n"
             .. "  Esto se lanza desde el SFX Lab del programa: activa el "
             .. "modo «Reemplazar», aparca el cabezal sobre el efecto y "
             .. "elige el sonido nuevo.")
    end

    if type(pendiente) ~= "table" or type(pendiente.wav) ~= "string" then
        fail("La orden de reemplazo esta dañada.")
    end
    local wav = pendiente.wav
    if not archivo_existe(wav) then
        fail("No encuentro el sonido nuevo:\n  " .. wav)
    end

    local project = resolve:GetProjectManager():GetCurrentProject()
    if not project then fail("No hay proyecto abierto en Resolve.") end
    local timeline = project:GetCurrentTimeline()
    if not timeline then fail("No hay timeline activo.") end

    local fps = tonumber(timeline:GetSetting("timelineFrameRate")) or 30
    local tc_actual = timeline:GetCurrentTimecode() or "01:00:00:00"
    local tc_inicio = "01:00:00:00"
    local ok_i, r_i = pcall(function() return timeline:GetStartTimecode() end)
    if ok_i and r_i then tc_inicio = r_i end
    local start_frame = math.floor(tonumber(timeline:GetStartFrame()) or 0)
    local delta = tc_a_frames(tc_actual, fps) - tc_a_frames(tc_inicio, fps)
    if delta < 0 then delta = 0 end
    local frame = start_frame + delta
    print(string.format("  Timeline: %s  |  cabezal: %s (frame %d)",
                        timeline:GetName(), tostring(tc_actual), frame))

    local item, pista, inicio_viejo, descartados =
        item_bajo_el_cabezal(timeline, frame, fps)
    if item == nil then
        local detalle = ""
        if #descartados > 0 then
            detalle = "\n  Bajo el cabezal hay: "
                .. table.concat(descartados, "; ")
                .. " — demasiado largo para ser un efecto nuestro, no lo "
                .. "toco."
        end
        fail("No encuentro un efecto NUESTRO bajo el cabezal (busco solo "
             .. "en pistas llamadas SFX, SFX-Modificado o SFX-Marcadores "
             .. "y clips de menos de 20 s — tus clips no los toco)."
             .. detalle
             .. "\n  Aparca el cabezal SOBRE el efecto a sustituir y "
             .. "repite.")
    end

    local nombre_viejo = "?"
    pcall(function() nombre_viejo = item:GetName() end)

    -- Importar ANTES de borrar: si el import falla, el timeline queda
    -- exactamente como estaba.
    local media_pool = project:GetMediaPool()
    local nuevo = importar_una_vez(media_pool, wav)
    if not nuevo then
        fail("No pude importar '" .. nombre_de_archivo(wav)
             .. "' al Media Pool; no toco el timeline.")
    end

    local duracion = frames_de_audio(nuevo, fps)
    if duracion < 1 then
        duracion = math.max(1, math.floor(0.5 * fps + 0.5))
    end

    local ok_b, borrado = pcall(function()
        return timeline:DeleteClips({ item })
    end)
    if not ok_b or not borrado then
        fail("Resolve no me dejo quitar el efecto viejo; no coloco nada.")
    end

    local puestos = media_pool:AppendToTimeline({ {
        mediaPoolItem = nuevo,
        startFrame = 0,
        endFrame = duracion - 1,
        trackIndex = pista,
        mediaType = 2,
        recordFrame = inicio_viejo,
    } })
    -- Una tabla vacia es VERDADERA en Lua: hay que mirar puestos[1].
    if not (puestos and puestos[1]) then
        fail("Quite el efecto viejo pero no pude colocar el nuevo. "
             .. "Un Ctrl+Z en Resolve recupera el viejo; luego repite.")
    end

    -- Sin io (Free 21.1) la orden la retira la app al ver el exito.
    if not SIN_IO then
        local out = io.open(ruta_hecho, "w")
        if out then
            out:write(string.format(
                '{"reemplazado": "%s", "por": "%s", "pista": %d,'
                .. ' "insertado_en": %d}',
                json_escapar(nombre_viejo), json_escapar(nombre_de_archivo(wav)),
                pista, os.time()))
            out:close()
        end
        os.remove(ruta_pendiente)
    end

    print(string.format("  LISTO: '%s' -> '%s' (pista A%d, frame %d).",
                        tostring(nombre_viejo), nombre_de_archivo(wav),
                        pista, inicio_viejo))
end

local ok, err = pcall(main)
if not ok then
    print("[SFX Reemplazar] termino con error: " .. tostring(err))
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
