-- CineCaptions · By Cinema Productions
-- 2_recursos/resolve_scripts/CineCaptions_Subtitulos.lua — coloca los subtítulos en el timeline (núcleo en Lua para Resolve Free).
--[[
CineCaptions_Subtitulos.lua
------------------
Version en Lua de "CineCaptions.py".

Corre DENTRO de Resolve (Area de trabajo > Scripts > Utility). Es la version
para Resolve FREE, que trae Lua pero puede no tener Python del sistema.

Lee ~/DaVinciSubtitles/subtitles_manifest.json y, por cada idioma dinamico,
coloca subtitulos de 3 lineas (contexto / principal / complemento) en tres
pistas de video, mas los efectos de sonido en una pista de audio.

Dos modos, igual que la version Studio:

  - CON TUS PLANTILLAS: si en el Media Pool hay Text+ llamados 'contexto',
    'principal' y 'complemento' (y sus juegos numerados: contexto 2,
    principal 2...), se usan tal cual y se van alternando bloque a bloque.
    El script solo les cambia el texto: la tipografia, el tamaño y la
    posicion las pones tu.

  - AUTOMATICO: si no hay plantillas, crea un Text+ solo y le aplica
    fuente, tamaño, peso, posicion y color, alternando entre varias
    variantes para que el video no sea siempre el mismo bloque.

La API de Resolve/Fusion es la misma que en Python; esto es una traduccion
directa de lo que ya funciona ahi.
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

local VERSION = "5.4.17 (subtitulos)"

-- La ENTREGA del Puente (v1.0.43): el resolve validado llega como
-- argumento del chunk, porque las globales del Puente NO cruzan el
-- dofile en el Lua de Resolve (entornos aislados por script; medido el
-- 01-09 con el diagnostico del cliente: candidatos: 3 y ni rastro del
-- prestamo, con el Puente latiendo al lado). Lanzado desde el menu no
-- llegan argumentos y esto queda en nil.
local ENTREGA_PUENTE = ({...})[1]
if type(ENTREGA_PUENTE) ~= "table" then ENTREGA_PUENTE = nil end
local FADE_OUT_SECONDS = 0.35
-- La animacion de entrada del camino por valores (v1.0.51). Corta a
-- proposito: es un "aparecer con suavidad", no un efecto — los packs traen
-- los suyos y no pasan por aqui. Misma constante en el gemelo .py.
local FADE_IN_SECONDS = 0.12
local DYNAMIC_ORDER = { "context", "main", "complement" }
local ROLE_SHORT = { context = "CTX", main = "MAIN", complement = "CMP" }

-- Plantillas del usuario. Si en el Media Pool hay Text+ llamados asi, se
-- usan TAL CUAL: el script solo les cambia el texto y no toca ni la
-- tipografia, ni el tamaño, ni la posicion. Es lo mismo que hace la version
-- Studio; hasta la 1.0.15 el .lua ignoraba esto y siempre imponia su propio
-- diseño, que es por lo que "no respetaba" lo que el usuario habia armado.
local DYNAMIC_TEMPLATES = {
    context = "contexto",
    main = "principal",
    complement = "complemento",
}
-- Plantilla suelta (sin numerar) para las palabras sin marcar (rol 'base').
local BASE_TEMPLATE_NAME = "base"
-- v5.3: la estructura NUEVA de un pack: arriba / principal / abajo / imagen (+ 'simple' para las
-- palabras sueltas), variantes 1..3 ("arriba 2", "arriba3"...). Los nombres de antes (contexto /
-- complemento / base) siguen valiendo. Gemela de packs_drt.ALIAS (la app) y de NOMBRES_ROL del .py.
-- Todo en UNA tabla: el chunk principal esta cerca del limite de 200 locales de Lua.
local NOMBRES = {
    rol = { context = { "arriba", "contexto" }, main = { "principal" },
            complement = { "abajo", "complemento" } },
    base = { "simple", "base" },
    imagen = "imagen",
    solo_nuevos = { arriba = true, abajo = true, imagen = true },
    max_variantes = 16,        -- v5.5: gemela de MAX_VARIANTES de CineCaptions.py (aquí se había quedado en 3)
}
-- Cuantos juegos numerados se buscan: contexto, contexto 2, contexto 3...
local MAX_SETS = 16
-- Formas de numerar que se aceptan, para no obligar a escribirlo de una
-- manera concreta: "contexto 2", "contexto2", "contexto-2", "contexto_2",
-- "contexto 02".
local SUFIJOS_DE_SET = { " %d", "%d", "-%d", "_%d", " %02d" }

-- Separacion entre clips, en fotogramas.
--
-- En 0: los bloques van PEGADOS donde el habla es seguida, y el hueco aparece
-- solo donde hay silencio de verdad. No hace falta detectar silencios: el fin
-- de un bloque ya es el fin de su ultima palabra (ver build_manual_cues en
-- dynamic_subtitles.py), no se estira hasta el bloque siguiente, asi que la
-- pausa del audio se traduce sola en hueco.
--
-- Y no se solapan: 'duracion = fin_frame - inicio_frame' con
-- 'endFrame = duracion - 1', o sea que el clip ocupa hasta fin_frame - 1 y el
-- siguiente arranca en su propio inicio_frame.
--
-- Se dejan como constantes, en vez de quitarlas del codigo, para que volver a
-- meter aire entre bloques sea cambiar un numero.
local GAP_BASICO_FRAMES = 0   -- entre palabras sueltas (rol 'base')
local GAP_BLOQUE_FRAMES = 0   -- entre bloques de 2 o 3 lineas

-- Donde va SIEMPRE la linea principal, y de ahi cuelgan las otras dos.
--
-- Las alturas NO son absolutas por rol. Lo fueron hasta la v1.0.24 y daba dos
-- problemas a la vez:
--
--   - Un bloque de 2 lineas dejaba el HUECO de la tercera. "contexto +
--     principal" flotaba alto y "principal + complemento" flotaba bajo,
--     porque cada linea iba a su altura fija pasara lo que pasara.
--   - Cada variante de diseño traia su propia 'y', asi que el texto REBOTABA
--     verticalmente entre un bloque y el siguiente.
--
-- Con un ancla fija para la principal y el resto colocado en relacion a ella,
-- las dos cosas desaparecen. Tiene que dar los MISMOS numeros que
-- altura_de_linea() del .py: si Free y Studio colocan distinto, el mismo
-- proyecto se ve diferente segun quien lo abra.
-- El prefijo de los bins que crea este programa para los packs .drt. Va aca
-- arriba y no junto a nombre_bin_pack() porque find_clip_by_name() lo usa
-- mucho antes: en Lua un local solo existe a partir de su linea.
local PREFIJO_BIN_PACK = "RCS · "

local ANCLA_Y = 0.196
-- 0.54 (v1.0.51, antes 0.66): el 0.66 salia de la caja em teorica de
-- Montserrat (1.219/2 + holgura), pero la caja em incluye ascendentes y
-- descendentes que un subtitulo casi nunca usa — medido en unidades de la
-- linea chica, el hueco quedaba a ~2 veces su propio em y el bloque se
-- leia como tres tiras sueltas (reporte con captura, 9:16). 0.54 es un
-- interlineado real de ~1.08 sobre la suma de tamaños. El 0.47 historico
-- si solapaba de verdad: no volver ahi. Ver la nota larga del .py.
local FACTOR_SEPARACION = 0.54

local function altura_de_linea(rol, estilos, ancla, factor)
    -- 'ancla'/'factor' llegan SOLO del modo «Diseño dinámico» (v1.0.49):
    -- posicion elegida por el usuario. Sin ellos, las constantes de
    -- siempre — el camino de packs no cambia ni un pelo.
    ancla = tonumber(ancla) or ANCLA_Y
    factor = tonumber(factor) or FACTOR_SEPARACION
    if rol == "main" or rol == "base" then return ancla end
    local tam_main = (estilos.main and estilos.main.size) or 0.082
    local mio = estilos[rol]
    local tam_mio = (mio and mio.size) or 0.05
    local separacion = (tam_main + tam_mio) * factor
    if rol == "context" then return ancla + separacion end
    return ancla - separacion
end

-- Diseño del modo automatico (mismos valores que AUTO_STYLES del .py).
-- La altura ya no se pone aqui: la calcula altura_de_linea().
--
-- Montserrat, no Open Sans/Georgia: desde la v1.0.27 Montserrat viaja
-- incrustada en el programa. Open Sans no viene instalada en Windows por
-- defecto -era ese el "error" del diseño automatico en un equipo recien
-- instalado- y Georgia esta pensada para pantalla chica, no subtitulo.
local AUTO_STYLES = {
    context    = { font = "Montserrat", style = "Regular", size = 0.038, tracking = 1.0,  r = 1.0, g = 1.0, b = 1.0 },
    main       = { font = "Montserrat", style = "Bold",    size = 0.082, tracking = 0.97, r = 1.0, g = 1.0, b = 1.0 },
    complement = { font = "Montserrat", style = "Italic",  size = 0.050, tracking = 1.0,  r = 0.88, g = 0.88, b = 0.88 },
}

-- Variantes que se alternan bloque a bloque. Cada una es un delta sobre
-- AUTO_STYLES: solo lo que cambia.
local AUTO_PRESETS = {
    {},
    { main = { size = 0.098 }, context = { size = 0.034 }, complement = { size = 0.044 } },
    { main = { size = 0.070 }, context = { size = 0.040 }, complement = { size = 0.052, style = "Regular" } },
    { main = { size = 0.076, tracking = 1.12 }, context = { size = 0.036, tracking = 1.15 }, complement = { size = 0.048 } },
    { main = { size = 0.090 }, context = { size = 0.032, r = 0.80, g = 0.80, b = 0.80 }, complement = { size = 0.046 } },
}

-- ---------------------------------------------------------------------
-- Modo destacados: Hormozi, Gadzhi, acumulativo y pintado
-- ---------------------------------------------------------------------
-- Los bloques ya vienen armados desde dynamic_subtitles.build_destacados_cues
-- (en la app): aca solo hay que dibujarlos. Tres de los cuatro looks son un
-- Text+ por bloque, igual que el modo automatico de arriba; el cuarto
-- ('pintado') es varias palabras, cada una su propio Text+, y necesita su
-- propio colocador (ver colocar_pintado). Tiene que dar el MISMO resultado
-- que DESTACADOS_ESTILOS del .py: hay un test que los compara con lupa.
-- Montserrat, no Open Sans (v1.0.51): Open Sans NO viene en Windows y era
-- el primer motivo por el que el modo destacados se escondio en la
-- v1.0.26 — Montserrat viaja incrustada en el programa.
local DESTACADOS_ESTILOS = {
    hormozi = {
        normal = { font = "Montserrat", style = "ExtraBold", size = 0.085,
                  tracking = 1.0, r = 1.0, g = 1.0, b = 1.0,
                  contorno = { grosor = 0.24, r = 0.0, g = 0.0, b = 0.0 } },
        resaltada = { font = "Montserrat", style = "ExtraBold", size = 0.085,
                     tracking = 1.0, r = 1.0, g = 0.85, b = 0.08,
                     contorno = { grosor = 0.24, r = 0.0, g = 0.0, b = 0.0 } },
    },
    gadzhi = {
        normal = { font = "Montserrat", style = "Bold", size = 0.10,
                  tracking = 1.0, r = 1.0, g = 1.0, b = 1.0 },
        resaltada = { font = "Montserrat", style = "Bold", size = 0.10,
                     tracking = 1.0, r = 1.0, g = 0.85, b = 0.08 },
    },
    acumulativo = {
        normal = { font = "Montserrat", style = "SemiBold", size = 0.065,
                  tracking = 1.0, r = 1.0, g = 1.0, b = 1.0 },
        resaltada = { font = "Montserrat", style = "SemiBold", size = 0.065,
                     tracking = 1.0, r = 1.0, g = 0.85, b = 0.08 },
    },
}

-- El estilo de 'pintado' es distinto de proposito: el tamaño y la fuente son
-- los MISMOS numeros que uso medir_texto.py en la app para calcular donde va
-- cada palabra. Si aca se usara otro tamaño, las palabras quedarian corridas
-- de su sitio. Por eso 'estilo_pintado' SIEMPRE se lee del manifiesto; esto
-- es solo el respaldo para un manifiesto viejo que no lo traiga.
local ESTILO_PINTADO_RESPALDO = {
    font = "Montserrat", style = "Bold", size = 0.07, tracking = 1.0,
    r = 1.0, g = 1.0, b = 1.0,
}
-- Tres estados por palabra: la que todavia no se dijo (tenue, para leer
-- adelantado sin competir con la que se esta diciendo), la ya dicha, y la ya
-- dicha que ademas era palabra clave.
local COLOR_PINTADO_MUDA = { r = 0.5, g = 0.5, b = 0.5 }
local COLOR_PINTADO_DICHA = { r = 1.0, g = 1.0, b = 1.0 }
local COLOR_PINTADO_DICHA_CLAVE = { r = 1.0, g = 0.85, b = 0.08 }

-- Techo de palabras simultaneas en un bloque 'pintado' (coincide con
-- MAX_BLOQUE_3L de dynamic_subtitles.py). Cada palabra usa DOS pistas (ver
-- colocar_pintado); solo se crean las que hagan falta de verdad.
local MAX_PALABRAS_PINTADO = 9

-- Ancho maximo de una fila del pintado, como fraccion del ANCHO del
-- fotograma (v1.0.51). Sin envolver, una frase de 7 palabras al tamaño de
-- la principal se salia del cuadro en 9:16. Una palabra sola mas ancha que
-- esto no se parte. Mismos numeros que el .py.
local ANCHO_MAX_PINTADO = 0.92
-- Separacion vertical entre filas del pintado, en multiplos del tamaño del
-- texto (interlineado). Fraccion de la ALTURA, como Size.
local INTERLINEA_PINTADO = 1.35

-- ---------------------------------------------------------------------
-- Utilidades (embebidas)
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
-- Registro en disco: que se sepa que paso sin abrir la consola de Resolve
-- ---------------------------------------------------------------------
-- Todo lo que este script informaba iba SOLO a print(), o sea a la ventana
-- "Consola de comandos" de Resolve. Si el usuario no la tiene abierta no ve
-- nada: ni el error ni el motivo. De ahi el clasico "lo pico y no pasa
-- nada", que costo varias rondas de diagnostico a ciegas.
--
-- Ahora lo mismo que se imprime queda ademas escrito en la carpeta que ya
-- comparten la app y los scripts, y la app lo muestra.
local NOMBRE_SCRIPT = "CineCaptions_Subtitulos"
local _salida = {}
local _print_original = print

local function escribir_archivo(ruta, texto)
    -- Sin io (menu de Free 21.1, medido el 16-09) no hay donde escribir: se
    -- dice que no y el epilogo reporta por el registro de Resolve.
    if io == nil then return false end
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

-- Se envuelve print() en vez de tocar las decenas de llamadas repartidas
-- por el script. Es la global, asi que lo ve todo el codigo de abajo.
print = function(...)
    local partes = {}
    for i = 1, select("#", ...) do
        partes[#partes + 1] = tostring((select(i, ...)))
    end
    _salida[#_salida + 1] = table.concat(partes, "\t")
    _print_original(...)
end

-- El MISMO json que lee resolve_bridge.ultimo_resultado(): al archivo con io,
-- y por el registro de Resolve sin io (v3.1.6). 'texto' es opcional y va al
-- FINAL a proposito: si el registro recortara la linea, la cabecera (ok,
-- mensaje, cuando) sobrevive y la app la rescata.
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

-- v5.5 — lo ultimo que hace el script: deja Resolve como el usuario lo quiere VER (gemelo de vista_final de CineCaptions.py). El manifiesto trae
-- "vista" = {pagina, preset, al_inicio}: la pagina (Edit), su disposicion de pantalla guardada (resolve:LoadLayoutPreset: vertical y vista expandida, la que el
-- usuario guardo una vez) y el cabezal al principio del timeline (la app pulsa luego «reproducir»). Nunca falla: cada cosa que no se puede deja una linea clara.
local function vista_final(timeline, manifest, solo_pagina)
    local v = type(manifest) == "table" and manifest.vista or nil
    if type(v) ~= "table" then return end
    if v.pagina then
        local ok = pcall(function() resolve:OpenPage(tostring(v.pagina)) end)
        if not ok then print("  Aviso: no pude abrir la pagina «" .. tostring(v.pagina) .. "» de Resolve.") end
    end
    if solo_pagina then return end
    local preset = tostring(v.preset or "")
    if preset ~= "" then
        local ok, msg = pcall(function()
            local lista = resolve:GetLayoutPresetList() or {}
            local esta = false
            for _, nombre in pairs(lista) do if nombre == preset then esta = true end end
            if esta then
                if resolve:LoadLayoutPreset(preset) then
                    print("  Vista de Resolve: aplique tu disposicion «" .. preset .. "».")
                else
                    print("  Aviso: Resolve no aplico la disposicion «" .. preset .. "».")
                end
            else
                print("  Nota: no tienes guardada la disposicion de pantalla «" .. preset .. "» (Area de trabajo > Distribucion de interfaz (Layout Presets) > Guardar como nueva, o el boton «Guardar la vista actual de Resolve» de CineCaptions).")
            end
        end)
        if not ok then print("  Aviso: no pude aplicar la disposicion de pantalla (" .. tostring(msg) .. ").") end
    end
    if v.al_inicio ~= false then
        local ok = pcall(function() timeline:SetCurrentTimecode(timeline:GetStartTimecode()) end)
        if not ok then print("  Aviso: no pude llevar el cabezal al inicio del timeline.") end
    end
end

-- Lo ultimo del registro, recortado, para el reporte que viaja por el
-- registro de Resolve cuando no hay io (ver el epilogo). El tope de linea de
-- ese registro no esta medido: se manda poco y lo esencial va antes.
local function texto_para_reporte()
    -- Las lineas de capacidades (bmd:/lua:, y desde la v3.3.0 la version de
    -- Resolve en la de bmd:) cierran casos con una captura: van SIEMPRE.
    -- Se apartan ANTES de recortar: en un registro corto caian dentro de la
    -- cola y el recorte a 1300 caracteres se las comia (v3.3.0).
    local cab, resto = {}, {}
    for i = 1, #_salida do
        local l = _salida[i]
        if l:find("bmd:", 1, true) or l:sub(1, 4) == "lua:" then
            cab[#cab + 1] = l
        else
            resto[#resto + 1] = l
        end
    end
    local cola = {}
    for i = math.max(1, #resto - 24), #resto do
        cola[#cola + 1] = resto[i]
    end
    local texto = table.concat(cola, "\n")
    if #texto > 1300 then texto = texto:sub(-1300) end
    if #cab > 0 then texto = table.concat(cab, "\n") .. "\n" .. texto end
    return texto
end

-- Recorrer una lista devuelta por la API de Resolve.
--
-- OJO: esas listas NO son arrays limpios: traen una clave extra con el
-- conteo. pairs() recorre todas las claves, asi que ademas de los objetos
-- entrega ese numero como si fuera un elemento mas. Al pasarselo a una
-- funcion que hacia obj:GetAlgo() el script reventaba con
--     attempt to index local 'folder' (a number value)
-- y no colocaba nada, aunque la app dijera que si.
--
-- En Python (Studio) no pasaba: ahi la lista es normal. Era del puerto a Lua.
--
-- ipairs recorre solo la parte 1..n e ignora esa clave. Ademas se filtra
-- cualquier cosa que no se pueda indexar, para que no vuelva a pasar por
-- otra via.
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
    if io == nil then
        -- Free 21.1: solo queda loadfile. Para un archivo de TEXTO (el .srt
        -- de la pista normal/traducida) la app deja "<ruta>.lua" con
        -- `return { texto = ... }` (subtitle_transcriber.write_srt). Los
        -- .json van por cargar_tabla, que es tabla directa.
        local chunk = loadfile(ruta .. ".lua")
        local ok, t = pcall(chunk or function() end)
        return (ok and type(t) == "table") and t.texto or nil
    end
    local f = io.open(ruta, "r")
    if not f then return nil end
    local c = f:read("*a"); f:close(); return c
end

local function archivo_existe(ruta)
    -- Sin io no se puede mirar el disco: se da por existente y decide la
    -- API (ImportFolderFromFile / ImportMedia / LoadSettings ya fallan
    -- bien con un archivo ausente, y cada llamador lo dice). Para los .json
    -- esta dato_existe, que si mira el sidecar.
    if io == nil then return true end
    local f = io.open(ruta, "r")
    if f then f:close(); return true end
    return false
end

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
                local e = texto:sub(pos, pos)
                if e == "n" then table.insert(partes, "\n")
                elseif e == "t" then table.insert(partes, "\t")
                else table.insert(partes, e) end
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
            pos = pos + 1; saltar()
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

-- Leer sin io: Free 21.1 capo io en el menu de Scripts, asi que los .lua no
-- pueden abrir archivos. El unico canal de lectura que sobrevive es loadfile,
-- y la app deja junto a cada .json un sidecar "<ruta>.lua" con `return {tabla}`
-- (ver sidecar_lua.py). Con io se lee el .json como siempre; sin io, el sidecar.
local SIN_IO = (io == nil)

local function cargar_tabla(ruta)
    if not SIN_IO then
        local txt = leer_archivo(ruta)
        if not txt then return nil end
        local ok, t = pcall(parsear_json, txt)
        return (ok and type(t) == "table") and t or nil
    end
    local chunk = loadfile(ruta .. ".lua")
    if not chunk then return nil end
    local ok, t = pcall(chunk)
    return (ok and type(t) == "table") and t or nil
end

local function dato_existe(ruta)
    if not SIN_IO then return archivo_existe(ruta) end
    return loadfile(ruta .. ".lua") ~= nil
end

local function fail(msg)
    print("[Subtitulos] ERROR: " .. msg)
    guardar_resultado(false, msg)
    error(msg, 0)
end

-- ---------------------------------------------------------------------
-- Copia profunda y mezcla de estilos (equivale a estilos_del_preset)
-- ---------------------------------------------------------------------
local function copiar(t)
    local r = {}
    for k, v in pairs(t) do
        if type(v) == "table" then r[k] = copiar(v) else r[k] = v end
    end
    return r
end

-- Desincronia real con el gemelo .py (v1.0.49): la eleccion de
-- tipografias del usuario (track.fonts) se ignoraba por completo en
-- Free. Mismo contrato que estilos_con_fuentes del .py.
local function estilos_con_fuentes(fuentes)
    local estilos = copiar(AUTO_STYLES)
    if type(fuentes) ~= "table" then return estilos end
    if fuentes.main_family then
        estilos.context.font = fuentes.main_family
        estilos.main.font = fuentes.main_family
    end
    if fuentes.complement_family then
        estilos.complement.font = fuentes.complement_family
    end
    if fuentes.tracking ~= nil then
        for _, rol in pairs({ "context", "main", "complement" }) do
            estilos[rol].tracking = tonumber(fuentes.tracking)
        end
    end
    if fuentes.line_spacing ~= nil then
        for _, rol in pairs({ "context", "main", "complement" }) do
            estilos[rol].line_spacing = tonumber(fuentes.line_spacing)
        end
    end
    return estilos
end

local function estilos_del_preset(base, indice)
    local resultado = copiar(base or AUTO_STYLES)
    local variante = AUTO_PRESETS[((indice - 1) % #AUTO_PRESETS) + 1]
    for rol, cambios in pairs(variante) do
        if resultado[rol] then
            for k, v in pairs(cambios) do resultado[rol][k] = v end
        end
    end
    return resultado
end

-- ---------------------------------------------------------------------
-- Packs de estilos
-- ---------------------------------------------------------------------
-- El pack viaja YA RESUELTO en el manifiesto: la app leyo estilos.json con
-- plantillas.py y mando los sets que hay, en el orden en que rotan, con la
-- carpeta donde estan los .setting. El script no lee estilos.json: asi la
-- validacion vive en un solo sitio y no hay dos parsers que se separen.
--
-- Prioridad, y no cambia: las plantillas del Media Pool del usuario mandan
-- sobre el pack, y el pack sobre el diseno automatico.
-- Los dos formatos viajan en el manifiesto y se elige AQUI, porque la
-- resolucion del timeline solo se conoce dentro de Resolve. Eligiendo en la
-- app, un pack completo se aplicaria en horizontal sobre un video vertical sin
-- que nadie lo notara.
local function pack_del_manifiesto(track_info, ancho, alto)
    local p = track_info and track_info.plantilla
    if type(p) ~= "table" then return nil end
    local formatos = p.formatos
    if type(formatos) ~= "table" then return nil end

    -- 'formato_forzado' es la eleccion EXPLICITA del usuario y manda sobre la
    -- deteccion: adivinar por la resolucion no siempre acierta -un timeline
    -- cuadrado no es ni una cosa ni la otra-, y lo que eligio una persona
    -- gana siempre a nuestra heuristica.
    local ETIQUETA_FORMATO = { h = "horizontal", v = "vertical", c = "cuadrado" }
    local forzado = p.formato_forzado
    local quiere
    if forzado == "h" or forzado == "v" or forzado == "c" then
        quiere = forzado
    else
        local a, b = tonumber(ancho) or 0, tonumber(alto) or 0
        if a > 0 and b > 0 and math.abs(a - b) <= 0.05 * math.max(a, b) then
            quiere = "c"
        else
            quiere = (b > a) and "v" or "h"
        end
    end
    local usado, aviso = quiere, nil
    if formatos[quiere] == nil then
        -- Se usa el mas parecido (para 'c' antes 'v' que 'h', etc.), pero se
        -- DICE: los tamaños de letra no se traducen entre formatos.
        local ORDEN = { c = { "v", "h" }, v = { "c", "h" }, h = { "c", "v" } }
        for _, f in ipairs(ORDEN[quiere]) do
            if formatos[f] ~= nil then usado = f; break end
        end
        if formatos[usado] == nil then
            usado = next(formatos)
            if usado == nil then return nil end
        end
        aviso = "el pack no trae version " .. ETIQUETA_FORMATO[quiere] ..
            ": uso la " .. ETIQUETA_FORMATO[usado] .. ". Los tamaños de "
            .. "letra no se traducen entre formatos, revisa como queda."
    end

    local bloque = formatos[usado] or {}
    local sets = {}
    for _, s in ipairs(bloque.sets or {}) do
        if type(s) == "table" then sets[#sets + 1] = s end
    end
    local base = (type(bloque.base) == "table") and bloque.base or nil
    local drt = (type(bloque.drt) == "string") and bloque.drt or nil
    local drb = (type(bloque.drb) == "string") and bloque.drb or nil
    -- Un pack SOLO-bin tambien vale (v1.0.57): trae drb sin drt y el
    -- peldaño drb lo importa entero.
    if #sets == 0 and base == nil and drt == nil and drb == nil then
        return nil
    end
    local sets_drt = {}
    for _, n in ipairs(bloque.sets_drt or {}) do sets_drt[#sets_drt + 1] = n end
    return {
        -- la revisión (v5.8) hace que un bin del pack importado ANTES, con otros clips, no se reutilice
        nombre = (p.pack or "?") .. ((p.revision ~= nil and p.revision ~= "") and (" · " .. tostring(p.revision)) or ""),
        formato = usado,
        carpeta = bloque.carpeta or "",
        sets = sets,
        base = base,
        aviso = aviso,
        drt = drt,
        drb = drb,
        sets_drt = sets_drt,
        base_drt = bloque.base_drt == true,
        -- {rol: [numeros de set]} cuya tipografia NO dibuja tildes
        -- (v1.0.61). Lo mide la app con los archivos de fuente delante;
        -- aqui solo se aplica al elegir set. Nil o vacio = sin veto.
        sets_sin_acentos = (type(bloque.sets_sin_acentos) == "table")
            and bloque.sets_sin_acentos or {},
        -- {"rol|numero": {"Arial", estilo}} para los clips cuya tipografia
        -- NO esta en el equipo (v2.0.2). Tambien lo mide la app; aqui se
        -- escribe Font/Style tras el texto. Vacio = nada que sustituir.
        fuentes_respaldo = (type(bloque.fuentes_respaldo) == "table")
            and bloque.fuentes_respaldo or {},
        -- Los .setting de la cache instalada no traen posicion: el que
        -- coloca tiene que reponer la altura por rol (ver rama 'cargado').
        settings_sin_posicion = bloque.settings_sin_posicion == true,
        -- {"rol|numero": {x, y, zoom_x, zoom_y}} (v3.3.0): la posicion de
        -- pagina Edicion del diseño, clip por clip, normalizada. La aplica
        -- aplicar_transformacion SOLO si Resolve no la aplico al colocar.
        transformaciones = (type(bloque.transformaciones) == "table")
            and bloque.transformaciones or {},
    }
end

-- El manifiesto trae el color como lista [r, g, b] -que es como lo guarda
-- estilos.json- pero aqui los estilos usan campos r/g/b sueltos. Sin esta
-- traduccion el color del pack se perderia en silencio y el texto saldria
-- blanco: exactamente el tipo de fallo mudo que no queremos.
local function estilo_del_manifiesto(e)
    local r = {
        font = e.font or "Open Sans",
        style = e.style or "Regular",
        size = tonumber(e.size) or 0.05,
        tracking = tonumber(e.tracking) or 1.0,
        r = 1.0, g = 1.0, b = 1.0,
    }
    if type(e.color) == "table" then
        r.r = tonumber(e.color[1]) or 1.0
        r.g = tonumber(e.color[2]) or 1.0
        r.b = tonumber(e.color[3]) or 1.0
    end
    if e.line_spacing then r.line_spacing = tonumber(e.line_spacing) end
    -- Desincronia real con el gemelo .py (v1.0.49): esta tabla se
    -- reconstruye campo a campo y el contorno del manifiesto se caia —
    -- un pack (o un diseño) con outline salia sin contorno en Free.
    if type(e.outline) == "table" then
        local c = e.outline.color
        r.contorno = {
            grosor = tonumber(e.outline.thickness) or 0.2,
            r = (type(c) == "table" and tonumber(c[1])) or 0.0,
            g = (type(c) == "table" and tonumber(c[2])) or 0.0,
            b = (type(c) == "table" and tonumber(c[3])) or 0.0,
        }
    end
    return r
end

-- Los tres roles de un set del pack, COMPLETOS. Un set al que le falte un rol
-- lo toma del diseno automatico: devolver un estilo incompleto dejaria a
-- altura_de_linea sin el tamano y el bucle de colocacion se caeria a mitad.
local function estilos_del_pack(pack, indice)
    local resultado = copiar(AUTO_STYLES)
    if #pack.sets == 0 then return resultado, nil end
    local entrada = pack.sets[((indice - 1) % #pack.sets) + 1]
    for _, rol in ipairs({ "context", "main", "complement" }) do
        if type(entrada[rol]) == "table" then
            resultado[rol] = estilo_del_manifiesto(entrada[rol])
        end
    end
    return resultado, entrada.n
end

-- Donde vive el nodo entero de ese rol. Mismo nombre que puso el importador;
-- si el archivo no esta, quien llame se queda con los valores.
local function ruta_de_setting(pack, n, rol)
    if not pack or pack.carpeta == "" or n == nil then return nil end
    local sep = es_windows() and "\\" or "/"
    local nombre = (rol == "base") and "base.setting"
        or string.format("%02d-%s.setting", math.floor(tonumber(n) or 0), rol)
    return pack.carpeta .. sep .. nombre
end

-- Que variante le toca a cada bloque, sin repetir dos seguidas. Equivale a
-- orden_de_variantes del .py; el reparto exacto no tiene que coincidir con
-- Studio, solo cumplir la regla de no repetir.
local function orden_de_variantes(cantidad, sets, semilla)
    if sets <= 1 then
        local r = {}
        for i = 1, cantidad do r[i] = 1 end
        return r
    end
    math.randomseed(semilla)
    local orden, ultimo = {}, nil
    while #orden < cantidad do
        local vuelta = {}
        for i = 1, sets do vuelta[i] = i end
        for i = sets, 2, -1 do
            local j = math.random(1, i)
            vuelta[i], vuelta[j] = vuelta[j], vuelta[i]
        end
        if vuelta[1] == ultimo and sets > 1 then
            vuelta[1], vuelta[2] = vuelta[2], vuelta[1]
        end
        for _, v in ipairs(vuelta) do table.insert(orden, v) end
        ultimo = vuelta[#vuelta]
    end
    local recorte = {}
    for i = 1, cantidad do recorte[i] = orden[i] end
    return recorte
end

-- ---------------------------------------------------------------------
-- Helpers de Fusion / Text+
-- ---------------------------------------------------------------------
local function get_text_plus(item)
    local comp = item:GetFusionCompByIndex(1)
    if not comp then return nil end
    -- los packs viralized llevan varios Text+ de apoyo: el que recibe el texto se llama «Template»
    local plantilla = comp:FindTool("Template")
    if plantilla then
        local ok, id = pcall(function() return plantilla.ID end)
        if ok and id == "TextPlus" then return plantilla end
    end
    for _, tool in ipairs(lista_api(comp:GetToolList())) do
        local ok, id = pcall(function() return tool.ID end)
        if ok and id == "TextPlus" then return tool end
    end
    return nil
end

local function set_input(tool, nombre, valor)
    local ok = pcall(function() tool:SetInput(nombre, valor) end)
    return ok
end

-- v5.5 — el BARRIDO DE LUZ del macro Luxe Shine (palabras grandes del estilo «guion»); gemela de ajustar_barrido de CineCaptions.py. De fábrica empieza a los 0,25 s y
-- tarda 1,5 s, pero una palabra grande se ve ~0,55 s (mediana): el barrido se quedaba a medias. Aquí empieza justo al entrar (salto = lo que ya se adelantó el comp) y
-- termina antes de que la palabra salga (dura 0,18-0,50 s). Si el clip no es un Luxe Shine (presets de Amro) no hace nada.
-- El macro calcula el RECORRIDO de la banda con el DataWindow del texto, que dentro de un macro no llega: recorre siempre ~0,31 del ancho del cuadro y en una palabra ancha sólo pasaba
-- por el centro. Medido en Resolve: recorrido (en anchos de cuadro) ~ 2,17 x (0,193 + inputShine). Gemela de BARRIDO_K / BARRIDO_BASE de CineCaptions.py.
local BARRIDO_K = 2.17
local BARRIDO_BASE = 0.193
local function ajustar_barrido(item, visible_s, salto_s, ancho_rel)
    local hecho = false
    pcall(function()
        local comp = item:GetFusionCompByIndex(1)
        if not comp then return end
        local macro = comp:FindTool("LuxeShine")
        if not macro then
            for _, herramienta in ipairs(lista_api(comp:GetToolList())) do
                local ok, v = pcall(function() return herramienta:GetInput("inputLength") end)
                if ok and v ~= nil then
                    macro = herramienta
                    break
                end
            end
        end
        if not macro then return end
        local largo = math.max(0.16, math.min(0.50, visible_s - 0.22))        -- la entrada del macro tarda 0,14 s y la salida 0,10: el barrido va entre las dos
        local a = set_input(macro, "inputOffset", (salto_s or 0) + 0.10)
        local b = set_input(macro, "inputLength", largo)
        if type(ancho_rel) == "number" and ancho_rel > 0 then
            set_input(macro, "inputShine", math.max(-0.05, (ancho_rel + 0.16) / BARRIDO_K - BARRIDO_BASE))
        end
        hecho = a and b
    end)
    return hecho
end

-- Los clips de las plantillas tienen SU frame rate (los .drb se crearon
-- a 30 fps: lo dice su FieldsBlob) y startFrame/endFrame de
-- AppendToTimeline son fotogramas DE ORIGEN: Resolve los convierte al
-- timeline con floor((endFrame - startFrame) * fps_timeline / fps_clip).
-- Medido en el registro de la Mac del usuario (v2.0.4, timeline a 24 fps,
-- 40 clips sin excepcion): pedi 19 -> 14, 52 -> 40, 84 -> 66 =
-- floor((N - 1) * 24/30). En Windows (timeline a 30 fps) la misma
-- formula da N - 1: el «fotograma de menos» de la v2.0.3 era el caso
-- k = 1 de esta regla. Por eso Free iba 10/10 en Windows y la Mac salia
-- en escalera y con huecos con el MISMO codigo: no era Studio, era el
-- fps del timeline. Se pide el mayor span de origen que no se pasa
-- (span_para) con el factor k del clip: GetClipProperty("FPS") si
-- contesta, y siempre VERIFICADO con la primera medida — si no cuadra,
-- k se aprende del cociente medido (ajustado al frame rate mas cercano:
-- el floor pierde precision en clips cortos) y el clip se recoloca.
local FACTORES = {}     -- nombre del clip -> fotogramas de timeline por fotograma de origen
local CALIBRADOS = {}   -- nombres ya verificados con una medida real
local OFF = { valor = 0 }  -- 1 si este Resolve CUENTA el fotograma final (inclusivo)
local FPS_CLIP_CANDIDATOS = { 23.976, 24.0, 25.0, 29.97, 30.0, 48.0, 50.0,
                              59.94, 60.0, 120.0 }

local function duracion_de(item)
    local puesto = 0
    pcall(function()
        puesto = math.floor(tonumber(item:GetDuration()) or 0)
    end)
    return puesto
end

local function nombre_clip(plantilla)
    local ok, n = pcall(function() return plantilla:GetName() end)
    if ok and n then return tostring(n) end
    return ""
end

-- Fotogramas de timeline por fotograma de origen de ese clip; 1.0 si
-- no hay forma de saberlo todavia.
local function factor_de(plantilla, fps)
    local nombre = nombre_clip(plantilla)
    if FACTORES[nombre] ~= nil then return FACTORES[nombre] end
    if fps and fps > 0 then
        local fps_clip = 0
        pcall(function()
            fps_clip = tonumber(plantilla:GetClipProperty("FPS")) or 0
        end)
        if fps_clip > 0 then
            FACTORES[nombre] = fps / fps_clip
            return FACTORES[nombre]
        end
    end
    return 1.0
end

-- El factor medido, llevado al cociente de frame rates mas cercano (a
-- menos de un 4%); nil si ninguno cuadra — entonces NO es un frame rate:
-- es un recorte real (comp mas corto que el bloque) y no se toca el
-- factor. Sin eso, un comp de 150 sobre un bloque de 270 daba k = 0.556
-- y las hermanas salian LARGAS (solapando al siguiente).
local function ajustar_factor(k_medido, fps)
    if not fps or fps <= 0 or k_medido <= 0 then return nil end
    local mejor, dist = nil, nil
    for _, c in ipairs(FPS_CLIP_CANDIDATOS) do
        local d = math.abs(fps / c - k_medido)
        if dist == nil or d < dist then mejor, dist = c, d end
    end
    local k = fps / mejor
    if math.abs(k - k_medido) <= 0.04 * k then return k end
    return nil
end

-- Fotogramas de ORIGEN a pedir: el mayor span con floor(span * k) <=
-- duracion (con k = 1 es duracion; con k < 1 cae exacto; con k > 1
-- puede quedar uno corto, nunca uno largo).
local function span_para(duracion, k)
    return math.max(1, math.ceil((duracion - OFF.valor + 1) / k - 1e-9) - 1)
end

-- v5.7 (pedido: «colorea los textos y sonidos de naranja, los emojis con su
-- sonido de amarillo y los sonidos de entrada y salida de morado»): colores de
-- Resolve (TimelineItem:SetClipColor) para reconocerlos en la linea de tiempo.
-- Una sola tabla (el chunk esta cerca del limite de 200 locales).
local COLORES_CC = {
    texto = "Orange", sfx = "Orange", emoji = "Yellow",
    sfx_emoji = "Yellow", sfx_entrada_salida = "Purple",
}
function COLORES_CC.pintar(item, color)
    if item ~= nil and color ~= nil then
        pcall(function() item:SetClipColor(color) end)
    end
end
function COLORES_CC.de_sfx(categoria)
    local c = tostring(categoria or "")
    if c:find("Introducci", 1, true) or c:sub(-5) == "Final" then
        return COLORES_CC.sfx_entrada_salida
    end
    if c == "Emojis" then return COLORES_CC.sfx_emoji end
    return COLORES_CC.sfx
end

-- AppendToTimeline con la duracion EXACTA en el timeline. Devuelve item,
-- puesto (item nil si no se pudo colocar). Sin 'timeline' no se puede
-- borrar y recolocar: se usa el factor conocido y no se calibra.
local function colocar_medido(media_pool, timeline, plantilla, desde,
                              duracion, pista, record, fps, color)
    local nombre = nombre_clip(plantilla)
    local k = factor_de(plantilla, fps)

    local function pedir(k_uso)
        local span = span_para(duracion, k_uso)
        local ini = 0
        if desde and desde > 0 then ini = math.floor(desde / k_uso + 0.5) end
        local ok, nuevos = pcall(function()
            return media_pool:AppendToTimeline({ {
                mediaPoolItem = plantilla,
                startFrame = ini,
                endFrame = ini + span,
                trackIndex = pista,
                mediaType = 1,
                recordFrame = record,
            } })
        end)
        -- Una tabla vacia es VERDADERA en Lua: hay que mirar nuevos[1].
        if ok and nuevos and nuevos[1] then return nuevos[1], span end
        return nil, span
    end

    -- Borra 'viejo' y vuelve a pedir; si lo nuevo no entra, repone con
    -- el factor anterior. Devuelve item, span (nil = no pudo borrar, el
    -- viejo sigue puesto), puesto.
    local function recolocar(viejo, k_uso)
        local borrado = pcall(function() timeline:DeleteClips({ viejo }) end)
        if not borrado then return viejo, nil, duracion_de(viejo) end
        local nuevo, span_n = pedir(k_uso)
        if nuevo == nil then nuevo, span_n = pedir(k) end
        return nuevo, span_n, (nuevo and duracion_de(nuevo) or 0)
    end

    local item, span = pedir(k)
    if item == nil then return nil, 0 end
    local puesto = duracion_de(item)
    if timeline ~= nil and puesto > 0 and puesto ~= duracion
            and duracion > 1 and not CALIBRADOS[nombre] then
        CALIBRADOS[nombre] = true
        -- 1) ¿Otro frame rate? Solo si el cociente medido se aleja mas
        --    de un 1% del factor en uso (29.97 frente a 30 no cuenta).
        local k2 = ajustar_factor((puesto - OFF.valor) / span, fps)
        if k2 ~= nil and math.abs(k2 - k) > 0.01 * k then
            FACTORES[nombre] = k2
            local span2
            item, span2, puesto = recolocar(item, k2)
            if item == nil then return nil, 0 end
            if span2 == nil or (puesto ~= duracion and puesto ~= duracion + 1) then
                -- No era el frame rate (un recorte que por casualidad
                -- cuadraba): el factor vuelve; el clip queda como salio.
                FACTORES[nombre] = k
                COLORES_CC.pintar(item, color)
                return item, puesto
            end
            k, span = k2, span2
            print(string.format("  La plantilla '%s' corre a otro frame "
                .. "rate que el timeline (factor %.3f): pido %d fotogramas "
                .. "de origen por cada %d del timeline.",
                nombre, k2, span2, duracion))
        end
        -- 2) ¿Fin inclusivo? Un fotograma de MAS con el factor bueno.
        if puesto == duracion + 1 and OFF.valor == 0 then
            OFF.valor = 1
            local span2
            item, span2, puesto = recolocar(item, k)
            if item == nil then return nil, 0 end
            if span2 == nil then
                OFF.valor = 0
            else
                print("  Resolve cuenta el fotograma final: pido uno menos "
                      .. "en todos los clips.")
            end
        end
    elseif puesto > 0 and puesto == duracion then
        CALIBRADOS[nombre] = true
    end
    COLORES_CC.pintar(item, color)
    return item, puesto
end


-- CARGAR UN PACK DE ESTILOS
--
-- Un pack guarda cada Text+ ENTERO en un .setting (ver plantillas.py).
-- Cargarlo es lo fiel: se lleva degradados, formas y fondos, cosas que no
-- caben en un punado de valores.
--
-- La prueba del Paso 0 confirmo que LoadSettings responde en Resolve 21, pero
-- es API de FUSION y no de Resolve, y no esta en la documentacion oficial de
-- scripting: puede no responder en otra version. Se prueba una vez y se
-- recuerda; si no va, el pack se sigue aplicando por sus VALORES, que es
-- exactamente para lo que existe estilos.json.
--
-- Tiene que dar lo mismo que cargar_setting() del .py: hay un test que lo
-- compara con lupa.
local PACK_CARGA = nil      -- nil sin averiguar, true/false despues
local PACK_MOTIVO = nil

local function cargar_setting(item, tool, ruta, estilo)
    if PACK_CARGA == false or ruta == nil or ruta == "" then return false end
    -- archivo_existe (no una copia con io.open directo): sin io da por
    -- existente y LoadSettings, que lee por su cuenta, decide.
    if not archivo_existe(ruta) then return false end

    -- Solo el PRIMER intento decide si esta version de Resolve sabe cargar
    -- settings. Despues, un fallo es de ESE archivo (corrupto, de otra
    -- version de Fusion) y no puede apagar el pack entero.
    local primero = (PACK_CARGA == nil)

    local ok = pcall(function() tool:LoadSettings(ruta) end)
    if not ok then
        if primero then
            PACK_CARGA = false
            PACK_MOTIVO = "LoadSettings no respondio"
        end
        return false
    end

    -- Que la llamada no reviente NO basta — es el mismo error que se
    -- descubrio en el fundido. Se comprueba que de verdad aplico algo.
    if type(estilo) == "table" then
        local fuente, tam = "", 0
        pcall(function()
            fuente = tostring(tool:GetInput("Font") or "")
            tam = tonumber(tool:GetInput("Size")) or 0
        end)
        local esperada = tostring(estilo.font or "")
        local esp_tam = tonumber(estilo.size) or 0
        -- Se exige que fallen LAS DOS para darlo por no aplicado: Resolve
        -- devuelve a veces el nombre de la fuente escrito distinto del que se
        -- guardo, y con un solo criterio un pack que si se cargo quedaria
        -- descartado.
        if esperada ~= "" and fuente ~= esperada
                and math.abs(tam - esp_tam) > 0.001 then
            if primero then
                PACK_CARGA = false
                PACK_MOTIVO = "LoadSettings no dio error pero no aplico nada "
                    .. "(esperaba '" .. esperada .. "', quedo '" .. fuente .. "')"
            end
            return false
        end
    end

    PACK_CARGA = true

    -- Reponer lo que el .setting trae de su timeline de origen. Guarda dentro
    -- el GlobalIn/GlobalOut y el Width/Height de donde se diseno (en el de
    -- prueba: 1080x1920 y GlobalOut 149); si se quedaran puestos, el texto se
    -- cortaria a mitad del clip o saldria con el tamano de otra resolucion.
    local comp = nil
    pcall(function() comp = item:GetFusionCompByIndex(1) end)
    if comp then
        pcall(function()
            local attrs = comp:GetAttrs() or {}
            local fin = attrs.COMPN_GlobalEnd
            if fin ~= nil then
                tool:SetInput("GlobalIn", attrs.COMPN_GlobalStart or 0)
                tool:SetInput("GlobalOut", fin)
            end
        end)
    end
    -- A 1 significa "usa el tamano de ESTE timeline". Si el disenador lo dejo
    -- en 0, el texto saldria dimensionado para la resolucion en la que se
    -- diseno, que es justo lo que no queremos al reusar un pack.
    set_input(tool, "UseFrameFormatSettings", 1)
    return true
end

-- La transformacion de pagina Edicion del DISEÑO (v3.3.0, reporte: 4 de
-- 550 clientes veian las tres lineas ENCIMADAS en el centro). La posicion y
-- el zoom de cada clip de un pack NO viven en su comp (Text+ sin Center,
-- PolyPath en reposo en 0): viven en el project.xml del .drb, un blob por
-- clip, y la mayoria de los Resolve la aplican solos al colocar el clip
-- -el del usuario si, el de esos clientes no-. La app la manda ya decodificada
-- (plantillas.transformaciones_de_drb). Solo se escribe si el clip llego con
-- la transformacion NEUTRA: donde Resolve ya la puso, no se toca nada. Pan y
-- Tilt van en pixeles del timeline (la API: "-4.0*width to 4.0*width").
local TRANSF = { ya = 0, puestas = 0, fallidas = 0 }

local function prop_de(item, clave)
    local ok, v = pcall(function() return item:GetProperty(clave) end)
    if ok then return tonumber(v) end
    return nil
end

local function poner_props(item, props)
    -- 21.1 trae SetProperties (y da SetProperty por forma vieja); las
    -- versiones anteriores solo tienen SetProperty. Se prueban las dos.
    local function una_vez()
        local ok, r = pcall(function() return item:SetProperties(props) end)
        if ok and r then return true end
        local todo = true
        for k, v in pairs(props) do
            local ok2, r2 = pcall(function() return item:SetProperty(k, v) end)
            if not (ok2 and r2) then todo = false end
        end
        return todo
    end
    if una_vez() then return true end
    -- v5.4.16 (auto-reparacion, visto en Resolve Free: de vez en cuando un clip recien puesto rechaza su primera orden y quedaba sin tamano ni posicion):
    -- una pausa corta y UN reintento. Solo se paga cuando falla.
    pcall(function() if bmd and bmd.wait then bmd.wait(0.2) end end)
    return una_vez()
end

-- Las UNIDADES de Pan/Tilt, en un solo sitio (v3.3.1): fraccion del
-- ancho/alto del cuadro (centro = 0, Y+ arriba) -> lo que pide la API. Hoy
-- pixeles del timeline ("-4.0*width to 4.0*width"); si la sonda
-- CineCaptions_Sonda_Transform mide otra cosa, se cambia AQUI y en el gemelo .py.
local function pan_px(x, ancho) return x * ancho end
local function tilt_px(y, alto) return y * alto end

-- ---------------------------------------------------------------------
-- La «Composición» (v3.4.0; la definicion vive en composicion.py de la app
-- y ESTAS son sus copias gemelas — test_v340 las compara). El layout es
-- la alineacion horizontal de contexto y complemento respecto a la
-- PRINCIPAL: dos letras (contexto, complemento) en i/c/d; 'c' = donde la
-- dejo la plantilla; "auto" = uno por bloque, elegido por el fotograma en
-- que arranca el bloque. Altura/Horizontal desplazan el grupo entero. Sin
-- composicion (o "cc" con 0/0) NO se escribe nada: la plantilla manda,
-- como desde la v1.0.32. Este ajuste es opcional y lo pidio el usuario para
-- «ajustar la posicion de los textos ya puestos» (rama recomponer).
-- ---------------------------------------------------------------------
local ANILLO_AUTO = { "id", "cc", "di", "ic", "dd", "ci", "ii", "cd", "dc" }
local COMP_TOPE = 0.4
local COMP = { movidas = 0, alineadas = 0, sin_medida = 0, fallidas = 0,
               layout = nil }

local function composicion_normal(c)
    local function num(v)
        v = tonumber(v) or 0
        if v > COMP_TOPE then v = COMP_TOPE elseif v < -COMP_TOPE then v = -COMP_TOPE end
        return v
    end
    if type(c) ~= "table" then c = {} end
    local layout = string.lower(tostring(c.layout or "cc"))
    if layout ~= "auto" and not layout:match("^[icd][icd]$") then layout = "cc" end
    local semilla = math.floor(tonumber(c.semilla) or 0) % #ANILLO_AUTO
    return { layout = layout, altura = num(c.altura),
             horizontal = num(c.horizontal), semilla = semilla }
end

local function composicion_es_defecto(comp)
    return comp.layout == "cc" and comp.altura == 0 and comp.horizontal == 0
end

-- La composicion ACTIVA del track, o nil si es la plantilla tal cual.
local function composicion_activa(c)
    if type(c) ~= "table" then return nil end
    local comp = composicion_normal(c)
    if composicion_es_defecto(comp) then return nil end
    return comp
end

-- 'bloque' = el fotograma donde arranca el bloque (record de su primera
-- linea). El floor(bloque / 9) rompe la periodicidad de 9.
local function layout_del_bloque(comp, bloque)
    if comp.layout ~= "auto" then return comp.layout end
    local b = math.max(0, math.floor(tonumber(bloque) or 0))
    return ANILLO_AUTO[((b + math.floor(b / 9) + comp.semilla) % #ANILLO_AUTO) + 1]
end

local function desplazamiento_layout(lado, w_main, w_linea)
    if lado == "i" then return -(w_main - w_linea) / 2 end
    if lado == "d" then return (w_main - w_linea) / 2 end
    return 0
end

-- Los desplazamientos (px) de las lineas de UN bloque. 'lineas' es una
-- lista de { rol=, ancho_em=, zx= } (ancho_em: la medida de la app en
-- fraccion del alto; nil si no la hay). Devuelve una lista paralela de
-- { dx=, dy=, alineada=, sin_medida= }: la principal y las base solo
-- reciben los globales; contexto/complemento ademas la alineacion, si
-- hay medida suya Y de la principal.
local function desplazamientos_bloque(comp, bloque, lineas, ancho_tl, alto_tl)
    local dx_g = pan_px(comp.horizontal, ancho_tl)
    local dy_g = tilt_px(comp.altura, alto_tl)
    local layout = layout_del_bloque(comp, bloque)
    local lado = { context = layout:sub(1, 1), complement = layout:sub(2, 2) }
    local w_main = nil
    for _, l in ipairs(lineas) do
        if l.rol == "main" and tonumber(l.ancho_em) then
            w_main = tonumber(l.ancho_em) * alto_tl * (tonumber(l.zx) or 1)
        end
    end
    local fuera = {}
    for k, l in ipairs(lineas) do
        local dx, alineada, sin_medida = dx_g, false, false
        local ld = lado[l.rol]
        if ld and ld ~= "c" then
            if w_main and tonumber(l.ancho_em) then
                dx = dx + desplazamiento_layout(ld, w_main,
                    tonumber(l.ancho_em) * alto_tl * (tonumber(l.zx) or 1))
                alineada = true
            else
                sin_medida = true
            end
        end
        fuera[k] = { dx = dx, dy = dy_g, alineada = alineada,
                     sin_medida = sin_medida }
    end
    return fuera, layout
end

local function informe_composicion()
    if COMP.layout == nil then return end
    print(string.format("  Composición: layout %s, %d clip(s) movido(s), %d "
        .. "línea(s) alineada(s), %d sin medida%s.", tostring(COMP.layout),
        COMP.movidas, COMP.alineadas, COMP.sin_medida,
        COMP.fallidas > 0 and string.format(", %d sin poder mover (la API "
            .. "dijo que no)", COMP.fallidas) or ""))
end

local function aplicar_transformacion(item, t, ancho, alto)
    if type(t) ~= "table" or not item then return end
    local x, y = tonumber(t[1]) or 0, tonumber(t[2]) or 0
    local zx, zy = tonumber(t[3]) or 1, tonumber(t[4]) or 1
    if x == 0 and y == 0 and zx == 1 and zy == 1 then return end
    local pan, tilt = prop_de(item, "Pan"), prop_de(item, "Tilt")
    local zoom = prop_de(item, "ZoomX")
    if (pan and math.abs(pan) > 0.01) or (tilt and math.abs(tilt) > 0.01)
            or (zoom and math.abs(zoom - 1) > 0.0001) then
        TRANSF.ya = TRANSF.ya + 1
        if TRANSF.medida == nil and tilt and y ~= 0 then
            TRANSF.medida = string.format("Tilt %.1f para Y %.4f", tilt, y)
        end
        return
    end
    local pedido = { Pan = pan_px(x, ancho), Tilt = tilt_px(y, alto),
                     ZoomX = zx, ZoomY = zy }
    local ok = poner_props(item, pedido)
    local leido = prop_de(item, "Tilt")
    if ok and (leido == nil or math.abs(leido - pedido.Tilt) < 1) then
        TRANSF.puestas = TRANSF.puestas + 1
    else
        TRANSF.fallidas = TRANSF.fallidas + 1
        TRANSF.motivo = TRANSF.motivo or (ok and string.format(
            "pedi Tilt %.1f y quedo %s", pedido.Tilt, tostring(leido))
            or "SetProperty no respondio")
    end
end

-- Una linea, cerca del FINAL del registro: el reporte que llega sin io solo
-- conserva las ultimas ~24 lineas, y esta es la que cierra el caso.
local function informe_transformaciones()
    local partes = {}
    if TRANSF.ya > 0 then
        partes[#partes + 1] = string.format("Resolve ya la traia en %d "
            .. "linea(s)", TRANSF.ya)
    end
    if TRANSF.puestas > 0 then
        partes[#partes + 1] = string.format("la aplique yo en %d (tu "
            .. "Resolve la habia dejado en el centro)", TRANSF.puestas)
    end
    if TRANSF.fallidas > 0 then
        partes[#partes + 1] = string.format("NO pude en %d: %s",
            TRANSF.fallidas, tostring(TRANSF.motivo or "?"))
    end
    if #partes == 0 then return end
    print("  Posicion del diseño: " .. table.concat(partes, "; ")
          .. (TRANSF.medida and (" (" .. TRANSF.medida .. ")") or "") .. ".")
end

local function set_center(tool, x, y)
    -- La API acepta el centro de varias formas; probamos las conocidas.
    if set_input(tool, "Center", { [1] = x, [2] = y }) then return true end
    if set_input(tool, "Center", { x, y }) then return true end
    return false
end

-- 'y' llega de fuera (ver altura_de_linea): depende de que roles tiene el
-- bloque, no solo del rol de esta linea, asi que no puede salir del estilo.
local function aplicar_estilo(tool, e, y)
    set_input(tool, "Size", e.size)
    set_input(tool, "Font", e.font)
    set_input(tool, "Style", e.style)
    set_center(tool, 0.5, y)
    -- OJO: el input NO se llama 'Tracking'. Hasta la v1.0.25 aqui decia eso
    -- y no existe: el volcado de las 310 entradas de un Text+
    -- (CineCaptions_Prueba_Animaciones) lo confirmo. Se llama 'CharacterSpacing', y
    -- como set_input se traga el fallo, el interletrado nunca se aplico.
    if e.tracking then set_input(tool, "CharacterSpacing", e.tracking) end
    -- Desincronia real con el gemelo .py (v1.0.49): el estilo traia
    -- line_spacing desde el manifiesto pero aqui nunca se escribia.
    if e.line_spacing then set_input(tool, "LineSpacing", e.line_spacing) end
    set_input(tool, "Red1", e.r)
    set_input(tool, "Green1", e.g)
    set_input(tool, "Blue1", e.b)

    -- El contorno (modo Hormozi). Confirmado por la prueba del Paso 0:
    -- Enabled2/Red2/Green2/Blue2/Thickness2 responden. Opcional: la mayoria
    -- de los estilos no lo traen.
    if e.contorno then
        set_input(tool, "Enabled2", 1)
        set_input(tool, "Thickness2", e.contorno.grosor or 0.2)
        set_input(tool, "Red2", e.contorno.r or 0.0)
        set_input(tool, "Green2", e.contorno.g or 0.0)
        set_input(tool, "Blue2", e.contorno.b or 0.0)
    end
end

-- EL FUNDIDO
--
-- Hasta la v1.0.24 esto era 'SetInput("Blend", v, fotograma)' a secas, y
-- devolvia true con que la llamada no reventara. La prueba
-- herramientas/CineCaptions_Prueba_Animaciones demostro que esa llamada NO crea ningun
-- fotograma clave: en Fusion un input es un VALOR FIJO hasta que se le conecta
-- una curva, y pasarle un fotograma no la crea. La llamada no falla —no hace
-- nada—, asi que el contador "con fundido: N" del informe llevaba versiones
-- contando fundidos que nunca existieron.
--
-- Y habia una mina debajo: si SetInput ignora el fotograma, la SEGUNDA llamada
-- deja el input en 0.0 como valor fijo, o sea el subtitulo INVISIBLE.
--
-- Ademas 'Blend' NO EXISTE en un Text+. El volcado de las 310 entradas reales
-- (CineCaptions_Prueba_Animaciones) lo confirmo: la opacidad del texto es 'Alpha1'. O
-- sea que el fundido llevaba versiones escribiendo en un sitio inexistente —
-- de ahi que la mina de arriba no reventara nunca.
--
-- Y de las formas de animar, solo UNA funciona en Resolve 21:
-- comp:BezierSpline() + tool.X = curva + curva:SetKeyFrames{...}. Va primera
-- para no gastar intentos fallidos en el primer clip; las otras se dejan
-- detras por si otra version se comporta distinto.
--
-- Se COMPRUEBA que el valor cambie de verdad entre los dos fotogramas, y si no
-- cambia se devuelve el input a su valor original y se dice que no hubo
-- fundido.

-- Donde escribir la opacidad, en orden de preferencia. 'Blend' queda detras
-- como respaldo: no esta en un Text+, pero si en otros nodos de Fusion.
local FADE_ENTRADAS = { "Alpha1", "Blend" }

local FADE_VIA = nil      -- nil sin averiguar, false imposible, o el indice
local FADE_ENTRADA = nil  -- cual de FADE_ENTRADAS resulto existir
local FADE_MOTIVO = nil

local function _fade_anima(tool, entrada, desde, fin)
    local a, b = nil, nil
    pcall(function() a = tool:GetInput(entrada, desde) end)
    pcall(function() b = tool:GetInput(entrada, fin) end)
    a, b = tonumber(a), tonumber(b)
    if a == nil or b == nil then return false end
    return math.abs(b - a) > 0.01
end

-- La primera es la unica que funciono en Resolve 21, medida por
-- CineCaptions_Prueba_Animaciones. La ultima es la de siempre: se deja porque si una
-- version futura la hiciera funcionar, funcionaria sin tocar nada.
-- 'claves' es { [fotograma] = { valor } }: TODOS los fotogramas del clip
-- (la entrada y la salida juntas) van en la MISMA curva — asignar una
-- curva nueva al input desconecta la anterior, asi que dos llamadas
-- separadas no suman: la segunda borra la primera (v1.0.51).
local FADE_FORMAS = {
    { nombre = "BezierSpline + SetKeyFrames",
      hacer = function(comp, tool, entrada, claves)
          local curva = comp:BezierSpline({})
          if curva == nil then error("sin BezierSpline") end
          tool[entrada] = curva
          curva:SetKeyFrames(claves)
      end },
    { nombre = "BezierSpline por indice",
      hacer = function(comp, tool, entrada, claves)
          local curva = comp:BezierSpline({})
          if curva == nil then error("sin BezierSpline") end
          tool[entrada] = curva
          for f, v in pairs(claves) do curva[f] = v[1] end
      end },
    { nombre = "tool.<entrada>[fotograma]",
      hacer = function(comp, tool, entrada, claves)
          for f, v in pairs(claves) do tool[entrada][f] = v[1] end
      end },
    { nombre = "SetInput con fotograma",
      hacer = function(comp, tool, entrada, claves)
          for f, v in pairs(claves) do tool:SetInput(entrada, v[1], f) end
      end },
}

-- Desconectar la curva y devolver el valor fijo. Sin esto, un intento fallido
-- con la ultima forma deja el subtitulo invisible.
local function _fade_limpiar(tool, entrada, original)
    pcall(function() tool[entrada] = nil end)
    if original ~= nil then
        pcall(function() tool:SetInput(entrada, original) end)
    end
end

-- Fundido de entrada y/o de salida, en UNA sola curva por input (v1.0.51).
-- Devuelve (entrada_ok, salida_ok): cada uno true SOLO si se comprobo que
-- el valor cambia entre sus dos fotogramas. Los dos extremos viajan JUNTOS
-- a proposito: asignar una curva nueva al input desconecta la anterior,
-- asi que aplicar la entrada y despues la salida en llamadas separadas
-- dejaria solo la ultima. Tiene que dar lo mismo que apply_fades del .py.
local function aplicar_fades(item, entrada_frames, salida_frames)
    entrada_frames = math.max(0, math.floor(tonumber(entrada_frames) or 0))
    salida_frames = math.max(0, math.floor(tonumber(salida_frames) or 0))
    if entrada_frames < 1 and salida_frames < 1 then return false, false end
    -- Averiguar la via en cada uno de los 200 subtitulos seria tirar el
    -- tiempo: la respuesta no cambia dentro de la misma sesion.
    if FADE_VIA == false then return false, false end

    local comp = item:GetFusionCompByIndex(1)
    if not comp then return false, false end
    local tool = get_text_plus(item)
    if not tool then return false, false end

    local attrs = comp:GetAttrs() or {}
    local fin = attrs.COMPN_GlobalEnd
    local ini = attrs.COMPN_GlobalStart or 0
    if fin == nil then return false, false end

    local hasta_entrada = ini + entrada_frames
    if entrada_frames > 0 and hasta_entrada >= fin then
        entrada_frames, hasta_entrada = 0, ini
    end
    local desde = math.max(ini, fin - salida_frames)
    if salida_frames > 0 and desde >= fin then salida_frames = 0 end
    -- Clip demasiado corto para las dos: gana la salida (que el texto se
    -- borre limpio importa mas que como aparecio).
    if entrada_frames > 0 and salida_frames > 0 and hasta_entrada >= desde then
        entrada_frames, hasta_entrada = 0, ini
    end
    if entrada_frames < 1 and salida_frames < 1 then return false, false end

    local claves = {}
    if entrada_frames > 0 then
        claves[ini] = { 0.0 }
        claves[hasta_entrada] = { 1.0 }
    end
    if salida_frames > 0 then
        claves[desde] = { 1.0 }
        claves[fin] = { 0.0 }
    end

    -- Cual de las entradas de opacidad existe en ESTE nodo.
    local entrada, original = FADE_ENTRADA, nil
    if entrada ~= nil then
        pcall(function() original = tool:GetInput(entrada) end)
    else
        for _, candidata in ipairs(FADE_ENTRADAS) do
            local valor = nil
            pcall(function() valor = tool:GetInput(candidata) end)
            if valor ~= nil then
                entrada, original = candidata, valor
                break
            end
        end
    end
    if entrada == nil or original == nil then
        -- No es que la llamada falle: es que en este nodo no hay donde
        -- escribir. Distinguirlo importa, porque son arreglos distintos.
        FADE_VIA = false
        FADE_MOTIVO = "este Text+ no tiene ninguna entrada de opacidad ("
            .. table.concat(FADE_ENTRADAS, ", ") .. ")"
        return false, false
    end
    FADE_ENTRADA = entrada

    local function intentar(i)
        pcall(FADE_FORMAS[i].hacer, comp, tool, entrada, claves)
        -- Se comprueba CADA tramo pedido, no uno solo: una via que animara
        -- la salida pero no la entrada mentiria en el resumen.
        local e_ok = entrada_frames < 1
            or _fade_anima(tool, entrada, ini, hasta_entrada)
        local s_ok = salida_frames < 1
            or _fade_anima(tool, entrada, desde, fin)
        if e_ok and s_ok then
            FADE_VIA = i
            FADE_MOTIVO = FADE_FORMAS[i].nombre .. " sobre '" .. entrada .. "'"
            return entrada_frames > 0, salida_frames > 0
        end
        _fade_limpiar(tool, entrada, original)
        return nil
    end

    if FADE_VIA ~= nil then
        local e_ok, s_ok = intentar(FADE_VIA)
        if e_ok == nil then return false, false end
        return e_ok, s_ok
    end
    for i = 1, #FADE_FORMAS do
        local e_ok, s_ok = intentar(i)
        if e_ok ~= nil then return e_ok, s_ok end
    end
    FADE_VIA = false
    FADE_MOTIVO = "esta version de Resolve no acepta fotogramas clave por script"
    return false, false
end

-- (compat) Solo el fundido de salida de siempre. Ver aplicar_fades.
local function aplicar_fade(item, fade_frames)
    local _, s_ok = aplicar_fades(item, 0, fade_frames)
    return s_ok
end

local function limpiar_pista(timeline, tipo, indice)
    if not indice then return 0 end
    local items = timeline:GetItemListInTrack(tipo, indice) or {}
    if #items == 0 then return 0 end
    -- v3.0.2: DeleteClips devuelve false EN SILENCIO (pista bloqueada) y
    -- aqui se contaba «N borrados» sin borrar nada: solo cuenta si dijo
    -- que si; si no, el bucle de abajo mide clip a clip.
    local ok, res = pcall(function() return timeline:DeleteClips(items) end)
    if ok and res then return #items end
    local borrados = 0
    for _, it in ipairs(lista_api(items)) do
        if pcall(function() timeline:DeleteClips({ it }) end) then borrados = borrados + 1 end
    end
    return borrados
end

-- ---------------------------------------------------------------------
-- Anti-destruccion: crear/reusar pistas SIN RIESGO de pisar contenido
-- ajeno (b-roll, musica, etc). Traduccion 1:1 de la misma logica que
-- "CineCaptions.py" (version Studio), agregada despues de
-- que un usuario reporto que el script le reemplazo TODO el b-roll con
-- texto: el indice de una pista "nueva" se calculaba a ojo
-- (cantidad + 1) sin comprobar que AddTrack realmente la hubiera creado.
-- Si AddTrack fallaba en silencio, ese "+1" apuntaba a una pista YA
-- EXISTENTE (tipicamente V1, con el video del usuario) y ahi se
-- escribian encima los ~150 clips de subtitulo a lo largo de todo el
-- timeline.
-- ---------------------------------------------------------------------

-- Un efecto de sonido nuestro nunca dura mas que esto. Un clip mas largo
-- en una pista que reutilizamos por nombre es, con altisima probabilidad,
-- contenido del usuario y no nuestro.
local DURACION_MAXIMA_SFX_SEGUNDOS = 20

local function crear_pista_verificada(timeline, tipo, nombre, args_extra)
    -- Devuelve (indice, error). NUNCA calcula el indice a ojo: confirma en
    -- dos pasos independientes que la pista es de verdad nueva.
    local ok_antes, antes = pcall(function() return timeline:GetTrackCount(tipo) end)
    if not ok_antes then return nil, "no pude leer GetTrackCount('" .. tipo .. "')" end

    local ok_add, resultado_add
    if args_extra then
        ok_add, resultado_add = pcall(function() return timeline:AddTrack(tipo, args_extra) end)
    else
        ok_add, resultado_add = pcall(function() return timeline:AddTrack(tipo) end)
    end

    local ok_despues, despues = pcall(function() return timeline:GetTrackCount(tipo) end)
    if not ok_despues then return nil, "no pude releer GetTrackCount('" .. tipo .. "')" end

    if despues ~= antes + 1 then
        return nil, string.format(
            "AddTrack('%s') no sumo una pista nueva (antes=%s, despues=%s, ok=%s)",
            tipo, tostring(antes), tostring(despues), tostring(ok_add and resultado_add))
    end

    local idx = despues
    local ok_items, items = pcall(function() return timeline:GetItemListInTrack(tipo, idx) end)
    if not ok_items then
        return nil, "no pude comprobar si la pista " .. idx .. " esta vacia"
    end
    -- OJO: aqui habia un next(items) ~= nil, y era un bug.
    --
    -- Las listas de la API traen una clave extra con el conteo, asi que una
    -- pista VACIA llega como {n = 0}. next() encontraba esa clave y el guard
    -- concluia que la pista recien creada ya tenia contenido: abortaba el
    -- idioma entero y no se colocaba NADA (ni subtitulos ni SFX). Solo se
    -- notaba al CREAR pistas; cuando las pistas ES-* ya existian se tomaba
    -- la rama de reutilizar y el fallo quedaba oculto.
    --
    -- lista_api cuenta solo los clips de verdad e ignora esa clave.
    if #lista_api(items) > 0 then
        -- No deberia pasar nunca (la acabamos de crear), pero si pasa es
        -- justo el escenario peligroso: mejor abortar que arriesgar.
        return nil, "la pista " .. tipo .. " " .. idx .. " recien creada ya tiene contenido; no la uso"
    end

    pcall(function() timeline:SetTrackName(tipo, idx, nombre) end)
    return idx, nil
end

local function es_clip_texto_nuestro(item)
    -- True si un item del timeline es un Text+ (lo que nosotros ponemos)
    -- o, desde la v3.3.0, uno de NUESTROS emojis (rcs_emoji_*.png): sin
    -- esto la pista EMOJI contaba como ajena y cada corrida apilaba otra.
    local ok, tool = pcall(get_text_plus, item)
    if ok and tool ~= nil then return true end
    local ok_n, nombre = pcall(function() return item:GetName() end)
    if not (ok_n and type(nombre) == "string") then return false end
    nombre = nombre:lower()
    if nombre:sub(1, 10) == "rcs_emoji_" then return true end
    -- v5.8: tambien las SECUENCIAS animadas (e_[0001-0023].png, en .../emojis_secuencia/<emoji>/): sin esto
    -- al volver a generar la pista de emojis se apilaba otra
    if nombre:sub(1, 3) == "e_[" then
        local ok_r, ruta = pcall(function()
            local mpi = item:GetMediaPoolItem()
            return mpi and mpi:GetClipProperty("File Path") or ""
        end)
        if ok_r and type(ruta) == "string" then
            return ruta:gsub("\\", "/"):lower():find("emojis_secuencia", 1, true) ~= nil
        end
    end
    return false
end

-- v3.0.3: las pistas BLOQUEADAS se RESPETAN (la gemela y el porque
-- completo estan en "CineCaptions.py", _pista_bloqueada):
-- con candado la pista cuenta como ajena — se deja tal cual y se crea
-- otra encima, diciendolo una vez. La v3.0.2 quitaba el candado y lo
-- reponia: retirado por orden del usuario, no lo revivas.
local BLOQUEADAS_AVISADAS = {}

local function pista_bloqueada(timeline, tipo, indice)
    local ok, bloqueada = pcall(function() return timeline:GetIsTrackLocked(tipo, indice) end)
    if not ok or not bloqueada then return false end
    local clave = tostring(tipo) .. ":" .. tostring(indice)
    if not BLOQUEADAS_AVISADAS[clave] then
        BLOQUEADAS_AVISADAS[clave] = true
        print(string.format("  La pista %s %s está bloqueada: no la toco "
            .. "(si tiene subtítulos viejos, seguirán ahí).",
            tostring(tipo), tostring(indice)))
    end
    return true
end

local function pista_video_reutilizable(timeline, indice)
    -- True si una pista de video existente es SOLO nuestra: vacia, o con
    -- puros clips Text+. Si hay aunque sea uno que no es Text+ (video
    -- real, b-roll), la pista no se toca. Con candado (v3.0.3) tampoco.
    if pista_bloqueada(timeline, "video", indice) then return false end
    local ok, items = pcall(function() return timeline:GetItemListInTrack("video", indice) end)
    if not ok then return false end
    for _, it in ipairs(lista_api(items)) do
        if not es_clip_texto_nuestro(it) then return false end
    end
    return true
end

-- Vacia TODAS las pistas de video con esos nombres que sean solo nuestras
-- (v2.0.2, pedido literal: «si pusimos dinamicos, solo dinamicos y
-- viceversa»). Generar en un modo dejaba delante los subtitulos del otro
-- (y place_srt ademas apilaba una pista LANG nueva por corrida): la
-- dinamica retira la pista LANG y la SRT retira LANG-CTX/-MAIN/-CMP y las
-- LANG sobrantes. Una pista con un clip que no es Text+ se deja intacta,
-- como siempre; se dice cuantas y por que.
local function retirar_pistas_nuestras(timeline, nombres, que, motivo)
    local pistas, clips = 0, 0
    for _, nombre in ipairs(nombres) do
        local ok, cantidad = pcall(function() return timeline:GetTrackCount("video") end)
        if not ok or not cantidad then return 0 end
        for t = 1, cantidad do
            local ok_n, actual = pcall(function() return timeline:GetTrackName("video", t) end)
            actual = ok_n and (actual or "") or ""
            actual = actual:gsub("^%s*(.-)%s*$", "%1")
            if string.upper(actual) == string.upper(nombre)
                    and pista_video_reutilizable(timeline, t) then
                local borrados = limpiar_pista(timeline, "video", t)
                if borrados > 0 then
                    pistas = pistas + 1
                    clips = clips + borrados
                end
            end
        end
    end
    if clips > 0 then
        print(string.format("  Retire %d %s anteriores (%d pista(s)): %s.",
                            clips, que, pistas, motivo))
    end
    return clips
end

local function pista_audio_reutilizable(timeline, indice, duracion_maxima_frames)
    -- True si una pista de audio existente es segura de limpiar: vacia, o
    -- con clips cortos (duracion tipica de un efecto de sonido). Si hay
    -- algo mas largo (musica, voz, ambiente), se trata como ajeno. Con
    -- candado (v3.0.3) tampoco se toca.
    if pista_bloqueada(timeline, "audio", indice) then return false end
    local ok, items = pcall(function() return timeline:GetItemListInTrack("audio", indice) end)
    if not ok then return false end
    for _, it in ipairs(lista_api(items)) do
        local ok_dur, dur = pcall(function() return it:GetDuration() end)
        if not ok_dur or dur == nil or dur > duracion_maxima_frames then
            return false
        end
    end
    return true
end

-- Con 'carpeta' se busca SOLO adentro de ese bin. Hace falta para los packs
-- .drt: sus clips quedan en un bin propio, y sin limitar la busqueda a el,
-- cualquier 'contexto' suelto que el usuario tuviera en otro lado del
-- proyecto le ganaria al pack que acaba de elegir, sin una linea que lo
-- explique.
local function find_clip_by_name(media_pool, nombre, carpeta)
    local objetivo = nombre:lower():gsub("^%s*(.-)%s*$", "%1")
    local acotada = carpeta ~= nil
    local function buscar(folder)
        for _, clip in ipairs(lista_api(folder:GetClipList())) do
            local ok, nom = pcall(function() return clip:GetName() end)
            if ok and nom and nom:lower():gsub("^%s*(.-)%s*$", "%1") == objetivo then
                return clip
            end
        end
        for _, sub in ipairs(lista_api(folder:GetSubFolderList())) do
            -- Buscando en TODO el Media Pool, los bins de los packs no
            -- cuentan: son NUESTROS, no plantillas del usuario. Sin esto,
            -- despues de usar un pack .drt una vez su bin se quedaba en el
            -- proyecto y en la siguiente generacion SIN pack la busqueda lo
            -- encontraba: el diseño no llegaba a correr, no se escribia ni
            -- una posicion, y todo caia amontonado. NO se borran -son del
            -- proyecto del usuario-, solo dejan de contar.
            local saltar = false
            if not acotada then
                local ok_n, n = pcall(function() return sub:GetName() end)
                saltar = ok_n and n ~= nil and n:sub(1, #PREFIJO_BIN_PACK) == PREFIJO_BIN_PACK
            end
            if not saltar then
                local encontrado = buscar(sub)
                if encontrado then return encontrado end
            end
        end
        return nil
    end
    local raiz = carpeta
    if raiz == nil then
        local ok
        ok, raiz = pcall(function() return media_pool:GetRootFolder() end)
        if not ok or not raiz then return nil end
    end
    return buscar(raiz)
end

-- Busca "contexto 3" probando las formas de numerar mas comunes.
local function buscar_plantilla_numerada(media_pool, base, numero, carpeta)
    -- El set 1 es el nombre a secas ('arriba'), pero tambien vale con el 1 puesto ('arriba 1', 'arriba1'...)
    if numero == 1 then
        local clip = find_clip_by_name(media_pool, base, carpeta)
        if clip then return clip end
    end
    for _, patron in ipairs(SUFIJOS_DE_SET) do
        local clip = find_clip_by_name(
            media_pool, base .. string.format(patron, numero), carpeta)
        if clip then return clip end
    end
    return nil
end

-- La plantilla de las palabras sueltas: 'simple' (nombre nuevo) o 'base' (el de siempre).
function NOMBRES.buscar_base(media_pool, carpeta)
    for _, nombre in ipairs(NOMBRES.base) do
        local clip = find_clip_by_name(media_pool, nombre, carpeta)
        if clip then return clip end
    end
    return nil
end

-- Busca TODOS los sets numerados que existan, del 1 al MAX_SETS.
--
-- Devuelve (sets, informe). 'sets' es una lista de tablas {rol = clip} y
-- 'informe' son lineas para imprimir, para que se vea exactamente que
-- encontro y que le falto a cada set.
--
-- Un set esta COMPLETO cuando tiene los tres roles. Si hay al menos uno
-- completo se usan SOLO los completos, y los incompletos se omiten con una
-- linea en el registro -"trabaja con los que haya y omite el incompleto"-.
--
-- Hasta la v1.0.29 se devolvia cualquier set con AL MENOS UNA plantilla y
-- los roles que faltaran se tomaban del set 1... y si el set 1 tampoco lo
-- tenia, la linea acababa usando la plantilla de 'principal'. Eso es lo que
-- se veia en Windows Free como "el bloque usa el estilo del principal donde
-- tocaba complemento": con clips sueltos a medio arrastrar en la raiz del
-- Media Pool (10 principales, 6 contextos, 2 complementos) TODOS los
-- complementos caian a la plantilla de principal, sin una sola linea que lo
-- explicara. En Mac no paso porque alli el bin del pack se preparo entero.
--
-- Cuando NINGUN set esta completo se devuelven tal cual, sin rellenar: la
-- colocacion elige por bloque un set que tenga los roles de ESE bloque, y
-- omite el bloque si no hay ninguno. Mezclar roles de sets distintos se veia
-- como "el pack no respeta el diseño" (v1.0.32), y sustituir un rol por
-- 'principal' era el aviso de "falta x texto" en la cara del usuario.
local function buscar_sets_de_plantillas(media_pool, carpeta)
    local crudos = {}
    for numero = 1, MAX_SETS do
        local encontrado, faltan, hay = {}, {}, false
        for _, rol in ipairs(DYNAMIC_ORDER) do
            local nombres_rol = NOMBRES.rol[rol] or { DYNAMIC_TEMPLATES[rol] }
            local clip = nil
            for _, nombre_base in ipairs(nombres_rol) do
                clip = buscar_plantilla_numerada(media_pool, nombre_base, numero, carpeta)
                if clip then break end
            end
            if clip then
                encontrado[rol] = clip
                hay = true
            else
                local nuevo = nombres_rol[1]
                table.insert(faltan, numero > 1 and (nuevo .. " " .. numero) or nuevo)
            end
        end
        if hay then
            table.insert(crudos, { numero = numero, roles = encontrado,
                                   faltan = faltan })
        end
    end

    if #crudos == 0 then return {}, {} end

    local function nombres_de(encontrado)
        local nombres = {}
        for _, rol in ipairs(DYNAMIC_ORDER) do
            local c = encontrado[rol]
            if c then
                local ok, nom = pcall(function() return c:GetName() end)
                table.insert(nombres, ok and tostring(nom) or "?")
            end
        end
        return table.concat(nombres, ", ")
    end

    local sets, informe = {}, {}
    local completos, omitidos = {}, {}
    for _, c in ipairs(crudos) do
        if #c.faltan == 0 then
            table.insert(completos, c)
        else
            table.insert(omitidos, tostring(c.numero))
        end
    end

    if #completos > 0 then
        for i, c in ipairs(completos) do
            -- El numero del BIN viaja con el set (v1.0.61): el indice de
            -- la lista NO es ese numero (los incompletos se descartan) y
            -- el veto de tildes del manifiesto usa numeros de bin.
            c.roles.numero = c.numero
            table.insert(sets, c.roles)
            table.insert(informe, string.format("  Set %d (numero %d): %s",
                                                i, c.numero, nombres_de(c.roles)))
        end
        if #omitidos > 0 then
            -- A registro, no a la cara del usuario: trabajar con los que hay
            -- y callar el incompleto es exactamente lo que se pidio.
            table.insert(informe, string.format(
                "  Omito el/los set(s) %s: no tienen los tres roles. Uso solo "
                .. "los %d completos.", table.concat(omitidos, ", "), #completos))
        end
        return sets, informe
    end

    -- Ningun set completo: se devuelven TAL CUAL, sin rellenar.
    --
    -- Hasta la v1.0.32 aqui se completaba cada set con el rol que faltara,
    -- tomandolo de otro set. Eso mezclaba diseños dentro de un mismo bloque
    -- (contexto de un set, principal de otro) y era el reporte de "no
    -- respeta la posicion, el color ni la tipografia" con un pack propio.
    -- Ahora la colocacion elige, bloque a bloque, un set que tenga TODOS
    -- los roles de ESE bloque, y si no hay ninguno omite el bloque entero.
    for _, c in ipairs(crudos) do
        c.roles.numero = c.numero
        table.insert(sets, c.roles)
        local detalle = string.format("  Set %d (numero %d): %s",
                                      #sets, c.numero, nombres_de(c.roles))
        if #c.faltan > 0 then
            detalle = detalle .. "  [incompleto: le falta "
                      .. table.concat(c.faltan, ", ") .. "]"
        end
        table.insert(informe, detalle)
    end
    table.insert(informe,
        "  Ningun set tiene los tres roles. Uso cada uno solo en los bloques "
        .. "cuyos roles tenga; los que no encajen se omiten (no mezclo "
        .. "estilos de sets distintos).")
    return sets, informe
end

-- ¿El 'Type' de ese clip lo delata como generador/Text+? Segun la version
-- de Resolve dice 'Generator', 'Fusion Title', 'Title'... Se acepta
-- cualquiera que mencione alguna. Vive suelta porque la usan dos caminos:
-- la busqueda de un Text+ cualquiera y el rescate del peldaño 0.
local function es_generador(tipo)
    -- OJO: GetClipProperty('Type') esta LOCALIZADO. En un Resolve en
    -- español dice «Generador»/«Título…» y con solo las palabras inglesas
    -- el lienzo arrastrado era invisible (caso real, 02-09): el cliente
    -- arrastro el Text+ y el script juro que no habia ninguno.
    tipo = tostring(tipo or ""):lower()
    for _, p in ipairs({ "generator", "fusion title", "title", "texto", "text",
                     "generador", "titulo", "título" }) do
        if tipo:find(p, 1, true) then return true end
    end
    return false
end

local function find_any_generator_clip(media_pool)
    -- Busca CUALQUIER Text+/generador ya presente en el Media Pool, sin
    -- depender de un nombre exacto. Es una busqueda de riesgo cero (no
    -- toca el timeline). Respaldo por NOMBRE: un clip llamado «Text+»
    -- (el arrastre de Effects conserva ese nombre) se acepta aunque su
    -- Type venga en un idioma que no conozcamos.
    local function buscar(folder)
        for _, clip in ipairs(lista_api(folder:GetClipList())) do
            local ok, tipo = pcall(function() return clip:GetClipProperty("Type") end)
            if ok and es_generador(tostring(tipo)) then return clip end
            local ok_n, nom = pcall(function() return clip:GetName() end)
            if ok_n and nom then
                local n = tostring(nom):lower()
                if n:find("text+", 1, true) or n:find("texto+", 1, true) then
                    return clip
                end
            end
        end
        for _, sub in ipairs(lista_api(folder:GetSubFolderList())) do
            local encontrado = buscar(sub)
            if encontrado then return encontrado end
        end
        return nil
    end
    local ok, raiz = pcall(function() return media_pool:GetRootFolder() end)
    if not ok or not raiz then return nil end
    return buscar(raiz)
end

local function frame_a_timecode(frame, fps)
    local fps_i = math.floor(fps + 0.5)
    local total = math.max(0, math.floor(frame))
    local h = math.floor(total / (3600 * fps_i))
    local resto = total % (3600 * fps_i)
    local m = math.floor(resto / (60 * fps_i))
    resto = resto % (60 * fps_i)
    local s = math.floor(resto / fps_i)
    local f = resto % fps_i
    return string.format("%02d:%02d:%02d:%02d", h, m, s, f)
end

local function crear_text_plus_en_zona_vacia(timeline, media_pool)
    -- Crea un Text+ SIN arriesgar tocar el contenido del usuario.
    -- InsertFusionTitleIntoTimeline inserta en la pista activa, en el
    -- playhead: si el playhead esta sobre contenido del usuario, hay
    -- riesgo de pisarlo. Aca se mueve el playhead a una zona GARANTIZADO
    -- vacia (varios segundos despues del ultimo clip) antes de insertar,
    -- y se restaura el playhead original al terminar, pase lo que pase.
    -- NO se pregunta antes si el metodo existe. Indexarlo
    -- (timeline.InsertFusionTitleIntoTimeline) NO prueba nada en el binding
    -- Lua de Resolve -era el unico sitio del repo que lo hacia asi- y por
    -- esa guarda el gemelo Free podia estar sin intentarlo siquiera. El
    -- bucle de abajo ya llama bajo pcall y COMPRUEBA el resultado, que es
    -- lo que hace el resto del archivo: si el metodo no esta, el pcall lo
    -- absorbe igual y no se pierde nada.
    local ok_fps, fps = pcall(function() return tonumber(timeline:GetSetting("timelineFrameRate")) end)
    if not ok_fps or not fps then fps = 30.0 end

    local ok_tc0, tc_original = pcall(function() return timeline:GetCurrentTimecode() end)
    if not ok_tc0 then tc_original = nil end

    local ok_fin, fin = pcall(function() return timeline:GetEndFrame() end)
    if not ok_fin then return nil end

    local zona_vacia = math.floor(fin) + math.floor(5 * fps + 0.5)
    local movido = pcall(function()
        timeline:SetCurrentTimecode(frame_a_timecode(zona_vacia, fps))
    end)

    -- Se prueban las dos inserciones que documenta la API. La segunda no
    -- se intentaba nunca.
    local metodos = { "InsertFusionTitleIntoTimeline",
                      "InsertFusionGeneratorIntoTimeline" }
    local mp_item, via = nil, nil
    for _, metodo in ipairs(metodos) do
        for _, nombre in ipairs({ "Text+", "Texto+", "Text" }) do
            local ok, item = pcall(function()
                return timeline[metodo](timeline, nombre)
            end)
            if ok and item then
                pcall(function() mp_item = item:GetMediaPoolItem() end)
                if mp_item then via = metodo .. " + GetMediaPoolItem" end
                if not mp_item then
                    -- Free no promueve con GetMediaPoolItem, pero la
                    -- insercion PUEDE haber dejado el generador en el Media
                    -- Pool. Aqui solo se llega si no habia ninguno
                    -- (obtener_text_plus_base ya busco), asi que cualquier
                    -- generador que aparezca ahora es el que acabamos de
                    -- meter. Es el mismo truco de la foto que salva al .drt.
                    mp_item = find_any_generator_clip(media_pool)
                    if mp_item then via = metodo .. " + lo dejo en el Media Pool" end
                end
                pcall(function() timeline:DeleteClips({ item }) end)
                if not mp_item then
                    -- Ultima oportunidad: algun Resolve lo materializa al
                    -- quitar el clip del timeline.
                    mp_item = find_any_generator_clip(media_pool)
                    if mp_item then via = metodo .. " + aparecio al borrar el clip" end
                end
                if mp_item then break end
            end
        end
        if mp_item then break end
    end

    if movido and tc_original then
        pcall(function() timeline:SetCurrentTimecode(tc_original) end)
    end

    if mp_item then
        print("  Cree un Text+ automaticamente en una zona vacia del timeline "
              .. "(via " .. tostring(via) .. ").")
    else
        print("  No pude crear un Text+: ni InsertFusionTitleIntoTimeline ni "
              .. "InsertFusionGeneratorIntoTimeline dejaron uno en el Media "
              .. "Pool en esta version de Resolve.")
    end
    return mp_item
end

local function obtener_text_plus_base(timeline, media_pool)
    -- Consigue un Text+ para clonar, del menor al mayor riesgo. Nunca
    -- toca el contenido existente del usuario:
    --   1. Plantilla con nombre exacto ('base' o 'Subtitle Template').
    --   2. Cualquier generador/Text+ que ya este en el Media Pool.
    --   3. Crear uno nuevo en una zona vacia del timeline (si la API lo permite).
    local plantilla = find_clip_by_name(media_pool, "Subtitle Template")
        or find_clip_by_name(media_pool, "base")
    if plantilla then return plantilla end

    local encontrado = find_any_generator_clip(media_pool)
    if encontrado then
        local ok, nom = pcall(function() return encontrado:GetName() end)
        print("  Usando el Text+ '" .. tostring(ok and nom or "?")
              .. "' que ya estaba en tu Media Pool.")
        return encontrado
    end

    return crear_text_plus_en_zona_vacia(timeline, media_pool)
end

-- ---------------------------------------------------------------------
-- Packs .drt: importar el timeline y pasar sus clips al Media Pool
-- ---------------------------------------------------------------------
-- Gemela de la de CineCaptions.py: un pack .drt es el timeline
-- exportado tal cual, no un Text+ suelto. La API de Resolve no tiene una
-- llamada oficial para "promover" un clip ya puesto en un timeline a un item
-- del Media Pool CON su estilo, asi que esto prueba mecanismos y VERIFICA
-- cual funciono, en vez de fiarse de uno solo.

-- Gemela de packs_drt.parsear_nombre() (la app) y de la del .py. Los tres
-- tienen que dar lo mismo o el pack se ve distinto segun quien lo lea.
local function parsear_nombre_pack(bruto)
    local n = (bruto or ""):lower():gsub("^%s*(.-)%s*$", "%1")
    n = n:gsub("%.%a+$", "")
    for _, nombre_base in ipairs(NOMBRES.base) do
        if n == nombre_base then return "base", 0 end
    end
    local candidatos = {}
    for _, rol in ipairs(DYNAMIC_ORDER) do
        for _, palabra in ipairs(NOMBRES.rol[rol]) do
            candidatos[#candidatos + 1] = { rol, palabra }
        end
    end
    candidatos[#candidatos + 1] = { "image", NOMBRES.imagen }
    for _, par in ipairs(candidatos) do
        local rol, palabra = par[1], par[2]
        if n == palabra then return rol, 1 end
        local patron = "^" .. palabra:gsub("[%(%)%.%%%+%-%*%?%[%]%^%$]", "%%%1")
            .. "[%s%-_%.]*0*(%d+)$"
        local num = n:match(patron)
        if num then
            local k = tonumber(num)
            local tope = NOMBRES.solo_nuevos[palabra] and NOMBRES.max_variantes or MAX_SETS
            if k and k >= 1 and k <= tope then return rol, k end
            return rol, -1
        end
    end
    return nil, 0
end

local function ruta_capacidades()
    local carpeta, sep = carpeta_compartida()
    return carpeta .. sep .. "capacidades.json"
end

local function leer_capacidades()
    return cargar_tabla(ruta_capacidades()) or {}
end

local function recordar_capacidad(clave, valor)
    local datos = leer_capacidades()
    datos[clave] = valor
    local partes = {}
    for k, v in pairs(datos) do
        partes[#partes + 1] = string.format('"%s":"%s"', json_escapar(k), json_escapar(v))
    end
    escribir_archivo(ruta_capacidades(), "{" .. table.concat(partes, ",") .. "}")
end

local function nombre_bin_pack(nombre_pack, formato)
    -- El prefijo tiene que ser el mismo que salta find_clip_by_name(): de eso
    -- depende que estos bins no se confundan con las plantillas del usuario.
    return PREFIJO_BIN_PACK .. nombre_pack .. " · " .. formato
end

local function subcarpeta(folder, nombre)
    for _, sub in ipairs(lista_api(folder:GetSubFolderList())) do
        local ok, nom = pcall(function() return sub:GetName() end)
        if ok and nom == nombre then return sub end
    end
    return nil
end

-- Le pone ese nombre a un MediaPoolItem. True si lo consiguio: se prueban
-- las dos formas y se COMPRUEBA leyendo el nombre de vuelta, porque las dos
-- devuelven algo verdadero sin haber hecho nada.
local function renombrar_clip(clip, nombre)
    for _, intento in ipairs({ "propiedad", "setname" }) do
        pcall(function()
            if intento == "propiedad" then
                clip:SetClipProperty("Clip Name", nombre)
            else
                clip:SetName(nombre)
            end
        end)
        local ok, nom = pcall(function() return clip:GetName() end)
        if ok and nom and nom:lower():gsub("^%s*(.-)%s*$", "%1")
                == nombre:lower():gsub("^%s*(.-)%s*$", "%1") then
            return true
        end
    end
    return false
end

-- MUEVE un clip del timeline importado al bin del pack, con su nombre.
-- Devuelve true solo si al final EXISTE un clip con ese nombre dentro del
-- bin: la llamada devuelve objetos que parecen validos aunque no hayan
-- dejado nada donde hace falta.
--
-- POR QUE SOLO SE MUEVE, Y NO SE COMPONE: hasta la v1.0.27 se probaba antes
-- Timeline:CreateFusionClip por ser la unica documentada. ENVUELVE el clip
-- -aunque le pases uno solo-, el Text+ deja de estar en el nivel superior
-- del comp, y al generar get_text_plus() devuelve nil: CADA LINEA ENTRA SIN
-- TEXTO. Ver la nota del .py.
local function promover_uno(metodo, media_pool, timeline_importado, item,
                            nombre, carpeta_destino)
    if metodo ~= "media_item" then return false end
    local exito, mpi = pcall(function() return item:GetMediaPoolItem() end)
    if not exito or not mpi then return false end
    -- Traerlo al bin del pack: la busqueda esta limitada a el a proposito.
    local ok_mover = pcall(function()
        return media_pool:MoveClips({ mpi }, carpeta_destino)
    end)
    if not ok_mover then return false end
    renombrar_clip(mpi, nombre)

    return find_clip_by_name(media_pool, nombre, carpeta_destino) ~= nil
end

-- ¿Este clip del Media Pool sirve de plantilla de subtitulo? LA pregunta, y
-- la unica que vale: se coloca de verdad y se mira si trae un TextPlus DE
-- PRIMER NIVEL, que es lo que hara get_text_plus() al generar. Hasta la
-- v1.0.27 se comprobaba por NOMBRE, y por eso un clip precompuesto pasaba el
-- filtro y luego salian las ~200 lineas sin texto.
--
-- Se prueba en el timeline IMPORTADO, que es de usar y tirar, para no dejar
-- ni una pista ni un clip en el montaje del usuario.
--
-- Devuelve true, false, o nil cuando no se pudo comprobar -que no es lo
-- mismo que false-.
local function sirve_para_subtitulos(timeline_desechable, media_pool, clip)
    if not timeline_desechable then return nil end
    local colocado = nil
    local resultado = nil
    pcall(function()
        local indice = timeline_desechable:GetTrackCount("video") or 1
        local nuevos = media_pool:AppendToTimeline({ {
            mediaPoolItem = clip, startFrame = 0, endFrame = 11,
            trackIndex = indice, mediaType = 1,
            recordFrame = timeline_desechable:GetStartFrame() + 1,
        } })
        -- Una tabla vacia es VERDADERA en Lua: hay que mirar nuevos[1].
        if nuevos and nuevos[1] then
            colocado = nuevos[1]
            resultado = get_text_plus(colocado) ~= nil
        end
    end)
    if colocado then
        pcall(function() timeline_desechable:DeleteClips({ colocado }) end)
    end
    return resultado
end

-- MUEVE al bin del pack los clips del timeline importado. Un solo
-- mecanismo: 'media_item' (GetMediaPoolItem + MoveClips), que mueve el clip
-- tal cual sin envolverlo en nada.
--
-- 'fusion_clip' se quito en la v1.0.28 porque PRE COMPONE. Quitarlo de esta
-- lista ademas NEUTRALIZA la cache de quien ya lo tuviera grabado en
-- capacidades.json: el guardia de abajo deja de reconocerlo y lo ignora solo.
--
-- Devuelve (cuantos_entraron, metodo), o (0, nil) si no se pudo.
-- Como se marca el timeline importado que ya cumplio su proposito. Se borra
-- en la corrida siguiente: borrarlo en caliente cerraba Resolve.
local MARCA_TIMELINE_TEMPORAL = "RCS · temporal (se limpia solo)"

-- Borra los timelines temporales de corridas anteriores. Se llama al
-- ARRANCAR, no al terminar: aqui ninguno es el timeline actual del usuario,
-- que es justo lo que hacia peligroso borrarlos antes.
local function limpiar_temporales(project, media_pool)
    local nombre_actual = nil
    pcall(function()
        local actual = project:GetCurrentTimeline()
        if actual then nombre_actual = actual:GetName() end
    end)
    local sobras = {}
    local ok = pcall(function()
        local n = tonumber(project:GetTimelineCount()) or 0
        for i = 1, n do
            local tl = project:GetTimelineByIndex(i)
            if tl then
                local nom = tl:GetName() or ""
                if nom:sub(1, #MARCA_TIMELINE_TEMPORAL) == MARCA_TIMELINE_TEMPORAL
                        and nom ~= nombre_actual then
                    sobras[#sobras + 1] = tl
                end
            end
        end
    end)
    if not ok or #sobras == 0 then return 0 end
    local ok_del = pcall(function() media_pool:DeleteTimelines(sobras) end)
    if not ok_del then return 0 end
    return #sobras
end

-- {clip = true} de esa carpeta, para comparar antes/despues.
local function clips_de_carpeta(folder)
    local mapa = {}
    local ok, lista = pcall(function() return folder:GetClipList() end)
    if not ok then return mapa end
    for _, c in ipairs(lista_api(lista)) do
        local ok_n, nom = pcall(function() return c:GetName() end)
        mapa[(ok_n and nom) and nom or tostring(c)] = true
    end
    return mapa
end

-- Mueve al bin los clips de rol que dejo la IMPORTACION del .drt.
--
-- Esto existe por Free: alli GetMediaPoolItem() no promueve nada, pero
-- Resolve deja los clips del timeline importado sueltos en la raiz igual.
-- La escalera se los perdia y mandaba al usuario al paso manual teniendo
-- los clips delante. Se compara con la foto de ANTES para no tocar un
-- 'principal' que el usuario ya tuviera suelto.
-- 'fotos' es una lista de { carpeta = ..., antes = ... }: se miran varias
-- (la raiz, y la carpeta donde estaba el usuario) porque la importacion
-- suelta los clips en el current folder y no todos los Resolve igual.
-- {nombre = cuantos} de TODO el Media Pool, recursivo. Por nombre, porque
-- cada GetClipList() devuelve envoltorios NUEVOS y comparar objetos no
-- sirve. Se cuenta -no true/false- para detectar un clip repetido que
-- aparece otra vez: con true/false, importar un segundo 'principal' con el
-- pool ya poblado pasaba por "no hay nada nuevo".
local function foto_del_pool(media_pool)
    local mapa = {}
    local ok, raiz = pcall(function() return media_pool:GetRootFolder() end)
    if not ok or not raiz then return mapa end
    local function recorrer(folder)
        local ok_l, lista = pcall(function() return folder:GetClipList() end)
        if ok_l then
            for _, clip in ipairs(lista_api(lista)) do
                local ok_n, nom = pcall(function() return clip:GetName() end)
                local clave = (ok_n and nom) and nom or tostring(clip)
                mapa[clave] = (mapa[clave] or 0) + 1
            end
        end
        local ok_s, subs = pcall(function() return folder:GetSubFolderList() end)
        if ok_s then
            for _, sub in ipairs(lista_api(subs)) do recorrer(sub) end
        end
    end
    pcall(function() recorrer(raiz) end)
    return mapa
end

-- Los clips que aparecieron en el pool desde la foto, MIREN DONDE MIREN.
--
-- Se recorre el pool ENTERO, el bin del pack incluido: la foto tambien lo
-- conto, y las dos mitades tienen que mirar el mismo universo. Excluyendo
-- el bin del recorrido pero no de la foto, un 'contexto' que quedara dentro
-- de una corrida a medias tapaba a un 'contexto' NUEVO de fuera (antes=1,
-- vistos=1, y 1 > 1 es falso). Contar por nombre ya impide re-mover lo que
-- esta dentro: no cuenta como nuevo.
local function nuevos_del_pool(media_pool, antes)
    local vistos, nuevos = {}, {}
    local ok, raiz = pcall(function() return media_pool:GetRootFolder() end)
    if not ok or not raiz then return nuevos end
    local function recorrer(folder)
        local ok_l, lista = pcall(function() return folder:GetClipList() end)
        if ok_l then
            for _, clip in ipairs(lista_api(lista)) do
                local ok_n, nom = pcall(function() return clip:GetName() end)
                if ok_n and nom then
                    vistos[nom] = (vistos[nom] or 0) + 1
                    if vistos[nom] > (antes[nom] or 0) then
                        nuevos[#nuevos + 1] = { clip = clip, nombre = nom }
                    end
                end
            end
        end
        local ok_s, subs = pcall(function() return folder:GetSubFolderList() end)
        if ok_s then
            for _, sub in ipairs(lista_api(subs)) do recorrer(sub) end
        end
    end
    pcall(function() recorrer(raiz) end)
    return nuevos
end

-- 'antes' es la foto del POOL ENTERO de antes de importar, y los clips
-- nuevos se recogen MIREN DONDE MIREN: hasta la v1.0.38 solo se miraba la
-- raiz y la carpeta donde estaba el usuario, asi que un Resolve que deje
-- los clips del .drt en un bin propio los perdia en silencio.
--
-- 'items_por_nombre' (opcional) es el mapa de clips del timeline importado:
-- sirve para el caso en que Resolve materialice los generadores SIN el
-- nombre del rol ('Text+', 'Titulos Dinamicos +'). Entonces se renombran
-- por el orden de las pistas, y SOLO si la cuenta cuadra exactamente.
local function recoger_importados(media_pool, antes, carpeta_destino,
                                  items_por_nombre, orden_importado)
    local aparecidos = nuevos_del_pool(media_pool, antes)
    local nuevos, sin_rol = {}, {}
    for _, n in ipairs(aparecidos) do
        local rol, numero = parsear_nombre_pack(n.nombre)
        if rol ~= nil and numero ~= -1 then
            nuevos[#nuevos + 1] = n.clip
        else
            local ok_t, tipo = pcall(function()
                return n.clip:GetClipProperty("Type")
            end)
            if ok_t and es_generador(tipo) then
                sin_rol[#sin_rol + 1] = n.clip
            end
        end
    end

    -- Ninguno trae nombre de rol, pero aparecieron tantos generadores como
    -- clips tiene el pack: se les pone el nombre que les toca por el orden
    -- del timeline. Con cuentas distintas NO se toca nada — renombrar a ojo
    -- pintaria un rol con el diseño de otro, que es el fallo que ya costo
    -- dos rondas.
    if #nuevos == 0 and #sin_rol > 0 and orden_importado ~= nil
            and #sin_rol == #orden_importado then
        print(string.format("  Peldaño 'importados': apareceieron %d "
            .. "generadores sin nombre de rol; les pongo el del timeline "
            .. "por orden.", #sin_rol))
        for i, clip in ipairs(sin_rol) do
            if renombrar_clip(clip, orden_importado[i]) then
                nuevos[#nuevos + 1] = clip
            end
        end
    end

    if #nuevos == 0 then return 0 end
    local ok_m = pcall(function()
        media_pool:MoveClips(nuevos, carpeta_destino)
    end)
    if not ok_m then return 0 end
    -- Comprobando en el bin, no fiandose de que MoveClips devolviera algo.
    local dentro = clips_de_carpeta(carpeta_destino)
    local entraron = 0
    for _, clip in ipairs(nuevos) do
        local ok_n, nom = pcall(function() return clip:GetName() end)
        if ok_n and nom and dentro[nom] then entraron = entraron + 1 end
    end
    return entraron
end


local function promover_a_media_pool(media_pool, timeline_importado,
                                     items_por_nombre, carpeta_destino)
    local cache = leer_capacidades()
    local orden = { "media_item" }
    local probado = cache.pasar_a_media_pool
    if probado == "media_item" then
        for i, m in ipairs(orden) do
            if m == probado then table.remove(orden, i); break end
        end
        table.insert(orden, 1, probado)
    end

    local total = 0
    for _ in pairs(items_por_nombre) do total = total + 1 end

    for _, metodo in ipairs(orden) do
        -- Se prueba con UNO antes de gastar 30 llamadas en una via que no
        -- funciona en este Resolve.
        local primer_nombre, primer_item = next(items_por_nombre)
        local ok = promover_uno(metodo, media_pool, timeline_importado,
                                primer_item, primer_nombre, carpeta_destino)
        if ok then
            local entraron = 1
            for nombre, item in pairs(items_por_nombre) do
                if nombre ~= primer_nombre then
                    if promover_uno(metodo, media_pool, timeline_importado,
                                    item, nombre, carpeta_destino) then
                        entraron = entraron + 1
                    end
                end
            end

            local sirve = true
            if total > 1 then
                -- Todos apuntando al mismo item = generador compartido.
                local distintos = {}
                for _, c in ipairs(lista_api(carpeta_destino:GetClipList())) do
                    local ok_nom, nom = pcall(function() return c:GetName() end)
                    if ok_nom and nom then distintos[nom] = true end
                end
                local n = 0
                for _ in pairs(distintos) do n = n + 1 end
                sirve = n >= 2
            end
            if sirve then
                recordar_capacidad("pasar_a_media_pool", metodo)
                return entraron, metodo
            end
        end
    end
    if probado ~= nil then
        -- La memoria mintio: el metodo que funciono la ultima vez ya no
        -- funciona (la API del Free es caprichosa entre corridas: el
        -- mismo equipo promovio a las 9:33 y fallo a las 11:15 del mismo
        -- dia). Se olvida para que capacidades.json no documente una
        -- capacidad que hoy no existe.
        recordar_capacidad("pasar_a_media_pool", nil)
        print("  El metodo recordado '" .. tostring(probado)
              .. "' ya no funciona: lo olvido para reprobar en limpio.")
    end
    return 0, nil
end

-- El slug ASCII gemelo del pack (copias identicas en CineCaptions_Exportar_PackDRB
-- y slug_pack del gemelo .py; un test compara las tres). Va en la RUTA del
-- respaldo .drb porque el io.open del Lua en Windows no abre rutas UTF-8
-- (la leccion de la carpeta 'incorporado'): el nombre del pack no puede
-- viajar tal cual. El checksum separa dos packs que solo difieren en
-- acentos (el slug los aplasta igual).
local function slug_pack(nombre)
    nombre = tostring(nombre or "")
    local suma = 0
    for i = 1, #nombre do suma = (suma + nombre:byte(i)) % 100000 end
    local limpio = nombre:lower():gsub("[^a-z0-9]", "_"):sub(1, 40)
    if limpio == "" then limpio = "pack" end
    return limpio .. "-" .. tostring(suma)
end

-- El tamaño del .drt viaja en el NOMBRE del respaldo (mismo patron que
-- plantillas_cache, que se invalida por APP_VERSION+tamaño): sin esto un
-- pack actualizado EN SITIO perdia contra el respaldo rancio para
-- siempre, en silencio (hallazgo de la revision de la v1.0.47).
local function tam_de_archivo(ruta)
    -- Sin io no se mide: la estampa queda en 0 y el candidato con estampa
    -- ni se propone (ver preparar_pack_drt).
    if SIN_IO then return 0 end
    local f = io.open(ruta, "rb")
    if not f then return 0 end
    local tam = f:seek("end") or 0
    f:close()
    return tam
end

local function ruta_respaldo_drb(nombre_pack, formato, ruta_drt)
    local carpeta, sep = carpeta_compartida()
    return carpeta .. sep .. "respaldo_bin_" .. slug_pack(nombre_pack)
        .. "_" .. tostring(formato) .. "_"
        .. tostring(tam_de_archivo(ruta_drt)) .. ".drb"
end

-- Tabla de plegado de tildes: las MISMAS secuencias UTF-8 (dos bytes cada
-- una) que pliega el gemelo .py. Si cambia alla, cambia aca: un test
-- compara las copias con lupa.
local PLEGADO = {
    { "\195\161", "a" }, { "\195\169", "e" }, { "\195\173", "i" },
    { "\195\179", "o" }, { "\195\186", "u" }, { "\195\177", "n" },
    { "\195\188", "u" }, { "\195\129", "a" }, { "\195\137", "e" },
    { "\195\141", "i" }, { "\195\147", "o" }, { "\195\154", "u" },
    { "\195\145", "n" }, { "\195\156", "u" },
}

local NOMBRE_FORMATO = { h = "horizontal", v = "vertical", c = "cuadrado" }

-- 'Base títulos dinámicos' -> 'base-titulos-dinamicos' (v1.0.55). el usuario
-- tecleo el slug con checksum en el dialogo de exportar de Resolve y
-- pidio nombres simples: las tildes se PLIEGAN (á->a) en vez de
-- aplastarse a '_' y no hay checksum — dos packs que solo difieran en
-- tildes colisionan, compromiso aceptado a cambio de un nombre que una
-- persona puede escribir. Sigue siendo ASCII puro (io.open en Windows no
-- abre rutas UTF-8) y el nombre viejo con checksum se sigue leyendo como
-- fuente 4. Copias identicas en el gemelo .py y en CineCaptions_Exportar_PackDRB.
local function nombre_legible(nombre)
    nombre = tostring(nombre or "")
    for _, par in ipairs(PLEGADO) do
        nombre = nombre:gsub(par[1], par[2])
    end
    local limpio = nombre:lower():gsub("[^a-z0-9]", "-")
        :gsub("%-+", "-"):gsub("^%-+", ""):gsub("%-+$", "")
    limpio = limpio:sub(1, 40):gsub("%-+$", "")
    if limpio == "" then limpio = "pack" end
    return limpio
end

-- El nombre que se le pide TECLEAR al usuario en la GUI: legible, sin
-- checksum y con el formato en palabra completa.
local function ruta_respaldo_manual(nombre_pack, formato)
    local carpeta, sep = carpeta_compartida()
    local palabra = NOMBRE_FORMATO[formato] or tostring(formato)
    return carpeta .. sep .. "respaldo_" .. nombre_legible(nombre_pack)
        .. "_" .. palabra .. ".drb"
end

-- Al menos un set con LOS TRES roles: un respaldo (o un .drb importado)
-- con sets incompletos se clavaria a nivel maquina y bloquearia a la
-- escalera de completarlo — peor que no tener respaldo.
local function hay_set_completo(sets)
    for _, s in ipairs(sets or {}) do
        if s.context and s.main and s.complement then return true end
    end
    return false
end

-- Exporta el bin SANO a un .drb en la carpeta compartida (v1.0.47). Con
-- ese archivo, el peldaño 'drb' de las corridas siguientes importa el bin
-- ENTERO directo al Media Pool -posicion y animacion incluidas- sin
-- promover nada: el arrastre manual pasa de "una vez por proyecto" a "una
-- vez por maquina y formato". Idempotente (si el respaldo existe, nada) y
-- JAMAS tumba la generacion (pcall alrededor de todo). Se verifica que el
-- archivo quedo escrito con tamaño > 0: que la llamada no reviente no
-- prueba nada (la leccion del fundido).
local function respaldar_bin_drb(media_pool, carpeta_bin, nombre_pack,
                                 formato, ruta_drt)
    -- Sin .drt no se respalda (v1.0.57): la estampa de frescura usa su
    -- tamaño (io.open(nil) ademas reventaria), y un pack solo-bin ya
    -- viaja con su .drb en el manifiesto — el respaldo seria redundante.
    if not ruta_drt then return end
    -- Sin io (Free 21.1) el respaldo no se puede medir ni verificar:
    -- tam_de_archivo da 0 siempre, asi que se re-exportaba el bin en CADA
    -- corrida y se imprimia un falso «tu Resolve no exporta bandejas»
    -- (v3.3.0). En 21.1 ese respaldo ni se lee (el candidato con estampa no
    -- se propone): no hay nada que ganar.
    if SIN_IO then return end
    pcall(function()
        local destino = ruta_respaldo_drb(nombre_pack, formato, ruta_drt)
        local tam_de = tam_de_archivo
        if tam_de(destino) > 0 then return end
        -- Solo un bin con al menos un set COMPLETO merece respaldo: uno a
        -- medias se clavaria a nivel maquina (hallazgo de la revision).
        if not hay_set_completo(
                buscar_sets_de_plantillas(media_pool, carpeta_bin)) then
            return
        end
        -- Las DOS firmas conocidas, como CineCaptions_Exportar_PackDRB.
        pcall(function() media_pool:ExportFolder(carpeta_bin, destino) end)
        if tam_de(destino) == 0 then
            pcall(function() carpeta_bin:Export(destino) end)
        end
        if tam_de(destino) > 0 then
            print("  Respalde el bin del pack en un .drb: las proximas "
                .. "corridas lo importan solas, aunque el bin se vacie "
                .. "(Ctrl+Z) o cambies de proyecto.")
        else
            -- Un cadaver de 0 bytes bloquearia el reintento y el peldaño
            -- drb: fuera.
            pcall(function() os.remove(destino) end)
            -- La sonda del 03-09 (Resolve 21.0.4.5, Studio Y Free) midio
            -- que ExportFolder ya NI EXISTE en la API. La salida real es
            -- la GUI, con el NOMBRE EXACTO: el legible de la fuente 3
            -- (v1.0.55) — el usuario valido este flujo en su Mac ese mismo
            -- dia y pidio un nombre que se pueda teclear.
            local ruta_manual = ruta_respaldo_manual(nombre_pack, formato)
            print("  Tu Resolve no exporta bandejas por script. Para dejar "
                .. "el automatico permanente hazlo tu UNA vez: clic "
                .. "derecho sobre el bin «RCS · " .. tostring(nombre_pack)
                .. " · " .. tostring(formato) .. "» en el Media Pool -> "
                .. "Exportar bandeja... -> guarda EXACTO como:")
            print("    " .. ruta_manual)
            print("  Desde ahi, cada corrida (y cada proyecto nuevo) lo "
                .. "importa sola.")
        end
    end)
end

-- Importa un .drt y deja sus clips listos en un bin del Media Pool.
-- Devuelve (carpeta_bin, aviso). 'carpeta_bin' es nil si no se pudo, y en
-- ese caso el aviso dice exactamente que hacer a mano.
local function preparar_pack_drt(project, media_pool, nombre_pack, formato, ruta_drt, ruta_drb)
    local nombre_bin = nombre_bin_pack(nombre_pack, formato)
    local raiz_ok, raiz = pcall(function() return media_pool:GetRootFolder() end)
    if not raiz_ok or not raiz then
        return nil, "no pude leer el Media Pool."
    end
    local existente = subcarpeta(raiz, nombre_bin)
    if existente then
        -- Se pregunta LO MISMO que preguntara la generacion, no una
        -- heuristica de "parece que hay clips": si el bin de una corrida
        -- anterior quedo a medias, hay que rehacerlo, no darlo por bueno.
        local ya_listos = buscar_sets_de_plantillas(media_pool, existente)
        if #ya_listos > 0 then
            -- El bin quedo sano (arrastre del usuario o corrida previa):
            -- momento perfecto para dejar el respaldo.
            respaldar_bin_drb(media_pool, existente, nombre_pack, formato,
                              ruta_drt)
            return existente, nil
        end
    end

    -- Un pack SOLO-bin llega con ruta_drt nil (v1.0.57): valido — el
    -- peldaño drb de abajo hace todo el trabajo. Lo que sigue siendo
    -- error es apuntar a un .drt que no existe, o no traer nada de nada.
    if ruta_drt and not archivo_existe(ruta_drt) then
        return nil, "el pack '" .. nombre_pack .. "' apunta a '"
            .. tostring(ruta_drt) .. "', que no encuentro en este equipo."
    end
    if not ruta_drt and not (ruta_drb and archivo_existe(ruta_drb)) then
        return nil, "el pack '" .. nombre_pack .. "' no trae ni timeline "
            .. "ni bin que yo encuentre en este equipo."
    end

    -- Peldaño 'drb': el bin exportado, si el pack lo trae. Lo importa
    -- DIRECTO al Media Pool (ImportFolderFromFile), sin depender de que
    -- Resolve promueva nada — es el "arrastrar a mano" hecho por API, y
    -- funciona igual en Free y en Studio. Importa con el bin del pack como
    -- current (el current manda donde cae) y se verifica con la MISMA
    -- pregunta que hara la generacion. Sin archivo o sin la llamada, la
    -- escalera de siempre sigue intacta.
    -- El peldaño drb bebe de CUATRO fuentes identificadas, la primera que
    -- exista: la del manifiesto (el .drb embebido junto al .drt — desde la
    -- v1.0.55 el pack incorporado lo trae), el respaldo automatico con
    -- estampa, el respaldo manual LEGIBLE (v1.0.55: el nombre que imprimen
    -- los carteles y escribe la herramienta), y el nombre viejo con slug y
    -- checksum — que se SIGUE leyendo: es el archivo que el usuario ya fabrico
    -- en su Mac, y un nombre nuevo degrada a «funciona como antes», nunca
    -- rompe lo que funcionaba. El pack_<f>.drb generico de la herramienta
    -- NO se lee aqui: no lleva identidad de pack y podria pintar el diseño
    -- de OTRO pack sin aviso. Los sin-estampa se aceptan sin frescura:
    -- exportar a mano o correr la herramienta es un acto deliberado.
    local fuente_drb = "el manifiesto"
    if not (ruta_drb and archivo_existe(ruta_drb)) then
        ruta_drb = nil
        local carpeta_c, sep_c = carpeta_compartida()
        local candidatas = {}
        -- Sin io (Free 21.1) archivo_existe da por existente lo que sea y
        -- tam_de_archivo vale 0: el candidato "_0.drb" ganaria siempre y
        -- taparia a los otros. No se propone. (El pack incorporado y todo
        -- .drb traen ruta_drb en el manifiesto: aqui no se entra.)
        if ruta_drt and not SIN_IO then
            -- La estampa lleva el tamaño del .drt: sin .drt no existe.
            candidatas[#candidatas + 1] =
                { ruta_respaldo_drb(nombre_pack, formato, ruta_drt),
                  "el respaldo de esta maquina" }
        end
        candidatas[#candidatas + 1] =
            { ruta_respaldo_manual(nombre_pack, formato),
              "el respaldo manual" }
        candidatas[#candidatas + 1] =
            { carpeta_c .. sep_c .. "respaldo_bin_"
                  .. slug_pack(nombre_pack) .. "_" .. tostring(formato)
                  .. ".drb",
              "el respaldo con el nombre antiguo" }
        for _, par in ipairs(candidatas) do
            if archivo_existe(par[1]) then
                ruta_drb = par[1]
                fuente_drb = par[2]
                break
            end
        end
    end
    if ruta_drb and archivo_existe(ruta_drb) then
        local carpeta_bin = existente
        if not carpeta_bin then
            local ok_c
            ok_c, carpeta_bin = pcall(function()
                return media_pool:AddSubFolder(raiz, nombre_bin)
            end)
            if not ok_c then carpeta_bin = nil end
            -- El peldaño CREO el bin: recordarlo. Sin esto, un drb que
            -- falla al importar dejaba 'existente' en nil y la escalera
            -- de abajo llamaba AddSubFolder OTRA VEZ — dos bins
            -- «RCS · <pack> · <f>» duplicados en el proyecto. Camino
            -- inalcanzable hasta la v1.0.55 (el manifiesto nunca traia
            -- drb); lo cazo test_v1039 al embeber los .drb de verdad.
            if carpeta_bin then existente = carpeta_bin end
        end
        if carpeta_bin then
            local previa_drb = nil
            pcall(function() previa_drb = media_pool:GetCurrentFolder() end)
            pcall(function() media_pool:SetCurrentFolder(carpeta_bin) end)
            local ok_f, importo = pcall(function()
                return media_pool:ImportFolderFromFile(ruta_drb)
            end)
            pcall(function()
                if previa_drb then media_pool:SetCurrentFolder(previa_drb) end
            end)
            if ok_f and importo then
                local sets_drb = buscar_sets_de_plantillas(media_pool, carpeta_bin)
                if hay_set_completo(sets_drb) then
                    print(string.format("  Peldaño 'drb': el bin del pack "
                        .. "entro DIRECTO al Media Pool (%d sets, desde "
                        .. "%s), sin promover nada.", #sets_drb, fuente_drb))
                    respaldar_bin_drb(media_pool, carpeta_bin, nombre_pack,
                                      formato, ruta_drt)
                    return carpeta_bin, nil
                end
                local sigo = ruta_drt and "; sigo con el .drt." or "."
                print("  Peldaño 'drb': importo pero no encontre sets "
                      .. "adentro" .. sigo)
            else
                local sigo = ruta_drt and "; sigo con el .drt." or "."
                print("  Peldaño 'drb': no funciono en este Resolve" .. sigo)
            end
        end
    end

    if not ruta_drt then
        -- Pack SOLO-bin (v1.0.57): sin .drt no hay escalera ni paso
        -- manual posible (no existe timeline que arrastrar). Si el bin no
        -- entro, la verdad y a seguir: generacion sin pack, nunca cero
        -- lineas ni un cartel pidiendo un arrastre imposible.
        return nil, "no pude meter el bin del pack '" .. nombre_pack
            .. "' en el Media Pool y este pack no trae timeline de "
            .. "respaldo. Genero sin el, con lo que haya."
    end

    local timeline_previo = project:GetCurrentTimeline()
    -- Un manual viejo de ESTE pack+formato (de un gate fallido anterior)
    -- se marca como temporal ANTES de importar el nuevo: cada corrida
    -- fallida acumulaba otra pestaña «(arrastrar a mano)» en el proyecto.
    -- Renombrar, no borrar (DeleteTimelines en caliente cerro Resolve una
    -- vez): la limpieza de la corrida siguiente se lo lleva cuando no es
    -- el current de nadie. Y si es el timeline ACTUAL, se deja en paz.
    pcall(function()
        local objetivo = "RCS · " .. nombre_pack .. " · " .. formato
            .. " (arrastrar a mano)"
        local actual = nil
        pcall(function() actual = project:GetCurrentTimeline():GetName() end)
        for i = 1, (project:GetTimelineCount() or 0) do
            local tl = project:GetTimelineByIndex(i)
            local ok_n, nom = pcall(function() return tl:GetName() end)
            if ok_n and nom == objetivo and nom ~= actual then
                pcall(function() tl:SetName(MARCA_TIMELINE_TEMPORAL) end)
            end
        end
    end)

    -- El bin donde el usuario estaba parado. HAY QUE RESTAURARLO: mas abajo
    -- se hace SetCurrentFolder(carpeta_bin) y, sin devolverlo, la siguiente
    -- ImportMedia (los efectos de sonido) aterriza dentro del bin del pack.
    -- Ahi los pillaba el vaciado de "el bin quedo a medias" y los borraba:
    -- ese era el reporte de "importa los SFX y despues se ponen en rojo".
    local carpeta_previa = nil
    pcall(function() carpeta_previa = media_pool:GetCurrentFolder() end)
    -- La importacion deja los clips sueltos en el CURRENT FOLDER, y la
    -- foto con la que se detectan se tomaba de la raiz: con el current
    -- apuntando a otro bin (el del pack de la corrida anterior, una bandeja
    -- del usuario), la foto no veia los clips nuevos y el peldaño 0
    -- fallaba en silencio. Se fija la RAIZ como current antes de importar
    -- -asi caen siempre en el mismo sitio- y ademas se fotografia TAMBIEN
    -- la carpeta donde estaba el usuario, por si su Resolve los deja alli.
    pcall(function() media_pool:SetCurrentFolder(media_pool:GetRootFolder()) end)
    -- Foto del POOL ENTERO (recursiva). Mirar solo la raiz y la carpeta del
    -- usuario perdia los clips cuando Resolve los dejaba en un bin propio.
    local antes_pool = foto_del_pool(media_pool)
    -- Con opciones explicitas primero (importSourceClips ya es el defecto
    -- documentado, pero pasarlo elimina la duda para siempre); si esa firma
    -- no existe en algun Resolve viejo, se reintenta a secas.
    local ok_imp, importado = pcall(function()
        return media_pool:ImportTimelineFromFile(ruta_drt,
            { importSourceClips = true })
    end)
    if not ok_imp or not importado then
        ok_imp, importado = pcall(function()
            return media_pool:ImportTimelineFromFile(ruta_drt)
        end)
    end
    if not ok_imp or not importado then
        -- Ya se fijo la raiz como current para importar: restaurar el bin
        -- del usuario tambien en este retorno temprano, que ocurre ANTES de
        -- la restauracion del final. Sin esto, los ImportMedia siguientes
        -- (los SFX) aterrizaban en la raiz.
        pcall(function()
            if carpeta_previa then media_pool:SetCurrentFolder(carpeta_previa) end
        end)
        return nil, "no pude importar el pack '" .. nombre_pack .. "' ("
            .. ruta_drt:match("[^\\/]+$") .. ")."
    end

    local resultado_carpeta, resultado_aviso = nil, nil
    local borrar_importado = false
    do
        pcall(function() project:SetCurrentTimeline(importado) end)

        local items_por_nombre = {}
        local orden_importado = {}
        local ok_n, n_pistas = pcall(function()
            return importado:GetTrackCount("video")
        end)
        n_pistas = ok_n and n_pistas or 0
        for pista = 1, n_pistas do
            local ok_l, lista = pcall(function()
                return importado:GetItemListInTrack("video", pista)
            end)
            if ok_l then
                for indice, item in ipairs(lista_api(lista)) do
                    local ok_nom, nombre = pcall(function() return item:GetName() end)
                    if ok_nom and nombre then
                        local rol, n = parsear_nombre_pack(nombre)
                        if rol ~= nil and n ~= -1 and not items_por_nombre[nombre] then
                            items_por_nombre[nombre] = item
                            orden_importado[#orden_importado + 1] = {
                                nombre = nombre, pista = pista, indice = indice }
                        end
                    end
                end
            end
        end

        local cuantos = 0
        for _ in pairs(items_por_nombre) do cuantos = cuantos + 1 end
        -- Los nombres EN EL ORDEN en que estan en el timeline: es lo unico
        -- que permite repartir roles si Resolve materializa los clips sin
        -- su nombre. Se arma aqui, donde todavia se tiene el timeline.
        table.sort(orden_importado, function(a, b)
            if a.pista ~= b.pista then return a.pista < b.pista end
            return a.indice < b.indice
        end)
        local nombres_en_orden = {}
        for i, e in ipairs(orden_importado) do nombres_en_orden[i] = e.nombre end
        orden_importado = nombres_en_orden
        if cuantos == 0 then
            -- No hay nada que rescatar a mano tampoco: se borra igual.
            borrar_importado = true
            resultado_aviso = "el pack '" .. nombre_pack .. "' no trae ningun "
                .. "clip llamado 'contexto', 'principal' o 'complemento' en "
                .. "ese timeline."
        else
            local carpeta_bin = existente
            if not carpeta_bin then
                local ok_c
                ok_c, carpeta_bin = pcall(function()
                    return media_pool:AddSubFolder(raiz, nombre_bin)
                end)
                if not ok_c then carpeta_bin = nil end
            end
            if not carpeta_bin then
                resultado_aviso = "no pude crear el bin '" .. nombre_bin
                    .. "' en el Media Pool."
            else
                pcall(function() media_pool:SetCurrentFolder(carpeta_bin) end)

                -- Foto del bin ANTES de meterle nada: si el gate rechaza
                -- esta corrida, SOLO se borra lo que esta corrida metio.
                local bin_antes = clips_de_carpeta(carpeta_bin)

                -- Peldaño 0: lo que la importacion ya dejo suelto (raiz, y
                -- la carpeta del usuario por si acaso). Es gratis y es el
                -- unico que funciona en Free, donde GetMediaPoolItem no
                -- promueve nada.
                local entraron = recoger_importados(
                    media_pool, antes_pool, carpeta_bin, items_por_nombre,
                    orden_importado)
                local metodo = (entraron > 0) and "importados" or nil
                if entraron > 0 then
                    print(string.format("  Pack '%s': recogi %d clips que "
                        .. "dejo la importacion y los movi al bin.",
                        nombre_pack, entraron))
                else
                    print("  Peldaño 'importados': la importacion no dejo "
                          .. "clips sueltos nuevos; pruebo GetMediaPoolItem.")
                    entraron, metodo = promover_a_media_pool(
                        media_pool, importado, items_por_nombre, carpeta_bin)
                    if metodo then
                        print(string.format(
                            "  Peldaño 'media_item': movio %d clips.", entraron))
                    else
                        print("  Peldaño 'media_item': no funciono en este "
                              .. "Resolve.")
                    end
                end

                -- La prueba que de verdad importa: ¿el bin sirve para
                -- generar? No basta con que las llamadas no fallaran. Se
                -- pregunta LO MISMO que preguntara la generacion un momento
                -- despues; si eso no encuentra sets, el pack no se aplicaria
                -- y mas vale decirlo ahora que dejar salir un render con el
                -- diseño equivocado.
                -- ¿Hay sets, por nombre? Necesario, pero NO suficiente.
                local sets_utiles = buscar_sets_de_plantillas(media_pool, carpeta_bin)

                -- Y la que de verdad decide: ¿uno de esos clips trae un
                -- TextPlus de primer nivel? Es lo que preguntara la
                -- generacion, y la que faltaba en la v1.0.27 -por eso los
                -- clips precompuestos pasaban el filtro de nombres y luego
                -- salian las ~200 lineas SIN TEXTO-.
                local estructura = nil
                if #sets_utiles > 0 then
                    -- OJO: el set lleva tambien la clave 'numero' (un
                    -- ENTERO, v1.0.62) y el orden de pairs es aleatorio:
                    -- sin el filtro, la sonda recibia un numero como
                    -- clip y la estructura salia nil AL AZAR (cazado por
                    -- test_v1034 fallando una corrida si y otra no).
                    local muestra = nil
                    for rol, c in pairs(sets_utiles[1]) do
                        if rol ~= "numero" then muestra = c; break end
                    end
                    if muestra then
                        estructura = sirve_para_subtitulos(importado, media_pool, muestra)
                    end
                    if estructura == false then
                        print("  Aviso: los clips de '" .. nombre_pack .. "' "
                              .. "llegaron al Media Pool, pero no traen un "
                              .. "Text+ utilizable (¿vienen precompuestos?). "
                              .. "No los uso: saldrian sin texto.")
                    elseif estructura == nil then
                        print("  Nota: no pude comprobar la estructura de los "
                              .. "clips de '" .. nombre_pack .. "'. Sigo, pero "
                              .. "si salen sin texto es por aqui.")
                    end
                end

                -- Hacen falta LAS TRES: que la via ganara, que haya sets, y
                -- que la estructura no sea explicitamente mala. Con menos no
                -- alcanza: cuando GetMediaPoolItem devuelve el generador
                -- COMPARTIDO, la via se rechaza -bien- pero ese clip ya se
                -- movio al bin y quedo renombrado a 'contexto', asi que la
                -- busqueda encontraba 1 set y daba el bin por bueno. Los tres
                -- roles habrian salido IGUALES.
                local rescatado = false
                if metodo == nil or #sets_utiles == 0 or estructura == false then
                    print(string.format("  Gate del pack: NO paso (via=%s, "
                        .. "sets=%d, estructura=%s).", tostring(metodo),
                        #sets_utiles, tostring(estructura)))
                    -- Y decir QUE hay en el bin: «sets=0» no distingue
                    -- «se vacio» de «hay clips pero no parsean», y son
                    -- arreglos distintos. El caso real (01-09): el bin
                    -- QUEDO VACIO entre dos corridas del mismo proyecto —
                    -- Ctrl+Z despues de generar deshace tambien el
                    -- ARRASTRE del usuario (misma pila de deshacer).
                    if #sets_utiles == 0 then
                        pcall(function()
                            local nombres_bin = {}
                            for _, clip in ipairs(lista_api(carpeta_bin:GetClipList())) do
                                local ok_n, nom = pcall(function() return clip:GetName() end)
                                if ok_n and nom then
                                    nombres_bin[#nombres_bin + 1] = nom
                                end
                            end
                            if #nombres_bin == 0 then
                                print("  El bin del pack esta VACIO. Si ya "
                                    .. "habias arrastrado los clips, ojo: "
                                    .. "Ctrl+Z despues de generar tambien "
                                    .. "deshace TU arrastre. Vuelve a "
                                    .. "arrastrarlos (incluido 'base').")
                            else
                                local muestra = {}
                                for i = 1, math.min(5, #nombres_bin) do
                                    muestra[#muestra + 1] = nombres_bin[i]
                                end
                                print(string.format("  El bin tiene %d clips "
                                    .. "pero ninguno forma un set completo. "
                                    .. "Primeros: %s", #nombres_bin,
                                    table.concat(muestra, ", ")))
                            end
                        end)
                    end
                    -- Se limpia SOLO lo que esta corrida metio al bin. Los
                    -- clips de corridas anteriores se quedan: una corrida
                    -- mala degrada a "como la corrida pasada", nunca a "sin
                    -- plantillas" — hasta la v1.0.33 aqui se vaciaba el bin
                    -- entero y un gate fallido dejaba el proyecto sin
                    -- plantillas de un plumazo ("solo importa el sfx").
                    --
                    -- Y de lo nuevo, SOLO clips con nombre de rol: un .wav
                    -- de efectos que acabara aqui no se toca (la regla de
                    -- nunca destruir el trabajo del usuario).
                    pcall(function()
                        local sobras = {}
                        for _, clip in ipairs(lista_api(carpeta_bin:GetClipList())) do
                            local ok_n, nom = pcall(function() return clip:GetName() end)
                            if ok_n and nom and not bin_antes[nom] then
                                local rol = parsear_nombre_pack(nom)
                                if rol ~= nil then sobras[#sobras + 1] = clip end
                            end
                        end
                        if #sobras > 0 then
                            media_pool:DeleteClips(sobras)
                            print(string.format("  Limpie %d clips que esta "
                                .. "corrida metio al bin; los de corridas "
                                .. "anteriores quedan.", #sobras))
                        end
                    end)
                    -- Si el bin conserva sets de una corrida anterior, se
                    -- usan: es lo que la generacion habria hecho la semana
                    -- pasada, y mejor eso que el paso manual con bin sano.
                    local previos = buscar_sets_de_plantillas(media_pool, carpeta_bin)
                    if #previos > 0 then
                        print(string.format("  El bin conserva %d sets de una "
                            .. "corrida anterior: genero con esos.", #previos))
                        resultado_carpeta = carpeta_bin
                        borrar_importado = true
                        rescatado = true
                    end
                end
                if rescatado then
                    -- nada mas que hacer: el bin previo manda
                elseif metodo == nil or #sets_utiles == 0 or estructura == false then
                    -- Ultimo peldaño: se deja el timeline importado, con
                    -- nombre claro, y se dice el paso manual exacto.
                    pcall(function()
                        importado:SetName("RCS · " .. nombre_pack .. " · "
                            .. formato .. " (arrastrar a mano)")
                    end)
                    local ok_nom, nom = pcall(function() return importado:GetName() end)
                    resultado_aviso = "tu version de Resolve no me deja pasar "
                        .. "los clips de '" .. nombre_pack .. "' al Media Pool "
                        .. "automaticamente. Deje el timeline «"
                        .. (ok_nom and nom or nombre_bin) .. "» en tu proyecto: "
                        .. "selecciona TODOS sus clips de texto "
                        .. "(contexto/principal/complemento y el clip "
                        .. "'base') y arrastralos al "
                        .. "Media Pool, al bin «" .. nombre_bin
                        .. "», y vuelve a generar."
                else
                    if entraron < cuantos then
                        -- Entro parte: se sigue -es utilizable- pero se dice
                        -- cuanto falta. Un pack a medias no puede parecer
                        -- completo.
                        print(string.format("  Aviso: del pack '%s' pasaron %d "
                            .. "de %d clips al Media Pool. Un bloque cuyo "
                            .. "set no llego entero se omite (no se "
                            .. "sustituye).", nombre_pack, entraron, cuantos))
                    end
                    print(string.format("  Pack '%s': %d sets listos en el bin "
                        .. "«%s» (via %s).", nombre_pack, #sets_utiles,
                        nombre_bin, tostring(metodo)))
                    resultado_carpeta = carpeta_bin
                    borrar_importado = true
                end
            end
        end
    end

    -- El timeline importado se borra SIEMPRE que se pudo promover -ya
    -- cumplio su unico proposito-. Si NO se pudo (ultimo peldaño), se deja
    -- a proposito: es el que el usuario tiene que usar a mano.
    pcall(function()
        if timeline_previo then project:SetCurrentTimeline(timeline_previo) end
    end)
    pcall(function()
        if carpeta_previa then media_pool:SetCurrentFolder(carpeta_previa) end
    end)
    if borrar_importado then
        -- NO se borra en caliente: DeleteTimelines sobre un timeline recien
        -- des-seleccionado cerraba Resolve entero (reportado en Studio,
        -- v1.0.32). Se marca y se limpia al principio de la corrida
        -- siguiente, cuando ya no es el current de nadie.
        pcall(function() importado:SetName(MARCA_TIMELINE_TEMPORAL) end)
    end
    if resultado_carpeta ~= nil then
        -- El prep termino con un bin sano (promocion o rescate): respaldo.
        respaldar_bin_drb(media_pool, resultado_carpeta, nombre_pack,
                          formato, ruta_drt)
    end
    return resultado_carpeta, resultado_aviso
end

-- ---------------------------------------------------------------------
-- Colocar una pista dinamica (3 lineas)
-- ---------------------------------------------------------------------
-- Los 14 caracteres que una caligrafica puede no traer (Tempting.otf no
-- mapea ninguno). Copia gemela de ACENTOS/tiene_acentos del .py de
-- Studio: secuencias UTF-8 literales, un test las compara byte a byte.
local ACENTOS = { "á", "é", "í", "ó", "ú", "Á", "É", "Í", "Ó", "Ú",
                  "ñ", "Ñ", "ü", "Ü" }

local function tiene_acentos(texto)
    if type(texto) ~= "string" or texto == "" then return false end
    for _, a in ipairs(ACENTOS) do
        if string.find(texto, a, 1, true) then return true end
    end
    return false
end

-- El set que sirve para un bloque con esos roles, o nil. Se prueba primero
-- el que tocaba por rotacion. NUNCA se mezclan dos sets en un mismo bloque:
-- el diseño sale entero de un set o el bloque no se coloca.
-- 'vetado' (v1.0.61, pedido literal: «si la palabra tiene tilde no uses
-- la combinacion de la tipografia Tempting») es {rol = {numeros de bin}}
-- SOLO con los roles cuyo texto de ESTE bloque lleva tilde: un set cuyo
-- numero este ahi no sirve. Un set sin numero no se veta nunca.
local function set_para(sets, preferido, roles, vetado)
    if #sets == 0 then return nil end
    -- El respaldo sigue LA RUEDA desde el set que tocaba (v2.0.2, reporte
    -- literal: «no esta mezclado bien las combinaciones»): hasta la
    -- v2.0.1 recorria los sets en orden ascendente desde el 1, asi que
    -- cada bloque cuyo set programado no servia (veto de tildes, roles
    -- que faltan) caia al set 1, uno tras otro.
    local orden = {}
    for k = 0, #sets - 1 do
        orden[#orden + 1] = ((preferido - 1 + k) % #sets) + 1
    end
    for _, i in ipairs(orden) do
        local sirve = true
        for rol in pairs(roles) do
            if not sets[i][rol] then sirve = false; break end
        end
        if sirve and vetado and sets[i].numero then
            for rol, numeros in pairs(vetado) do
                for _, n in ipairs(numeros or {}) do
                    if n == sets[i].numero then sirve = false; break end
                end
                if not sirve then break end
            end
        end
        if sirve then return sets[i] end
    end
    return nil
end


local function place_dynamic(timeline, media_pool, track, fps, start_frame, project)
    local lang = track.language
    local data_path = track.data_path
    if not data_path or not dato_existe(data_path) then
        print("  Aviso: no encuentro el .json de '" .. tostring(lang) .. "', lo salto.")
        return
    end
    local datos = cargar_tabla(data_path) or {}
    local cues = datos.cues or {}
    if #cues == 0 then
        print("  Aviso: '" .. tostring(lang) .. "' no tiene bloques.")
        return
    end

    -- ¿La app pidio un pack en modo .drt? Se prepara ANTES de buscar
    -- sets: si sus clips llegan al Media Pool, la busqueda de "TUS
    -- plantillas" los encuentra sola -son los mismos nombres que ya
    -- reconoce- y se hereda gratis el camino que ya funciona.
    local carpeta_pack_drt = nil
    local pack_previo = nil
    -- QUE pidio el manifiesto. Sin esta linea, "la app no pidio pack" y "el
    -- script no pudo prepararlo" acaban las dos en «no encontre ningun
    -- Text+», y cada una se arregla en un sitio distinto (la v1.0.35 se
    -- diagnostico a ciegas por esto).
    if type(track.plantilla) == "table" then
        local nombre_p = track.plantilla.pack or "?"
        if project then
            print("  El manifiesto pide el pack '" .. tostring(nombre_p) .. "'")
        else
            print("  El manifiesto pide el pack '" .. tostring(nombre_p)
                  .. "' (pero no tengo el proyecto: no puedo prepararlo)")
        end
    else
        print("  El manifiesto NO trae pack: uso tus plantillas del Media "
              .. "Pool, o el diseño automatico si no tienes.")
    end
    if type(track.plantilla) == "table" and project then
        local function res_tl(clave, por_defecto)
            local ok, v = pcall(function() return timeline:GetSetting(clave) end)
            if ok and v and tonumber(v) then return math.floor(tonumber(v)) end
            return por_defecto
        end
        pack_previo = pack_del_manifiesto(
            track, res_tl("timelineResolutionWidth", 1920),
            res_tl("timelineResolutionHeight", 1080))
        if pack_previo and (pack_previo.drt or pack_previo.drb) then
            -- El prep NO puede tumbar la generacion. La leccion de la
            -- v1.0.34: el fix de aridad activo de golpe seis versiones de
            -- codigo del prep nunca corrido en Free, y dentro quedan
            -- llamadas crudas a la API (GetCurrentTimeline, subcarpeta,
            -- buscar_sets_de_plantillas): cualquier error ahi abortaba
            -- place_dynamic ENTERO — cero lineas y cero SFX, el "en free no
            -- hace nada" del reporte. Un prep roto degrada a "sin pack" (el
            -- bin de una corrida anterior si existe, o las plantillas del
            -- usuario, o el diseño automatico), diciendolo; nunca a cero
            -- lineas.
            local ok_prep, carpeta_o_err, aviso_drt = pcall(
                preparar_pack_drt, project, media_pool, pack_previo.nombre,
                pack_previo.formato, pack_previo.drt, pack_previo.drb)
            if ok_prep then
                carpeta_pack_drt = carpeta_o_err
            else
                carpeta_pack_drt = nil
                aviso_drt = "fallo preparando el pack ("
                    .. tostring(carpeta_o_err)
                    .. "). Genero sin el, con lo que haya."
                -- Mismo rescate que hace el gate: si el bin del pack quedo
                -- listo en una corrida anterior, se genera con ese.
                local ok_bin, bin_previo = pcall(function()
                    return subcarpeta(media_pool:GetRootFolder(),
                        nombre_bin_pack(pack_previo.nombre, pack_previo.formato))
                end)
                if ok_bin and bin_previo then
                    local ok_sets, sets_bin = pcall(
                        buscar_sets_de_plantillas, media_pool, bin_previo)
                    if ok_sets and sets_bin and #sets_bin > 0 then
                        carpeta_pack_drt = bin_previo
                        aviso_drt = "fallo preparando el pack ("
                            .. tostring(carpeta_o_err)
                            .. "). Genero con los sets que su bin ya tenia "
                            .. "de una corrida anterior."
                    end
                end
            end
            if aviso_drt then
                print("  Aviso (pack '" .. pack_previo.nombre .. "'): " .. aviso_drt)
            end
        end
    end

    -- ¿El usuario tiene sus propias plantillas (una o varias numeradas)? Si
    -- el pack .drt se preparo arriba, se busca SOLO en su bin.
    local sets, informe_sets = buscar_sets_de_plantillas(media_pool, carpeta_pack_drt)
    local modo_plantillas = #sets > 0

    -- Plantilla para las palabras sueltas sin marcar (rol 'base'). La del
    -- BIN DEL PACK manda: la busqueda global salta los bins RCS a proposito
    -- (un pack de ayer no debe contaminar una generacion sin pack), y por
    -- eso el 'base' del propio pack era INVISIBLE aqui — 55 de 65 bloques
    -- de un video real salieron pintados de principal (reporte del 01-09).
    -- Misma prioridad que la pista SRT: primero el pack, despues el usuario.
    local base_simple_template = nil
    if carpeta_pack_drt then
        base_simple_template =
            NOMBRES.buscar_base(media_pool, carpeta_pack_drt)
        if base_simple_template then
            print("  Plantilla 'simple' (base): la del bin del pack.")
        end
    end
    if not base_simple_template then
        base_simple_template = NOMBRES.buscar_base(media_pool)
        if base_simple_template then
            print("  Encontre una plantilla 'simple' (o 'base') separada " ..
                  "para las palabras sueltas (subtitulo simple).")
        end
    end
    -- Y si hay lineas 'base' sin plantilla propia, DECIRLO: el respaldo a
    -- la principal es visible en pantalla y sin esta linea era un misterio.
    if modo_plantillas and not base_simple_template then
        local hay_lineas_base = false
        for _, c in ipairs(cues) do
            for _, l in ipairs(c.lines or {}) do
                if l.role == "base" then hay_lineas_base = true; break end
            end
            if hay_lineas_base then break end
        end
        if hay_lineas_base then
            print("  Aviso: hay lineas simples (rol 'base') y no encontre "
                  .. "plantilla 'base': saldran con el estilo de la "
                  .. "principal. Arrastra tambien el clip 'base' del "
                  .. "timeline del pack al bin y vuelve a generar.")
        end
    end

    local base_template = nil
    if modo_plantillas then
        print(string.format("\nIdioma '%s': %d bloques dinamicos", lang, #cues))
        print(string.format("  Usando TUS plantillas: encontre %d %s de %d posibles " ..
                            "(tipografia, tamaño y POSICION las pones tu).",
                            #sets, #sets == 1 and "set" or "sets", MAX_SETS))
        for _, linea in ipairs(informe_sets) do print(linea) end
        if #sets > 1 then
            print(string.format("  Los %d sets se van alternando bloque a bloque, " ..
                                "sin repetir el mismo dos veces seguidas.", #sets))
        end
    else
        base_template = obtener_text_plus_base(timeline, media_pool)
        if not base_template then
            if pack_previo ~= nil then
                -- Con un pack pedido, decir QUE gana cada salida: la
                -- rapida (un lienzo cualquiera) ya da el automatico
                -- entero con los estilos del pack; la completa da ademas
                -- la posicion y animacion exactas.
                print("  Aviso: para '" .. tostring(lang) .. "' no hay "
                      .. "NINGUN Text+ en el Media Pool que me sirva de "
                      .. "lienzo y tu version de Resolve no me deja crear "
                      .. "uno por script. Salida RAPIDA (una vez): "
                      .. "arrastra UN Text+ cualquiera (Effects > Titles) "
                      .. "al Media Pool y vuelve a generar — con ese "
                      .. "lienzo genero TODO en automatico con los "
                      .. "estilos del pack (posicion aproximada por rol). "
                      .. "La COMPLETA es el arrastre del bin del aviso de "
                      .. "arriba (posicion y animacion exactas).")
            else
                print("  Aviso: para '" .. tostring(lang) .. "' no encontre ningun Text+ " ..
                      "para usar y no pude crear uno automaticamente (tu version de " ..
                      "Resolve no lo permite por script). Arrastra un Text+ " ..
                      "(Effects > Titles) al Media Pool y vuelve a generar.")
            end
            -- QUE tipos vio: sin esta linea, un idioma que no conozcamos
            -- en GetClipProperty('Type') seria otra ronda a ciegas.
            pcall(function()
                local vistos = {}
                local function recorrer(folder)
                    for _, clip in ipairs(lista_api(folder:GetClipList())) do
                        if #vistos >= 6 then return end
                        local n, t = "?", "?"
                        pcall(function() n = tostring(clip:GetName()) end)
                        pcall(function()
                            t = tostring(clip:GetClipProperty("Type"))
                        end)
                        vistos[#vistos + 1] = n .. " (" .. t .. ")"
                    end
                    for _, sub in ipairs(lista_api(folder:GetSubFolderList())) do
                        if #vistos >= 6 then return end
                        recorrer(sub)
                    end
                end
                recorrer(media_pool:GetRootFolder())
                print("  En el Media Pool vi: "
                      .. (#vistos > 0 and table.concat(vistos, ", ")
                          or "nada") .. ".")
            end)
            print("  Para saber QUE es lo que tu Resolve no deja hacer, corre "
                  .. "una vez: Area de trabajo > Scripts > Utility > "
                  .. "CineCaptions_Prueba_MediaPool. Escribe un informe para pegar.")
            return
        end
        if pack_previo ~= nil then
            -- El manifiesto pedia un pack y estamos en el diseño automatico:
            -- sus clips no llegaron al Media Pool. Se genera con sus VALORES
            -- (tipografia, tamaño, color), que viajan justo para esto desde
            -- la v1.0.37. Hay que DECIR que se pierde, o el usuario ve un
            -- resultado distinto del pack y no sabe por que.
            print(string.format(
                "\nIdioma '%s': %d bloques dinamicos con los ESTILOS del pack "
                .. "'%s' (tipografia, tamaño y color).", lang, #cues,
                tostring(pack_previo.nombre)))
            print("  Sus clips no llegaron al Media Pool en esta version de "
                  .. "Resolve, asi que va sin la animacion ni la posicion "
                  .. "exacta del pack. El texto se coloca igual.")
        else
            print(string.format("\nIdioma '%s': %d bloques dinamicos (modo automatico)", lang, #cues))
        end
    end

    -- Crear o reutilizar las 3 pistas ES-CTX / ES-MAIN / ES-CMP.
    --
    -- NUNCA se calcula el indice de una pista nueva a ojo. Antes esto era
    --   cantidad = timeline:GetTrackCount("video")
    --   timeline:AddTrack("video")
    --   idx = cantidad + 1
    -- y si AddTrack fallaba en silencio, ese "+1" apuntaba a una pista YA
    -- EXISTENTE (tipicamente V1, con el video del usuario): ahi se
    -- escribian encima los subtitulos a lo largo de todo el timeline.
    -- crear_pista_verificada confirma en dos pasos independientes que la
    -- pista es nueva y esta vacia antes de devolver su indice.
    --
    -- Al reutilizar una pista por nombre, se verifica que su contenido
    -- sea SOLO nuestro (puros Text+) antes de limpiarla.
    local indices = {}
    for _, rol in ipairs(DYNAMIC_ORDER) do
        local deseado = string.upper(lang) .. "-" .. ROLE_SHORT[rol]
        -- Se busca la primera pista con ese nombre QUE ADEMAS SEA
        -- REUTILIZABLE (vacia o con puros Text+ nuestros).
        --
        -- Antes se tomaba la primera que coincidiera de nombre y, si tenia
        -- contenido ajeno, se abortaba el idioma entero. Pero si el usuario
        -- borro los subtitulos y puso una imagen suya en esa pista, no poder
        -- generar nunca mas es peor que crear otra: no tocar lo suyo esta
        -- bien, no colocar nada por eso no.
        local existente, ocupadas = nil, 0
        for t = 1, timeline:GetTrackCount("video") do
            local nom = timeline:GetTrackName("video", t) or ""
            if string.upper(nom:gsub("^%s*(.-)%s*$", "%1")) == string.upper(deseado) then
                if pista_video_reutilizable(timeline, t) then
                    existente = t; break
                end
                ocupadas = ocupadas + 1
            end
        end
        if existente == nil then
            if ocupadas > 0 then
                print("  La pista '" .. deseado .. "' tiene contenido tuyo: "
                      .. "la dejo intacta y creo una nueva encima.")
            end
            local idx, error_msg = crear_pista_verificada(timeline, "video", deseado)
            if error_msg then
                -- fail() en vez de un return silencioso: si nos plantamos
                -- aqui NO se coloca nada, y el Puente tiene que responder
                -- FALLO. Antes salia "terminó bien" con el timeline vacio.
                fail("no pude crear la pista '" .. deseado
                     .. "' de forma segura (" .. error_msg .. "). Salto '"
                     .. tostring(lang) .. "' entero para no arriesgar tu timeline.")
            end
            indices[rol] = idx
        else
            local borrados = limpiar_pista(timeline, "video", existente)
            if borrados > 0 then
                print(string.format("  Pista '%s' limpiada (%d clips previos).", deseado, borrados))
            end
            indices[rol] = existente
        end
    end
    do
        local nombres_k = { string.upper(lang) }
        for k = 1, 24 do nombres_k[#nombres_k + 1] = string.format("%s-K%d", string.upper(lang), k) end
        retirar_pistas_nuestras(timeline, nombres_k, "subtitulos normales", "esta corrida es dinamica")
    end

    local fade_frames = math.floor(FADE_OUT_SECONDS * fps + 0.5)

    -- Con un pack .drt NO se aplica fundido. Sus comps traen su PROPIA
    -- animacion de entrada y salida (StyledTextFollower + PolyPath + curvas),
    -- y nuestro fundido escribe Alpha1/Blend: pelearia contra ella y ademas
    -- pisaria el modo de fusion, que es de lo que decide el pack. La regla es
    -- una sola: el diseño lo pone el pack, el script solo escribe el texto.
    if carpeta_pack_drt ~= nil and fade_frames > 0 then
        fade_frames = 0
        print("  Fundido: lo pone el pack (trae su propia animacion), asi "
              .. "que no le añado el mio.")
    end

    -- Un bloque "usa set" cuando tiene alguna linea que no es 'base': es
    -- decir, cuando es un bloque destacado de 2 o 3 lineas y no una palabra
    -- suelta. Se usa para tres cosas: repartir las variantes de diseño,
    -- elegir la separacion, y decidir el adelanto.
    local function usa_set_de(cue)
        for _, l in ipairs((cue or {}).lines or {}) do
            if l.role ~= "base" then return true end
        end
        return false
    end

    -- Cuantos fotogramas ANTES de que se diga la palabra tiene que aparecer
    -- el bloque destacado. Lo pide la app en el manifiesto y se aplica aqui
    -- porque el fps solo se conoce dentro de Resolve.
    --
    -- Solo se adelantan los bloques de 2 y 3 lineas: son los que llevan
    -- animacion y necesitan margen para entrar. Las palabras sueltas no se
    -- tocan, van pegadas al habla.
    local adelanto = math.floor(tonumber(track.adelanto_frames or 0) or 0)
    if adelanto < 0 then adelanto = 0 end
    if adelanto > 0 then
        print(string.format("  Adelanto: los bloques destacados entran %d "
                            .. "fotograma(s) antes.", adelanto))
    end

    -- En que fotograma arranca un bloque, ya con el adelanto aplicado.
    --
    -- El adelanto NO puede comerse al bloque anterior. Con un adelanto mas
    -- grande que la duracion del bloque de delante -por ejemplo 30
    -- fotogramas y una palabra suelta que dura 15- el bloque adelantado
    -- arrancaba ANTES de que empezara el anterior, y los dos clips se
    -- encabalgaban. Por eso se pasa el inicio ya fijado del anterior y se
    -- deja siempre al menos un fotograma de por medio.
    --
    -- Y tampoco puede comerse el HABLA del anterior (v2.0.2, reporte
    -- literal: «desaparecen antes de que termine de decir la palabra...
    -- todo debe ser acorde al audio»): el fin del bloque anterior se
    -- recorta al inicio adelantado de este, asi que con adelanto > 0 la
    -- palabra suelta de delante se cortaba a medias. El adelanto se
    -- acorta hasta donde el anterior deja de hablar (nunca mas tarde del
    -- inicio real de este, por si Whisper solapa dos palabras).
    local function inicio_de(cue, ini_anterior, fin_hablado_anterior)
        if cue == nil then return nil end
        local real = start_frame + math.floor(cue.start * fps + 0.5)
        local ini = real - (usa_set_de(cue) and adelanto or 0)
        if fin_hablado_anterior ~= nil then
            ini = math.max(ini, math.min(real, fin_hablado_anterior))
        end
        if ini < start_frame then ini = start_frame end
        if ini_anterior ~= nil and ini <= ini_anterior then
            ini = ini_anterior + 1
        end
        return ini
    end

    -- Reparto de variantes: solo cuentan los bloques que usan set (no 'base').
    local bloques_con_set = 0
    for _, cue in ipairs(cues) do
        if usa_set_de(cue) then bloques_con_set = bloques_con_set + 1 end
    end
    -- Con plantillas propias se alternan los SETS del usuario; sin ellas,
    -- las variantes de diseño automatico.
    -- El pack de estilos, si la app pidio uno. Las plantillas del Media Pool
    -- del usuario siguen mandando sobre el: esa regla no se toca.
    local function res(clave, por_defecto)
        local ok, v = pcall(function()
            return tonumber(timeline:GetSetting(clave))
        end)
        if ok and v then return math.floor(v) end
        return por_defecto
    end

    -- OJO: hasta la v1.0.27 esta linea decia 'track_info' -una global
    -- inexistente, no el parametro de la funcion, que se llama 'track'-.
    -- pack_del_manifiesto(nil, ...) siempre devolvia nil, asi que un pack en
    -- modo VALORES (estilos.json, sin .drt) jamas se aplicaba en Resolve
    -- Free: caia en silencio al diseño automatico. En Studio no pasaba
    -- -alla el parametro se llama igual que se usaba-, asi que era una
    -- diferencia de comportamiento entre Free y Studio que nadie habia
    -- reportado como tal.
    local pack = (not modo_plantillas) and pack_del_manifiesto(
        track, res("timelineResolutionWidth", 1920),
        res("timelineResolutionHeight", 1080)) or nil

    -- El modo «Diseño dinámico» (v1.0.49): los estilos y la posicion los
    -- eligio el usuario en el programa y viajan POR VALORES en el track.
    -- No toca el Media Pool ni el prep de packs. Prioridad: los sets del
    -- pool del usuario (si los tiene) ganan; despues este diseño; despues
    -- pack; despues los presets de fabrica.
    local estilos_base = estilos_con_fuentes(track.fonts)
    local diseno = track.diseno
    local diseno_activo = false
    local ancla_dis, factor_dis = nil, nil
    if type(diseno) == "table" and type(diseno.estilos) == "table" then
        diseno_activo = true
        -- 'base' solo viene cuando el preset lo define (el motor de 2
        -- lineas, v1.0.51): es el estilo de los bloques simples. Sin el,
        -- 'base' sigue cayendo al estilo de 'main', como siempre.
        for _, rol in ipairs({ "context", "main", "complement", "base" }) do
            local e = diseno.estilos[rol]
            if type(e) == "table" then
                estilos_base[rol] = estilo_del_manifiesto(e)
            end
        end
        ancla_dis = tonumber(diseno.ancla_y)
        factor_dis = tonumber(diseno.factor_separacion)
        print(string.format("  Diseño dinámico: preset '%s' (estilos y "
            .. "posición elegidos en el programa).",
            tostring(diseno.preset or "personalizado")))
    end

    -- El fundido de ENTRADA (v1.0.51) es solo del camino por valores puro
    -- (diseño dinamico / automatico): a un pack, a las plantillas del
    -- usuario o a un .setting cargado no se les toca la entrada. El gate
    -- fino por clip esta abajo, junto a aplicar_fades. (Se calcula aqui y
    -- no junto a fade_frames porque necesita 'diseno', que se lee recien
    -- en este punto.)
    local entrada_frames = math.floor(FADE_IN_SECONDS * fps + 0.5)
    if diseno_activo and diseno.entrada == "ninguna" then
        entrada_frames = 0
    end
    if pack and pack.drt and #pack.sets == 0 then
        -- El pack pedido ES un .drt pero no se pudo preparar (el aviso ya
        -- salio mas arriba). No hay valores de respaldo: este pack nunca
        -- los tuvo, es puro .drt.
        print("  El pack '" .. pack.nombre .. "' no se pudo aplicar (ver "
              .. "aviso arriba): sigo con el diseño automático.")
        pack = nil
    elseif pack then
        print(string.format("  Pack de estilos: '%s' (%d sets, %s).",
            tostring(pack.nombre), #pack.sets,
            (pack.formato == "v") and "vertical"
                or (pack.formato == "c") and "cuadrado" or "horizontal"))
        if pack.aviso then print("  Aviso: " .. pack.aviso) end
    end

    local n_variantes
    if modo_plantillas then
        n_variantes = #sets
    elseif pack and #pack.sets > 0 then
        n_variantes = #pack.sets
    else
        n_variantes = #AUTO_PRESETS
    end
    local reparto = orden_de_variantes(bloques_con_set, n_variantes, 20260811)
    -- «Estilo fijo»: la variante elegida en Composicion del bloque (0 = ir alternando)
    local fijo = tonumber(track.estilo_fijo) or 0
    if fijo >= 1 and fijo <= n_variantes then
        for i = 1, math.max(1, #reparto) do reparto[i] = fijo end
    end
    local turno = 1

    -- 'con_hold' cuenta los bloques que TENIAN tiempo de sobra detras del
    -- habla. Sin ese dato, un proyecto donde todos los bloques van pegados
    -- salia acusando a Resolve de no dejar poner fotogramas clave, cuando lo
    -- que pasaba es que no habia hueco donde desvanecer.
    -- 'con_pack' cuenta las lineas que entraron con el NODO ENTERO del pack
    -- (degradados, formas, fondos) y no solo con sus valores. Si el pack se
    -- pidio y esto queda en cero, hay que decirlo: se parece pero no es el
    -- diseño.
    local colocados, sin_texto, con_fundido, con_hold, con_pack = 0, 0, 0, 0, 0
    local con_entrada = 0
    -- Bloques que ningun set del pack podia vestir enteros: se omiten (no se
    -- mezclan estilos) y se cuentan para decirlo al final, en el registro.
    local omitidos_sin_set = 0

    -- El veto de tildes del manifiesto (v1.0.61): {rol = {numeros de set}}
    -- cuya tipografia no dibuja acentos. Se aplica solo a los bloques cuyo
    -- texto de ese rol lleva tilde; manifiestos viejos no lo traen y todo
    -- sigue como siempre.
    local sets_sin_acentos = (pack_previo and pack_previo.sets_sin_acentos)
                             or {}
    local bloques_con_veto = 0
    local veto_sin_salida = 0
    -- Arial donde falta la tipografia del clip (v2.0.2): {"rol|numero" =
    -- {"Arial", estilo}}, medido por la app. Se cuenta para decirlo.
    local fuentes_respaldo = (pack_previo and pack_previo.fuentes_respaldo)
                             or {}
    local con_arial = 0
    -- La posicion del diseño por clip (v3.3.0): de pack_previo, como el
    -- veto y el Arial — con los clips del bin, 'pack' es nil. SOLO si los
    -- sets salieron del bin del pack: con el prep fallido la busqueda es
    -- global y los clips serian las plantillas del USUARIO, cuya posicion
    -- no es asunto del pack.
    local transformaciones = (carpeta_pack_drt ~= nil and pack_previo
                              and pack_previo.transformaciones) or {}
    local ancho_tl = res("timelineResolutionWidth", 1920)
    local alto_tl = res("timelineResolutionHeight", 1080)
    TRANSF = { ya = 0, puestas = 0, fallidas = 0 }
    -- v3.4.0: la Composicion del manifiesto (nil = la plantilla tal cual).
    -- Las medidas de las lineas van por formato: el que decidio el pack (o
    -- el de la resolucion).
    local comp_activa = composicion_activa(track.composicion)
    local formato_comp = (pack_previo and pack_previo.formato)
        or ((alto_tl > ancho_tl) and "v" or "h")
    COMP = { movidas = 0, alineadas = 0, sin_medida = 0, fallidas = 0,
             layout = comp_activa and comp_activa.layout or nil }
    -- Los emojis de los bloques (v3.3.0): se anotan al colocar cada bloque
    -- (cuando entra la principal, hasta donde dura, a que altura quedaron
    -- sus lineas) y se colocan al final, en su propia pista.
    local planes_emoji = {}
    -- Sets usados de verdad, bloque a bloque (v2.0.2): el registro decia
    -- «ningun set dos veces seguidas» contando el set PEDIDO por la rueda,
    -- no el que set_para devolvia tras el veto.
    local uso_por_variante = {}
    local ultimo_set_usado = nil
    local repetidos_seguidos = 0

    local ini_bloque = inicio_de(cues[1], nil)
    -- Huella de colocacion (v2.0.3): los 3 primeros bloques con set
    -- imprimen el inicio-fin REAL de cada linea, para que el proximo
    -- reporte de escalera se lea en numeros y no en capturas.
    local bloques_huella = 0

    for i_cue, cue in ipairs(cues) do
        local usa_set = usa_set_de(cue)
        if usa_set then bloques_huella = bloques_huella + 1 end
        -- v3.4.0: las lineas de ESTE bloque, para la Composicion.
        local bloque_comp = {}

        -- Donde deja de hablarse de verdad. 'end' viene estirado para que no
        -- queden huecos, asi que no sirve para saberlo. Un manifiesto viejo
        -- no trae este dato: ahi se toma el final del bloque, que deja el
        -- fundido en cero — preferible a volver a borrar sobre la voz.
        -- Va ANTES de inicio_de(siguiente): el adelanto del siguiente no
        -- puede pisar este habla (v2.0.2).
        local fin_hablado_frame = start_frame + math.floor(
            (tonumber(cue.fin_hablado) or cue["end"]) * fps + 0.5)

        -- Hay que saber donde arranca el SIGUIENTE para saber donde termina
        -- este: si el que viene se adelanto, este tiene que cerrar justo
        -- antes. Es lo unico que hace falta para que sigan pegados y no se
        -- encabalguen.
        local ini_siguiente = inicio_de(cues[i_cue + 1], ini_bloque,
                                        fin_hablado_frame)

        -- Separacion con el bloque siguiente. Antes los clips quedaban
        -- pegados (el final de uno era el primer frame del otro).
        local gap = usa_set and GAP_BLOQUE_FRAMES or GAP_BASICO_FRAMES
        local fin_frame = start_frame + math.floor(cue["end"] * fps + 0.5) - gap

        -- Cortar solo si de verdad invade. Cuando hay silencio de por medio
        -- el final natural ya cae antes, asi que el hueco se conserva: lo
        -- unico que pasa es que se acorta lo que el siguiente se adelanto,
        -- que es exactamente lo que se quiere.
        if ini_siguiente ~= nil and fin_frame > ini_siguiente then
            fin_frame = ini_siguiente
        end

        -- v1.0.63 (reporte literal: «dejan fotogramas vacios entre
        -- medios»): el bump anti-solape de inicio_de (ini_anterior + 1)
        -- empuja el arranque del siguiente sin extender el fin de este —
        -- con un cue de menos de medio fotograma quedaba EXACTAMENTE un
        -- frame vacio que nadie cerraba. Un hueco de 1-2 frames solo
        -- puede ser nuestro: los silencios que la app deja a proposito
        -- miden mas de HOLD_MAXIMO (2 s), decenas de frames.
        if ini_siguiente ~= nil and fin_frame < ini_siguiente
                and (ini_siguiente - fin_frame) <= 2 then
            fin_frame = ini_siguiente
        end

        -- El turno se GASTA tras elegir el set (v2.0.2): un bloque
        -- omitido por falta de set no consume rueda.
        local indice_estilo = 1
        if usa_set then
            indice_estilo = reparto[turno] or 1
            -- v5.8: la APP decide el estilo de cada bloque (cue.estilo = el número de la variante del pack) y lo enseña en Creativo;
            -- la rueda de arriba solo vale si la app no mandó nada (manifiestos viejos)
            if modo_plantillas and cue.estilo ~= nil then
                for j, s_pack in ipairs(sets) do
                    if s_pack.numero == tonumber(cue.estilo) then
                        indice_estilo = j
                        break
                    end
                end
            end
        end
        -- Solo hace falta calcular estilos si el script va a imponerlos.
        local estilos, n_set_pack = nil, nil
        if modo_plantillas then
            estilos = nil
        elseif diseno_activo then
            -- El look es EL ELEGIDO: sin rotacion de variantes.
            estilos = estilos_base
        elseif pack then
            estilos, n_set_pack = estilos_del_pack(pack, indice_estilo)
        else
            estilos = estilos_del_preset(estilos_base, indice_estilo)
        end
        local juego = nil
        if modo_plantillas then
            -- Que roles necesita ESTE bloque ('base' comparte pista con
            -- 'main'). Si ningun set los tiene todos, el bloque se omite
            -- entero: mezclar sets o sustituir por 'principal' era lo que
            -- se veia como "el pack no respeta su diseño".
            local roles_bloque = {}
            for _, l in ipairs(cue.lines or {}) do
                local texto = (l.text or ""):gsub("^%s*(.-)%s*$", "%1")
                if texto ~= "" then
                    roles_bloque[(l.role == "base") and "main" or l.role] = true
                end
            end
            -- El veto por tildes (v1.0.61): solo los roles de ESTE bloque
            -- cuyo texto lleva acento y cuyo rol figura en el veto.
            local vetado, hay_veto = {}, false
            if next(sets_sin_acentos) ~= nil then
                for _, l in ipairs(cue.lines or {}) do
                    local rol = (l.role == "base") and "main" or l.role
                    if sets_sin_acentos[rol] ~= nil
                            and tiene_acentos(l.text) then
                        vetado[rol] = sets_sin_acentos[rol]
                        hay_veto = true
                    end
                end
            end
            if hay_veto then
                bloques_con_veto = bloques_con_veto + 1
            end
            juego = set_para(sets, indice_estilo, roles_bloque,
                             hay_veto and vetado or nil)
            if juego == nil and hay_veto then
                -- Sin el veto habria set: mejor una tilde con la fuente
                -- equivocada que omitir un bloque que la version anterior
                -- colocaba. Se dice, no en silencio.
                juego = set_para(sets, indice_estilo, roles_bloque)
                if juego ~= nil then
                    veto_sin_salida = veto_sin_salida + 1
                end
            end
            if juego == nil then
                omitidos_sin_set = omitidos_sin_set + 1
                goto siguiente_cue
            end
        end
        if usa_set then
            -- El set que SALIO, no el pedido: tras el veto pueden diferir,
            -- y el registro tiene que decir la verdad.
            local usado = indice_estilo
            if modo_plantillas then
                for i, s in ipairs(sets) do
                    if s == juego then usado = i; break end
                end
            end
            -- v5.8: si la APP decidio el estilo (alternar, uno fijo o el que el usuario eligio en Creativo) repetirlo es una eleccion, no un fallo
            if usado == ultimo_set_usado and cue.estilo == nil then
                repetidos_seguidos = repetidos_seguidos + 1
            end
            ultimo_set_usado = usado
            uso_por_variante[usado] = (uso_por_variante[usado] or 0) + 1
            turno = turno + 1
        end

        -- La escalera (reporte literal 14-09: «los bloques desaparecen en
        -- escalera... las primeras deben esperar a la ultima y salir
        -- juntas»): un titulo Fusion del pool tiene la duracion de su comp
        -- y Resolve puede RECORTAR en silencio cada linea a esa duracion
        -- cuando el bloque dura mas — la que entro primero se cortaba
        -- primero. La verdad se mide DESPUES de colocar (GetDuration,
        -- abajo): la primera linea colocada fija el fin que sus hermanas
        -- pueden alcanzar. Para eso se colocan en orden de entrada — la
        -- mas temprana es la mas restrictiva (inicio + largo del comp).
        -- En Free el registro nunca mostro recortes: aqui es un no-op.
        -- El do...end es obligatorio: el goto de arriba no puede saltar
        -- por encima de un local del mismo bloque que su etiqueta.
        do
        local lineas_en_orden = {}
        for _, l in ipairs(cue.lines or {}) do
            lineas_en_orden[#lineas_en_orden + 1] = l
        end
        table.sort(lineas_en_orden, function(a, b)
            return (a.start or cue.start) < (b.start or cue.start)
        end)
        local primera_colocada = true

        for _, linea in ipairs(lineas_en_orden) do
            local rol = linea.role
            local texto = (linea.text or ""):gsub("^%s*(.-)%s*$", "%1")
            if texto ~= "" then
                local rol_pista = (rol == "base") and "main" or rol
                local idx_pista = indices[rol_pista]

                -- Que plantilla usa esta linea, de menor a mayor rodeo:
                -- la 'base' propia del usuario, la del set que toca, o la
                -- principal.
                --
                -- buscar_sets_de_plantillas ya dejo cada set con los tres
                -- roles (o avisando de cual falta en TODOS). Antes habia un
                -- 'or sets[1][rol_pista]' en medio, y con el set 1 incompleto
                -- la cadena terminaba en juego.main en silencio: el
                -- complemento salia con el estilo de la principal y no habia
                -- forma de saber por que.
                local usa_base_propia = (rol == "base") and base_simple_template ~= nil
                local plantilla
                if usa_base_propia then
                    plantilla = base_simple_template
                elseif modo_plantillas then
                    -- El set ya se eligio para que TENGA estos roles
                    -- (set_para), asi que no hace falta respaldo. Y no debe
                    -- haberlo: hasta la v1.0.32 la cadena acababa en
                    -- juego.main y el complemento salia con el estilo de la
                    -- principal — "no respeta el diseño" en el reporte.
                    plantilla = juego[rol_pista]
                else
                    plantilla = base_template
                end

                if idx_pista and plantilla then
                    -- Cada linea entra escalonada respecto al bloque, no
                    -- respecto al timeline: asi el escalonado se conserva
                    -- aunque el arranque del bloque se haya movido.
                    local retardo = math.floor(
                        (((linea.start or cue.start) - cue.start) * fps) + 0.5)
                    local inicio_frame = ini_bloque + retardo
                    if inicio_frame < start_frame then inicio_frame = start_frame end
                    -- NUNCA terminar despues que los hermanos (v1.0.57):
                    -- cuando el adelanto del bloque SIGUIENTE recorta
                    -- fin_frame por debajo del inicio de una linea tardia,
                    -- el math.max(1,...) dejaba ese clip de 1 frame
                    -- acabando DESPUES de fin_frame-1 — la «salida en
                    -- escalera» del reporte. Con el clamp cierra CON los
                    -- demas.
                    if inicio_frame > fin_frame - 1 then
                        inicio_frame = fin_frame - 1
                    end
                    local duracion = math.max(1, fin_frame - inicio_frame)

                    -- Desde donde arranca el COMP dentro del clip (no en el
                    -- timeline).
                    --
                    -- v1.0.68 (reporte literal 12-09: «entran como que
                    -- cortados, no desde el principio y por ello no se les
                    -- ve la animacion»): el comp arranca SIEMPRE en su
                    -- fotograma 0 — cada linea reproduce su animacion de
                    -- entrada ENTERA al entrar en su tiempo real. Esto
                    -- INVIERTE a proposito la fase v1.0.25/v1.0.33 (el comp
                    -- empezaba avanzado en 'retardo' para que las curvas
                    -- fueran en fase y cerraran juntas — con retardos
                    -- reales de 12-45 fotogramas eso SALTABA la entrada
                    -- entera): el FIN comun del grupo NO cambia (fin_frame
                    -- es el mismo para las tres lineas; startFrame no toca
                    -- recordFrame ni duracion), lo unico cedido es que la
                    -- salida de las lineas 2/3 puede quedar a mitad de
                    -- curva. Elegido por orden literal — no lo «arregles»
                    -- de vuelta sin una orden suya.
                    --
                    -- 'continuacion' (manifiestos <= v1.0.65, base
                    -- acumulativo) conserva su lectura: la palabra que se
                    -- suma no re-anima la entrada del texto que ya estaba.
                    local desfase = 0
                    local viene_de = tonumber(cue.continuacion)
                    if viene_de then
                        desfase = math.floor((cue.start - viene_de) * fps + 0.5)
                    end
                    if desfase < 0 then desfase = 0 end
                    -- v5.7 (FIX DE ANIMACION): linea que se ve tan poco que su
                    -- entrada no alcanzaria a mostrar el texto -> la app marca
                    -- 'salto_anim' (segundos) y el comp arranca adelantado.
                    -- Solo lineas cortas y solo con packs / plantillas.
                    if pack or modo_plantillas then
                        local salto_anim = tonumber(linea.salto_anim) or 0
                        if salto_anim > 0 then
                            local d = math.floor(salto_anim * fps + 0.5)
                            if d > desfase then desfase = d end
                        end
                    end

                    local function colocar(desde)
                        return colocar_medido(media_pool, timeline, plantilla,
                                              desde, duracion, idx_pista,
                                              inicio_frame, fps, COLORES_CC.texto)
                    end

                    local item, puesto = colocar(desfase)
                    if item == nil and desfase > 0 then
                        -- El generador puede ser mas corto que el desfase.
                        -- Caer DIRECTO a 0 dejaba esa linea animando
                        -- 'retardo' fotogramas por detras de sus hermanas
                        -- — su salida cerraba tarde: la otra mitad de la
                        -- «salida en escalera» (v1.0.57). Primero se
                        -- recorta el desfase a lo que el generador permita
                        -- y solo despues se cae a 0, DICIENDOLO.
                        local desfase_max = 0
                        pcall(function()
                            local frames = tonumber(
                                plantilla:GetClipProperty("Frames")) or 0
                            desfase_max = math.max(0,
                                math.floor(frames) - duracion)
                        end)
                        if desfase_max > 0 and desfase_max < desfase then
                            item, puesto = colocar(desfase_max)
                            if item ~= nil then
                                print(string.format("  Aviso: el generador "
                                    .. "de '%s' es corto para su desfase "
                                    .. "(%d); lo recorte a %d para que "
                                    .. "cierre casi en fase.",
                                    tostring(rol), desfase, desfase_max))
                            end
                        end
                        if item == nil then
                            item, puesto = colocar(0)
                            if item ~= nil then
                                print(string.format("  Aviso: '%s' anima "
                                    .. "sin desfase (generador corto): su "
                                    .. "salida puede no cerrar exacta con "
                                    .. "las otras lineas.", tostring(rol)))
                            end
                        end
                    end
                    if item ~= nil then
                        puesto = puesto or 0
                        -- v1.0.63: nadie verificaba que Resolve respetara
                        -- la duracion pedida — si la recorta EN SILENCIO
                        -- (en vez de devolver falso), esa linea termina
                        -- ANTES que sus hermanas: escalera real sin una
                        -- linea que la explique. Que la llamada no
                        -- reviente no prueba nada (la leccion del
                        -- fundido).
                        -- v2.0.2: si recorto la PRIMERA linea del bloque,
                        -- ese es el fin que las demas pueden alcanzar —
                        -- se baja fin_frame y las hermanas cierran con
                        -- ella. v2.0.3: 'puesto' viene del colocador, que
                        -- ya compenso el fotograma de menos de Resolve —
                        -- lo que quede corto aqui es un recorte de verdad.
                        if usa_set and bloques_huella <= 3 and puesto > 0 then
                            if bloques_huella == 1 and primera_colocada then
                                print("  Huella de colocacion (3 primeros "
                                      .. "bloques con set): inicio-fin real "
                                      .. "(fotogramas).")
                            end
                            print(string.format("    %.2fs %s: %d-%d (%d f)",
                                tonumber(cue.start) or 0, tostring(rol),
                                inicio_frame, inicio_frame + puesto - 1,
                                puesto))
                        end
                        if puesto > 0 and puesto ~= duracion then
                            if primera_colocada and puesto < duracion then
                                fin_frame = inicio_frame + puesto
                                print(string.format("  La plantilla de "
                                    .. "'%s' dura %d fotogramas: el bloque "
                                    .. "de %.2fs se acorta de %d a %d para "
                                    .. "que las lineas cierren juntas.",
                                    tostring(rol), puesto,
                                    tonumber(cue.start) or 0, duracion,
                                    puesto))
                            else
                                print(string.format("  Aviso: Resolve "
                                    .. "coloco '%s' con %d fotogramas "
                                    .. "(pedi %d) en %.2fs — esa linea "
                                    .. "puede no cerrar junto a sus "
                                    .. "hermanas.", tostring(rol), puesto,
                                    duracion, tonumber(cue.start) or 0))
                            end
                        end
                        primera_colocada = false
                        local tool = get_text_plus(item)
                        -- EL ORDEN IMPORTA: primero el nodo entero del pack,
                        -- despues el texto. Al reves, LoadSettings borraria lo
                        -- que se acaba de escribir (el .setting trae su propio
                        -- StyledText dentro).
                        local cargado = false
                        if tool and pack and not usa_base_propia then
                            local con_base = (rol == "base") and pack.base ~= nil
                            local estilo_rol = con_base
                                and estilo_del_manifiesto(pack.base)
                                or (estilos and estilos[rol_pista])
                            cargado = cargar_setting(item, tool,
                                ruta_de_setting(pack,
                                    con_base and "base" or n_set_pack,
                                    con_base and "base" or rol_pista),
                                estilo_rol)
                            if cargado then con_pack = con_pack + 1 end
                        end
                        if tool and set_input(tool, "StyledText", texto) then
                            -- Arial donde falta la tipografia del clip
                            -- (v2.0.2, pedido literal: «en el caso de no
                            -- tener la tipografia se use Arial en el grosor
                            -- o inclinacion de la que falta»). La UNICA
                            -- excepcion nueva al «solo StyledText» del modo
                            -- plantillas, y solo con la medicion de la app
                            -- delante: sin entrada no se toca Font ni
                            -- Style. DESPUES del texto (LoadSettings
                            -- pisaria lo escrito).
                            if modo_plantillas and juego ~= nil then
                                local clave_f = usa_base_propia and "base|0"
                                    or (rol_pista .. "|"
                                        .. tostring(juego.numero))
                                local arial = fuentes_respaldo[clave_f]
                                if type(arial) == "table" and arial[1]
                                        and arial[2]
                                        and set_input(tool, "Font", arial[1])
                                        and set_input(tool, "Style", arial[2])
                                        then
                                    con_arial = con_arial + 1
                                end
                                -- La posicion del diseño, si Resolve la
                                -- dejo en el centro (v3.3.0).
                                aplicar_transformacion(item,
                                    transformaciones[clave_f], ancho_tl,
                                    alto_tl)
                            end
                            if cargado then
                                -- El pack decide EL LOOK Y LA POSICION. Hasta
                                -- la v1.0.25 aqui se pisaba el Center con
                                -- altura_de_linea(), para tapar el hueco de
                                -- la tercera linea en bloques de 2 -pero en
                                -- un pack el usuario YA coloco contexto/
                                -- principal/complemento donde los quiere: esa
                                -- disposicion ES el diseno. Pisarla es
                                -- exactamente lo que prohibe la regla de
                                -- nunca destruir el trabajo del usuario.
                                --
                                -- EXCEPCION declarada: los .setting de la
                                -- cache instalada (pack incorporado) no
                                -- traen posicion -vive en el PolyPath del
                                -- grupo, irreproducible offline-. Sin esto,
                                -- los tres roles salian apilados al centro.
                                if pack and pack.settings_sin_posicion then
                                    set_center(tool, 0.5,
                                        altura_de_linea(rol, estilos))
                                end
                            elseif not modo_plantillas and not usa_base_propia then
                                -- El estilo automatico SOLO cuando el diseño lo
                                -- decide el script. Si el usuario puso sus
                                -- plantillas (o su 'base'), se le respeta la
                                -- tipografia, el tamaño y la posicion: aqui solo
                                -- se escribe el texto. Hasta la 1.0.15 esto se
                                -- aplicaba siempre y le pisaba su diseño.
                                --
                                -- Con un pack cuyo .setting no cargo, aqui
                                -- entran igual sus VALORES: para eso viajan.
                                local con_base = (rol == "base") and pack ~= nil
                                    and pack.base ~= nil
                                local estilo
                                if con_base then
                                    estilo = estilo_del_manifiesto(pack.base)
                                elseif rol == "base" and estilos
                                        and estilos.base then
                                    -- 'base' con estilo propio (v1.0.51): si
                                    -- el diseño lo trae (motor de 2 lineas),
                                    -- los bloques simples lo usan — sin esto,
                                    -- lo que era el complemento saldria
                                    -- grande y dorado como otra clave.
                                    estilo = estilos.base
                                else
                                    estilo = estilos and estilos[rol_pista]
                                end
                                if estilo then
                                    aplicar_estilo(tool, estilo,
                                        altura_de_linea(rol, estilos,
                                            ancla_dis, factor_dis))
                                end
                            end
                            -- El fundido SOLO en el tiempo prestado.
                            --
                            -- Antes se aplicaba en los ultimos fade_frames
                            -- del clip a secas, y como el bloque terminaba
                            -- justo con su ultima palabra, el texto se estaba
                            -- borrando MIENTRAS aun se hablaba. Ahora se mide
                            -- contra 'fin_hablado': si detras del habla no
                            -- sobra tiempo, no hay fundido y el bloque corta
                            -- limpio para que entre el siguiente.
                            local hold = fin_frame - fin_hablado_frame
                            local fade = math.min(fade_frames,
                                                  math.max(0, hold),
                                                  duracion - 1)
                            -- La entrada solo en el camino por valores puro:
                            -- ni plantillas del usuario, ni .setting cargado
                            -- (traen su animacion), ni el 'base' propio. Y
                            -- nunca sobre un clip continuacion (re-animar la
                            -- entrada del texto que ya estaba en pantalla
                            -- era el parpadeo entre palabras).
                            local entrada = 0
                            if entrada_frames > 0 and not modo_plantillas
                                    and not cargado and not usa_base_propia
                                    and cue.continuacion == nil then
                                entrada = math.min(entrada_frames,
                                                   duracion - 1)
                            end
                            if fade >= 1 then
                                con_hold = con_hold + 1
                            end
                            if entrada >= 1 or fade >= 1 then
                                local e_ok, s_ok = aplicar_fades(item,
                                                                 entrada, fade)
                                if e_ok then
                                    con_entrada = con_entrada + 1
                                end
                                if s_ok then
                                    con_fundido = con_fundido + 1
                                end
                            end
                            if comp_activa then
                                local clave_c = usa_base_propia and "base|0"
                                    or (rol_pista .. "|" .. tostring(
                                        juego and juego.numero or 1))
                                local m = type(linea.medidas) == "table"
                                    and linea.medidas[formato_comp] or nil
                                bloque_comp[#bloque_comp + 1] = {
                                    rol = rol, item = item,
                                    ancho_em = (type(m) == "table")
                                        and tonumber(m[clave_c]) or nil,
                                    zx = prop_de(item, "ZoomX") or 1 }
                            end
                            colocados = colocados + 1
                        else
                            sin_texto = sin_texto + 1
                        end
                    end
                end
            end
        end
        -- v3.4.0: la Composicion del bloque, SOBRE lo que la plantilla (o
        -- Resolve) dejo: se lee el Pan/Tilt actual y se le suma. Con "cc"
        -- y 0/0 este bloque ni se entra (comp_activa es nil).
        if comp_activa and #bloque_comp > 0 then
            local d = desplazamientos_bloque(comp_activa, ini_bloque,
                                             bloque_comp, ancho_tl, alto_tl)
            for k, l in ipairs(bloque_comp) do
                local pan = prop_de(l.item, "Pan") or 0
                local tilt = prop_de(l.item, "Tilt") or 0
                if poner_props(l.item, { Pan = pan + d[k].dx,
                                         Tilt = tilt + d[k].dy }) then
                    COMP.movidas = COMP.movidas + 1
                    if d[k].alineada then
                        COMP.alineadas = COMP.alineadas + 1
                    end
                else
                    COMP.fallidas = COMP.fallidas + 1
                end
                if d[k].sin_medida then
                    COMP.sin_medida = COMP.sin_medida + 1
                end
            end
        end
        -- El emoji del bloque (v3.3.0): entra con la PRINCIPAL (como el
        -- golpe del SFX) y dura hasta el fin del bloque; su altura sale de
        -- la de las lineas: la posicion del diseño con los clips del bin,
        -- altura_de_linea en el resto (centro = 0, arriba positivo).
        if cue.emoji then
            local plan = { emoji = cue.emoji, fin = fin_frame }
            -- v3.4.0: el emoji se mueve con el grupo (Altura/Horizontal).
            if comp_activa then
                plan.dx_n = comp_activa.horizontal
                plan.dy_n = comp_activa.altura
            end
            -- v5.3: si el pack trae el bloque 'imagen', ESE bloque manda donde y de que tamaño va
            -- el emoji (su Pan/Tilt/Zoom en el bin); sin el, va debajo de las lineas.
            if modo_plantillas and juego ~= nil then
                local slot = transformaciones["image|" .. tostring(juego.numero)]
                    or transformaciones["image|1"]
                if slot then plan.slot = slot end
            end
            -- v3.3.1: el emoji pertenece a UNA linea (cue.emoji_linea, base
            -- 0, la de la palabra elegida) y la app mando el ancho de esa
            -- linea por formato y set (l.emoji_medidas): se coloca al FINAL
            -- de esa linea. Sin medidas, encima del bloque como en la v3.3.0.
            local k_emoji = (tonumber(cue.emoji_linea) or 0) + 1
            for k, l in ipairs(cue.lines or {}) do
                local texto_l = (l.text or ""):gsub("^%s*(.-)%s*$", "%1")
                if texto_l ~= "" then
                    local y, tr
                    if modo_plantillas and juego ~= nil then
                        local clave = (l.role == "base"
                                       and base_simple_template ~= nil)
                            and "base|0"
                            or (((l.role == "base") and "main" or l.role)
                                .. "|" .. tostring(juego.numero))
                        tr = transformaciones[clave]
                        y = tr and tonumber(tr[2]) or 0
                    else
                        y = altura_de_linea(l.role, estilos or {}, ancla_dis,
                                            factor_dis) - 0.5
                    end
                    if k == k_emoji then
                        plan.medidas = (type(l.emoji_medidas) == "table")
                            and l.emoji_medidas or nil
                        plan.numero = juego and juego.numero or nil
                        plan.y = y
                        plan.x = tr and tonumber(tr[1]) or 0
                        plan.zx = tr and tonumber(tr[3]) or 1
                    end
                    plan.y_arriba = math.max(plan.y_arriba or y, y)
                    plan.y_abajo = math.min(plan.y_abajo or y, y)
                    if l.role == "main" or plan.ini == nil then
                        local r = math.floor((((l.start or cue.start)
                            - cue.start) * fps) + 0.5)
                        plan.ini = math.max(start_frame,
                            math.min(ini_bloque + r, fin_frame - 1))
                    end
                end
            end
            -- v4.1.0 (pedido literal: «que los png o emoji duren lo que
            -- dura la palabra, siguen extendiendose»): tambien EMPIEZA con
            -- la palabra (cue.emoji_ini), no con su linea ni con el bloque:
            -- en un bloque base de 5 palabras con la clave en la 3.ª el
            -- emoji salia desde la primera. Sin la clave, como siempre.
            if plan.ini and tonumber(cue.emoji_ini) then
                local f0 = ini_bloque + math.floor(
                    ((tonumber(cue.emoji_ini) - cue.start) * fps) + 0.5)
                plan.ini = math.max(ini_bloque, math.min(f0, fin_frame - 2))
            end
            -- v3.3.3 (pedido literal: «ajusta su duracion solo hasta donde
            -- dura la palabra clave, de momento dura mas»): el emoji
            -- termina cuando termina la PALABRA (cue.emoji_fin, segundos),
            -- no con el bloque; minimo 2 fotogramas. Sin la clave
            -- (manifiestos viejos), hasta el fin del bloque como siempre.
            if plan.ini and tonumber(cue.emoji_fin) then
                local f = ini_bloque + math.floor(
                    ((tonumber(cue.emoji_fin) - cue.start) * fps) + 0.5)
                plan.fin = math.max(plan.ini + 2, math.min(fin_frame, f))
            end
            if plan.ini then planes_emoji[#planes_emoji + 1] = plan end
        end
        end

        ::siguiente_cue::
        -- El inicio que acabamos de calcular para el siguiente pasa a ser el
        -- del bloque en curso. Asi no se recalcula (y no se puede recalcular
        -- distinto, que es como se cuelan los desajustes de un fotograma).
        -- OJO: va DESPUES de la etiqueta a proposito. Un bloque omitido
        -- tambien tiene que dejar el inicio avanzado, o el siguiente
        -- calcularia su posicion contra un bloque que no existe.
        ini_bloque = ini_siguiente
    end

    if omitidos_sin_set > 0 then
        print(string.format("  Omiti %d bloques: ningun set de tus plantillas "
            .. "tenia todos los roles que ese bloque necesitaba. No mezclo "
            .. "estilos de sets distintos.", omitidos_sin_set))
    end
    if bloques_con_veto > 0 then
        local partes = {}
        for rol, numeros in pairs(sets_sin_acentos) do
            local ns = {}
            for _, n in ipairs(numeros or {}) do ns[#ns + 1] = tostring(n) end
            partes[#partes + 1] = rol .. ": sets " .. table.concat(ns, ", ")
        end
        table.sort(partes)
        print(string.format("  Tildes: en %d bloque(s) evite los sets cuya "
            .. "tipografia no dibuja acentos (%s).", bloques_con_veto,
            table.concat(partes, "; ")))
    end
    if veto_sin_salida > 0 then
        print(string.format("  Aviso: en %d bloque(s) NINGUN set libre de "
            .. "ese veto tenia los roles necesarios; use el que habia — esa "
            .. "tilde puede salir con la fuente sustituida.", veto_sin_salida))
    end

    -- Colocar CERO no es haber colocado. Si se llega aqui sin un solo clip
    -- habiendo bloques que poner, es un fallo: que la app lo diga en vez de
    -- anunciar "ya quedaron puestos en tu timeline" con el timeline vacio.
    if colocados == 0 then
        fail(string.format(
            "no pude colocar ni una sola linea de '%s' (habia %d bloques). "
            .. "Revisa que tus plantillas Text+ sigan en el Media Pool.",
            tostring(lang), #cues))
    end

    print(string.format("  Colocadas %d lineas en %s-CTX / -MAIN / -CMP.", colocados, string.upper(lang)))
    -- La rotacion que SALIO (v2.0.2): sets usados de verdad, y si alguno
    -- repitio dos bloques seguidos por el veto o por roles que faltaban.
    local n_usados, partes_uso = 0, {}
    for v, c in pairs(uso_por_variante) do
        n_usados = n_usados + 1
        partes_uso[#partes_uso + 1] = { v, c }
    end
    if n_usados > 1 then
        table.sort(partes_uso, function(a, b) return a[1] < b[1] end)
        local textos = {}
        for _, p in ipairs(partes_uso) do
            textos[#textos + 1] = string.format("variante %d: %d bloques",
                                                p[1], p[2])
        end
        print("  Rotacion de estilo confirmada — "
              .. table.concat(textos, ", ") .. ".")
        if repetidos_seguidos > 0 then
            print(string.format("  Aviso: %d vez/veces salio el mismo set "
                .. "dos bloques seguidos (por el veto de tildes o por "
                .. "roles que faltan en el set que tocaba).",
                repetidos_seguidos))
        else
            print("  Ningun set se uso dos bloques seguidos.")
        end
    end
    if con_arial > 0 then
        print(string.format("  Tipografias: %d linea(s) salieron en Arial "
            .. "porque a este equipo le falta la del clip (instalala desde "
            .. "el programa para ver el diseño original).", con_arial))
    end
    if pack then
        if con_pack > 0 then
            print(string.format(
                "  Pack '%s': %d de %d lineas con el diseño completo.",
                tostring(pack.nombre), con_pack, colocados))
        else
            print(string.format(
                "  Aviso: el pack '%s' entro solo con sus valores (fuente, "
                .. "tamaño, color). Los degradados, formas y fondos NO. "
                .. "Motivo: %s.", tostring(pack.nombre),
                tostring(PACK_MOTIVO or "no encontre los .setting")))
        end
    end

    -- Tres finales distintos, porque son tres cosas distintas y hasta la
    -- v1.0.24 las tres se contaban como la misma (y encima la primera se daba
    -- por buena sin comprobar nada).
    if con_entrada > 0 then
        print(string.format("  Entrada con fundido en %d de %d.",
                            con_entrada, colocados))
    end
    if con_fundido > 0 then
        print(string.format("  Fundido de salida en %d de %d (via: %s).",
                            con_fundido, con_hold,
                            tostring(FADE_MOTIVO or "?")))
    elseif colocados > 0 and con_hold == 0 then
        print("  Sin fundido: ningun bloque tenia tiempo de sobra detras del habla. "
              .. "Es lo correcto, van pegados y cortan limpio.")
    elseif colocados > 0 then
        print(string.format(
            "  Aviso: no pude aplicar el fundido en %d bloques que si tenian "
            .. "sitio. Motivo: %s. Los subtitulos funcionan, solo cortan seco.",
            con_hold, tostring(FADE_MOTIVO or "desconocido")))
    end
    if sin_texto > 0 then
        print(string.format("  Aviso: %d clips quedaron sin texto (escribilos a mano).", sin_texto))
    end
    informe_transformaciones()
    informe_composicion()
    colocar_emojis(timeline, media_pool, track, planes_emoji, fps)

    -- SFX de este idioma, si el manifiesto trae libreria.
    local efectos = 0
    if track.sfx_library or track.sfx_archivos then
        efectos = place_sfx(timeline, media_pool, cues, track, fps, start_frame) or 0
    end

    -- Se devuelven los numeros para que la app pueda decir lo que DE VERDAD
    -- paso, en vez de suponerlo.
    return colocados, efectos
end

-- ---------------------------------------------------------------------
-- Modo destacados
-- ---------------------------------------------------------------------

-- Una pista de video lista para usar: la reutiliza (limpiandola de sus
-- clips previos) si ya existe y es nuestra, la crea si no. Mismo criterio
-- que el bucle de DYNAMIC_ORDER en place_dynamic -aca separado porque el
-- modo destacados no tiene un numero fijo de pistas (depende del look y, en
-- 'pintado', de cuantas palabras tenga el bloque mas largo)-.
local function conseguir_pista_video(timeline, nombre_deseado)
    local ocupada_por_el_usuario = 0
    for t = 1, timeline:GetTrackCount("video") do
        if string.upper(timeline:GetTrackName("video", t) or "") ==
                string.upper(nombre_deseado) then
            if pista_video_reutilizable(timeline, t) then
                local borrados = limpiar_pista(timeline, "video", t)
                if borrados > 0 then
                    print(string.format(
                        "  Pista existente '%s' limpiada (%d clips previos borrados).",
                        nombre_deseado, borrados))
                end
                return t, nil
            end
            ocupada_por_el_usuario = ocupada_por_el_usuario + 1
        end
    end
    if ocupada_por_el_usuario > 0 then
        print("  La pista '" .. nombre_deseado .. "' tiene contenido tuyo: " ..
              "la dejo intacta y creo una nueva encima.")
    end
    return crear_pista_verificada(timeline, "video", nombre_deseado)
end

-- Coloca un Text+ y le aplica texto + estilo. Devuelve (item, motivo): item
-- es nil si no se pudo colocar el clip; motivo no-nil si se coloco pero algo
-- fallo despues (para contarlo aparte, sin perder el clip).
local function colocar_texto(media_pool, plantilla, pista, inicio_frame,
                             fin_frame, texto, estilo, x, y)
    local duracion = math.max(1, fin_frame - inicio_frame)
    -- Sin timeline a mano no se mide: se aplica el ajuste ya aprendido.
    local item = colocar_medido(media_pool, nil, plantilla, 0, duracion,
                                pista, inicio_frame, nil, COLORES_CC.texto)
    if item == nil then
        return nil, "no pude colocar el clip"
    end
    local tool = get_text_plus(item)
    if tool == nil then
        return item, "sin Text+ dentro del clip"
    end
    if not set_input(tool, "StyledText", texto) then
        return item, "no pude escribir el texto"
    end
    aplicar_estilo(tool, estilo, y)
    if x ~= nil then set_center(tool, x, y) end
    return item, nil
end

-- Los looks de un Text+ por bloque: hormozi, gadzhi, acumulativo. A
-- diferencia del motor de 3 lineas, aca los bloques nunca se superponen en
-- el tiempo -cada uno es una sola linea-, asi que basta con UNA pista.
-- 'estilos_look' y 'ancla' (v1.0.51) llegan del Diseño dinamico cuando el
-- manifiesto los trae: el look conserva los colores/tipografia del preset
-- elegido y la altura del deslizador, en vez de las constantes de fabrica.
local function colocar_grupos(timeline, media_pool, lang, cues, look,
                              base_template, fps, start_frame, fade_frames,
                              estilos_look, ancla)
    local estilos = estilos_look or DESTACADOS_ESTILOS[look]
    local y = ancla or ANCLA_Y
    local idx, error = conseguir_pista_video(timeline, string.upper(lang) .. "-DEST")
    if error then
        fail(string.format(
            "no pude preparar la pista de '%s' de forma segura (%s). No coloque nada.",
            lang, tostring(error)))
    end

    local colocados, sin_texto, con_fundido, con_hold = 0, 0, 0, 0
    for i, cue in ipairs(cues) do
        local linea = (cue.lines and cue.lines[1]) or {}
        local texto = linea.text or ""
        if texto ~= "" then
            local rol = linea.role or "normal"
            local estilo = estilos[rol] or estilos.normal

            local inicio_frame = start_frame + math.floor(cue.start * fps + 0.5)
            local fin_frame = start_frame + math.floor(cue["end"] * fps + 0.5)
            if cues[i + 1] then
                local ini_siguiente = start_frame +
                    math.floor(cues[i + 1].start * fps + 0.5)
                if fin_frame > ini_siguiente then fin_frame = ini_siguiente end
            end
            local duracion = math.max(1, fin_frame - inicio_frame)

            local item, motivo = colocar_texto(media_pool, base_template, idx,
                inicio_frame, fin_frame, texto, estilo, 0.5, y)
            if item == nil then
                print(string.format("  Aviso: %s en %.2fs", motivo, cue.start))
            elseif motivo ~= nil then
                sin_texto = sin_texto + 1
            else
                local fin_hablado_frame = start_frame + math.floor(
                    (tonumber(cue.fin_hablado) or cue["end"]) * fps + 0.5)
                local hold = fin_frame - fin_hablado_frame
                local fade = math.min(fade_frames, math.max(0, hold), duracion - 1)
                if fade >= 1 then
                    con_hold = con_hold + 1
                    if aplicar_fade(item, fade) then
                        con_fundido = con_fundido + 1
                    end
                end
                colocados = colocados + 1
            end
        end
    end
    return colocados, sin_texto, con_fundido, con_hold
end

-- El look 'pintado': cada palabra en su propio Text+, dos veces. Una copia
-- "muda" (color tenue) cubre TODA la frase, para poder leer adelantado.
-- Encima, una copia "dicha" (blanca, o dorada si la palabra estaba marcada)
-- empieza justo cuando esa palabra se dice y dura hasta el final de la
-- frase: como ocupan el MISMO lugar, la de encima tapa a la de abajo en
-- cuanto arranca. No hace falta ningun fotograma clave -la unica tecnica que
-- se sabe que funciona en cualquier Resolve es colocar clips en el tiempo-.
--
-- Necesita DOS pistas por cada POSICION de palabra dentro de un bloque
-- (palabra 1, palabra 2...), reutilizadas entre bloques -igual que las 3
-- pistas de contexto/principal/complemento se reutilizan para todos los
-- bloques del video-.
-- 'razon_aspecto' es alto/ancho del timeline REAL. Los anchos que trae cada
-- palabra ('ancho_em') viajan como fraccion de la ALTURA -la app nunca ve la
-- resolucion del timeline, igual que nunca ve el fps-, asi que ACA es donde
-- se convierten a fraccion del ANCHO (la unidad que usa 'Center'),
-- multiplicando por esta razon.
-- Las frases se ENVUELVEN en filas (v1.0.51): con el ancho real de cada
-- palabra ya convertido, las que no caben en ANCHO_MAX_PINTADO bajan a la
-- fila siguiente, y las filas se centran verticalmente alrededor del
-- ancla. Es lo que hace al look usable en 9:16 — antes toda la frase iba
-- en una sola fila y se salia del cuadro por los dos lados.
-- 'colores' {muda, dicha, clave} (listas [r,g,b] del manifiesto) y 'ancla'
-- llegan del Diseño dinamico; sin ellos, las constantes de fabrica.
local function colocar_pintado(timeline, media_pool, lang, cues,
                               base_template, fps, start_frame,
                               estilo_pintado, fade_frames, razon_aspecto,
                               colores, ancla)
    local maximo = 0
    for _, cue in ipairs(cues) do
        local n = cue.palabras and #cue.palabras or 0
        if n > maximo then maximo = n end
    end
    maximo = math.min(maximo, MAX_PALABRAS_PINTADO)
    if maximo == 0 then return 0, 0, 0, 0 end

    local function color_de(lista, respaldo)
        if type(lista) == "table" and tonumber(lista[1]) then
            return { r = tonumber(lista[1]), g = tonumber(lista[2]) or 0,
                     b = tonumber(lista[3]) or 0 }
        end
        return respaldo
    end
    colores = colores or {}
    local color_muda = color_de(colores.muda, COLOR_PINTADO_MUDA)
    local color_dicha_normal = color_de(colores.dicha, COLOR_PINTADO_DICHA)
    local color_clave = color_de(colores.clave, COLOR_PINTADO_DICHA_CLAVE)
    local y_ancla = ancla or ANCLA_Y

    local pistas_muda, pistas_dicha = {}, {}
    for n = 1, maximo do
        local idx, error = conseguir_pista_video(
            timeline, string.format("%s-PINT%d-MUDA", string.upper(lang), n))
        if error then
            fail(string.format(
                "no pude preparar la pista de pintado de '%s' (palabra %d, muda): %s. "
                .. "No coloque nada.", lang, n, tostring(error)))
        end
        pistas_muda[n] = idx
    end
    for n = 1, maximo do
        local idx, error = conseguir_pista_video(
            timeline, string.format("%s-PINT%d-DICHA", string.upper(lang), n))
        if error then
            fail(string.format(
                "no pude preparar la pista de pintado de '%s' (palabra %d, dicha): %s. "
                .. "No coloque nada.", lang, n, tostring(error)))
        end
        pistas_dicha[n] = idx
    end

    local estilo_muda = copiar(estilo_pintado)
    estilo_muda.r, estilo_muda.g, estilo_muda.b =
        color_muda.r, color_muda.g, color_muda.b

    local colocados, sin_texto = 0, 0
    for i_cue, cue in ipairs(cues) do
        local palabras = cue.palabras or {}
        if #palabras > 0 then
            local fin_frame = start_frame + math.floor(cue["end"] * fps + 0.5)
            if cues[i_cue + 1] then
                local ini_siguiente = start_frame +
                    math.floor(cues[i_cue + 1].start * fps + 0.5)
                if fin_frame > ini_siguiente then fin_frame = ini_siguiente end
            end
            local inicio_frase = start_frame + math.floor(cue.start * fps + 0.5)

            -- Convertir 'ancho_em' (fraccion de ALTURA) a fraccion de ANCHO.
            -- Por bloque, porque cada frase tiene su propio ancho.
            local anchos_ancho = {}
            for n, palabra in ipairs(palabras) do
                anchos_ancho[n] = (tonumber(palabra.ancho_em) or 0) * razon_aspecto
            end
            local espacio_ancho = (tonumber(cue.espacio_em) or 0) * razon_aspecto

            -- Envolver en filas: las palabras que no caben bajan de fila.
            -- Una fila jamas queda vacia (la palabra que abre fila entra
            -- aunque sola ya se pase del maximo).
            local filas = {}
            local fila_actual, ancho_fila = {}, 0
            for n = 1, #palabras do
                local ancho = anchos_ancho[n]
                local extra = (#fila_actual == 0) and ancho
                    or (ancho + espacio_ancho)
                if #fila_actual > 0
                        and ancho_fila + extra > ANCHO_MAX_PINTADO then
                    filas[#filas + 1] = fila_actual
                    fila_actual, ancho_fila = { n }, ancho
                else
                    fila_actual[#fila_actual + 1] = n
                    ancho_fila = ancho_fila + extra
                end
            end
            if #fila_actual > 0 then filas[#filas + 1] = fila_actual end

            -- La posicion de cada palabra: su fila centrada en X, y las
            -- filas centradas en Y alrededor del ancla (la primera fila
            -- arriba — en Fusion la Y crece hacia ARRIBA, la trampa de
            -- siempre).
            local interlinea = (tonumber(estilo_pintado.size) or 0.07)
                * INTERLINEA_PINTADO
            local n_filas = #filas
            local x_de, y_de = {}, {}
            for i_fila, fila in ipairs(filas) do
                local ancho_total = espacio_ancho * (#fila - 1)
                for _, j in ipairs(fila) do
                    ancho_total = ancho_total + anchos_ancho[j]
                end
                local x_cursor = 0.5 - ancho_total / 2
                local y_fila = y_ancla
                    + (n_filas - 1 - 2 * (i_fila - 1)) * interlinea / 2
                for _, j in ipairs(fila) do
                    x_de[j] = x_cursor + anchos_ancho[j] / 2
                    y_de[j] = y_fila
                    x_cursor = x_cursor + anchos_ancho[j] + espacio_ancho
                end
            end

            for n, palabra in ipairs(palabras) do
                local texto = palabra.texto or ""
                local x, y = x_de[n], y_de[n]
                if texto ~= "" then
                    -- La copia "muda": desde que arranca la FRASE.
                    local item, motivo = colocar_texto(media_pool, base_template,
                        pistas_muda[n], inicio_frase, fin_frame, texto,
                        estilo_muda, x, y)
                    if item == nil then
                        print(string.format("  Aviso: %s en %.2fs ('%s')",
                            motivo, cue.start, texto))
                    elseif motivo ~= nil then
                        sin_texto = sin_texto + 1
                    else
                        colocados = colocados + 1
                    end

                    -- La copia "dicha": desde que se dice ESA palabra.
                    local inicio_palabra = start_frame + math.floor(
                        (tonumber(palabra.start) or cue.start) * fps + 0.5)
                    if inicio_palabra < inicio_frase then inicio_palabra = inicio_frase end
                    if inicio_palabra > fin_frame - 1 then inicio_palabra = fin_frame - 1 end
                    local color_dicha = palabra.resaltada
                        and color_clave or color_dicha_normal
                    local estilo_dicha = copiar(estilo_pintado)
                    estilo_dicha.r, estilo_dicha.g, estilo_dicha.b =
                        color_dicha.r, color_dicha.g, color_dicha.b

                    item, motivo = colocar_texto(media_pool, base_template,
                        pistas_dicha[n], inicio_palabra, fin_frame, texto,
                        estilo_dicha, x, y)
                    if item == nil then
                        print(string.format("  Aviso: %s en %.2fs ('%s')",
                            motivo, cue.start, texto))
                    elseif motivo ~= nil then
                        sin_texto = sin_texto + 1
                    else
                        colocados = colocados + 1
                    end
                end
            end
        end
    end
    return colocados, sin_texto, 0, 0
end

-- ---------------------------------------------------------------------
-- Pintado v3 (v1.0.53): TODOS los clips son Text+ de UNA linea colocados
-- por MEDIDAS — centro = borde izquierdo de la fila + offset medido en la
-- app (x_antes_em / ancho_em, con el MISMO estilo del texto). Cero
-- propiedades de layout de Fusion: la v1.0.52 verifico
-- HorizontalJustificationNew leyendo un 0 que resulto ser el DEFAULT
-- (centrado), y todo salio corrido — un enum no se verifica leyendo el
-- valor que ya tenia. Posicionar con numeros propios es lo unico que no
-- puede mentir. Tiene que dar lo mismo que el gemelo .py (test con lupa).
-- ---------------------------------------------------------------------

local function retirar_pistas_pintado_viejas(timeline, lang)
    -- Barre las pistas del pintado v1 (ES-PINTn-MUDA/DICHA: hasta 18 por
    -- idioma — el "demasiadas capas" del reporte). Solo pistas NUESTRAS;
    -- DeleteTrack va bajo pcall y VERIFICANDO que el conteo baje. Las
    -- pistas fijas del v3 (-PINT-BASE/BASE2/PINTA/CLAVE) que esta corrida
    -- no reuse solo se LIMPIAN. Contenido ajeno: intacto.
    local prefijo = string.upper(lang) .. "%-PINT%d+%-"
    local fijas = {}
    for _, s in ipairs({ "BASE", "BASE2", "PINTA", "CLAVE" }) do
        fijas[string.upper(lang) .. "-PINT-" .. s] = true
    end
    local borradas, vaciadas, ajenas = 0, 0, 0
    for idx = timeline:GetTrackCount("video"), 1, -1 do
        local nombre = ""
        pcall(function()
            nombre = (timeline:GetTrackName("video", idx) or "")
        end)
        nombre = nombre:gsub("^%s+", ""):gsub("%s+$", ""):upper()
        if fijas[nombre] then
            if pista_video_reutilizable(timeline, idx) then
                limpiar_pista(timeline, "video", idx)
            end
        else
            local resto = nombre:match("^" .. prefijo .. "(%u+)$")
            if resto == "MUDA" or resto == "DICHA" then
                if not pista_video_reutilizable(timeline, idx) then
                    ajenas = ajenas + 1
                else
                    limpiar_pista(timeline, "video", idx)
                    local antes = timeline:GetTrackCount("video")
                    local ok = false
                    pcall(function()
                        ok = timeline:DeleteTrack("video", idx)
                            and true or false
                    end)
                    if ok and timeline:GetTrackCount("video") < antes then
                        borradas = borradas + 1
                    else
                        vaciadas = vaciadas + 1
                    end
                end
            end
        end
    end
    if borradas + vaciadas + ajenas > 0 then
        local partes = {}
        if borradas > 0 then
            partes[#partes + 1] = borradas .. " borradas"
        end
        if vaciadas > 0 then
            partes[#partes + 1] = vaciadas .. " vaciadas (este Resolve no "
                .. "borra pistas por script)"
        end
        if ajenas > 0 then
            partes[#partes + 1] = ajenas .. " con contenido tuyo, intactas"
        end
        print("  Pistas del pintado anterior: "
              .. table.concat(partes, ", ") .. ".")
    end
end

local function colocar_pintado_v2(timeline, media_pool, lang, cues,
                                  base_template, fps, start_frame, cfg,
                                  razon_aspecto, ancla)
    -- El pintado v3: capas de UNA linea, posicionadas por medidas.
    -- 'acumula' (Hormozi, 1 fila): BASE tenue centrada + PINTA (el
    -- prefijo dicho, borde izquierdo clavado en el de la base) + CLAVE
    -- (la marcada, dorada, persistente). 'viaja' (Gadzhi, 2 filas): BASE
    -- y BASE2 centradas visibles + la palabra actual en Bold sobre su
    -- gemela (la resaltada con el color de main). Las Y son nuestras:
    -- ancla +- interlinea/2, interlinea = size * INTERLINEA_PINTADO.
    local estilo_base = estilo_del_manifiesto(cfg.estilo_base or {})
    local estilo_dicha = cfg.estilo_dicha
        and estilo_del_manifiesto(cfg.estilo_dicha) or estilo_base
    local estilo_clave = cfg.estilo_clave
        and estilo_del_manifiesto(cfg.estilo_clave) or estilo_dicha
    local modo = (cfg.modo == "viaja") and "viaja" or "acumula"
    local y_ancla = ancla or ANCLA_Y
    local interlinea = (tonumber(estilo_base.size) or 0.06)
        * INTERLINEA_PINTADO

    retirar_pistas_pintado_viejas(timeline, lang)

    local max_filas = 1
    local hay_clave = false
    for _, c in ipairs(cues) do
        local n = c.filas_texto and #c.filas_texto or 0
        if n > max_filas then max_filas = n end
        if modo == "acumula" then
            for _, p in ipairs(c.palabras or {}) do
                if p.resaltada then hay_clave = true end
            end
        end
    end

    local idx_base, err1 = conseguir_pista_video(
        timeline, string.upper(lang) .. "-PINT-BASE")
    if err1 then
        fail(string.format("no pude preparar la pista base del pintado de "
            .. "'%s' (%s). No coloque nada.", lang, tostring(err1)))
    end
    local idx_base2 = nil
    if max_filas >= 2 then
        local err_b2
        idx_base2, err_b2 = conseguir_pista_video(
            timeline, string.upper(lang) .. "-PINT-BASE2")
        if err_b2 then
            fail(string.format("no pude preparar la segunda fila del "
                .. "pintado de '%s' (%s). No coloque nada.",
                lang, tostring(err_b2)))
        end
    end
    local idx_pinta, err2 = conseguir_pista_video(
        timeline, string.upper(lang) .. "-PINT-PINTA")
    if err2 then
        fail(string.format("no pude preparar la pista de pintado de '%s' "
            .. "(%s). No coloque nada.", lang, tostring(err2)))
    end
    local idx_clave = nil
    if hay_clave then
        local err3
        idx_clave, err3 = conseguir_pista_video(
            timeline, string.upper(lang) .. "-PINT-CLAVE")
        if err3 then
            fail(string.format("no pude preparar la pista de claves de "
                .. "'%s' (%s). No coloque nada.", lang, tostring(err3)))
        end
    end

    local colocados, sin_texto = 0, 0
    local aviso_filas = false
    for i_cue, cue in ipairs(cues) do
        local palabras = cue.palabras or {}
        local filas_texto = cue.filas_texto or {}
        if #palabras > 0 and #filas_texto > 0 then
            if #filas_texto > 2 then
                -- Solo hay dos pistas de base: un manifiesto raro con mas
                -- filas se acota (el armador de la app ya no las produce).
                if not aviso_filas then
                    print("  Aviso: un bloque pintado trae mas de 2 "
                          .. "filas; coloco solo las dos primeras.")
                    aviso_filas = true
                end
                filas_texto = { filas_texto[1], filas_texto[2] }
            end
            local n_filas = #filas_texto
            local anchos_filas, izq, y_fila = {}, {}, {}
            for r = 1, n_filas do
                anchos_filas[r] = tonumber(
                    (cue.ancho_filas_em or {})[r]) or 0
                izq[r] = 0.5 - (anchos_filas[r] * razon_aspecto) / 2.0
                y_fila[r] = y_ancla
                    + (n_filas - 1 - 2 * (r - 1)) * interlinea / 2.0
            end

            local ini_frase = start_frame
                + math.floor(cue.start * fps + 0.5)
            local fin_frame = start_frame
                + math.floor(cue["end"] * fps + 0.5)
            if cues[i_cue + 1] then
                local ini_sig = start_frame
                    + math.floor(cues[i_cue + 1].start * fps + 0.5)
                if fin_frame > ini_sig then fin_frame = ini_sig end
            end
            if fin_frame <= ini_frase then fin_frame = ini_frase + 1 end

            -- LAS BASES: un clip de una linea por fila, centrado.
            local pistas_base = { idx_base, idx_base2 }
            for r = 1, n_filas do
                local item, motivo = colocar_texto(
                    media_pool, base_template, pistas_base[r], ini_frase,
                    fin_frame, filas_texto[r], estilo_base, 0.5, y_fila[r])
                if item == nil then
                    print(string.format("  Aviso: %s en %.2fs (base)",
                        tostring(motivo), cue.start))
                elseif motivo ~= nil then
                    sin_texto = sin_texto + 1
                else
                    colocados = colocados + 1
                end
            end

            -- LA PINTA: un clip por palabra, consecutivos (sin solapes).
            for k, p in ipairs(palabras) do
                local texto_p = (p.texto or ""):gsub("^%s+", "")
                    :gsub("%s+$", "")
                if texto_p ~= "" then
                    local fila = math.floor(tonumber(p.fila) or 0)
                    if fila > n_filas - 1 then fila = n_filas - 1 end
                    local ini_p = start_frame + math.floor(
                        (tonumber(p.start) or cue.start) * fps + 0.5)
                    if ini_p < ini_frase then ini_p = ini_frase end
                    if ini_p > fin_frame - 1 then ini_p = fin_frame - 1 end
                    local fin_p
                    if palabras[k + 1] then
                        fin_p = start_frame + math.floor(
                            (tonumber(palabras[k + 1].start)
                             or cue["end"]) * fps + 0.5)
                        if fin_p > fin_frame then fin_p = fin_frame end
                        if fin_p <= ini_p then fin_p = ini_p + 1 end
                    else
                        fin_p = fin_frame
                    end
                    local x_antes = tonumber(p.x_antes_em) or 0
                    local ancho = tonumber(p.ancho_em) or 0
                    local texto_clip, x_clip, estilo_p
                    if modo == "acumula" then
                        -- El prefijo dicho de SU fila: borde izquierdo
                        -- clavado en el de la base, centro = izq + mitad
                        -- del ancho MEDIDO del prefijo.
                        local partes = {}
                        for i = 1, k do
                            local f_i = math.floor(
                                tonumber(palabras[i].fila) or 0)
                            if f_i > n_filas - 1 then f_i = n_filas - 1 end
                            if f_i == fila then
                                partes[#partes + 1] =
                                    (palabras[i].texto or "")
                                    :gsub("^%s+", ""):gsub("%s+$", "")
                            end
                        end
                        texto_clip = table.concat(partes, " ")
                        x_clip = izq[fila + 1]
                            + ((x_antes + ancho) * razon_aspecto) / 2.0
                        estilo_p = estilo_dicha
                    else
                        texto_clip = texto_p
                        x_clip = izq[fila + 1]
                            + (x_antes + ancho / 2.0) * razon_aspecto
                        estilo_p = p.resaltada and estilo_clave
                            or estilo_dicha
                    end
                    local item, motivo = colocar_texto(
                        media_pool, base_template, idx_pinta, ini_p,
                        fin_p, texto_clip, estilo_p, x_clip,
                        y_fila[fila + 1])
                    if item == nil then
                        print(string.format(
                            "  Aviso: %s en %.2fs ('%s')",
                            tostring(motivo), cue.start, texto_p))
                    elseif motivo ~= nil then
                        sin_texto = sin_texto + 1
                    else
                        colocados = colocados + 1
                    end
                end
            end

            -- LA CLAVE (solo 'acumula'): la marcada, dorada, en su sitio
            -- exacto hasta el fin de la frase; una clave posterior
            -- recorta a la anterior (una sola pista, sin solapes).
            if modo == "acumula" and idx_clave ~= nil then
                local claves = {}
                for _, p in ipairs(palabras) do
                    if p.resaltada then claves[#claves + 1] = p end
                end
                for j, p in ipairs(claves) do
                    local texto_p = (p.texto or ""):gsub("^%s+", "")
                        :gsub("%s+$", "")
                    if texto_p ~= "" then
                        local fila = math.floor(tonumber(p.fila) or 0)
                        if fila > n_filas - 1 then fila = n_filas - 1 end
                        local ini_c = start_frame + math.floor(
                            (tonumber(p.start) or cue.start) * fps + 0.5)
                        if ini_c < ini_frase then ini_c = ini_frase end
                        if ini_c > fin_frame - 1 then
                            ini_c = fin_frame - 1
                        end
                        local fin_c
                        if claves[j + 1] then
                            fin_c = start_frame + math.floor(
                                (tonumber(claves[j + 1].start)
                                 or cue["end"]) * fps + 0.5)
                            if fin_c > fin_frame then fin_c = fin_frame end
                            if fin_c <= ini_c then fin_c = ini_c + 1 end
                        else
                            fin_c = fin_frame
                        end
                        local x_c = izq[fila + 1]
                            + ((tonumber(p.x_antes_em) or 0)
                               + (tonumber(p.ancho_em) or 0) / 2.0)
                            * razon_aspecto
                        local item, motivo = colocar_texto(
                            media_pool, base_template, idx_clave, ini_c,
                            fin_c, texto_p, estilo_clave, x_c,
                            y_fila[fila + 1])
                        if item == nil then
                            print(string.format(
                                "  Aviso: %s en %.2fs ('%s')",
                                tostring(motivo), cue.start, texto_p))
                        elseif motivo ~= nil then
                            sin_texto = sin_texto + 1
                        else
                            colocados = colocados + 1
                        end
                    end
                end
            end
        end
    end
    return colocados, sin_texto, 0, 0
end

-- v5.9 — estilo «guion» (gemela de place_guion_track de CineCaptions.py):
-- cada PALABRA (o tramo de palabras) es su propio clip, con su estilo, su
-- posicion y su momento. El archivo de datos trae bloques
-- {start, end, estilo, runs: [{rol, texto, t, fin, x, y, estilo, zoom, salto}]}
-- que el planificador de la app (guion_captions / guion_planificador) ya armo:
--   rol 'main' -> clip «principal» del set (variante) de la palabra o del bloque
--   rol 'context' -> «arriba» (linea pequeña FINA); 'complement' -> «abajo» (NEGRITA)
-- x, y = centro de la palabra en fraccion del cuadro (y desde ARRIBA). Cada
-- palabra va en la primera pista libre («ES-T1», «ES-T2»…).
local function place_guion(timeline, media_pool, track, fps, start_frame, project)
    local lang = track.language
    local L = string.upper(tostring(lang))
    local data_path = track.data_path
    if not data_path or not dato_existe(data_path) then
        print("  Aviso: no encuentro el .json de '" .. tostring(lang) .. "', lo salto.")
        return 0, 0
    end
    local datos = cargar_tabla(data_path) or {}
    local cues = datos.cues or {}
    if #cues == 0 then
        print("  Aviso: '" .. tostring(lang) .. "' no tiene bloques.")
        return 0, 0
    end

    local function res_tl(clave, por_defecto)
        local ok, v = pcall(function() return timeline:GetSetting(clave) end)
        if ok and v and tonumber(v) then return math.floor(tonumber(v)) end
        return por_defecto
    end
    local ancho_tl = res_tl("timelineResolutionWidth", 1080)
    local alto_tl = res_tl("timelineResolutionHeight", 1920)

    local carpeta_pack_drt = nil
    local pack_previo = nil
    if type(track.plantilla) == "table" then
        print("  El manifiesto pide el pack '" .. tostring(track.plantilla.pack or "?")
              .. "' (estilo guion).")
    end
    if type(track.plantilla) == "table" and project then
        pack_previo = pack_del_manifiesto(track, ancho_tl, alto_tl)
        if pack_previo and (pack_previo.drt or pack_previo.drb) then
            local ok_prep, carpeta_o_err, aviso_drt = pcall(
                preparar_pack_drt, project, media_pool, pack_previo.nombre,
                pack_previo.formato, pack_previo.drt, pack_previo.drb)
            if ok_prep then
                carpeta_pack_drt = carpeta_o_err
            else
                carpeta_pack_drt = nil
                aviso_drt = "fallo preparando el pack (" .. tostring(carpeta_o_err) .. ")."
            end
            if aviso_drt then
                print("  Aviso (pack '" .. tostring(pack_previo.nombre) .. "'): " .. tostring(aviso_drt))
            end
        end
    end
    local sets, informe_sets = buscar_sets_de_plantillas(media_pool, carpeta_pack_drt)
    if #sets == 0 then
        fail("el estilo «guion» necesita un pack con sets (principal / arriba / abajo) y no encontre "
             .. "ninguno para '" .. tostring(lang) .. "'. Elige un pack de estilos (por ejemplo «Referencia»).")
    end
    print(string.format("\nIdioma '%s': %d bloques (estilo guion), %d sets en el pack.", lang, #cues, #sets))
    for _, linea in ipairs(informe_sets) do print(linea) end

    -- fuera lo de otras corridas (dinamico / normal) y lo propio de la anterior
    do
        local nombres_g = { L .. "-CTX", L .. "-MAIN", L .. "-CMP", L, L .. "-EMOJI" }
        for k = 1, 24 do nombres_g[#nombres_g + 1] = string.format("%s-K%d", L, k) end
        retirar_pistas_nuestras(timeline, nombres_g, "subtitulos", "esta corrida es de estilo guion")
    end

    -- PISTAS. Las palabras GRANDES van en las pistas de abajo y las pequeñas
    -- encima: el macro «Luxe Shine» es de cristal y refracta lo que tiene
    -- debajo (con la linea pequeña en una pista inferior se le colaba dentro
    -- de las letras, volteada). Primero se reparte cada palabra en su hueco
    -- (el primero libre de su grupo), luego se crean en orden «ES-T1…» (las
    -- grandes primero) y por ultimo se coloca.
    local function a_fotogramas(segundos) return math.floor(segundos * fps + 0.5) end
    local function recortar(s) return (tostring(s or ""):gsub("^%s*(.-)%s*$", "%1")) end

    local colocados, sin_texto, sin_pista = 0, 0, 0
    -- la salida del macro (un fundido de ~6 fotogramas) empieza ANTES del fin del clip: se alarga un poco
    local extra_fin = tonumber(track.extra_fin_s) or 0.04
    local min_frames = a_fotogramas(0.3)
    local pendientes = {}
    for _, cue in ipairs(cues) do
        local estilo_cue = cue.estilo
        for _, run in ipairs(cue.runs or {}) do
            local texto = recortar(run.texto)
            if texto ~= "" then
                local rol = run.rol
                if rol ~= "main" and rol ~= "context" and rol ~= "complement" then rol = "context" end
                local n_estilo = run.estilo or estilo_cue
                local juego = nil
                if n_estilo then
                    for _, s in ipairs(sets) do
                        if s.numero == n_estilo then juego = s; break end
                    end
                end
                if juego == nil then
                    for _, s in ipairs(sets) do
                        if s[rol] then juego = s; break end
                    end
                    juego = juego or sets[1]
                end
                local plantilla = juego[rol] or juego.main
                if not plantilla then
                    sin_pista = sin_pista + 1
                else
                    local t_run = tonumber(run.t) or cue.start
                    local ini = math.max(start_frame, start_frame + a_fotogramas(t_run))
                    local fin_s = tonumber(run.fin) or cue["end"]
                    local fin = start_frame + a_fotogramas(fin_s + extra_fin)
                    fin = math.max(fin, ini + min_frames)
                    pendientes[#pendientes + 1] = { run = run, texto = texto, rol = rol, juego = juego,
                                                    plantilla = plantilla, ini = ini, fin = fin,
                                                    orden = #pendientes + 1 }
                end
            end
        end
    end
    table.sort(pendientes, function(a, b)
        if a.ini ~= b.ini then return a.ini < b.ini end
        local ra, rb = (a.rol == "main" and 0 or 1), (b.rol == "main" and 0 or 1)
        if ra ~= rb then return ra < rb end
        return a.orden < b.orden
    end)
    local huecos = { main = {}, peq = {} }      -- fotograma desde el que esta libre cada hueco de cada grupo
    for _, d in ipairs(pendientes) do
        local lista = (d.rol == "main") and huecos.main or huecos.peq
        local puesto_en = nil
        for k, libre in ipairs(lista) do
            if libre <= d.ini then puesto_en = k; break end
        end
        if puesto_en == nil then
            puesto_en = #lista + 1
        end
        lista[puesto_en] = d.fin
        d.hueco = puesto_en
    end
    local n_main = #huecos.main
    for _, d in ipairs(pendientes) do
        d.n = (d.rol == "main") and d.hueco or (n_main + d.hueco)
    end
    local total_pistas = n_main + #huecos.peq
    local idx_pista = {}
    for n = 1, total_pistas do
        local nombre = string.format("%s-T%d", L, n)
        local idx, err = conseguir_pista_video(timeline, nombre)
        if err or not idx then
            print("  ERROR: no pude crear la pista '" .. nombre .. "' de forma segura (" .. tostring(err) .. ").")
        else
            idx_pista[n] = idx
        end
    end
    local pistas = {}
    for n = 1, total_pistas do pistas[n] = n end
    for _, d in ipairs(pendientes) do
        local run, texto, rol, juego, plantilla = d.run, d.texto, d.rol, d.juego, d.plantilla
        local ini, fin = d.ini, d.fin
        local idx = idx_pista[d.n]
        if idx == nil then
            sin_pista = sin_pista + 1
        else
            local salto = tonumber(run.salto)
            if salto == nil then
                salto = tonumber(rol == "main" and track.salto_principal_s or track.salto_pequena_s) or 0
            end
            local desfase = math.max(0, a_fotogramas(salto))
            local item = colocar_medido(media_pool, timeline, plantilla, desfase,
                                        fin - ini, idx, ini, fps, COLORES_CC.texto)
            if item == nil and desfase > 0 then
                item = colocar_medido(media_pool, timeline, plantilla, 0,
                                      fin - ini, idx, ini, fps, COLORES_CC.texto)
            end
            if item == nil then
                print("  Aviso: no pude colocar «" .. texto .. "» en " .. tostring(run.t) .. "s")
            else
                local tool = get_text_plus(item)
                if tool == nil or not set_input(tool, "StyledText", texto) then
                    sin_texto = sin_texto + 1
                else
                    local props = {}
                    if type(run.x) == "number" then props.Pan = pan_px(run.x - 0.5, ancho_tl) end
                    if type(run.y) == "number" then props.Tilt = tilt_px(0.5 - run.y, alto_tl) end
                    if type(run.zoom) == "number" and run.zoom > 0 then
                        props.ZoomX = run.zoom
                        props.ZoomY = run.zoom
                    end
                    if next(props) ~= nil then poner_props(item, props) end
                    if rol == "main" then ajustar_barrido(item, (fin - ini) / fps, salto, run.ancho_rel) end
                    colocados = colocados + 1
                end
            end
        end
    end
    -- v5.10 — SONIDOS y EMOJIS (gemela de place_guion_track de CineCaptions.py): el sonido de cada palabra cae donde entra; el emoji entra con
    -- la palabra grande del bloque (cue.emoji_ini) y se queda hasta que se va la pila, encima o debajo de su caja (cue.caja, fraccion del alto
    -- desde ARRIBA) segun emoji_posicion.
    if track.sfx_library or track.sfx_archivos then
        place_sfx(timeline, media_pool, cues, track, fps, start_frame)
    end
    local planes_emoji = {}
    for _, cue in ipairs(cues) do
        if cue.emoji then
            local arriba_y, abajo_y = nil, nil
            local caja = cue.caja
            if type(caja) == "table" and tonumber(caja[1]) and tonumber(caja[2]) then
                arriba_y, abajo_y = 0.5 - tonumber(caja[1]), 0.5 - tonumber(caja[2])
            else
                local ymin, ymax = nil, nil
                for _, r in ipairs(cue.runs or {}) do
                    if type(r.y) == "number" then
                        ymin = (ymin == nil) and r.y or math.min(ymin, r.y)
                        ymax = (ymax == nil) and r.y or math.max(ymax, r.y)
                    end
                end
                if ymin ~= nil then arriba_y, abajo_y = 0.5 - ymin, 0.5 - ymax end
            end
            if arriba_y ~= nil then
                local ini_p = math.max(start_frame, start_frame + a_fotogramas(tonumber(cue.emoji_ini) or cue.start))
                local fin_p = start_frame + a_fotogramas(cue["end"] + extra_fin)
                if fin_p > ini_p + 1 then
                    planes_emoji[#planes_emoji + 1] = { emoji = cue.emoji, ini = ini_p, fin = fin_p, y_arriba = arriba_y, y_abajo = abajo_y }
                end
            end
        end
    end
    local ok_em, err_em = pcall(colocar_emojis, timeline, media_pool, track, planes_emoji, fps)
    if not ok_em then
        print("  Aviso: no pude colocar los emojis del estilo guion (" .. tostring(err_em) .. ").")
    end
    -- pistas de corridas anteriores que ya no hacen falta
    local sobran = {}
    for k = #pistas + 1, #pistas + 24 do sobran[#sobran + 1] = string.format("%s-T%d", L, k) end
    retirar_pistas_nuestras(timeline, sobran, "palabras", "esta corrida necesita menos pistas")
    print(string.format("  Colocadas %d palabras en %d pista(s) (%s-T1…%s-T%d).",
                        colocados, #pistas, L, L, #pistas))
    if sin_texto > 0 then
        print(string.format("  Aviso: %d palabra(s) se colocaron pero no pude escribir su texto.", sin_texto))
    end
    if sin_pista > 0 then
        print(string.format("  Aviso: %d palabra(s) no se colocaron (sin pista o sin clip para ese rol).", sin_pista))
    end
    return colocados, 0
end

-- v5.4 — estilo «Kinetic» (gemela de place_kinetic_track de CineCaptions.py): titulos de gancho. Cada ELEMENTO de la pila (heroe, linea pequeña,
-- serif, pincel, cinta, anillo, subrayado) es su propio clip del pack «Kinetic», con su posicion, su tamaño, su giro y su momento. El archivo de
-- datos trae bloques {start, end, runs: [{k, texto, t, x, y, size, rot, zx, zy}]} que ya armo la app (kinetic_planificador / kinetic_captions):
-- `k` = clip del pack («k hero lima»); `texto` y `size` van al Text+ «Template» del clip; x/y = centro en fraccion del cuadro (y desde ARRIBA);
-- `rot` = giro en grados; zx/zy = zoom de los trazos. Cada elemento va en la primera pista libre de su capa («ES-K1»…).
local KINETIC_CLIP_PRUEBA = "k hero blanco"

local function preparar_pack_kinetic(media_pool, nombre_pack, formato, ruta_drb, clip_prueba)
    clip_prueba = clip_prueba or KINETIC_CLIP_PRUEBA            -- el clip que prueba que el bin del pack esta completo (el pack «VIRAL» trae otros: v fina…)
    local nombre_bin = nombre_bin_pack(nombre_pack, formato)
    local raiz_ok, raiz = pcall(function() return media_pool:GetRootFolder() end)
    if not raiz_ok or not raiz then return nil, "no pude leer el Media Pool." end
    local existente = subcarpeta(raiz, nombre_bin)
    if existente and find_clip_by_name(media_pool, clip_prueba, existente) then return existente, nil end
    -- v5.4.16: archivo_existe, no dato_existe (que mira el sidecar .lua de un .json): un .drb es binario y NO tiene sidecar, asi que en el menu de Free 21.1 (sin io) siempre «faltaba»
    if not ruta_drb or not archivo_existe(ruta_drb) then
        return nil, "el pack '" .. tostring(nombre_pack) .. "' no trae su .drb en este equipo (" .. tostring(ruta_drb or "sin ruta") .. ")."
    end
    -- Resolve a veces devuelve nil justo despues de crear el proyecto o el timeline: se reintenta, y antes de rendirse se mira si el bin se creo igual
    local carpeta = existente
    local ultimo_error = nil
    for _ = 1, 5 do
        if carpeta then break end
        local ok_c, nueva = pcall(function() return media_pool:AddSubFolder(media_pool:GetRootFolder(), nombre_bin) end)
        if ok_c then carpeta = nueva or nil else ultimo_error = nueva end
        if not carpeta then
            local ok_r, raiz2 = pcall(function() return media_pool:GetRootFolder() end)
            if ok_r and raiz2 then carpeta = subcarpeta(raiz2, nombre_bin) end
        end
        if not carpeta and os and os.execute then pcall(os.execute, "ping -n 2 127.0.0.1 > nul") end
    end
    if not carpeta then
        return nil, "no pude crear el bin '" .. nombre_bin .. "' en el Media Pool" .. (ultimo_error and (" (" .. tostring(ultimo_error) .. ").") or " (Resolve no devolvio la carpeta).")
    end
    local ok_p, previa = pcall(function() return media_pool:GetCurrentFolder() end)
    pcall(function() media_pool:SetCurrentFolder(carpeta) end)
    local importo = false
    local ok_i, res_i = pcall(function() return media_pool:ImportFolderFromFile(ruta_drb) end)
    if ok_i then
        importo = res_i and true or false
    else
        print("  ImportFolderFromFile no esta en este Resolve (" .. tostring(res_i) .. ").")
    end
    if ok_p and previa then pcall(function() media_pool:SetCurrentFolder(previa) end) end
    if importo and find_clip_by_name(media_pool, clip_prueba, carpeta) then
        print("  El bin del pack '" .. tostring(nombre_pack) .. "' entro DIRECTO al Media Pool (desde el .drb).")
        return carpeta, nil
    end
    return nil, "importe el .drb del pack '" .. tostring(nombre_pack) .. "' pero no encuentro sus clips («" .. clip_prueba .. "»…)."
end

-- capa del elemento: de la de abajo (heroe) a la de arriba (lineas pequeñas); cada capa tiene sus propias pistas
local function grupo_kinetic(nombre)
    local n = string.lower(tostring(nombre))
    if n:sub(1, 2) == "v " then return (n == "v fina") and 1 or 0 end          -- pack «VIRAL»: palabras con efecto abajo, lineas finas aparte
    if n:sub(1, 6) == "k hero" then return 0 end
    if n:sub(1, 6) == "k line" then return 1 end
    if n:sub(1, 6) == "k ring" then return 3 end
    if n:sub(1, 5) == "k sup" or n:sub(1, 7) == "k label" then return 4 end
    return 2          -- cintas, serif, pincel
end

local function place_kinetic(timeline, media_pool, track, fps, start_frame, project)
    local lang = track.language
    local L = string.upper(tostring(lang))
    local data_path = track.data_path
    if not data_path or not dato_existe(data_path) then
        print("  Aviso: no encuentro el .json de '" .. tostring(lang) .. "', lo salto.")
        return 0, 0
    end
    local datos = cargar_tabla(data_path) or {}
    local cues = datos.cues or {}
    if #cues == 0 then
        print("  Aviso: '" .. tostring(lang) .. "' no tiene bloques.")
        return 0, 0
    end
    if track.sfx_library or track.sfx_archivos then
        place_sfx(timeline, media_pool, cues, track, fps, start_frame)
    end

    local function res_tl(clave, por_defecto)
        local ok, v = pcall(function() return timeline:GetSetting(clave) end)
        if ok and v and tonumber(v) then return math.floor(tonumber(v)) end
        return por_defecto
    end
    local ancho_tl = res_tl("timelineResolutionWidth", 1080)
    local alto_tl = res_tl("timelineResolutionHeight", 1920)

    local pack_previo = nil
    if type(track.plantilla) == "table" then pack_previo = pack_del_manifiesto(track, ancho_tl, alto_tl) end
    if not pack_previo or not pack_previo.drb then
        fail("el estilo «Kinetic» necesita su pack (.drb) y el manifiesto no lo trae. Elige el pack «Kinetic» en Estilos.")
    end
    local carpeta, aviso = preparar_pack_kinetic(media_pool, pack_previo.nombre, pack_previo.formato, pack_previo.drb, track.clip_prueba)
    if not carpeta then fail("no pude preparar el pack «" .. tostring(pack_previo.nombre) .. "»: " .. tostring(aviso)) end
    local clips = {}
    local function clip_de(nombre)
        if clips[nombre] == nil then clips[nombre] = find_clip_by_name(media_pool, nombre, carpeta) or false end
        return clips[nombre] or nil
    end
    print(string.format("\nIdioma '%s': %d bloques (estilo Kinetic).", lang, #cues))

    local nombres_previos = { L .. "-CTX", L .. "-MAIN", L .. "-CMP", L, L .. "-EMOJI" }
    for k = 1, 24 do nombres_previos[#nombres_previos + 1] = string.format("%s-T%d", L, k) end
    retirar_pistas_nuestras(timeline, nombres_previos, "subtitulos", "esta corrida es de estilo Kinetic")

    local function a_fotogramas(segundos) return math.floor(segundos * fps + 0.5) end
    local extra_fin = tonumber(track.extra_fin_s) or 0.05
    local min_frames = a_fotogramas(0.45)       -- la entrada (8 fotogramas) y la salida (5) del comp necesitan ~13 fotogramas para verse enteras
    local pendientes, sin_clip = {}, {}
    for _, cue in ipairs(cues) do
        for _, run in ipairs(cue.runs or {}) do
            local nombre = run.k
            local plantilla = nombre and clip_de(nombre) or nil
            if plantilla == nil then
                if nombre then sin_clip[nombre] = true end
            else
                local ini = math.max(start_frame, start_frame + a_fotogramas(tonumber(run.t) or cue.start))
                local fin_s = tonumber(run.fin) or cue["end"]
                local fin = start_frame + a_fotogramas(fin_s + extra_fin)
                fin = math.max(fin, ini + min_frames)
                pendientes[#pendientes + 1] = { run = run, nombre = nombre, plantilla = plantilla, ini = ini, fin = fin,
                                                grupo = grupo_kinetic(nombre), orden = #pendientes + 1 }
            end
        end
    end
    table.sort(pendientes, function(a, b)
        if a.grupo ~= b.grupo then return a.grupo < b.grupo end
        if a.ini ~= b.ini then return a.ini < b.ini end
        return a.orden < b.orden
    end)
    local huecos = {}          -- capa -> { fotograma desde el que esta libre cada hueco }
    for _, d in ipairs(pendientes) do
        huecos[d.grupo] = huecos[d.grupo] or {}
        local lista = huecos[d.grupo]
        local puesto_en = nil
        for k, libre in ipairs(lista) do
            if libre <= d.ini then puesto_en = k; break end
        end
        puesto_en = puesto_en or (#lista + 1)
        lista[puesto_en] = d.fin
        d.hueco = puesto_en
    end
    local grupos = {}
    for g in pairs(huecos) do grupos[#grupos + 1] = g end
    table.sort(grupos)
    local orden, n_pista = {}, 0
    for _, g in ipairs(grupos) do
        for k = 1, #huecos[g] do
            n_pista = n_pista + 1
            orden[g .. ":" .. k] = n_pista
        end
    end
    local idx_pista = {}
    for n = 1, n_pista do
        local nombre = string.format("%s-K%d", L, n)
        local idx, err = conseguir_pista_video(timeline, nombre)
        if err or not idx then
            print("  ERROR: no pude crear la pista '" .. nombre .. "' de forma segura (" .. tostring(err) .. ").")
        else
            idx_pista[n] = idx
        end
    end
    local colocados, sin_pista, sin_texto = 0, 0, 0
    for _, d in ipairs(pendientes) do
        local run = d.run
        local idx = idx_pista[orden[d.grupo .. ":" .. d.hueco]]
        if idx == nil then
            sin_pista = sin_pista + 1
        else
            local item = colocar_medido(media_pool, timeline, d.plantilla, 0, d.fin - d.ini, idx, d.ini, fps, COLORES_CC.texto)
            if item == nil then
                print("  Aviso: no pude colocar «" .. tostring(run.texto or d.nombre) .. "» en " .. tostring(run.t) .. "s")
            else
                local ok_texto = true
                if run.texto ~= nil then
                    local tool = get_text_plus(item)
                    if tool == nil or not set_input(tool, "StyledText", tostring(run.texto)) then
                        ok_texto = false
                        sin_texto = sin_texto + 1
                    elseif type(run.size) == "number" then
                        set_input(tool, "Size", run.size)
                    end
                end
                if ok_texto then
                    local props = {}
                    if type(run.x) == "number" then props.Pan = pan_px(run.x - 0.5, ancho_tl) end
                    if type(run.y) == "number" then props.Tilt = tilt_px(0.5 - run.y, alto_tl) end
                    if type(run.rot) == "number" and math.abs(run.rot) > 0.01 then props.RotationAngle = run.rot end
                    if type(run.zx) == "number" and run.zx > 0 then props.ZoomX = run.zx end
                    if type(run.zy) == "number" and run.zy > 0 then props.ZoomY = run.zy end
                    if next(props) ~= nil then poner_props(item, props) end
                    colocados = colocados + 1
                end
            end
        end
    end
    -- v5.5 — EMOJIS (los manda el estilo VIRAL; Kinetic no): gemela del bloque de place_kinetic_track de CineCaptions.py. Sin cue.emoji no se hace nada.
    local planes_emoji = {}
    for _, cue in ipairs(cues) do
        if cue.emoji then
            local arriba_y, abajo_y = nil, nil
            local caja = cue.caja
            if type(caja) == "table" and tonumber(caja[1]) and tonumber(caja[2]) then
                arriba_y, abajo_y = 0.5 - tonumber(caja[1]), 0.5 - tonumber(caja[2])
            else
                local ymin, ymax = nil, nil
                for _, r in ipairs(cue.runs or {}) do
                    if type(r.y) == "number" then
                        ymin = (ymin == nil) and r.y or math.min(ymin, r.y)
                        ymax = (ymax == nil) and r.y or math.max(ymax, r.y)
                    end
                end
                if ymin ~= nil then arriba_y, abajo_y = 0.5 - ymin, 0.5 - ymax end
            end
            if arriba_y ~= nil then
                local ini_p = math.max(start_frame, start_frame + a_fotogramas(tonumber(cue.emoji_ini) or cue.start))
                local fin_p = start_frame + a_fotogramas(cue["end"] + extra_fin)
                if fin_p > ini_p + 1 then
                    planes_emoji[#planes_emoji + 1] = { emoji = cue.emoji, ini = ini_p, fin = fin_p, y_arriba = arriba_y, y_abajo = abajo_y }
                end
            end
        end
    end
    if #planes_emoji > 0 then
        local ok_em, err_em = pcall(colocar_emojis, timeline, media_pool, track, planes_emoji, fps)
        if not ok_em then print("  Aviso: no pude colocar los emojis (" .. tostring(err_em) .. ").") end
    end
    local sobran = {}
    for k = n_pista + 1, n_pista + 24 do sobran[#sobran + 1] = string.format("%s-K%d", L, k) end
    retirar_pistas_nuestras(timeline, sobran, "elementos", "esta corrida necesita menos pistas")
    print(string.format("  Colocados %d elementos en %d pista(s) (%s-K1…%s-K%d).", colocados, n_pista, L, L, n_pista))
    local faltan = {}
    for nombre in pairs(sin_clip) do faltan[#faltan + 1] = nombre end
    table.sort(faltan)
    if #faltan > 0 then print("  Aviso: el pack no trae estos clips: " .. table.concat(faltan, ", ") .. ".") end
    if sin_texto > 0 then print(string.format("  Aviso: %d elemento(s) se colocaron pero no pude escribir su texto.", sin_texto)) end
    if sin_pista > 0 then print(string.format("  Aviso: %d elemento(s) no se colocaron (sin pista).", sin_pista)) end
    return colocados, 0
end

-- El modo destacados: Hormozi, Gadzhi, acumulativo o pintado. A diferencia
-- del modo dinamico (3 lineas), aca NO se respetan las plantillas del Media
-- Pool del usuario: el estilo es parte del look, y los 11 sets de un pack no
-- tienen donde encajar en un esquema de 1-2 estados por palabra.
-- 'base_template' (v1.0.51) alinea la firma con el gemelo .py: si el main
-- ya resolvio el lienzo, se reusa; si llega nil, se busca aqui como
-- siempre. La aridad se vigila en las baterias (leccion de test_v1034: un
-- argumento de menos en Lua es un nil silencioso, no un error).
local function place_destacados(timeline, media_pool, track, fps, start_frame,
                                base_template)
    local lang = track.language
    local data_path = track.data_path
    if not data_path or not dato_existe(data_path) then
        print("  Aviso: no encuentro el .json de '" .. tostring(lang) .. "', lo salto.")
        return 0, 0
    end
    local datos = cargar_tabla(data_path) or {}
    local cues = datos.cues or {}
    if #cues == 0 then
        print("  Aviso: '" .. tostring(lang) .. "' no tiene bloques.")
        return 0, 0
    end

    local look = datos.look or "hormozi"
    if not DESTACADOS_ESTILOS[look] and look ~= "pintado" then
        print("  Aviso: look '" .. tostring(look) .. "' desconocido, uso 'hormozi'.")
        look = "hormozi"
    end

    -- El Diseño dinamico puede venir en la pista (v1.0.51, presets con
    -- motor): el ancla del deslizador, el dorado editable del preset y —
    -- para los looks de un Text+ por bloque— sus estilos {normal,
    -- resaltada}. Sin ellos, las constantes de fabrica de siempre.
    local diseno = track.diseno
    local ancla_dis = nil
    if type(diseno) == "table" then
        ancla_dis = tonumber(diseno.ancla_y)
        if diseno.preset then
            print(string.format("  Diseño dinámico: preset '%s' (estilos y "
                .. "posición elegidos en el programa).",
                tostring(diseno.preset)))
        end
    end
    local estilos_look = nil
    if type(datos.estilo_destacados) == "table" then
        estilos_look = {}
        for rol, e in pairs(datos.estilo_destacados) do
            if type(e) == "table" then
                estilos_look[rol] = estilo_del_manifiesto(e)
            end
        end
        if not (estilos_look.normal or estilos_look.resaltada) then
            estilos_look = nil
        end
    end

    if not base_template then
        base_template = obtener_text_plus_base(timeline, media_pool)
    end
    if not base_template then
        print("  Aviso: para '" .. tostring(lang) .. "' no encontre ningun Text+ " ..
              "para usar y no pude crear uno automaticamente. Arrastra un Text+ " ..
              "(Effects > Titles) al Media Pool y vuelve a generar.")
        return 0, 0
    end

    print(string.format("\nIdioma '%s': %d bloques, modo destacados (%s)",
        lang, #cues, look))

    local fade_frames = math.floor(FADE_OUT_SECONDS * fps + 0.5)
    local colocados, sin_texto, con_fundido, con_hold

    if look == "pintado" then
        local ok_a, ancho_t = pcall(function()
            return tonumber(timeline:GetSetting("timelineResolutionWidth"))
        end)
        local ok_b, alto_t = pcall(function()
            return tonumber(timeline:GetSetting("timelineResolutionHeight"))
        end)
        if not ok_a or not ancho_t or ancho_t <= 0 then ancho_t = 1920 end
        if not ok_b or not alto_t or alto_t <= 0 then alto_t = 1080 end
        local razon_aspecto = alto_t / ancho_t
        if type(datos.pintado) == "table" and cues[1]
                and type(cues[1].filas_texto) == "table" then
            -- v2 (v1.0.52): filas por caracteres, 3 capas multilinea.
            colocados, sin_texto, con_fundido, con_hold =
                colocar_pintado_v2(timeline, media_pool, lang, cues,
                                   base_template, fps, start_frame,
                                   datos.pintado, razon_aspecto, ancla_dis)
        else
            -- v1 (manifiestos viejos): dos pistas por palabra.
            local estilo_pintado = ESTILO_PINTADO_RESPALDO
            if type(datos.estilo_pintado) == "table" then
                estilo_pintado = estilo_del_manifiesto(datos.estilo_pintado)
            else
                print("  Aviso: el manifiesto no trae el estilo con el que "
                      .. "se midieron los anchos; uso un respaldo, las "
                      .. "palabras pueden no alinear perfecto.")
            end
            colocados, sin_texto, con_fundido, con_hold = colocar_pintado(
                timeline, media_pool, lang, cues, base_template, fps,
                start_frame, estilo_pintado, fade_frames, razon_aspecto,
                datos.colores_pintado, ancla_dis)
        end
    else
        colocados, sin_texto, con_fundido, con_hold = colocar_grupos(
            timeline, media_pool, lang, cues, look, base_template, fps,
            start_frame, fade_frames, estilos_look, ancla_dis)
    end

    if colocados == 0 then
        fail(string.format(
            "no pude colocar ni un bloque de '%s' (habia %d). Revisa que " ..
            "tengas un Text+ en el Media Pool.", lang, #cues))
    end

    print(string.format("  Colocados %d clips en modo destacados (%s).", colocados, look))
    if con_fundido > 0 then
        print(string.format("  Fundido de salida en %d de %d.", con_fundido, con_hold))
    end
    if sin_texto > 0 then
        print(string.format("  Aviso: %d clips quedaron sin texto automatico.", sin_texto))
    end

    -- Los efectos van en su propia pista, igual que en el modo dinamico
    -- (v1.0.51): hasta aqui esta rama no los colocaba NUNCA — la app
    -- mandaba las claves sfx_* del manifiesto y nadie las leia, o sea
    -- efectos en silencio con la casilla puesta.
    if track.sfx_library or track.sfx_archivos then
        place_sfx(timeline, media_pool, cues, track, fps, start_frame)
    end

    -- En pintado 'colocados' cuenta DOS clips por palabra (muda + dicha):
    -- sumarlo al total de lineas del resumen inflaba el "Colocadas N
    -- lineas" del epilogo. Al total se le aportan los BLOQUES.
    if look == "pintado" then
        return #cues, 0
    end
    return colocados, 0
end

-- ---------------------------------------------------------------------
-- Efectos de sonido (traducido de place_sfx_track)
--
-- El golpe suena con la palabra PRINCIPAL del bloque, no con la primera:
-- el contexto entra antes (0,8 s de media en manifiestos reales) y el
-- efecto sonando ahi parecia adelantado. Sin principal, suena al inicio.
-- ---------------------------------------------------------------------
local EXT_SFX = { ".wav", ".mp3", ".aif", ".aiff", ".m4a", ".flac", ".ogg" }

-- LOS EMOJIS (v3.3.0, pedido literal: «poner emojis a las palabras
-- claves... que salga por encima del bloque de dinámico o en la parte
-- inferior, a elección»). Text+ dibuja los emojis de color como contornos,
-- asi que van como PNG (Fluent 3D) en su propia pista <LANG>-EMOJI, encima
-- del texto. Alto y margen en fraccion del ALTO del cuadro; el margen va del
-- centro de la linea de arriba (o de abajo) al borde del emoji.
local EMOJI_ALTO = { v = 0.085, h = 0.13 }
local EMOJI_MARGEN = { v = 0.065, h = 0.10 }
-- v3.3.1: al FINAL de su linea (eleccion del usuario) el lado del emoji es el
-- alto de la letra de esa linea (Size del Text+ por el zoom del clip) por
-- este factor; entre el ultimo caracter y el emoji, 0.3 lados. Es LA
-- perilla: se ajusta con una captura, no a ciegas.
local FACTOR_EMOJI_LINEA = 1.15
local HUECO_EMOJI_LINEA = 0.3

local function importar_emoji(media_pool, ruta)
    -- La MISMA ruta se reusa; otro clip con el mismo nombre no (la leccion
    -- de los SFX desconectados de esta misma version).
    local function comparable(r)
        local c = tostring(r or ""):gsub("\\", "/")
        if es_windows() then c = c:lower() end
        return c
    end
    local buscada = comparable(ruta)
    local function buscar(carpeta)
        for _, clip in ipairs(lista_api(carpeta:GetClipList())) do
            local ok, r = pcall(function()
                return clip:GetClipProperty("File Path")
            end)
            if ok and type(r) == "string" and r ~= ""
                    and comparable(r) == buscada then
                return clip
            end
        end
        for _, sub in ipairs(lista_api(carpeta:GetSubFolderList())) do
            local x = buscar(sub)
            if x then return x end
        end
        return nil
    end
    local ok_b, ya = pcall(function() return buscar(media_pool:GetRootFolder()) end)
    if ok_b and ya then return ya end
    -- A la RAIZ y se devuelve el current como estaba (leccion v1.0.33).
    local previa = nil
    pcall(function()
        previa = media_pool:GetCurrentFolder()
        media_pool:SetCurrentFolder(media_pool:GetRootFolder())
    end)
    local ok, nuevos = pcall(function() return media_pool:ImportMedia({ ruta }) end)
    if previa then pcall(function() media_pool:SetCurrentFolder(previa) end) end
    if ok and nuevos and nuevos[1] then return nuevos[1] end
    return nil
end

-- v5.8: las SECUENCIAS animadas de emoji (gemela de _importar_secuencia / _animar_emoji de CineCaptions.py): la secuencia de PNG como UN clip del
-- Media Pool, repetida en bucle hasta cubrir el bloque, con entrada (rebote) en el primero y salida en el ultimo. Sin `io` (Free 21.1) no se puede
-- escribir la comp de Fusion: ahi las secuencias van en bucle pero sin rebote.
local function importar_secuencia(media_pool, datos)
    local patron = tostring(datos.patron or "")
    local n = math.floor(tonumber(datos.n) or 0)
    if patron == "" or n < 1 then return nil end
    local function comparable(r)
        local c = tostring(r or ""):gsub("\\", "/")
        if es_windows() then c = c:lower() end
        return c
    end
    local buscada = comparable((patron:gsub("%%04d", string.format("[0001-%04d]", n))))
    local function buscar(carpeta)
        for _, clip in ipairs(lista_api(carpeta:GetClipList())) do
            local ok, r = pcall(function() return clip:GetClipProperty("File Path") end)
            if ok and type(r) == "string" and r ~= "" and comparable(r) == buscada then
                return clip
            end
        end
        for _, sub in ipairs(lista_api(carpeta:GetSubFolderList())) do
            local x = buscar(sub)
            if x then return x end
        end
        return nil
    end
    local ok_b, ya = pcall(function() return buscar(media_pool:GetRootFolder()) end)
    if ok_b and ya then return ya end
    local previa = nil
    pcall(function()
        previa = media_pool:GetCurrentFolder()
        media_pool:SetCurrentFolder(media_pool:GetRootFolder())
    end)
    local ok, nuevos = pcall(function()
        return media_pool:ImportMedia({ { FilePath = patron, StartIndex = 1, EndIndex = n } })
    end)
    if previa then pcall(function() media_pool:SetCurrentFolder(previa) end) end
    if ok and nuevos and nuevos[1] then return nuevos[1] end
    return nil
end

local function comp_animacion_emoji(largo, entrada, salida)
    local t = "(math.min(1,math.max(0,time/8))-1)"
    local pop = entrada and string.format("(1+2.70158*%s^3+1.70158*%s^2)", t, t) or "1"
    local fuera = salida and string.format("math.max(0,math.min(1,(%d-time)/6))", largo) or "1"
    local expr = string.format("math.max(0.001,%s*%s)", pop, fuera)
    return string.format("Composition {\n\tCurrentTime = 0,\n\tRenderRange = { 0, %d },\n\tGlobalRange = { 0, %d },\n\tTools = ordered() {\n"
        .. "\t\tTransform1 = Transform {\n\t\t\tInputs = {\n\t\t\t\tSize = Input { Value = 1, Expression = \"%s\", },\n"
        .. "\t\t\t\tInput = Input { SourceOp = \"MediaIn1\", Source = \"Output\", },\n\t\t\t},\n"
        .. "\t\t\tViewInfo = OperatorInfo { Pos = { 200, 50 } },\n\t\t},\n"
        .. "\t\tMediaIn1 = MediaIn {\n\t\t\tViewInfo = OperatorInfo { Pos = { 0, 50 } },\n\t\t},\n"
        .. "\t\tMediaOut1 = MediaOut {\n\t\t\tInputs = {\n\t\t\t\tIndex = Input { Value = \"0\", },\n"
        .. "\t\t\t\tInput = Input { SourceOp = \"Transform1\", Source = \"Output\", },\n\t\t\t},\n"
        .. "\t\t\tViewInfo = OperatorInfo { Pos = { 400, 50 } },\n\t\t},\n\t},\n}\n", largo, largo, expr)
end

local function animar_emoji(colocado, largo, entrada, salida)
    if io == nil then return false end
    local ok, hecho = pcall(function()
        local carpeta = os.getenv("TEMP") or os.getenv("TMPDIR") or "/tmp"
        local ruta = string.format("%s/cinecaptions_emoji_%d_%d%d.comp", carpeta, largo, entrada and 1 or 0, salida and 1 or 0)
        local f = io.open(ruta, "r")
        if f then
            f:close()
        else
            f = io.open(ruta, "w")
            if not f then return false end
            f:write(comp_animacion_emoji(largo, entrada, salida))
            f:close()
        end
        return colocado:ImportFusionComp(ruta) and true or false
    end)
    return ok and hecho or false
end

function colocar_emojis(timeline, media_pool, track, planes, fps)
    local L = string.upper(tostring(track.language or "??"))
    local rutas = (type(track.emojis) == "table") and track.emojis or {}
    local secuencias = (type(track.emojis_secuencias) == "table") and track.emojis_secuencias or {}
    local animados = 0
    local con = {}
    for _, p in ipairs(planes or {}) do
        if p.emoji and type(rutas[p.emoji]) == "string" and p.fin > p.ini then
            con[#con + 1] = p
        end
    end
    if #con == 0 then
        -- Sin emojis esta vez: fuera los de una corrida anterior.
        retirar_pistas_nuestras(timeline, { L .. "-EMOJI" }, "emojis",
                                "esta corrida no lleva emojis")
        return 0
    end
    local idx, error_msg = conseguir_pista_video(timeline, L .. "-EMOJI")
    if error_msg then
        print("  Aviso: no pude crear la pista de emojis de forma segura ("
              .. tostring(error_msg) .. "): los subtitulos van sin emojis.")
        return 0
    end
    local ancho = tonumber(timeline:GetSetting("timelineResolutionWidth")) or 1920
    local alto = tonumber(timeline:GetSetting("timelineResolutionHeight")) or 1080
    local f = (alto > ancho) and "v" or "h"
    -- v5.3: 'abajo' (por defecto: debajo de las lineas, o en el bloque 'imagen' del pack),
    -- 'arriba' o 'linea' (al final de su linea, como en la v3.3.1).
    local modo = tostring(track.emoji_posicion or "abajo")
    local arriba = (modo == "arriba")
    -- Las medidas viajan en fraccion del ALTO; a fraccion del ANCHO con la
    -- razon de aspecto, como el pintado.
    local razon = alto / ancho
    local ajustar = 2
    pcall(function() ajustar = resolve.SCALE_FIT or 2 end)
    local items, puestos, sin_poner, sin_mover = {}, 0, 0, 0
    local junto, encima, en_slot = 0, 0, 0
    for _, p in ipairs(con) do
        local item = items[p.emoji]
        if item == nil then
            if type(secuencias[p.emoji]) == "table" then
                item = importar_secuencia(media_pool, secuencias[p.emoji]) or false
            end
            if not item then
                item = importar_emoji(media_pool, rutas[p.emoji]) or false
            end
            items[p.emoji] = item
            if item then
                -- Un PNG no calibra nada: el factor y el fotograma final
                -- ya los aprendio el texto (y un still no debe enseñarle
                -- otros a los titulos de la corrida).
                local n = nombre_clip(item)
                FACTORES[n] = 1
                CALIBRADOS[n] = true
            end
        end
        local colocado = nil
        local trozos = {}
        if item then
            local largo_plan = p.fin - p.ini
            local sec = secuencias[p.emoji]
            local es_secuencia = false
            if type(sec) == "table" then
                local ok_p, ruta_p = pcall(function() return item:GetClipProperty("File Path") end)
                es_secuencia = ok_p and type(ruta_p) == "string" and ruta_p:find("[", 1, true) ~= nil
            end
            if es_secuencia then
                -- secuencia animada: se repite (en bucle) hasta cubrir el bloque; la entrada va en el 1.o y la salida en el ultimo
                local cuadros = math.max(2, math.floor(tonumber(sec.n) or 2))
                local pos = 0
                while pos < largo_plan do
                    local seg = math.min(cuadros, largo_plan - pos)
                    local c = colocar_medido(media_pool, timeline, item, 0, seg, idx, p.ini + pos, fps, COLORES_CC.emoji)
                    if not c then break end
                    trozos[#trozos + 1] = { c, seg }
                    pos = pos + seg
                end
                if #trozos > 0 then colocado = trozos[1][1] end
            else
                colocado = colocar_medido(media_pool, timeline, item, 0,
                                          largo_plan, idx, p.ini, fps, COLORES_CC.emoji)
                if colocado then trozos = { { colocado, largo_plan } } end
            end
        end
        if colocado then
            -- v5.3: el bloque 'imagen' del pack manda (posicion y tamaño); sin el, DEBAJO de las
            -- lineas, centrado. 'linea' = al final de su linea (v3.3.1), 'arriba' = encima.
            local lado, y, cx = EMOJI_ALTO[f], nil, 0.5
            local slot = p.slot
            if track.emoji_forzar then slot = nil end        -- el usuario eligio Abajo/Arriba: manda su eleccion
            if type(slot) == "table" and tonumber(slot[1]) and tonumber(slot[2])
                    and tonumber(slot[3]) then
                lado = math.max(0.03, math.min(0.5, EMOJI_ALTO[f] * tonumber(slot[3])))
                cx = 0.5 + tonumber(slot[1])
                y = tonumber(slot[2])
                en_slot = en_slot + 1
            end
            if y == nil and modo == "linea" then
                local par = nil
                if type(p.medidas) == "table" and type(p.medidas[f]) == "table" then
                    local m = p.medidas[f]
                    par = (p.numero ~= nil and m[tostring(p.numero)]) or m["*"]
                end
                if type(par) == "table" and tonumber(par[1]) and tonumber(par[2]) then
                    local ancho_em, alto_em = tonumber(par[1]), tonumber(par[2])
                    local zx = tonumber(p.zx) or 1
                    local lado_l = math.max(0.04, math.min(EMOJI_ALTO[f],
                        alto_em * zx * FACTOR_EMOJI_LINEA))
                    local borde = 0.5 + (tonumber(p.x) or 0)
                        + (ancho_em * zx * razon) / 2
                    local cx_l = borde + (HUECO_EMOJI_LINEA * lado_l + lado_l / 2)
                        * razon
                    if cx_l + (lado_l * razon) / 2 <= 0.99 then
                        lado, cx, y = lado_l, cx_l, tonumber(p.y) or 0
                        junto = junto + 1
                    end
                end
            end
            if y == nil then
                if arriba then
                    y = (p.y_arriba or 0) + EMOJI_MARGEN[f] + lado / 2
                else
                    y = (p.y_abajo or 0) - EMOJI_MARGEN[f] - lado / 2
                end
                encima = encima + 1
            end
            local tope = 0.5 - lado / 2 - 0.01
            if y > tope then y = tope elseif y < -tope then y = -tope end
            -- Con «Ajustar» el PNG cuadrado ocupa min(ancho, alto): de ahi
            -- el zoom.
            local zoom = lado * alto / math.min(ancho, alto)
            local bien = true
            for k_t, par_t in ipairs(trozos) do
                local c_t, largo_t = par_t[1], par_t[2]
                poner_props(c_t, { Scaling = ajustar })
                if not poner_props(c_t, { ZoomX = zoom, ZoomY = zoom,
                                          Pan = pan_px(cx - 0.5 + (tonumber(p.dx_n) or 0), ancho),
                                          Tilt = tilt_px(y + (tonumber(p.dy_n) or 0), alto) }) then
                    bien = false
                end
                -- entrada (rebote) en el primero y salida en el ultimo: el icono no aparece ni desaparece de golpe
                if animar_emoji(c_t, math.max(2, math.floor(largo_t)), k_t == 1, k_t == #trozos) then
                    animados = animados + 1
                end
            end
            if bien then
                puestos = puestos + 1
            else
                sin_mover = sin_mover + 1
            end
        else
            sin_poner = sin_poner + 1
        end
    end
    print(string.format("  Emojis: %d de %d en la pista '%s' (%d en el bloque "
        .. "'imagen', %d al final de su linea, %d %s del bloque).", puestos, #con,
        L .. "-EMOJI", en_slot, junto, encima, arriba and "encima" or "debajo"))
    if animados > 0 then
        print(string.format("  Emojis con animacion: %d clip(s) con entrada y salida (los animados de Google, en bucle).", animados))
    end
    if sin_mover > 0 then
        print(string.format("  Aviso: %d emoji(s) quedaron sin tamaño ni "
            .. "posicion (tu Resolve no acepto SetProperty): quedan en el "
            .. "centro, muevelos a mano.", sin_mover))
    end
    if sin_poner > 0 then
        print(string.format("  Aviso: %d emoji(s) no se pudieron colocar "
            .. "(no pude importar su PNG).", sin_poner))
    end
    return puestos
end

function place_sfx(timeline, media_pool, cues, track, fps, start_frame)
    local libreria = track.sfx_library
    local sfx_archivos = track.sfx_archivos or {}
    -- Con las rutas en el manifiesto ya no hace falta que exista
    -- sfx_library: los sonidos pueden venir enteros de una carpeta del
    -- usuario, que vive fuera de esa raiz.
    if not libreria and next(sfx_archivos) == nil then return end

    local con_efecto = {}
    for _, c in ipairs(cues) do
        if c.sfx then table.insert(con_efecto, c) end
    end
    if #con_efecto == 0 then return end

    local config = track.sfx_config or {}
    local nombre_pista = config.nombre_pista or config.nombre_pista_audio or "SFX"

    -- El efecto se mueve CON su bloque. Si el bloque entra 6 fotogramas antes
    -- y el sonido no, el golpe suena tarde y se nota mas que el propio
    -- adelanto.
    --
    -- Y se calcula igual que alli, recorriendo TODOS los cues en orden: si
    -- aqui se restara el adelanto a secas, en los casos en que place_dynamic
    -- tuvo que recortarlo (para no comerse el bloque anterior) el sonido
    -- quedaria unos fotogramas antes que su propio subtitulo.
    local adelanto = math.floor(tonumber(track.adelanto_frames or 0) or 0)
    if adelanto < 0 then adelanto = 0 end

    local function destacado(cue)
        for _, l in ipairs((cue or {}).lines or {}) do
            if l.role ~= "base" then return true end
        end
        return false
    end

    local inicio_de_cue = {}
    local ini_anterior = nil
    for _, c in ipairs(cues) do
        local ini = start_frame + math.floor(c.start * fps + 0.5)
                    - (destacado(c) and adelanto or 0)
        if ini < start_frame then ini = start_frame end
        if ini_anterior ~= nil and ini <= ini_anterior then
            ini = ini_anterior + 1
        end
        inicio_de_cue[c] = ini
        ini_anterior = ini
    end

    -- Listar audios por categoria.
    --
    -- Primero se mira lo que la app dejo en el manifiesto: trae las rutas
    -- COMPLETAS y es el unico camino que funciona cuando los sonidos vienen
    -- de una carpeta del usuario o de sus favoritos.
    --
    -- Recorrer la carpeta queda como respaldo para manifiestos viejos, y ese
    -- respaldo TIENE COSTE: si bmd.readdir no esta, el ultimo recurso es
    -- io.popen, que en Windows abre una ventana de consola por categoria.
    -- Por eso el camino normal ya no pasa por ahi.
    local function audios_de(categoria)
        local dados = sfx_archivos[categoria]
        if type(dados) == "table" then
            local rutas = {}
            for _, r in ipairs(dados) do
                if type(r) == "string" and archivo_existe(r) then
                    rutas[#rutas + 1] = r
                end
            end
            if #rutas > 0 then return rutas end
            if #dados > 0 then
                print(string.format(
                    "  Aviso: el manifiesto lista %d sonidos de '%s' pero "
                    .. "ninguno existe ya en disco. Se movio la carpeta?",
                    #dados, tostring(categoria)))
            end
        end

        if not libreria then return {} end
        local sep = es_windows() and "\\" or "/"
        local carpeta = libreria .. sep .. categoria
        local archivos = {}

        local function considerar(nombre)
            local ext = nombre:match("(%.[^%.]+)$")
            if not ext then return end
            ext = ext:lower()
            for _, e in ipairs(EXT_SFX) do
                if ext == e then
                    table.insert(archivos, carpeta .. sep .. nombre)
                    return
                end
            end
        end

        if bmd ~= nil and bmd.readdir ~= nil then
            local ok, entradas = pcall(function()
                return bmd.readdir(carpeta .. sep .. "*")
            end)
            if ok and type(entradas) == "table" then
                for _, en in ipairs(entradas) do
                    local n = (type(en) == "table") and en.Name or en
                    if type(n) == "string" and n ~= "." and n ~= ".." then
                        considerar(n)
                    end
                end
                -- Vacio no se da por bueno: puede ser una categoria sin
                -- sonidos o que bmd.readdir no entendiera la ruta.
                if #archivos > 0 then return archivos end
            end
        end

        -- Respaldo con shell, SOLO fuera de Windows: alli abre una ventana
        -- de consola encima de Resolve. Con el manifiesto nuevo esto no se
        -- usa nunca; queda para manifiestos de versiones anteriores.
        if es_windows() then
            print("  Aviso: este manifiesto no trae las rutas de los sonidos "
                  .. "y no puedo listar la carpeta sin abrir una consola. "
                  .. "Vuelve a generar desde el programa.")
            return archivos
        end
        -- Sin io tampoco hay popen (Free 21.1 fuera de Windows). Guarda
        -- aparte: test_v1024_puente busca la literal de arriba.
        if SIN_IO then return archivos end
        local p = io.popen('ls -1 "' .. carpeta .. '" 2>/dev/null')
        if p then
            for linea in p:lines() do
                local ext = linea:match("(%.[^%.]+)$")
                if ext then
                    ext = ext:lower()
                    for _, e in ipairs(EXT_SFX) do
                        if ext == e then
                            table.insert(archivos, carpeta .. (es_windows() and "\\" or "/") .. linea)
                            break
                        end
                    end
                end
            end
            p:close()
        end
        table.sort(archivos)
        return archivos
    end

    -- Importar sin duplicar.
    local importados = {}
    local function item_de(ruta)
        if importados[ruta] ~= nil then return importados[ruta] end
        -- ImportMedia deja el archivo en el CURRENT FOLDER, no en la raiz.
        -- Si algo dejo el current apuntando al bin del pack, los efectos
        -- aterrizan ahi dentro y la limpieza de ese bin se los lleva (clips
        -- en rojo). Se fija la raiz a proposito y se devuelve como estaba.
        local previa = nil
        pcall(function()
            previa = media_pool:GetCurrentFolder()
            media_pool:SetCurrentFolder(media_pool:GetRootFolder())
        end)
        local nuevos = media_pool:ImportMedia({ ruta })
        if previa then
            pcall(function() media_pool:SetCurrentFolder(previa) end)
        end
        local item = (nuevos and nuevos[1]) or false
        importados[ruta] = item
        return item
    end

    -- Crear/reutilizar la pista de audio (misma anti-destruccion).
    local max_frames_sfx = math.floor(DURACION_MAXIMA_SFX_SEGUNDOS * fps + 0.5)
    -- Igual que con las pistas de video: la primera con ese nombre que
    -- ADEMAS sea reutilizable. Si el usuario dejo audio suyo en la pista
    -- 'SFX', se le respeta y se crea otra, en vez de quedarse sin efectos.
    local idx, ocupadas_audio = nil, 0
    for t = 1, timeline:GetTrackCount("audio") do
        local nom = timeline:GetTrackName("audio", t) or ""
        if string.upper(nom:gsub("^%s*(.-)%s*$", "%1")) == string.upper(nombre_pista) then
            if pista_audio_reutilizable(timeline, t, max_frames_sfx) then
                idx = t; break
            end
            ocupadas_audio = ocupadas_audio + 1
        end
    end
    if idx == nil then
        if ocupadas_audio > 0 then
            print("  La pista '" .. tostring(nombre_pista) .. "' tiene audio tuyo: "
                  .. "la dejo intacta y creo una nueva encima.")
        end
        local error_msg
        idx, error_msg = crear_pista_verificada(timeline, "audio", nombre_pista, "stereo")
        -- Algunas versiones no aceptan "stereo": ahi AddTrack no crea nada y
        -- vale la pena reintentar sin ese argumento.
        --
        -- Pero SOLO en ese caso. Antes se reintentaba ante cualquier error,
        -- incluso cuando AddTrack SI habia anadido la pista y lo que fallo
        -- fue la verificacion: el reintento anadia otra, y el timeline
        -- terminaba con pistas de audio huerfanas.
        if error_msg and error_msg:find("no sumo una pista nueva", 1, true) then
            idx, error_msg = crear_pista_verificada(timeline, "audio", nombre_pista)
        end
        if error_msg then
            print("\n  ERROR: no pude crear la pista de audio para los efectos " ..
                  "de forma segura (" .. error_msg .. "). No coloco ningun efecto " ..
                  "para no arriesgar tu timeline.")
            return
        end
    else
        -- Ya se comprobo al elegirla que esta pista es nuestra.
        local borrados = limpiar_pista(timeline, "audio", idx)
        if borrados > 0 then
            print(string.format("  Pista SFX limpiada (%d clips previos).", borrados))
        end
    end

    print(string.format("\nEfectos de sonido: %d bloques con efecto -> pista '%s'",
          #con_efecto, nombre_pista))

    -- Rotacion de archivos por categoria, sin repetir seguidos.
    local por_cat = {}
    for _, cue in ipairs(con_efecto) do
        por_cat[cue.sfx] = (por_cat[cue.sfx] or 0) + 1
    end
    local turnos = {}
    for categoria, cuantos in pairs(por_cat) do
        local archivos = audios_de(categoria)
        if #archivos > 0 then
            turnos[categoria] = {
                archivos = archivos,
                orden = orden_de_variantes(cuantos, #archivos, 20260811),
                siguiente = 1,
            }
        end
    end

    local colocados = 0
    local por_colocar = {}
    for _, cue in ipairs(con_efecto) do
        -- v5.4 (modo simple): un sonido por PALABRA; la app manda los eventos dentro del bloque (sfx_eventos)
        local con_eventos = type(cue.sfx_eventos) == "table" and #cue.sfx_eventos > 0
        if con_eventos then
            local base_ini = inicio_de_cue[cue] or (start_frame + math.floor(cue.start * fps + 0.5))
            for _, ev in ipairs(cue.sfx_eventos) do
                local ruta_ev = ev.sfx_archivo
                -- v5.4.16: archivo_existe (no io.open directo): el menu de Free 21.1 no tiene io y reventaba con «attempt to index global 'io'»
                if type(ruta_ev) == "string" and ruta_ev ~= "" and archivo_existe(ruta_ev) then
                    local item_ev = item_de(ruta_ev)
                    if item_ev then
                        local delta = math.floor(((tonumber(ev.t) or cue.start) - cue.start) * fps + 0.5)
                        if delta < 0 then delta = 0 end
                        local d = frames_de_audio(item_ev, fps)
                        if d < 1 then d = math.max(1, math.floor(0.5 * fps + 0.5)) end
                        por_colocar[#por_colocar + 1] = { inicio = base_ini + delta, item = item_ev, dur = d, cat = ev.sfx or cue.sfx }
                    end
                end
            end
        end
        local turno = (not con_eventos) and turnos[cue.sfx] or nil
        -- v5.4: la app dice QUE archivo suena en cada bloque (el punto del editor); sin el, se turnan los de la categoria
        local directo = cue.sfx_archivo
        local tiene_directo = false
        if (not con_eventos) and type(directo) == "string" and directo ~= "" then
            if archivo_existe(directo) then tiene_directo = true end
        end
        if turno or tiene_directo then
            local archivo
            if tiene_directo then
                archivo = directo
            else
                archivo = turno.archivos[turno.orden[turno.siguiente]]
                turno.siguiente = turno.siguiente + 1
            end
            local item = item_de(archivo)
            if item then
                local dur = frames_de_audio(item, fps)
                if dur < 1 then dur = math.max(1, math.floor(0.5 * fps + 0.5)) end
                local inicio_sfx = inicio_de_cue[cue]
                    or (start_frame + math.floor(cue.start * fps + 0.5))
                -- El mismo retardo que place_dynamic le aplica a la linea
                -- 'main' (calculado EN DELTA, no restando dos redondeos:
                -- la otra forma cae un fotograma al lado del texto). Se
                -- suma DESPUES del clamping de inicio_de_cue para no
                -- desalinear el efecto de su propio bloque adelantado.
                local retardo_main = 0
                for _, l in ipairs(cue.lines or {}) do
                    if l.role == "main" then
                        local delta = (tonumber(l.start) or cue.start) - cue.start
                        retardo_main = math.floor(delta * fps + 0.5)
                        if retardo_main < 0 then retardo_main = 0 end
                        break
                    end
                end
                if retardo_main == 0 then
                    -- Bloques 'pintado' (v1.0.51): el golpe visual es la
                    -- primera palabra resaltada — el MISMO instante que
                    -- midio sfx_rules para la separacion entre efectos.
                    for _, p in ipairs(cue.palabras or {}) do
                        if p.resaltada then
                            local delta = (tonumber(p.start) or cue.start)
                                - cue.start
                            retardo_main = math.floor(delta * fps + 0.5)
                            if retardo_main < 0 then retardo_main = 0 end
                            break
                        end
                    end
                end
                if config.al_inicio then retardo_main = 0 end  -- modo simple: al PRINCIPIO del bloque
                if retardo_main > 0 then
                    -- Tope: dentro del bloque. 'end' esta estirado hasta el
                    -- siguiente, asi que el margen sobra.
                    local fin_cue = tonumber(cue["end"]) or cue.start
                    local tope = start_frame
                        + math.floor(fin_cue * fps + 0.5) - 1
                    local nuevo = inicio_sfx + retardo_main
                    if tope > inicio_sfx and nuevo > tope then nuevo = tope end
                    inicio_sfx = nuevo
                end
                por_colocar[#por_colocar + 1] = { inicio = inicio_sfx, item = item, dur = dur, cat = cue.sfx }
            end
        end
    end
    -- v5.4: con la duracion REAL de cada sonido (antes todos se cortaban a 0,5 s) los largos se pisan y Resolve rechaza
    -- el clip que no cabe en la pista: cada efecto dura lo que su sonido (o su recorte) pero, como mucho, hasta el siguiente.
    table.sort(por_colocar, function(x, y) return x.inicio < y.inicio end)
    -- v5.4: los sonidos son POR PALABRA y pueden pisarse: cada uno va en la primera pista (SFX, SFX 2, SFX 3...) donde cabe
    -- entero, sin recortarlo.
    local pistas = { idx }
    local fin_pista = { -1 }
    local sin_sitio = 0
    local nombre_base = tostring(nombre_pista or "SFX")
    local function pista_extra(n)
        local pref = string.upper(nombre_base) .. " "
        for t = 1, timeline:GetTrackCount("audio") do
            local nm = string.upper(tostring(timeline:GetTrackName("audio", t) or ""))
            if t ~= idx and nm == pref .. tostring(n + 1) then
                if pista_audio_reutilizable(timeline, t, max_frames_sfx) then
                    limpiar_pista(timeline, "audio", t)      -- efectos de una corrida anterior
                    return t
                end
            end
        end
        local antes = timeline:GetTrackCount("audio")
        local ok = timeline:AddTrack("audio", "stereo") or timeline:AddTrack("audio")
        if not ok then return nil end
        local nuevo = timeline:GetTrackCount("audio")
        if nuevo == antes then nuevo = antes + 1 end
        pcall(function() timeline:SetTrackName("audio", nuevo, nombre_base .. " " .. tostring(n + 1)) end)
        return nuevo
    end
    for _, p in ipairs(por_colocar) do
        local k = nil
        for j = 1, #pistas do
            if fin_pista[j] <= p.inicio then k = j; break end
        end
        if k == nil then
            if #pistas >= 8 then
                sin_sitio = sin_sitio + 1
            else
                local nueva = pista_extra(#pistas)
                if nueva then
                    pistas[#pistas + 1] = nueva
                    fin_pista[#fin_pista + 1] = -1
                    k = #pistas
                else
                    sin_sitio = sin_sitio + 1
                end
            end
        end
        if k then
            fin_pista[k] = p.inicio + p.dur
            local clip_info = {
                mediaPoolItem = p.item,
                startFrame = 0,
                endFrame = p.dur - 1,
                trackIndex = pistas[k],
                mediaType = 2,
                recordFrame = p.inicio,
            }
            -- OJO: en Lua una tabla VACIA es verdadera: hay que mirar el primer elemento.
            local nuevos = media_pool:AppendToTimeline({ clip_info })
            if nuevos and nuevos[1] then
                COLORES_CC.pintar(nuevos[1], COLORES_CC.de_sfx(p.cat))
                colocados = colocados + 1
            end
        end
    end
    if sin_sitio > 0 then
        print(string.format("  Aviso: %d efecto(s) no cupieron en las %d pistas y se omitieron.", sin_sitio, #pistas))
    end
    if colocados == 0 then
        -- No se falla: los subtitulos ya estan puestos y son lo importante.
        -- Pero hay que DECIRLO: marcar la casilla y que no pase nada, sin
        -- una sola linea que lo explique, es lo que hubo que diagnosticar
        -- a ciegas.
        print(string.format(
            "  ATENCION: no coloque ningun efecto (esperaba %d). Revisa que "
            .. "la carpeta '%s' tenga audios en las categorias que pediste.",
            #con_efecto, tostring(libreria)))
    else
        print(string.format("  Colocados %d efectos de %d.", colocados, #con_efecto))
    end
    return colocados
end

-- ---------------------------------------------------------------------
-- Pistas SRT (la traduccion viaja asi). Gemela de la rama de Studio.
-- ---------------------------------------------------------------------

-- "00:01:23,450" -> segundos. nil si no parece un tiempo.
local function srt_a_segundos(texto)
    local h, m, s, ms = tostring(texto):match("(%d+):(%d+):(%d+)[,%.](%d+)")
    if not h then return nil end
    return tonumber(h) * 3600 + tonumber(m) * 60 + tonumber(s)
           + tonumber(ms) / 1000
end

-- Un .srt entero -> lista de { start, fin, text }. Tolerante: un bloque
-- que no se entienda se salta, no tumba el archivo.
local function parse_srt(ruta)
    local contenido = leer_archivo(ruta)
    if not contenido then return nil end
    contenido = contenido:gsub("\r\n", "\n"):gsub("\r", "\n")
    local cues = {}
    for bloque in (contenido .. "\n\n"):gmatch("(.-)\n\n") do
        local ini, fin = bloque:match(
            "(%d+:%d+:%d+[,%.]%d+)%s*%-%->%s*(%d+:%d+:%d+[,%.]%d+)")
        if ini then
            local s0, s1 = srt_a_segundos(ini), srt_a_segundos(fin)
            local texto = bloque:match("%-%->[^\n]*\n(.*)$") or ""
            texto = texto:gsub("^%s+", ""):gsub("%s+$", "")
            if s0 and s1 and texto ~= "" then
                cues[#cues + 1] = { start = s0, fin = s1, text = texto }
            end
        end
    end
    return cues
end

-- El clip 'base' de un bin RCS (el pack ya preparado), o nil. La busqueda
-- global EXCLUYE los bins nuestros a proposito; para la pista TRADUCIDA es
-- al reves: se quiere justamente la 'base' del pack.
local function plantilla_base_del_pack(media_pool)
    local ok, raiz = pcall(function() return media_pool:GetRootFolder() end)
    if not ok or not raiz then return nil end
    for _, sub in ipairs(lista_api(raiz:GetSubFolderList())) do
        local ok_n, nombre = pcall(function() return sub:GetName() end)
        if ok_n and nombre
                and tostring(nombre):sub(1, #PREFIJO_BIN_PACK) == PREFIJO_BIN_PACK then
            local clip = NOMBRES.buscar_base(media_pool, sub)
            if clip then return clip end
        end
    end
    return nil
end

-- Cuanto baja la pista traducida respecto de donde el pack pone la 'base'
-- (fraccion de la altura, la unidad de Center Y). Mismos numeros que el
-- gemelo de Studio: hay un test que los compara.
local BAJADA_TRADUCIDA = 0.10
local PISO_TRADUCIDA = 0.04

-- Baja el Center del Text+ de ese clip. true solo si se COMPROBO (la
-- leccion del fundido: SetInput no lanza aunque no haga nada). Si el comp
-- no expone Center (grupo con PolyPath) devuelve false y no toca nada.
local function bajar_center(item, bajada, piso)
    bajada = bajada or BAJADA_TRADUCIDA
    piso = piso or PISO_TRADUCIDA
    local tool = get_text_plus(item)
    if not tool then return false end
    local x, y
    local ok = pcall(function()
        local c = tool:GetInput("Center")
        x, y = tonumber(c[1]), tonumber(c[2])
    end)
    if not ok or not x or not y then return false end
    local nuevo = math.max(piso, y - bajada)
    if math.abs(nuevo - y) < 1e-6 then return true end
    local cy
    local ok2 = pcall(function()
        tool:SetInput("Center", { x, nuevo })
        local c = tool:GetInput("Center")
        cy = tonumber(c[2])
    end)
    if not ok2 or not cy or math.abs(cy - nuevo) > 1e-4 then
        pcall(function() tool:SetInput("Center", { x, y }) end)
        return false
    end
    return true
end

-- ------------------- el pack de SUBTITULOS BASICOS (v1.0.69) -------------
-- Gemelas del .py de Studio: dos .drb con clips 'basico|traducion
-- {inferior|superior} {1..3}'. OJO con los nombres REALES: 'traducion' va
-- sin c y con DOBLE espacio dentro de los .drb — se compara NORMALIZADO
-- (minusculas + espacios colapsados) y aceptando tambien 'traduccion'.

local function norm_nombre_basico(texto)
    -- Parentesis a proposito: gsub devuelve DOS valores y sin ellos el
    -- conteo se colaria como segundo retorno.
    return (tostring(texto or ""):lower():gsub("^%s+", "")
            :gsub("%s+$", ""):gsub("%s+", " "))
end

local function clip_basico_en(carpeta, tipo, pos, n)
    local objetivo = tipo .. " " .. pos .. " " .. tostring(n)
    local alterno = nil
    if tipo == "traducion" then
        alterno = "traduccion " .. pos .. " " .. tostring(n)
    end
    local function buscar(f)
        for _, c in ipairs(lista_api(f:GetClipList())) do
            local ok_n, nombre = pcall(function() return c:GetName() end)
            if ok_n and nombre then
                local limpio = norm_nombre_basico(nombre)
                if limpio == objetivo or limpio == alterno then
                    return c
                end
            end
        end
        for _, s in ipairs(lista_api(f:GetSubFolderList())) do
            local hallado = buscar(s)
            if hallado then return hallado end
        end
        return nil
    end
    local ok, resultado = pcall(buscar, carpeta)
    if ok then return resultado end
    return nil
end

local function pack_basicos_del_manifiesto(track, timeline)
    -- El bloque 'plantilla_basicos' resuelto a UN formato, o nil. Misma
    -- regla que pack_del_manifiesto: forzado > resolucion > el mas
    -- parecido con aviso.
    local bruto = track.plantilla_basicos
    if type(bruto) ~= "table" or type(bruto.formatos) ~= "table" then
        return nil
    end
    local formatos = bruto.formatos
    local formato = bruto.formato_forzado
    if formato ~= nil and type(formatos[formato]) ~= "table" then
        formato = nil
    end
    if formato == nil then
        local ancho = tonumber(timeline:GetSetting(
            "timelineResolutionWidth")) or 0
        local alto = tonumber(timeline:GetSetting(
            "timelineResolutionHeight")) or 0
        local deseado = (alto > ancho) and "v" or "h"
        if type(formatos[deseado]) == "table" then
            formato = deseado
        else
            for _, f in ipairs({ "h", "v", "c" }) do
                if type(formatos[f]) == "table" then
                    formato = f
                    break
                end
            end
            if formato then
                print("  Basicos: el pack no trae el formato '" .. deseado
                      .. "'; uso '" .. formato .. "'.")
            end
        end
    end
    if formato == nil then return nil end
    local drb = formatos[formato].drb
    local n = math.floor(tonumber(bruto.n) or 0)
    local pos = bruto.pos
    if not drb or n < 1
            or (pos ~= "inferior" and pos ~= "superior") then
        return nil
    end
    return { nombre = tostring(bruto.pack or "Subtitulos basicos"),
             formato = formato, pos = pos, n = n, drb = tostring(drb),
             -- v3.3.0: la posicion de superior/inferior y de la traduccion.
             transformaciones = (type(formatos[formato].transformaciones)
                 == "table") and formatos[formato].transformaciones or {} }
end

local function preparar_bin_basicos(media_pool, pb)
    -- (bin, nil) o (nil, aviso). Idempotente: si el bin ya trae el clip
    -- pedido se reutiliza. Calco del peldaño drb: foto del current +
    -- SetCurrentFolder(bin) + ImportFolderFromFile + restaurar (leccion
    -- v1.0.33); verificacion PROPIA re-buscando el clip, NUNCA
    -- buscar_sets_de_plantillas (busca contexto/principal).
    local nombre_bin = nombre_bin_pack(pb.nombre, pb.formato)
    local ok_r, raiz = pcall(function()
        return media_pool:GetRootFolder()
    end)
    if not ok_r or not raiz then
        return nil, "el Media Pool no respondio"
    end
    local carpeta = subcarpeta(raiz, nombre_bin)
    if carpeta and clip_basico_en(carpeta, "basico", pb.pos, pb.n) then
        return carpeta, nil
    end
    if not archivo_existe(pb.drb) then
        return nil, "no encuentro el archivo del pack (" .. pb.drb .. ")"
    end
    if not carpeta then
        local ok_c
        ok_c, carpeta = pcall(function()
            return media_pool:AddSubFolder(raiz, nombre_bin)
        end)
        if not ok_c then carpeta = nil end
    end
    if not carpeta then
        return nil, "no pude crear el bin del pack de basicos"
    end
    local previa = nil
    pcall(function() previa = media_pool:GetCurrentFolder() end)
    pcall(function() media_pool:SetCurrentFolder(carpeta) end)
    local importo = false
    local ok_i, err_i = pcall(function()
        importo = media_pool:ImportFolderFromFile(pb.drb) and true or false
    end)
    if not ok_i then
        print("  Basicos: ImportFolderFromFile no esta en este Resolve ("
              .. tostring(err_i) .. ").")
    end
    if previa then
        pcall(function() media_pool:SetCurrentFolder(previa) end)
    end
    if importo and clip_basico_en(carpeta, "basico", pb.pos, pb.n) then
        return carpeta, nil
    end
    return nil, "no pude meter el bin de basicos en el Media Pool"
end

-- Coloca una pista .srt (la traduccion). Devuelve cuantos bloques entraron.
local function place_srt(timeline, media_pool, track, fps, start_frame)
    local lang = tostring(track.language or "??")
    local cues = parse_srt(track.srt_path)
    if not cues or #cues == 0 then
        print("  Aviso: no pude leer '" .. tostring(track.srt_path)
              .. "', salto '" .. lang .. "'.")
        return 0
    end
    print(string.format("\nIdioma '%s': %d bloques -> %s",
                        lang, #cues, tostring(track.srt_path)))

    local es_traducida = track.traducida == true
    -- La plantilla de BASICOS elegida (v1.0.69): 'basico <pos> <n>' para
    -- la pista normal y 'traducion <pos> <n>' para la traducida. Cualquier
    -- tropiezo degrada a la cascada de siempre, diciendolo.
    local clip_basico = nil
    local pb = pack_basicos_del_manifiesto(track, timeline)
    if pb then
        local carpeta_b, aviso_b = preparar_bin_basicos(media_pool, pb)
        if aviso_b then
            print("  Aviso (basicos): " .. aviso_b
                  .. ". Genero como siempre.")
        end
        if carpeta_b then
            local tipo = es_traducida and "traducion" or "basico"
            clip_basico = clip_basico_en(carpeta_b, tipo, pb.pos, pb.n)
            if clip_basico then
                print(string.format(
                    "  Plantilla de basicos: '%s %s %d' (pack '%s').",
                    tipo, pb.pos, pb.n, pb.nombre))
            elseif es_traducida then
                print(string.format(
                    "  Aviso: el pack de basicos no trae 'traducion %s %d'"
                    .. ": la traducida va como siempre.", pb.pos, pb.n))
            end
        end
    end
    local usa_basicos = clip_basico ~= nil

    -- La plantilla: la de basicos manda; despues la 'base' del pack
    -- preparado para la traducida; despues la 'base'/'Subtitle Template'
    -- del usuario; y como ultimo recurso, cualquier Text+ utilizable.
    local plantilla = clip_basico
    if not plantilla and es_traducida then
        plantilla = plantilla_base_del_pack(media_pool)
        if plantilla then
            print("  Pista traducida: uso la plantilla 'base' del pack.")
        end
    end
    plantilla = plantilla or NOMBRES.buscar_base(media_pool)
        or find_clip_by_name(media_pool, "Subtitle Template")
        or obtener_text_plus_base(timeline, media_pool)
    if not plantilla then
        print("  Aviso: '" .. lang .. "' necesita un Text+ de plantilla y no "
              .. "encontre ninguno. Salto este idioma.")
        return 0
    end

    -- Un modo, un juego de subtitulos (v2.0.2): fuera los dinamicos de una
    -- corrida anterior y las pistas LANG apiladas (hasta la v2.0.1 cada
    -- corrida normal CREABA una pista nueva encima de la anterior);
    -- despues se reutiliza la primera LANG que sea nuestra o se crea, con
    -- el mismo criterio que las dinamicas.
    local L = string.upper(lang)
    do
        local nombres_n = { L .. "-CTX", L .. "-MAIN", L .. "-CMP", L, L .. "-EMOJI" }
        for k = 1, 24 do nombres_n[#nombres_n + 1] = string.format("%s-K%d", L, k) end
        retirar_pistas_nuestras(timeline, nombres_n, "subtitulos", "esta corrida es de subtitulos normales")
    end
    local idx, error_msg = conseguir_pista_video(timeline, L)
    if error_msg then
        print("  ERROR: no pude crear la pista '" .. string.upper(lang)
              .. "' de forma segura (" .. error_msg .. "). Salto '"
              .. lang .. "'.")
        return 0
    end

    local colocados, bajados, sin_bajar = 0, 0, 0
    -- La posicion del clip de basicos (v3.3.0), por su clave del .drb.
    local transf_basico = nil
    local ancho_tl, alto_tl = 1920, 1080
    if usa_basicos then
        transf_basico = pb.transformaciones[(es_traducida and "traducion"
            or "basico") .. "|" .. pb.pos .. "|" .. tostring(pb.n)]
        ancho_tl = tonumber(timeline:GetSetting("timelineResolutionWidth"))
            or ancho_tl
        alto_tl = tonumber(timeline:GetSetting("timelineResolutionHeight"))
            or alto_tl
    end
    TRANSF = { ya = 0, puestas = 0, fallidas = 0 }
    for _, cue in ipairs(cues) do
        local ini = start_frame + math.floor(cue.start * fps + 0.5)
        local fin = start_frame + math.floor(cue.fin * fps + 0.5)
        local duracion = math.max(1, fin - ini)
        -- Con la duracion EXACTA (v2.0.3): el fotograma de menos que
        -- Resolve pone a cada clip era el hueco entre subtitulos.
        local item_srt = colocar_medido(media_pool, timeline, plantilla, 0,
                                        duracion, idx, ini, fps, COLORES_CC.texto)
        local nuevos = item_srt and { item_srt } or nil
        if nuevos and nuevos[1] then
            local tool = get_text_plus(nuevos[1])
            if tool and set_input(tool, "StyledText", cue.text) then
                colocados = colocados + 1
                if transf_basico then
                    aplicar_transformacion(nuevos[1], transf_basico,
                                           ancho_tl, alto_tl)
                end
                -- Con basicos, ni escalon: el clip del pack ya viene
                -- colocado donde el diseñador lo quiso (v1.0.69).
                if es_traducida and not usa_basicos then
                    if bajar_center(nuevos[1]) then
                        bajados = bajados + 1
                    else
                        sin_bajar = sin_bajar + 1
                    end
                end
            end
        end
    end
    print(string.format("  Colocados %d/%d bloques en la pista '%s'.",
                        colocados, #cues, string.upper(lang)))
    informe_transformaciones()
    if bajados > 0 then
        print(string.format("  Pista traducida: %d bloques bajados un "
            .. "escalón para no tapar la original.", bajados))
    end
    if sin_bajar > 0 then
        print(string.format("  Aviso: %d bloques traducidos quedaron en la "
            .. "posición original de la plantilla (su diseño no deja "
            .. "moverlos por script).", sin_bajar))
    end
    return colocados
end

-- ---------------------------------------------------------------------
-- Main
-- ---------------------------------------------------------------------
-- ---------------------------------------------------------------------
-- Recomponer (v3.4.0): mover los textos YA PUESTOS. La app deja
-- composicion_pendiente.json (+ sidecar) y corre la accion 'subtitulos'
-- de siempre; main() mira la orden ANTES del manifiesto y, si es fresca
-- (menos de 10 min: una orden huerfana no puede convertir el proximo clic
-- de colocar en una recomposicion), recompone en vez de colocar. La base
-- de cada clip = lo que tiene ahora − lo que ya se le aplico (los tramos
-- 'anterior' de la orden): aplicar dos veces no acumula y un ajuste a mano
-- se conserva. Ni el Puente ni el bridge cambian.
-- ---------------------------------------------------------------------
local ORDEN_VALE_S = 600

local function tc_a_frames(tc, fps)
    -- Copia de CineCaptions_InsertarSFX (v1.0.62: el ';' del drop-frame).
    local h, m, s, f = tostring(tc):match("(%d+)[:;](%d+)[:;](%d+)[:;](%d+)")
    if not h then return 0 end
    return math.floor(((h * 3600 + m * 60 + s) * fps) + f + 0.5)
end

local function frame_del_cabezal(timeline, fps, start_frame)
    local ok, tc_actual = pcall(function() return timeline:GetCurrentTimecode() end)
    tc_actual = (ok and tc_actual) or "01:00:00:00"
    local tc_inicio = "01:00:00:00"
    local ok2, r2 = pcall(function() return timeline:GetStartTimecode() end)
    if ok2 and r2 then tc_inicio = r2 end
    local delta = tc_a_frames(tc_actual, fps) - tc_a_frames(tc_inicio, fps)
    if delta < 0 then delta = 0 end
    return start_frame + delta
end

-- v3.4.1: el ROL lo dice la PISTA (ES-CTX / -MAIN / -CMP; las base viven
-- en la MAIN) y el SET se busca en cadena: el nombre del clip del Media
-- Pool (GetMediaPoolItem), el nombre del clip del timeline, y el ESTILO del
-- Text+ (Size; Font solo desempata) contra los estilos del pack que trae la
-- orden. Existe porque la v3.4.0 identificaba SOLO por nombre y en el
-- Resolve del usuario ninguno de los dos parseaba: «19 clips no son de una
-- plantilla conocida», 0 movidos — y los dobles de test_v340 devolvian el
-- nombre de la plantilla en GetName(), asi que la suite estaba en verde con
-- el producto roto. El tamaño es la señal fiable: Resolve devuelve a veces
-- la fuente escrita distinto de como se guardo (ver cargar_setting).
local ROL_DE_PISTA = { ["-CTX"] = "context", ["-MAIN"] = "main",
                       ["-CMP"] = "complement" }

local function estilo_del_tool(tool)
    local fuente, tam = "", nil
    pcall(function()
        fuente = tostring(tool:GetInput("Font") or "")
        tam = tonumber(tool:GetInput("Size"))
    end)
    return fuente, tam
end

local function casa_fuente(a, b)
    a, b = string.lower(tostring(a or "")), string.lower(tostring(b or ""))
    if a == "" or b == "" then return false end
    return a == b or a:find(b, 1, true) ~= nil or b:find(a, 1, true) ~= nil
end

-- (rol, n, como, huella). 'como' = "pool" | "nombre" | "estilo" | nil (sin
-- identificar: n nil, la linea recibe solo Altura/Horizontal); 'huella' =
-- lo que se vio, para que el registro lo diga y no haya otra ronda a ciegas.
local function identificar_clip(item, tool, rol_pista, estilos_f)
    local nombre_tl = nombre_clip(item)
    local nombre_pool = nil
    local ok_m, mpi = pcall(function() return item:GetMediaPoolItem() end)
    if ok_m and mpi then nombre_pool = nombre_clip(mpi) end
    local function acepta(nombre)
        if nombre == nil or nombre == "" then return nil end
        local rol, n = parsear_nombre_pack(nombre)
        if rol == "base" and rol_pista == "main" then return "base", 0 end
        if rol == rol_pista and n and n >= 1 then return rol, n end
        return nil
    end
    local rol, n = acepta(nombre_pool)
    if rol then return rol, n, "pool", nil end
    rol, n = acepta(nombre_tl)
    if rol then return rol, n, "nombre", nil end
    local fuente, tam = estilo_del_tool(tool)
    local huella = string.format("timeline '%s', pool %s, Font '%s', Size %s",
        tostring(nombre_tl),
        nombre_pool and ("'" .. nombre_pool .. "'") or "sin respuesta",
        fuente, tostring(tam))
    if tam and type(estilos_f) == "table" then
        local mejor, mejor_fuente = nil, false
        for clave, est in pairs(estilos_f) do
            local r = tostring(clave):match("^(%a+)|%d+$")
            local s = type(est) == "table" and tonumber(est.size) or nil
            if s and r and (r == rol_pista or (r == "base" and rol_pista == "main"))
                    and math.abs(s - tam) <= 0.002 then
                local cf = casa_fuente(fuente, est.font)
                -- pairs() no tiene orden: el desempate es determinista
                -- (fuente que casa primero, despues la clave menor).
                if mejor == nil or (cf and not mejor_fuente)
                        or (cf == mejor_fuente and tostring(clave) < mejor) then
                    mejor, mejor_fuente = tostring(clave), cf
                end
            end
        end
        if mejor then
            local r, num = mejor:match("^(%a+)|(%d+)$")
            return r, tonumber(num), "estilo", huella
        end
    end
    return rol_pista, nil, nil, huella
end

local function tramo_para(tramos, frame)
    local actual = nil
    for _, t in ipairs(tramos or {}) do
        if (tonumber(t.desde) or 0) <= frame then actual = t.composicion end
    end
    if actual == nil then return nil end
    return composicion_normal(actual)
end

local function recomponer(timeline, orden, fps, start_frame)
    local nueva = composicion_normal(orden.nueva)
    local L = string.upper(tostring(orden.language or "es"))
    local ancho = tonumber(timeline:GetSetting("timelineResolutionWidth")) or 1920
    local alto = tonumber(timeline:GetSetting("timelineResolutionHeight")) or 1080
    local formato = (alto > ancho) and "v" or "h"
    local medidas_f = (type(orden.medidas) == "table" and orden.medidas[formato])
    if type(medidas_f) ~= "table" and type(orden.medidas) == "table" then
        for _, m in pairs(orden.medidas) do medidas_f = m; break end
    end
    if type(medidas_f) ~= "table" then medidas_f = {} end
    local estilos_f = (type(orden.estilos) == "table" and orden.estilos[formato])
    if type(estilos_f) ~= "table" and type(orden.estilos) == "table" then
        for _, m in pairs(orden.estilos) do estilos_f = m; break end
    end
    if type(estilos_f) ~= "table" then estilos_f = {} end
    local desde = start_frame
    if orden.desde ~= "todo" then
        desde = frame_del_cabezal(timeline, fps, start_frame)
    end
    print(string.format("  Recomposición: layout %s, altura %+.3f, horizontal "
        .. "%+.3f, desde el fotograma %d (%s).", nueva.layout, nueva.altura,
        nueva.horizontal, desde, orden.desde == "todo" and "todo" or "el cabezal"))

    local lineas, emojis_clips, ajenos = {}, {}, 0
    local como_cuenta = { pool = 0, nombre = 0, estilo = 0, ninguno = 0 }
    local huellas = {}
    local ok_c, cantidad = pcall(function() return timeline:GetTrackCount("video") end)
    for t = 1, (ok_c and cantidad or 0) do
        local ok_n, nombre_p = pcall(function() return timeline:GetTrackName("video", t) end)
        nombre_p = string.upper((ok_n and nombre_p or ""):gsub("^%s*(.-)%s*$", "%1"))
        local rol_pista = (nombre_p:sub(1, #L) == L) and ROL_DE_PISTA[nombre_p:sub(#L + 1)] or nil
        local es_emoji = nombre_p == L .. "-EMOJI"
        if rol_pista or es_emoji then
            local ok_i, items = pcall(function() return timeline:GetItemListInTrack("video", t) end)
            for _, it in ipairs(ok_i and lista_api(items) or {}) do
                local ok_s, record = pcall(function() return it:GetStart() end)
                local ok_e, fin = pcall(function() return it:GetEnd() end)
                record, fin = tonumber(ok_s and record), tonumber(ok_e and fin)
                -- v3.4.1: fin > desde — el bloque que esta BAJO el cabezal
                -- tambien entra (es lo que uno espera al parar a mitad).
                if record and fin and fin > desde then
                    if es_emoji then
                        if es_clip_texto_nuestro(it) then
                            emojis_clips[#emojis_clips + 1] = { item = it, record = record }
                        end
                    else
                        local ok_t, tool = pcall(get_text_plus, it)
                        if not (ok_t and tool) then
                            -- Sin Text+ no es nuestro: no se toca.
                            ajenos = ajenos + 1
                        else
                            local rol, n, como, huella = identificar_clip(
                                it, tool, rol_pista, estilos_f)
                            como_cuenta[como or "ninguno"] = como_cuenta[como or "ninguno"] + 1
                            if como == nil and #huellas < 3 then
                                huellas[#huellas + 1] = huella
                            end
                            local texto = nil
                            local ok_g, v = pcall(function() return tool:GetInput("StyledText") end)
                            if ok_g and type(v) == "string" then texto = v end
                            local ancho_em = nil
                            if n ~= nil then
                                local por_texto = medidas_f[rol .. "|" .. tostring(n)]
                                ancho_em = (type(por_texto) == "table" and texto)
                                    and tonumber(por_texto[texto]) or nil
                            end
                            lineas[#lineas + 1] = { item = it, rol = rol, record = record,
                                fin = fin, ancho_em = ancho_em,
                                zx = prop_de(it, "ZoomX") or 1 }
                        end
                    end
                end
            end
        end
    end

    -- Los bloques: las lineas que CIERRAN en el mismo fotograma (±1).
    table.sort(lineas, function(a, b)
        if a.fin ~= b.fin then return a.fin < b.fin end
        return a.record < b.record
    end)
    local bloques = {}
    for _, l in ipairs(lineas) do
        local b = bloques[#bloques]
        if b and math.abs(l.fin - b.fin) <= 1 then
            b.lineas[#b.lineas + 1] = l
            if l.record < b.record then b.record = l.record end
        else
            bloques[#bloques + 1] = { fin = l.fin, record = l.record, lineas = { l } }
        end
    end

    -- El fotograma que se anota en el estado: donde ARRANCA el primer
    -- bloque tocado (puede ser antes del cabezal), o el cabezal si no hay.
    local desde_efectivo = desde
    for _, b in ipairs(bloques) do
        if b.record < desde_efectivo then desde_efectivo = b.record end
    end
    for _, e in ipairs(emojis_clips) do
        if e.record < desde_efectivo then desde_efectivo = e.record end
    end

    local movidos, alineadas, sin_medida, fallidos = 0, 0, 0, 0
    local function mover(item, dx, dy)
        if math.abs(dx) < 0.01 and math.abs(dy) < 0.01 then return true end
        local pan = prop_de(item, "Pan") or 0
        local tilt = prop_de(item, "Tilt") or 0
        if poner_props(item, { Pan = pan + dx, Tilt = tilt + dy }) then
            movidos = movidos + 1
            return true
        end
        fallidos = fallidos + 1
        return false
    end
    local ceros = { dx = 0, dy = 0 }
    for _, b in ipairs(bloques) do
        local d_nueva, layout_b = desplazamientos_bloque(nueva, b.record, b.lineas, ancho, alto)
        local ant = tramo_para(orden.anterior, b.record)
        local d_ant = ant and desplazamientos_bloque(ant, b.record, b.lineas, ancho, alto) or nil
        for k, l in ipairs(b.lineas) do
            local da = d_ant and d_ant[k] or ceros
            mover(l.item, d_nueva[k].dx - da.dx, d_nueva[k].dy - da.dy)
            if d_nueva[k].alineada then alineadas = alineadas + 1 end
            if d_nueva[k].sin_medida then sin_medida = sin_medida + 1 end
        end
    end
    local emojis_movidos = 0
    for _, e in ipairs(emojis_clips) do
        local ant = tramo_para(orden.anterior, e.record)
        local dx = pan_px(nueva.horizontal - (ant and ant.horizontal or 0), ancho)
        local dy = tilt_px(nueva.altura - (ant and ant.altura or 0), alto)
        if mover(e.item, dx, dy) and (math.abs(dx) >= 0.01 or math.abs(dy) >= 0.01) then
            emojis_movidos = emojis_movidos + 1
        end
    end
    print(string.format("  Recompuse %d bloque(s) (%d línea(s)) y %d emoji(s) desde "
        .. "el fotograma %d: %d clip(s) movido(s), %d línea(s) alineada(s), %d "
        .. "sin medida (se quedan donde la plantilla las puso).", #bloques,
        #lineas, #emojis_clips, desde_efectivo, movidos, alineadas, sin_medida))
    if #lineas > 0 then
        print(string.format("  Identificación: %d por el Media Pool, %d por el nombre, "
            .. "%d por el estilo, %d sin identificar (solo Altura/Horizontal).",
            como_cuenta.pool, como_cuenta.nombre, como_cuenta.estilo,
            como_cuenta.ninguno))
        for _, h in ipairs(huellas) do print("    sin identificar: " .. h) end
    end
    if sin_medida > 0 and next(medidas_f) == nil then
        print("  Aviso: la orden no trae medidas de esta plantilla (Media Pool o "
              .. ".drb sin estilos): solo se aplican Altura y Horizontal.")
    end
    if fallidos > 0 then
        print(string.format("  Aviso: %d clip(s) no se pudieron mover (tu Resolve "
            .. "no acepto SetProperty).", fallidos))
    end
    if ajenos > 0 then
        print(string.format("  Aviso: %d clip(s) de las pistas de subtitulos no "
            .. "son Text+: no los toco.", ajenos))
    end
    if #bloques == 0 and #emojis_clips == 0 then
        print("  No hay subtitulos nuestros desde ese fotograma: nada que mover "
              .. "(¿el cabezal esta despues del ultimo bloque, o el timeline no "
              .. "lleva subtitulos de este programa?).")
    end
    -- El fotograma va en el resumen: la app lo lee para anotar el estado.
    return string.format("Recomposición: %d clips movidos en %d bloques desde el "
                         .. "fotograma %d", movidos, #bloques, desde_efectivo)
        .. "  ·  v" .. (VERSION:match("^[%d%.]+") or VERSION)
end

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
                     .. "Area de trabajo > Scripts > Utility > CineCaptions_Subtitulos"
        end
        fail(motivo .. "  |  Diagnostico: " .. tostring(diag))
    end
    resolve = r
    print("[Subtitulos] version " .. VERSION)
    print("[Subtitulos] entrega del Puente: "
        .. (ENTREGA_PUENTE and "recibida" or "no (corrida manual o Puente viejo)"))

    local carpeta, sep = carpeta_compartida()
    -- v3.4.0: una ORDEN de composicion fresca manda sobre el manifiesto
    -- (ver recomponer). Una vieja se ignora diciendolo.
    local ruta_orden = carpeta .. sep .. "composicion_pendiente.json"
    local orden = cargar_tabla(ruta_orden)
    if orden then
        local edad = os.time() - (tonumber(orden.creada_en) or 0)
        -- -5: la app escribe creada_en con decimales y os.time() es entero.
        if edad >= -5 and edad <= ORDEN_VALE_S then
            local project = resolve:GetProjectManager():GetCurrentProject()
            if not project then fail("No hay proyecto abierto en Resolve.") end
            local timeline = project:GetCurrentTimeline()
            if not timeline then fail("No hay timeline activo. Abre uno primero.") end
            local fps = tonumber(timeline:GetSetting("timelineFrameRate")) or 30
            local inicio = math.floor(tonumber(timeline:GetStartFrame()) or 0)
            local ok_proy, nombre_proy = pcall(function() return project:GetName() end)
            print(string.format("Proyecto: %s  |  Timeline: %s  |  fps: %s",
                                tostring(ok_proy and nombre_proy or "?"),
                                timeline:GetName(), tostring(fps)))
            print(globales_lua())
            local resumen = recomponer(timeline, orden, fps, inicio)
            -- Con io se borra aqui; sin io (21.1) la app la retira.
            if os.remove ~= nil then
                pcall(os.remove, ruta_orden)
                pcall(os.remove, ruta_orden .. ".lua")
            end
            return resumen
        end
        print(string.format("  Aviso: hay una orden de composición de hace %d s: "
            .. "la ignoro y coloco los subtítulos como siempre.", math.floor(edad)))
    end
    local ruta_manifest = carpeta .. sep .. "subtitles_manifest.json"
    local manifest = cargar_tabla(ruta_manifest)
    if not manifest then
        fail("No encuentro " .. ruta_manifest .. ". Genera los subtitulos primero desde el programa.")
    end

    local project = resolve:GetProjectManager():GetCurrentProject()
    if not project then fail("No hay proyecto abierto en Resolve.") end
    local timeline = project:GetCurrentTimeline()
    if not timeline then fail("No hay timeline activo. Abre uno primero.") end
    local media_pool = project:GetMediaPool()

    -- Lo que dejo la corrida anterior (ver MARCA_TIMELINE_TEMPORAL). Se
    -- limpia AQUI, cuando ninguno es el timeline actual.
    local sobras_tl = limpiar_temporales(project, media_pool)
    if sobras_tl > 0 then
        print(string.format("  Limpie %d timeline(s) temporal(es) de la "
            .. "corrida anterior.", sobras_tl))
    end

    local fps = tonumber(timeline:GetSetting("timelineFrameRate"))
    local inicio_timeline = math.floor(tonumber(timeline:GetStartFrame()) or 0)
    -- El PROYECTO va en el registro: una corrida en cero por estar en el
    -- proyecto equivocado era indistinguible de un fallo real (01-09).
    local ok_proy, nombre_proy = pcall(function() return project:GetName() end)
    print(string.format("Proyecto: %s  |  Timeline: %s  |  fps: %s",
                        tostring(ok_proy and nombre_proy or "?"),
                        timeline:GetName(), tostring(fps)))
    -- Va a ultimo_resultado.txt, que es lo que muestra la app: si algo falla
    -- en casa de un cliente, este renglon dice de que primitivas dispone su
    -- Resolve sin tener que preguntarselo.
    -- 'resolve=' (v3.3.0): la version de Resolve del cliente, en la linea
    -- que el reporte conserva SIEMPRE. El caso de las lineas encimadas
    -- llego sin ella y no se podia saber que Resolve era.
    local ok_ver, version_resolve = pcall(function()
        return resolve:GetVersionString()
    end)
    print(string.format(
        "bmd: readdir=%s createdir=%s direxists=%s wait=%s resolve=%s",
        (bmd ~= nil and bmd.readdir ~= nil) and "si" or "NO",
        (bmd ~= nil and bmd.createdir ~= nil) and "si" or "NO",
        (bmd ~= nil and bmd.direxists ~= nil) and "si" or "NO",
        (bmd ~= nil and bmd.wait ~= nil) and "si" or "NO",
        tostring(ok_ver and version_resolve or "?")))
    print(globales_lua())

    local total_lineas, total_efectos = 0, 0
    for _, track in ipairs(manifest.tracks or {}) do
        -- La pista traducida viaja como .srt sin style. Hasta la v1.0.31
        -- este bucle la IGNORABA: en Free la traduccion nunca llegaba al
        -- timeline y no habia ni una linea que lo dijera.
        if track.style == nil and type(track.srt_path) == "string" then
            local start_frame = inicio_timeline
            local offset = tonumber(track.offset_frames)
            if offset and offset > 0 then start_frame = math.floor(offset) end
            total_lineas = total_lineas
                + place_srt(timeline, media_pool, track, fps, start_frame)
        end
        if track.style == "dynamic" or track.style == "destacados" or track.style == "guion" or track.style == "kinetic" then
            -- El origen de coordenadas.
            --
            -- Normalmente es el inicio del timeline, como siempre. Pero si
            -- el usuario marco un punto de entrada, lo que se transcribio
            -- EMPIEZA ahi: el segundo 0 de los bloques es la marca, no el
            -- principio. Ese numero lo manda la app en el manifiesto; sin
            -- el, los subtitulos de un tramo marcado en el minuto 5 se
            -- colocarian en el minuto 0.
            local start_frame = inicio_timeline
            local offset = tonumber(track.offset_frames)
            if offset and offset > 0 then
                start_frame = math.floor(offset)
                print(string.format(
                    "  Zona marcada: los bloques arrancan en el fotograma "
                    .. "%d, no en %d.", start_frame, inicio_timeline))
            end
            local lineas, efectos
            if track.style == "dynamic" then
                -- OJO CON LA ARIDAD: place_dynamic declara 'project' como
                -- SEXTO parametro y esta llamada le pasaba cinco. En Lua eso
                -- no es un error: project llegaba nil en silencio, el
                -- 'if ... and project then' de la preparacion del pack nunca
                -- entraba, y el pack incrustado JAMAS se preparo en Free
                -- (desde la v1.0.27, seis versiones). En un proyecto sin
                -- plantillas propias: 0 sets, "no encontre ningun Text+",
                -- 0 lineas. test_v1034 corre el main entero con dobles y
                -- barre la aridad de todas las llamadas para que esto no
                -- pueda volver a pasar sin que una bateria lo grite.
                lineas, efectos = place_dynamic(timeline, media_pool, track,
                                                fps, start_frame, project)
            elseif track.style == "guion" then
                lineas, efectos = place_guion(timeline, media_pool, track,
                                              fps, start_frame, project)
            elseif track.style == "kinetic" then
                lineas, efectos = place_kinetic(timeline, media_pool, track,
                                                fps, start_frame, project)
            else
                -- 6 argumentos, como declara la funcion (leccion de
                -- test_v1034: en Lua un argumento de menos es un nil
                -- mudo). El lienzo se resuelve adentro, aqui va nil.
                lineas, efectos = place_destacados(timeline, media_pool,
                                                   track, fps, start_frame,
                                                   nil)
            end
            total_lineas = total_lineas + (lineas or 0)
            total_efectos = total_efectos + (efectos or 0)
        end
    end

    if (total_lineas or 0) > 0 then
        print("\nListo. Revisa la linea de tiempo: cada bloque es un Text+ "
              .. "editable (doble clic para retocar texto, estilo o "
              .. "posicion).")
    else
        -- Decir "Listo" con cero lineas era mentirle al registro: el
        -- usuario pegaba un informe que terminaba bien y el fallo quedaba
        -- diez lineas mas arriba.
        print("\nNO se coloco ninguna linea. El motivo esta unas lineas mas "
              .. "arriba (las que empiezan por «Aviso»).")
    end

    -- Este resumen viaja a ultimo_resultado.json y lo muestra la app.
    local resumen = string.format("%d lineas colocadas", total_lineas)
    if total_efectos > 0 then
        resumen = resumen .. string.format(" y %d efectos", total_efectos)
    end
    resumen = resumen .. "  ·  v" .. (VERSION:match("^[%d%.]+") or VERSION)
    -- v5.5: la disposicion de pantalla y el cabezal al inicio (gemelo de vista_final de CineCaptions.py)
    vista_final(timeline, manifest, (total_lineas or 0) == 0)
    return resumen, total_lineas
end

-- En caso de exito, 'err' trae lo que devolvio main(): el resumen con los
-- numeros reales. La app lo muestra en vez de dar por hecho lo que paso.
local ok, err, lineas_colocadas = pcall(main)
if not ok then
    print("[Subtitulos] termino con error: " .. tostring(err))
    -- fail() ya dejo su motivo; esto cubre los errores inesperados. Escribir
    -- dos veces no molesta: gana el ultimo, que es igual de valido.
    guardar_resultado(false, tostring(err))
elseif (lineas_colocadas or 0) <= 0 then
    -- v5.5: «Listo» con CERO lineas era mentirle al usuario (la app decia ¡Listo! y en Resolve no aparecia nada): se guarda como FALLO y la app lo cuenta asi
    guardar_resultado(false, "No se coloco ninguna linea (mira el registro de la corrida: el motivo esta unas lineas mas arriba)  ·  v" .. (VERSION:match("^[%d%.]+") or VERSION))
else
    guardar_resultado(true, type(err) == "string" and err or "")
end

-- No dejar el wrapper de print puesto: el Puente corre estos scripts con
-- dofile dentro de SU propio estado de Lua, y print es global.
print = _print_original

-- Free 21.1, sin io (v3.1.6): el registro no se pudo escribir, y el UNICO
-- canal que sale del menu es un error() sin capturar, que Resolve escribe
-- TAL CUAL en Support/logs/ResolveDebug.txt (medido con la sonda del 16-09:
-- una linea de 471 chars, sin recortar y sin prefijo de fecha). La app lee
-- ese archivo (resolve_bridge.reportes_del_registro) y con eso "Que
-- respondio Resolve", el diagnostico, el aviso de version ajena y el paso
-- manual pendiente vuelven a funcionar en 21.1. Va SIEMPRE, tambien en
-- exito: un clic = una corrida = un reporte. No es un latido (error()
-- termina el script): por eso el Puente sigue sin poder correr ahi. Con io
-- NO se lanza: bajo el Puente, un error() al final se leeria como fallo.
if SIN_IO then
    local mensaje = ok and (type(err) == "string" and err or "") or tostring(err)
    local reporte = "CINECAPTIONS_REPORTE|" .. json_resultado(ok, mensaje, texto_para_reporte())
    -- Bajo el Puente (v3.1.7, modo señales) se DEVUELVE en vez de lanzarse:
    -- el Puente lo relata al registro por fusion:Execute y saca el veredicto
    -- del json. Un error() aqui se leeria como fallo del trabajo.
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
