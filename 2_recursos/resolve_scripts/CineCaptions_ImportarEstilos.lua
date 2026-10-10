-- CineCaptions · By Cinema Productions
-- 2_recursos/resolve_scripts/CineCaptions_ImportarEstilos.lua — saca un pack de estilos de un timeline (Resolve Free).
--[[
CineCaptions_ImportarEstilos.lua
-----------------------
Lee un timeline de Resolve lleno de Text+ nombrados como siempre -'contexto',
'principal', 'complemento', 'contexto 2'...- y saca de ahi un PACK DE ESTILOS.

Un pack no es contenido que venga dentro del programa: es un formato. Quien
sepa hacer un Text+ bonito puede hacer un pack, y pasarselo a otro exportando
el timeline. No hace falta actualizar el programa para que haya packs nuevos.

Lo que deja este script:
  ~/DaVinciSubtitles/importar_estilos.json    lo extraido (lo lee la app)
  ~/DaVinciSubtitles/importar_estilos_tmp/    los .setting y las miniaturas

La app (plantillas.py) es la que convierte eso en un pack de verdad: mezcla
con lo que ya hubiera, reescala las miniaturas y limpia la basura. Aqui solo
se EXTRAE, porque validar y mezclar en Lua seria repetir codigo que del lado
de Python ya esta probado.

OJO CON LAS MINIATURAS: GrabStill() es de la pagina de Color, asi que Resolve
SALTA a esa pagina al capturarlas. Es normal y no es un fallo. Al terminar se
vuelve a Edicion.

Este script no borra nada del proyecto ni toca los Text+: solo los lee.
]]

local VERSION = "5.4.20 (importar estilos)"

-- La ENTREGA del Puente (v1.0.43): el resolve validado llega como
-- argumento del chunk, porque las globales del Puente NO cruzan el
-- dofile en el Lua de Resolve (entornos aislados por script; medido el
-- 01-09 con el diagnostico del cliente: candidatos: 3 y ni rastro del
-- prestamo, con el Puente latiendo al lado). Lanzado desde el menu no
-- llegan argumentos y esto queda en nil.
local ENTREGA_PUENTE = ({...})[1]
if type(ENTREGA_PUENTE) ~= "table" then ENTREGA_PUENTE = nil end

-- Los mismos nombres y el mismo tope que el resto del programa. Si esto se
-- separa de MAX_SETS de CineCaptions_Subtitulos, un pack valido se importaria a medias
-- sin decir por que.
local NOMBRES = {
    context = "contexto",
    main = "principal",
    complement = "complemento",
}
local ORDEN_ROLES = { "context", "main", "complement" }
local MAX_SETS = 10
-- v5.3: la estructura nueva (arriba / principal / abajo, variantes 1..3, 'simple' para las
-- palabras sueltas y 'imagen' para el icono) y los nombres de antes, que siguen valiendo.
local ALIAS = {
    context = { "arriba", "contexto" },
    main = { "principal" },
    complement = { "abajo", "complemento" },
}
local MAX_VARIANTES = 10

-- ---------------------------------------------------------------------
-- Utilidades (mismas que el resto de los scripts)
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

local NOMBRE_SCRIPT = "CineCaptions_ImportarEstilos"
local _salida = {}
local _print_original = print

local function escribir_archivo(ruta, texto)
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

local function guardar_resultado(ok, mensaje)
    local carpeta, sep = carpeta_compartida()
    escribir_archivo(carpeta .. sep .. "ultimo_resultado.txt",
                     table.concat(_salida, "\n"))
    escribir_archivo(carpeta .. sep .. "ultimo_resultado.json", string.format(
        '{"script": "%s", "version": "%s", "ok": %s, "mensaje": "%s",'
        .. ' "cuando": %d}',
        NOMBRE_SCRIPT, json_escapar(VERSION),
        tostring(ok and true or false), json_escapar(mensaje), os.time()))
end

-- Abortar lanzando, NUNCA con return: el pcall(dofile) del Puente daba por
-- bueno un script que se rendia en silencio.
local function fail(mensaje)
    guardar_resultado(false, mensaje)
    error(mensaje, 0)
end

-- Las listas de la API traen una clave extra con el conteo, y pairs() la
-- devuelve como si fuera un elemento. Ver la explicacion larga en
-- CineCaptions_Subtitulos.lua.
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

-- En Windows NO se ejecuta shell nunca, ni como respaldo: io.popen abre una
-- ventana de consola. Se usa bmd.createdir, y si no esta se prefiere no hacer
-- la operacion -diciendolo- antes que dejar Resolve inusable.
local function crear_carpeta(ruta)
    if bmd ~= nil and bmd.createdir ~= nil then
        pcall(function() bmd.createdir(ruta) end)
        if bmd.direxists ~= nil then
            local ok, hay = pcall(function() return bmd.direxists(ruta) end)
            if ok and hay then return true end
        else
            return true
        end
    end
    if es_windows() then return false end
    local ok = pcall(function()
        local p = io.popen('mkdir -p "' .. ruta .. '" 2>/dev/null')
        if p then p:close() end
    end)
    return ok
end

-- ---------------------------------------------------------------------
-- Conseguir Resolve
-- ---------------------------------------------------------------------
-- rawget salta el metatable, asi que el acceso normal va PRIMERO. Y nunca se
-- asigna el global 'resolve' sin validar: al fallar escribia nil y envenenaba
-- la sesion entera de Resolve, el Puente incluido.
local function obtener_resolve()
    -- La entrega en mano del Puente (v1.0.43): unico canal que cruza los
    -- entornos aislados de Resolve. Validada como el resto.
    if ENTREGA_PUENTE ~= nil and ENTREGA_PUENTE.resolve ~= nil then
        local ok0, pm0 = pcall(function()
            return ENTREGA_PUENTE.resolve:GetProjectManager()
        end)
        if ok0 and pm0 ~= nil then return ENTREGA_PUENTE.resolve end
    end
    local ok_g, g = pcall(function() return resolve end)
    if ok_g and g ~= nil then
        local ok2, pm = pcall(function() return g:GetProjectManager() end)
        if ok2 and pm ~= nil then return g end
    end
    local g2 = type(_G) == "table" and rawget(_G, "resolve") or nil
    if g2 ~= nil then
        local ok2, pm = pcall(function() return g2:GetProjectManager() end)
        if ok2 and pm ~= nil then return g2 end
    end
    local ok_b, b = pcall(function() return bmd end)
    if ok_b and type(b) == "table" and b.scriptapp ~= nil then
        local ok3, r = pcall(function() return b.scriptapp("Resolve") end)
        if ok3 and r ~= nil then
            local ok4, pm = pcall(function() return r:GetProjectManager() end)
            if ok4 and pm ~= nil then return r end
        end
    end
    return nil
end

-- ---------------------------------------------------------------------
-- Que set y que rol es cada clip
-- ---------------------------------------------------------------------
-- Se aceptan las mismas formas de numerar que en el Media Pool:
-- "contexto 2", "contexto2", "contexto-2", "contexto_2", "contexto 02".
-- Un nombre escrito distinto no puede dejar un set fuera sin avisar.
local function parsear_nombre(nombre)
    local n = tostring(nombre or ""):lower()
    n = n:gsub("^%s+", ""):gsub("%s+$", "")
    -- Resolve suele anadir la extension al clip del timeline. Solo se quitan
    -- extensiones de LETRAS: con digitos, "contexto.2" perderia su numero y
    -- se importaria como si fuera el set 1, pisando al de verdad.
    n = n:gsub("%.%a+$", "")
    if n == "simple" or n == "base" then return "base", 0 end
    for _, rol in ipairs(ORDEN_ROLES) do
        for _, palabra in ipairs(ALIAS[rol]) do
            if n == palabra then return rol, 1 end
            local num = n:match("^" .. palabra .. "[%s%-_%.]*0*(%d+)$")
            if num then
                local k = tonumber(num)
                local tope = (palabra == "arriba" or palabra == "abajo") and MAX_VARIANTES or MAX_SETS
                if k and k >= 1 and k <= tope then return rol, k end
                -- Un set fuera de rango no se ignora en silencio.
                return rol, -1
            end
        end
    end
    -- 'imagen' (el bloque del icono) no lleva estilo de texto: no es un set que importar.
    return nil, nil
end

-- ---------------------------------------------------------------------
-- Sacarle los valores a un Text+
-- ---------------------------------------------------------------------
local function leer(tool, id)
    local v = nil
    local ok = pcall(function() v = tool:GetInput(id) end)
    if not ok then return nil end
    return v
end

local function numero(tool, id, por_defecto)
    local v = tonumber(leer(tool, id))
    if v == nil then return por_defecto end
    return v
end

local function estilo_de(tool)
    local e = {
        font = tostring(leer(tool, "Font") or "Open Sans"),
        style = tostring(leer(tool, "Style") or "Regular"),
        size = numero(tool, "Size", 0.05),
        -- 'CharacterSpacing', no 'Tracking': ese input no existe en un Text+
        -- (ver CineCaptions_Prueba_Animaciones). Leyendo el que no es, todos los packs
        -- se importarian con interletrado 1.0 pasara lo que pasara.
        tracking = numero(tool, "CharacterSpacing", 1.0),
        color = {
            numero(tool, "Red1", 1.0),
            numero(tool, "Green1", 1.0),
            numero(tool, "Blue1", 1.0),
        },
    }
    local esp = numero(tool, "LineSpacing", nil)
    if esp ~= nil then e.line_spacing = esp end

    -- El contorno. La prueba del Paso 0 confirmo que estas entradas responden,
    -- y de ellas depende el modo Hormozi.
    local grosor = numero(tool, "Thickness2", 0)
    local activo = numero(tool, "Enabled2", 0)
    if activo and activo > 0 and grosor and grosor > 0 then
        e.outline = {
            thickness = grosor,
            color = {
                numero(tool, "Red2", 0.0),
                numero(tool, "Green2", 0.0),
                numero(tool, "Blue2", 0.0),
            },
        }
    end
    return e
end

local function text_plus_de(item)
    local ok, comp = pcall(function() return item:GetFusionCompByIndex(1) end)
    if not ok or not comp then return nil, nil end
    for _, t in ipairs(lista_api(comp:GetToolList())) do
        local ok_id, id = pcall(function() return t.ID end)
        if ok_id and id == "TextPlus" then return t, comp end
    end
    return nil, comp
end

-- ---------------------------------------------------------------------
-- Miniaturas
-- ---------------------------------------------------------------------
local function timecode_de(frame_abs, fps)
    local fps_i = math.floor((tonumber(fps) or 24) + 0.5)
    if fps_i < 1 then fps_i = 24 end
    local f = math.floor(tonumber(frame_abs) or 0)
    local total_s = math.floor(f / fps_i)
    return string.format("%02d:%02d:%02d:%02d",
        math.floor(total_s / 3600), math.floor(total_s / 60) % 60,
        total_s % 60, f % fps_i)
end

-- Devuelve el prefijo con el que quedo el archivo, o nil y el motivo.
--
-- Se exporta con un PREFIJO DISTINTO por set a proposito: ExportStills nombra
-- los archivos por TIMECODE ('cinecaptions_prueba_5.3.1.png'), no en orden, asi que
-- sin un prefijo propio no habria forma de saber cual es de quien. La app
-- despues busca por ese prefijo.
local function capturar_miniatura(project, timeline, item, fps, destino, n)
    local ok_tc = pcall(function()
        timeline:SetCurrentTimecode(timecode_de((item:GetStart() or 0) + 2, fps))
    end)
    if not ok_tc then return nil, "no pude mover el cursor al clip" end

    local still = nil
    local ok_grab = pcall(function() still = timeline:GrabStill() end)
    if not ok_grab or still == nil then
        return nil, "GrabStill no devolvio nada"
    end

    local album = nil
    pcall(function() album = project:GetGallery():GetCurrentStillAlbum() end)
    if album == nil then
        return nil, "no pude llegar al album de la galeria"
    end

    local prefijo = string.format("cinecaptions_set_%02d", n)
    local ok_exp = pcall(function()
        return album:ExportStills({ still }, destino, prefijo, "png")
    end)
    -- No dejarle basura en la galeria del proyecto.
    pcall(function() album:DeleteStills({ still }) end)

    if not ok_exp then return nil, "ExportStills fallo" end
    return prefijo, nil
end

-- ---------------------------------------------------------------------
-- Escribir lo extraido
-- ---------------------------------------------------------------------
local function json_color(c)
    return string.format("[%.6f, %.6f, %.6f]",
                         c[1] or 1, c[2] or 1, c[3] or 1)
end

local function json_estilo(e)
    local partes = {
        string.format('"font": "%s"', json_escapar(e.font)),
        string.format('"style": "%s"', json_escapar(e.style)),
        string.format('"size": %.6f', e.size or 0.05),
        string.format('"tracking": %.6f', e.tracking or 1.0),
        string.format('"color": %s', json_color(e.color or {})),
    }
    if e.line_spacing then
        partes[#partes + 1] = string.format('"line_spacing": %.6f',
                                            e.line_spacing)
    end
    if e.outline then
        partes[#partes + 1] = string.format(
            '"outline": {"thickness": %.6f, "color": %s}',
            e.outline.thickness or 0, json_color(e.outline.color or {}))
    end
    return "{" .. table.concat(partes, ", ") .. "}"
end

-- ---------------------------------------------------------------------
-- Main
-- ---------------------------------------------------------------------
-- Archivo que deja la app cuando el usuario elige importar desde un .drt en
-- vez de desde el timeline abierto. Nombre fijo (como jobs/pendiente.json),
-- contenido: la ruta del .drt, en una sola linea, sin JSON -es un dato
-- suelto, no hace falta un parser para esto-.
local function ruta_drt_pendiente()
    local carpeta, sep = carpeta_compartida()
    local marcador = carpeta .. sep .. "importar_drt.txt"
    local f = io.open(marcador, "r")
    if not f then return nil end
    local ruta = f:read("*l")
    f:close()
    os.remove(marcador)   -- se borra ya: un marcador viejo no puede repetir la importacion
    if ruta == nil or ruta == "" then return nil end
    return ruta
end

-- Modulo, no local de main(): la limpieza (borrar el timeline importado y
-- devolver el que estaba activo) tiene que correr SIEMPRE, incluso si main()
-- aborta a mitad con fail() -por ejemplo "no encontre ningun Text+"-, y para
-- eso el epilogo de mas abajo necesita verlas despues de que pcall(main)
-- termine, ya sea bien o mal.
local project_global = nil
local timeline_previo = nil
local timeline_importado = nil

local function main()
    print("CineCaptions Importar estilos  v" .. VERSION)

    local r = obtener_resolve()
    if r == nil then
        fail("No pude conectar con Resolve. Corre esto DESDE Resolve: "
             .. "Area de trabajo > Scripts.")
    end

    local project = r:GetProjectManager():GetCurrentProject()
    if not project then fail("No hay ningun proyecto abierto en Resolve.") end
    project_global = project
    local media_pool = project:GetMediaPool()

    -- Si el usuario eligio "Importar desde un archivo .drt", el timeline no
    -- esta abierto: hay que traerlo primero. Se importa, se usa, y se borra
    -- al terminar -es un timeline nuestro, de usar y tirar, no algo del
    -- usuario-. El timeline que estuviera activo se restaura para no dejar
    -- a alguien mirando un timeline que no eligio.
    local ruta_drt = ruta_drt_pendiente()
    local timeline

    if ruta_drt then
        print("  Importando desde " .. ruta_drt .. "...")
        timeline_previo = project:GetCurrentTimeline()
        local ok_imp, importado = pcall(function()
            return media_pool:ImportTimelineFromFile(ruta_drt)
        end)
        if not ok_imp or importado == nil then
            fail("No pude importar '" .. ruta_drt .. "'. ¿Es un .drt "
                 .. "exportado de Resolve (Archivo > Exportar > Timeline)?")
        end
        timeline_importado = importado
        -- ImportTimelineFromFile puede o no dejarlo como timeline activo
        -- segun la version: se fija a mano para no depender de eso.
        pcall(function() project:SetCurrentTimeline(importado) end)
        timeline = importado
    else
        timeline = project:GetCurrentTimeline()
    end

    if not timeline then
        fail("No hay ningun timeline abierto. Abre el timeline del pack de "
             .. "estilos y vuelve a pulsar Importar.")
    end

    local ancho = tonumber(timeline:GetSetting("timelineResolutionWidth"))
        or tonumber(project:GetSetting("timelineResolutionWidth")) or 1920
    local alto = tonumber(timeline:GetSetting("timelineResolutionHeight"))
        or tonumber(project:GetSetting("timelineResolutionHeight")) or 1080
    local fps = tonumber(timeline:GetSetting("timelineFrameRate"))
        or tonumber(project:GetSetting("timelineFrameRate")) or 24
    local formato = (alto > ancho) and "v" or "h"

    print(string.format("  Timeline '%s'  %dx%d @ %.3f fps  -> formato %s",
        tostring(timeline:GetName()), ancho, alto, fps, formato))

    local carpeta, sep = carpeta_compartida()
    local tmp = carpeta .. sep .. "importar_estilos_tmp"
    local tmp_min = tmp .. sep .. "miniaturas"
    if not crear_carpeta(tmp) or not crear_carpeta(tmp_min) then
        fail("No pude crear la carpeta de trabajo en " .. tmp
             .. ". Sin ella no puedo guardar los estilos.")
    end

    -- Recorrer el timeline. Un set cuenta con que tenga UNA de las tres
    -- plantillas: exigir las tres hacia desaparecer sets enteros en silencio.
    local entradas = {}
    local avisos = {}
    local clip_de_set = {}      -- para la miniatura: un clip por numero
    local vistos, fuera_de_rango, sin_textplus = 0, 0, 0

    for pista = 1, (timeline:GetTrackCount("video") or 0) do
        for _, item in ipairs(lista_api(
                timeline:GetItemListInTrack("video", pista) or {})) do
            local nombre = nil
            pcall(function() nombre = item:GetName() end)
            local rol, n = parsear_nombre(nombre)
            if rol ~= nil then
                vistos = vistos + 1
                if n == -1 then
                    fuera_de_rango = fuera_de_rango + 1
                    avisos[#avisos + 1] = string.format(
                        "'%s' tiene un numero mayor que %d: lo salte",
                        tostring(nombre), MAX_SETS)
                else
                    local tool = text_plus_de(item)
                    if tool == nil then
                        sin_textplus = sin_textplus + 1
                        avisos[#avisos + 1] = string.format(
                            "'%s' no tiene un Text+ dentro: lo salte",
                            tostring(nombre))
                    else
                        local e = estilo_de(tool)
                        local nombre_setting = (rol == "base")
                            and "base.setting"
                            or string.format("%02d-%s.setting", n, rol)
                        -- El .setting es lo FIEL: se lleva degradados, formas
                        -- y fondos. El estilos.json de al lado es el plan B y
                        -- lo unico que se puede dibujar en la ventana.
                        local ok_set = pcall(function()
                            return tool:SaveSettings(tmp .. sep .. nombre_setting)
                        end)
                        if not ok_set then
                            avisos[#avisos + 1] = string.format(
                                "no pude guardar el nodo entero de '%s' "
                                .. "(se usaran solo sus valores)",
                                tostring(nombre))
                            nombre_setting = nil
                        end
                        entradas[#entradas + 1] = {
                            rol = rol, n = n, estilo = e,
                            setting = nombre_setting,
                        }
                        local clave = (rol == "base") and "base" or n
                        -- La miniatura se saca del clip 'principal', que es
                        -- el que manda visualmente. Si no hay, vale el que
                        -- haya.
                        if clip_de_set[clave] == nil or rol == "main" then
                            clip_de_set[clave] = item
                        end
                    end
                end
            end
        end
    end

    if #entradas == 0 then
        fail(string.format(
            "En el timeline '%s' no encontre ningun Text+ con los nombres del "
            .. "pack. Tienen que llamarse 'arriba', 'principal', "
            .. "'abajo' (y 'arriba 2', 'principal 2'... hasta 3 "
            .. "variantes), mas 'simple' e 'imagen' si quieres.",
            tostring(timeline:GetName())))
    end

    -- Miniaturas. Van al final y aparte porque saltan a la pagina de Color, y
    -- porque si fallan el pack sigue siendo perfectamente usable.
    local miniaturas = {}
    local pagina_previa = nil
    pcall(function() pagina_previa = r:GetCurrentPage() end)

    local n_min = 0
    for clave, item in pairs(clip_de_set) do
        local n = (clave == "base") and 0 or clave
        local prefijo, motivo = capturar_miniatura(
            project, timeline, item, fps, tmp_min, n)
        if prefijo then
            miniaturas[#miniaturas + 1] = { clave = clave, prefijo = prefijo }
            n_min = n_min + 1
        else
            avisos[#avisos + 1] = string.format(
                "sin miniatura para el set %s (%s)", tostring(clave),
                tostring(motivo))
        end
    end

    -- Volver a donde estaba el usuario. GrabStill lo dejo en Color.
    pcall(function() r:OpenPage(pagina_previa or "edit") end)

    -- Escribir lo extraido para que lo recoja la app.
    local trozos = {}
    for _, e in ipairs(entradas) do
        trozos[#trozos + 1] = string.format(
            '{"rol": "%s", "n": %d, "estilo": %s, "setting": %s}',
            e.rol, e.n, json_estilo(e.estilo),
            e.setting and ('"' .. json_escapar(e.setting) .. '"') or "null")
    end
    local trozos_min = {}
    for _, m in ipairs(miniaturas) do
        trozos_min[#trozos_min + 1] = string.format(
            '{"clave": "%s", "prefijo": "%s"}',
            json_escapar(tostring(m.clave)), json_escapar(m.prefijo))
    end
    local trozos_av = {}
    for _, a in ipairs(avisos) do
        trozos_av[#trozos_av + 1] = '"' .. json_escapar(a) .. '"'
    end

    local json = string.format(
        '{\n  "ok": true,\n  "version": "%s",\n  "timeline": "%s",\n'
        .. '  "resolucion": [%d, %d],\n  "fps": %.6f,\n  "formato": "%s",\n'
        .. '  "carpeta": "%s",\n  "entradas": [%s],\n'
        .. '  "miniaturas": [%s],\n  "avisos": [%s],\n  "cuando": %d\n}\n',
        json_escapar(VERSION), json_escapar(tostring(timeline:GetName())),
        ancho, alto, fps, formato, json_escapar(tmp),
        table.concat(trozos, ",\n    "), table.concat(trozos_min, ", "),
        table.concat(trozos_av, ", "), os.time())

    local destino = carpeta .. sep .. "importar_estilos.json"
    if not escribir_archivo(destino, json) then
        fail("Extraje los estilos pero no pude escribir " .. destino)
    end

    -- Contar por set, que es como lo piensa el usuario.
    local por_set = {}
    for _, e in ipairs(entradas) do
        local clave = (e.rol == "base") and "base" or tostring(e.n)
        por_set[clave] = (por_set[clave] or 0) + 1
    end
    local cuantos = 0
    for _ in pairs(por_set) do cuantos = cuantos + 1 end

    print(string.format("  Encontrados %d Text+ en %d sets.", #entradas, cuantos))
    print(string.format("  Miniaturas capturadas: %d.", n_min))
    if #avisos > 0 then
        print("  Avisos:")
        for _, a in ipairs(avisos) do print("    - " .. a) end
    end

    guardar_resultado(true, string.format(
        "Importados %d estilos en %d sets (%s).", #entradas, cuantos,
        formato == "v" and "vertical" or "horizontal"))
end

local ok, err = pcall(main)
if not ok then
    -- fail() ya escribio el resultado antes de lanzar; volver a escribirlo es
    -- idempotente y cubre ademas los errores que NO pasaron por fail().
    local msg = tostring(err)
    print("ERROR: " .. msg)
    guardar_resultado(false, msg)
end

-- La limpieza del timeline importado desde un .drt corre SIEMPRE, pase lo
-- que pase adentro de main() -es un timeline nuestro, de usar y tirar-.
if timeline_importado ~= nil and project_global ~= nil then
    pcall(function()
        if timeline_previo ~= nil then
            project_global:SetCurrentTimeline(timeline_previo)
        end
    end)
    local media_pool_final = nil
    pcall(function() media_pool_final = project_global:GetMediaPool() end)
    if media_pool_final ~= nil then
        pcall(function()
            media_pool_final:DeleteTimelines({ timeline_importado })
        end)
    end
end
