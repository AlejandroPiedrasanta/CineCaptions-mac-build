// CineCaptions · By Cinema Productions
// 2_recursos/premiere/com.cinecaptions.premiere/jsx/colocar.jsx — ExtendScript (ES3) de Premiere Pro: toma el pedido de GO y lo coloca.
// Pedido (1_codigo/premiere.py → armar_pedido): video, capa (ProRes 4444 con alfa), sfx [{ruta, t, dur}], secuencia, bin, proyecto_nuevo.
// Cola: Folder.userData/CineCaptions/premiere: pedido.json → pedido.en_curso.json (tomado: nunca se coloca dos veces) → resultado.json;
// latido.json cada ~3 s (CineCaptions sabe así que Premiere y el panel están vivos).
// Resultado en la secuencia nueva (carpeta «CineCaptions» del proyecto): V1 + A1 el video, V2 los captions, A2… los sonidos sin pisarse.

var CC = (typeof CC !== 'undefined' && CC) ? CC : {};

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
    var info = { t: new Date().getTime(), version: String(app.version), proyecto: '' };
    try {
        if (CC.hayProyecto()) { info.proyecto = String(app.project.name); }
    } catch (e) {}
    CC.escribir(new File(CC.carpeta().fsName + '/latido.json'), CC.aTexto(info));
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

CC.colocar = function (p) {
    var nuevo = false, i;
    if (!CC.hayProyecto()) {                     // sin proyecto abierto: uno nuevo junto al video
        if (!p.proyecto_nuevo) { throw new Error('no hay ningún proyecto abierto en Premiere Pro'); }
        app.newProject(p.proyecto_nuevo);
        nuevo = true;
        if (!CC.hayProyecto()) { throw new Error('no pude crear el proyecto ' + p.proyecto_nuevo); }
    }
    var proj = app.project;
    var bin = CC.bin(proj.rootItem, p.bin || 'CineCaptions');
    var sfx = p.sfx || [], musica = p.musica || [];
    var mapa = CC.importar(proj, bin, [p.video, p.capa]);
    var video = mapa[CC.norma(p.video)], capa = mapa[CC.norma(p.capa)];
    if (!video) { throw new Error('Premiere no pudo importar el video ' + p.video); }
    if (!capa) { throw new Error('Premiere no pudo importar los subtítulos ' + p.capa); }
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
    seq = CC.asegurarPistas(seq, p.solo_audio ? 1 : baseV + 1, baseA + fin.length + (musica.length ? 1 : 0));

    if (p.solo_audio) {                          // un audio suelto: la capa es la imagen (V1) y el audio va en A1
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
    try { seq.setPlayerPosition('0'); } catch (e3) {}
    if (nuevo) {
        try { proj.save(); } catch (e4) {}
    }
    return { ok: true, secuencia: String(seq.name), sfx: puestos, sfx_total: sfx.length, musica: conMusica, musica_total: musica.length,
             proyecto: String(proj.name), proyecto_nuevo: nuevo, version: String(app.version) };
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
