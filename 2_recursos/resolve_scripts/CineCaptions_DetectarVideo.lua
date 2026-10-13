-- CineCaptions · By Cinema Productions
-- 2_recursos/resolve_scripts/CineCaptions_DetectarVideo.lua — renderiza el audio del timeline activo (Resolve Free).
--[[
CineCaptions_DetectarVideo.lua
--------------------
Version en Lua de "CineCaptions - Detectar Video.py".

Corre DENTRO de Resolve (Area de trabajo > Scripts > Utility). Version para
Resolve FREE.

Renderiza SOLO el audio de la linea de tiempo activa a
<datos locales>/CineCaptions/audio (fuera de la vista), y deja la ruta en
~/DaVinciSubtitles/video_detectado.json para que la ventana la lea.

Si el render falla, cae al plan B: el archivo del clip mas largo de la
pista de video 1.
]]

local VERSION = "5.5.1 (detectar video)"

-- La ENTREGA del Puente (v1.0.43): el resolve validado llega como
-- argumento del chunk, porque las globales del Puente NO cruzan el
-- dofile en el Lua de Resolve (entornos aislados por script; medido el
-- 01-09 con el diagnostico del cliente: candidatos: 3 y ni rastro del
-- prestamo, con el Puente latiendo al lado). Lanzado desde el menu no
-- llegan argumentos y esto queda en nil.
local ENTREGA_PUENTE = ({...})[1]
if type(ENTREGA_PUENTE) ~= "table" then ENTREGA_PUENTE = nil end
-- v5.4.45: carpeta INTERNA (nada a la vista del usuario, ya no en Descargas).
local NOMBRE_CARPETA_AUDIO = "audio"
local PRESET_PROPIO = "CineCaptions - Solo audio"
local CODEC_AUDIO = "aac"
local BITRATE_AUDIO = 256000
local SAMPLE_RATE = 48000
local TIMEOUT_RENDER_SEG = 1800
local EXT_AUDIO = { mp4 = true, m4a = true, aac = true, wav = true,
                    aif = true, aiff = true, mp3 = true, mov = true, mxf = true }

-- ---------------------------------------------------------------------
-- Utilidades
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

-- Que globales de Lua da ESTE Resolve, para la cabecera. 21.1 quito
-- 'package' sin avisar y lo proximo que quite tiene que verse en una
-- captura. Se mira SIN indexar: nombrar un global ausente da nil; indexarlo
-- es justo lo que reventaba.
local function globales_lua()
    local partes = {}
    for _, par in ipairs({ { "package", package }, { "debug", debug },
                           { "loadfile", loadfile }, { "dofile", dofile },
                           { "io", io }, { "os", os }, { "_G", _G } }) do
        partes[#partes + 1] = par[1] .. "=" .. (par[2] ~= nil and "si" or "NO")
    end
    return "lua: " .. table.concat(partes, " ")
end
local SEP = es_windows() and "\\" or "/"

-- Free 21.1 capo io en el menu de Scripts (medido el 16-09; v3.1.5/v3.1.6):
-- sin io no se escribe nada -ni el json del video ni el registro- y el
-- resultado viaja por el registro de Resolve (ver el epilogo). Tampoco hay
-- os.remove: ver renderizar_audio.
local SIN_IO = (io == nil)

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

-- ---------------------------------------------------------------------
-- Registro en disco (ver la explicacion larga en CineCaptions_Subtitulos.lua)
-- ---------------------------------------------------------------------
-- Sin esto, todo lo que informa el script va solo a la consola de Resolve
-- y el usuario que no la tiene abierta ve "no pasa nada".
local NOMBRE_SCRIPT = "CineCaptions_DetectarVideo"
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

-- El MISMO json que lee resolve_bridge.ultimo_resultado(): al archivo con io,
-- y por el registro de Resolve sin io (v3.1.6). 'texto' y 'video' son
-- opcionales y van al FINAL a proposito: si el registro recortara la linea,
-- la cabecera (ok, mensaje, cuando) sobrevive y la app la rescata. 'video'
-- es el json de video_detectado.json, que sin io no se pudo escribir.
local function json_resultado(ok, mensaje, texto, video_json)
    local extra = ""
    if texto ~= nil then
        extra = extra .. string.format(', "texto": "%s"', json_escapar(texto))
    end
    if video_json ~= nil then
        extra = extra .. ', "video": ' .. video_json
    end
    return string.format(
        '{"script": "%s", "version": "%s", "ok": %s, "mensaje": "%s",'
        .. ' "cuando": %d%s}',
        NOMBRE_SCRIPT, json_escapar(VERSION),
        tostring(ok and true or false), json_escapar(mensaje), os.time(), extra)
end

local function guardar_resultado(ok, mensaje)
    local carpeta = carpeta_compartida()
    escribir_archivo(carpeta .. SEP .. "ultimo_resultado.txt",
                     table.concat(_salida, "\n"))
    escribir_archivo(carpeta .. SEP .. "ultimo_resultado.json",
                     json_resultado(ok, mensaje))
end

-- Lo ultimo del registro, recortado, para el reporte que viaja por el
-- registro de Resolve cuando no hay io (ver el epilogo). Gemela de la de
-- CineCaptions_Subtitulos.
local function texto_para_reporte()
    local inicio = math.max(1, #_salida - 24)
    local cola = {}
    for i = inicio, #_salida do
        cola[#cola + 1] = _salida[i]
    end
    local texto = table.concat(cola, "\n")
    if #texto > 1300 then texto = texto:sub(-1300) end
    -- Las lineas de capacidades (bmd:/lua:) cierran casos con una captura:
    -- van SIEMPRE, aunque la cola las haya dejado atras.
    local cab = {}
    for i = 1, inicio - 1 do
        local l = _salida[i]
        if l:find("bmd:", 1, true) or l:sub(1, 4) == "lua:" then
            cab[#cab + 1] = l
        end
    end
    if #cab > 0 then texto = table.concat(cab, "\n") .. "\n" .. texto end
    return texto
end

-- Recorrer una lista devuelta por la API de Resolve.
-- Ver la explicacion larga en CineCaptions_Subtitulos.lua: esas listas traen una
-- clave extra con el conteo, y pairs() la entregaba como un elemento mas
-- (un numero). Aca afectaba a la lista de presets de render: el preset de
-- solo audio no se elegia bien, el render fallaba y caia al plan B, que
-- devolvia el clip mas largo de V1 en vez del audio del timeline.
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

-- OJO con io.popen y os.execute en Windows: cada llamada arranca un cmd.exe,
-- y como Resolve es un proceso grafico eso ABRE UNA VENTANA DE CONSOLA que
-- parpadea encima. Aqui es un destello por accion -molesto pero soportable-;
-- en el bucle del Puente eran cuatro por segundo y dejaban Resolve inusable.
--
-- Fusion expone las mismas operaciones de forma nativa (bmd.direxists,
-- bmd.createdir, bmd.readdir) y esas no lanzan nada. Se usan cuando estan y
-- se deja el camino de siempre como respaldo.
-- Que primitivas nativas tiene este Resolve. Se mira una vez y se imprime,
-- para que un solo screenshot baste si algo vuelve a fallar.
local CAP = {
    wait = (bmd ~= nil and bmd.wait ~= nil),
    readdir = (bmd ~= nil and bmd.readdir ~= nil),
    createdir = (bmd ~= nil and bmd.createdir ~= nil),
    direxists = (bmd ~= nil and bmd.direxists ~= nil),
}

local function capacidades()
    local partes = {}
    for _, k in ipairs({ "wait", "readdir", "createdir", "direxists" }) do
        partes[#partes + 1] = k .. "=" .. (CAP[k] and "si" or "NO")
    end
    return "bmd: " .. table.concat(partes, " ") .. "  |  " .. globales_lua()
end

-- En Windows NUNCA se ejecuta shell: abre una ventana de consola encima de
-- Resolve. Los respaldos quedan para macOS y Linux, donde no abren nada.
-- Y SIN 'io' TAMPOCO: en el menu de Free 21.1 no hay io ni os.execute
-- (medido), asi que cualquier respaldo de shell revienta. La guarda va aqui,
-- en la CLASE, y no en cada sitio: en macOS TODOS los respaldos son
-- alcanzables (en Windows se cortan antes) y el primero que se olvide mata el
-- script mudo. Paso el 17-09: el Puente 1.0.36 de un cliente con Mac Free
-- 21.1 moria en el io.popen de listar_dir nada mas arrancar, con el latido ya
-- escrito y sin un solo error que la app pudiera enseñar. Se miran los
-- globales DIRECTO (no SIN_IO) para no depender del orden de declaracion.
local function puede_usar_shell()
    return not es_windows() and io ~= nil and os.execute ~= nil
end

local function existe_dir(ruta)
    if CAP.direxists then
        local ok, hay = pcall(function() return bmd.direxists(ruta) end)
        if ok then return hay and true or false end
    end
    -- Sin io no hay sonda posible: "no existe" y crear_dir lo intenta por
    -- bmd.createdir (el render de Resolve crea su carpeta de todos modos).
    if SIN_IO then return false end
    -- Respaldo SIN procesos: si se puede crear un archivo dentro, la carpeta
    -- existe. Se borra enseguida. Es C puro y sirve en los dos sistemas.
    local prueba = ruta .. SEP .. ".cinecaptions_probe"
    local f = io.open(prueba, "w")
    if f then
        f:close()
        os.remove(prueba)
        return true
    end
    if not puede_usar_shell() then return false end
    local p = io.popen('[ -d "' .. ruta .. '" ] && echo si')
    if not p then return false end
    local r = p:read("*a"); p:close()
    return r ~= nil and r:match("si") ~= nil
end

local function crear_dir(ruta)
    if CAP.createdir then
        local ok = pcall(function() return bmd.createdir(ruta) end)
        if ok then return end
    end
    if existe_dir(ruta) then return end
    if puede_usar_shell() then
        os.execute('mkdir -p "' .. ruta .. '"')
        return
    end
    print("[Detectar Video] Aviso: no pude crear " .. ruta
          .. " sin abrir una consola. Crea esa carpeta a mano si algo falla.")
end

local function listar(carpeta)
    -- Devuelve un set {nombre=true} de los archivos de una carpeta.
    local nombres = {}
    if CAP.readdir then
        local ok, entradas = pcall(function()
            return bmd.readdir(carpeta .. SEP .. "*")
        end)
        if ok and type(entradas) == "table" then
            local hubo = false
            for _, e in ipairs(entradas) do
                local n = (type(e) == "table") and e.Name or e
                if type(n) == "string" and n ~= "." and n ~= ".." then
                    nombres[n] = true
                    hubo = true
                end
            end
            -- Vacio no se da por bueno: puede ser una carpeta vacia de verdad
            -- o que bmd.readdir no entendiera la ruta. Ante la duda, se
            -- comprueba con el camino de siempre.
            if hubo then return nombres end
        end
    end
    -- Respaldo con shell, SOLO fuera de Windows (ver puede_usar_shell).
    --
    -- Ojo con la trampa que traia esto: bmd.readdir sobre una carpeta VACIA
    -- devuelve vacio legitimamente, y como aqui se daba por "no entendio la
    -- ruta", se caia al popen. La carpeta de render esta vacia justo mientras
    -- el render no ha terminado, asi que en Windows saltaba una consola cada
    -- vez. Ahora, sin shell disponible, se devuelve el vacio y ya.
    if not puede_usar_shell() or SIN_IO then
        if not CAP.readdir then
            print("[Detectar Video] Aviso: sin bmd.readdir no puedo listar "
                  .. carpeta .. " sin abrir una consola. "
                  .. "Puede que no encuentre el audio recien renderizado.")
        end
        return nombres
    end
    local p = io.popen('ls -1 "' .. carpeta .. '" 2>/dev/null')
    if p then
        for linea in p:lines() do nombres[linea] = true end
        p:close()
    end
    return nombres
end

local function tam_archivo(ruta)
    if SIN_IO then return 0 end
    local f = io.open(ruta, "rb")
    if not f then return 0 end
    local t = f:seek("end") or 0
    f:close()
    return t
end

local function dormir(seg)
    if bmd ~= nil and bmd.wait ~= nil then
        bmd.wait(seg)
    else
        local hasta = os.clock() + seg
        while os.clock() < hasta do end
    end
end

-- Marcas de entrada y salida del timeline, en fotogramas absolutos.
--
-- Devuelve nil si no hay marcas, o si esta version de Resolve no expone
-- GetMarkInOut (llego en la 18.5). En los dos casos se renderiza el timeline
-- entero, que es lo que se hacia siempre: una funcion que no existe no puede
-- ser motivo de que el programa deje de funcionar.
--
-- La API devuelve {video = {startFrame, endFrame}, audio = {...}}. Aqui
-- interesa el AUDIO -es lo que se transcribe-, con el video de respaldo por
-- si alguien marco solo la pista de video.
local MARCA_APLICADA = nil
-- El json del video detectado, para que el epilogo lo mande por el registro
-- de Resolve cuando no hay io (v3.1.6).
local VIDEO_REPORTADO = nil

local function marcas_de(timeline)
    local ok, marcas = pcall(function() return timeline:GetMarkInOut() end)
    if not ok or type(marcas) ~= "table" then return nil end
    for _, cual in ipairs({ "audio", "video" }) do
        local m = marcas[cual]
        if type(m) == "table" then
            local ini = tonumber(m.startFrame)
            local fin = tonumber(m.endFrame)
            if ini and fin and fin > ini then
                return math.floor(ini), math.floor(fin)
            end
        end
    end
    return nil
end

local function nombre_seguro(texto)
    local limpio = texto:gsub("[^%w%s%-_]", "_"):gsub("^%s*(.-)%s*$", "%1")
    if limpio == "" then return "timeline" end
    return limpio
end

local function ext_de(nombre)
    local e = nombre:match("%.([^%.]+)$")
    return e and e:lower() or ""
end

-- Escapa una string para meterla en JSON.
local function json_str(s)
    s = tostring(s or "")
    s = s:gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n"):gsub("\t", "\\t")
    return '"' .. s .. '"'
end

local function volver_a_edicion()
    pcall(function() resolve:OpenPage("edit") end)
end

local function fail(msg)
    print("[Detectar Video] ERROR: " .. msg)
    volver_a_edicion()
    guardar_resultado(false, msg)
    error(msg, 0)
end

-- ---------------------------------------------------------------------
-- Carpeta del audio
-- ---------------------------------------------------------------------
local function carpeta_de_audio()
    -- Windows: LOCALAPPDATA, subcarpeta CineCaptions/audio (oculta por defecto).
    -- Mac: ~/Library/Application Support/CineCaptions/audio (Library esta oculta).
    -- Se crea nivel por nivel: bmd.createdir no siempre crea los intermedios.
    local base
    if es_windows() then
        base = os.getenv("LOCALAPPDATA")
        if not base or base == "" then
            base = home() .. SEP .. "AppData" .. SEP .. "Local"
        end
    else
        base = home() .. SEP .. "Library" .. SEP .. "Application Support"
    end
    local raiz = base .. SEP .. "CineCaptions"
    crear_dir(raiz)
    local destino = raiz .. SEP .. NOMBRE_CARPETA_AUDIO
    crear_dir(destino)
    return destino
end

-- ---------------------------------------------------------------------
-- Plan A: render del audio del timeline
-- ---------------------------------------------------------------------
local function cargar_preset_audio(project, log)
    local presets = project:GetRenderPresetList() or {}
    local candidatos = {}
    -- Aca la lista trae NOMBRES (strings), no objetos: ipairs pelado, sin
    -- el filtro de lista_api, que descartaria justamente los strings. Lo
    -- que importa es no usar pairs, que colaba la clave del conteo.
    for _, p in ipairs(presets or {}) do
        if tostring(p) == PRESET_PROPIO then table.insert(candidatos, 1, tostring(p)) end
    end
    for _, p in ipairs(presets or {}) do
        local s = tostring(p)
        if s ~= PRESET_PROPIO and s:lower():match("audio") then
            table.insert(candidatos, s)
        end
    end
    for _, nombre in ipairs(candidatos) do
        local ok = pcall(function() return project:LoadRenderPreset(nombre) end)
        if ok then
            log("Preset de render cargado: '" .. nombre .. "'.")
            return true
        end
    end
    log("No hay preset de solo audio; sigo con ajustes a mano.")
    return false
end

local function fijar_formato(project, log)
    -- Best-effort; nunca corta el render.
    local ok = pcall(function()
        return project:SetCurrentRenderFormatAndCodec("mp4", CODEC_AUDIO)
    end)
    if ok then log("Formato de render: mp4 / " .. CODEC_AUDIO .. ".") end
    return ok
end

-- Devuelve (ok, incluyo_marcas). Lo SEGUNDO importa: el reintento minimo se
-- queda con carpeta y nombre, o sea que pierde MarkIn/MarkOut y vuelve a
-- renderizar el timeline ENTERO. Si el llamante no se entera, anota la marca
-- igual, el manifiesto dice que el audio empieza en la marca, y TODOS los
-- subtitulos salen corridos sin un solo aviso. Hasta la v1.0.28 esta funcion
-- solo devolvia true/false y el comentario de abajo prometia lo contrario.
local function aplicar_ajustes(project, ajustes, log)
    local pedia_marcas = ajustes.MarkIn ~= nil
    local ok = pcall(function() return project:SetRenderSettings(ajustes) end)
    if ok then return true, pedia_marcas end
    -- Reintento minimo: solo carpeta y nombre.
    local minimo = { TargetDir = ajustes.TargetDir, CustomName = ajustes.CustomName }
    ok = pcall(function() return project:SetRenderSettings(minimo) end)
    if ok then
        log("Resolve rechazo los ajustes completos; use solo carpeta y nombre.")
        if pedia_marcas then
            log("OJO: en ese nivel se perdieron las marcas de entrada/salida. "
                .. "Se renderiza el timeline entero y los subtitulos se "
                .. "colocan desde el principio, para que no queden corridos.")
        end
        return true, false
    end
    log("Resolve no acepto los ajustes de render.")
    return false, false
end

local function guardar_preset_propio(project, log)
    local presets = project:GetRenderPresetList() or {}
    -- Nombres, no objetos: ipairs pelado (ver cargar_preset_audio).
    for _, p in ipairs(presets or {}) do
        if tostring(p) == PRESET_PROPIO then return end
    end
    local ok = pcall(function() return project:SaveAsNewRenderPreset(PRESET_PROPIO) end)
    if ok then log("Deje creado el preset '" .. PRESET_PROPIO .. "'.") end
end

local function lanzar_render(project, job_id, log)
    local intentos = {
        function() return project:StartRendering({ job_id }, false) end,
        function() return project:StartRendering(job_id) end,
        function() return project:StartRendering({ job_id }) end,
        function() return project:StartRendering() end,
    }
    for _, intento in ipairs(intentos) do
        local ok, r = pcall(intento)
        if ok and r then
            log("Render arrancado.")
            return true
        end
    end
    log("No pude arrancar el render.")
    return false
end

local function esperar_render(project, log)
    for _ = 1, 20 do
        local ok, r = pcall(function() return project:IsRenderingInProgress() end)
        if not ok or r then break end
        dormir(0.25)
    end
    local arranque = os.time()
    local ultimo = 0
    while true do
        local ok, r = pcall(function() return project:IsRenderingInProgress() end)
        if not ok or not r then return true end
        if os.time() - arranque > TIMEOUT_RENDER_SEG then
            log("El render tardo demasiado; lo detengo.")
            pcall(function() project:StopRendering() end)
            return false
        end
        local transcurrido = os.time() - arranque
        if transcurrido >= ultimo + 15 then
            ultimo = transcurrido
            print("    ... renderizando (" .. transcurrido .. "s)")
        end
        dormir(0.5)
    end
end

local function renderizar_audio(project, timeline, diagnostico)
    local function log(msg)
        print("  " .. msg)
        table.insert(diagnostico, msg)
    end

    local ok, r = pcall(function() return project:IsRenderingInProgress() end)
    if ok and r then
        log("Resolve ya esta renderizando otra cosa. Espera a que termine.")
        return nil
    end

    local destino = carpeta_de_audio()
    log("Carpeta de salida: " .. destino)

    local base = nombre_seguro(timeline:GetName()) .. "_audio"
    -- Borrar el render anterior de ESTE timeline. Sin os.remove (Free 21.1
    -- lo capo junto a io; llamarlo a secas era "attempt to call field
    -- 'remove'" y el script moria ANTES de renderizar, mudo) no se puede
    -- borrar: el nombre lleva la hora, asi es UNICO y el archivo nuevo se
    -- distingue igual por la foto de 'antes'. Los renders viejos los poda
    -- la app (que si tiene io) al Buscar audio.
    if os.remove ~= nil then
        for nombre in pairs(listar(destino)) do
            if nombre:sub(1, #base) == base then
                os.remove(destino .. SEP .. nombre)
            end
        end
    else
        base = base .. "_" .. tostring(os.time())
    end

    cargar_preset_audio(project, log)
    fijar_formato(project, log)

    local ajustes = {
        TargetDir = destino,
        CustomName = base,
        SelectAllFrames = true,
        ExportVideo = false,
        ExportAudio = true,
        AudioCodec = CODEC_AUDIO,
        AudioBitRate = BITRATE_AUDIO,
        AudioSampleRate = SAMPLE_RATE,
    }

    -- Si hay marcas de entrada y salida, se transcribe SOLO ese tramo.
    --
    -- Hay que anotar el mark_in ademas de recortar el render: el audio que
    -- sale empieza en la marca, asi que el segundo 0 de la transcripcion es
    -- la marca y no el principio del timeline. Sin ese dato, los subtitulos
    -- se colocarian al principio en vez de donde se hablo. El numero viaja
    -- en video_detectado.json y de ahi al manifiesto como 'offset_frames'.
    local marca_in, marca_out = marcas_de(timeline)
    if marca_in then
        ajustes.SelectAllFrames = false
        ajustes.MarkIn = marca_in
        ajustes.MarkOut = marca_out
        log(string.format("Marcas de entrada/salida: %d -> %d. "
                          .. "Solo se transcribe ese tramo.",
                          marca_in, marca_out))
    end

    local ok_ajustes, con_marcas = aplicar_ajustes(project, ajustes, log)
    if not ok_ajustes then return nil end
    -- Si Resolve rechazo los ajustes completos, aplicar_ajustes reintenta
    -- con carpeta y nombre nada mas, y ahi el recorte se pierde. Se anota
    -- SOLO lo que de verdad quedo aplicado: anotar la marca cuando el render
    -- salio entero corre todos los subtitulos.
    if marca_in and con_marcas then
        MARCA_APLICADA = { entrada = marca_in, salida = marca_out }
    end

    guardar_preset_propio(project, log)

    local job_id = project:AddRenderJob()
    if not job_id then
        log("Resolve no creo el trabajo de render.")
        return nil
    end

    -- La ruta EXACTA del render, de la propia cola de Resolve (v3.1.8). Hasta
    -- la v3.1.7 el archivo nuevo se buscaba LISTANDO la carpeta antes y
    -- despues, y el menu de Free 21.1 no tiene bmd.readdir: el render salia
    -- bien (medido el 16-09: Timeline 1_audio_<hora>.mp4 en disco, 2,3 MB)
    -- y el script decia "no aparecio ningun archivo" y caia al clip suelto
    -- de V1, que no es el audio del timeline. Si la cola no lo dice, el
    -- nombre que pone Resolve: <CustomName>.mp4 (el formato lo fija
    -- fijar_formato). Listar queda de respaldo, para 21.0.x.
    local esperado = nil
    pcall(function()
        for _, job in ipairs(lista_api(project:GetRenderJobList())) do
            if tostring(job.JobId) == tostring(job_id)
                    and type(job.TargetDir) == "string"
                    and type(job.OutputFilename) == "string"
                    and job.OutputFilename ~= "" then
                esperado = (job.TargetDir:gsub("[\\/]+$", "")) .. SEP
                    .. job.OutputFilename
            end
        end
    end)
    esperado = esperado or (destino .. SEP .. base .. ".mp4")

    -- Existe el render? Sin io, bmd.fileexists (en el menu de 21.1, medido);
    -- con io, el tamaño de siempre (un archivo de verdad, no uno vacio).
    local function hay_render(ruta)
        if SIN_IO then
            local ok_e, hay = pcall(function() return bmd.fileexists(ruta) end)
            return ok_e and hay == true
        end
        return tam_archivo(ruta) > 1024
    end

    -- La foto de 'antes' solo sirve al respaldo por listado, y sin readdir
    -- solo imprime un aviso que aqui ya seria falso. AddRenderJob no crea
    -- archivos: tomarla aqui es lo mismo que antes de encolar.
    local antes = (CAP.readdir or puede_usar_shell()) and listar(destino) or {}

    print("  Renderizando el audio de '" .. timeline:GetName() .. "'...")
    if not lanzar_render(project, job_id, log) then
        pcall(function() project:DeleteRenderJob(job_id) end)
        return nil
    end

    esperar_render(project, log)
    -- El estado del trabajo, antes de borrarlo: distingue "el render fallo"
    -- de "no lo encuentro", que se arreglan en sitios distintos.
    local estado = nil
    pcall(function()
        local st = project:GetRenderJobStatus(job_id)
        if type(st) == "table" and st.JobStatus then
            estado = tostring(st.JobStatus)
            if st.Error and tostring(st.Error) ~= "" then
                estado = estado .. " — " .. tostring(st.Error)
            end
        end
    end)
    pcall(function() project:DeleteRenderJob(job_id) end)

    if hay_render(esperado) then return esperado end

    -- Respaldo: buscar el archivo nuevo listando (Resolve puede agregar
    -- timecode al nombre).
    local mejor, mejor_mtime = nil, -1
    for nombre in pairs(listar(destino)) do
        if not antes[nombre] and ext_de(nombre) ~= "json" then
            local ruta = destino .. SEP .. nombre
            -- Sin io no se mide: vale cualquier archivo NUEVO de audio.
            if SIN_IO or tam_archivo(ruta) > 1024 then
                -- preferimos extensiones de audio conocidas
                local peso = EXT_AUDIO[ext_de(nombre)] and 1 or 0
                if peso >= 0 then
                    mejor = ruta; mejor_mtime = peso
                end
            end
        end
    end
    if not mejor then
        log("El render termino pero no aparecio ningun archivo de audio en " .. destino
            .. " (busque " .. esperado .. "; estado del trabajo: "
            .. (estado or "desconocido") .. ")")
        return nil
    end
    return mejor
end

-- ---------------------------------------------------------------------
-- Plan B: clip mas largo de la pista de video 1
-- ---------------------------------------------------------------------
local function video_fuente(timeline)
    if timeline:GetTrackCount("video") < 1 then return nil, 0 end
    local items = timeline:GetItemListInTrack("video", 1) or {}
    local lista = {}
    for _, it in ipairs(lista_api(items)) do if it then table.insert(lista, it) end end
    if #lista == 0 then return nil, 0 end

    local mejor, mejor_dur = nil, -1
    for _, it in ipairs(lista) do
        local dur = 0
        pcall(function() dur = it:GetDuration() end)
        if dur and dur > mejor_dur then mejor = it; mejor_dur = dur end
    end
    if not mejor then return nil, #lista end

    local mp = nil
    pcall(function() mp = mejor:GetMediaPoolItem() end)
    if not mp then return nil, #lista end
    local ruta = nil
    pcall(function() ruta = mp:GetClipProperty("File Path") end)
    if not ruta or ruta == "" then return nil, #lista end
    return ruta, #lista
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
            -- "Abre un proyecto" era un diagnostico FALSO en el caso mas
            -- comun: el proyecto esta abierto y lo que hay muerto es el
            -- objeto 'resolve' global de esa sesion de Resolve. En Free la
            -- unica via de rescate es el 'resolve' que presta el Puente
            -- (desde la v1.0.31), asi que si el Puente es viejo -o no
            -- corre- no hay de donde sacar otro. Se dicen las dos cosas.
            motivo = "Encontre Resolve pero no me respondio (GetProjectManager "
                     .. "vino vacio). Si no hay un proyecto abierto, abrelo. "
                     .. "Con el proyecto abierto, esto es la conexion muerta: "
                     .. "vuelve a lanzar CineCaptions_Puente (Area de trabajo > "
                     .. "Scripts > Utility) — el nuevo releva al viejo solo — "
                     .. "y genera de nuevo."
        else
            motivo = "No pude conectar con Resolve. Corre este script desde "
                     .. "Area de trabajo > Scripts > Utility > CineCaptions_DetectarVideo"
        end
        fail(motivo .. "  |  Diagnostico: " .. tostring(diag))
    end
    resolve = r
    print("[Detectar Video] version " .. VERSION)
    print("[Detectar Video] entrega del Puente: "
        .. (ENTREGA_PUENTE and "recibida" or "no (corrida manual o Puente viejo)"))

    local project = resolve:GetProjectManager():GetCurrentProject()
    if not project then fail("No hay proyecto abierto en Resolve.") end
    local timeline = project:GetCurrentTimeline()
    if not timeline then fail("No hay timeline activo. Abre uno primero.") end

    print("[Detectar Video] Timeline: " .. timeline:GetName())
    print("[Detectar Video] " .. capacidades())

    local diagnostico = {}
    local ruta = renderizar_audio(project, timeline, diagnostico)
    local desde_timeline = ruta ~= nil

    if desde_timeline then
        if SIN_IO then
            print("  LISTO: audio de la linea de tiempo (tamaño no medible "
                  .. "sin io)")
        else
            local mb = tam_archivo(ruta) / (1024 * 1024)
            print(string.format("  LISTO: audio de la linea de tiempo (%.1f MB)", mb))
        end
        print("    " .. ruta)
    else
        local ruta_b, cantidad = video_fuente(timeline)
        if not ruta_b then
            fail("No pude renderizar el audio del timeline ni encontrar un clip "
                 .. "en la pista de video 1 de '" .. timeline:GetName() .. "'.")
        end
        ruta = ruta_b
        print("\n  ATENCION: no se pudo renderizar el audio; uso el archivo del "
              .. "clip mas largo de la pista de video 1:")
        print("    " .. ruta)
        if cantidad and cantidad > 1 then
            print("    Hay " .. cantidad .. " clips en esa pista; si el timeline "
                  .. "tiene varios videos, los tiempos podrian no coincidir.")
        end
    end

    local carpeta = carpeta_compartida()
    crear_dir(carpeta)
    -- Las marcas solo valen si el audio salio del RENDER del timeline. Si se
    -- cayo al plan B (el archivo del clip mas largo de V1), ese audio es el
    -- video entero y aplicar un offset descolocaria todo.
    local ini_tl = 0
    pcall(function() ini_tl = math.floor(tonumber(timeline:GetStartFrame()) or 0) end)
    local fps_tl = 0
    pcall(function()
        fps_tl = tonumber(timeline:GetSetting("timelineFrameRate")) or 0
    end)
    -- La resolucion viaja por el mismo motivo que el fps: solo se conoce
    -- DENTRO de Resolve. Con ella la app puede decir, antes de generar, que
    -- formato detecto y que version del pack va a usar.
    local ancho_tl, alto_tl = 0, 0
    pcall(function()
        ancho_tl = math.floor(tonumber(timeline:GetSetting("timelineResolutionWidth")) or 0)
        alto_tl = math.floor(tonumber(timeline:GetSetting("timelineResolutionHeight")) or 0)
    end)
    local marca = desde_timeline and MARCA_APLICADA or nil

    local salida = carpeta .. SEP .. "video_detectado.json"
    -- El json se arma en memoria: con io va al archivo de siempre; sin io
    -- (Free 21.1) el epilogo lo manda por el registro de Resolve y la app lo
    -- lee de ahi (resolve_bridge.video_detectado).
    -- el archivo del clip principal (V1): si ya no esta en el disco, Resolve lo muestra «Archivo no encontrado» y su audio sale en silencio
    local clip_principal = nil
    pcall(function() clip_principal = video_fuente(timeline) end)
    local partes = {
        '"video_path": ' .. json_str(ruta),
        '"clip_principal": ' .. (clip_principal and json_str(clip_principal) or "null"),
        '"timeline_name": ' .. json_str(timeline:GetName()),
        '"project_name": ' .. json_str(project:GetName()),
        '"desde_timeline": ' .. tostring(desde_timeline),
        -- El primer fotograma del timeline (normalmente 86400 = 01:00:00:00)
        -- y el fps, para que la app pueda mostrar la zona en timecode.
        '"timeline_start_frame": ' .. ini_tl,
        '"fps": ' .. string.format("%.6f", fps_tl),
        '"ancho": ' .. ancho_tl,
        '"alto": ' .. alto_tl,
    }
    if marca then
        partes[#partes + 1] = '"mark_in": ' .. marca.entrada
        partes[#partes + 1] = '"mark_out": ' .. marca.salida
    end
    -- v5.4.16: los clips de V1 (inicio, duracion, resolucion, nombre): sin MCP (Resolve Free) la app los necesita para armar el movimiento sobre V1 de los efectos visuales
    -- (zoom, temblor, transiciones). Con mas de 40 clips se omite (el registro de Resolve recorta las lineas largas y se perderia todo el reporte).
    pcall(function()
        local clips_v1 = timeline:GetItemListInTrack("video", 1) or {}
        if #clips_v1 > 0 and #clips_v1 <= 40 then
            local filas = {}
            for _, it in ipairs(clips_v1) do
                local res = ""
                pcall(function() res = it:GetMediaPoolItem():GetClipProperty("Resolution") or "" end)
                filas[#filas + 1] = string.format('{"inicio": %d, "dur": %d, "res": %s, "nombre": %s}',
                    math.floor(tonumber(it:GetStart()) or 0), math.floor(tonumber(it:GetDuration()) or 0), json_str(tostring(res)), json_str(tostring(it:GetName()):sub(1, 40)))
            end
            partes[#partes + 1] = '"v1": [' .. table.concat(filas, ", ") .. ']'
        end
    end)
    partes[#partes + 1] = '"version": ' .. json_str(VERSION)
    partes[#partes + 1] = '"detectado_en": ' .. os.time()
    VIDEO_REPORTADO = "{" .. table.concat(partes, ", ") .. "}"
    escribir_archivo(salida, VIDEO_REPORTADO .. "\n")

    if marca then
        print(string.format(
            "  Zona marcada: fotogramas %d a %d. Los subtitulos se van a "
            .. "colocar ahi, no al principio del timeline.",
            marca.entrada, marca.salida))
    end

    volver_a_edicion()
    print("  Ahora abre (o vuelve a) 'CineCaptions' y usa "
          .. "'Detectar de Resolve'.")
end

local ok, err = pcall(main)
if not ok then
    print("[Detectar Video] termino con error: " .. tostring(err))
    guardar_resultado(false, tostring(err))
else
    guardar_resultado(true, "")
end

-- No dejar el wrapper de print puesto: el Puente corre estos scripts con
-- dofile dentro de SU propio estado de Lua, y print es global.
print = _print_original

-- Free 21.1, sin io (v3.1.6): el unico canal que sale del menu es un error()
-- sin capturar, que Resolve escribe TAL CUAL en Support/logs/ResolveDebug.txt
-- (ver la explicacion larga en el epilogo de CineCaptions_Subtitulos.lua). Aqui viaja
-- ademas el json del video detectado, que sin io no se pudo escribir. Con io
-- NO se lanza: bajo el Puente se leeria como fallo.
if SIN_IO then
    local reporte = "CINECAPTIONS_REPORTE|" .. json_resultado(ok, ok and "" or tostring(err),
                                                     texto_para_reporte(),
                                                     VIDEO_REPORTADO)
    -- Bajo el Puente (v3.1.7, modo señales) se DEVUELVE: el Puente lo relata
    -- al registro y la app lee 'video' de ahi (resolve_bridge.video_detectado).
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
