-- CineCaptions · By Cinema Productions
-- 2_recursos/resolve_scripts/CineCaptions_Pausas.lua — «Quitar pausas» (jump cuts en los silencios) en Resolve Free.
--[[
CineCaptions_Pausas.lua
-----------------------
Version en Lua para Resolve FREE (el Puente la corre con dofile) de pausas._CORTAR, que en Studio corre por el MCP: rehace V1 y A1 del timeline actual con los tramos
que se quedan pegados uno tras otro. Solo toca un timeline con UN unico clip en V1 (el que GO armo con el video soltado).
]]

local VERSION = "5.5.1 (pausas)"

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

local NOMBRE_SCRIPT = "CineCaptions_Pausas"
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

-- El reporte con un campo propio «pausas» (lo que paso: tramos, clips que quedaron): la app lo lee con resolve_bridge.reportes_del_registro.
local function reporte_con_pausas(ok, mensaje, texto, pausas_json)
    local base = json_resultado(ok, mensaje, texto)
    if pausas_json ~= nil then base = base:sub(1, -2) .. ', "pausas": ' .. pausas_json .. "}" end
    return base
end

local function fail(msg)
    print("[Pausas] ERROR: " .. msg)
    guardar_resultado(false, msg)
    error(msg, 0)
end

local function redondear(x) return math.floor(x + 0.5) end

-- ---------------------------------------------------------------------
-- Gemela de pausas._CORTAR (la de Studio, por el MCP): rehace V1 y A1 del timeline actual con los tramos que se quedan (segundos de la FUENTE) pegados uno tras otro.
-- Solo se toca un timeline con UN unico clip en V1 (el que GO armo con el video soltado): jamas el de otro trabajo. La orden: pausas_orden.json (sidecar .lua en Free).
-- ---------------------------------------------------------------------
local RESULTADO = nil

local function main()
    local r, diag, rechazados = obtener_resolve()
    if r == nil then
        fail("No pude conectar con Resolve (relanza CineCaptions_Puente: Area de trabajo > Scripts > CineCaptions_Puente)  |  Diagnostico: " .. tostring(diag))
    end
    resolve = r
    print("[Pausas] version " .. VERSION)
    print("[Pausas] entrega del Puente: " .. (ENTREGA_PUENTE and "recibida" or "no (corrida manual o Puente viejo)"))
    local carpeta, sep = carpeta_compartida()
    local orden, habia = cargar_tabla(carpeta .. sep .. "pausas_orden.json")
    if not habia then fail("No hay ninguna orden pendiente (pausas_orden.json): la deja el programa con «Quitar pausas».") end
    if type(orden) ~= "table" or type(orden.segs) ~= "table" or #orden.segs == 0 then fail("La orden de quitar pausas esta danada.") end
    local SEGS = orden.segs

    local pm = resolve:GetProjectManager()
    local project = pm and pm:GetCurrentProject() or nil
    if project == nil then fail("No hay ningun proyecto abierto en Resolve.") end
    local tl = project:GetCurrentTimeline()
    if tl == nil then fail("No hay un timeline activo en Resolve.") end
    local mp = project:GetMediaPool()
    local res = { ok = false }
    local v1 = lista_api(tl:GetItemListInTrack("video", 1))
    local a1 = lista_api(tl:GetItemListInTrack("audio", 1))
    if #v1 ~= 1 then
        res.error = string.format("V1 no tiene un solo clip (%d): no se toca", #v1)
    else
        local it = v1[1]
        local mpi = it:GetMediaPoolItem()
        if mpi == nil then
            res.error = "el clip de V1 no viene del Media Pool"
        else
            local fps_tl = tonumber(tl:GetSetting("timelineFrameRate")) or 30
            local fps_clip = tonumber(mpi:GetClipProperty("FPS")) or 0
            if fps_clip <= 0 then fps_clip = fps_tl end
            local total = math.floor(tonumber(mpi:GetClipProperty("Frames")) or 0)
            local inicio = math.floor(tonumber(tl:GetStartFrame()) or 0)
            local viejos = {}
            for _, x in ipairs(v1) do viejos[#viejos + 1] = x end
            for _, x in ipairs(a1) do viejos[#viejos + 1] = x end
            tl:DeleteClips(viejos, false)
            local pos, puestos = inicio, 0
            for _, seg in ipairs(SEGS) do
                local sf = redondear((tonumber(seg[1]) or 0) * fps_clip)
                local ef = redondear((tonumber(seg[2]) or 0) * fps_clip) - 1
                if total > 0 then ef = math.min(ef, total - 1) end
                if ef >= sf then
                    local ok, nuevos = pcall(function()
                        return mp:AppendToTimeline({ { mediaPoolItem = mpi, startFrame = sf, endFrame = ef, recordFrame = pos, trackIndex = 1 } })
                    end)
                    if not (ok and type(nuevos) == "table" and #nuevos > 0) then
                        res.error = string.format("Resolve no coloco el tramo %d", puestos)
                        break
                    end
                    puestos = puestos + 1
                    pos = pos + redondear((ef - sf + 1) * fps_tl / fps_clip)
                end
            end
            res.tramos = puestos
            local v1n = lista_api(tl:GetItemListInTrack("video", 1))
            local a1n = lista_api(tl:GetItemListInTrack("audio", 1))
            res.v1, res.a1 = #v1n, #a1n
            local ESCALA = 1
            pcall(function() ESCALA = resolve.SCALE_FIT or 1 end)
            for _, x in ipairs(v1n) do pcall(function() x:SetProperty("Scaling", ESCALA) end) end
            if res.error == nil and puestos == #SEGS and #v1n == puestos then
                res.ok = true
            else
                res.error = res.error or string.format("quedaron %d tramos de video y %d de audio", #v1n, #a1n)
                -- a medias: se intenta dejar el video entero como estaba
                local rest = {}
                for _, x in ipairs(v1n) do rest[#rest + 1] = x end
                for _, x in ipairs(a1n) do rest[#rest + 1] = x end
                pcall(function() tl:DeleteClips(rest, false) end)
                local ok2, n2 = pcall(function() return mp:AppendToTimeline({ { mediaPoolItem = mpi, recordFrame = inicio, trackIndex = 1 } }) end)
                res.restaurado = (ok2 and type(n2) == "table") and #lista_api(tl:GetItemListInTrack("video", 1)) or 0
            end
        end
    end
    RESULTADO = string.format('{"ok": %s, "error": "%s", "tramos": %d, "v1": %d, "a1": %d, "restaurado": %d}', tostring(res.ok), json_escapar(res.error or ""),
        math.floor(tonumber(res.tramos) or 0), math.floor(tonumber(res.v1) or 0), math.floor(tonumber(res.a1) or 0), math.floor(tonumber(res.restaurado) or 0))
    print("PAUSAS " .. RESULTADO)
    if not res.ok then error(res.error or "Quitar pausas no se pudo aplicar", 0) end
end

local ok, err = pcall(main)
if not ok then
    print("[Pausas] termino con error: " .. tostring(err))
    guardar_resultado(false, tostring(err))
else
    guardar_resultado(true, "Pausas quitadas")
end

-- No dejar el wrapper de print puesto (el Puente comparte estado de Lua).
print = _print_original

-- Free 21.1, sin io: el resultado viaja por el registro de Resolve. Bajo el Puente se DEVUELVE (el Puente lo relata); a mano, un error() sin capturar lo deja en ResolveDebug.txt.
if SIN_IO then
    local reporte = "CINECAPTIONS_REPORTE|" .. reporte_con_pausas(ok, ok and "Pausas quitadas" or tostring(err), texto_para_reporte(), RESULTADO)
    if ENTREGA_PUENTE ~= nil then return reporte end
    error(reporte, 0)
end

-- Un script que falla tiene que fallar hacia afuera (el pcall(dofile) del Puente daria el trabajo por bueno).
if not ok then
    error(err, 0)
end
