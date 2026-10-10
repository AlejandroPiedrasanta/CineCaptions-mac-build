-- CineCaptions · By Cinema Productions
-- 2_recursos/resolve_scripts/CineCaptions_Puente.lua — el Puente para Resolve Free: vigila la cola de trabajos y ejecuta los scripts.
--[[
CineCaptions_Puente.lua
--------------
Version en Lua de "CineCaptions - Puente.py".

Corre DENTRO de Resolve (Area de trabajo > Scripts > Utility). Es la pieza
que hace que, en Resolve FREE, los botones del programa se ejecuten solos.

COMO SE USA
===========
1. Abre tu proyecto en Resolve.
2. Area de trabajo > Scripts > Utility > CineCaptions_Puente
3. Deja esa consola abierta y usa el programa normalmente.

Para apagarlo: cierra la consola, o crea el archivo
~/DaVinciSubtitles/puente.stop

QUE HACE
========
Se queda vigilando ~/DaVinciSubtitles/jobs/ en un bucle (ya verificamos que
el bucle NO congela la interfaz de Resolve). Cuando la app deja un trabajo,
ejecuta el script .lua correspondiente y responde. El trabajo dice solo la
accion ('detectar', 'subtitulos' o 'sfx'); el input real ya lo dejo la app
en sus propios archivos (subtitles_manifest.json, sfx_pendiente.json).
]]

-- OJO: este texto lo lee la app para saber si el Puente que esta corriendo
-- quedo viejo. Si lo cambias, cambia tambien VERSION_PUENTE_ESPERADA en
-- resolve_bridge.py.
-- v1.0.25: entra la accion 'importar_estilos'. Un Puente viejo no la conoce y
-- responderia "Accion desconocida", asi que la version SUBE y con ella
-- VERSION_PUENTE_ESPERADA en resolve_bridge.py — las dos a la vez, o la app
-- encola trabajos que el Puente no sabe hacer.
-- v1.0.29: la entrega en mano (el resolve viaja como argumento del chunk)
-- y el no-correr con el handle muerto. Cambio real de comportamiento del
-- Puente: sube la version para que el aviso de relanzarlo llegue.
-- v1.0.30: el relevo — el candado anti-duplicados pedia el turno en vez de
-- retirarse, porque retirandose dejaba al residente viejo atendiendo para
-- siempre y "relanza el Puente" no hacia nada (caso real, 01-09).
-- v1.0.31: la accion nueva sfx_marcadores (un residente viejo no la
-- conoce; el aviso de relanzar es el camino — la MINIMA no se toca).
-- v1.0.32: la accion nueva sfx_reemplazar (el modo Reemplazar del SFX
-- Lab). Mismo criterio: la MINIMA no se toca.
-- v1.0.34: la huella de arranque (puente.arranque.txt) y los dos
-- fallos mudos de latir()/crear_dir(). La MINIMA no se toca.
-- v1.0.35: es_windows() sin package (Resolve 21.1), guardas de _G y la
-- linea "lua:" de globales. La MINIMA no se toca.
-- v1.0.36 (v3.1.7): el modo SEÑALES para el menu sin io de Free 21.1 (ver
-- SIN_IO): latido/tomado/respuesta por ExportKeyboardPreset, trabajos por
-- sidecar .lua, reportes por fusion:Execute -> ResolveDebug.txt. Con io no
-- cambia nada, salvo que responder() ya escapa las barras. La MINIMA no se toca.
-- v1.0.38: la accion nueva efectos (los efectos visuales en Resolve Free: CineCaptions_Efectos.lua, gemela de colocar_efectos.py). Un Puente viejo no la conoce:
-- la version sube y con ella VERSION_PUENTE_ESPERADA en resolve_bridge.py (las dos a la vez).
-- v1.0.39: la accion nueva vista (guardar / aplicar la disposicion de pantalla de Resolve: CineCaptions_Vista.lua). Un Puente viejo no la conoce: la version sube y con ella
-- VERSION_PUENTE_ESPERADA en resolve_bridge.py (las dos a la vez).
local VERSION = "1.0.39"

-- La version del PROGRAMA con la que se distribuyo este archivo. Existe
-- porque el propio creador leyo el 1.0.28 de arriba como "quedo una copia
-- vieja" teniendo la app 1.0.42 delante: el Puente numera aparte y el
-- banner no lo decia. Se sube JUNTO a APP_VERSION en cada release (misma
-- regla que los tres auxiliares). OJO: no va en el latido — las apps
-- viejas parten el latido en dos campos y un tercero las haria declarar
-- INCOMPATIBLE a un Puente sano.
local PAQUETE = "5.4.32"

-- El resolve VALIDADO del arranque. Es un local a proposito: si mas tarde
-- algo pisa el global 'resolve' (el veneno clasico de la sesion), este
-- sigue apuntando al objeto bueno y se lo podemos prestar a los scripts.
local RESOLVE_BUENO = nil
local INTERVALO = 0.25       -- cada cuanto miramos si hay trabajo (ver main)
local LATIDO_CADA = 2.0      -- cada cuanto reescribimos el latido
local INACTIVIDAD_MAX = 8 * 60 * 60

-- Que script corre cada accion (tabla gemela de resolve_bridge.SCRIPTS).
local SCRIPTS = {
    detectar = "CineCaptions_DetectarVideo.lua",
    subtitulos = "CineCaptions_Subtitulos.lua",
    sfx = "CineCaptions_InsertarSFX.lua",
    sfx_marcadores = "CineCaptions_SfxMarcadores.lua",
    sfx_reemplazar = "CineCaptions_SfxReemplazar.lua",
    importar_estilos = "CineCaptions_ImportarEstilos.lua",
    efectos = "CineCaptions_Efectos.lua",
    armar_video = "CineCaptions_ArmarVideo.lua",
    pausas = "CineCaptions_Pausas.lua",
    vista = "CineCaptions_Vista.lua",
}

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

local CARPETA = home() .. SEP .. "DaVinciSubtitles"
local CARPETA_JOBS = CARPETA .. SEP .. "jobs"
local LATIDO = CARPETA .. SEP .. "puente.heartbeat"
local STOP = CARPETA .. SEP .. "puente.stop"
-- La huella de arranque. Se escribe ANTES de validar nada y se reescribe con
-- el desenlace, asi que es la unica prueba de que el usuario llego a pulsar
-- CineCaptions_Puente en el menu. Hasta la v3.1.2 el arranque era MUDO: un script que
-- moria en su primera linea no dejaba nada en disco, y "no lo lanzo nunca" y
-- "lo lanzo y se murio" llegaban al soporte como el mismo diagnostico -misma
-- captura, arreglos opuestos-. Caso del 16-09: instalacion perfecta, latido
-- fosil de hace 31 dias, y una ronda entera para saber cual de los dos era.
local ARRANQUE = CARPETA .. SEP .. "puente.arranque.txt"
-- La firma de ESTA instancia sobre puente.stop. Un STOP con mi token es
-- la orden que YO le deje a un residente anterior colgado: mi bucle lo
-- ignora sin borrarlo (el viejo lo consume al despertar); uno con token
-- ajeno -o vacio, escrito a mano- me apaga. os.clock() separa dos
-- instancias lanzadas el mismo segundo.
local MI_TOKEN = "relevo-" .. os.time() .. "-" .. tostring(os.clock())
local RELEVO_MAXIMO_S = 15
-- La app escribe aca en que carpeta dejo los scripts (ver carpetas_posibles).
local ARCHIVO_CARPETA_SCRIPTS = CARPETA .. SEP .. "scripts_dir.txt"

-- El trabajo pendiente tiene SIEMPRE el mismo nombre.
--
-- Antes cada trabajo llevaba su id en el nombre del archivo, asi que para
-- encontrarlo habia que LISTAR la carpeta, y listar desde Lua se hacia con
-- io.popen("dir"). En Windows eso arranca un cmd.exe: a cuatro sondeos por
-- segundo, una ventana de consola abriendose y cerrandose sin parar, robando
-- el foco y dejando Resolve inusable hasta reiniciar.
--
-- Con un nombre fijo alcanza io.open, que es C puro y no lanza ningun
-- proceso. El id viaja DENTRO del JSON.
local JOB_PENDIENTE = CARPETA_JOBS .. SEP .. "pendiente.json"
local JOB_TOMADO = CARPETA_JOBS .. SEP .. "pendiente.tomado"

-- EL MODO SEÑALES (v1.0.36 / v3.1.7). Free 21.1 capo io, os.remove y
-- os.rename en el menu de Scripts (medido el 16-09): el backend de siempre
-- no puede latir, reclamar ni responder. Lo que SI queda, medido con las
-- sondas CineCaptions_Sonda_Canales y CineCaptions_Sonda_Canales2 en el 21.1 del usuario:
--   * La API de Resolve escribe archivos con codigo propio de Resolve, no con
--     el io de Lua: resolve:ExportKeyboardPreset(nombre, ruta) deja ~1 KB en
--     la ruta EXACTA que se le pide, sobrescribe, y no toca nada del usuario
--     (exporta el preset de teclado ACTUAL). Es la "señal": lo que importa es
--     que el archivo exista y su fecha; el contenido no es nuestro y nadie
--     lo lee (la app acepta el latido por mtime desde la v1.0.25).
--   * bmd.fileexists / bmd.direxists / bmd.wait existen (readdir y createdir
--     NO: sin listar, todo va por nombres fijos, que ya era la regla).
--   * loadfile lee los sidecars .lua que deja la app (sidecar_lua.py).
--   * fusion:Execute(codigo) corre Lua en OTRO estado, sincrono: un error()
--     sin capturar ahi sale al registro de Resolve (ResolveDebug.txt, con
--     prefijo "[Fusion] ERROR") y ESTE script sigue vivo. Por ahi viaja todo
--     lo que tiene contenido: los CINECAPTIONS_REPORTE de los scripts (la app los lee
--     igual que cuando se pulsan a mano), el arranque y el cierre del Puente.
-- Lo que el Lua no puede hacer -borrar- lo hace la app, que si tiene io
-- (pendiente.json, .tomado, las señales .hecho, puente.relevo).
-- Con io (21.0.x) nada de esto entra: el backend de siempre, intacto.
local SIN_IO = (io == nil)
local RELEVO = CARPETA .. SEP .. "puente.relevo"
local KB_PRESET = nil          -- el preset de teclado que se exporta como señal
local RELEVO_MIO = false       -- puente.relevo lo escribi yo (ver el bucle)
local ULTIMO_ID = nil          -- sin os.rename no hay reclamo: se recuerda el id

local function json_escapar(s)
    s = tostring(s or "")
    s = s:gsub("\\", "\\\\"):gsub('"', '\\"')
    s = s:gsub("\r", " "):gsub("\n", "\\n"):gsub("\t", " ")
    return s
end

-- Crea o refresca el archivo-señal 'ruta' (modo señales). true si Resolve
-- dijo que lo hizo. Vale antes de main() porque RESOLVE_BUENO es upvalue.
local function senal(ruta)
    if RESOLVE_BUENO == nil or KB_PRESET == nil then return false end
    local ok, r = pcall(function()
        return RESOLVE_BUENO:ExportKeyboardPreset(KB_PRESET, ruta)
    end)
    return ok and r == true
end

-- Relata una linea entera al registro de Resolve por fusion:Execute (modo
-- señales). Corchetes largos: el json trae comillas y barras.
local function relatar(linea)
    if fusion == nil then return false end
    linea = linea:gsub("%]==%]", "]=]")
    local ok = pcall(function()
        return fusion:Execute("error([==[" .. linea .. "]==], 0)")
    end)
    return ok
end

-- El mismo json de ultimo_resultado.json, con 'puente' (la version del
-- protocolo) y lo que se le sume ('arranque', el desenlace). OJO: 'version'
-- lleva PAQUETE delante porque la app compara ese campo por PREFIJO con
-- APP_VERSION (desajuste_de_version): "1.0.36" a secas dispararia el aviso
-- de "hay otra version instalada" en cada arranque del Puente.
local function json_reporte(ok, mensaje, extra)
    return string.format(
        '{"script": "CineCaptions_Puente", "version": "%s (puente %s)", "puente": "%s", '
        .. '"ok": %s, "mensaje": "%s", "cuando": %d%s}',
        json_escapar(PAQUETE), json_escapar(VERSION), json_escapar(VERSION),
        tostring(ok and true or false), json_escapar(mensaje), os.time(),
        extra or "")
end

local function reportar(ok, mensaje, extra)
    return relatar("CINECAPTIONS_REPORTE|" .. json_reporte(ok, mensaje, extra))
end

-- Saca el string de una clave de un json chico, deshaciendo los escapes.
local function json_string(texto, clave)
    local _, fin = texto:find('"' .. clave .. '"%s*:%s*"')
    if not fin then return nil end
    local partes, i = {}, fin + 1
    while i <= #texto do
        local c = texto:sub(i, i)
        if c == "\\" then
            local e = texto:sub(i + 1, i + 1)
            partes[#partes + 1] = (e == "n") and " " or e
            i = i + 2
        elseif c == '"' then
            break
        else
            partes[#partes + 1] = c
            i = i + 1
        end
    end
    return table.concat(partes)
end

-- Que primitivas nativas tiene este Resolve.
--
-- Se mira UNA vez, al cargar, y se imprime en la cabecera. Hasta ahora esto
-- se estaba deduciendo a ciegas a partir de los sintomas que contaba el
-- cliente: con esta linea, un solo screenshot dice si el parpadeo o el
-- consumo de CPU vienen de que falta bmd.readdir o bmd.wait.
local CAP = {
    wait = (bmd ~= nil and bmd.wait ~= nil),
    readdir = (bmd ~= nil and bmd.readdir ~= nil),
    createdir = (bmd ~= nil and bmd.createdir ~= nil),
    direxists = (bmd ~= nil and bmd.direxists ~= nil),
    fileexists = (bmd ~= nil and bmd.fileexists ~= nil),
}

local function capacidades()
    local partes = {}
    for _, k in ipairs({ "wait", "readdir", "createdir", "direxists" }) do
        partes[#partes + 1] = k .. "=" .. (CAP[k] and "si" or "NO")
    end
    -- fileexists va aparte para no mover las cuatro de siempre (hay
    -- baterias que las cuentan): es la que sostiene el modo señales.
    return "bmd: " .. table.concat(partes, " ")
        .. " fileexists=" .. (CAP.fileexists and "si" or "NO")
        .. "  |  " .. globales_lua()
end

-- En Windows NUNCA se ejecuta shell.
--
-- io.popen y os.execute arrancan un cmd.exe, y como Resolve es una app
-- grafica eso ABRE UNA VENTANA DE CONSOLA que parpadea encima y roba el
-- foco. Los respaldos que quedan solo se usan en macOS y Linux, donde no
-- abren nada. En Windows se prefiere no hacer la operacion -y decirlo- antes
-- que dejar el equipo inusable, que es como llegaban los reportes.
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

local function crear_dir(ruta)
    -- Modo señales: ni createdir ni io. La carpeta jobs/ la crea la app
    -- antes de encolar nada; aqui solo se puede mirar.
    if SIN_IO then return end
    -- bmd.createdir es la via nativa de Fusion y no lanza procesos.
    if CAP.createdir then
        pcall(function() return bmd.createdir(ruta) end)
    end
    -- VERIFICAR, no suponer. Hasta la v3.1.2 el pcall de arriba llevaba un
    -- "if ok then return end", y ese ok es true aunque bmd.createdir conteste
    -- false: la llamada no lanzo error, nada mas. La carpeta se daba por
    -- creada sin mirarlo y el latido moria despues en silencio.
    --
    -- Crear un archivo dentro solo funciona si la carpeta existe de verdad,
    -- asi que esta sonda es la unica respuesta honesta. No crea la carpeta,
    -- pero dice si hace falta avisar.
    local prueba = ruta .. SEP .. ".cinecaptions_ok"
    local f = io.open(prueba, "w")
    if f then f:close(); os.remove(prueba); return end

    if puede_usar_shell() then
        os.execute('mkdir -p "' .. ruta .. '"')
        return
    end
    -- En Windows la carpeta jobs/ ya la crea la app antes de encolar nada,
    -- asi que llegar aqui es raro. Se avisa en vez de abrir una consola.
    print("[Puente] Aviso: no pude crear " .. ruta
          .. " sin abrir una consola. Si algo falla, crea esa carpeta a mano.")
end

local function leer(ruta)
    if SIN_IO then
        -- Solo se puede leer un sidecar "<ruta>.lua" con `return {texto=...}`
        -- (la app los deja junto a lo que el Puente necesita leer).
        local chunk = loadfile(ruta .. ".lua")
        local ok, t = pcall(chunk or function() end)
        return (ok and type(t) == "table") and t.texto or nil
    end
    local f = io.open(ruta, "r")
    if not f then return nil end
    local c = f:read("*a"); f:close(); return c
end

local function escribir(ruta, texto)
    -- Modo señales: el contenido se pierde, solo existe el archivo. Los
    -- llamadores que necesitan contenido (marcar, responder) no pasan por
    -- aqui en ese modo.
    if SIN_IO then return senal(ruta) end
    local f = io.open(ruta, "w")
    if not f then return false end
    f:write(texto); f:close(); return true
end

local function existe(ruta)
    if SIN_IO then
        if not CAP.fileexists then return false end
        local ok, hay = pcall(function() return bmd.fileexists(ruta) end)
        return ok and hay == true
    end
    local f = io.open(ruta, "r")
    if f then f:close(); return true end
    return false
end

-- Deja la huella del arranque: "<hora>|<version>|<desenlace>". Nunca aborta
-- ni avisa: si no se puede escribir, se sigue como si nada (el Puente tiene
-- que arrancar aunque el diagnostico se quede sin este dato). En modo
-- señales la huella viaja por el registro de Resolve (campo 'arranque'), que
-- es de donde la app la lee cuando el archivo no es suyo.
local function marcar(desenlace)
    if SIN_IO then
        reportar(desenlace == "ok" or desenlace == "arrancando",
                 "Puente " .. desenlace, ', "arranque": "' .. desenlace .. '"')
        return
    end
    escribir(ARRANQUE, os.time() .. "|" .. VERSION .. "|" .. desenlace)
end

-- Extrae el valor de una clave string de un JSON chico, sin parser completo.
-- Alcanza para leer "accion" e "id" del trabajo.
local function json_valor(texto, clave)
    local patron = '"' .. clave .. '"%s*:%s*"([^"]*)"'
    return texto:match(patron)
end

-- Reclamar el trabajo pendiente, si lo hay. Devuelve (id, accion), o nil.
--
-- El reclamo sigue siendo un os.rename, que es atomico: si dos Puentes van a
-- por el mismo trabajo, solo uno se lo lleva y al otro le falla el rename.
-- Esa proteccion no cambia. Lo unico que cambia es que ya no hace falta
-- listar la carpeta para saber si hay algo (ver JOB_PENDIENTE).
--
-- Modo señales: sin os.rename no hay reclamo atomico ni borrado. Se lee el
-- sidecar pendiente.json.lua que deja la app, se recuerda el id (el archivo
-- se queda hasta que la app lo borre al ver la señal de tomado) y se avisa
-- con la señal pendiente.tomado. Un trabajo de hace mas de 5 min es de una
-- sesion anterior que nadie recogio: se ignora, no se corre por sorpresa.
local function tomar_trabajo()
    if not existe(JOB_PENDIENTE) then return nil end
    if SIN_IO then
        local chunk = loadfile(JOB_PENDIENTE .. ".lua")
        local ok, t = pcall(chunk or function() end)
        if not ok or type(t) ~= "table" or t.id == nil then return nil end
        if t.id == ULTIMO_ID then return nil end
        ULTIMO_ID = t.id
        local creado = tonumber(t.creado_en)
        if creado and os.time() - creado > 300 then return nil end
        senal(JOB_TOMADO)
        return tostring(t.id), (t.accion ~= nil) and tostring(t.accion) or nil
    end
    if not os.rename(JOB_PENDIENTE, JOB_TOMADO) then
        return nil          -- se lo llevo otro Puente
    end
    local contenido = leer(JOB_TOMADO)
    if not contenido then return nil end
    return json_valor(contenido, "id") or "pendiente", json_valor(contenido, "accion")
end

-- Como esperar entre sondeo y sondeo, de mejor a peor.
--
-- Esto importa mas de lo que parece: sin una primitiva de espera de verdad
-- no queda mas remedio que dar vueltas en un bucle, y eso mantiene un nucleo
-- al 100% TODO el rato que el Puente este abierto. Es el candidato serio al
-- "no deja hacer nada" que reportan algunos clientes, que es un sintoma
-- distinto del parpadeo aunque llegue en la misma frase.
--
-- Se prueban varias porque el nombre cambia segun por donde corra el script
-- (Resolve, Fusion, la consola). Ninguna se inventa: si no existe, se cae a
-- la siguiente.
local ESPERA, ESPERA_NOMBRE
for _, cand in ipairs({
    { "bmd.wait", function() return bmd and bmd.wait end },
    { "bmd.sleep", function() return bmd and bmd.sleep end },
    { "os.sleep", function() return os.sleep end },
}) do
    local ok, fn = pcall(cand[2])
    if ok and type(fn) == "function" then
        ESPERA, ESPERA_NOMBRE = fn, cand[1]
        break
    end
end
local HAY_BMD_WAIT = ESPERA ~= nil

-- Sin primitiva de espera el sondeo se espacia: con 0.25 s se quema un
-- nucleo entero para ganar unas decimas en responder, y no compensa. Un
-- segundo sigue siendo imperceptible al pulsar un boton.
local INTERVALO_SIN_ESPERA = 1.0

local function dormir(seg)
    if ESPERA then
        -- Bajo pcall (v3.1.10): si la primitiva de ESTE Resolve lanza, el
        -- Puente se queda sin dormir (gira mas rapido), pero no muere mudo.
        pcall(ESPERA, seg)
        return
    end
    -- Ultimo recurso. Se avisa al arrancar (ver main) para no volver a
    -- diagnosticar a ciegas un Resolve que va lento con el Puente abierto.
    local hasta = os.clock() + seg
    while os.clock() < hasta do end
end

-- El latido lleva la version ademas de la hora: "<hora>|<version>".
--
-- El Puente se carga UNA sola vez, cuando el usuario lo lanza desde el menu.
-- Si despues la app se actualiza y reescribe este archivo, el Puente viejo
-- sigue corriendo con el codigo viejo hasta que lo relancen a mano, y nada
-- se lo avisaba al usuario: solo veia errores raros que ya estaban
-- arreglados en disco. Con la version en el latido, la app se da cuenta y
-- le dice que lo vuelva a lanzar.
local AVISE_SIN_LATIDO = false

local function latir()
    if escribir(LATIDO, os.time() .. "|" .. VERSION) then return end
    -- escribir() ya devolvia false y latir() lo TIRABA: con la carpeta
    -- inexistente o sin permiso, el Puente seguia dando vueltas "sano" sin
    -- latir jamas y la app lo daba por apagado con su ventana abierta
    -- delante del usuario. Se dice UNA vez -en el bucle serian miles- y con
    -- la ruta exacta, que es lo que cierra el caso en una captura.
    if not AVISE_SIN_LATIDO then
        AVISE_SIN_LATIDO = true
        marcar("sin_latido")
        print("")
        print("[Puente] PROBLEMA: no puedo escribir mi latido en:")
        print("         " .. LATIDO)
        print("         El programa me va a dar por apagado por mas que esta")
        print("         ventana siga abierta. Revisa que esa carpeta exista")
        print("         y se pueda escribir.")
        print("")
    end
end

-- Todas las carpetas donde pueden estar nuestros .lua, en orden de
-- preferencia: primero la del propio Puente, despues las Utility conocidas
-- (la del usuario y la del sistema).
-- Subcarpetas de Fusion/Scripts donde Resolve lista scripts. 'Utility' es la
-- nuestra, pero se miran todas por si quedo algo de una version anterior, y
-- la raiz misma ("") por si estan sueltos ahi.
local SUBCARPETAS = { "Utility", "", "Edit", "Comp", "Color", "Deliver" }

local function agregar_raiz(lista, raiz)
    if not raiz or raiz == "" then return end
    for _, sub in ipairs(SUBCARPETAS) do
        table.insert(lista, sub == "" and raiz or (raiz .. SEP .. sub))
    end
end

-- Los contenedores de sandbox de macOS (Mac App Store). El bundle id cambia
-- entre versiones, asi que se enumeran en vez de escribirlo a mano. Es el
-- mismo criterio que usa el instalador del lado Python.
-- Listar una carpeta sin lanzar procesos cuando se pueda.
--
-- bmd.readdir es la via nativa de Fusion. Si no esta, o devuelve algo que no
-- reconocemos, se cae al comando de shell de siempre. Ese respaldo abre una
-- consola en Windows, asi que esto NO se usa en el bucle de sondeo: alli el
-- nombre del trabajo es fijo y basta io.open (ver JOB_PENDIENTE).
local function listar_dir(ruta)
    local nombres = {}
    if CAP.readdir then
        local ok, entradas = pcall(function()
            return bmd.readdir(ruta .. SEP .. "*")
        end)
        if ok and type(entradas) == "table" then
            for _, e in ipairs(entradas) do
                local n = (type(e) == "table") and e.Name or e
                if type(n) == "string" and n ~= "." and n ~= ".." then
                    nombres[#nombres + 1] = n
                end
            end
            -- Si vino vacio no lo damos por bueno: puede que la carpeta este
            -- vacia de verdad, o que bmd.readdir no haya entendido la ruta.
            -- Ante la duda, se comprueba con el camino de siempre.
            if #nombres > 0 then return nombres end
        end
    end
    -- El respaldo con shell, SOLO fuera de Windows (ver puede_usar_shell).
    -- Esto ademas solo lo llama raices_en_contenedores(), que es de Mac, asi
    -- que en Windows no deberia entrar aqui nunca.
    if not puede_usar_shell() then return nombres end
    local p = io.popen('ls -1 "' .. ruta .. '" 2>/dev/null')
    if p then
        for linea in p:lines() do nombres[#nombres + 1] = linea end
        p:close()
    end
    return nombres
end

local function raices_en_contenedores()
    if es_windows() then return {} end
    local raices = {}
    local base = home() .. "/Library/Containers"
    for _, nombre in ipairs(listar_dir(base)) do
        local minus = nombre:lower()
        if minus:find("blackmagic", 1, true) or minus:find("davinci", 1, true) then
            table.insert(raices, base .. "/" .. nombre
                .. "/Data/Library/Application Support/Blackmagic Design"
                .. "/DaVinci Resolve/Fusion/Scripts")
        end
    end
    return raices
end

local function carpetas_posibles()
    local lista = {}

    -- 1. La carpeta de donde Resolve cargo ESTE script. Va primero porque es
    --    el dato mas fiable que hay: no es una suposicion ni una nota de
    --    otro proceso, es de donde el propio Resolve nos acaba de leer. En
    --    Mac el instalador podia anotar una carpeta que Resolve no mira (la
    --    de fuera del contenedor de sandbox), y entonces scripts_dir.txt
    --    mandaba a buscar al sitio equivocado.
    local fuente = debug and debug.getinfo and debug.getinfo(1, "S")
    if fuente and fuente.source then
        local ruta = fuente.source:gsub("^@", "")
        local dir = ruta:match("^(.*)[/\\][^/\\]+$")
        if dir then table.insert(lista, dir) end
    end

    -- 2. Lo que la app dejo escrito al instalar.
    local apuntada = leer(ARCHIVO_CARPETA_SCRIPTS)
    if apuntada then
        apuntada = apuntada:gsub("^%s+", ""):gsub("%s+$", "")
        if apuntada ~= "" then table.insert(lista, apuntada) end
    end

    -- 3. Respaldo: las raices conocidas, con todas sus subcarpetas.
    if es_windows() then
        local appdata = os.getenv("APPDATA") or ""
        local programdata = os.getenv("PROGRAMDATA") or "C:\\ProgramData"
        if appdata ~= "" then
            agregar_raiz(lista, appdata .. "\\Blackmagic Design\\DaVinci Resolve\\Support\\Fusion\\Scripts")
        end
        agregar_raiz(lista, programdata .. "\\Blackmagic Design\\DaVinci Resolve\\Fusion\\Scripts")
    else
        local soporte = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts"
        agregar_raiz(lista, home() .. soporte)
        agregar_raiz(lista, soporte)
        for _, raiz in ipairs(raices_en_contenedores()) do
            agregar_raiz(lista, raiz)
        end
    end
    return lista
end

-- Donde esta AHORA MISMO el script que necesitamos.
--
-- OJO: se busca EL script que hace falta, no siempre CineCaptions_Subtitulos.lua, y
-- se busca en el momento de usarlo, no una sola vez al arrancar. Antes se
-- resolvia la carpeta al inicio y quedaba cacheada para toda la sesion; si
-- despues los archivos se movian (una actualizacion del programa instala en
-- una carpeta y limpia la otra), el Puente seguia apuntando a la carpeta
-- vieja y TODOS los botones fallaban con "No encuentro el script", aunque
-- el menu de Resolve siguiera mostrandolos (Resolve arma ese menu al
-- arrancar y no lo vuelve a mirar).
local function carpeta_de_scripts(nombre_script)
    nombre_script = nombre_script or SCRIPTS.subtitulos
    for _, c in ipairs(carpetas_posibles()) do
        if existe(c .. SEP .. nombre_script) then return c end
    end
    return nil
end

-- ---------------------------------------------------------------------
-- Ejecutar una accion (corriendo su script .lua)
-- ---------------------------------------------------------------------
local function correr_accion(accion, dir_scripts)
    local nombre = SCRIPTS[accion]
    if not nombre then
        return false, "Accion desconocida: " .. tostring(accion)
    end

    -- La carpeta que traiamos es solo una pista. Si el script no esta ahi
    -- (nos actualizaron por debajo, o arrancamos desde una carpeta que
    -- despues se limpio), lo buscamos de nuevo antes de dar por perdido.
    local ruta = dir_scripts and (dir_scripts .. SEP .. nombre)
    if not ruta or not existe(ruta) then
        local encontrada = carpeta_de_scripts(nombre)
        if not encontrada then
            local buscadas = table.concat(carpetas_posibles(), "\n    ")
            -- La version va en el mensaje a proposito: si algo vuelve a
            -- fallar, un solo screenshot alcanza para saber que Puente
            -- estaba corriendo. Deducirlo a mano costo una sesion entera.
            return false, ("No encuentro " .. nombre .. " (Puente " .. VERSION
                           .. "). Busque en:\n    " .. buscadas)
        end
        ruta = encontrada .. SEP .. nombre
    end
    -- dofile ejecuta el script completo (incluye su propio pcall(main)).
    -- El script lee su input de los archivos que la app dejo; el 'resolve'
    -- global lo hereda de este contexto.
    --
    -- Y ademas se le PRESTA el resolve validado del arranque: en Free
    -- >=19.1 Resolve()/bmd.scriptapp no responden (via externa cerrada),
    -- asi que si algo pisa el global 'resolve', el script no tiene de
    -- donde sacar otro -era el "Encontre Resolve pero no me respondio"
    -- con el proyecto abierto delante-. Se revalida ANTES de publicarlo:
    -- un objeto muerto no se presta, se avisa.
    CINECAPTIONS_BAJO_PUENTE = true

    -- El handle capturado al arrancar CADUCA solo en el Free (medido el
    -- 01-09: vivo a las 9:15, muerto a las 9:41 en el mismo Puente sin
    -- tocar nada) y un lanzamiento fresco lo revive. Antes de rendirse,
    -- se intenta ADOPTAR el global 'resolve' actual de esta sesion.
    local function con_pm(r)
        if r == nil then return false end
        local ok_pm, pm = pcall(function() return r:GetProjectManager() end)
        return ok_pm and pm ~= nil
    end
    if not con_pm(RESOLVE_BUENO) then
        local ok_g, g = pcall(function() return resolve end)
        if ok_g and con_pm(g) then
            RESOLVE_BUENO = g
        else
            local g2 = type(_G) == "table" and rawget(_G, "resolve") or nil
            if con_pm(g2) then RESOLVE_BUENO = g2 end
        end
    end
    local vivo = con_pm(RESOLVE_BUENO)

    -- Estas globales quedan SOLO de compatibilidad: medido el 01-09, en
    -- el Lua de Resolve NO cruzan el dofile (entornos aislados por
    -- script; el diagnostico del cliente mostro candidatos: 3 sin rastro
    -- del prestamo, con este Puente latiendo al lado). El canal que SI
    -- llega es el argumento del chunk, mas abajo.
    CINECAPTIONS_RESOLVE_DEL_PUENTE = vivo and RESOLVE_BUENO or nil
    CINECAPTIONS_SESION_MUERTA = (RESOLVE_BUENO ~= nil) and (not vivo) or false

    if not vivo then
        -- Sin un handle vivo el script solo puede producir el mensaje
        -- generico de siempre. El consejo real viaja directo en la
        -- respuesta del trabajo, sin correr nada: relanzar el Puente da
        -- un handle fresco (medido: lo que el cliente hacia por instinto
        -- y SI le funcionaba).
        return false, "El Puente perdio su conexion con Resolve (caduca "
            .. "sola en la version gratuita). Vuelve a lanzar CineCaptions_Puente "
            .. "(Area de trabajo > Scripts > Utility): el nuevo me releva "
            .. "solo y llega con conexion fresca. Despues genera de "
            .. "nuevo. Si sigue pasando, cierra DaVinci Resolve por "
            .. "completo y abrelo otra vez."
    end

    -- La ENTREGA EN MANO (v1.0.43): el resolve validado viaja como
    -- argumento del chunk — los chunks de Lua reciben varargs — porque
    -- es el unico canal en-banda que sobrevive a los entornos aislados.
    -- Un script viejo que no lea argumentos los ignora sin efecto.
    local chunk = nil
    pcall(function() chunk = loadfile(ruta) end)
    if chunk == nil then
        -- loadfile capado o archivo ilegible: el dofile de siempre, sin
        -- entrega (el script usara su global 'resolve', que esta vivo).
        local ok, err = pcall(dofile, ruta)
        if ok then return true, "" end
        return false, tostring(err)
    end
    local ok, err = pcall(chunk, {
        resolve = RESOLVE_BUENO, puente = VERSION, paquete = PAQUETE })
    -- Modo señales: el script no pudo escribir ultimo_resultado.* y DEVUELVE
    -- su reporte "CINECAPTIONS_REPORTE|json" (un script viejo lo lanzaria por
    -- error(): se acepta igual). Se relata al registro de Resolve TAL CUAL
    -- -la app lo lee como si el script se hubiera pulsado a mano- y el
    -- veredicto sale del json. Un script que muere sin reporte (uno que
    -- todavia use io) se relata como fallo, con su error, para que llegue.
    local reporte = nil
    if type(err) == "string" then
        local pos = err:find("CINECAPTIONS_REPORTE|", 1, true)
        if pos then reporte = err:sub(pos) end
    end
    if reporte then
        relatar(reporte)
        local ok_rep = reporte:match('"ok":%s*(%a+)') == "true"
        return ok_rep, json_string(reporte, "mensaje") or ""
    end
    if ok then return true, "" end
    if SIN_IO then
        relatar("CINECAPTIONS_REPORTE|" .. string.format(
            '{"script": "%s", "version": "%s (puente)", "ok": false, '
            .. '"mensaje": "%s", "cuando": %d}',
            json_escapar(nombre), json_escapar(PAQUETE),
            json_escapar(tostring(err)), os.time()))
    end
    return false, tostring(err)
end

local function responder(job_id, ok, mensaje)
    if SIN_IO then
        -- La respuesta es una señal cuyo NOMBRE lleva el veredicto y un
        -- resumen corto, sin los caracteres que Windows prohibe en un
        -- nombre; el detalle ya viajo por el registro (correr_accion). La
        -- app la recoge y la borra (_encolar).
        local corto = (tostring(mensaje or ""):gsub('[\\/:%*%?"<>|\r\n\t]', " "))
        corto = (corto:gsub("%s+", " "):gsub("^%s+", ""):gsub("%s+$", ""))
        senal(CARPETA_JOBS .. SEP .. job_id .. ".hecho." .. (ok and "ok" or "err")
              .. "." .. corto:sub(1, 120))
        return
    end
    -- json_escapar, no el gsub de comillas de antes: un mensaje con una ruta
    -- de Windows (barras) producia JSON invalido y la app giraba hasta el
    -- timeout en vez de mostrar el error (hallazgo del inventario, 16-09).
    local ruta = CARPETA_JOBS .. SEP .. job_id .. ".done.json"
    escribir(ruta, string.format(
        '{"id": "%s", "ok": %s, "mensaje": "%s", "version": "%s", '
        .. '"paquete": "%s", "respondido_en": %d}',
        job_id, tostring(ok), json_escapar(mensaje or ""),
        VERSION, PAQUETE, os.time()))
end

-- ---------------------------------------------------------------------
-- Lock: no correr dos Puentes al mismo tiempo
-- ---------------------------------------------------------------------
-- Antes se podia correr el Puente desde las dos carpetas del menu
-- (usuario y sistema, cuando el instalador copiaba a ambas). Los dos
-- vigilaban la misma carpeta jobs/, se peleaban los mismos trabajos
-- (rename atomico + "Accion desconocida: nil"), y disparaban renders
-- simultaneos que chocaban ("No pude arrancar el render").
--
-- Esta comprobacion detecta si ya hay OTRO Puente vivo (heartbeat fresco)
-- y sale sin quedar residente. La app puede seguir usando el que ya esta.
local LATIDO_MAXIMO_S = 12

local function ya_hay_puente_activo()
    -- Modo señales: el latido no se puede leer (ni contenido ni fecha). El
    -- relevo va por la señal puente.relevo (ver main).
    if SIN_IO then return false end
    local contenido = leer(LATIDO)
    if not contenido then return false end
    -- El latido es "<hora>|<version>", pero uno de una version anterior
    -- trae solo "<hora>". Nos quedamos con lo de antes del '|' y aceptamos
    -- los dos formatos: si no, al actualizar quedarian dos Puentes vivos.
    --
    -- OJO: gsub devuelve DOS valores (string y contador). tonumber tomaria
    -- el segundo como base. Los parentesis fuerzan un solo valor.
    local hora = contenido:match("^([^|]*)") or contenido
    local anterior = tonumber((hora:gsub("%s+$", "")))
    if not anterior then return false end
    local edad = os.time() - anterior
    return edad >= 0 and edad <= LATIDO_MAXIMO_S
end

-- ---------------------------------------------------------------------
-- Main
-- ---------------------------------------------------------------------
local function main()
    -- Que globales de Lua hay, ANTES que nada: marcar() ya necesita io, y si
    -- este Resolve no lo da, lo unico que se puede hacer es decirlo. 21.1
    -- quito package sin avisar (ver es_windows); lo proximo que quite tiene
    -- que verse en la primera linea de la ventana, no en otra ronda a ciegas.
    print("  " .. globales_lua())
    -- Sin io (Free 21.1) el Puente ya no se rinde: pasa al modo SEÑALES (ver
    -- SIN_IO). Ahi las señales las escribe Resolve, asi que la huella de
    -- arranque -que con io va PRIMERO- tiene que esperar a validarlo.
    if SIN_IO then
        print("[Puente] Este Resolve no da 'io' a los scripts del menu: modo SEÑALES.")
    else
        -- La huella va PRIMERO, antes de validar nada: sin ella no hay forma
        -- de saber si el usuario llego a pulsar el script (ver ARRANQUE).
        marcar("arrancando")
    end

    -- Validar DE VERDAD, no solo ~= nil: un 'resolve' presente pero sin
    -- GetProjectManager es el objeto hueco de siempre, y quedarse residente
    -- con el seria repartir un objeto muerto a cada script que venga.
    local pm = nil
    if resolve ~= nil then
        pcall(function() pm = resolve:GetProjectManager() end)
    end
    if resolve == nil or pm == nil then
        if not SIN_IO then marcar("sin_resolve") end
        print("[Puente] ERROR: corre este script DESDE Resolve:")
        print("         Area de trabajo > Scripts > Utility > CineCaptions_Puente")
        if resolve ~= nil then
            print("[Puente] (habia un objeto 'resolve' pero no respondio: "
                  .. "reinicia Resolve y vuelve a lanzarme)")
        end
        if SIN_IO then
            -- Sin canal todavia: el unico sitio que llega es el registro.
            error("CINECAPTIONS_REPORTE|" .. json_reporte(false,
                "Resolve no le respondio al Puente (GetProjectManager vacio). "
                .. "Reinicia Resolve y vuelve a lanzar CineCaptions_Puente.",
                ', "arranque": "sin_resolve"'), 0)
        end
        return
    end
    RESOLVE_BUENO = resolve

    if SIN_IO then
        -- El canal de señales: el preset de teclado ACTUAL (o el primero de
        -- la lista). Se prueba con el propio latido; sin canal no hay Puente
        -- posible y se dice por el unico sitio que llega: el registro.
        pcall(function() KB_PRESET = resolve:GetCurrentKeyboardPreset() end)
        if type(KB_PRESET) ~= "string" or KB_PRESET == "" then
            pcall(function()
                KB_PRESET = (resolve:GetKeyboardPresetList() or {})[1]
            end)
        end
        if type(KB_PRESET) ~= "string" or KB_PRESET == "" then KB_PRESET = nil end
        if not (KB_PRESET and CAP.fileexists and senal(LATIDO) and existe(LATIDO)) then
            print("[Puente] ERROR: sin 'io' y sin poder escribir una señal")
            print("         (ExportKeyboardPreset). Usa CineCaptions_DetectarVideo y")
            print("         CineCaptions_Subtitulos a mano: esos si funcionan.")
            error("CINECAPTIONS_REPORTE|" .. json_reporte(false,
                "Este Resolve no deja escribir al Puente (ni io ni señales). "
                .. "Usa CineCaptions_DetectarVideo y CineCaptions_Subtitulos a mano desde el menu.",
                ', "arranque": "sin_canal"'), 0)
        end
        marcar("arrancando")
    end

    -- Sin primitiva de espera, sondear cuatro veces por segundo cuesta un
    -- nucleo entero. Se espacia (ver INTERVALO_SIN_ESPERA).
    if not HAY_BMD_WAIT then
        INTERVALO = INTERVALO_SIN_ESPERA
    end

    crear_dir(CARPETA_JOBS)

    if SIN_IO then
        -- El relevo en modo señales: no se puede leer el latido del
        -- residente anterior, asi que se le deja la señal puente.relevo y se
        -- sigue a los 3 s. El bucle la ignora mientras sea la mia (hasta que
        -- la app la borre) y obedece cualquier otra. Con dos Puentes
        -- lanzados SIN la app corriendo el segundo no se entera: no lances
        -- dos (lo dice el banner).
        senal(RELEVO)
        RELEVO_MIO = true
        dormir(3)
    elseif ya_hay_puente_activo() then
        -- EL RELEVO (v1.0.30). Antes este candado se retiraba y dejaba al
        -- residente viejo en el trono: el cliente "relanzaba el Puente"
        -- (el consejo de todos los mensajes) y no cambiaba NADA, porque
        -- el nuevo se iba y el viejo -con su conexion caducada- seguia
        -- atendiendo los trabajos (caso real, 01-09). El viejo ya obedece
        -- puente.stop en cada vuelta de su bucle: se le pide el turno.
        print(string.rep("=", 58))
        print("  CineCaptions_Puente  |  " .. VERSION .. "  |  del programa v" .. PAQUETE)
        print(string.rep("=", 58))
        print("")
        print("  Un Puente anterior sigue corriendo: le pido el relevo...")
        escribir(STOP, MI_TOKEN)
        local esperado = 0
        while esperado < RELEVO_MAXIMO_S and ya_hay_puente_activo() do
            dormir(0.5)
            esperado = esperado + 0.5
        end
        if ya_hay_puente_activo() then
            -- No suelta el turno: estara bloqueado dentro de un trabajo
            -- largo (ahi no puede mirar el STOP). Solo se borra MI orden
            -- -un STOP ajeno no es mio y no se toca- y se explica.
            local orden = leer(STOP)
            if orden and orden:gsub("%s+$", "") == MI_TOKEN then
                os.remove(STOP)
            end
            print("")
            print("  El Puente anterior no suelta el turno (puede estar a")
            print("  mitad de un trabajo largo). Espera a que termine y")
            print("  vuelve a lanzar CineCaptions_Puente; si sigue asi, cierra")
            print("  DaVinci Resolve por completo y abrelo de nuevo.")
            marcar("relevo_fallido")
            return
        end
        print("  Relevo hecho: el Puente anterior se retiro. Sigo yo.")
        -- OJO: si el latido murio sin que el STOP se consumiera (el viejo
        -- esta bloqueado en dofile y su latido caduco), el archivo queda
        -- A PROPOSITO con MI_TOKEN: cuando el viejo despierte lo vera y
        -- se ira solo. Antes ese caso dejaba DOS Puentes vivos peleandose
        -- los trabajos. Mi bucle ignora el token propio.
    else
        -- Nadie latiendo: un puente.stop huerfano de otra sesion se tira,
        -- o mataria a ESTE Puente en su primera vuelta.
        os.remove(STOP)
    end

    -- Tirar lo que quedara de una sesion anterior. Con nombres fijos no hay
    -- que listar la carpeta: dos os.remove y listo. (Modo señales: no se
    -- puede borrar; tomar_trabajo ignora un pendiente de hace mas de 5 min
    -- y la app limpia lo suyo.)
    if not SIN_IO then
        os.remove(JOB_PENDIENTE)
        os.remove(JOB_TOMADO)
    end

    -- Pista inicial nada mas: cada trabajo vuelve a comprobar donde esta
    -- realmente su script (ver carpeta_de_scripts).
    local dir_scripts = carpeta_de_scripts()

    print(string.rep("=", 58))
    print("  CineCaptions_Puente  |  " .. VERSION .. "  |  del programa v" .. PAQUETE)
    print(string.rep("=", 58))
    print("")
    print("  (El número del Puente va aparte del programa: solo cambia")
    print("   cuando cambia el protocolo. Este es el que trae la v" .. PAQUETE .. ".)")
    print("")
    print("  Puente ACTIVO. Ya puedes usar el programa normalmente:")
    print("  los botones van a ejecutarse solos.")
    print("")
    -- La carpeta compartida, SIEMPRE: si no es la misma que dice el
    -- programa en su aviso, el Puente esta latiendo donde nadie lo mira
    -- (el bug de la v3.1.1) y se ve de un vistazo en cualquier captura.
    print("  Carpeta de trabajo: " .. CARPETA)
    print("  Carpeta de scripts: " .. (dir_scripts or "(la busco al usarla)"))
    -- La linea de capacidades va SIEMPRE, tenga o no problemas: es lo que
    -- convierte el proximo reporte en un screenshot en vez de en otra sesion
    -- de diagnostico a ciegas.
    print("  " .. capacidades()
          .. (ESPERA_NOMBRE and ("  |  espera: " .. ESPERA_NOMBRE) or ""))
    print("  Deja esta ventana abierta mientras trabajas.")
    if SIN_IO then
        print("  Modo señales (este Resolve no da 'io'): latido y respuestas van")
        print("  por ExportKeyboardPreset y el registro de Resolve. No lances")
        print("  dos Puentes a la vez.")
    end
    if not HAY_BMD_WAIT then
        print("")
        print(string.rep("*", 58))
        print("  AVISO IMPORTANTE")
        print("")
        print("  Este Resolve no expone ninguna funcion de espera, asi que")
        print("  el Puente tiene que dar vueltas en un bucle. Eso mantiene")
        print("  UN NUCLEO DE CPU AL 100% mientras esta abierto, y puede")
        print("  hacer que Resolve vaya a tirones.")
        print("")
        print("  Todo funciona igual. Pero CIERRA ESTA VENTANA en cuanto")
        print("  termines de colocar subtitulos.")
        print("")
        print("  (Ya se subio el intervalo de sondeo a " .. INTERVALO
              .. " s para que moleste menos.)")
        print(string.rep("*", 58))
    end
    print("")

    -- Antes del primer latido: si latir() falla, el lo reescribe a
    -- "sin_latido" y gana el suyo.
    marcar("ok")
    latir()
    local ultimo_latido = os.time()
    local ultima_actividad = os.time()
    local atendidos = 0

    while true do
        local ahora = os.time()

        if SIN_IO then
            -- puente.relevo: mio hasta que la app lo borre; despues, de otro.
            local hay = existe(RELEVO)
            if not hay then
                RELEVO_MIO = false
            elseif not RELEVO_MIO then
                print("[Puente] Un Puente mas nuevo pide el relevo. Chau.")
                reportar(true, "Puente relevado por otro mas nuevo",
                         ', "arranque": "relevado"')
                break
            end
        elseif existe(STOP) then
            local orden = leer(STOP)
            if not orden or orden:gsub("%s+$", "") ~= MI_TOKEN then
                print("[Puente] Recibi la orden de apagado (o el relevo "
                      .. "de un Puente mas nuevo). Chau.")
                os.remove(STOP)
                break
            end
            -- Un STOP con MI token es la orden que le deje al residente
            -- anterior colgado: no es para mi y NO se borra — el viejo la
            -- consume cuando despierte de su dofile.
        end

        if ahora - ultimo_latido >= LATIDO_CADA then
            latir()
            ultimo_latido = ahora
        end

        if ahora - ultima_actividad > INACTIVIDAD_MAX then
            print("[Puente] Muchas horas sin trabajos. Me apago.")
            break
        end

        local job_id, accion = tomar_trabajo()
        if job_id == nil then
            dormir(INTERVALO)
        else
            if not accion then
                -- Trabajo ilegible o sin accion. Respondemos con un mensaje
                -- util y seguimos.
                responder(job_id, false, "trabajo sin campo 'accion' o ilegible")
            else
                print("\n[Puente] -> " .. tostring(accion))
                local ok, mensaje = correr_accion(accion, dir_scripts)
                print("[Puente] " .. (ok and "OK" or
                      ("FALLO: " .. tostring(mensaje))))
                responder(job_id, ok, mensaje)
            end

            -- El .tomado se borra AQUI, cuando el trabajo YA termino.
            --
            -- Antes se borraba justo antes de ejecutar, y eso dejaba a la app
            -- sin ninguna senal de que hubiera algo en marcha. Mientras corre
            -- el trabajo el Puente esta bloqueado dentro de dofile y no puede
            -- latir; la app daba el Puente por muerto a los 12 segundos y
            -- cancelaba, aunque el trabajo siguiera avanzando. Colocar 80-124
            -- Text+ o renderizar el audio tarda mucho mas que eso, asi que
            -- practicamente todo trabajo real se cancelaba solo, y la unica
            -- forma de que saliera era correr los scripts a mano desde el
            -- menu. Con el .tomado presente, la app sabe que hay trabajo en
            -- curso y espera. (Modo señales: lo borra la app al recoger la
            -- señal .hecho; aqui no se puede.)
            if not SIN_IO then os.remove(JOB_TOMADO) end

            atendidos = atendidos + 1
            ultima_actividad = os.time()
            latir()
            ultimo_latido = os.time()
        end
    end

    if SIN_IO then
        -- El latido no se puede borrar: envejece solo. El cierre se relata.
        reportar(true, "Puente cerrado. Trabajos atendidos: " .. atendidos,
                 ', "arranque": "cerrado"')
    else
        os.remove(LATIDO)
    end
    print("\n[Puente] Cerrado. Trabajos atendidos: " .. atendidos .. ".")
end

-- Que una muerte a mitad NO sea muda (v3.1.10, 17-09). Hasta la v3.1.9 esto
-- era main() a pelo: un error dentro salia al host de Resolve como una linea
-- Lua cualquiera -sin CINECAPTIONS_REPORTE-, y la app solo veia la huella anterior
-- («arrancando»: SE QUEDO A MEDIAS) sin poder decir DONDE. Asi llego el caso
-- del Mac Free 21.1, que costo una ronda entera de lectura de codigo. Ahora
-- el error viaja con su archivo y su linea por el unico canal que sale, y se
-- relanza para que Resolve lo registre igual.
local ok_main, err_main = pcall(main)
if not ok_main then
    local detalle = tostring(err_main)
    print("[Puente] ERROR: murio a mitad: " .. detalle)
    if SIN_IO then
        reportar(false, "El Puente murio a mitad: " .. detalle,
                 ', "arranque": "murio"')
    else
        escribir(ARRANQUE, os.time() .. "|" .. VERSION .. "|murio")
    end
    error(err_main, 0)
end
