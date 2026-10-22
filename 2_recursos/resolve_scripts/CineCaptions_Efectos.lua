-- CineCaptions · By Cinema Productions
-- 2_recursos/resolve_scripts/CineCaptions_Efectos.lua — los efectos visuales (intro, cortes, iconos, B-roll, sonidos, movimiento sobre V1) en Resolve Free.
--[[
CineCaptions_Efectos.lua
------------------------
Version en Lua para Resolve FREE (el Puente la corre con dofile) de "2_recursos/efectos/colocar_efectos.py", que es la de Studio (por el MCP).
Lee el plan que deja la app (efectos_plan.json; sin io, su sidecar .lua) y pone la intro, las transiciones de los cortes, los iconos flotantes, el
B-roll, los sonidos de la intro/cortes/gancho, la musica de fondo y la composicion de Fusion de cada clip de V1 (zoom, temblor, transiciones, fondo).
Reglas (las mismas que la gemela): nunca toca V1/A1 ni las pistas de los captions; las pistas «FX-…» se vacian y se vuelven a llenar en cada corrida;
los clips de una misma pista nunca se pisan; los archivos se importan una sola vez al bin «RCS · Efectos».
]]

local VERSION = "5.37 (efectos)"

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

local NOMBRE_SCRIPT = "CineCaptions_Efectos"
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
    print("[Efectos] ERROR: " .. msg)
    guardar_resultado(false, msg)
    error(msg, 0)
end

-- ---------------------------------------------------------------------
-- Gemela de 2_recursos/efectos/colocar_efectos.py (la de Studio, que corre por el MCP): pone la intro, las transiciones de los cortes, los iconos flotantes,
-- el B-roll, los sonidos y el movimiento sobre V1 (comps de Fusion) en pistas propias «FX-…». Nunca toca V1/A1 ni las pistas de los captions.
-- El plan lo deja la app en ~/DaVinciSubtitles/efectos_plan.json (y su sidecar .lua, que es lo que lee Free 21.1: sin io).
-- ---------------------------------------------------------------------
local PISTAS = {
    { "intro", "FX-INTRO" }, { "corte", "FX-CORTES" }, { "icono", "FX-ICONOS" }, { "numero", "FX-NUMEROS" }, { "pegatina", "FX-PEGATINAS" },
    { "enfasis", "FX-ENFASIS" }, { "overlay", "FX-OVERLAY" }, { "propio", "FX-PROPIOS" }, { "outro", "FX-OUTRO" }, { "broll", "FX-BROLL" },
}
local PISTA_SONIDO = "FX-SONIDO"
local PISTA_MUSICA = "FX-MUSICA"
local PISTA_VOZ_AI = "AI VOICE"              -- v5.34, AI Sound Director: la voz restaurada (una COPIA; A1 se apaga solo con ella ya puesta)
local PISTAS_AI = { "AI MUSIC", "AI AMBIENCE", "AI SFX MOTION", "AI SFX UI", "AI SFX IMPACTS", "AI SFX TONAL", "AI SFX TEXTURE" }
local PROPIAS = { "FX-", "PRO-", "AI ", "SFX" }  -- las pistas de audio que pone CineCaptions (las demas son del usuario)
local MAX_CARRILES = 8
local BIN = "RCS · Efectos"
local NOMBRE_COMP = "CineCaptions FX"

local function redondear(x) return math.floor(x + 0.5) end

-- «os.path.normcase(normpath())»: en Windows las rutas no distinguen mayusculas ni barras
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

local function carpeta_efectos(mp)
    local raiz = mp:GetRootFolder()
    for _, f in ipairs(lista_api(raiz:GetSubFolderList())) do
        if f:GetName() == BIN then return f end
    end
    return mp:AddSubFolder(raiz, BIN) or raiz
end

-- El clip del Media Pool de ese archivo / secuencia (se reusa si ya esta).
local function importar(mp, caja, ev)
    local buscada, pedido
    if type(ev.secuencia) == "table" then
        local patron, n = tostring(ev.secuencia.patron), math.floor(tonumber(ev.secuencia.n) or 0)
        buscada = norm((patron:gsub("%%04d", string.format("[0001-%04d]", n))))
        pedido = { { FilePath = patron, StartIndex = 1, EndIndex = n } }
    else
        buscada = norm(ev.archivo)
        pedido = { tostring(ev.archivo) }
    end
    local ya = buscar_clip(mp:GetRootFolder(), buscada)
    if ya ~= nil then return ya end
    local previa = nil
    pcall(function() previa = mp:GetCurrentFolder() end)
    pcall(function() mp:SetCurrentFolder(caja) end)
    local ok, nuevos = pcall(function() return mp:ImportMedia(pedido) end)
    if previa ~= nil then pcall(function() mp:SetCurrentFolder(previa) end) end
    if ok and type(nuevos) == "table" then return nuevos[1] end
    return nil
end

local function nombre_pista(tl, tipo, i)
    local nombre = ""
    pcall(function() nombre = tl:GetTrackName(tipo, i) or "" end)
    return nombre
end

-- El indice de la pista (de video o de audio, `sub` mono/stereo) con ese nombre (se crea si no esta) y sus clips de antes ya borrados.
local function pista(tl, nombre, tipo, sub)
    tipo = tipo or "video"
    for i = 1, math.floor(tonumber(tl:GetTrackCount(tipo)) or 0) do
        if nombre_pista(tl, tipo, i) == nombre then
            pcall(function()
                if tl:GetIsTrackLocked(tipo, i) then tl:SetTrackLock(tipo, i, false) end
            end)
            local viejos = lista_api(tl:GetItemListInTrack(tipo, i))
            if #viejos > 0 then pcall(function() tl:DeleteClips(viejos, false) end) end
            return i
        end
    end
    local creada = false
    if tipo == "audio" then
        local ok, r = pcall(function() return tl:AddTrack("audio", sub or "stereo") end)
        creada = ok and r == true
    end
    if not creada then
        local ok, r = pcall(function() return tl:AddTrack(tipo) end)
        if not (ok and r) then return nil end
    end
    local i = math.floor(tonumber(tl:GetTrackCount(tipo)) or 0)
    tl:SetTrackName(tipo, i, nombre)
    return i
end

-- Una pista FX de una vez anterior que ahora no lleva nada: se vacia y se quita (sin crear pistas nuevas que luego sobrarian).
local function vaciar_y_quitar(tl, nombre, tipo)
    tipo = tipo or "video"
    for i = math.floor(tonumber(tl:GetTrackCount(tipo)) or 0), 1, -1 do
        if nombre_pista(tl, tipo, i) == nombre then
            local viejos = lista_api(tl:GetItemListInTrack(tipo, i))
            if #viejos > 0 then pcall(function() tl:DeleteClips(viejos, false) end) end
            pcall(function() tl:DeleteTrack(tipo, i) end)
        end
    end
end

local function quitar_si_vacia(tl, nombre, tipo)
    tipo = tipo or "video"
    for i = math.floor(tonumber(tl:GetTrackCount(tipo)) or 0), 1, -1 do
        if nombre_pista(tl, tipo, i) == nombre and #lista_api(tl:GetItemListInTrack(tipo, i)) == 0 then
            pcall(function() tl:DeleteTrack(tipo, i) end)
        end
    end
end

-- v5.34, AI Sound Director (unico dueño del sonido): los clips de los sonidos de Simple (pistas cuyo nombre empieza por uno de `nombres`: «SFX»,
-- «SFX 2»...) se APAGAN -siguen ahi, y un GO con el director apagado los vuelve a poner-. Las pistas «AI SFX ...» no se tocan. Devuelve cuantos.
local function apagar_sfx(tl, nombres)
    local apagados = 0
    for i = 1, math.floor(tonumber(tl:GetTrackCount("audio")) or 0) do
        local nombre = string.upper(nombre_pista(tl, "audio", i) or "")
        local suyo = false
        for _, n in ipairs(nombres or {}) do
            local p = string.upper(tostring(n))
            if p ~= "" and string.sub(nombre, 1, #p) == p then suyo = true end
        end
        if suyo then
            for _, it in ipairs(lista_api(tl:GetItemListInTrack("audio", i))) do
                local ok, r = pcall(function() return it:GetClipEnabled() and it:SetClipEnabled(false) end)
                if ok and r then apagados = apagados + 1 end
            end
        end
    end
    return apagados
end

local function poner_prop(item, clave, valor)
    local ok, r = pcall(function() return item:SetProperty(clave, valor) end)
    if ok and r then return true end
    local ok2, r2 = pcall(function() return item:SetProperties({ [clave] = valor }) end)
    return ok2 and r2 == true
end

local function lista_api_texto(t)
    local salida = {}
    if type(t) ~= "table" then return salida end
    for _, v in ipairs(t) do salida[#salida + 1] = tostring(v) end
    return salida
end

-- La composicion de Fusion de cada clip de V1 (zoom, temblor, transiciones, fondo desenfocado): se quita la de la vez anterior y se importa la nueva.
-- `entradas`: [{inicio = fotograma del clip en el timeline, ruta = .comp | nil, nombre = nombre de la comp (por defecto NOMBRE_COMP)}].
-- v5.33: «CineCaptions Intro» = solo el zoom de la intro del gancho (con la PRO: colocar_pro si recorta a la persona encima). Devuelve cuantas se pusieron.
local function poner_movimiento(tl, entradas)
    local puestas = 0
    local por_inicio = {}
    local NOMBRE_INTRO = "CineCaptions Intro"
    for _, e in ipairs(entradas or {}) do por_inicio[math.floor(tonumber(e.inicio) or -1)] = e end
    for _, it in ipairs(lista_api(tl:GetItemListInTrack("video", 1))) do
        local e = por_inicio[math.floor(tonumber(it:GetStart()) or -2)]
        if e ~= nil then
            local ok, err = pcall(function()
                for _, n in ipairs(lista_api_texto(it:GetFusionCompNameList())) do
                    if n == NOMBRE_COMP or n == NOMBRE_INTRO then it:DeleteFusionCompByName(n) end
                end
                if e.ruta == nil or e.ruta == "" then return end
                local nombre = (e.nombre ~= nil and e.nombre ~= "") and e.nombre or NOMBRE_COMP
                local antes = {}
                for _, n in ipairs(lista_api_texto(it:GetFusionCompNameList())) do antes[n] = true end
                local comp = it:ImportFusionComp(e.ruta)
                if not comp then
                    print("  Resolve no acepto la composicion de movimiento")
                    return
                end
                local nuevo = nil
                for _, n in ipairs(lista_api_texto(it:GetFusionCompNameList())) do
                    if not antes[n] then nuevo = n; break end
                end
                if nuevo ~= nil then
                    pcall(function()
                        it:RenameFusionCompByName(nuevo, nombre)
                        it:LoadFusionCompByName(nombre)
                    end)
                end
                pcall(function() it:SetFusionOutputCache("enabled") end)   -- v5.5.4: se pre-renderiza en segundo plano (gemelo de colocar_efectos.py)
                puestas = puestas + 1
            end)
            if not ok then print("  (movimiento sobre V1: " .. tostring(err) .. ")") end
        end
    end
    return puestas
end

-- Los eventos de audio (sonidos de la intro, de los cortes, del gancho...) en pistas «nombre_base», «nombre_base 2»... (A1 no se toca): cada evento va a la primera pista donde no pisa a otro.
local function poner_audio(tl, mp, caja, fps, base, eventos, nombre_base)
    local carriles = {}
    local puestos, saltados = 0, 0
    table.sort(eventos, function(a, b) return (tonumber(a.ini) or 0) < (tonumber(b.ini) or 0) end)
    for _, ev in ipairs(eventos) do
        local clip = importar(mp, caja, ev)
        if clip == nil then
            print("  no pude importar el sonido " .. tostring(ev.asset))
            saltados = saltados + 1
        else
            local frames = math.max(2, redondear((tonumber(ev.dur) or 1.0) * fps))
            local ini = base + redondear((tonumber(ev.ini) or 0) * fps)
            local k = nil
            for i, c in ipairs(carriles) do
                if c.fin <= ini then k = i; break end
            end
            if k == nil and #carriles >= MAX_CARRILES then
                saltados = saltados + 1
            else
                if k == nil then
                    local nombre = (#carriles == 0) and nombre_base or string.format("%s %d", nombre_base, #carriles + 1)
                    local idx = pista(tl, nombre, "audio")
                    if idx == nil then
                        print("  no pude crear la pista de audio " .. nombre)
                        saltados = saltados + 1
                    else
                        carriles[#carriles + 1] = { idx = idx, fin = -1 }
                        k = #carriles
                    end
                end
                if k ~= nil then
                    local ok, nuevos = pcall(function()
                        return mp:AppendToTimeline({ { mediaPoolItem = clip, startFrame = 0, endFrame = frames - 1, recordFrame = ini, trackIndex = carriles[k].idx, mediaType = 2 } })
                    end)
                    local item = (ok and type(nuevos) == "table") and nuevos[1] or nil
                    if not item then
                        saltados = saltados + 1
                    else
                        carriles[k].fin = ini + frames
                        pcall(function() item:SetName(string.format("%s · %s", nombre_base, tostring(ev.asset or ""))) end)
                        puestos = puestos + 1
                    end
                end
            end
        end
    end
    -- las pistas de una vez anterior que ya no hacen falta
    for i = #carriles + 1, MAX_CARRILES do
        vaciar_y_quitar(tl, string.format("%s %d", nombre_base, i), "audio")
    end
    if #carriles == 0 then vaciar_y_quitar(tl, nombre_base, "audio") end
    return puestos, saltados
end

local function indice_pista(tl, nombre, tipo)
    for i = 1, math.floor(tonumber(tl:GetTrackCount(tipo or "audio")) or 0) do
        if nombre_pista(tl, tipo or "audio", i) == nombre then return i end
    end
    return nil
end

local function empieza_con(s, prefijos)
    for _, p in ipairs(prefijos) do
        if s:sub(1, #p) == p then return true end
    end
    return false
end

-- v5.34, AI Sound Director: la voz restaurada (una COPIA: el audio original sigue en A1) en la pista «AI VOICE». A1 se apaga SOLO despues de
-- comprobar que la copia quedo puesta entera y en su sitio; si algo falla, la copia se quita y A1 queda encendida. Sin evento (director apagado o
-- voz que no hacia falta tocar): AI VOICE fuera y A1 vuelve a sonar. Con otras pistas de audio del usuario la voz original no se sustituye.
-- Gemelo de _poner_voz_ai (colocar_efectos.py). Devuelve (puestas, nota).
local function poner_voz_ai(tl, mp, caja, fps, base, eventos)
    local ev = nil
    for _, e in ipairs(eventos) do
        if e.tipo == "voz_ai" and e.archivo then ev = e; break end
    end
    local function a1_encendida() pcall(function() tl:SetTrackEnable("audio", 1, true) end) end
    if ev == nil then
        if indice_pista(tl, PISTA_VOZ_AI, "audio") == nil then return 0, "" end
        vaciar_y_quitar(tl, PISTA_VOZ_AI, "audio")
        a1_encendida()
        return 0, "AI VOICE quitada: la voz original (A1) vuelve a sonar"
    end
    local function deshacer(motivo)
        vaciar_y_quitar(tl, PISTA_VOZ_AI, "audio")
        a1_encendida()
        return 0, motivo .. ": la voz original sigue en A1"
    end
    local propias = {}
    for _, p in ipairs(PROPIAS) do propias[#propias + 1] = p end
    if type(ev.propias) == "table" then
        for _, p in ipairs(ev.propias) do if p and tostring(p) ~= "" then propias[#propias + 1] = tostring(p) end end
    end
    local ajenas = {}
    for i = 2, math.floor(tonumber(tl:GetTrackCount("audio")) or 0) do
        local nombre = nombre_pista(tl, "audio", i)
        if not empieza_con(nombre, propias) then
            local activa = true
            pcall(function() activa = tl:GetIsTrackEnabled("audio", i) ~= false end)
            if activa and #lista_api(tl:GetItemListInTrack("audio", i)) > 0 then ajenas[#ajenas + 1] = (nombre ~= "" and nombre or ("A" .. i)) end
        end
    end
    if #ajenas > 0 then return deshacer("hay otras pistas de audio con clips (" .. table.concat(ajenas, ", ", 1, math.min(3, #ajenas)) .. ")") end
    local a1 = lista_api(tl:GetItemListInTrack("audio", 1))
    table.sort(a1, function(x, y) return x:GetStart() < y:GetStart() end)
    local frames = math.max(2, redondear((tonumber(ev.dur) or 0) * fps))
    local ini = base + redondear((tonumber(ev.ini) or 0) * fps)
    if #a1 == 0 then return deshacer("A1 esta vacia") end
    local tolerancia = math.max(3, redondear(0.5 * fps))      -- (el audio de un video puede acabar unos fotogramas antes que su imagen)
    if math.abs(a1[1]:GetStart() - ini) > 1 or math.abs(a1[#a1]:GetEnd() - (ini + frames)) > tolerancia then
        return deshacer(string.format("la copia no cuadra con A1 (A1 %d-%d, copia %d-%d)", a1[1]:GetStart(), a1[#a1]:GetEnd(), ini, ini + frames))
    end
    local clip = importar(mp, caja, ev)
    if clip == nil then return deshacer("no pude importar la voz restaurada") end
    vaciar_y_quitar(tl, PISTA_VOZ_AI, "audio")                -- re-aplicar no apila: una pista nueva con un solo clip
    local idx = pista(tl, PISTA_VOZ_AI, "audio", (tonumber(ev.canales) or 2) == 1 and "mono" or "stereo")
    if idx == nil then return deshacer("no pude crear la pista AI VOICE") end
    local ok, nuevos = pcall(function()
        return mp:AppendToTimeline({ { mediaPoolItem = clip, startFrame = 0, endFrame = frames - 1, recordFrame = ini, trackIndex = idx, mediaType = 2 } })
    end)
    local puestos = lista_api(tl:GetItemListInTrack("audio", idx))
    if not (ok and type(nuevos) == "table" and nuevos[1]) or #puestos ~= 1 or math.abs(puestos[1]:GetStart() - ini) > 1
            or math.abs(puestos[1]:GetDuration() - frames) > 2 then
        return deshacer("AI VOICE no quedo bien puesta")
    end
    pcall(function() puestos[1]:SetName("AI VOICE · " .. tostring(ev.backend or "voz restaurada")) end)
    local apagada = false
    pcall(function()
        tl:SetTrackEnable("audio", 1, false)
        apagada = tl:GetIsTrackEnabled("audio", 1) == false
    end)
    if not apagada then return deshacer("no pude apagar A1 (sonarian las dos voces)") end
    return 1, "AI VOICE puesta y A1 apagada (reversible: al apagar el director, A1 vuelve)"
end

local function sin_pista(eventos)
    local salida = {}
    for _, e in ipairs(eventos) do
        if not e.pista then salida[#salida + 1] = e end
    end
    return salida
end

local function de_tipo(eventos, tipo)
    local salida = {}
    for i, e in ipairs(eventos) do
        if e.tipo == tipo then salida[#salida + 1] = e end
    end
    return salida
end

local RESUMEN = ""

local function main()
    local r, diag, rechazados = obtener_resolve()
    if r == nil then
        local motivo
        if rechazados > 0 then
            motivo = "Encontre Resolve pero no me respondio. Si no hay un proyecto abierto, abrelo; si lo hay, relanza CineCaptions_Puente (Area de trabajo > Scripts > CineCaptions_Puente)."
        else
            motivo = "No pude conectar con Resolve. Corre este script desde Area de trabajo > Scripts > CineCaptions_Efectos"
        end
        fail(motivo .. "  |  Diagnostico: " .. tostring(diag))
    end
    resolve = r

    print("[Efectos] version " .. VERSION)
    print("[Efectos] entrega del Puente: " .. (ENTREGA_PUENTE and "recibida" or "no (corrida manual o Puente viejo)"))

    local carpeta, sep = carpeta_compartida()
    local datos, habia = cargar_tabla(carpeta .. sep .. "efectos_plan.json")
    if not habia then fail("No hay ningun plan de efectos pendiente (efectos_plan.json): lo deja el programa al pulsar GO con efectos visuales.") end
    if type(datos) ~= "table" then fail("El plan de efectos esta danado.") end

    local pm = resolve:GetProjectManager()
    local project = pm and pm:GetCurrentProject() or nil
    if project == nil then fail("No hay ningun proyecto abierto en Resolve.") end
    local tl = project:GetCurrentTimeline()
    if tl == nil then fail("No hay un timeline activo en Resolve.") end
    print("Proyecto: " .. tostring(project:GetName()) .. "  |  Timeline: " .. tostring(tl:GetName()))
    local mp = project:GetMediaPool()
    local fps = tonumber(datos.fps) or tonumber(tl:GetSetting("timelineFrameRate")) or 30
    local base = math.floor(tonumber(datos.inicio) or tonumber(tl:GetStartFrame()) or 0) + math.floor(tonumber(datos.offset_frames) or 0)
    local modos = {}
    pcall(function() modos.screen = resolve.COMPOSITE_SCREEN end)
    pcall(function() modos.multiply = resolve.COMPOSITE_MULTIPLY end)
    local ESCALA_LLENAR = 3
    pcall(function() ESCALA_LLENAR = resolve.SCALE_FILL or 3 end)
    local caja = carpeta_efectos(mp)
    local v1_antes = #lista_api(tl:GetItemListInTrack("video", 1))
    local eventos_todos = (type(datos.eventos) == "table") and datos.eventos or {}
    local puestos = { movimiento = 0 }
    for _, p in ipairs(PISTAS) do puestos[p[1]] = 0 end
    local solo_ai = datos.solo_ai == true                  -- v5.34: solo las pistas del AI Sound Director (la limpieza al apagarlo)
    local solo_audio = datos.solo_audio == true or solo_ai  -- sin efectos visuales: solo el audio extra (musica, sonidos); las pistas visuales no se tocan
    if not solo_audio then puestos.movimiento = poner_movimiento(tl, datos.v1) end
    local saltados = 0
    local por_pista = {}
    if not solo_audio then
        for _, par in ipairs(PISTAS) do
            local tipo, nombre = par[1], par[2]
            local eventos = de_tipo(eventos_todos, tipo)
            table.sort(eventos, function(a, b) return (tonumber(a.ini) or 0) < (tonumber(b.ini) or 0) end)
            if #eventos == 0 then
                if tipo ~= "broll" then vaciar_y_quitar(tl, nombre) end         -- la pista reservada de B-roll se queda (bloqueada) para la proxima vez
            else
                local hay_broll = false
                if tipo == "broll" then
                    for i = 1, math.floor(tonumber(tl:GetTrackCount("video")) or 0) do
                        if nombre_pista(tl, "video", i) == nombre then hay_broll = true end
                    end
                end
                if tipo == "broll" and not hay_broll then
                    print("  B-roll: falta la pista reservada FX-BROLL (debajo de los captions): no se pone para no tapar los subtitulos")
                    saltados = saltados + #eventos
                else
                    local idx = pista(tl, nombre, "video")
                    if idx == nil then
                        print("  no pude crear la pista " .. nombre)
                        saltados = saltados + #eventos
                    else
                        por_pista[tipo] = idx
                        local fin_anterior = -1
                        for _, ev in ipairs(eventos) do
                            local clip = importar(mp, caja, ev)
                            if clip == nil then
                                print(string.format("  no pude importar el efecto %s (%s)", tipo, tostring(ev.asset)))
                                saltados = saltados + 1
                            else
                                local frames = math.floor(tonumber(clip:GetClipProperty("Frames")) or 0)
                                local fps_clip = tonumber(clip:GetClipProperty("FPS")) or fps
                                if fps_clip <= 0 then fps_clip = fps end
                                if frames <= 1 then
                                    saltados = saltados + 1
                                else
                                    if ev.dur then            -- un tramo del clip (el ultimo bucle de un overlay, p. ej.)
                                        frames = math.max(2, math.min(frames, redondear(tonumber(ev.dur) * fps_clip)))
                                    end
                                    local dur_tl = redondear(frames * fps / fps_clip)         -- lo que dura en el timeline (fotogramas)
                                    local ini = base + redondear((tonumber(ev.ini) or 0) * fps)
                                    if tipo == "corte" then ini = ini - math.floor(dur_tl / 2) end         -- el corte cae en medio del efecto
                                    ini = math.max(base, ini)
                                    if fin_anterior - 2 <= ini and ini < fin_anterior then ini = fin_anterior end         -- redondeos entre bucles seguidos: se pegan, no se saltan
                                    if ini < fin_anterior then
                                        saltados = saltados + 1                                    -- nunca se pisan dos clips de la misma pista
                                    else
                                        local ok, nuevos = pcall(function()
                                            return mp:AppendToTimeline({ { mediaPoolItem = clip, startFrame = 0, endFrame = frames - 1, recordFrame = ini, trackIndex = idx, mediaType = 1 } })
                                        end)
                                        local item = (ok and type(nuevos) == "table") and nuevos[1] or nil
                                        if not item then
                                            saltados = saltados + 1
                                        else
                                            fin_anterior = ini + dur_tl
                                            if tipo == "broll" then poner_prop(item, "Scaling", ESCALA_LLENAR) end        -- la toma llena el cuadro
                                            if modos[ev.modo] ~= nil then
                                                if not poner_prop(item, "CompositeMode", modos[ev.modo]) then print("  (no pude poner el modo " .. tostring(ev.modo) .. ")") end
                                            end
                                            if ev.opacidad ~= nil and (tonumber(ev.opacidad) or 100) < 99.5 then
                                                if not poner_prop(item, "Opacity", tonumber(ev.opacidad)) then print("  (no pude poner la opacidad)") end
                                            end
                                            pcall(function() item:SetName(string.format("%s · %s", nombre, tostring(ev.asset or ""))) end)
                                            puestos[tipo] = puestos[tipo] + 1
                                        end
                                    end
                                end
                            end
                        end
                    end
                end
            end
        end
    end
    -- los sonidos (intro, cortes, gancho...) en pistas «FX-SONIDO», «FX-SONIDO 2»... y la musica de fondo en «FX-MUSICA» (el audio del video, en A1, no se toca)
    local s1, s2 = 0, 0
    if not solo_ai then
        puestos.sonido, s1 = poner_audio(tl, mp, caja, fps, base, sin_pista(de_tipo(eventos_todos, "sonido")), PISTA_SONIDO)
        puestos.musica, s2 = poner_audio(tl, mp, caja, fps, base, sin_pista(de_tipo(eventos_todos, "musica")), PISTA_MUSICA)
    end
    saltados = saltados + s1 + s2
    -- v5.34, AI Sound Director: sus pistas (por NOMBRE, nunca por indice) y la voz restaurada; sin sus eventos, sus pistas se quitan y A1 vuelve
    puestos.ai = 0
    local existentes = {}
    for i = 1, math.floor(tonumber(tl:GetTrackCount("audio")) or 0) do existentes[nombre_pista(tl, "audio", i)] = true end
    local pedidos_ai = 0
    for _, nombre in ipairs(PISTAS_AI) do
        local evs = {}
        for _, e in ipairs(eventos_todos) do if e.pista == nombre then evs[#evs + 1] = e end end
        pedidos_ai = pedidos_ai + #evs
        if #evs > 0 or existentes[nombre] then
            local n_ai, s_ai = poner_audio(tl, mp, caja, fps, base, evs, nombre)
            puestos.ai = puestos.ai + n_ai
            saltados = saltados + s_ai
        end
    end
    if type(datos.apagar_sfx) == "table" and (puestos.ai > 0 or pedidos_ai == 0) then   -- solo con los sonidos del director ya puestos (o su silencio a proposito)
        local apagados = apagar_sfx(tl, datos.apagar_sfx)
        if apagados > 0 then print(string.format("  %d sonidos de Simple apagados (los decide el AI Sound Director)", apagados)) end
    end
    local nota_voz
    puestos.voz, nota_voz = poner_voz_ai(tl, mp, caja, fps, base, eventos_todos)
    if nota_voz ~= "" then print("  " .. nota_voz) end
    for _, par in ipairs(PISTAS) do
        if not solo_audio and por_pista[par[1]] and puestos[par[1]] == 0 and par[1] ~= "broll" then quitar_si_vacia(tl, par[2]) end
    end
    local partes, total = {}, 0
    local orden = { "movimiento" }
    for _, p in ipairs(PISTAS) do orden[#orden + 1] = p[1] end
    orden[#orden + 1] = "sonido"
    orden[#orden + 1] = "musica"
    orden[#orden + 1] = "ai"
    orden[#orden + 1] = "voz"
    for _, k in ipairs(orden) do
        local v = puestos[k] or 0
        total = total + v
        if v > 0 then partes[#partes + 1] = string.format("%d %s", v, k) end
    end
    RESUMEN = string.format("Efectos: %s (%d sin poner).", table.concat(partes, ", "), saltados)
    print(RESUMEN)
    local v1_ahora = #lista_api(tl:GetItemListInTrack("video", 1))
    if v1_ahora < v1_antes then          -- nunca deberia pasar: se avisa en voz alta en vez de callar
        fail(string.format("ATENCION: V1 tenia %d clip(s) y ahora tiene %d tras colocar los efectos", v1_antes, v1_ahora))
    end
    local reales = 0                     -- (la voz que no se sustituye no es un fallo)
    for _, e in ipairs(eventos_todos) do if e.tipo ~= "voz_ai" then reales = reales + 1 end end
    if total == 0 and reales > 0 then fail("Resolve no coloco ningun efecto") end
end

local ok, err = pcall(main)
if not ok then
    print("[Efectos] termino con error: " .. tostring(err))
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
