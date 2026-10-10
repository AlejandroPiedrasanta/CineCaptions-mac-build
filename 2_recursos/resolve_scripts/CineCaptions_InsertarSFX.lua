-- CineCaptions · By Cinema Productions
-- 2_recursos/resolve_scripts/CineCaptions_InsertarSFX.lua — importa un sonido y lo coloca en el cabezal (Resolve Free).
--[[
CineCaptions_InsertarSFX.lua
-------------------
Version en Lua de "CineCaptions - Insertar SFX.py".

Corre DENTRO de Resolve (Area de trabajo > Scripts > Utility). Es la version
para Resolve FREE, que trae Lua incorporado pero puede no tener Python del
sistema (sin Python, Resolve no lista ni corre los .py del menu).

Hace lo mismo que el .py:
  1) lee la orden en ~/DaVinciSubtitles/sfx_pendiente.json
  2) importa ese .wav al Media Pool (una sola vez)
  3) busca la primera pista de audio vacia en el playhead (o crea una)
  4) coloca el clip en el playhead con su duracion natural
  5) borra la orden al terminar bien

La API de Resolve es la misma que en Python; solo cambia la sintaxis
(metodos con ':', tablas con '{}', indices desde 1).
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

local VERSION = "5.4.27 (insertar SFX)"

-- La ENTREGA del Puente (v1.0.43): el resolve validado llega como
-- argumento del chunk, porque las globales del Puente NO cruzan el
-- dofile en el Lua de Resolve (entornos aislados por script; medido el
-- 01-09 con el diagnostico del cliente: candidatos: 3 y ni rastro del
-- prestamo, con el Puente latiendo al lado). Lanzado desde el menu no
-- llegan argumentos y esto queda en nil.
local ENTREGA_PUENTE = ({...})[1]
if type(ENTREGA_PUENTE) ~= "table" then ENTREGA_PUENTE = nil end
local NOMBRE_PISTA_NUEVA = "SFX-Modificado"

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

-- ---------------------------------------------------------------------
-- Registro en disco (ver la explicacion larga en CineCaptions_Subtitulos.lua)
-- ---------------------------------------------------------------------
-- Sin esto, todo lo que informa el script va solo a la consola de Resolve
-- y el usuario que no la tiene abierta ve "no pasa nada".
local NOMBRE_SCRIPT = "CineCaptions_InsertarSFX"
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

-- Recorrer una lista devuelta por la API de Resolve.
-- Ver la explicacion larga en CineCaptions_Subtitulos.lua: esas listas traen una
-- clave extra con el conteo, y pairs() la entregaba como un elemento mas
-- (un numero), reventando con "attempt to index a number value".
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

-- Conseguir el objeto 'resolve' de forma fiable.
--
-- Al correr el script desde el MENU, Resolve inyecta el global 'resolve'.
-- Pero cuando lo ejecuta el Puente con dofile, ese global puede llegar sin
-- los metodos: el script pasaba el 'if resolve == nil' y reventaba despues
-- con "attempt to call method 'GetProjectManager' (a nil value)". Ese es el
-- sintoma de "a mano avanza, desde el boton no".
--
-- Se prueban las tres vias documentadas y se VALIDA cada una llamando de
-- verdad a GetProjectManager antes de darla por buena.
--
-- Devuelve (resolve, diagnostico, rechazados):
--   resolve      el objeto ya validado, o nil
--   diagnostico  texto corto con lo que se encontro y que se descarto
--   rechazados   cuantos candidatos existian pero no pasaron la validacion
local function obtener_resolve()
    local candidatos = {}
    local diag = {}

    -- OJO con rawget: es *raw*, o sea que salta el __index de _G. Si Resolve
    -- provee 'resolve'/'bmd' por metatable en vez de escribirlos en la tabla,
    -- rawget devuelve nil y el acceso normal no. Por eso el acceso normal va
    -- PRIMERO y rawget queda de respaldo: cubren casos distintos, y antes solo
    -- estaba rawget (de ahi el "No pude conectar con Resolve" con Resolve
    -- abierto delante).
    -- La entrega en mano del Puente (v1.0.43) va PRIMERO: sobrevive a un
    -- global 'resolve' pisado Y a los entornos aislados. Se valida abajo
    -- igual que todos: entregado no es de fiar.
    if ENTREGA_PUENTE ~= nil and ENTREGA_PUENTE.resolve ~= nil then
        candidatos[#candidatos + 1] =
            { nombre = "entrega del Puente",
              traer = function() return ENTREGA_PUENTE.resolve end }
    end

    -- El prestamo por GLOBAL (v1.0.31) queda de compatibilidad con un
    -- Puente viejo residente. Con Resolve aislando los entornos este
    -- candidato no llega a verse (por eso existe la entrega de arriba),
    -- pero quitarlo romperia justo la combinacion scripts-nuevos +
    -- Puente-viejo que mas aparece tras una actualizacion.
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
            { nombre = "bmd.scriptapp", traer = function() return b.scriptapp("Resolve") end }
    end

    -- El diagnostico viaja al usuario dentro de ultimo_resultado.txt. Sin el,
    -- "no habia nada" y "habia algo y lo rechace" dan el MISMO mensaje, y son
    -- problemas distintos con arreglos distintos: diagnosticarlo a ciegas
    -- costo una ronda entera con un cliente.
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

-- Parser JSON minimo en Lua puro (verificado). Alcanza para lo que dejan
-- nuestros manifiestos: objetos, arrays, strings, numeros, booleanos, null.
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
    print("[Insertar SFX] ERROR: " .. msg)
    guardar_resultado(false, msg)
    error(msg, 0)
end

-- ---------------------------------------------------------------------
-- Timeline: hueco en el playhead (traducido del .py)
-- ---------------------------------------------------------------------
local function tc_a_frames(tc, fps)
    -- v1.0.62: en un timeline DROP-FRAME el ultimo separador es ';'
    -- ('01:00:00;12') y el patron con ':' fijo devolvia 0 EN SILENCIO:
    -- el clip aterrizaba al inicio del timeline en vez del cabezal.
    local h, m, s, f = tc:match("(%d+)[:;](%d+)[:;](%d+)[:;](%d+)")
    if not h then return 0 end
    return math.floor(((h * 3600 + m * 60 + s) * fps) + f + 0.5)
end

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

local function buscar_pista_vacia(timeline, frame_inicio, duracion)
    local cantidad = timeline:GetTrackCount("audio")
    for i = 1, cantidad do
        local bloqueada = false
        local ok, r = pcall(function() return timeline:GetIsTrackLocked("audio", i) end)
        if ok and r then bloqueada = true end
        if not bloqueada and hay_hueco(timeline, i, frame_inicio, duracion) then
            return i
        end
    end
    return nil
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

-- ---------------------------------------------------------------------
-- Media Pool: importar sin duplicar
-- ---------------------------------------------------------------------
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
    -- OJO: NO se toca el global hasta tener algo valido. Antes esto era
    -- `resolve = obtener_resolve()` a secas, y como es una asignacion GLOBAL,
    -- al fallar escribia _G.resolve = nil y se cargaba el objeto para TODA la
    -- sesion de Resolve -el Puente incluido, que sigue residente-. El primer
    -- fallo envenenaba la sesion: a partir de ahi fallaba todo igual aunque la
    -- causa original fuera pasajera. Por eso reiniciar el programa no arreglaba
    -- nada y habia que cerrar Resolve entero.
    local r, diag, rechazados = obtener_resolve()
    if r == nil then
        -- Si Resolve estaba pero no respondio, mandar al usuario a correr el
        -- script que YA esta corriendo no ayuda: son dos problemas distintos.
        local motivo
        local bajo_puente = false
        -- La entrega es la señal fiable; la global queda de respaldo
        -- para un Puente viejo (y en la practica no cruza el dofile).
        bajo_puente = ENTREGA_PUENTE ~= nil
        pcall(function()
            bajo_puente = bajo_puente or CINECAPTIONS_BAJO_PUENTE == true
        end)
        if rechazados > 0 and bajo_puente then
            -- Corriendo bajo el Puente, "abre un proyecto" despista: el
            -- proyecto suele estar abierto y lo muerto es la conexion.
            -- Con el Puente >=1.0.29 llegar aqui es raro: el Puente ya no
            -- corre el script con su handle muerto (responde el consejo el
            -- mismo, sin ejecutar). Esto es un handle que caduco a MITAD
            -- del trabajo o un Puente viejo residente. El arreglo medido
            -- (01-09): relanzar el Puente da un handle fresco; cerrar
            -- Resolve entero es la escalada, no la primera opcion.
            motivo = "La conexion con Resolve caduco. Vuelve a lanzar "
                     .. "CineCaptions_Puente (Area de trabajo > Scripts > Utility): "
                     .. "el nuevo releva al viejo solo. Despues genera de "
                     .. "nuevo. Si sigue pasando, cierra DaVinci Resolve "
                     .. "por completo y abrelo otra vez."
        elseif rechazados > 0 then
            motivo = "Encontre Resolve pero no me respondio (GetProjectManager "
                     .. "vino vacio). Si no hay un proyecto abierto, abrelo. "
                     .. "Con el proyecto abierto, esto es la conexion muerta: "
                     .. "vuelve a lanzar CineCaptions_Puente (Area de trabajo > "
                     .. "Scripts > Utility) — el nuevo releva al viejo solo — "
                     .. "y genera de nuevo."
        else
            motivo = "No pude conectar con Resolve. Corre este script desde "
                     .. "Area de trabajo > Scripts > Utility > CineCaptions_InsertarSFX"
        end
        fail(motivo .. "  |  Diagnostico: " .. tostring(diag))
    end
    resolve = r

    print("[Insertar SFX] version " .. VERSION)
    print("[Insertar SFX] entrega del Puente: "
        .. (ENTREGA_PUENTE and "recibida" or "no (corrida manual o Puente viejo)"))

    local carpeta, sep = carpeta_compartida()
    local ruta_pendiente = carpeta .. sep .. "sfx_pendiente.json"
    local ruta_hecho = carpeta .. sep .. "sfx_pendiente.hecho.json"

    local pendiente, habia_orden = cargar_tabla(ruta_pendiente)
    if not habia_orden then
        -- Este script hace UNA cosa: insertar el sonido que dejaste elegido
        -- en el Estudio. Al usuario le resultaba confuso porque lo corria
        -- desde el menu esperando los efectos POR BLOQUE, que no pasan por
        -- aqui: los coloca CineCaptions_Subtitulos al generar. Se explica.
        fail("No hay ningun sonido pendiente.\n"
             .. "  Este script inserta UN sonido suelto: elegilo primero en el "
             .. "'Estudio de sonidos' y presiona 'Enviar a Resolve'.\n"
             .. "  Si lo que querias son los efectos POR BLOQUE, no hace falta "
             .. "correr nada a mano: marca 'Agregar efectos de sonido por "
             .. "bloque' en el programa y genera; se colocan junto con los "
             .. "subtitulos.")
    end

    if type(pendiente) ~= "table" then
        fail("La orden pendiente esta dañada.")
    end

    local wav = pendiente.video_path or pendiente.wav or ""
    if wav == "" or not archivo_existe(wav) then
        fail("No encuentro el WAV que la ventana dejo: " .. tostring(wav))
    end

    local project = resolve:GetProjectManager():GetCurrentProject()
    if not project then fail("No hay proyecto abierto en Resolve.") end
    local timeline = project:GetCurrentTimeline()
    if not timeline then fail("No hay timeline activo.") end

    local fps = tonumber(timeline:GetSetting("timelineFrameRate"))
    local tc_actual = timeline:GetCurrentTimecode() or "01:00:00:00"
    local tc_inicio = "01:00:00:00"
    local ok2, r2 = pcall(function() return timeline:GetStartTimecode() end)
    if ok2 and r2 then tc_inicio = r2 end
    local start_frame = math.floor(tonumber(timeline:GetStartFrame()) or 0)

    local delta = tc_a_frames(tc_actual, fps) - tc_a_frames(tc_inicio, fps)
    if delta < 0 then delta = 0 end
    local frame_absoluto = start_frame + delta

    print(string.format("  Timeline: %s  |  fps: %s", timeline:GetName(), tostring(fps)))
    print(string.format("  Playhead TC: %s  |  frame_absoluto: %d", tc_actual, frame_absoluto))
    print("  WAV: " .. wav)

    local media_pool = project:GetMediaPool()
    local item = importar_una_vez(media_pool, wav)
    if not item then fail("No pude importar el WAV al Media Pool.") end

    local duracion = frames_de_audio(item, fps)
    if duracion < 1 then duracion = math.max(1, math.floor(0.5 * fps + 0.5)) end

    local indice = buscar_pista_vacia(timeline, frame_absoluto, duracion)
    local creada = false
    if indice == nil then
        print("  Todas las pistas tienen algo en el playhead; creando '"
              .. NOMBRE_PISTA_NUEVA .. "'.")
        indice = crear_pista_sfx(timeline)
        creada = true
        if not indice then fail("No pude crear una pista de audio.") end
    else
        print("  Uso la pista vacia A" .. indice .. ".")
    end

    local clip_info = {
        mediaPoolItem = item,
        startFrame = 0,
        endFrame = duracion - 1,
        trackIndex = indice,
        mediaType = 2,           -- 2 = audio
        recordFrame = frame_absoluto,
    }
    local colocados = media_pool:AppendToTimeline({ clip_info })
    if not colocados then
        fail("Resolve no coloco el clip (posiblemente hay algo pisando el hueco).")
    end

    -- Al terminar bien: la orden ya no vale. Sin io (Free 21.1) la retira
    -- la app al ver el exito.
    if not SIN_IO then
        local out = io.open(ruta_hecho, "w")
        if out then
            out:write(string.format(
                '{"colocado_en_pista": %d, "pista_creada": %s, "insertado_en": %d}',
                indice, tostring(creada), os.time()))
            out:close()
        end
        os.remove(ruta_pendiente)
    end

    print(string.format("  LISTO: '%s' insertado en la pista A%d, frame %d.",
          nombre_de_archivo(wav), indice, frame_absoluto))
end

local ok, err = pcall(main)
if not ok then
    print("[Insertar SFX] termino con error: " .. tostring(err))
    guardar_resultado(false, tostring(err))
else
    guardar_resultado(true, "")
end

-- No dejar el wrapper de print puesto: el Puente corre estos scripts con
-- dofile dentro de SU propio estado de Lua, y print es global.
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

-- Y volver a lanzar el error.
--
-- Antes se atrapaba aca y no se relanzaba: el Puente ejecuta estos scripts
-- con pcall(dofile, ...), asi que al no salir ningun error daba el trabajo
-- por BUENO y la app anunciaba "ya quedaron puestos en tu timeline" con el
-- timeline vacio. Un script que falla tiene que fallar hacia afuera.
if not ok then
    error(err, 0)
end
