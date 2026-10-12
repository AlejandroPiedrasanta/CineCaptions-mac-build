// CineCaptions · By Cinema Productions
// 2_recursos/edicion_pro/ograf/lib/motor.js — motor común de las piezas OGraf de «Edición PRO» (DaVinci Resolve 21.1+).
//
// Cada pieza es una FUNCIÓN PURA DEL TIEMPO: Resolve pide goToTime(t) en cualquier orden (adelante, atrás, al azar, al exportar)
// y el mismo t tiene que dar SIEMPRE el mismo fotograma. Por eso aquí no hay setTimeout, requestAnimationFrame, Date ni Math.random:
// todo sale de t. Una pieza solo define construir() (crea sus elementos con el estado del Inspector) y pintar(t, q)
// (t = segundos desde que entra; q = 0..1 de la salida, que empieza en el stopAction que Resolve pone al final del clip).
//
// Medidas: el lienzo es el del timeline (renderCharacteristics). La unidad U = lado corto / 1080, así la misma pieza sirve en
// 1080x1920, 1920x1080 o 4K. Los textos se miden con canvas (determinista) y se encogen para no salirse nunca del cuadro.

export const clamp = (v, a = 0, b = 1) => (v < a ? a : v > b ? b : v);
export const lerp = (a, b, p) => a + (b - a) * p;
export const E = {
  lin: p => p,
  out2: p => 1 - (1 - p) * (1 - p),
  out3: p => 1 - Math.pow(1 - p, 3),
  out4: p => 1 - Math.pow(1 - p, 4),
  in2: p => p * p,
  in3: p => p * p * p,
  io3: p => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
  ioSine: p => -(Math.cos(Math.PI * p) - 1) / 2,
  outExpo: p => (p >= 1 ? 1 : 1 - Math.pow(2, -10 * p)),
  back: p => { const s = 1.70158; return 1 + (s + 1) * Math.pow(p - 1, 3) + s * Math.pow(p - 1, 2); },
};
/* progreso 0..1 de algo que empieza en t0 y dura d */
export const P = (t, t0, d, e = E.out3) => e(clamp((t - t0) / Math.max(d, 1e-6)));
/* RESORTES:INICIO (lo escribe 1_codigo/herramientas_dev/resortes_motion.py: no lo edites a mano) */
/* Resortes de Motion (motion.dev, MIT): tablas de 65 muestras de 0 a d segundos (lo que tarda en quedarse quieto). */
export const RESORTES = {
  suave: { d: 0.739, k: 140, a: 20, v: [0,0.0086,0.032,0.0666,0.1097,0.1587,0.2115,0.2666,0.3226,0.3783,0.4328,0.4855,0.536,0.5837,0.6285,0.6703,0.7089,0.7445,0.7769,0.8064,0.833,0.8569,0.8782,0.8972,0.914,0.9287,0.9416,0.9528,0.9625,0.9708,0.9779,0.9839,0.9889,0.9931,0.9965,0.9993,1.0015,1.0032,1.0046,1.0055,1.0062,1.0067,1.0069,1.007,1.0069,1.0067,1.0065,1.0062,1.0059,1.0055,1.0051,1.0047,1.0043,1.004,1.0036,1.0032,1.0029,1.0026,1.0023,1.002,1.0018,1.0016,1.0014,1.0012,1] },
  firme: { d: 0.493, k: 320, a: 26, v: [0,0.0089,0.0332,0.0697,0.1155,0.1682,0.2257,0.286,0.3477,0.4093,0.4699,0.5287,0.5848,0.6379,0.6876,0.7336,0.7759,0.8143,0.849,0.8799,0.9073,0.9314,0.9522,0.9701,0.9852,0.9979,1.0083,1.0166,1.0232,1.0282,1.0317,1.0341,1.0355,1.036,1.0358,1.035,1.0338,1.0322,1.0303,1.0283,1.0261,1.0239,1.0217,1.0195,1.0174,1.0153,1.0134,1.0116,1.0099,1.0084,1.0069,1.0057,1.0045,1.0035,1.0026,1.0019,1.0012,1.0006,1.0002,0.9998,0.9995,0.9992,0.999,0.9989,1] },
  rebote: { d: 1.052, k: 210, a: 13, v: [0,0.0263,0.0971,0.2002,0.3241,0.4585,0.5946,0.7251,0.8445,0.9489,1.0357,1.104,1.1539,1.1864,1.2031,1.2063,1.1984,1.1819,1.1594,1.1331,1.105,1.0771,1.0505,1.0266,1.0059,0.9888,0.9756,0.9662,0.9604,0.9576,0.9576,0.9597,0.9634,0.9683,0.9739,0.9797,0.9854,0.9908,0.9956,0.9997,1.003,1.0056,1.0073,1.0084,1.0088,1.0087,1.0082,1.0073,1.0063,1.0051,1.0039,1.0027,1.0016,1.0007,0.9999,0.9992,0.9987,0.9984,1,1,1,1,0.9985,0.9988,1] },
  elastico: { d: 1.484, k: 260, a: 9, v: [0,0.0645,0.2336,0.4663,0.7218,0.9639,1.1648,1.3074,1.3848,1.3996,1.3618,1.286,1.1888,1.0864,0.9925,0.9172,0.8664,0.8419,0.8417,0.8612,0.8944,0.9345,0.9753,1.0114,1.0393,1.0571,1.0643,1.0622,1.0528,1.0385,1.0221,1.0061,0.9923,0.9821,0.976,0.9741,0.9757,0.9801,0.9862,0.9928,0.9991,1.0043,1.008,1.01,1.0104,1.0094,1.0074,1.0049,1.0022,0.9998,0.9979,0.9965,0.9959,0.9959,0.9964,0.9973,0.9983,0.9994,1.0003,1.001,1.0015,1,1,1.0014,1] },
};
const _resorte = v => p => { if (p <= 0) return 0; if (p >= 1) return 1; const x = p * (v.length - 1), i = Math.floor(x); return v[i] + (v[i + 1] - v[i]) * (x - i); };
for (const [n, r] of Object.entries(RESORTES)) E[n] = _resorte(r.v);
/* progreso con resorte: S(t, t0, 'rebote') (la duración es la del resorte; `vel` la acorta o alarga) */
export const S = (t, t0, nombre = 'firme', vel = 1) => { const r = RESORTES[nombre] || RESORTES.firme; return E[nombre in RESORTES ? nombre : 'firme']((t - t0) / (r.d * vel)); };
/* RESORTES:FIN */
/* 0 -> 1 -> 0 entre t0 y t0 + d */
export const bump = (t, t0, d) => (t < t0 || t > t0 + d ? 0 : Math.sin((Math.PI * (t - t0)) / d));

/* ---------- fuentes (todas OFL, dentro del paquete) ---------- */
const FUENTES = {
  serif: [['CCSerif', 'serif-400.woff2', { weight: '400' }], ['CCSerif', 'serif-400i.woff2', { weight: '400', style: 'italic' }]],
  grotesk: [['CCGrotesk', 'grotesk.woff2', { weight: '300 700' }]],
  redonda: [['CCRedonda', 'outfit-600.woff2', { weight: '600' }], ['CCRedonda', 'outfit-800.woff2', { weight: '800' }]],
  mono: [['CCMono', 'jbmono-500.woff2', { weight: '500' }]],
};
export const FAMILIA = {
  serif: "'CCSerif', Georgia, serif",
  grotesk: "'CCGrotesk', 'Segoe UI', Arial, sans-serif",
  redonda: "'CCRedonda', 'Segoe UI', Arial, sans-serif",
  mono: "'CCMono', Consolas, monospace",
};
export const PESO = { serif: 400, grotesk: 700, redonda: 800, mono: 500 };
const _cargadas = new Set();
async function cargarFuentes(familias) {
  for (const fam of familias) {
    for (const [nombre, archivo, op] of FUENTES[fam] || []) {
      const clave = nombre + archivo;
      if (_cargadas.has(clave)) continue;
      try {
        const f = new FontFace(nombre, `url("${new URL('./fonts/' + archivo, import.meta.url)}")`, op);
        await f.load();
        document.fonts.add(f);
        _cargadas.add(clave);
      } catch (e) { /* sin la fuente: la de respaldo del sistema */ }
    }
  }
}

/* ---------- medir texto (canvas: no depende de que el elemento ya esté en pantalla) ---------- */
let _ctx = null;
export function anchoTexto(texto, px, familia, peso = 400, estilo = 'normal', tracking = 0) {
  _ctx = _ctx || document.createElement('canvas').getContext('2d');
  _ctx.font = `${estilo} ${peso} ${px}px ${FAMILIA[familia] || familia}`;
  return _ctx.measureText(String(texto)).width + tracking * px * Math.max(0, String(texto).length - 1);
}

/* ---------- utilidades de las piezas ---------- */
export function el(tag, cls, padre, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  if (padre) padre.appendChild(e);
  return e;
}
export const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
/* "0.0, 0.42, 1.1" -> [0, 0.42, 1.1] (los huecos se rellenan con el anterior + paso) */
export function tiempos(texto, n, paso = 0.35) {
  const v = String(texto ?? '').split(/[,; ]+/).map(Number).filter(x => isFinite(x));
  const out = [];
  for (let i = 0; i < n; i++) out.push(v[i] != null ? v[i] : (i ? out[i - 1] + paso : 0));
  return out;
}
/* rgb de un color #rrggbb */
export function rgb(hex) {
  const h = String(hex || '#ffffff').replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map(c => c + c).join('') : h.slice(0, 6), 16) || 0;
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
/* negro o blanco, lo que mejor se lea sobre ese color */
export function sobre(hex) {
  const [r, g, b] = rgb(hex);
  return 0.299 * r + 0.587 * g + 0.114 * b > 150 ? '#111111' : '#ffffff';
}
/* palabras de un texto, cada una en su <span class="w"> con sus letras en <span class="c"> (para animar letra a letra) */
export function palabras(padre, texto) {
  const ws = [];
  String(texto ?? '').split(/\s+/).filter(Boolean).forEach((w, i) => {
    if (i) padre.appendChild(document.createTextNode(' '));
    const s = el('span', 'w', padre);
    s._c = [...w].map(ch => el('span', 'c', s, esc(ch)));
    ws.push(s);
  });
  return ws;
}
export const ICONOS = {
  check: '<path d="M20 6 9 17l-5-5"/>',
  pin: '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
  flecha: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
  estrella: '<path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.12 2.12 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.12 2.12 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.12 2.12 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.12 2.12 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.12 2.12 0 0 0 1.597-1.16z"/>',
  corazon: '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
  camara: '<path d="m16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.87a.5.5 0 0 0-.752-.432L16 10.5"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
  casa: '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  cubiertos: '<path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/><path d="M7 2v20"/><path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/>',
  anillos: '<circle cx="9" cy="14" r="6"/><circle cx="15" cy="14" r="6"/><path d="m9 5 1.5-2h3L15 5"/>',
  corona: '<path d="M11.562 3.266a.5.5 0 0 1 .876 0L15.39 8.87a1 1 0 0 0 1.516.294L21.183 5.5a.5.5 0 0 1 .798.519l-2.834 10.246a1 1 0 0 1-.956.734H5.81a1 1 0 0 1-.957-.734L2.02 6.02a.5.5 0 0 1 .798-.519l4.276 3.664a1 1 0 0 0 1.516-.294z"/><path d="M5 21h14"/>',
};
/* más iconos Lucide (lucide.dev, ISC) para las infografías de concepto: copiados tal cual de la plantilla de animaciones */
const ICONOS_LUCIDE = {
  /* iconos de tema (Lucide, ISC; vía Supericons): casa, boda/XV, restaurante, detrás de cámara */
  bed: '<path d="M2 20v-8a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v8"/><path d="M4 10V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v4"/><path d="M12 4v6"/><path d="M2 18h20"/>',
  bath: '<path d="M10 4 8 6"/><path d="M17 19v2"/><path d="M2 12h20"/><path d="M7 19v2"/><path d="M9 5 7.621 3.621A2.121 2.121 0 0 0 4 5v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5"/>',
  trees: '<path d="M10 10v.2A3 3 0 0 1 8.9 16H5a3 3 0 0 1-1-5.8V10a3 3 0 0 1 6 0Z"/><path d="M7 16v6"/><path d="M13 19v3"/><path d="M12 19h8.3a1 1 0 0 0 .7-1.7L18 14h.3a1 1 0 0 0 .7-1.7L16 9h.2a1 1 0 0 0 .8-1.7L13 3l-1.4 1.5"/>',
  waves: '<path d="M2 6c.6.5 1.2 1 2.5 1C7 7 7 5 9.5 5c2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M2 12c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M2 18c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/>',
  car: '<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/>',
  cake: '<path d="M20 21v-8a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8"/><path d="M4 16s.5-1 2-1 2.5 2 4 2 2.5-2 4-2 2.5 2 4 2 2-1 2-1"/><path d="M2 21h20"/><path d="M7 8v3"/><path d="M12 8v3"/><path d="M17 8v3"/><path d="M7 4h.01"/><path d="M12 4h.01"/><path d="M17 4h.01"/>',
  gem: '<path d="M10.5 3 8 9l4 13 4-13-2.5-6"/><path d="M17 3a2 2 0 0 1 1.6.8l3 4a2 2 0 0 1 .013 2.382l-7.99 10.986a2 2 0 0 1-3.247 0l-7.99-10.986A2 2 0 0 1 2.4 7.8l2.998-3.997A2 2 0 0 1 7 3z"/><path d="M2 9h20"/>',
  wine: '<path d="M8 22h8"/><path d="M7 10h10"/><path d="M12 15v7"/><path d="M12 15a5 5 0 0 0 5-5c0-2-.5-4-2-8H9c-1.5 4-2 6-2 8a5 5 0 0 0 5 5Z"/>',
  chefHat: '<path d="M17 21a1 1 0 0 0 1-1v-5.35c0-.457.316-.844.727-1.041a4 4 0 0 0-2.134-7.589 5 5 0 0 0-9.186 0 4 4 0 0 0-2.134 7.588c.411.198.727.585.727 1.041V20a1 1 0 0 0 1 1Z"/><path d="M6 17h12"/>',
  coffee: '<path d="M10 2v2"/><path d="M14 2v2"/><path d="M16 8a1 1 0 0 1 1 1v8a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1h14a4 4 0 1 1 0 8h-1"/><path d="M6 2v2"/>',
  pizza: '<path d="m12 14-1 1"/><path d="m13.75 18.25-1.25 1.42"/><path d="M17.775 5.654a15.68 15.68 0 0 0-12.121 12.12"/><path d="M18.8 9.3a1 1 0 0 0 2.1 7.7"/><path d="M21.964 20.732a1 1 0 0 1-1.232 1.232l-18-5a1 1 0 0 1-.695-1.232A19.68 19.68 0 0 1 15.732 2.037a1 1 0 0 1 1.232.695z"/>',
  aperture: '<circle cx="12" cy="12" r="10"/><path d="m14.31 8 5.74 9.94"/><path d="M9.69 8h11.48"/><path d="m7.38 12 5.74-9.94"/><path d="M9.69 16 3.95 6.06"/><path d="M14.31 16H2.83"/><path d="m16.62 12-5.74 9.94"/>',
  mountain: '<path d="m8 3 4 8 5-5 5 15H2L8 3z"/>',
  sofa: '<path d="M20 9V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v3"/><path d="M2 16a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-5a2 2 0 0 0-4 0v1.5a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5V11a2 2 0 0 0-4 0z"/><path d="M4 18v2"/><path d="M20 18v2"/><path d="M12 4v9"/>',
  ruler: '<path d="M21.3 15.3a2.4 2.4 0 0 1 0 3.4l-2.6 2.6a2.4 2.4 0 0 1-3.4 0L2.7 8.7a2.41 2.41 0 0 1 0-3.4l2.6-2.6a2.41 2.41 0 0 1 3.4 0Z"/><path d="m14.5 12.5 2-2"/><path d="m11.5 9.5 2-2"/><path d="m8.5 6.5 2-2"/><path d="m17.5 15.5 2-2"/>',
  flower: '<path d="M12 5a3 3 0 1 1 3 3m-3-3a3 3 0 1 0-3 3m3-3v1M9 8a3 3 0 1 0 3 3M9 8h1m5 0a3 3 0 1 1-3 3m3-3h-1m-2 3v-1"/><circle cx="12" cy="8" r="2"/><path d="M12 10v12"/><path d="M12 22c4.2 0 7-1.667 7-5-4.2 0-7 1.667-7 5Z"/><path d="M12 22c-4.2 0-7-1.667-7-5 4.2 0 7 1.667 7 5Z"/>',
  heartHandshake: '<path d="M19.414 14.414C21 12.828 22 11.5 22 9.5a5.5 5.5 0 0 0-9.591-3.676.6.6 0 0 1-.818.001A5.5 5.5 0 0 0 2 9.5c0 2.3 1.5 4 3 5.5l5.535 5.362a2 2 0 0 0 2.879.052 2.12 2.12 0 0 0-.004-3 2.124 2.124 0 1 0 3-3 2.124 2.124 0 0 0 3.004 0 2 2 0 0 0 0-2.828l-1.881-1.882a2.41 2.41 0 0 0-3.409 0l-1.71 1.71a2 2 0 0 1-2.828 0 2 2 0 0 1 0-2.828l2.823-2.762"/>',
  plane: '<path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/>',
  shieldCheck: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
  map: '<path d="M14.106 5.553a2 2 0 0 0 1.788 0l3.659-1.83A1 1 0 0 1 21 4.619v12.764a1 1 0 0 1-.553.894l-4.553 2.277a2 2 0 0 1-1.788 0l-4.212-2.106a2 2 0 0 0-1.788 0l-3.659 1.83A1 1 0 0 1 3 19.381V6.618a1 1 0 0 1 .553-.894l4.553-2.277a2 2 0 0 1 1.788 0z"/><path d="M15 5.764v15"/><path d="M9 3.236v15"/>',
  gift: '<path d="M12 7v14"/><path d="M20 11v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-8"/><path d="M7.5 7a1 1 0 0 1 0-5A4.8 8 0 0 1 12 7a4.8 8 0 0 1 4.5-5 1 1 0 0 1 0 5"/><rect x="3" y="7" width="18" height="4" rx="1"/>',
  music: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
  bell: '<path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/>',
  briefcase: '<path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/><rect width="20" height="14" x="2" y="6" rx="2"/>',
  building2: '<path d="M10 12h4"/><path d="M10 8h4"/><path d="M14 21v-3a2 2 0 0 0-4 0v3"/><path d="M6 10H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2"/><path d="M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16"/>',
  calendarDays: '<path d="M8 2v3"/><path d="M16 2v3"/><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M8 13h.01"/><path d="M12 13h.01"/><path d="M16 13h.01"/><path d="M8 17h.01"/><path d="M12 17h.01"/><path d="M16 17h.01"/>',
  camera: '<path d="M13.997 4a2 2 0 0 1 1.76 1.05l.486.9A2 2 0 0 0 18.003 7H20a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h1.997a2 2 0 0 0 1.759-1.048l.489-.904A2 2 0 0 1 10.004 4z"/><circle cx="12" cy="13" r="3"/>',
  chartColumn: '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
  clapperboard: '<path d="m12.296 3.464 3.02 3.956"/><path d="M20.2 6 3 11l-.9-2.4c-.3-1.1.3-2.2 1.3-2.5l13.5-4c1.1-.3 2.2.3 2.5 1.3z"/><path d="M3 11h18v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="m6.18 5.276 3.1 3.899"/>',
  clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  coins: '<path d="M13.744 17.736a6 6 0 1 1-7.48-7.48"/><path d="M15 6h1v4"/><path d="m6.134 14.768.866-.5 2 3.464"/><circle cx="16" cy="8" r="6"/>',
  crown: '<path d="M11.562 3.266a.5.5 0 0 1 .876 0L15.39 8.87a1 1 0 0 0 1.516.294L21.183 5.5a.5.5 0 0 1 .798.519l-2.834 10.246a1 1 0 0 1-.956.734H5.81a1 1 0 0 1-.957-.734L2.02 6.02a.5.5 0 0 1 .798-.519l4.276 3.664a1 1 0 0 0 1.516-.294z"/><path d="M5 21h14"/>',
  film: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M7 3v18"/><path d="M3 7.5h4"/><path d="M3 12h18"/><path d="M3 16.5h4"/><path d="M17 3v18"/><path d="M17 7.5h4"/><path d="M17 16.5h4"/>',
  globe: '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
  graduationCap: '<path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/>',
  hourglass: '<path d="M5 22h14"/><path d="M5 2h14"/><path d="M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22"/><path d="M7 2v4.172a2 2 0 0 0 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2"/>',
  image: '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
  key: '<path d="m2 21 9.6-9.6"/><path d="m7.5 15.5 2.3 2.3a1 1 0 0 1 0 1.4l-2.1 2.1a1 1 0 0 1-1.4 0L4 19"/><circle cx="15.5" cy="7.5" r="5.5"/>',
  lightbulb: '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
  mail: '<path d="m22 7-8.991 5.727a2 2 0 0 1-2.009 0L2 7"/><rect x="2" y="4" width="20" height="16" rx="2"/>',
  medal: '<path d="M7.21 15 2.66 7.14a2 2 0 0 1 .13-2.2L4.4 2.8A2 2 0 0 1 6 2h12a2 2 0 0 1 1.6.8l1.6 2.14a2 2 0 0 1 .14 2.2L16.79 15"/><path d="M11 12 5.12 2.2"/><path d="m13 12 5.88-9.8"/><path d="M8 7h8"/><circle cx="12" cy="17" r="5"/><path d="M12 18v-2h-.5"/>',
  messageSquare: '<path d="M22 17a2 2 0 0 1-2 2H6.828a2 2 0 0 0-1.414.586l-2.202 2.202A.71.71 0 0 1 2 21.286V5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2z"/>',
  mic: '<path d="M12 19v3"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><rect x="9" y="2" width="6" height="13" rx="3"/>',
  moon: '<path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401"/>',
  palette: '<path d="M12 22a1 1 0 0 1 0-20 10 9 0 0 1 10 9 5 5 0 0 1-5 5h-2.25a1.75 1.75 0 0 0-1.4 2.8l.3.4a1.75 1.75 0 0 1-1.4 2.8z"/><circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/>',
  percent: '<line x1="19" x2="5" y1="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
  piggyBank: '<path d="M11 17h3v2a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1v-3a3.16 3.16 0 0 0 2-2h1a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1h-1a5 5 0 0 0-2-4V3a4 4 0 0 0-3.2 1.6l-.3.4H11a6 6 0 0 0-6 6v1a5 5 0 0 0 2 4v3a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1z"/><path d="M16 10h.01"/><path d="M2 8v1a2 2 0 0 0 2 2h1"/>',
  rocket: '<path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09"/><path d="M9 12a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.4 22.4 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 .05 5 .05"/>',
  scissors: '<circle cx="6" cy="6" r="3"/><path d="M8.12 8.12 12 12"/><path d="M20 4 8.12 15.88"/><circle cx="6" cy="18" r="3"/><path d="M14.8 14.8 20 20"/>',
  shoppingCart: '<path d="m2.05 2.05 1.099-.028a1 1 0 0 1 1.008.815l2.69 14.347A1 1 0 0 0 7.83 18H18"/><path d="M4.563 5h16.435a1 1 0 0 1 .981 1.204l-1.026 6.226A2 2 0 0 1 18.962 14H6.25"/><circle cx="18" cy="20" r="2"/><circle cx="8" cy="20" r="2"/>',
  smartphone: '<rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/>',
  sparkles: '<path d="M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z"/><path d="M20 2v4"/><path d="M22 4h-4"/><circle cx="4" cy="20" r="2"/>',
  store: '<path d="M15 21v-5a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v5"/><path d="M17.774 10.31a1.12 1.12 0 0 0-1.549 0 2.5 2.5 0 0 1-3.451 0 1.12 1.12 0 0 0-1.548 0 2.5 2.5 0 0 1-3.452 0 1.12 1.12 0 0 0-1.549 0 2.5 2.5 0 0 1-3.77-3.248l2.889-4.184A2 2 0 0 1 7 2h10a2 2 0 0 1 1.653.873l2.895 4.192a2.5 2.5 0 0 1-3.774 3.244"/><path d="M4 10.95V19a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8.05"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
  sunrise: '<path d="M12 2v8"/><path d="m4.93 10.93 1.41 1.41"/><path d="M2 18h2"/><path d="M20 18h2"/><path d="m19.07 10.93-1.41 1.41"/><path d="M22 22H2"/><path d="m8 6 4-4 4 4"/><path d="M16 18a4 4 0 0 0-8 0"/>',
  target: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
  thumbsUp: '<path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"/><path d="M7 10v12"/>',
  timer: '<line x1="10" x2="14" y1="2" y2="2"/><line x1="12" x2="15" y1="14" y2="11"/><circle cx="12" cy="14" r="8"/>',
  trendingUp: '<path d="M16 7h6v6"/><path d="m22 7-8.5 8.5-5-5L2 17"/>',
  trophy: '<path d="M10 14.66V17a1 1 0 0 1-1 1 2 2 0 0 0-2 2v2"/><path d="M14 14.66V17a1 1 0 0 0 1 1 2 2 0 0 1 2 2v2"/><path d="M17.916 10H19.5A2.5 2.5 0 0 0 22 7.5V5a1 1 0 0 0-1-1h-3"/><path d="M4 22h16"/><path d="M6 9a6 6 0 0 0 12 0V3a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1z"/><path d="M6.084 10H4.5A2.5 2.5 0 0 1 2 7.5V5a1 1 0 0 1 1-1h3"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><path d="M16 3.128a4 4 0 0 1 0 7.744"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><circle cx="9" cy="7" r="4"/>',
  video: '<path d="m16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.87a.5.5 0 0 0-.752-.432L16 10.5"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
  wrench: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.106-3.105c.32-.322.863-.22.983.218a6 6 0 0 1-8.259 7.057l-7.91 7.91a1 1 0 0 1-2.999-3l7.91-7.91a6 6 0 0 1 7.057-8.259c.438.12.54.662.219.984z"/>',
  zap: '<path d="M15.914 4a1.5 1.5 0 00-2.474-1.561l-9 9A1.5 1.5 0 005.5 14h4.002a.5.5 0 01.471.666L8.086 20a1.5 1.5 0 002.475 1.56l9-9A1.5 1.5 0 0018.5 10h-3.997a.5.5 0 01-.472-.667z"/>',
};
Object.assign(ICONOS, ICONOS_LUCIDE);
/* iconos 3D (3dicons, CC0): la imagen va dentro del .ograf, en lib/iconos3d/ (solo las que usa la pieza) */
export const IMG3D = n => new URL('./iconos3d/' + String(n || '').replace(/[^a-z0-9-]/gi, '') + '.png', import.meta.url).href;
export function icono(nombre, tam, grosor = 2) {
  return `<svg viewBox="0 0 24 24" width="${tam}" height="${tam}" fill="none" stroke="currentColor" stroke-width="${grosor}" stroke-linecap="round" stroke-linejoin="round" style="display:block">${ICONOS[nombre] || ''}</svg>`;
}

/* ---------- la clase base: los 8 métodos de OGraf y la reproducción del calendario de Resolve ---------- */
const CSS_BASE = `
:host{position:absolute;left:0;top:0;width:100vw;height:100vh;display:block;pointer-events:none;overflow:visible}
*{box-sizing:border-box;margin:0;padding:0}
.escena{position:absolute;left:0;top:0;overflow:visible;transform-origin:0 0}
.L{position:absolute;left:0;top:0;will-change:transform,opacity}
.w{display:inline-block;white-space:nowrap}
.c{display:inline-block;white-space:pre}
`;

export class PiezaPro extends HTMLElement {
  /* lo que cada pieza declara */
  static DEFAULTS = {};
  static FUENTES = ['serif', 'grotesk', 'redonda', 'mono'];
  static SALIDA = 0.45;          // segundos de la animación de salida (= actionDurations.stopAction del manifiesto)
  construir(s) {}
  pintar(t, q, s) {}

  constructor() {
    super();
    this._root = this.attachShadow({ mode: 'open' });
    this._css = document.createElement('style');
    this._escena = document.createElement('div');
    this._escena.className = 'escena';
    this._root.append(this._css, this._escena);
    this._base = { ...this.constructor.DEFAULTS };
    this._s = { ...this._base };
    this._schedule = [];
    this._montado = '';
    this._ts = 0;
    this.W = 1920; this.H = 1080; this.U = 1;
  }

  /* --- medidas del lienzo --- */
  _medidas(res) {
    this.W = Math.max(16, Math.round(res?.width || window.innerWidth || 1920));
    this.H = Math.max(16, Math.round(res?.height || window.innerHeight || 1080));
    this.U = Math.min(this.W, this.H) / 1080;
    this.vertical = this.H > this.W;
    Object.assign(this._escena.style, { width: this.W + 'px', height: this.H + 'px' });
    this.style.setProperty('--u', this.U + 'px');
    // El entorno OGraf de Resolve escala el gráfico para encajar la resolución que pide el manifiesto (1920x1080 si no dice nada)
    // en el lienzo real: en un timeline vertical lo dejaba a 0,5625 y arriba a la izquierda. Se mide ese escalado y se deshace,
    // para que la escena ocupe SIEMPRE el cuadro entero en píxeles del timeline.
    try {
      const r = this.getBoundingClientRect(), k = r.width / (this.offsetWidth || this.W);
      if (isFinite(k) && k > 0.05 && (Math.abs(k - 1) > 0.002 || Math.abs(r.left) > 0.5 || Math.abs(r.top) > 0.5))
        this._escena.style.transform = `translate(${(-r.left / k).toFixed(3)}px,${(-r.top / k).toFixed(3)}px) scale(${(1 / k).toFixed(6)})`;
      else this._escena.style.transform = 'none';
    } catch (e) { /* sin medidas: se queda como está */ }
  }
  /* coloca un elemento (x, y en px del lienzo; ax, ay = anclaje en %) */
  put(e, o) {
    const op = o.o ?? 1;
    if (!(op > 0.002)) { e.style.visibility = 'hidden'; e.style.opacity = '0'; return; }
    e.style.visibility = 'visible';
    let tr = `translate(${(o.x ?? 0).toFixed(2)}px,${(o.y ?? 0).toFixed(2)}px) translate(${-(o.ax ?? 50)}%,${-(o.ay ?? 50)}%)`;
    if (o.rx || o.ry) tr += ` perspective(1400px) rotateX(${(o.rx || 0).toFixed(2)}deg) rotateY(${(o.ry || 0).toFixed(2)}deg)`;
    if (o.r) tr += ` rotate(${o.r.toFixed(2)}deg)`;
    const s = o.s ?? 1, sx = (o.sx ?? 1) * s, sy = (o.sy ?? 1) * s;
    if (sx !== 1 || sy !== 1) tr += ` scale(${sx.toFixed(4)},${sy.toFixed(4)})`;
    e.style.transform = tr;
    e.style.transformOrigin = `${o.ax ?? 50}% ${o.ay ?? 50}%`;
    e.style.opacity = op.toFixed(4);
    e.style.filter = (o.b ?? 0) > 0.05 ? `blur(${o.b.toFixed(2)}px)` : 'none';
  }
  /* letras de una palabra: entran a partir de t0 (escalonadas) */
  letras(w, t, t0, modo = 'subir', dur = 0.42) {
    w._c.forEach((c, k) => {
      const p = clamp((t - t0 - k * 0.022) / dur), e = E.out4(p);
      c.style.opacity = clamp(p * 2.4).toFixed(3);
      if (modo === 'desenfoque') { c.style.transform = `scale(${lerp(1.18, 1, e).toFixed(3)})`; c.style.filter = p < 1 ? `blur(${((1 - e) * 9).toFixed(1)}px)` : 'none'; }
      else if (modo === 'mascara') { c.style.transform = `translateY(${((1 - e) * 0.9).toFixed(3)}em)`; c.style.filter = 'none'; }
      else { c.style.transform = `translateY(${((1 - e) * 0.42).toFixed(3)}em)`; c.style.filter = p < 1 ? `blur(${((1 - e) * 5).toFixed(1)}px)` : 'none'; }
    });
  }
  /* tamaño de letra que cabe en `ancho` px (sin pasar de `max`) */
  encajar(texto, max, ancho, familia, peso, estilo = 'normal', tracking = 0) {
    const w = anchoTexto(texto, 100, familia, peso, estilo, tracking);
    return w > 0 ? Math.min(max, (100 * ancho) / w) : max;
  }

  /* --- estado: lo del Inspector + las actualizaciones programadas --- */
  _montar(s) {
    const clave = JSON.stringify(s);
    if (clave === this._montado) return;
    this._montado = clave;
    this._escena.innerHTML = '';
    this.construir(s);
  }
  _setFrame(timestamp) {
    let s = { ...this._base }, play = null, stop = null;
    for (const ev of this._schedule) {
      if (ev.timestamp > timestamp) break;
      const a = ev.action || {};
      if (a.type === 'updateAction') s = { ...s, ...(a.params?.data || {}) };
      else if (a.type === 'playAction') { play = ev.timestamp; stop = null; }
      else if (a.type === 'stopAction') stop = ev.timestamp;
    }
    this._s = s;
    this._montar(s);
    const t = (timestamp - (play ?? 0)) / 1000;
    const q = stop != null ? clamp((timestamp - stop) / 1000 / this.constructor.SALIDA) : 0;
    this.pintar(Math.max(0, t), q, s);
  }

  /* las imágenes (iconos 3D) se cargan solas y Resolve captura el fotograma en cuanto vuelve goToTime: hay que esperarlas, como a las fuentes */
  async _listo() {
    const imgs = [...this._escena.querySelectorAll('img')];
    await Promise.all(imgs.map(i => (i.complete && i.naturalWidth ? null : i.decode().catch(() => null))));
  }

  /* --- los 8 métodos de OGraf --- */
  async load(params) {
    this._medidas(params?.renderCharacteristics?.resolution);
    this._base = { ...this.constructor.DEFAULTS, ...(params?.data || {}) };
    this._schedule = [];
    this._css.textContent = CSS_BASE + (this.constructor.CSS || '');
    await cargarFuentes(this.constructor.FUENTES);
    this._montado = '';
    this._setFrame(0);
    await this._listo();
    return { statusCode: 200 };
  }
  async dispose() { this._escena.innerHTML = ''; return { statusCode: 200 }; }
  async playAction() { return { statusCode: 200 }; }
  async stopAction() { return { statusCode: 200 }; }
  async customAction() { return { statusCode: 200 }; }
  async updateAction(params) {
    this._base = { ...this._base, ...(params?.data || {}) };
    this._setFrame(this._ts);
    await this._listo();
    return { statusCode: 200 };
  }
  async setActionsSchedule(payload) {
    // cada llamada REEMPLAZA el calendario y Resolve no lo manda ordenado
    this._schedule = (payload?.schedule || []).slice().sort((a, b) => a.timestamp - b.timestamp);
    this._setFrame(this._ts);
    await this._listo();
    return { statusCode: 200 };
  }
  async goToTime(params) {
    this._ts = params?.timestamp ?? 0;
    this._setFrame(this._ts);
    await this._listo();
    return { statusCode: 200 };
  }
}
