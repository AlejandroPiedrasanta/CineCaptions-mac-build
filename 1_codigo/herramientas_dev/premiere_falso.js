// CineCaptions · By Cinema Productions
// 1_codigo/herramientas_dev/premiere_falso.js — un Premiere Pro FALSO que corre el colocar.jsx REAL del panel (Node, sin Adobe): late como el
// panel, toma el pedido de GO de la cola, lo coloca en una secuencia de mentira y escribe resultado.json. Para probar GO con «Usar con
// Premiere Pro» donde no hay Premiere (las Mac de GitHub, verificar_mac.py).
//   node premiere_falso.js <colocar.jsx> <carpeta de datos de usuario (= Folder.userData)> [segundos máximos]
// Sale tras colocar UN pedido (código 0 si salió bien, 1 si el panel dio error) o al pasar los segundos (código 2).
const fs = require('fs'), path = require('path'), vm = require('vm');
const [jsxPath, base, maxS] = process.argv.slice(2);
const TICKS = 254016000000;
const FUENTE = JSON.stringify({ mTextParam: { mStyleSheet: { mText: 'Your Title Here', mFontName: { mParamValues: [[0, 'MyriadPro-Regular']] } } } });

function coleccion(a) {
  const c = { _a: a };
  Object.defineProperty(c, 'numItems', { get() { return a.length; } });
  Object.defineProperty(c, 'numTracks', { get() { return a.length; } });
  return new Proxy(c, { get(t, k) { if (typeof k === 'string' && /^\d+$/.test(k)) { return t._a[+k]; } return t[k]; } });
}
class Time { constructor() { this.seconds = 0; } get ticks() { return String(Math.round(this.seconds * TICKS)); } }
const mkT = (s) => { const t = new Time(); t.seconds = s; return t; };
class Folder {
  constructor(p) { this.fsName = String(p); }
  get exists() { return fs.existsSync(this.fsName); }
  get parent() { return new Folder(path.dirname(this.fsName)); }
  create() { fs.mkdirSync(this.fsName, { recursive: true }); return true; }
  getFiles(f) { try { return fs.readdirSync(this.fsName).map((n) => { const p = path.join(this.fsName, n); return fs.statSync(p).isDirectory() ? new Folder(p) : new File(p); }).filter((x) => !f || f(x)); } catch (e) { return []; } }
}
Folder.userData = new Folder(base);
Folder.appPackage = undefined;                     // (sin Premiere instalado: CC.plantillaTexto no encuentra nada, como en una Mac sin él)
class File {
  constructor(p) { this.fsName = String(p); }
  get exists() { return fs.existsSync(this.fsName); }
  open(m) { this._m = m; if (m === 'r') { if (!this.exists) { return false; } this._b = fs.readFileSync(this.fsName, 'utf8'); } else { this._b = ''; } return true; }
  read() { return this._b; } write(s) { this._b += s; }
  close() { if (this._m === 'w') { fs.writeFileSync(this.fsName, this._b, 'utf8'); } }
  rename(n) { const d = path.join(path.dirname(this.fsName), n); try { fs.renameSync(this.fsName, d); return true; } catch (e) { return false; } }
  remove() { try { fs.unlinkSync(this.fsName); return true; } catch (e) { return false; } }
}
const ProjectItemType = { CLIP: 1, BIN: 2, ROOT: 3, FILE: 4 };
let nodo = 0;
function Item(name, type, ruta) { this.name = name; this.type = type; this._ruta = ruta; this.nodeId = String(++nodo); this.children = coleccion([]); }
Item.prototype.getMediaPath = function () { return this._ruta || ''; };
Item.prototype.createBin = function (n) { const b = new Item(n, ProjectItemType.BIN); this.children._a.push(b); return b; };

function Prop(nombre, v) { this.displayName = nombre; this._v = v; this.keys = []; this.varia = false; }
Prop.prototype.getValue = function () { return this._v; };
Prop.prototype.setValue = function (v) { this._v = v; };
Prop.prototype.setTimeVarying = function (b) { this.varia = b; };
Prop.prototype.addKey = function (t) { if (typeof t !== 'number' || !isFinite(t)) { throw new Error('addKey: segundos'); } this.keys.push([t, null]); };
Prop.prototype.setValueAtKey = function (t, v) { const k = this.keys.find((x) => Math.abs(x[0] - t) < 1e-6); if (!k) { throw new Error('sin clave'); } k[1] = v; };
function Comp(nombre, match, props) { this.displayName = nombre; this.matchName = match; this.properties = coleccion(props); }

function TrackItem(pi, s, e, texto) {
  this.projectItem = pi; this._s = s; this._e = e; this.inPoint = mkT(texto ? 3600 : 0); this.name = pi ? pi.name : 'Gráfico';
  const comps = [new Comp('Opacidad', 'AE.ADBE Opacity', [new Prop('Opacidad', 100), new Prop('Modo de fusión', 0)]),
    new Comp('Movimiento', 'AE.ADBE Motion', [new Prop('Posición', [0.5, 0.5]), new Prop('Escala', 100), new Prop('Anchura de escala', 100),
      new Prop('Escala uniforme', true), new Prop('Rotación', 0), new Prop('Punto de anclaje', [0.5, 0.5]), new Prop('Filtro antiparpadeo', 0),
      new Prop('Recortar hacia la izquierda', 0), new Prop('Recortar hacia arriba', 0), new Prop('Recortar hacia la derecha', 0), new Prop('Recortar hacia abajo', 0)])];
  if (texto) {
    comps.push(new Comp('Texto', 'AE.ADBE Text', [new Prop('Texto de origen', FUENTE), new Prop('Transformar', false),
      new Prop('Posición', [0.5, 0.52]), new Prop('Escala', 56.25), new Prop('Escala horizontal', 56.25), new Prop('Escala uniforme', true), new Prop('Rotación', 0),
      new Prop('Opacidad', 100), new Prop('Punto de anclaje', [0, 0])]));
  }
  this.components = coleccion(comps);
}
Object.defineProperty(TrackItem.prototype, 'start', { get() { return mkT(this._s); } });
Object.defineProperty(TrackItem.prototype, 'end', {
  get() { return mkT(this._e); },
  set(v) { this._e = (v instanceof Time) ? v.seconds : Number(v); },
});
TrackItem.prototype.remove = function () { const a = this._pista.clips._a; const i = a.indexOf(this); if (i >= 0) { a.splice(i, 1); } };

function Track(nombre) { this.name = nombre; this.clips = coleccion([]); }
Track.prototype.overwriteClip = function (item, t) {
  if (!(t instanceof Time)) { throw new Error('overwriteClip: Time'); }
  const it = new TrackItem(item, t.seconds, t.seconds + 5, false);
  it._pista = this; this.clips._a.push(it);
};
let pedidoActual = null;
function Sequence(nombre, clip) {
  this.name = nombre; this.sequenceID = 'S' + (++nodo);
  this.frameSizeHorizontal = (pedidoActual && pedidoActual.ancho) || 1080; this.frameSizeVertical = (pedidoActual && pedidoActual.alto) || 1920;
  this.videoTracks = coleccion([new Track('V1')]); this.audioTracks = coleccion([new Track('A1')]);
  const dur = (pedidoActual && pedidoActual.duracion) || 60;
  const v = new TrackItem(clip, 0, dur, false); v._pista = this.videoTracks[0]; this.videoTracks[0].clips._a.push(v);
  const a = new TrackItem(clip, 0, dur, false); a._pista = this.audioTracks[0]; this.audioTracks[0].clips._a.push(a);
}
Sequence.prototype.importMGT = function (ruta, ticks, v) {
  if (typeof ticks !== 'string') { throw new Error('importMGT: ticks en texto'); }
  if (!fs.existsSync(ruta)) { throw new Error('no existe la plantilla ' + ruta); }
  const s = Number(ticks) / TICKS, pista = this.videoTracks[v];
  const it = new TrackItem(null, s, s + 10, true); it._pista = pista; pista.clips._a.push(it); return it;
};
Sequence.prototype.setPlayerPosition = function (t) { this._cti = Number(t) / TICKS; };

const raiz = new Item('Root', ProjectItemType.ROOT);
const secuencias = [];
const project = {
  rootItem: raiz, path: path.join(base, 'falso', 'proyecto.prproj'), name: 'proyecto.prproj', sequences: coleccion(secuencias), activeSequence: null,
  importFiles(rutas, _a, bin) { rutas.forEach((r) => { if (!fs.existsSync(r)) { throw new Error('no existe ' + r); } bin.children._a.push(new Item(path.basename(r), ProjectItemType.CLIP, r)); }); return true; },
  createNewSequenceFromClips(n, items) { const s = new Sequence(n, items[0]); secuencias.push(s); this.activeSequence = s; return s; },
  deleteSequence(s) { secuencias.splice(secuencias.indexOf(s), 1); return true; },
  openSequence() { return true; }, save() {},
};
const app = { version: '26.5.2 (falso)', projects: { numProjects: 1 }, project, enableQE() {}, newProject() { return true; } };
const qe = { project: { getActiveSequence() {
  const s = project.activeSequence;
  return {
    addTracks(nv, _dv, na) { for (let i = 0; i < nv; i++) { s.videoTracks._a.push(new Track('V' + (s.videoTracks._a.length + 1))); } for (let i = 0; i < na; i++) { s.audioTracks._a.push(new Track('A')); } },
    get CTI() { return { timecode: '00:00:00:00' }; },
    exportFramePNG(_tc, ruta) { fs.writeFileSync(ruta + '.png', 'falso'); },
  };
} } };
const $ = { fileName: jsxPath, os: 'Macintosh OS 15.0 (falso)', sleep() {}, evalFile(f) { vm.runInThisContext(fs.readFileSync(f.fsName || f, 'utf8')); } };
Object.assign(globalThis, { File, Folder, Time, ProjectItemType, app, qe, $ });
vm.runInThisContext(fs.readFileSync(jsxPath, 'utf8'), { filename: jsxPath });

const cola = path.join(base, 'CineCaptions', 'premiere');
const hasta = Date.now() + 1000 * Number(maxS || 600);
let vuelta = 0;
const reloj = setInterval(() => {
  vuelta += 1;
  try {
    const p = path.join(cola, 'pedido.json');
    if (fs.existsSync(p)) { try { pedidoActual = JSON.parse(fs.readFileSync(p, 'utf8')); } catch (e) { return; } }   // (a medio escribir: la próxima vuelta)
    const r = CC.revisar(vuelta % 3 === 1);
    if (r === 'colocado' || r === 'error') {
      clearInterval(reloj);
      const res = JSON.parse(fs.readFileSync(path.join(cola, 'resultado.json'), 'utf8'));
      const s = secuencias[secuencias.length - 1];
      const resumen = { r, ok: res.ok, error: res.error, textos: res.textos, textos_total: res.textos_total, textos_animados: res.textos_animados,
        imagenes: res.imagenes, imagenes_total: res.imagenes_total, sfx: res.sfx, sfx_total: res.sfx_total, reintentos: res.reintentos, con_textos: res.con_textos };
      if (s) {
        resumen.pistas_video = s.videoTracks.numTracks;
        resumen.clips = s.videoTracks._a.reduce((n, tr) => n + tr.clips._a.length, 0);
        resumen.claves = s.videoTracks._a.reduce((n, tr) => n + tr.clips._a.reduce((m, c) => m + c.components._a.reduce((q, cp) => q + cp.properties._a.reduce((z, pr) => z + pr.keys.length, 0), 0), 0), 0);
      }
      console.log('PREMIERE_FALSO ' + JSON.stringify(resumen));
      process.exit(res.ok ? 0 : 1);
    }
  } catch (e) {
    console.log('PREMIERE_FALSO_EXCEPCION ' + (e && e.stack || e));
    process.exit(1);
  }
  if (Date.now() > hasta) { clearInterval(reloj); console.log('PREMIERE_FALSO sin pedido'); process.exit(2); }
}, 300);
