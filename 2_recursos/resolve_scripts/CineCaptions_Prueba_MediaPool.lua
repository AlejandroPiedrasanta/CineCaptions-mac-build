-- CineCaptions · By Cinema Productions
-- 2_recursos/resolve_scripts/CineCaptions_Prueba_MediaPool.lua — herramienta de prueba: comprueba si se puede meter un Text+ al Media Pool.
--[[
CineCaptions_Prueba_MediaPool.lua
------------------------
PRUEBA, no es parte del programa. Contesta la unica pregunta que hoy decide
si los subtitulos automaticos salen o no en TU version de Resolve:

  ¿Se puede meter un Text+ en el Media Pool por script?

Todo el producto depende de eso. Un Text+ del Media Pool es lo unico que
AppendToTimeline acepta para colocar un subtitulo; sin ninguno, no hay nada
que colocar. Y hay dos caminos posibles, los dos sin garantia:

  A. Crear uno: timeline:InsertFusionTitleIntoTimeline / ...Generator...
     y quedarse con su MediaPoolItem.
  B. Importar el pack (.drt) y quedarse con los clips que Resolve deje
     sueltos en el Media Pool.

En Studio funciona A. En Free, GetMediaPoolItem() no promueve, asi que todo
cuelga de si Resolve deja algo suelto — y eso no esta documentado en ningun
sitio. Esta prueba lo mide en tu equipo, en vez de suponerlo.

COMO SE CORRE
=============
1. Abre un proyecto DE PRUEBA (no uno de trabajo) con un timeline abierto.
   Puede estar vacio: es justo el caso interesante.
2. Copia este archivo a la carpeta de Scripts de Resolve:
     Windows: %APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility
     macOS:   ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility
3. Area de trabajo > Scripts > Utility > CineCaptions_Prueba_MediaPool
4. Mandame el archivo que deja en:
     ~/DaVinciSubtitles/prueba_mediapool.txt

Lo que toca y lo que no: inserta un titulo en una zona VACIA del timeline
(5 s despues del ultimo clip) y lo borra; importa el pack .drt como un
timeline nuevo y lo deja marcado para que lo borres tu. NO borra nada tuyo,
NO toca tus proyectos guardados y NO instala nada.
]]

local VERSION = "1.1"

-- ---------------------------------------------------------------------
-- Utilidades (mismo criterio que el resto de los scripts del proyecto)
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

local function carpeta_compartida()
    return home() .. SEP .. "DaVinciSubtitles"
end

local lineas = {}
local function apuntar(texto)
    lineas[#lineas + 1] = tostring(texto)
    print(texto)
end

-- Las listas de la API traen una clave extra 'n'. pairs() la devuelve como
-- elemento y revienta; ipairs + filtro es la forma segura (misma trampa que
-- documenta el resto del proyecto).
local function lista_api(lista)
    local fuera = {}
    if type(lista) ~= "table" then return fuera end
    for i = 1, (#lista or 0) do
        if lista[i] ~= nil then fuera[#fuera + 1] = lista[i] end
    end
    return fuera
end

-- ---------------------------------------------------------------------
-- Conexion (el mismo orden que usan los scripts de verdad)
-- ---------------------------------------------------------------------
local function obtener_resolve()
    -- El Puente presta su resolve validado; se prueba PRIMERO.
    local candidatos = {}
    if type(_G) == "table" and rawget(_G, "CINECAPTIONS_RESOLVE_DEL_PUENTE") ~= nil then
        candidatos[#candidatos + 1] = CINECAPTIONS_RESOLVE_DEL_PUENTE
    end
    if resolve ~= nil then candidatos[#candidatos + 1] = resolve end
    if type(_G) == "table" and rawget(_G, "resolve") ~= nil then
        candidatos[#candidatos + 1] = rawget(_G, "resolve")
    end
    local ok, r = pcall(function() return Resolve() end)
    if ok and r then candidatos[#candidatos + 1] = r end
    ok, r = pcall(function() return bmd.scriptapp("Resolve") end)
    if ok and r then candidatos[#candidatos + 1] = r end

    for _, cand in ipairs(candidatos) do
        local vivo = false
        pcall(function() vivo = cand:GetProjectManager() ~= nil end)
        if vivo then return cand end
    end
    return nil
end

local function frame_a_timecode(frame, fps)
    local f = math.floor(fps + 0.5)
    if f < 1 then f = 30 end
    local total = math.max(0, math.floor(frame))
    local h = math.floor(total / (3600 * f))
    local resto = total % (3600 * f)
    local m = math.floor(resto / (60 * f))
    resto = resto % (60 * f)
    local s = math.floor(resto / f)
    return string.format("%02d:%02d:%02d:%02d", h, m, s, resto % f)
end

-- Foto del Media Pool entero: {nombre = cuantos}. Por NOMBRE, porque cada
-- GetClipList() devuelve envoltorios NUEVOS y comparar objetos no sirve.
local function foto_del_pool(media_pool)
    local mapa, total = {}, 0
    local ok, raiz = pcall(function() return media_pool:GetRootFolder() end)
    if not ok or not raiz then return mapa, total end
    local function recorrer(folder)
        for _, clip in ipairs(lista_api(folder:GetClipList())) do
            local ok_n, nom = pcall(function() return clip:GetName() end)
            local clave = (ok_n and nom) and nom or "?"
            mapa[clave] = (mapa[clave] or 0) + 1
            total = total + 1
        end
        for _, sub in ipairs(lista_api(folder:GetSubFolderList())) do
            recorrer(sub)
        end
    end
    pcall(function() recorrer(raiz) end)
    return mapa, total
end

local function nuevos_desde(antes, despues)
    local fuera = {}
    for nombre, cuantos in pairs(despues) do
        local diferencia = cuantos - (antes[nombre] or 0)
        if diferencia > 0 then
            fuera[#fuera + 1] = { nombre = nombre, cuantos = diferencia }
        end
    end
    table.sort(fuera, function(a, b) return a.nombre < b.nombre end)
    return fuera
end

-- ---------------------------------------------------------------------
local function main()
    apuntar("CineCaptions_Prueba_MediaPool " .. VERSION)
    apuntar(string.rep("=", 58))

    local res = obtener_resolve()
    if not res then
        apuntar("NO pude hablar con Resolve. Si estas en Free, lanza primero "
                .. "CineCaptions_Puente y vuelve a correr esta prueba.")
        return
    end

    local pm, proyecto, timeline, media_pool
    pcall(function() pm = res:GetProjectManager() end)
    pcall(function() proyecto = pm:GetCurrentProject() end)
    if not proyecto then
        apuntar("Hay Resolve pero no hay proyecto abierto. Abre uno de prueba.")
        return
    end
    pcall(function() timeline = proyecto:GetCurrentTimeline() end)
    pcall(function() media_pool = proyecto:GetMediaPool() end)
    if not timeline or not media_pool then
        apuntar("Falta el timeline o el Media Pool. Abre un timeline (puede "
                .. "estar vacio) y vuelve a correr la prueba.")
        return
    end

    local nombre_prod = "?"
    pcall(function() nombre_prod = res:GetProductName() end)
    local version_res = "?"
    pcall(function() version_res = res:GetVersionString() end)
    apuntar("Resolve      : " .. tostring(nombre_prod) .. "  "
            .. tostring(version_res))
    local bajo_puente = (type(_G) == "table" and rawget(_G, "CINECAPTIONS_BAJO_PUENTE")) and "si" or "no"
    apuntar("Bajo el Puente: " .. bajo_puente)

    local _, cuantos_antes = foto_del_pool(media_pool)
    apuntar("Clips en el Media Pool al empezar: " .. cuantos_antes)
    apuntar("")

    -- ---------------------------------------------------------------
    apuntar("A. CREAR un Text+ e intentar quedarselo")
    apuntar(string.rep("-", 58))

    local fps = 30.0
    pcall(function()
        fps = tonumber(timeline:GetSetting("timelineFrameRate")) or 30.0
    end)
    local tc_original = nil
    pcall(function() tc_original = timeline:GetCurrentTimecode() end)
    local fin = 0
    pcall(function() fin = tonumber(timeline:GetEndFrame()) or 0 end)
    local zona = math.floor(fin) + math.floor(5 * fps + 0.5)
    pcall(function()
        timeline:SetCurrentTimecode(frame_a_timecode(zona, fps))
    end)

    for _, metodo in ipairs({ "InsertFusionTitleIntoTimeline",
                              "InsertFusionGeneratorIntoTimeline" }) do
        -- OJO: rawget solo acepta TABLAS, y 'timeline' es un userdata de
        -- Resolve — rawget(timeline, ...) REVENTABA la sonda entera aqui
        -- mismo (medido en produccion, 02-09: "bad argument #1 to
        -- 'rawget'"), y las secciones B/C/D no corrian nunca. La regla del
        -- CLAUDE.md: indexar bajo pcall y mirar el type del resultado.
        local tipo_metodo = "?"
        pcall(function() tipo_metodo = type(timeline[metodo]) end)
        for _, nombre in ipairs({ "Text+", "Texto+", "Text" }) do
            local antes = foto_del_pool(media_pool)
            local ok, item = pcall(function()
                return timeline[metodo](timeline, nombre)
            end)
            local detalle = string.format("  %s('%s')", metodo, nombre)
            if not ok then
                apuntar(detalle .. " -> ERROR: " .. tostring(item))
            elseif not item then
                apuntar(detalle .. " -> no devolvio nada")
            else
                local mpi = nil
                pcall(function() mpi = item:GetMediaPoolItem() end)
                local despues = foto_del_pool(media_pool)
                local aparecidos = nuevos_desde(antes, despues)
                local texto = detalle .. " -> INSERTO. GetMediaPoolItem: "
                    .. (mpi and "SI (promueve)" or "NO (no promueve)")
                apuntar(texto)
                if #aparecidos > 0 then
                    for _, n in ipairs(aparecidos) do
                        apuntar(string.format(
                            "      y dejo en el Media Pool: '%s' x%d",
                            n.nombre, n.cuantos))
                    end
                else
                    apuntar("      y NO dejo nada nuevo en el Media Pool")
                end
                pcall(function() timeline:DeleteClips({ item }) end)
                local tras_borrar = foto_del_pool(media_pool)
                local tras = nuevos_desde(antes, tras_borrar)
                if #tras > 0 then
                    for _, n in ipairs(tras) do
                        apuntar(string.format(
                            "      tras borrar el clip queda: '%s' x%d",
                            n.nombre, n.cuantos))
                    end
                else
                    apuntar("      tras borrar el clip no queda nada")
                end
            end
        end
        apuntar("  (type(timeline." .. metodo .. ") = " .. tipo_metodo .. ")")
    end
    if tc_original then
        pcall(function() timeline:SetCurrentTimecode(tc_original) end)
    end
    apuntar("")

    -- ---------------------------------------------------------------
    apuntar("B. IMPORTAR el pack .drt y ver que deja en el Media Pool")
    apuntar(string.rep("-", 58))

    -- La ruta del .drt: manda prueba_drt.txt si existe; si no (v1.1), se
    -- busca SOLO en las rutas de la app instalada — la primera corrida
    -- real salto esta seccion por pedir un paso manual que nadie hizo.
    local ruta_drt = nil
    local f = io.open(carpeta_compartida() .. SEP .. "prueba_drt.txt", "r")
    if f then
        ruta_drt = (f:read("*a") or ""):gsub("%s+$", "")
        f:close()
    end
    if not ruta_drt or ruta_drt == "" then
        local candidatas = {}
        -- El cuadrado se retiro del pack incorporado en la v1.0.55
        -- (pedido del usuario): solo quedan estos dos candidatos.
        local nombres_drt = { "Base titulos dinamicos vertical.drt",
                              "Base titulos dinamicos Horizontal.drt" }
        local appdata = os.getenv("APPDATA")
        for _, n in ipairs(nombres_drt) do
            if appdata then
                candidatas[#candidatas + 1] = appdata
                    .. "\\CineCaptions\\_internal"
                    .. "\\plantillas_incluidas\\" .. n
            end
            candidatas[#candidatas + 1] =
                "/Applications/CineCaptions.app/Contents"
                .. "/Frameworks/plantillas_incluidas/" .. n
        end
        for _, ruta in ipairs(candidatas) do
            local fa = io.open(ruta, "rb")
            if fa then
                fa:close()
                ruta_drt = ruta
                break
            end
        end
        if ruta_drt then
            apuntar("  (.drt del programa encontrado solo)")
        end
    end
    if not ruta_drt or ruta_drt == "" then
        apuntar("  Salto la prueba B: no encontre ningun .drt del programa")
        apuntar("  (¿esta instalado?). Puedes pasar una ruta a mano en:")
        apuntar("    " .. carpeta_compartida() .. SEP .. "prueba_drt.txt")
    else
        apuntar("  Pack: " .. ruta_drt)
        local carpeta_previa = nil
        pcall(function() carpeta_previa = media_pool:GetCurrentFolder() end)
        pcall(function()
            media_pool:SetCurrentFolder(media_pool:GetRootFolder())
        end)
        local antes = foto_del_pool(media_pool)
        local ok, importado = pcall(function()
            return media_pool:ImportTimelineFromFile(ruta_drt)
        end)
        if not ok or not importado then
            apuntar("  ImportTimelineFromFile -> FALLO: " .. tostring(importado))
        else
            apuntar("  ImportTimelineFromFile -> OK (timeline importado)")
            local despues = foto_del_pool(media_pool)
            local aparecidos = nuevos_desde(antes, despues)
            if #aparecidos == 0 then
                apuntar("  NO dejo NINGUN clip en el Media Pool.")
                apuntar("  => en este Resolve el pack solo puede aplicarse por")
                apuntar("     VALORES (tipografia/tamaño/color), no con sus")
                apuntar("     clips. Es lo que hace la v1.0.37.")
            else
                apuntar("  Dejo estos clips sueltos en el Media Pool:")
                for _, n in ipairs(aparecidos) do
                    apuntar(string.format("      '%s' x%d", n.nombre, n.cuantos))
                end
                apuntar("  => ESTE es el camino bueno: los nombres de arriba")
                apuntar("     dicen si se pueden repartir por rol.")
            end

            -- Y de paso: ¿GetMediaPoolItem promueve los clips del pack?
            local promovio, mirados = 0, 0
            local n_pistas = 0
            pcall(function()
                n_pistas = tonumber(importado:GetTrackCount("video")) or 0
            end)
            for pista = 1, n_pistas do
                local ok_l, lista = pcall(function()
                    return importado:GetItemListInTrack("video", pista)
                end)
                if ok_l then
                    for _, item in ipairs(lista_api(lista)) do
                        mirados = mirados + 1
                        local mpi = nil
                        pcall(function() mpi = item:GetMediaPoolItem() end)
                        if mpi then promovio = promovio + 1 end
                    end
                end
            end
            apuntar(string.format(
                "  GetMediaPoolItem sobre sus clips: %d de %d promovieron.",
                promovio, mirados))

            pcall(function()
                importado:SetName("CineCaptions · PRUEBA (puedes borrarlo)")
            end)
            apuntar("  Dejo el timeline importado con el nombre")
            apuntar("  'CineCaptions · PRUEBA (puedes borrarlo)' para que lo borres tu.")
        end
        pcall(function()
            if carpeta_previa then media_pool:SetCurrentFolder(carpeta_previa) end
        end)
    end

    -- ---------------------------------------------------------------
    apuntar("")
    apuntar("C. El ciclo .drb: ExportFolder + ImportFolderFromFile")
    apuntar(string.rep("-", 58))
    -- Es la via de la v1.0.38 (el 'arrastrar a mano' hecho por API) y la
    -- unica que queda por medir: si este ciclo funciona en Free, el pack
    -- puede entrar al Media Pool como bin exportado, con posicion y
    -- animacion intactas.
    -- Nada de rawget sobre 'media_pool': es userdata y rawget solo acepta
    -- tablas (la misma mina que corto la seccion A en produccion).
    local tipo_exp, tipo_imp = "?", "?"
    pcall(function() tipo_exp = type(media_pool.ExportFolder) end)
    pcall(function() tipo_imp = type(media_pool.ImportFolderFromFile) end)
    apuntar("  type(ExportFolder)         = " .. tipo_exp)
    apuntar("  type(ImportFolderFromFile) = " .. tipo_imp)
    -- v1.1: la primera corrida real (Mac Studio 21.0.4.5, 03-09) dio
    -- media_pool.ExportFolder = nil, pero el producto usa TAMBIEN la firma
    -- carpeta:Export(ruta) y esa no se media. Se prueban LAS DOS, sobre un
    -- bin de PRUEBA propio (no la raiz: exportar el pool entero no es lo
    -- que hace el producto y puede pesar cientos de MB).
    local ruta_drb = carpeta_compartida() .. SEP .. "prueba_ciclo.drb"
    local bin_prueba = nil
    pcall(function()
        bin_prueba = media_pool:AddSubFolder(media_pool:GetRootFolder(),
                                             "CineCaptions · prueba ciclo (borrame)")
    end)
    apuntar("  bin de prueba creado: " .. (bin_prueba and "si" or "NO"))
    local objetivo = bin_prueba
    if not objetivo then
        pcall(function() objetivo = media_pool:GetRootFolder() end)
    end
    local tipo_export2 = "?"
    pcall(function() tipo_export2 = type(objetivo.Export) end)
    apuntar("  type(bin.Export)           = " .. tipo_export2)

    local firmas = {
        { nombre = "media_pool:ExportFolder(bin, ruta)",
          llamar = function()
              return media_pool:ExportFolder(objetivo, ruta_drb)
          end },
        { nombre = "bin:Export(ruta)",
          llamar = function() return objetivo:Export(ruta_drb) end },
    }
    local exporto = false
    for _, firma in ipairs(firmas) do
        if not exporto then
            pcall(function() os.remove(ruta_drb) end)
            local ok_e, res_e = pcall(firma.llamar)
            local bytes = 0
            local fd = io.open(ruta_drb, "rb")
            if fd then
                bytes = fd:seek("end") or 0
                fd:close()
            end
            if bytes > 0 then
                exporto = true
                apuntar(string.format("  %s -> EXPORTO (%d bytes)",
                                      firma.nombre, bytes))
            else
                apuntar(string.format("  %s -> no dejo archivo (%s)",
                                      firma.nombre, tostring(res_e)))
            end
        end
    end

    if exporto then
        -- Roundtrip: la prueba definitiva de la via. Se cuentan BINS
        -- nuevos (el de prueba esta vacio, asi que no deja clips).
        local function contar_bins()
            local total = 0
            local ok_r2, raiz2 = pcall(function()
                return media_pool:GetRootFolder()
            end)
            if not ok_r2 or not raiz2 then return 0 end
            local function rec(folder)
                for _, sub in ipairs(lista_api(folder:GetSubFolderList())) do
                    total = total + 1
                    rec(sub)
                end
            end
            pcall(function() rec(raiz2) end)
            return total
        end
        local bins_antes = contar_bins()
        local ok_imp, res_imp = pcall(function()
            return media_pool:ImportFolderFromFile(ruta_drb)
        end)
        local bins_nuevos = contar_bins() - bins_antes
        apuntar(string.format("  ImportFolderFromFile -> %s, bins nuevos: %d",
                              tostring(ok_imp and res_imp), bins_nuevos))
        if bins_nuevos > 0 then
            apuntar("  => EL CICLO .drb FUNCIONA COMPLETO en este Resolve:")
            apuntar("     con el bin del pack exportado UNA vez (o embebido")
            apuntar("     en el programa), el pack entra solo con posicion")
            apuntar("     y animacion. Borra los bins de prueba '(borrame)'.")
        else
            apuntar("  => ImportFolderFromFile no dejo nada visible.")
        end
        pcall(function() os.remove(ruta_drb) end)
    else
        apuntar("  => NINGUNA firma de exportacion existe en este Resolve:")
        apuntar("     el respaldo automatico no es posible aqui. La salida")
        apuntar("     real: exportar el bin del pack UNA vez A MANO (clic")
        apuntar("     derecho sobre el bin -> Exportar bandeja...) con el")
        apuntar("     nombre exacto que dice el registro al generar. La")
        apuntar("     IMPORTACION " .. ((tipo_imp == "function")
                and "SI existe: ese archivo entrara solo."
                or "tampoco existe: no hay ciclo .drb aqui."))
    end
    -- El bin de prueba se intenta retirar; si la API no borra carpetas,
    -- queda con su nombre '(borrame)' y lo dice.
    if bin_prueba then
        local borrado = false
        pcall(function()
            borrado = media_pool:DeleteFolders({ bin_prueba }) and true or false
        end)
        if not borrado then
            apuntar("  (no pude borrar el bin de prueba por script: "
                    .. "borralo tu, se llama 'CineCaptions · prueba ciclo "
                    .. "(borrame)')")
        end
    end

    apuntar("")
    -- SECCION D (v1.0.49): dos preguntas para el Diseño dinamico.
    -- 1. ¿El Text+ tiene entradas de CAJA de fondo? (para un futuro look
    --    tipo CapCut con fondo detras del texto). Se mide sobre un Text+
    --    colocado: se escribe y se RELEE cada entrada candidata.
    -- 2. ¿Un emoji sobrevive el viaje a StyledText? (aceptacion, no
    --    rendering: si se relee identico, el pipeline no lo rompe).
    apuntar("D) Entradas de caja y emoji (para el Diseño dinamico):")
    local tp = nil
    pcall(function()
        for i = 1, (timeline:GetTrackCount("video") or 0) do
            for _, it in ipairs(lista_api(timeline:GetItemListInTrack("video", i))) do
                local comp = nil
                pcall(function() comp = it:GetFusionCompByIndex(1) end)
                if comp then
                    for _, tool in pairs(comp:GetToolList() or {}) do
                        local ok_id, id = pcall(function()
                            return tool:GetAttrs().TOOLS_RegID
                        end)
                        if ok_id and id == "TextPlus" then tp = tool end
                        if tp then break end
                    end
                end
                if tp then break end
            end
            if tp then break end
        end
    end)
    if not tp then
        apuntar("  (no encontre ningun Text+ en el timeline para medir; "
                .. "coloca uno y re-corre si quieres este dato)")
    else
        for _, entrada in ipairs({ "Enabled3", "ElementShape3",
                                   "ExtendHorizontal3", "ExtendVertical3",
                                   "Red3", "Green3", "Blue3", "Alpha3",
                                   "Opacity3" }) do
            local antes = nil
            pcall(function() antes = tp:GetInput(entrada) end)
            local escrito = false
            pcall(function()
                tp:SetInput(entrada, (entrada == "ElementShape3") and 2 or 0.5)
                escrito = true
            end)
            local despues = nil
            pcall(function() despues = tp:GetInput(entrada) end)
            pcall(function() tp:SetInput(entrada, antes) end)
            apuntar(string.format("  %s: %s (antes=%s, despues=%s)",
                entrada,
                (escrito and despues ~= nil and tostring(despues) ~= tostring(antes))
                    and "RESPONDE" or "no responde",
                tostring(antes), tostring(despues)))
        end
        local emoji = "Prueba " .. string.char(240, 159, 148, 165) .. " emoji"
        local texto_antes = nil
        pcall(function() texto_antes = tp:GetInput("StyledText") end)
        local releido = nil
        pcall(function()
            tp:SetInput("StyledText", emoji)
            releido = tp:GetInput("StyledText")
        end)
        pcall(function() tp:SetInput("StyledText", texto_antes) end)
        apuntar("  emoji en StyledText: "
                .. ((releido == emoji) and "SOBREVIVE identico"
                    or ("cambio a: " .. tostring(releido))))
    end

    apuntar("")
    local _, cuantos_final = foto_del_pool(media_pool)
    apuntar("Clips en el Media Pool al terminar: " .. cuantos_final)
    apuntar("Listo. Mandame el archivo prueba_mediapool.txt")
end

local ok_main, err = pcall(main)
if not ok_main then
    apuntar("La prueba se corto: " .. tostring(err))
end

local destino = carpeta_compartida() .. SEP .. "prueba_mediapool.txt"
local salida = io.open(destino, "w")
if salida then
    salida:write(table.concat(lineas, "\n"))
    salida:close()
    print("Informe escrito en: " .. destino)
else
    print("No pude escribir el informe en: " .. destino)
end
