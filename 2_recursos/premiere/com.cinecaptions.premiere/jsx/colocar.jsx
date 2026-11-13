// CineCaptions · By Cinema Productions
// 2_recursos/premiere/com.cinecaptions.premiere/jsx/colocar.jsx — ExtendScript (ES3) de Premiere Pro: toma el pedido de GO y lo coloca.
// Pedido (1_codigo/premiere.py → armar_pedido): video, capa (ProRes 4444 con alfa), sfx [{ruta, t, dur}], secuencia, bin, proyecto_nuevo,
// proyectos_cc (v5.85: los .prproj que escribió CineCaptions para abrir Premiere con ellos: si es el abierto, se guarda al terminar).
// Cola: Folder.userData/CineCaptions/premiere: pedido.json → pedido.en_curso.json (tomado: nunca se coloca dos veces) → resultado.json;
// latido.json cada ~3 s (CineCaptions sabe así que Premiere y el panel están vivos).
// Resultado en la secuencia nueva (carpeta «CineCaptions» del proyecto): V1 + A1 el video, V2 los captions, A2… los sonidos sin pisarse.
// v5.85 (el usuario: «quiero los textos que se vayan armando en la línea de tiempo»): con `textos` en el pedido (1_codigo/premiere_textos.py)
// cada texto es un clip de la plantilla «Basic Title» de Premiere con su letra, tamaño, color, contorno y sombra; `imagenes` (cajas, aros,
// emojis) van como PNG en las pistas de debajo. Sin capa de video.

var CC = (typeof CC !== 'undefined' && CC) ? CC : {};
CC.PANEL = 2;                                    // protocolo del panel (latido.panel): 2 = textos editables
CC.REV = 15;                                 // revisión de ESTE archivo (latido.rev): CineCaptions sabe si Premiere corre un panel viejo
// v5.87 (rev 15): animación de cada pieza (`anim`: fotogramas clave), cada texto comprobado en su sitio (a veces Premiere lo dejaba en el 0),
// latido con `inicio` (las letras instaladas después no las ve este Premiere) y `plantilla` (la «Basic Title» que encuentra él: Mac y Windows)
if (!CC.INICIO) { CC.INICIO = new Date().getTime(); }
// (sin recarga en caliente: probado en Premiere 26.5, `$.evalFile` del panel desde CC.revisar da «Stack overrun» al sustituir las funciones
// en marcha y deja ExtendScript tocado; un panel nuevo entra al reiniciar Premiere, como siempre)
CC.TICKS = 254016000000;                         // ticks de Premiere por segundo

CC.carpeta = function () {
    var f = new Folder(Folder.userData.fsName + '/CineCaptions/premiere');
    if (!f.exists) { f.create(); }
    return f;
};

CC.leer = function (archivo) {
    archivo.encoding = 'UTF-8';
    if (!archivo.open('r')) { return null; }
    var s = archivo.read();
    archivo.close();
    return s;
};

CC.escribir = function (archivo, texto) {
    archivo.encoding = 'UTF-8';
    archivo.lineFeed = 'Unix';
    if (!archivo.open('w')) { return false; }
    archivo.write(texto);
    archivo.close();
    return true;
};

CC.comillas = function (s) {
    s = String(s);
    var r = '"';
    for (var i = 0; i < s.length; i++) {
        var c = s.charAt(i), n = s.charCodeAt(i);
        if (c === '"' || c === '\\') {
            r += '\\' + c;
        } else if (n < 32 || n > 126) {
            var h = n.toString(16);
            while (h.length < 4) { h = '0' + h; }
            r += '\\u' + h;
        } else {
            r += c;
        }
    }
    return r + '"';
};

CC.aTexto = function (v) {                       // ExtendScript no trae JSON
    if (v === null || v === undefined) { return 'null'; }
    var t = typeof v;
    if (t === 'boolean') { return v ? 'true' : 'false'; }
    if (t === 'number') { return isFinite(v) ? String(v) : 'null'; }
    if (t === 'string') { return CC.comillas(v); }
    var partes = [];
    if (v instanceof Array) {
        for (var i = 0; i < v.length; i++) { partes.push(CC.aTexto(v[i])); }
        return '[' + partes.join(',') + ']';
    }
    for (var k in v) {
        if (v.hasOwnProperty(k)) { partes.push(CC.comillas(k) + ':' + CC.aTexto(v[k])); }
    }
    return '{' + partes.join(',') + '}';
};

CC.desdeTexto = function (s) {                   // como json2.js: solo se evalúa si el texto es JSON puro (sin llamadas ni funciones)
    var limpio = String(s).replace(/\\(?:["\\\/bfnrt]|u[0-9a-fA-F]{4})/g, '@')
        .replace(/"[^"\\\n\r]*"|true|false|null|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?/g, ']')
        .replace(/(?:^|:|,)(?:\s*\[)+/g, '');
    if (!/^[\],:{}\s]*$/.test(limpio)) { throw new Error('el pedido de CineCaptions no es JSON'); }
    return eval('(' + s + ')');
};

CC.norma = function (ruta) {
    return String(ruta).replace(/\\/g, '/').toLowerCase();
};

CC.hayProyecto = function () {
    try {
        if (app.projects && app.projects.numProjects === 0) { return false; }
        return !!(app.project && app.project.rootItem && app.project.path);
    } catch (e) {
        return false;
    }
};

CC.latido = function () {
    var info = { t: new Date().getTime(), version: String(app.version), proyecto: '', panel: CC.PANEL, rev: CC.REV, inicio: CC.INICIO,
                 plantilla: CC.plantillaTexto(), so: String($.os) };
    try {
        if (CC.hayProyecto()) { info.proyecto = String(app.project.name); }
    } catch (e) {}
    CC.escribir(new File(CC.carpeta().fsName + '/latido.json'), CC.aTexto(info));
};

CC.plantillaTexto = function () {               // v5.87: la «Basic Title.mogrt» de ESTE Premiere (Windows: junto al .exe; Mac: dentro de la .app)
    if (CC._plantilla !== undefined) { return CC._plantilla; }
    CC._plantilla = '';
    try {
        var base = Folder.appPackage, bases = [], i, j, k;
        if (!base || !base.exists) { return ''; }
        bases.push(base);
        if (base.parent) { bases.push(base.parent); }
        var rel = ['Essential Graphics/Basic Title.mogrt', 'Contents/Essential Graphics/Basic Title.mogrt',
                   'Resources/Essential Graphics/Basic Title.mogrt', 'Contents/Resources/Essential Graphics/Basic Title.mogrt'];
        for (i = 0; i < bases.length; i++) {
            for (j = 0; j < rel.length; j++) {
                var f = new File(bases[i].fsName + '/' + rel[j]);
                if (f.exists) { CC._plantilla = f.fsName; return CC._plantilla; }
            }
        }
        for (i = 0; i < bases.length; i++) {      // (otra carpeta: hasta dos niveles más abajo, solo carpetas)
            var d1 = bases[i].getFiles(function (x) { return x instanceof Folder; }) || [];
            for (j = 0; j < d1.length && j < 80; j++) {
                var g = new File(d1[j].fsName + '/Essential Graphics/Basic Title.mogrt');
                if (g.exists) { CC._plantilla = g.fsName; return CC._plantilla; }
                var d2 = d1[j].getFiles(function (x) { return x instanceof Folder; }) || [];
                for (k = 0; k < d2.length && k < 80; k++) {
                    var h = new File(d2[k].fsName + '/Essential Graphics/Basic Title.mogrt');
                    if (h.exists) { CC._plantilla = h.fsName; return CC._plantilla; }
                }
            }
        }
    } catch (e) {}
    return CC._plantilla;
};

CC.bin = function (padre, nombre) {
    var i, h;
    for (i = 0; i < padre.children.numItems; i++) {
        h = padre.children[i];
        if (h && h.type === ProjectItemType.BIN && h.name === nombre) { return h; }
    }
    var nuevo = padre.createBin(nombre);
    if (nuevo) { return nuevo; }
    for (i = padre.children.numItems - 1; i >= 0; i--) {
        h = padre.children[i];
        if (h && h.type === ProjectItemType.BIN && h.name === nombre) { return h; }
    }
    return padre;
};

CC.buscar = function (bin, ruta) {
    var objetivo = CC.norma(ruta);
    for (var i = bin.children.numItems - 1; i >= 0; i--) {
        var h = bin.children[i];
        try {
            if (h && h.type !== ProjectItemType.BIN && CC.norma(h.getMediaPath()) === objetivo) { return h; }
        } catch (e) {}
    }
    return null;
};

CC.importar = function (proj, bin, rutas) {      // → {ruta normalizada: ProjectItem}; lo que ya estaba en la carpeta se reutiliza
    var mapa = {}, faltan = [], i, it;
    for (i = 0; i < rutas.length; i++) {
        it = CC.buscar(bin, rutas[i]);
        if (it) { mapa[CC.norma(rutas[i])] = it; } else { faltan.push(rutas[i]); }
    }
    if (faltan.length) {
        proj.importFiles(faltan, true, bin, false);
        for (i = 0; i < faltan.length; i++) {
            it = CC.buscar(bin, faltan[i]);
            if (it) { mapa[CC.norma(faltan[i])] = it; }
        }
    }
    return mapa;
};

CC.nombreLibre = function (proj, nombre) {
    var usados = {};
    for (var i = 0; i < proj.sequences.numSequences; i++) { usados[String(proj.sequences[i].name)] = true; }
    if (!usados[nombre]) { return nombre; }
    for (var n = 2; n < 500; n++) {
        if (!usados[nombre + ' ' + n]) { return nombre + ' ' + n; }
    }
    return nombre + ' ' + new Date().getTime();
};

CC.tiempo = function (seg) {
    var t = new Time();
    t.seconds = seg;
    return t;
};

CC.inicios = function (track, item) {            // dónde empieza cada clip de ese elemento en la pista
    var r = [];
    for (var i = 0; i < track.clips.numItems; i++) {
        var c = track.clips[i];
        try {
            if (c.projectItem && c.projectItem.nodeId === item.nodeId) { r.push(c.start.seconds); }
        } catch (e) {}
    }
    return r;
};

CC.poner = function (track, item, seg) {
    // overwriteClip acepta un Time o segundos según la versión de Premiere: se prueba y se comprueba que cayó donde debía
    var formas = [
        function () { track.overwriteClip(item, CC.tiempo(seg)); },
        function () { track.overwriteClip(item, seg); },
        function () { track.overwriteClip(item, String(seg)); }
    ];
    for (var f = 0; f < formas.length; f++) {
        var antes = CC.inicios(track, item), i, j;
        try { formas[f](); } catch (e) {}
        var despues = CC.inicios(track, item);
        for (i = 0; i < despues.length; i++) {
            if (Math.abs(despues[i] - seg) < 0.08) { return true; }
        }
        for (i = track.clips.numItems - 1; i >= 0; i--) {   // cayó en otro sitio: se quita y se prueba la forma siguiente
            var c = track.clips[i], viejo = false;
            try {
                if (!c.projectItem || c.projectItem.nodeId !== item.nodeId) { continue; }
                for (j = 0; j < antes.length; j++) {
                    if (Math.abs(antes[j] - c.start.seconds) < 0.001) { viejo = true; }
                }
                if (!viejo) { c.remove(false, false); }
            } catch (e2) {}
        }
    }
    return false;
};

CC.ultimaOcupada = function (pistas) {           // índice de la última pista con algo (−1 si ninguna)
    var u = -1;
    for (var i = 0; i < pistas.numTracks; i++) {
        if (pistas[i].clips.numItems > 0) { u = i; }
    }
    return u;
};

CC.asegurarPistas = function (seq, nVideo, nAudio) {
    var fv = nVideo - seq.videoTracks.numTracks, fa = nAudio - seq.audioTracks.numTracks;
    if (fv <= 0 && fa <= 0) { return seq; }
    try {
        app.enableQE();
        qe.project.getActiveSequence().addTracks(fv > 0 ? fv : 0, seq.videoTracks.numTracks, fa > 0 ? fa : 0, 1,
                                                 seq.audioTracks.numTracks, 0, 0, 0);
    } catch (e) {}
    return app.project.activeSequence || seq;
};

// ---------------------------------------------------------------------------------------------- v5.85: textos editables e imágenes sueltas
CC.ticks = function (seg) {
    return String(Math.round(seg * CC.TICKS));
};

CC.componente = function (item, nombres) {      // por matchName (no cambia con el idioma) o por nombre visible
    try {
        for (var i = 0; i < item.components.numItems; i++) {
            var c = item.components[i];
            for (var j = 0; j < nombres.length; j++) {
                if (String(c.matchName) === nombres[j] || String(c.displayName) === nombres[j]) { return c; }
            }
        }
    } catch (e) {}
    return null;
};

CC.propiedad = function (comp, nombres, indice) {   // por nombre visible (inglés o español) y si no, por su posición
    if (!comp) { return null; }
    try {
        for (var i = 0; i < comp.properties.numItems; i++) {
            var n = String(comp.properties[i].displayName);
            for (var j = 0; j < nombres.length; j++) {
                if (n === nombres[j]) { return comp.properties[i]; }
            }
        }
        if (indice !== undefined && indice < comp.properties.numItems) { return comp.properties[indice]; }
    } catch (e) {}
    return null;
};

CC.clipEn = function (track, seg) {               // el clip de esa pista que empieza en `seg` (el último si hay varios)
    var mejor = null;
    try {
        for (var i = 0; i < track.clips.numItems; i++) {
            var c = track.clips[i];
            if (Math.abs(c.start.seconds - seg) < 0.02) { mejor = c; }
        }
    } catch (e) {}
    return mejor;
};

CC.fijarFin = function (it, t1) {
    var bien = function () { try { return Math.abs(it.end.seconds - t1) < 0.02; } catch (e) { return false; } };
    try { it.end = CC.tiempo(t1); } catch (e1) {}
    if (bien()) { return true; }
    try { it.end = t1; } catch (e2) {}
    if (bien()) { return true; }
    try { it.outPoint = CC.tiempo(it.inPoint.seconds + (t1 - it.start.seconds)); } catch (e3) {}
    return bien();
};

CC.fundido = function (it, entrada) {             // la entrada de cada pieza: de 0 a 100 de opacidad en `entrada` segundos
    if (!(entrada > 0)) { return; }
    try {
        var op = CC.propiedad(CC.componente(it, ['AE.ADBE Opacity']), ['Opacity', 'Opacidad'], 0);
        if (!op) { return; }
        var t0 = it.inPoint.seconds;
        op.setTimeVarying(true);
        op.addKey(t0);
        op.setValueAtKey(t0, 0, true);
        op.addKey(t0 + entrada);
        op.setValueAtKey(t0 + entrada, 100, true);
    } catch (e) {}
};

CC.claves = function (prop, lista, base, valor) {   // v5.87: fotogramas clave [[s desde el inicio del clip, valor…]] (tiempo del clip = entrada + s)
    if (!prop || !lista || lista.length < 2) { return false; }
    try {
        prop.setTimeVarying(true);
        for (var i = 0; i < lista.length; i++) {
            var tt = base + lista[i][0];
            prop.addKey(tt);
            prop.setValueAtKey(tt, valor(lista[i]), i === lista.length - 1);
        }
        return true;
    } catch (e) {
        return false;
    }
};

CC.animar = function (it, t, esTexto, ancho, alto, norm) {
    // v5.87: la animación de la pieza (premiere_textos.animacion: la de la vista de Creativo, a imagen de los macros de Resolve).
    // Texto: escala, giro y posición en su capa de texto; imagen: en Movimiento. Opacidad del clip y recorte por la derecha (Movimiento).
    var a = t.anim;
    if (!a) { return false; }
    var base = 0, hecho = false;
    try { base = it.inPoint.seconds; } catch (e0) { return false; }
    var mov = CC.componente(it, ['AE.ADBE Motion']);
    var capa = esTexto ? CC.componente(it, ['AE.ADBE Text']) : mov;
    var uno = function (k) { return k[1]; };
    if (a.op) { hecho = CC.claves(CC.propiedad(CC.componente(it, ['AE.ADBE Opacity']), ['Opacity', 'Opacidad'], 0), a.op, base, uno) || hecho; }
    if (a.es) { hecho = CC.claves(CC.propiedad(capa, ['Scale', 'Escala'], esTexto ? 3 : 1), a.es, base, uno) || hecho; }
    if (a.gi) { hecho = CC.claves(CC.propiedad(capa, ['Rotation', 'Rotación'], esTexto ? 6 : 4), a.gi, base, uno) || hecho; }
    if (a.po) {
        hecho = CC.claves(CC.propiedad(capa, ['Position', 'Posición'], esTexto ? 2 : 0), a.po, base,
                          function (k) { return norm ? [k[1] / ancho, k[2] / alto] : [k[1], k[2]]; }) || hecho;
    }
    if (a.cr) { hecho = CC.claves(CC.propiedad(mov, ['Crop Right', 'Recortar hacia la derecha'], 9), a.cr, base, uno) || hecho; }
    return hecho;
};

CC.tieneTexto = function (it) {
    return !!(it && CC.componente(it, ['AE.ADBE Text']));
};

CC.importarTexto = function (seq, t, v) {
    // v5.87: el texto en SU sitio. Visto en Premiere 26.5 (Estilo 3): a veces importMGT devuelve un clip en el segundo 0 y sin capa de texto
    // («MI», «AÑOS», «DE» faltaban): se busca el clip que sí cayó en t0 y, si no hay, se quita lo que cayó mal y se vuelve a importar.
    var track = seq.videoTracks[v];
    var quitar = function (it, antes) {           // solo lo que acaba de caer mal (nunca un texto que ya estaba en la pista)
        try {
            var s = it.start.seconds;
            for (var i = 0; i < antes.length; i++) { if (Math.abs(antes[i] - s) < 0.001) { return; } }
            it.remove(false, false);
        } catch (e) {}
    };
    for (var intento = 0; intento < 3; intento++) {
        var it = null, w, antes = [];
        try {
            for (w = 0; w < track.clips.numItems; w++) { antes.push(track.clips[w].start.seconds); }
        } catch (e0) {}
        try { it = seq.importMGT(t.mogrt, CC.ticks(t.t0), v, 0); } catch (e) { CC._errorImportar = String(e.message || e); }
        var enSitio = false;
        try { enSitio = !!it && Math.abs(it.start.seconds - t.t0) < 0.02; } catch (e1) { enSitio = false; }
        var ahi = enSitio ? it : CC.clipEn(track, t.t0);
        if (ahi) {                                // (sin capa de texto, colocarTexto lo pone con Movimiento; nada de $.sleep: ExtendScript
            if (!enSitio && it) { quitar(it, antes); }   // corre en el hilo principal de Premiere y dormir ahí lo traba)
            return ahi;
        }
        if (!it) { break; }                       // (Premiere no la acepta: no insistir)
        quitar(it, antes);                        // cayó fuera de su sitio: fuera, y otra vez
        CC.reintentos = (CC.reintentos || 0) + 1;
    }
    return null;
};

CC.colocarTexto = function (it, t, ancho, alto, diag) {   // la capa de texto: al 100 % (la plantilla la adapta al ancho de la secuencia), en su sitio y con su giro
    var comp = CC.componente(it, ['AE.ADBE Text']), norm = true;
    try {
        var escala = CC.propiedad(comp, ['Scale', 'Escala'], 3);
        if (diag) { diag.escala_antes = String(escala.getValue()); }
        escala.setValue(100, true);                 // (el tamaño de la letra ya va en píxeles de la secuencia)
    } catch (e0) {
        if (diag) { diag.error_escala = String(e0.message || e0); }
    }
    var pos = CC.propiedad(comp, ['Position', 'Posición'], 2);
    try {
        var v = pos.getValue();
        if (diag) { diag.pos_antes = String(v); }
        norm = (v instanceof Array) && Math.abs(v[0]) <= 2 && Math.abs(v[1]) <= 2;
        pos.setValue(norm ? [t.x / ancho, t.y / alto] : [t.x, t.y], true);       // (ancla: centro del avance, línea de base)
    } catch (e) {
        if (diag) { diag.error_pos = String(e.message || e); }
        try {                                     // sin la capa de texto: Movimiento (el gráfico entero, centrado en el cuadro)
            var mov = CC.propiedad(CC.componente(it, ['AE.ADBE Motion']), ['Position', 'Posición'], 0);
            mov.setValue([0.5 + (t.x - ancho / 2) / ancho, 0.5 + (t.y - alto / 2) / alto], true);
        } catch (e2) {}
    }
    if (t.rot) {
        try {
            var giro = CC.propiedad(comp, ['Rotation', 'Rotación'], 6);
            if (giro) { giro.setValue(t.rot, true); }
        } catch (e3) {}
    }
    return norm;
};

CC.recortar = function (it, t, fps) {             // v5.85, Estilo 5: la línea se destapa palabra a palabra («Recortar hacia la derecha» de Movimiento)
    var pasos = t.recorte;
    if (!pasos || pasos.length < 2) { return; }
    try {
        var pr = CC.propiedad(CC.componente(it, ['AE.ADBE Motion']), ['Crop Right', 'Recortar hacia la derecha'], 9);
        if (!pr) { return; }
        var base = it.inPoint.seconds - it.start.seconds, cuadro = 1 / (fps || 30), i;   // (tiempo del clip = entrada + (tiempo de la secuencia − inicio))
        pr.setTimeVarying(true);
        for (i = 0; i < pasos.length; i++) {
            var ti = base + pasos[i][0];
            if (i > 0) {                          // un fotograma antes, lo que se veía: el cambio va en escalón (no se desliza)
                pr.addKey(ti - cuadro);
                pr.setValueAtKey(ti - cuadro, pasos[i - 1][1], true);
            }
            pr.addKey(ti);
            pr.setValueAtKey(ti, pasos[i][1], true);
        }
    } catch (e) {}
};

CC.diagnostico = function (it) {                 // qué expone el clip de texto (para ajustar sin adivinar)
    var d = { comps: [] };
    try {
        for (var i = 0; i < it.components.numItems; i++) {
            var c = it.components[i], props = [];
            for (var j = 0; j < c.properties.numItems && j < 16; j++) {
                var nombre = String(c.properties[j].displayName), val = '';
                try { val = String(c.properties[j].getValue()).substring(0, 60); } catch (e) { val = '?'; }
                props.push(nombre + '=' + val);
            }
            d.comps.push(String(c.displayName) + ' | ' + String(c.matchName) + ' | ' + props.join(' ; '));
        }
        d.inicio = it.start.seconds;
        d.fin = it.end.seconds;
        d.entrada_clip = it.inPoint.seconds;
        d.nombre = String(it.name);
    } catch (e2) {
        d.error = String(e2.message || e2);
    }
    return d;
};

CC.totalPiezas = function (p) {
    return (p.textos ? p.textos.length : 0) + (p.imagenes ? p.imagenes.length : 0);
};

CC.avance = function (p, hechos, total) {        // v5.85: mientras coloca no hay latido (ExtendScript hace una cosa a la vez): el avance, cada 10 piezas
    if (hechos % 10 !== 0 && hechos !== total) { return; }
    try {
        CC.escribir(new File(CC.carpeta().fsName + '/progreso.json'), CC.aTexto({ id: p.id || '', hechos: hechos, total: total, t: new Date().getTime() }));
    } catch (e) {}
};

CC.ponerTextos = function (seq, p, primera, res) {
    // v5.85: cada texto trae SU plantilla (premiere_textos.mogrt_de_texto: la «Basic Title» del propio Premiere con el texto y el estilo dentro;
    // en Premiere 26 escribir el «Texto de origen» por ExtendScript no se dibuja). Al importarla, Premiere la convierte en un texto normal.
    var textos = p.textos || [], ancho = seq.frameSizeHorizontal || p.ancho, alto = seq.frameSizeVertical || p.alto;
    var diag = {}, puestos = 0, animados = 0, i;
    res.diag = diag;
    CC.reintentos = 0;
    CC._errorImportar = '';
    for (i = 0; i < textos.length; i++) {
        var t = textos[i], v = primera + (t.pista || 0);
        if (v >= seq.videoTracks.numTracks || !t.mogrt) { continue; }
        var it = CC.importarTexto(seq, t, v);
        if (CC._errorImportar && !diag.error_importar) { diag.error_importar = CC._errorImportar; }
        if (!it) {
            if (puestos === 0) { return { ok: false, causa: 'textos', error: 'Premiere no puso la plantilla del texto «' + t.texto + '»' }; }
            continue;
        }
        CC.fijarFin(it, t.t1);
        var norm = CC.colocarTexto(it, t, ancho, alto, puestos === 0 ? diag : null);
        if (CC.tieneTexto(it) && CC.animar(it, t, true, ancho, alto, norm)) {
            animados++;
        } else {
            CC.fundido(it, t.entrada);
        }
        CC.recortar(it, t, p.fps);
        if (puestos === 0) { diag.clip = CC.diagnostico(it); }
        try { it.name = t.texto; } catch (e4) {}
        if (p.depurar) {                          // (pruebas) dónde quedó cada texto
            if (!res.clips) { res.clips = []; }
            var posd = '';
            try { posd = String(CC.propiedad(CC.componente(it, ['AE.ADBE Text']), ['Position', 'Posición'], 2).getValue()); } catch (ed) {}
            res.clips.push([i, t.texto, v, it.start.seconds, it.end.seconds, posd, String(it.name)]);
        }
        puestos++;
        CC.avance(p, puestos, CC.totalPiezas(p));
    }
    if (!puestos && textos.length) { return { ok: false, causa: 'textos', error: 'Premiere no puso ningún texto' }; }
    res.textos = puestos;
    res.textos_total = textos.length;
    res.textos_estilo = puestos;
    res.textos_animados = animados;
    res.reintentos = CC.reintentos || 0;
    return null;
};

CC.ponerImagenes = function (seq, proj, bin, p, primera, res) {
    var imagenes = p.imagenes || [], ancho = seq.frameSizeHorizontal || p.ancho, alto = seq.frameSizeVertical || p.alto;
    var rutas = [], vistas = {}, i, puestas = 0, animadas = 0;
    for (i = 0; i < imagenes.length; i++) {
        var k = CC.norma(imagenes[i].ruta);
        if (!vistas[k]) { vistas[k] = true; rutas.push(imagenes[i].ruta); }
    }
    var mapa = rutas.length ? CC.importar(proj, CC.bin(bin, 'Elementos'), rutas) : {};
    for (i = 0; i < imagenes.length; i++) {
        var im = imagenes[i], item = mapa[CC.norma(im.ruta)], v = primera + (im.pista || 0);
        if (!item || v >= seq.videoTracks.numTracks) { continue; }
        var track = seq.videoTracks[v];
        if (!CC.poner(track, item, im.t0)) { continue; }
        var it = CC.clipEn(track, im.t0);
        if (!it) { continue; }
        CC.fijarFin(it, im.t1);
        try {
            var mov = CC.componente(it, ['AE.ADBE Motion']);
            CC.propiedad(mov, ['Position', 'Posición'], 0).setValue([im.x / ancho, im.y / alto], true);
            CC.propiedad(mov, ['Scale', 'Escala'], 1).setValue(100, true);
        } catch (e) {}
        if (CC.animar(it, im, false, ancho, alto, true)) {
            animadas++;
        } else {
            CC.fundido(it, im.entrada);
        }
        puestas++;
        CC.avance(p, (res.textos || 0) + puestas, CC.totalPiezas(p));
    }
    res.imagenes = puestas;
    res.imagenes_total = imagenes.length;
    res.imagenes_animadas = animadas;
};

CC.fotos = function (seq, p, res) {              // (pruebas) cuadros de la secuencia en PNG, para compararlos con el dibujo de CineCaptions
    if (!p.fotos || !p.fotos.length || !p.carpeta_fotos) { return; }
    res.fotos = [];
    try {
        app.enableQE();
        var qs = qe.project.getActiveSequence();
        for (var i = 0; i < p.fotos.length; i++) {
            seq.setPlayerPosition(CC.ticks(p.fotos[i]));
            var tc = String(qs.CTI.timecode);
            var formas = p.fotos_formas || ['tc'];          // (medido en Premiere 26.5: con «:»; sin ellos —como el ejemplo PProPanel— o en ticks, siempre el 1.er cuadro)
            for (var f = 0; f < formas.length; f++) {
                var arg = formas[f] === 'tc' ? tc : (formas[f] === 'tc_' ? tc.replace(/:|;/g, '_') : CC.ticks(p.fotos[i]));
                var ruta = new File(p.carpeta_fotos + '/foto_' + i + '_' + formas[f]).fsName;
                try { qs.exportFramePNG(arg, ruta); res.fotos.push(formas[f] + ' ' + arg); } catch (e) { res.fotos.push(formas[f] + ' error ' + (e.message || e)); }
            }
        }
    } catch (e2) {
        res.fotos.push('error: ' + (e2.message || e2));
    }
};

CC.propio = function (p) {                       // v5.85: ¿el proyecto abierto es uno que escribió CineCaptions (premiere.crear_proyecto)?
    try {                                        // (por el nombre: la ruta puede venir con «\\?\» o con «Usuarios» en vez de «Users»)
        var nombre = function (r) { return CC.norma(r).replace(/^.*\//, ''); };
        var abierto = nombre(app.project.path), lista = (p.proyectos_cc || []).concat(p.proyecto_nuevo ? [p.proyecto_nuevo] : []);
        for (var i = 0; i < lista.length; i++) { if (nombre(lista[i]) === abierto) { return true; } }
    } catch (e) {}
    return false;
};

CC.colocar = function (p) {
    var nuevo = false, i;
    if (!CC.hayProyecto()) {                     // sin proyecto abierto: uno nuevo junto al video
        if (!p.proyecto_nuevo) { throw new Error('no hay ningún proyecto abierto en Premiere Pro'); }
        app.newProject(p.proyecto_nuevo);
        nuevo = true;
        if (!CC.hayProyecto()) { throw new Error('no pude crear el proyecto ' + p.proyecto_nuevo); }
    } else if (CC.propio(p)) {                   // v5.85: Premiere se abrió con el proyecto que GO dejó junto al video: se guarda al terminar
        nuevo = true;
    }
    var proj = app.project;
    var bin = CC.bin(proj.rootItem, p.bin || 'CineCaptions');
    var sfx = p.sfx || [], musica = p.musica || [];
    var conTextos = !!(p.textos && p.textos.length && p.plantilla && !p.solo_audio);    // v5.85: textos editables en vez de la capa
    var mapa = CC.importar(proj, bin, conTextos ? [p.video] : [p.video, p.capa]);
    var video = mapa[CC.norma(p.video)], capa = conTextos ? null : mapa[CC.norma(p.capa)];
    if (!video) { throw new Error('Premiere no pudo importar el video ' + p.video); }
    if (!capa && !conTextos) { throw new Error('Premiere no pudo importar los subtítulos ' + p.capa); }
    var unicas = [], vistas = {}, todos = sfx.concat(musica);
    for (i = 0; i < todos.length; i++) {
        var k = CC.norma(todos[i].ruta);
        if (!vistas[k]) { vistas[k] = true; unicas.push(todos[i].ruta); }
    }
    var sonidos = unicas.length ? CC.importar(proj, CC.bin(bin, 'Sonidos'), unicas) : {};

    var seq = proj.createNewSequenceFromClips(CC.nombreLibre(proj, p.secuencia), [p.solo_audio ? capa : video], bin);
    if (!seq) { throw new Error('Premiere no pudo crear la secuencia'); }
    try { proj.activeSequence = seq; } catch (e1) {}
    try { proj.openSequence(seq.sequenceID); } catch (e2) {}

    // cada sonido en la primera pista libre (A2, A3…) para que ninguno corte a otro
    var fin = [], pista = [], maxP = p.pistas_sfx || 6;
    for (i = 0; i < sfx.length; i++) {
        var j = 0;
        while (j < fin.length && fin[j] > sfx[i].t + 0.001) { j++; }
        if (j === fin.length) {
            if (fin.length < maxP) {
                fin.push(0);
            } else {
                j = 0;
                for (var q = 1; q < fin.length; q++) { if (fin[q] < fin[j]) { j = q; } }
            }
        }
        fin[j] = sfx[i].t + (sfx[i].dur || 0.5);
        pista.push(j);
    }
    var baseA = Math.max(1, CC.ultimaOcupada(seq.audioTracks) + 1);     // (un video con dos canales sueltos ocupa A1 y A2)
    var baseV = Math.max(1, CC.ultimaOcupada(seq.videoTracks) + 1);
    var nImg = conTextos ? (p.carriles_imagen || 0) : 0, nTxt = conTextos ? (p.carriles_texto || 1) : 0;
    seq = CC.asegurarPistas(seq, p.solo_audio ? 1 : (conTextos ? baseV + nImg + nTxt : baseV + 1), baseA + fin.length + (musica.length ? 1 : 0));
    var res = { ok: true };

    if (conTextos) {                             // v5.85: los textos encima (primero: si Premiere no deja, se vuelve a la capa) y las piezas debajo
        if (seq.videoTracks.numTracks < baseV + nImg + nTxt) {
            try { proj.deleteSequence(seq); } catch (e5) {}
            return { ok: false, causa: 'textos', error: 'Premiere no creó las pistas para los textos', version: String(app.version) };
        }
        var fallo = CC.ponerTextos(seq, p, baseV + nImg, res);
        if (fallo) {
            try { proj.deleteSequence(seq); } catch (e6) {}
            fallo.version = String(app.version);
            fallo.diag = res.diag;
            return fallo;
        }
        CC.ponerImagenes(seq, proj, bin, p, baseV, res);
    } else if (p.solo_audio) {                   // un audio suelto: la capa es la imagen (V1) y el audio va en A1
        CC.poner(seq.audioTracks[0], video, 0);
    } else if (seq.videoTracks.numTracks <= baseV || !CC.poner(seq.videoTracks[baseV], capa, 0)) {
        throw new Error('Premiere no pudo poner los subtítulos encima del video');
    }
    var puestos = 0, nA = seq.audioTracks.numTracks;
    for (i = 0; i < sfx.length; i++) {
        var it = sonidos[CC.norma(sfx[i].ruta)];
        if (!it || nA <= baseA) { continue; }
        var idx = baseA + pista[i];
        if (idx >= nA) { idx = baseA + (pista[i] % (nA - baseA)); }
        if (CC.poner(seq.audioTracks[idx], it, sfx[i].t)) { puestos++; }
    }
    var conMusica = 0, pistaM = baseA + fin.length;   // la música, en su pista, debajo de los sonidos
    for (i = 0; i < musica.length; i++) {
        var m = sonidos[CC.norma(musica[i].ruta)];
        if (m && pistaM < seq.audioTracks.numTracks && CC.poner(seq.audioTracks[pistaM], m, musica[i].t)) { conMusica++; }
    }
    CC.fotos(seq, p, res);
    try { seq.setPlayerPosition('0'); } catch (e3) {}
    if (nuevo) {
        try { proj.save(); } catch (e4) {}
    }
    res.secuencia = String(seq.name);
    res.sfx = puestos;
    res.sfx_total = sfx.length;
    res.musica = conMusica;
    res.musica_total = musica.length;
    res.proyecto = String(proj.name);
    res.proyecto_nuevo = nuevo;
    res.version = String(app.version);
    res.panel = CC.PANEL;
    res.con_textos = conTextos;
    return res;
};

CC.revisar = function (conLatido) {
    var dir = CC.carpeta().fsName;
    if (conLatido) { CC.latido(); }
    var pedidoArchivo = new File(dir + '/pedido.json');
    if (!pedidoArchivo.exists) { return 'nada'; }
    var curso = new File(dir + '/pedido.en_curso.json');
    if (curso.exists) { curso.remove(); }
    if (!pedidoArchivo.rename('pedido.en_curso.json')) { return 'ocupado'; }
    curso = new File(dir + '/pedido.en_curso.json');
    var pedido = null, res;
    try {
        pedido = CC.desdeTexto(CC.leer(curso));
        res = CC.colocar(pedido);
    } catch (e) {
        res = { ok: false, error: String(e.message || e) + (e.line ? ' (colocar.jsx, línea ' + e.line + ')' : '') };
    }
    res.id = (pedido && pedido.id) ? pedido.id : '';
    curso.remove();
    var tmp = new File(dir + '/resultado.tmp');
    CC.escribir(tmp, CC.aTexto(res));
    var listo = new File(dir + '/resultado.json');           // («final» es palabra reservada en ES3)
    if (listo.exists) { listo.remove(); }
    tmp.rename('resultado.json');
    CC.latido();
    return res.ok ? 'colocado' : 'error';
};
