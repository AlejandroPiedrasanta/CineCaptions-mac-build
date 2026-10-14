-- CineCaptions · By Cinema Productions
-- 2_recursos/resolve_scripts/CineCaptions_ArmarVideo.lua — arma el proyecto y el timeline de un video soltado en CineCaptions (Resolve Free).
--[[
CineCaptions_ArmarVideo.lua
---------------------------
Version en Lua para Resolve FREE (el Puente la corre con dofile) de lo que en Studio hace el MCP (resolve_mcp.preparar_proyecto + crear_timeline_con_video):
crea un proyecto NUEVO «CineCaptions» (guardando y cerrando el que hubiera abierto), importa el video, arma un timeline con su orientacion y fps, comprueba
que su audio suena en A1 y reserva la pista FX-BROLL si hace falta. Sin esto, en Free los captions de un video soltado caian en el timeline que hubiera abierto.
]]

local VERSION = "5.5.5 (armar video)"

-- La ENTREGA del Puente: ver CineCaptions_InsertarSFX.lua.
local ENTREGA_PUENTE = ({...})[1]
if type(ENTREGA_PUENTE) ~= "table" then ENTREGA_PUENTE = nil end

-- Free 21.1 capo io en el menu de Scripts: sin io la orden se lee de su sidecar .lua y el resultado viaja por el registro de Resolve (ver el epilogo).
local SIN_IO = (io == nil)

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

local NOMBRE_SCRIPT = "CineCaptions_ArmarVideo"
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

local function lista_api_texto(t)
    local salida = {}
    if type(t) ~= "table" then return salida end
    for _, v in ipairs(t) do salida[#salida + 1] = tostring(v) end
    return salida
end

-- El reporte con un campo propio «armado» (lo que paso: proyecto, timeline, medidas, clips de V1): la app lo lee con resolve_bridge.ultimo_reporte.
local function reporte_con_armado(ok, mensaje, texto, armado_json)
    local base = json_resultado(ok, mensaje, texto)
    if armado_json ~= nil then base = base:sub(1, -2) .. ', "armado": ' .. armado_json .. "}" end
    return base
end

local function fail(msg)
    print("[ArmarVideo] ERROR: " .. msg)
    guardar_resultado(false, msg)
    error(msg, 0)
end

-- ---------------------------------------------------------------------
-- Gemela de resolve_mcp._PROYECTO + resolve_mcp._CREAR_TIMELINE (las de Studio, por el MCP): con el video soltado en CineCaptions, crea un proyecto NUEVO
-- («CineCaptions», numerado si ya existe; guarda y cierra el que hubiera abierto: nunca se pierde trabajo), le importa el video, arma un timeline con su orientacion
-- y fps, comprueba que el audio original suena en A1 y reserva la pista FX-BROLL si hace falta. La orden la deja la app en armar_video.json (sidecar .lua en Free).
-- Al final deja UNA linea «ARMADO {json}» con lo que paso, que la app lee del registro de Resolve.
-- ---------------------------------------------------------------------
local RESULTADO = nil

local function pausa(segundos)
    pcall(function() if bmd and bmd.wait then bmd.wait(segundos) end end)
end

local function nombres_de_proyectos(pm, prof, salida)
    for _, n in ipairs(lista_api_texto(pm:GetProjectListInCurrentFolder())) do salida[n] = true end
    if prof < 5 then
        for _, c in ipairs(lista_api_texto(pm:GetFolderListInCurrentFolder())) do
            if pm:OpenFolder(c) then
                nombres_de_proyectos(pm, prof + 1, salida)
                pm:GotoParentFolder()
            end
        end
    end
    return salida
end

-- v5.4.23: «descartar» = el proyecto VACIO que la app creo (pulsando «Crear proyecto» en el Organizador de proyectos de Resolve) solo para que el Puente pudiera arrancar: al crear el
-- definitivo se borra, para no dejar un proyecto vacio por cada video.
local function proyecto_vacio(p)
    local n = math.floor(tonumber(p:GetTimelineCount()) or 0)
    if n == 0 then return true end
    if n > 1 then return false end
    local tl = p:GetTimelineByIndex(1)
    if tl == nil then return true end
    for _, t in ipairs({ "video", "audio" }) do
        for i = 1, math.floor(tonumber(tl:GetTrackCount(t)) or 0) do
            local items = tl:GetItemListInTrack(t, i)
            if items ~= nil and next(items) ~= nil then return false end
        end
    end
    return true
end

local function proyecto_nuevo(pm, base, descartar)
    local p = pm:GetCurrentProject()
    local previo = p and p:GetName() or nil
    local vacio_previo = false
    if p ~= nil then pcall(function() vacio_previo = proyecto_vacio(p) end) end
    if p ~= nil then
        local sin_nada = (tostring(previo):sub(1, 16) == "Untitled Project") and (math.floor(tonumber(p:GetTimelineCount()) or 0) == 0)
        if not sin_nada then pcall(function() pm:SaveProject() end) end
        pcall(function() pm:CloseProject(p) end)
    end
    pm:GotoRootFolder()
    local existentes = nombres_de_proyectos(pm, 0, {})
    pm:GotoRootFolder()
    local nombre, k, nuevo = base, 2, nil
    for _ = 1, 8 do
        while existentes[nombre] do
            nombre = string.format("%s %d", base, k)
            k = k + 1
        end
        nuevo = pm:CreateProject(nombre)
        if nuevo then break end
        existentes[nombre] = true
    end
    if not nuevo and previo then pcall(function() pm:LoadProject(previo) end) end
    -- (por el nombre que paso la app, o por el prefijo CineCaptions_nuevo_ que ella misma le pone: sirve aunque la app se haya reiniciado entre medias)
    if nuevo and vacio_previo and previo ~= nil and previo ~= nombre and ((descartar ~= nil and descartar ~= "" and previo == descartar) or tostring(previo):sub(1, 18) == "CineCaptions_nuevo") then
        local borrado = false
        pcall(function() borrado = pm:DeleteProject(previo) and true or false end)
        print("Proyecto vacio de arranque «" .. tostring(previo) .. "»: " .. (borrado and "borrado" or "no se pudo borrar"))
    end
    local q = pm:GetCurrentProject()
    pcall(function() resolve:OpenPage("edit") end)
    return q, nuevo ~= nil
end

local function main()
    local r, diag, rechazados = obtener_resolve()
    if r == nil then
        local motivo
        if rechazados > 0 then
            motivo = "Encontre Resolve pero no me respondio. Si no hay un proyecto abierto, abrelo; si lo hay, relanza CineCaptions_Puente (Area de trabajo > Scripts > CineCaptions_Puente)."
        else
            motivo = "No pude conectar con Resolve. Corre este script desde Area de trabajo > Scripts > CineCaptions_ArmarVideo"
        end
        fail(motivo .. "  |  Diagnostico: " .. tostring(diag))
    end
    resolve = r
    print("[ArmarVideo] version " .. VERSION)
    print("[ArmarVideo] entrega del Puente: " .. (ENTREGA_PUENTE and "recibida" or "no (corrida manual o Puente viejo)"))

    local carpeta, sep = carpeta_compartida()
    local orden, habia = cargar_tabla(carpeta .. sep .. "armar_video.json")
    if not habia then fail("No hay ninguna orden pendiente (armar_video.json): la deja el programa al soltar un video en Inicio.") end
    if type(orden) ~= "table" or not orden.ruta then fail("La orden de armar el video esta danada.") end
    local RUTA = tostring(orden.ruta)
    local ANCHO, ALTO = math.floor(tonumber(orden.ancho) or 1080), math.floor(tonumber(orden.alto) or 1920)
    local FPS = tonumber(orden.fps) or 30
    local res = { previo_tl = "" }

    local pm = resolve:GetProjectManager()
    if pm == nil then fail("Resolve no entrego el gestor de proyectos.") end
    local project = pm:GetCurrentProject()
    if tostring(orden.proyecto or "") ~= "" then
        local creado
        project, creado = proyecto_nuevo(pm, tostring(orden.proyecto), orden.descartar and tostring(orden.descartar) or nil)
        if not creado or project == nil then fail("Resolve no creo el proyecto «" .. tostring(orden.proyecto) .. "» (nombre ocupado o base de datos ocupada). Cierra los dialogos de Resolve y repite.") end
        print("Proyecto nuevo: " .. tostring(project:GetName()))
    end
    if project == nil then fail("No hay ningun proyecto abierto en Resolve: abre uno y repite.") end
    res.proyecto = project:GetName()

    -- Recien creado el proyecto, Resolve a veces devuelve nil (el Media Pool, la carpeta raiz o la subcarpeta que acaba de crear): se reintenta
    local mp, raiz, carpeta_mp = nil, nil, nil
    for intento = 1, 8 do
        mp = project:GetMediaPool()
        raiz = mp and mp:GetRootFolder() or nil
        if raiz ~= nil then
            for _, c in ipairs(lista_api(raiz:GetSubFolderList())) do
                if c:GetName() == "CineCaptions · videos" then carpeta_mp = c; break end
            end
            if carpeta_mp == nil then
                local ok_a, nueva = pcall(function() return mp:AddSubFolder(raiz, "CineCaptions · videos") end)
                if ok_a and nueva then carpeta_mp = nueva end
                if carpeta_mp == nil then
                    for _, c in ipairs(lista_api(raiz:GetSubFolderList())) do
                        if c:GetName() == "CineCaptions · videos" then carpeta_mp = c; break end
                    end
                end
            end
            if carpeta_mp ~= nil then break end
        end
        pausa(0.8)
    end
    if carpeta_mp == nil then carpeta_mp = raiz end
    if carpeta_mp == nil then fail("Resolve no entrego el Media Pool del proyecto nuevo") end
    pcall(function() mp:SetCurrentFolder(carpeta_mp) end)
    local clip = nil
    for _, it in ipairs(lista_api(carpeta_mp:GetClipList())) do
        local ok_p, rp = pcall(function() return it:GetClipProperty("File Path") end)
        if ok_p and rp == RUTA then clip = it; break end
    end
    if clip == nil then
        local ok_i, items = pcall(function() return mp:ImportMedia({ RUTA }) end)
        clip = (ok_i and type(items) == "table") and items[1] or nil
    end
    if clip == nil then fail("Resolve no pudo importar el video: " .. RUTA) end

    local existentes = {}
    for i = 1, math.floor(tonumber(project:GetTimelineCount()) or 0) do
        local t = project:GetTimelineByIndex(i)
        if t then existentes[t:GetName()] = true end
    end
    local base = tostring(orden.nombre or "CineCaptions")
    local nombre, k = base, 2
    while existentes[nombre] do
        nombre = string.format("%s %d", base, k)
        k = k + 1
    end
    local tl = mp:CreateEmptyTimeline(nombre)
    if not tl then fail("Resolve no creo el timeline «" .. nombre .. "».") end
    res.timeline = nombre
    -- v5.4.40: Resolve hace una copia de respaldo del timeline recien creado en segundo plano; si los SetSetting llegan antes de que acabe, Resolve Free se cuelga (medido: el 2.º GO
    -- seguido se colgaba 5 de 7 veces, siempre justo ahi: «sequence setup changed» sin el «timeline backup created» de las veces que sale bien). Se le da tiempo y se espacian los cambios.
    pausa(2.0)
    for _, par in ipairs({ { "useCustomSettings", "1" }, { "timelineResolutionWidth", tostring(ANCHO) }, { "timelineResolutionHeight", tostring(ALTO) },
                           { "timelineOutputResolutionWidth", tostring(ANCHO) }, { "timelineOutputResolutionHeight", tostring(ALTO) }, { "timelineFrameRate", string.format("%g", FPS) } }) do
        pcall(function() tl:SetSetting(par[1], par[2]) end)
        pausa(0.3)
    end
    pcall(function() project:SetCurrentTimeline(tl) end)
    local ok_ap, puestos = pcall(function() return mp:AppendToTimeline({ clip }) end)
    res.anadido = (ok_ap and type(puestos) == "table") and #puestos or 0
    if res.anadido == 0 then fail("Resolve no puso el video en el timeline.") end

    -- el audio ORIGINAL del video tiene que estar en A1 y sonar: se comprueba y, si Resolve solo metio la imagen, se anade el audio aparte
    local function a1() return lista_api(tl:GetItemListInTrack("audio", 1)) end
    local tipo = ""
    pcall(function() tipo = tostring(clip:GetClipProperty("Type") or ""):lower() end)
    local canales = 0
    pcall(function() canales = math.floor(tonumber(clip:GetClipProperty("Audio Ch")) or 0) end)
    res.clip_con_audio = (tipo:find("audio", 1, true) ~= nil) or canales > 0
    res.audio_a1 = #a1()
    res.audio_repuesto = 0
    if res.clip_con_audio and #a1() == 0 then
        pcall(function() mp:AppendToTimeline({ { mediaPoolItem = clip, mediaType = 2, trackIndex = 1, recordFrame = tl:GetStartFrame() } }) end)
        res.audio_repuesto = #a1()
    end
    pcall(function()
        tl:SetTrackEnable("audio", 1, true)
        for _, it in ipairs(a1()) do it:SetClipEnabled(true) end
    end)
    local ESCALA = 1
    pcall(function() ESCALA = resolve.SCALE_FIT or 1 end)
    local v1 = lista_api(tl:GetItemListInTrack("video", 1))
    for _, it in ipairs(v1) do pcall(function() it:SetProperty("Scaling", ESCALA) end) end
    res.ancho = math.floor(tonumber(tl:GetSetting("timelineResolutionWidth")) or 0)
    res.alto = math.floor(tonumber(tl:GetSetting("timelineResolutionHeight")) or 0)
    res.fps = tonumber(tl:GetSetting("timelineFrameRate")) or 0
    res.inicio = math.floor(tonumber(tl:GetStartFrame()) or 0)
    res.fin = math.floor(tonumber(tl:GetEndFrame()) or 0)
    res.pista_broll = false
    if orden.pista_broll == true then
        -- una pista de video vacia y BLOQUEADA justo encima de V1: los captions (que saltan las pistas bloqueadas) se ponen mas arriba y el B-roll queda DEBAJO de ellos
        pcall(function()
            if tl:AddTrack("video") then
                local n = math.floor(tonumber(tl:GetTrackCount("video")) or 0)
                tl:SetTrackName("video", n, "FX-BROLL")
                res.pista_broll = (tl:SetTrackLock("video", n, true) == true)
            end
        end)
    end
    local filas = {}
    for _, it in ipairs(v1) do
        local rs = ""
        pcall(function() rs = it:GetMediaPoolItem():GetClipProperty("Resolution") or "" end)
        filas[#filas + 1] = string.format('{"inicio": %d, "dur": %d, "res": "%s", "nombre": "%s"}', math.floor(tonumber(it:GetStart()) or 0), math.floor(tonumber(it:GetDuration()) or 0),
            json_escapar(rs), json_escapar(tostring(it:GetName()):sub(1, 40)))
    end
    RESULTADO = string.format('{"proyecto": "%s", "timeline": "%s", "ancho": %d, "alto": %d, "fps": %g, "inicio": %d, "fin": %d, "anadido": %d, "clip_con_audio": %s, "audio_a1": %d, "audio_repuesto": %d, "pista_broll": %s, "v1": [%s]}',
        json_escapar(res.proyecto), json_escapar(res.timeline), res.ancho, res.alto, res.fps, res.inicio, res.fin, res.anadido, tostring(res.clip_con_audio), res.audio_a1, res.audio_repuesto,
        tostring(res.pista_broll), table.concat(filas, ", "))
    print("ARMADO " .. RESULTADO)
    print(string.format("Timeline «%s» armado con tu video en el proyecto «%s» (%dx%d, %g fps).", res.timeline, res.proyecto, res.ancho, res.alto, res.fps))
end

local ok, err = pcall(main)
if not ok then
    print("[ArmarVideo] termino con error: " .. tostring(err))
    guardar_resultado(false, tostring(err))
else
    guardar_resultado(true, "Timeline armado")
end

-- No dejar el wrapper de print puesto (el Puente comparte estado de Lua).
print = _print_original

-- Free 21.1, sin io: el resultado viaja por el registro de Resolve (ver el epilogo de CineCaptions_SfxMarcadores.lua). Bajo el Puente se DEVUELVE (el Puente lo relata); a mano, un error() sin capturar lo deja en ResolveDebug.txt.
-- OJO: el texto del reporte lleva SOLO lo ultimo del registro (1300 caracteres): la linea «ARMADO {json}» tiene que caber ahi; por eso el JSON va tambien en un campo propio.
if SIN_IO then
    local reporte = "CINECAPTIONS_REPORTE|" .. reporte_con_armado(ok, ok and "Timeline armado" or tostring(err), texto_para_reporte(), RESULTADO)
    if ENTREGA_PUENTE ~= nil then return reporte end
    error(reporte, 0)
end

-- Un script que falla tiene que fallar hacia afuera (el pcall(dofile) del Puente daria el trabajo por bueno).
if not ok then
    error(err, 0)
end
