-- CineCaptions · By Cinema Productions
-- 2_recursos/resolve_scripts/CineCaptions_Vista.lua — guardar o aplicar la disposicion de pantalla de Resolve (vertical, vista expandida) por el Puente.
--[[
CineCaptions_Vista.lua
----------------------
Guarda («guardar») o aplica («cargar») la disposicion de pantalla de Resolve (resolve:SaveLayoutPreset / UpdateLayoutPreset / LoadLayoutPreset) que usa CineCaptions al terminar GO: vertical y con
la vista expandida. En Studio lo hace el MCP; en Resolve FREE (sin MCP) el Puente la corre con dofile. La orden: vista_orden.json (sidecar .lua en Free).
]]

local VERSION = "5.37 (vista)"

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

local NOMBRE_SCRIPT = "CineCaptions_Vista"
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

-- El reporte con un campo propio «vista» (lo que paso): la app lo lee con resolve_bridge.reportes_del_registro.
local function reporte_con_vista(ok, mensaje, texto, vista_json)
    local base = json_resultado(ok, mensaje, texto)
    if vista_json ~= nil then base = base:sub(1, -2) .. ', "vista": ' .. vista_json .. "}" end
    return base
end

local function fail(msg)
    print("[Vista] ERROR: " .. msg)
    guardar_resultado(false, msg)
    error(msg, 0)
end

-- ---------------------------------------------------------------------
-- La orden: vista_orden.json = { accion = "guardar" | "cargar" | "borrar" | "render" | "render_estado", nombre = "CineCaptions vertical" }.
--   guardar: deja la disposicion ACTUAL de Resolve con ese nombre (la crea o la actualiza).
--   cargar:  aplica la que ya esta guardada con ese nombre.
--   borrar:  quita la guardada con ese nombre (para las pruebas).
--   render:  (v5.4.30, herramienta de desarrollo: hacer_vistas_mezcla.py) manda a la cola de render el timeline ACTUAL y EMPIEZA a renderizar (no espera: un script del Puente que se queda
--            minutos esperando deja al Puente sin latido). Orden: destino (carpeta), nombre (sin extension), ancho, alto. Devuelve el trabajo.
--   render_estado: {en_curso, estado, avance} del trabajo `job` (o del ultimo): la app pregunta cada pocos segundos hasta que termina.
-- ---------------------------------------------------------------------
local RESULTADO = nil

local function norm_ruta(r)
    return string.lower(tostring(r or ""):gsub("\\", "/"):gsub("/+$", ""))
end

local function proyecto_actual()
    local ok, pm = pcall(function() return resolve:GetProjectManager() end)
    if not ok or pm == nil then return nil end
    local ok2, p = pcall(function() return pm:GetCurrentProject() end)
    if ok2 then return p end
    return nil
end

local function render_empezar(orden)
    local proyecto = proyecto_actual()
    if proyecto == nil then fail("No hay ningun proyecto abierto en Resolve.") end
    local tl = proyecto:GetCurrentTimeline()
    if tl == nil then fail("El proyecto no tiene un timeline actual que renderizar.") end
    local destino = tostring(orden.destino or "")
    local nombre = tostring(orden.nombre or "vistas")
    if destino == "" then fail("La orden de render no trae la carpeta de destino.") end
    -- solo se borran los trabajos DE NUESTRA carpeta: la cola de render del usuario no se toca
    for _, j in ipairs(proyecto:GetRenderJobList() or {}) do
        if norm_ruta(j.TargetDir) == norm_ruta(destino) then proyecto:DeleteRenderJob(j.JobId) end
    end
    local preset = proyecto:LoadRenderPreset(tostring(orden.preset or "H.264 Master")) and true or false
    local ajustes = { SelectAllFrames = true, TargetDir = destino, CustomName = nombre }
    local fps_tl = tonumber(tl:GetSetting("timelineFrameRate")) or 30
    if tonumber(orden.hasta_s) then                                  -- solo un tramo (segundos desde el principio del timeline): MarkIn / MarkOut en fotogramas del timeline
        local ini = (tl:GetStartFrame() or 0) + math.floor((tonumber(orden.desde_s) or 0) * fps_tl + 0.5)
        local fin = (tl:GetStartFrame() or 0) + math.floor(tonumber(orden.hasta_s) * fps_tl + 0.5) - 1
        ajustes.SelectAllFrames = false
        ajustes.MarkIn = ini
        ajustes.MarkOut = fin
    end
    if tonumber(orden.ancho) and tonumber(orden.alto) then
        ajustes.FormatWidth = math.floor(tonumber(orden.ancho))
        ajustes.FormatHeight = math.floor(tonumber(orden.alto))
    end
    local fps = tonumber(tl:GetSetting("timelineFrameRate"))
    if fps then ajustes.FrameRate = fps end
    local ok_aj = proyecto:SetRenderSettings(ajustes) and true or false
    local job = proyecto:AddRenderJob()
    if not job or job == "" then fail("Resolve no creo el trabajo de render (preset " .. tostring(preset) .. ", ajustes " .. tostring(ok_aj) .. ").") end
    local inicio = proyecto:StartRendering(job) and true or false
    RESULTADO = string.format('{"ok": %s, "accion": "render", "job": "%s", "preset": %s, "ajustes": %s, "inicio": %s, "timeline": "%s"}',
        tostring(inicio), json_escapar(job), tostring(preset), tostring(ok_aj), tostring(inicio), json_escapar(tl:GetName() or ""))
    print("VISTA " .. RESULTADO)
    if not inicio then error("Resolve no empezo a renderizar.", 0) end
end

local function render_parar(orden)
    local proyecto = proyecto_actual()
    if proyecto == nil then fail("No hay ningun proyecto abierto en Resolve.") end
    pcall(function() proyecto:StopRendering() end)
    -- fuera los trabajos DE NUESTRA carpeta (la cola de render del usuario no se toca)
    local destino = tostring(orden.destino or "")
    local borrados = 0
    if destino ~= "" then
        for _, j in ipairs(proyecto:GetRenderJobList() or {}) do
            if norm_ruta(j.TargetDir) == norm_ruta(destino) then proyecto:DeleteRenderJob(j.JobId); borrados = borrados + 1 end
        end
    end
    RESULTADO = string.format('{"ok": true, "accion": "render_parar", "borrados": %d, "en_curso": %s}', borrados, tostring(proyecto:IsRenderingInProgress() and true or false))
    print("VISTA " .. RESULTADO)
end

-- «cerrar» (v5.4.35, herramienta de pruebas): guarda y cierra Resolve, SOLO si el proyecto abierto es uno de pruebas de CineCaptions («CineCaptions», «CineCaptions 7», «CineCaptions_nuevo_…»): nunca
-- toca un proyecto del usuario. Las pruebas necesitan un Resolve recién arrancado en cada vuelta (Resolve Free se cuelga tras varios proyectos) y un script no puede matar el proceso: se lo pide a Resolve.
local function cerrar_resolve(orden)
    local ok_pm, pm = pcall(function() return resolve:GetProjectManager() end)
    local proyecto = proyecto_actual()
    local nombre = tostring(proyecto and proyecto:GetName() or "")
    local de_pruebas = (nombre == "CineCaptions") or (nombre:match("^CineCaptions %d+$") ~= nil) or (nombre:match("^CineCaptions_nuevo") ~= nil)
    if not de_pruebas then
        fail("No cierro Resolve: el proyecto abierto («" .. nombre .. "») no es uno de pruebas de CineCaptions.")
    end
    if ok_pm and pm ~= nil then pcall(function() pm:SaveProject() end) end
    RESULTADO = string.format('{"ok": true, "accion": "cerrar", "proyecto": "%s"}', json_escapar(nombre))
    print("VISTA " .. RESULTADO)
    pcall(function() CINECAPTIONS_CERRAR_RESOLVE = true end)
end

local function render_estado(orden)
    local proyecto = proyecto_actual()
    if proyecto == nil then fail("No hay ningun proyecto abierto en Resolve.") end
    local job = tostring(orden.job or "")
    local en_curso = proyecto:IsRenderingInProgress() and true or false
    local estado, avance = "", -1
    if job ~= "" then
        local st = proyecto:GetRenderJobStatus(job)
        if type(st) == "table" then
            estado = tostring(st.JobStatus or "")
            avance = tonumber(st.CompletionPercentage) or -1
        end
    end
    RESULTADO = string.format('{"ok": true, "accion": "render_estado", "en_curso": %s, "estado": "%s", "avance": %s, "job": "%s"}',
        tostring(en_curso), json_escapar(estado), tostring(avance), json_escapar(job))
    print("VISTA " .. RESULTADO)
end

-- v5.4.40: lleva el cabezal al PRIMER fotograma del timeline actual (la app luego manda «reproducir»: Resolve no tiene llamada de script para reproducir ni la tecla Inicio llega siempre)
local function cabezal_al_inicio(orden)
    local proyecto = proyecto_actual()
    if proyecto == nil then fail("No hay ningun proyecto abierto en Resolve.") end
    local tl = proyecto:GetCurrentTimeline()
    if tl == nil then fail("No hay timeline abierto.") end
    local tc = tl:GetStartTimecode()
    local ok = false
    if tc ~= nil then ok = tl:SetCurrentTimecode(tc) and true or false end
    pcall(function() resolve:OpenPage("edit") end)
    RESULTADO = string.format('{"ok": %s, "accion": "cabezal", "timecode": "%s"}', tostring(ok), json_escapar(tostring(tc)))
    print("VISTA " .. RESULTADO)
end

-- DIAGNOSTICO (solo lectura): Pan/Tilt/Zoom de los clips de una pista de video del timeline abierto
local function inspeccionar(orden)
    local proyecto = proyecto_actual()
    if proyecto == nil then fail("No hay ningun proyecto abierto en Resolve.") end
    local tl = proyecto:GetCurrentTimeline()
    if tl == nil then fail("No hay timeline abierto.") end
    local pista = tostring(orden.pista or "")
    local filas = {}
    for t = 1, tl:GetTrackCount("video") do
        local nom = tostring(tl:GetTrackName("video", t) or "")
        if pista == "" or nom == pista then
            for _, it in ipairs(tl:GetItemListInTrack("video", t) or {}) do
                local function g(k) local ok, v = pcall(function() return it:GetProperty(k) end); return (ok and tonumber(v)) or 0 end
                filas[#filas + 1] = string.format('{"t":%d,"pista":"%s","n":"%s","ini":%d,"pan":%s,"tilt":%s,"zx":%s,"zy":%s}',
                    t, json_escapar(nom), json_escapar(tostring(it:GetName())), it:GetStart(), tostring(g("Pan")), tostring(g("Tilt")), tostring(g("ZoomX")), tostring(g("ZoomY")))
                if #filas >= 14 then break end
            end
        end
    end
    RESULTADO = string.format('{"ok": true, "accion": "inspeccionar", "ancho": "%s", "alto": "%s", "items": [%s]}',
        tostring(tl:GetSetting("timelineResolutionWidth")), tostring(tl:GetSetting("timelineResolutionHeight")), table.concat(filas, ","))
    print("VISTA " .. RESULTADO)
end

-- DIAGNOSTICO: pone Pan/Tilt/Zoom al clip N de una pista de video (orden.pista, orden.indice, orden.props)
local function ajustar_clip(orden)
    local proyecto = proyecto_actual()
    if proyecto == nil then fail("No hay ningun proyecto abierto en Resolve.") end
    local tl = proyecto:GetCurrentTimeline()
    if tl == nil then fail("No hay timeline abierto.") end
    local pista = tostring(orden.pista or "")
    local indice = math.floor(tonumber(orden.indice) or 1)
    local hechos = {}
    for t = 1, tl:GetTrackCount("video") do
        if tostring(tl:GetTrackName("video", t) or "") == pista then
            local it = (tl:GetItemListInTrack("video", t) or {})[indice]
            if it ~= nil then
                for k, v in pairs(orden.props or {}) do
                    local ok, r = pcall(function() return it:SetProperty(k, tonumber(v)) end)
                    hechos[#hechos + 1] = string.format('"%s": %s', json_escapar(tostring(k)), tostring(ok and r and true or false))
                end
            end
        end
    end
    RESULTADO = '{"ok": true, "accion": "ajustar_clip", "hechos": {' .. table.concat(hechos, ",") .. '}}'
    print("VISTA " .. RESULTADO)
end

local function main()
    local r, diag = obtener_resolve()
    if r == nil then
        fail("No pude conectar con Resolve (relanza CineCaptions_Puente: Area de trabajo > Scripts > CineCaptions_Puente)  |  Diagnostico: " .. tostring(diag))
    end
    resolve = r
    print("[Vista] version " .. VERSION)
    local carpeta, sep = carpeta_compartida()
    local orden, habia = cargar_tabla(carpeta .. sep .. "vista_orden.json")
    if not habia or type(orden) ~= "table" then fail("No hay ninguna orden pendiente (vista_orden.json): la deja el programa con «Guardar la vista actual de Resolve».") end
    local nombre = tostring(orden.nombre or "CineCaptions vertical")
    local accion = tostring(orden.accion or "guardar")
    if accion == "render" then render_empezar(orden); return end
    if accion == "render_estado" then render_estado(orden); return end
    if accion == "render_parar" then render_parar(orden); return end
    if accion == "cerrar" then cerrar_resolve(orden); return end
    if accion == "ping" then RESULTADO = '{"ok": true, "accion": "ping"}'; print("VISTA " .. RESULTADO); return end
    if accion == "cabezal" then cabezal_al_inicio(orden); return end
    if accion == "inspeccionar" then inspeccionar(orden); return end
    if accion == "ajustar_clip" then ajustar_clip(orden); return end
    local lista = resolve:GetLayoutPresetList() or {}
    local existia = false
    for _, n in pairs(lista) do if n == nombre then existia = true end end
    local ok = false
    if accion == "cargar" then
        if not existia then fail("No hay una disposicion de pantalla guardada con el nombre «" .. nombre .. "».") end
        ok = resolve:LoadLayoutPreset(nombre) and true or false
    elseif accion == "borrar" then
        ok = (not existia) or (resolve:DeleteLayoutPreset(nombre) and true or false)
    else
        if existia then ok = resolve:UpdateLayoutPreset(nombre) and true or false else ok = resolve:SaveLayoutPreset(nombre) and true or false end
    end
    RESULTADO = string.format('{"ok": %s, "accion": "%s", "nombre": "%s", "existia": %s}', tostring(ok), json_escapar(accion), json_escapar(nombre), tostring(existia))
    print("VISTA " .. RESULTADO)
    if not ok then error("Resolve no " .. (accion == "cargar" and "aplico" or "guardo") .. " la disposicion de pantalla «" .. nombre .. "».", 0) end
end

local ok, err = pcall(main)
if not ok then
    print("[Vista] termino con error: " .. tostring(err))
    guardar_resultado(false, tostring(err))
else
    guardar_resultado(true, "Disposicion de pantalla lista")
end

-- No dejar el wrapper de print puesto (el Puente comparte estado de Lua).
print = _print_original

-- «cerrar»: el reporte ya salió (guardar_resultado); ahora se le pide a Resolve que se cierre.
do
    local ok_c, pedido = pcall(function() return CINECAPTIONS_CERRAR_RESOLVE end)
    if ok_c and pedido == true then
        CINECAPTIONS_CERRAR_RESOLVE = nil
        pcall(function() resolve:Quit() end)
    end
end

-- Free 21.1, sin io: el resultado viaja por el registro de Resolve. Bajo el Puente se DEVUELVE (el Puente lo relata); a mano, un error() sin capturar lo deja en ResolveDebug.txt.
if SIN_IO then
    local reporte = "CINECAPTIONS_REPORTE|" .. reporte_con_vista(ok, ok and "Disposicion de pantalla lista" or tostring(err), texto_para_reporte(), RESULTADO)
    if ENTREGA_PUENTE ~= nil then return reporte end
    error(reporte, 0)
end

-- Un script que falla tiene que fallar hacia afuera (el pcall(dofile) del Puente daria el trabajo por bueno).
if not ok then
    error(err, 0)
end
