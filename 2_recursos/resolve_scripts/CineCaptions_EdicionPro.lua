-- CineCaptions · By Cinema Productions
-- 2_recursos/resolve_scripts/CineCaptions_EdicionPro.lua — la Edición PRO (gráficos OGraf, la persona recortada, sonidos) en Resolve Free.
--[[
CineCaptions_EdicionPro.lua
---------------------------
Version en Lua para Resolve FREE (el Puente la corre con dofile) de "2_recursos/edicion_pro/colocar_pro.py", que es la de Studio (por el MCP).
Lee el plan que deja la app (edicion_pro_plan.json; sin io, su sidecar .lua) y pone los graficos animados (.ograf), la persona recortada con IA local
(ProRes 4444 con alfa: en Free no hay Magic Mask) y los sonidos en pistas «PRO-…» encima de V1 y debajo de los captions.
Reglas (las mismas que la gemela): nunca toca V1/A1 ni las pistas de los captions; las pistas «PRO-…» se vacian y se vuelven a llenar en cada corrida;
los clips de una misma pista nunca se pisan; los archivos se importan una sola vez al bin «RCS · Edición PRO».
]]

local VERSION = "5.4.50 (edicion pro)"

-- La ENTREGA del Puente: ver CineCaptions_InsertarSFX.lua.
local ENTREGA_PUENTE = ({...})[1]
if type(ENTREGA_PUENTE) ~= "table" then ENTREGA_PUENTE = nil end

-- Free 21.1 capo io en el menu de Scripts (medido el 16-09): sin io no se escribe nada, el plan se lee de su sidecar .lua y el resultado viaja por el
-- registro de Resolve (ver el epilogo). Con io, todo como siempre.
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

local NOMBRE_SCRIPT = "CineCaptions_EdicionPro"
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
    print("[Edicion PRO] ERROR: " .. msg)
    guardar_resultado(false, msg)
    error(msg, 0)
end

-- ---------------------------------------------------------------------
-- Gemela de 2_recursos/edicion_pro/colocar_pro.py (la de Studio, que corre por el MCP): pone los graficos OGraf de la Edicion PRO, la persona
-- recortada (ProRes 4444 con alfa: en Free no hay Magic Mask) y los sonidos en pistas propias «PRO-…» justo encima de V1 y DEBAJO de los
-- captions. Nunca toca V1/A1 ni las pistas de los captions. Nada de InsertFusionTitleIntoTimeline: solo ImportMedia + AppendToTimeline.
-- El plan lo deja la app en ~/DaVinciSubtitles/edicion_pro_plan.json (y su sidecar .lua, que es lo que lee Free 21.1: sin io).
-- ---------------------------------------------------------------------
local ORDEN = { "PRO-BROLL", "PRO-GRIS", "PRO-FONDO", "PRO-VELO", "PRO-DETRAS", "PRO-PERSONA", "PRO-DELANTE" }
local CAPA = { fondo = "PRO-FONDO", velo = "PRO-VELO", detras = "PRO-DETRAS", delante = "PRO-DELANTE", iconos = "PRO-ICONOS" }
local PISTA_ENCIMA = "PRO-ENCIMA"
local PISTA_ICONOS = "PRO-ICONOS"        -- los iconos 3D junto a los captions: encima de ellos (y debajo de PRO-ENCIMA)
local MARCA_EMOJI = "ccpro-emoji-off"    -- el emoji del tema que se apago porque en ese bloque va un icono 3D
local MARCA = "ccpro-subir"              -- marca en cada clip de captions que se subio: "ccpro-subir:<Tilt antes>:<Tilt despues>"
local PISTA_SONIDO = "PRO-SONIDO"
local BIN = "RCS · Edición PRO"
local RESUMEN = ""

local function redondear(x) return math.floor(x + 0.5) end

local function norm(r)
    r = tostring(r or "")
    if es_windows() then
        r = r:gsub("/", "\\"):gsub("\\+", "\\"):lower()
    else
        r = r:gsub("//+", "/")
    end
    return r
end

local function buscar_clip(carpeta, buscada)
    for _, clip in ipairs(lista_api(carpeta:GetClipList())) do
        local ok, r = pcall(function() return clip:GetClipProperty("File Path") end)
        if ok and r and r ~= "" and norm(r) == buscada then return clip end
    end
    for _, sub in ipairs(lista_api(carpeta:GetSubFolderList())) do
        local x = buscar_clip(sub, buscada)
        if x ~= nil then return x end
    end
    return nil
end

local function caja_pro(mp)
    local raiz = mp:GetRootFolder()
    for _, f in ipairs(lista_api(raiz:GetSubFolderList())) do
        if f:GetName() == BIN then return f end
    end
    return mp:AddSubFolder(raiz, BIN) or raiz
end

local function importar(mp, caja, ruta)
    local ya = buscar_clip(mp:GetRootFolder(), norm(ruta))
    if ya ~= nil then return ya end
    local previa = nil
    pcall(function() previa = mp:GetCurrentFolder() end)
    pcall(function() mp:SetCurrentFolder(caja) end)
    local ok, nuevos = pcall(function() return mp:ImportMedia({ tostring(ruta) }) end)
    if previa ~= nil then pcall(function() mp:SetCurrentFolder(previa) end) end
    if ok and type(nuevos) == "table" then return nuevos[1] end
    return nil
end

local function nombre_pista(tl, tipo, i)
    local nombre = ""
    pcall(function() nombre = tl:GetTrackName(tipo, i) or "" end)
    return nombre
end

local function indice(tl, nombre, tipo)
    tipo = tipo or "video"
    for i = 1, math.floor(tonumber(tl:GetTrackCount(tipo)) or 0) do
        if nombre_pista(tl, tipo, i) == nombre then return i end
    end
    return nil
end

local function vaciar(tl, i, tipo)
    tipo = tipo or "video"
    pcall(function() if tl:GetIsTrackLocked(tipo, i) then tl:SetTrackLock(tipo, i, false) end end)
    local viejos = lista_api(tl:GetItemListInTrack(tipo, i))
    if #viejos > 0 then pcall(function() tl:DeleteClips(viejos, false) end) end
end

-- Las pistas PRO, vacias y en su orden, justo encima de V1 (o de FX-BROLL).
local function pistas_pro(tl)
    for _, n in ipairs(ORDEN) do
        local i = indice(tl, n)
        if i then vaciar(tl, i) end
    end
    local debajo = indice(tl, "FX-BROLL") or 1
    for _, n in ipairs(ORDEN) do
        local ya = indice(tl, n)
        if ya then
            debajo = ya
        else
            local ok, r = pcall(function() return tl:AddTrack("video", { index = debajo + 1 }) end)
            if ok and r then
                tl:SetTrackName("video", debajo + 1, n)
            else
                pcall(function() tl:AddTrack("video") end)
                tl:SetTrackName("video", math.floor(tonumber(tl:GetTrackCount("video")) or 1), n)
            end
            debajo = indice(tl, n) or debajo
        end
    end
    local idx = {}
    for _, n in ipairs(ORDEN) do idx[n] = indice(tl, n) end
    return idx
end

local function quitar_vacias(tl)
    local todas = { PISTA_ENCIMA, PISTA_ICONOS }
    for _, n in ipairs(ORDEN) do todas[#todas + 1] = n end
    for _, n in ipairs(todas) do
        local i = indice(tl, n)
        if i and #lista_api(tl:GetItemListInTrack("video", i)) == 0 then pcall(function() tl:DeleteTrack("video", i) end) end
    end
end

local function append(mp, info)
    local ok, r = pcall(function() return mp:AppendToTimeline({ info }) end)
    if ok and type(r) == "table" then return r[1] end
    return nil
end

local function es_pro(n)
    for _, x in ipairs(ORDEN) do if x == n then return true end end
    return false
end

local TRANSFORMACION = { "Scaling", "ZoomX", "ZoomY", "Pan", "Tilt", "RotationAngle", "AnchorPointX", "AnchorPointY", "Pitch", "Yaw", "FlipX", "FlipY",
                         "CropLeft", "CropRight", "CropTop", "CropBottom", "CropSoftness" }

-- El clip de V1 que contiene [f0, f1) (nil si no hay uno solo).
local function clip_v1(tl, f0, f1)
    for _, it in ipairs(lista_api(tl:GetItemListInTrack("video", 1))) do
        if it:GetStart() <= f0 and f1 <= it:GetEnd() then return it end
    end
    return nil
end

-- El recorte tiene que caer EXACTAMENTE sobre la persona de V1: misma escala, zoom (punch-in), Pan, Tilt, recorte...
local function copiar_transformacion(de, a)
    local ok, props = pcall(function() return de:GetProperty() end)
    if not ok or type(props) ~= "table" then return end
    for _, k in ipairs(TRANSFORMACION) do
        if props[k] ~= nil then pcall(function() a:SetProperty(k, props[k]) end) end
    end
end

-- El punch-in que alterna en los saltos de V1 (pausas quitadas): zoom fijo en uno de cada dos clips. Absoluto (re-aplicar no apila).
local function punch_ins(tl, punch)
    local zooms, puestos = {}, 0
    for _, par in ipairs(punch or {}) do zooms[math.floor(tonumber(par[1]) or -1)] = tonumber(par[2]) end
    for _, it in ipairs(lista_api(tl:GetItemListInTrack("video", 1))) do
        local z = zooms[math.floor(tonumber(it:GetStart()) or -2)]
        if z then
            local ok = pcall(function() it:SetProperty("ZoomX", z); it:SetProperty("ZoomY", z) end)
            if ok then puestos = puestos + 1 end
        end
    end
    return puestos
end

-- Donde acaba de verdad lo que va DETRAS de la persona que empieza en f0 (los OGraf duran mas que su tramo: llevan su salida).
local function fin_detras(tl, idx, f0)
    local fin = 0
    for _, n in ipairs({ "PRO-DETRAS", "PRO-VELO", "PRO-FONDO" }) do
        if idx[n] then
            for _, x in ipairs(lista_api(tl:GetItemListInTrack("video", idx[n]))) do
                if math.abs(x:GetStart() - f0) <= 2 then fin = math.max(fin, x:GetEnd()) end
            end
        end
    end
    return fin
end

-- El recorte de la persona con IA local (ProRes 4444 con alfa recto), con la transformacion del clip de V1. En Free no hay Magic Mask.
local function poner_clip_persona(tl, mp, caja, p, f0, f1, pista)
    if p.modo ~= "clip" or not p.archivo then return nil end
    local v1 = clip_v1(tl, f0, f1)
    if v1 ~= nil then
        local ok, nombres = pcall(function() return v1:GetFusionCompNameList() end)
        for _, n in ipairs((ok and type(nombres) == "table") and nombres or {}) do
            if n == "CineCaptions FX" then return nil end          -- con el movimiento de Efectos el recorte no casaria
        end
    end
    local clip = importar(mp, caja, p.archivo)
    if clip == nil then return nil end
    pcall(function() clip:SetClipProperty("Alpha mode", "Straight") end)
    pcall(function() f1 = math.min(f1, f0 + math.floor(tonumber(clip:GetClipProperty("Frames")) or (f1 - f0))) end)
    local it = append(mp, { mediaPoolItem = clip, startFrame = 0, endFrame = f1 - f0 - 1, recordFrame = f0, trackIndex = pista, mediaType = 1 })
    if it ~= nil and v1 ~= nil then copiar_transformacion(v1, it) end
    return it
end

-- Las tomas de stock en PRO-BROLL (debajo de todo lo PRO y de los captions), llenando el cuadro.
local function poner_broll(tl, mp, caja, tomas, base, pista, fps)
    table.sort(tomas, function(a, b) return (tonumber(a.ini) or 0) < (tonumber(b.ini) or 0) end)
    local escala = 3
    pcall(function() escala = resolve.SCALE_FILL or 3 end)
    local puestas, fin = 0, -1
    for _, ev in ipairs(tomas) do
        local clip = importar(mp, caja, ev.archivo)
        if clip ~= nil and pista then
            local frames, fps_clip = 0, fps
            pcall(function() frames = tonumber(clip:GetClipProperty("Frames")) or 0 end)
            pcall(function() fps_clip = tonumber(clip:GetClipProperty("FPS")) or fps end)
            frames = math.min(frames, redondear((tonumber(ev.dur) or 2.0) * fps_clip))
            local ini = base + math.floor(tonumber(ev.ini) or 0)
            if frames > 1 and ini >= fin then
                local it = append(mp, { mediaPoolItem = clip, startFrame = 0, endFrame = frames - 1, recordFrame = ini, trackIndex = pista, mediaType = 1 })
                if it ~= nil then
                    fin = it:GetEnd()
                    puestas = puestas + 1
                    pcall(function() it:SetProperty("Scaling", escala) end)
                    pcall(function() it:SetName("PRO · B-roll " .. tostring(ev.palabra or "")) end)
                end
            end
        end
    end
    return puestas
end

-- Las pistas de los captions (y sus emojis): las que hay encima de las PRO que no son de PRO ni de los Efectos.
local function pistas_captions(tl)
    local n = math.floor(tonumber(tl:GetTrackCount("video")) or 0)
    local tope = 1
    for i = 1, n do if es_pro(nombre_pista(tl, "video", i)) then tope = i end end
    local out = {}
    for i = tope + 1, n do
        local nm = nombre_pista(tl, "video", i)
        if nm:sub(1, 4) ~= "PRO-" and nm:sub(1, 3) ~= "FX-" then out[#out + 1] = i end
    end
    return out
end

-- Re-aplicar no apila: los captions que subio una corrida anterior (llevan la marca) vuelven a su sitio si siguen donde se dejaron.
local function deshacer_subidas(tl)
    local vueltos = 0
    for _, i in ipairs(pistas_captions(tl)) do
        for _, it in ipairs(lista_api(tl:GetItemListInTrack("video", i))) do
            local ok, marcas = pcall(function() return it:GetMarkers() end)
            if ok and type(marcas) == "table" then
                for _, m in pairs(marcas) do
                    local dato = tostring(m.customData or "")
                    if dato == MARCA_EMOJI then
                        pcall(function() it:SetClipEnabled(true) end)
                        pcall(function() it:DeleteMarkerByCustomData(dato) end)
                    end
                    local antes, despues = dato:match("^ccpro%-subir:([%-%d%.]+):([%-%d%.]+)$")
                    if antes then
                        pcall(function()
                            if math.abs((tonumber(it:GetProperty("Tilt")) or 0) - tonumber(despues)) < 0.5 and it:SetProperty("Tilt", tonumber(antes)) then
                                vueltos = vueltos + 1
                            end
                        end)
                        pcall(function() it:DeleteMarkerByCustomData(dato) end)
                    end
                end
            end
        end
    end
    return vueltos
end

-- Sube (Tilt) los clips de los captions que EMPIEZAN dentro de cada bloque y les deja la marca. Devuelve cuantos movio.
-- Pone el Tilt de un clip de captions y deja (o actualiza) la marca con su Tilt ORIGINAL, para que re-aplicar lo devuelva a su sitio.
local function poner_tilt(it, nuevo)
    local original = 0
    pcall(function() original = tonumber(it:GetProperty("Tilt")) or 0 end)
    local ok, marcas = pcall(function() return it:GetMarkers() end)
    if ok and type(marcas) == "table" then
        for _, m in pairs(marcas) do
            local dato = tostring(m.customData or "")
            local antes = dato:match("^ccpro%-subir:([%-%d%.]+):")
            if antes then
                original = tonumber(antes) or original
                pcall(function() it:DeleteMarkerByCustomData(dato) end)
            end
        end
    end
    local ok2, r = pcall(function() return it:SetProperty("Tilt", nuevo) end)
    if ok2 and r then
        pcall(function() it:AddMarker(0, "Sand", "PRO · captions movidos", "", 1, string.format("%s:%.3f:%.3f", MARCA, original, nuevo)) end)
        return true
    end
    return false
end

local function subir_captions(tl, cues, base)
    local clips = {}
    for _, i in ipairs(pistas_captions(tl)) do
        for _, it in ipairs(lista_api(tl:GetItemListInTrack("video", i))) do clips[#clips + 1] = { it:GetStart(), it } end
    end
    local movidos = 0
    for _, c in ipairs(cues or {}) do
        local f0, f1, d = base + math.floor(tonumber(c.ini) or 0), base + math.floor(tonumber(c.fin) or 0), tonumber(c.subir) or 0
        if math.abs(d) >= 0.5 then
            for _, par in ipairs(clips) do
                if par[1] >= f0 - 1 and par[1] < f1 then
                    local antes = 0
                    pcall(function() antes = tonumber(par[2]:GetProperty("Tilt")) or 0 end)
                    if poner_tilt(par[2], antes + d) then movidos = movidos + 1 end
                end
            end
        end
    end
    return movidos
end

-- REGLA DEL USUARIO: ningun emoji tapa una cara. Los emojis de cada bloque que caen sobre una de sus 'caras' bajan debajo de la barbilla o
-- suben encima de la cabeza (lo que quede mas cerca dentro del cuadro). Devuelve cuantos aparto.
local function emojis_sin_cara(tl, cues, base)
    local W = tonumber(tl:GetSetting("timelineResolutionWidth")) or 1080
    local H = tonumber(tl:GetSetting("timelineResolutionHeight")) or 1920
    local emojis = {}
    for _, i in ipairs(pistas_captions(tl)) do
        if nombre_pista(tl, "video", i):upper():find("EMOJI", 1, true) then
            for _, it in ipairs(lista_api(tl:GetItemListInTrack("video", i))) do emojis[#emojis + 1] = { it:GetStart(), it } end
        end
    end
    local r, aire, apartados = 0.045, 0.015, 0
    for _, c in ipairs(cues or {}) do
        local caras = (type(c.caras) == "table") and c.caras or {}
        if #caras > 0 then
            local f0, f1 = base + math.floor(tonumber(c.ini) or 0), base + math.floor(tonumber(c.fin) or 0)
            for _, par in ipairs(emojis) do
                if par[1] >= f0 - 1 and par[1] < f1 then
                    local it, x, y = par[2], 0.5, 0.5
                    pcall(function() x = 0.5 + (tonumber(it:GetProperty("Pan")) or 0) / W; y = 0.5 - (tonumber(it:GetProperty("Tilt")) or 0) / H end)
                    local abajo, arriba, pisa = -1, 2, false
                    for _, k in ipairs(caras) do
                        if k[1] - r < x and x < k[3] + r and k[2] - r < y and y < k[4] + r then
                            pisa = true
                            abajo = math.max(abajo, k[4] + r + aire)
                            arriba = math.min(arriba, k[2] - r - aire)
                        end
                    end
                    if pisa then
                        local mejor = nil
                        for _, o in ipairs({ abajo, arriba }) do
                            if o >= 0.04 + r and o <= 0.96 - r and (mejor == nil or math.abs(o - y) < math.abs(mejor - y)) then mejor = o end
                        end
                        if mejor and poner_tilt(it, (0.5 - mejor) * H) then apartados = apartados + 1 end
                    end
                end
            end
        end
    end
    return apartados
end

-- Los captions DETRAS de la persona: la persona recortada en PRO-ENCIMA (la pista de mas arriba) en cada tramo, su velo suave en PRO-VELO
-- y la pila de los captions subida hasta la coronilla. Devuelve (tramos puestos, clips de captions movidos).
local function poner_encima(tl, mp, caja, tramos, base)
    local hay = false
    for _, t in ipairs(tramos) do if t.modo == "clip" then hay = true end end
    local i = indice(tl, PISTA_ENCIMA)
    if i then
        vaciar(tl, i)
        if i ~= math.floor(tonumber(tl:GetTrackCount("video")) or 0) or not hay then
            pcall(function() tl:DeleteTrack("video", i) end)
            i = nil
        end
    end
    if not hay then return 0, 0 end
    if not i then
        pcall(function() tl:AddTrack("video") end)
        i = math.floor(tonumber(tl:GetTrackCount("video")) or 1)
        tl:SetTrackName("video", i, PISTA_ENCIMA)
    end
    table.sort(tramos, function(a, b) return (tonumber(a.ini) or 0) < (tonumber(b.ini) or 0) end)
    local idx_velo = indice(tl, "PRO-VELO")
    local velos = {}
    if idx_velo then
        for _, x in ipairs(lista_api(tl:GetItemListInTrack("video", idx_velo))) do velos[#velos + 1] = { x:GetStart(), x:GetEnd() } end
    end
    local hechos, movidos, fin = 0, 0, -1
    for _, t in ipairs(tramos) do
        local f0, f1 = base + math.floor(tonumber(t.ini) or 0), base + math.floor(tonumber(t.fin) or 0)
        if f1 - f0 >= 6 and f0 >= fin then
            local it = poner_clip_persona(tl, mp, caja, t, f0, f1, i)
            if it ~= nil then
                fin = it:GetEnd()
                pcall(function() it:SetName("PRO · persona encima") end)
                pcall(function() it:SetClipColor("Orange") end)
                movidos = movidos + subir_captions(tl, t.cues, base)
                hechos = hechos + 1
                local libre = idx_velo ~= nil and t.velo ~= nil
                for _, v in ipairs(velos) do if v[1] < fin and f0 < v[2] then libre = false end end
                if libre then
                    local clip = importar(mp, caja, t.velo)
                    local r = clip and append(mp, { mediaPoolItem = clip, trackIndex = idx_velo, recordFrame = f0 }) or nil
                    if r ~= nil then
                        velos[#velos + 1] = { r:GetStart(), r:GetEnd() }
                        pcall(function() r:SetName("PRO · velo de los captions") end)
                    end
                end
            end
        end
    end
    return hechos, movidos
end

-- PRO-ICONOS, vacia, encima de los captions (se crea al final; PRO-ENCIMA, si hace falta, va despues y queda por encima).
local function pista_iconos(tl, hace_falta)
    local i = indice(tl, PISTA_ICONOS)
    if i then vaciar(tl, i); return i end
    if not hace_falta then return nil end
    pcall(function() tl:AddTrack("video") end)
    i = math.floor(tonumber(tl:GetTrackCount("video")) or 1)
    tl:SetTrackName("video", i, PISTA_ICONOS)
    return i
end

-- Apaga (con marca, para re-aplicar) el emoji del tema en los bloques donde va un icono 3D: uno solo, el 3D.
local function apagar_emojis(tl, ventanas, base)
    local apagados = 0
    for _, i in ipairs(pistas_captions(tl)) do
        if nombre_pista(tl, "video", i):upper():find("EMOJI", 1, true) then
            for _, it in ipairs(lista_api(tl:GetItemListInTrack("video", i))) do
                local s0 = it:GetStart()
                for _, v in ipairs(ventanas or {}) do
                    if s0 >= base + (tonumber(v[1]) or 0) and s0 < base + (tonumber(v[2]) or 0) then
                        local ok, r = pcall(function() return it:SetClipEnabled(false) end)
                        if ok and r then
                            pcall(function() it:AddMarker(0, "Sand", "PRO · emoji cambiado por un icono 3D", "", 1, MARCA_EMOJI) end)
                            apagados = apagados + 1
                        end
                        break
                    end
                end
            end
        end
    end
    return apagados
end

-- «Modo error»: el plano en gris un momento. Una copia del clip de V1 de ese tramo, encima, sin saturacion (SetCDL), misma transformacion.
local function poner_gris(tl, mp, tramos, base, pista)
    local puestos = 0
    for _, g in ipairs(tramos or {}) do
        local f0, f1 = base + math.floor(tonumber(g[1]) or 0), base + math.floor(tonumber(g[2]) or 0)
        local v1 = clip_v1(tl, f0, f1)
        local fx = false
        if v1 ~= nil then
            local ok, nombres = pcall(function() return v1:GetFusionCompNameList() end)
            for _, n in ipairs((ok and type(nombres) == "table") and nombres or {}) do if n == "CineCaptions FX" then fx = true end end
        end
        if v1 ~= nil and not fx and pista then
            local src0 = math.floor(tonumber(v1:GetLeftOffset()) or 0) + (f0 - v1:GetStart())
            local it = append(mp, { mediaPoolItem = v1:GetMediaPoolItem(), startFrame = src0, endFrame = src0 + (f1 - f0) - 1, recordFrame = f0, trackIndex = pista, mediaType = 1 })
            if it ~= nil then
                copiar_transformacion(v1, it)
                local ok, r = pcall(function() return it:SetCDL({ NodeIndex = "1", Slope = "1.0 1.0 1.0", Offset = "0.0 0.0 0.0", Power = "1.0 1.0 1.0", Saturation = "0.0" }) end)
                if ok and r then
                    pcall(function() it:SetName("PRO · gris") end)
                    puestos = puestos + 1
                else
                    pcall(function() tl:DeleteClips({ it }, false) end)
                end
            end
        end
    end
    return puestos
end

local function main()
    local r, diag, rechazados = obtener_resolve()
    if r == nil then
        local motivo
        if rechazados > 0 then
            motivo = "Encontre Resolve pero no me respondio. Si no hay un proyecto abierto, abrelo; si lo hay, relanza CineCaptions_Puente (Area de trabajo > Scripts > CineCaptions_Puente)."
        else
            motivo = "No pude conectar con Resolve. Corre este script desde Area de trabajo > Scripts > CineCaptions_EdicionPro"
        end
        fail(motivo .. "  |  Diagnostico: " .. tostring(diag))
    end
    resolve = r
    print("[Edicion PRO] version " .. VERSION)
    local carpeta, sep = carpeta_compartida()
    local datos, habia = cargar_tabla(carpeta .. sep .. "edicion_pro_plan.json")
    if not habia then fail("No hay ninguna Edicion PRO pendiente (edicion_pro_plan.json): la deja el programa al pulsar GO con la Edicion PRO activada.") end
    if type(datos) ~= "table" then fail("El plan de la Edicion PRO esta danado.") end
    local pm = resolve:GetProjectManager()
    local project = pm and pm:GetCurrentProject() or nil
    if project == nil then fail("No hay ningun proyecto abierto en Resolve.") end
    local tl = project:GetCurrentTimeline()
    if tl == nil then fail("No hay un timeline activo en Resolve.") end
    local mp = project:GetMediaPool()
    local fps = tonumber(datos.fps) or tonumber(tl:GetSetting("timelineFrameRate")) or 30
    local base = math.floor(tonumber(datos.inicio) or tonumber(tl:GetStartFrame()) or 0)
    local caja = caja_pro(mp)
    local v1_antes = #lista_api(tl:GetItemListInTrack("video", 1))
    local idx = pistas_pro(tl)
    local hay_iconos = false
    for _, g in ipairs((type(datos.graficos) == "table") and datos.graficos or {}) do if g.capa == "iconos" then hay_iconos = true end end
    idx[PISTA_ICONOS] = pista_iconos(tl, hay_iconos)
    local fin_pista = { [PISTA_ICONOS] = -1 }
    for _, n in ipairs(ORDEN) do fin_pista[n] = -1 end
    local puestos = { fondo = 0, velo = 0, detras = 0, delante = 0, iconos = 0, persona = 0, sonido = 0, broll = 0, encima = 0, movidos = 0, punch = 0,
                      emojis = 0, cambiados = 0, gris = 0 }
    local sin_poner = 0
    -- 1) los graficos OGraf
    local graficos = (type(datos.graficos) == "table") and datos.graficos or {}
    table.sort(graficos, function(a, b) return (tonumber(a.ini) or 0) < (tonumber(b.ini) or 0) end)
    for _, g in ipairs(graficos) do
        local nombre = CAPA[g.capa] or "PRO-DELANTE"
        local clip = importar(mp, caja, g.archivo)
        local ini = base + math.floor(tonumber(g.ini) or 0)
        if clip == nil or idx[nombre] == nil or ini < fin_pista[nombre] then
            sin_poner = sin_poner + 1
        else
            local item = append(mp, { mediaPoolItem = clip, trackIndex = idx[nombre], recordFrame = ini })
            if item == nil then
                sin_poner = sin_poner + 1
            else
                fin_pista[nombre] = item:GetEnd()
                pcall(function() item:SetName(tostring(g.nombre or "PRO")) end)
                pcall(function() item:SetFusionOutputCache("enabled") end)
                local c = (g.capa == "velo" or g.capa == "detras" or g.capa == "fondo" or g.capa == "iconos") and g.capa or "delante"
                puestos[c] = puestos[c] + 1
            end
        end
    end
    -- 2) el B-roll de stock, debajo de todo
    puestos.broll = poner_broll(tl, mp, caja, (type(datos.broll) == "table") and datos.broll or {}, base, idx["PRO-BROLL"], fps)
    puestos.gris = poner_gris(tl, mp, (type(datos.gris) == "table") and datos.gris or {}, base, idx["PRO-GRIS"])
    -- 3) la persona recortada con IA local (ProRes 4444 con alfa recto); antes, los punch-ins de V1 (el recorte copia su zoom)
    puestos.punch = punch_ins(tl, (type(datos.punch) == "table") and datos.punch or {})
    local personas = (type(datos.persona) == "table") and datos.persona or {}
    for _, p in ipairs(personas) do
        local f0, f1 = base + math.floor(tonumber(p.ini) or 0), base + math.floor(tonumber(p.fin) or 0)
        f1 = math.max(f1, fin_detras(tl, idx, f0))
        if f1 - f0 >= 6 and f0 >= fin_pista["PRO-PERSONA"] then
            local item = poner_clip_persona(tl, mp, caja, p, f0, f1, idx["PRO-PERSONA"])
            if item ~= nil then
                fin_pista["PRO-PERSONA"] = item:GetEnd()
                pcall(function() item:SetName("PRO · persona") end)
                pcall(function() item:SetClipColor("Orange") end)
                puestos.persona = puestos.persona + 1
            end
        end
    end
    -- 4) los captions DETRAS de la persona (la persona en la pista de mas arriba)
    deshacer_subidas(tl)                       -- re-aplicar no apila: primero, todo a su sitio
    local encima = (type(datos.encima) == "table") and datos.encima or {}
    puestos.encima, puestos.movidos = poner_encima(tl, mp, caja, encima, base)
    -- 4b) el resto de los captions, fuera de las caras; y ningun emoji encima de una cara
    local mover = (type(datos.mover) == "table") and datos.mover or {}
    puestos.movidos = puestos.movidos + subir_captions(tl, mover, base)
    local todos = {}
    for _, e in ipairs(encima) do for _, c in ipairs((type(e.cues) == "table") and e.cues or {}) do todos[#todos + 1] = c end end
    for _, c in ipairs(mover) do todos[#todos + 1] = c end
    puestos.emojis = emojis_sin_cara(tl, todos, base)
    if puestos.iconos > 0 then puestos.cambiados = apagar_emojis(tl, (type(datos.sin_emoji) == "table") and datos.sin_emoji or {}, base) end
    -- 5) el diseno de sonido: cada familia en su pista (PRO-WHOOSH, PRO-TEXTURA, PRO-RISER, PRO-HIT), clips enteros con su nivel
    local sonidos = (type(datos.sonidos) == "table") and datos.sonidos or {}
    local por_pista = {}
    for _, ev in ipairs(sonidos) do
        local n = ev.pista or PISTA_SONIDO
        por_pista[n] = por_pista[n] or {}
        table.insert(por_pista[n], ev)
    end
    local todas_audio = { PISTA_SONIDO, "PRO-WHOOSH", "PRO-TEXTURA", "PRO-RISER", "PRO-HIT" }
    for _, n in ipairs(todas_audio) do
        local ia = indice(tl, n, "audio")
        if ia then
            vaciar(tl, ia, "audio")
            if por_pista[n] == nil then pcall(function() tl:DeleteTrack("audio", ia) end) end
        end
    end
    for _, n in ipairs(todas_audio) do
        local lista = por_pista[n]
        if lista then
            local ia = indice(tl, n, "audio")
            if not ia then
                local ok = pcall(function() tl:AddTrack("audio", "stereo") end)
                if not ok then pcall(function() tl:AddTrack("audio") end) end
                ia = math.floor(tonumber(tl:GetTrackCount("audio")) or 1)
                tl:SetTrackName("audio", ia, n)
            end
            table.sort(lista, function(x, y) return (tonumber(x.ini) or 0) < (tonumber(y.ini) or 0) end)
            local fin = -1
            for _, ev in ipairs(lista) do
                local clip = importar(mp, caja, ev.archivo)
                local ini = base + math.floor(tonumber(ev.ini) or 0)
                local frames = math.max(2, redondear((tonumber(ev.dur) or 1.0) * fps))
                if clip ~= nil and ini >= fin then
                    local item = append(mp, { mediaPoolItem = clip, startFrame = 0, endFrame = frames - 1, recordFrame = ini, trackIndex = ia, mediaType = 2 })
                    if item ~= nil then
                        fin = ini + frames
                        puestos.sonido = puestos.sonido + 1
                        pcall(function() item:SetProperty("Volume", tonumber(ev.db) or -9) end)
                    end
                end
            end
        end
    end
    quitar_vacias(tl)
    local total = puestos.fondo + puestos.velo + puestos.detras + puestos.delante + puestos.iconos
    RESUMEN = string.format("Edicion PRO: %d graficos (%d detras, %d delante, %d escenas, %d velos), %d recortes de persona, captions detras de la persona en %d tramos (%d clips movidos, %d emojis apartados de la cara), %d iconos 3D (%d emojis cambiados), %d tramos en gris, %d tomas de B-roll, %d punch-ins, %d sonidos%s.",
        total, puestos.detras, puestos.delante, puestos.fondo, puestos.velo, puestos.persona, puestos.encima, puestos.movidos, puestos.emojis, puestos.iconos,
        puestos.cambiados, puestos.gris, puestos.broll, puestos.punch, puestos.sonido,
        sin_poner > 0 and string.format(", %d sin poner", sin_poner) or "")
    print(RESUMEN)
    if #lista_api(tl:GetItemListInTrack("video", 1)) < v1_antes then fail("ATENCION: V1 perdio clips al colocar la Edicion PRO") end
    if total == 0 and #graficos > 0 then fail("Resolve no coloco ningun grafico de la Edicion PRO") end
end

local ok, err = pcall(main)
if not ok then
    print("[Edicion PRO] termino con error: " .. tostring(err))
    guardar_resultado(false, tostring(err))
else
    guardar_resultado(true, RESUMEN)
end

-- No dejar el wrapper de print puesto (el Puente comparte estado de Lua).
print = _print_original

-- Free 21.1, sin io: el resultado viaja por el registro de Resolve (ver el epilogo de CineCaptions_SfxMarcadores.lua). Bajo el Puente se DEVUELVE (el Puente lo relata); a mano, un error() sin capturar lo deja en ResolveDebug.txt.
if SIN_IO then
    local reporte = "CINECAPTIONS_REPORTE|" .. json_resultado(ok, ok and RESUMEN or tostring(err), texto_para_reporte())
    if ENTREGA_PUENTE ~= nil then return reporte end
    error(reporte, 0)
end

-- Un script que falla tiene que fallar hacia afuera (el pcall(dofile) del Puente daria el trabajo por bueno).
if not ok then
    error(err, 0)
end
