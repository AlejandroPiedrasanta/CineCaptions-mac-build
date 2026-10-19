// @ts-nocheck
// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/kitneon/motor.ts — v5.5.13: el motor de gráficos del kit «TEMA 1» del usuario (Escritorio/TEMA 1/graficos/motor.js), el
// MISMO código, dentro de Remotion: así el Tema 1 neón sale idéntico a su video de referencia (entregas/3_neon_kinetic_hook.mp4).
// Cambios respecto al original (solo de enchufe, ninguno de diseño ni de movimiento):
//   · crearMotor(raiz, tema, img) devuelve una instancia: cada composición tiene su escenario (antes: globales ST, R, SIG, window.TEMA);
//   · las imágenes pasan por img(src) (en el programa llegan como data: URI, fotogramas del propio video);
//   · los id de los SVG de la tarjeta de ruta llevan un número (puede haber más de una en una página).
// Cada fotograma es una función pura de t: render(t) coloca TODO en su sitio para ese instante (Remotion puede pintar en cualquier orden).

export const TEMAS = {
  neon: { on: [255, 45, 203], ruta: '#FF2DCB', barrido1: '#D6FF3B', barrido2: 'linear-gradient(#7A35F5,#2A1258 55%,#140A28)',
          aro1: 'rgba(214,255,59,.55)', aro2: 'rgba(255,45,203,.55)', disco1: 'rgba(255,255,255,.06)', disco2: 'rgba(255,255,255,.10)',
          trazo: '#D6FF3B', trazo2: '#FF2DCB', lineas: '#fff' },
  terracota: { on: [180, 86, 46], ruta: '#B4562E', barrido1: '#D88A5E', barrido2: 'linear-gradient(#BE5F35,#8E3E1F 60%)',
          aro1: 'rgba(180,86,46,.32)', aro2: 'rgba(255,255,255,.6)', disco1: 'rgba(255,255,255,.38)', disco2: 'rgba(255,255,255,.55)',
          trazo: '#FFFFFF', trazo2: '#B4562E', lineas: '#fff' },
};

export const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
export function spring(p, z = .7, w = 7.6) {
  if (p <= 0) return 0; if (p >= 1) return 1;
  const wd = w * Math.sqrt(1 - z * z);
  return 1 - Math.exp(-z * w * p) * (Math.cos(wd * p) + (z * w / wd) * Math.sin(wd * p));
}
export const sale = p => { p = clamp(p); return p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2; };
export const suave = p => { p = clamp(p); return p * p * (3 - 2 * p); };
const lerp = (a, b, p) => a + (b - a) * p;

// iconos (Lucide, licencia ISC)
export const IC = {
  globe: '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
  gamepad: '<line x1="6" x2="10" y1="11" y2="11"/><line x1="8" x2="8" y1="9" y2="13"/><line x1="15" x2="15.01" y1="12" y2="12"/><line x1="18" x2="18.01" y1="10" y2="10"/><path d="M17.32 5H6.68a4 4 0 0 0-3.978 3.59c-.006.052-.01.101-.017.152C2.604 9.416 2 14.456 2 16a3 3 0 0 0 3 3c1 0 1.5-.5 2-1l1.414-1.414A2 2 0 0 1 9.828 16h4.344a2 2 0 0 1 1.414.586L17 18c.5.5 1 1 2 1a3 3 0 0 0 3-3c0-1.545-.604-6.584-.685-7.258-.007-.05-.011-.1-.017-.151A4 4 0 0 0 17.32 5z"/>',
  music: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
  grad: '<path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/>',
  mic: '<path d="M12 19v3"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><rect x="9" y="2" width="6" height="13" rx="3"/>',
  gift: '<path d="M12 7v14"/><path d="M20 11v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-8"/><path d="M7.5 7a1 1 0 0 1 0-5A4.8 8 0 0 1 12 7a4.8 8 0 0 1 4.5-5 1 1 0 0 1 0 5"/><rect x="3" y="7" width="18" height="4" rx="1"/>',
  utensils: '<path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/><path d="M7 2v20"/><path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/>',
  star: '<path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  trophy: '<path d="M10 14.66V17a1 1 0 0 1-1 1 2 2 0 0 0-2 2v2"/><path d="M14 14.66V17a1 1 0 0 0 1 1 2 2 0 0 1 2 2v2"/><path d="M17.916 10H19.5A2.5 2.5 0 0 0 22 7.5V5a1 1 0 0 0-1-1h-3"/><path d="M4 22h16"/><path d="M6 9a6 6 0 0 0 12 0V3a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1z"/><path d="M6.084 10H4.5A2.5 2.5 0 0 1 2 7.5V5a1 1 0 0 1 1-1h3"/>',
  chat: '<path d="M22 17a2 2 0 0 1-2 2H6.828a2 2 0 0 0-1.414.586l-2.202 2.202A.71.71 0 0 1 2 21.286V5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2z"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><path d="M16 3.128a4 4 0 0 1 0 7.744"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><circle cx="9" cy="7" r="4"/>',
  cal: '<path d="M8 2v3"/><path d="M16 2v3"/><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M8 13h.01"/><path d="M12 13h.01"/><path d="M16 13h.01"/><path d="M8 17h.01"/><path d="M12 17h.01"/><path d="M16 17h.01"/>',
  clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  pin: '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
  heart: '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
  bell: '<path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/>',
  send: '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/>',
};
const ico = (n, cls = 'i') => `<svg class="${cls}" viewBox="0 0 24 24">${IC[n] || IC.star}</svg>`;
const SVGNS = 'http://www.w3.org/2000/svg';
let SERIE = 0;

export function crearMotor(ST: HTMLElement, tema = 'neon', IMG = (s: string) => s) {
  const TM = TEMAS[tema] || TEMAS.neon;
  let SIG = [];
  const R = [];          // funciones de render (una por componente)
  const BARRIDOS = [];   // tiempos de cortinillas (más subfotogramas)

  function mk(html, css = '', cls = 'a', parent = ST) {
    const d = document.createElement('div');
    d.className = cls; d.innerHTML = html; if (css) d.style.cssText += css;
    parent.appendChild(d); return d;
  }
  function pon(e, { x = 0, y = 0, s = 1, o = 1, r = 0, ry = 0, sx = 1 } = {}) {
    // v5.5.19: lo marcado con _guarda (las palabras y pegatinas de los captions) se oculta SIN soltar su sitio: con display:none, al aparecer
    // cada palabra la línea se volvía a centrar y las ya visibles saltaban de lado («de» → «de paso»: el tambaleo de las letras)
    if (o <= 0.002) {
      if (e._guarda) { if (e.style.visibility !== 'hidden') e.style.visibility = 'hidden'; }
      else if (e.style.display !== 'none') e.style.display = 'none';
      SIG.push(0); return;
    }
    if (e._guarda) { if (e.style.visibility === 'hidden') e.style.visibility = ''; }
    else if (e.style.display === 'none') e.style.display = '';
    let tr = `translate3d(${x.toFixed(2)}px,${y.toFixed(2)}px,0)`;
    if (ry) tr = `perspective(1400px) ${tr} rotateY(${ry.toFixed(2)}deg)`;
    tr += ` scale(${s.toFixed(4)})`;
    if (sx !== 1) tr += ` scaleX(${sx.toFixed(4)})`;
    if (r) tr += ` rotate(${r.toFixed(3)}deg)`;
    const op = o.toFixed(3);
    if (e._tr !== tr) { e.style.transform = tr; e._tr = tr; }
    if (e._op !== op) { e.style.opacity = op; e._op = op; }
    SIG.push(tr + op);
  }
  // entra con muelle y sale con ease-in-out; fuera de su ventana, oculto
  function ap(t, tin, tout, { dx = 0, dy = 46, din = .62, fin = .16, dout = .3, odx = 0, ody = -22, rot = 0, ry = 0 } = {}) {
    if (t < tin || t >= tout + dout) return { o: 0, x: 0, y: 0 };
    const p = spring((t - tin) / din);
    const res = { o: clamp((t - tin) / fin), x: dx * (1 - p), y: dy * (1 - p), r: rot * (1 - p), ry: ry * (1 - p) };
    if (t >= tout) { const q = sale((t - tout) / dout); res.o *= 1 - q; res.x += odx * q; res.y += ody * q; }
    return res;
  }
  function revela(t, tin, tout, h, { din = .58, rot = 5, dout = .32 } = {}) {
    if (t < tin || t >= tout + dout) return { o: 0 };
    const p = spring((t - tin) / din, .72, 7.6);
    let y = h * (1 - p);
    if (t >= tout) y -= h * 1.08 * sale((t - tout) / dout);
    return { o: clamp((t - tin) / .08), y, r: rot * (1 - p) };
  }
  function revela2(t, tin, tout, h, dir, rot, din = .55) {
    if (t < tin || t >= tout + .32) return { o: 0 };
    const p = spring((t - tin) / din, .72, 7.6);
    let y = dir * h * (1 - p);
    if (t >= tout) y -= h * 1.08 * sale((t - tout) / .32);
    return { o: clamp((t - tin) / .06), y, r: rot * (1 - p) };
  }
  function despliega(t, tin, tout, { d = .34, dout = .3 } = {}) {
    if (t < tin || t >= tout + dout) return { o: 0 };
    const p = 1 - Math.pow(1 - clamp((t - tin) / d), 3);
    return { sx: Math.max(p, .001), o: t >= tout ? 1 - sale((t - tout) / dout) : 1 };
  }
  function pega(t, tin, tout, rot) {
    if (t < tin || t >= tout + .3) return { o: 0 };
    const p = spring((t - tin) / .55, .62, 8);
    return { o: clamp((t - tin) / .07) * (t >= tout ? 1 - sale((t - tout) / .3) : 1), y: -70 * (1 - p), r: rot - 18 * (1 - p) };
  }
  function enmascara(parent, texto) {
    const m = document.createElement('span'); m.className = 'mk';
    const i = document.createElement('span'); i.className = 'in'; i.textContent = texto;
    m.appendChild(i); parent.appendChild(m); return i;
  }

  // ==== RÓTULO CLÁSICO: línea pequeña palabra a palabra + mayúsculas con máscara =========
  function rotulo({ top, sm, smT, lines, tout, glide }) {
    const c = mk('', `top:${top}px`, 'a cap');
    const piezas = [], barras = [];
    if (sm) {
      const smEl = mk('', '', 'sm', c);
      sm.split(' ').forEach((w, k) => {
        if (k) smEl.appendChild(document.createTextNode(' '));
        piezas.push({ el: enmascara(smEl, w), t: smT + .035 * k, h: 62, rot: 0 });
      });
    }
    for (const ln of lines) {
      const d = mk('', '', 'ln' + (ln.thin ? ' thin' : ''), c);
      const fs = ln.size || (ln.thin ? 92 : 150);
      d.style.fontSize = fs + 'px';
      const wrap = mk('', '', 'lnw', d);
      let host = wrap;
      if (ln.box !== undefined) {
        host = mk('', '', 'boxw' + (ln.blanco ? ' blanco' : ''), wrap);
        barras.push({ el: mk('', '', 'bxbg', host), t: ln.box - .06 });
      }
      for (const [w, t] of ln.ws) {
        const span = document.createElement('span'); span.className = 'w'; host.appendChild(span);
        if (ln.letras) [...w].forEach((ch, k) => piezas.push({ el: enmascara(span, ch), t: t + .06 * k, h: fs * 1.06, rot: 7 }));
        else piezas.push({ el: enmascara(span, w), t, h: fs * 1.06, rot: ln.thin ? 0 : 5 });
      }
      if (ln.sub !== undefined) barras.push({ el: mk('', '', 'subr', wrap), t: ln.sub });
    }
    const t0 = Math.min(...piezas.map(p => p.t), ...barras.map(b => b.t));
    R.push(t => {
      const vis = t >= t0 - .05 && t < tout + .45;
      pon(c, { y: glide ? glide(t) : 0, o: vis ? 1 : 0 });
      if (!vis) return;
      for (const b of barras) pon(b.el, despliega(t, b.t, tout));
      for (const p of piezas) pon(p.el, revela(t, p.t - .03, tout, p.h, { rot: p.rot }));
    });
    return c;
  }

  // ==== BLOQUE HOOK: tipografías mezcladas apiladas, pegatinas y trazos a mano ===========
  // items: {k:'esp'|'big'|'serif'|'script'|'stk', txt, t (o lista por palabra), size?, fill?|fills?, bg?, rot?, mt?, letras?}
  // deco:  {k:'circulo'|'lazo'|'subraya', i:[índices de items], t, color?, w?}
  function hook({ top, items, deco = [], tout, glide }) {
    const c = mk('', `top:${top}px`, 'a cap hk');
    const piezas = [], lineas = [];
    const TAM = { esp: 34, big: 170, serif: 78, script: 120, stk: 96 };
    items.forEach(it => {
      const ln = mk('', it.mt ? `margin-top:${it.mt}em` : '', 'hl-' + it.k, c);
      const fs = it.size || TAM[it.k];
      ln.style.fontSize = fs + 'px';
      const cnt = mk('', '', 'cnt', ln);
      if (it.k === 'stk') {
        cnt.classList.add('stk', 'stk-' + (it.bg || 'rojo')); cnt.textContent = it.txt; cnt._guarda = true;
        piezas.push({ tipo: 'stk', el: cnt, t: it.t, rot: it.rot ?? -4 });
      } else if (it.k === 'script') {
        cnt.classList.add('scr', it.fill || 'acento'); cnt.textContent = it.txt; cnt._guarda = true;
        piezas.push({ tipo: 'scr', el: cnt, t: it.t, rot: it.rot ?? -6 });
      } else {
        const ws = it.letras ? [...it.txt] : it.txt.split(' ');
        ws.forEach((w, k) => {
          if (k && !it.letras) cnt.appendChild(document.createTextNode(' '));
          const inner = enmascara(cnt, w);
          inner._guarda = true;
          const f = it.fills ? it.fills[k] : it.fill;
          if (f) inner.classList.add('f-' + f);
          const st = it.k === 'esp' ? .04 : it.letras ? .06 : 0;
          const tw = Array.isArray(it.t) ? it.t[k] : it.t + st * k;
          const conf = { esp: [1, 0], serif: [1, 4], big: [-1, -4] }[it.k];
          piezas.push({ tipo: 'txt', el: inner, t: tw, h: fs * 1.08, dir: conf[0], rot: conf[1] });
        });
      }
      lineas.push(cnt);
    });
    const svg = document.createElementNS(SVGNS, 'svg');
    svg.setAttribute('width', '1000'); svg.setAttribute('height', '900');
    svg.style.cssText = 'position:absolute;left:0;top:0;overflow:visible';
    c.appendChild(svg);
    const trazos = deco.map(d => {
      const pa = document.createElementNS(SVGNS, 'path');
      pa.setAttribute('fill', 'none'); pa.setAttribute('stroke', d.color || TM.trazo); pa.setAttribute('stroke-width', d.w || 7);
      pa.setAttribute('stroke-linecap', 'round'); pa.setAttribute('stroke-linejoin', 'round');
      svg.appendChild(pa); return { pa, d, len: 1 };
    });
    let medido = false;
    function medir() {
      if (!c.getClientRects().length) return;          // v5.5.17: sin maquetar (oculto) no se mide: medido 0 × 0 = un aro suelto en la esquina
      for (const tr of trazos) {
        // offsets acumulados hasta el bloque (el filter de cada línea la convierte en offsetParent)
        const cj = tr.d.i.map(i => {
          const e = lineas[i]; let x = 0, y = 0, n = e;
          while (n && n !== c) { x += n.offsetLeft; y += n.offsetTop; n = n.offsetParent; }
          return [x, y, e.offsetWidth, e.offsetHeight];
        });
        const x0 = Math.min(...cj.map(b => b[0])), y0 = Math.min(...cj.map(b => b[1]));
        const x1 = Math.max(...cj.map(b => b[0] + b[2])), y1 = Math.max(...cj.map(b => b[1] + b[3]));
        let dd = '';
        if (tr.d.k === 'subraya') dd = `M${x0 - 14} ${y1 + 4} Q${(x0 + x1) / 2} ${y1 + 36} ${x1 + 26} ${y1 - 8}`;
        else {
          const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, lazo = tr.d.k === 'lazo';
          const rx = (x1 - x0) / 2 + (lazo ? 44 : 30), ry = (y1 - y0) / 2 + (lazo ? 26 : 14), giro = (lazo ? -8 : -4) * Math.PI / 180;
          const pts = [];
          for (let k = 0; k <= 64; k++) {
            const a = -1.9 + k / 64 * Math.PI * 2 * 1.1, f = 1 + .035 * Math.sin(3 * a + .7);
            const x = rx * f * Math.cos(a), y = ry * f * Math.sin(a);
            pts.push(`${(cx + x * Math.cos(giro) - y * Math.sin(giro)).toFixed(1)} ${(cy + x * Math.sin(giro) + y * Math.cos(giro)).toFixed(1)}`);
          }
          dd = 'M' + pts.join(' L');
        }
        tr.pa.setAttribute('d', dd);
        tr.len = tr.pa.getTotalLength();
        tr.pa.style.strokeDasharray = tr.len;
      }
      medido = true;
    }
    const t0 = Math.min(...piezas.map(q => q.t));
    R.push(t => {
      const vis = t >= t0 - .05 && t < tout + .45;
      pon(c, { y: glide ? glide(t) : 0, o: vis ? 1 : 0 });
      if (!vis) return;
      if (!medido) medir();
      for (const q of piezas) {
        if (q.tipo === 'txt') pon(q.el, revela2(t, q.t - .03, tout, q.h, q.dir, q.rot));
        else if (q.tipo === 'stk') pon(q.el, pega(t, q.t - .03, tout, q.rot));
        else {
          const a = revela2(t, q.t - .03, tout, 0, 1, 0);
          const pw = 1 - Math.pow(1 - clamp((t - q.t + .03) / .5), 2.2);
          // v5.5.19: sale CON los demás (antes se quedaba sola 0,3 s, quieta, y desaparecía de golpe): se borra de izquierda a derecha y sube
          const po = t >= tout ? sale((t - tout) / .3) : 0;
          const clip = `inset(-40% ${(100 - 100 * pw).toFixed(2)}% -40% ${(-15 + 130 * po).toFixed(2)}%)`;
          if (q.el._clip !== clip) { q.el.style.clipPath = clip; q.el._clip = clip; }
          pon(q.el, { o: a.o * (1 - po * po), y: 16 * (1 - spring((t - q.t) / .55)) - 70 * po, r: q.rot });
          SIG.push(clip);
        }
      }
      const fo = t >= tout ? 1 - sale((t - tout) / .3) : 1;
      svg.style.opacity = fo.toFixed(3);
      for (const tr of trazos) {
        const pd = 1 - Math.pow(1 - clamp((t - tr.d.t) / .45), 2.4);
        const off = (tr.len * (1 - pd)).toFixed(1);
        tr.pa.style.strokeDashoffset = off; tr.pa.style.opacity = t < tr.d.t ? 0 : 1;
        SIG.push(off + fo.toFixed(3));
      }
    });
    return c;
  }

  // ==== CORTINILLA: dos paneles redondeados suben y tapan el corte en tc =================
  function barrido(tc, queda = false) {
    const css = 'width:1080px;height:3600px;border-radius:230px;';
    const p1 = mk('', css + `background:${TM.barrido1}`, 'a');
    const p2 = mk('', css + `background:${TM.barrido2}`, 'a');
    BARRIDOS.push(tc);
    R.push(t => {
      [[p1, -.07], [p2, 0]].forEach(([e, dk]) => {
        if (queda) {
          if (t < tc + dk) return pon(e, { o: 0 });
          return pon(e, { y: 1920 * (1 - spring((t - tc - dk) / .75, .74, 7.6)) });
        }
        const p = (t - (tc + dk - .4)) / .8;
        if (p <= 0 || p >= 1) return pon(e, { o: 0 });
        pon(e, { y: 1920 - 5520 * sale(p) });
      });
    });
  }

  // ==== COMPONENTES ======================================================================
  function etiqueta({ img, nombre, sub = '', tin, tout, x = 60, y = 250 }) {
    const e = mk(`<div class="tag"><img src="${IMG(img)}"><div><b>${nombre}</b><i>${sub}</i></div></div>`, `left:${x}px;top:${y}px`);
    R.push(t => pon(e, ap(t, tin, tout, { dx: -60, dy: 0, odx: -30, ody: 0, rot: -4 })));
  }
  function notificacion({ img, titulo, texto, hora = 'ahora', tin, tout, y = 236 }) {
    const n = mk(`<div class="noti"><div class="nic"><img src="${IMG(img)}"></div><div class="ntx"><b>${titulo}</b><span>${texto}</span></div><em>${hora}</em></div>`,
      `left:70px;top:${y}px`);
    R.push(t => pon(n, ap(t, tin, tout, { dy: -210, din: .7, fin: .1, ody: -230, dout: .34 })));
  }
  function degradado(tin, tout) {
    const g = mk('', '', 'a grad');
    R.push(t => {
      if (t < tin || t >= tout + .3) return pon(g, { o: 0 });
      const p = spring((t - tin) / .7, .75, 7.6);
      pon(g, { y: 1150 * (1 - p), o: clamp((t - tin) / .12) * (t >= tout ? 1 - sale((t - tout) / .3) : 1) });
    });
  }
  function tarjetaInferior({ rect, img, tin, tout, chips = [] }) {
    const [x, y, w, h, r] = rect;
    const card = mk(`<img src="${IMG(img)}" style="width:100%;height:100%;object-fit:cover;display:block">`,
      `left:${x}px;top:${y}px;width:${w}px;height:${h}px;border-radius:${r}px;overflow:hidden;box-shadow:0 22px 60px var(--sombra)`);
    let cx = x + 34;
    const cs = chips.map(([txt, ic, t, rot = -5]) => {
      const e = mk(`<div class="chip">${ico(ic)}${txt}</div>`, `left:${cx}px;top:${y - 40}px`);
      cx += 30 + txt.length * 19 + 90;
      return { e, t, rot };
    });
    R.push(t => {
      pon(card, ap(t, tin + .06, tout, { dy: 520, din: .62, fin: .08, dout: .42, ody: 560 }));
      cs.forEach((c, k) => pon(c.e, ap(t, c.t, tout - .12 + .04 * k, { dy: 40, dout: .25, ody: 30, rot: c.rot })));
    });
  }
  function orbita({ tin, tout, img, iconos, cx = 540, cy = 800, desdeY = 560 }) {
    const veil = mk('', '', 'a veil');
    const d1 = mk('', `left:${cx - 330}px;top:${cy - 330}px;width:660px;height:660px;background:${TM.disco1}`, 'a disco');
    const d2 = mk('', `left:${cx - 215}px;top:${cy - 215}px;width:430px;height:430px;background:${TM.disco2}`, 'a disco');
    const r1 = mk('', `left:${cx - 250}px;top:${cy - 250}px;width:500px;height:500px;border:2.5px solid ${TM.aro1}`, 'a ring');
    const r2 = mk('', `left:${cx - 400}px;top:${cy - 400}px;width:800px;height:800px;border:2.5px solid ${TM.aro2}`, 'a ring');
    const centro = mk(`<div class="centro"><img src="${IMG(img)}"></div>`, `left:${cx - 160}px;top:${cy - 160}px`);
    const ics = iconos.map(([n, rad, a0, w], k) => ({ el: mk(`<div class="ico">${ico(n)}</div>`, `left:${cx - 62}px;top:${cy - 62}px`), rad, a0, w, k }));
    R.push(t => {
      const on = t >= tin && t < tout + .5;
      pon(veil, { o: on ? suave((t - tin) / .4) * (1 - suave((t - tout) / .4)) : 0 });
      const fueraP = sale((t - tout) / .4);
      for (const [e, t0] of [[d1, .05], [d2, .1], [r1, .08], [r2, .14]]) {
        if (!on) { pon(e, { o: 0 }); continue; }
        const p = suave((t - tin - t0) / .5);
        pon(e, { o: p * (1 - fueraP), s: .94 + .06 * p });
      }
      const pc = ap(t, tin - .05, tout, { dy: desdeY, din: .8, fin: .1, dout: .4, ody: 0 });
      pon(centro, { ...pc, s: .55 + .45 * (1 - Math.pow(1 - clamp((t - tin + .05) / .55), 3)) });
      for (const ic of ics) {
        const ti = tin + .25 + .12 * ic.k;
        if (!on || t < ti) { pon(ic.el, { o: 0 }); continue; }
        const p = spring((t - ti) / .6);
        const rad = ic.rad - 70 * (1 - p) + 24 * fueraP;
        const ang = (ic.a0 + ic.w * (t - tin)) * Math.PI / 180;
        pon(ic.el, { x: rad * Math.cos(ang), y: rad * Math.sin(ang), o: clamp((t - ti) / .16) * (1 - fueraP) });
      }
    });
  }
  function avataresArco({ imgs, t0, paso = .1, tout, cx = 548, y = 980, sep = 184, tam = 128 }) {
    const n = imgs.length, mid = (n - 1) / 2;
    const pos = imgs.map((_, k) => [cx - tam / 2 + (k - mid) * sep, y - (k === Math.round(mid) && n % 2 ? 56 : 0)]);
    const p0 = [pos[0][0] + tam / 2, pos[0][1] + tam / 2], p1 = [pos[n - 1][0] + tam / 2, pos[n - 1][1] + tam / 2];
    const arco = mk(`<svg width="1080" height="1920" style="position:absolute;left:0;top:0"><path d="M${p0[0]} ${p0[1]} Q${cx} ${p0[1] - 114} ${p1[0]} ${p1[1]}"
       fill="none" stroke="${TM.lineas}" stroke-width="5" stroke-linecap="round" stroke-opacity=".85"/></svg>`);
    const path = arco.querySelector('path'), LA = path.getTotalLength();
    path.style.strokeDasharray = LA;
    const avs = imgs.map((f, k) => ({ el: mk(`<img class="av" src="${IMG(f)}" style="width:${tam}px;height:${tam}px">`, `left:${pos[k][0]}px;top:${pos[k][1]}px`), t: t0 + paso * k, k }));
    R.push(t => {
      const vis = t >= t0 - .05 && t < tout + .3;
      pon(arco, { o: vis ? (t >= tout ? 1 - sale((t - tout) / .3) : 1) : 0 });
      if (vis) { const o = (LA * (1 - suave((t - t0 - .06) / .5))).toFixed(1); path.style.strokeDashoffset = o; SIG.push(o); }
      for (const a of avs) pon(a.el, ap(t, a.t, tout, { dy: 150, din: .62, fin: .1, rot: (a.k - mid) * 8 }));
    });
  }
  function filaEtiqueta({ titulo, icono = 'star', t, tout, pills, x = 70, y = 1150, fill = 'acento' }) {
    const tit = mk(`<div style="display:flex;align-items:center;gap:26px"><div class="badge">${ico(icono)}</div>
      <div class="ln f-${fill}" style="font-size:150px;text-align:left;text-shadow:none;filter:drop-shadow(0 6px 18px var(--sombra))">${titulo}</div></div>`, `left:${x}px;top:${y}px`);
    let px = x, py = y + 160;
    const els = pills.map(([txt, ic, tp]) => {
      const w = 110 + txt.length * 19;
      if (px + w > 1010) { px = x; py += 96; }
      const e = mk(`<div class="chip">${ico(ic)}${txt}</div>`, `left:${px}px;top:${py}px`);
      px += w + 16;
      return { e, t: tp };
    });
    R.push(tt => {
      pon(tit, ap(tt, t, tout, { dx: -50, dy: 0, din: .62 }));
      for (const p of els) pon(p.e, ap(tt, p.t - .03, tout, { dy: 34, din: .55, rot: -4 }));
    });
  }
  function alerta({ tin, tout, linea, previo, chip, y = 1150 }) {
    const bang = mk(`<div class="badge blanco" style="font:900 52px Inter;color:var(--acento)">!</div>`, `left:70px;top:${y}px`);
    const l1 = mk(linea[0], `left:176px;top:${y + 8}px;font:800 66px Inter;color:#fff;letter-spacing:-1px;text-shadow:0 4px 20px var(--sombra);white-space:nowrap`);
    const l2 = mk(previo[0], `left:70px;top:${y + 142}px;font:600 56px Inter;color:#fff;text-shadow:0 4px 20px var(--sombra)`);
    const cx = 70 + previo[0].length * 30 + 20;
    const ch = mk(`<div class="chip hl" style="height:96px;font-size:50px;padding:0 38px">${ico(chip[1])}${chip[0]}</div>`, `left:${cx}px;top:${y + 122}px`);
    R.push(t => {
      pon(bang, ap(t, tin, tout, { dy: 0, dx: -40, rot: -120 }));
      pon(l1, ap(t, linea[1], tout, { dy: 34 }));
      pon(l2, ap(t, previo[1], tout, { dy: 34 }));
      pon(ch, ap(t, chip[2], tout, { dy: 0, dx: 60, din: .65, ry: -70 }));
    });
  }
  function interruptores({ tin, tout, filas, avatares = [], tDerecha, etiqueta = 'Conectados', y = 1066 }) {
    const tiles = filas.map(([, n], k) => ({ el: mk(`<div class="tile">${ico(n)}</div>`, `left:30px;top:${y + 26 + k * 136}px`), k }));
    const card = mk(`<div class="card" style="width:500px;height:${filas.length * 140}px;position:relative">${filas.map(([n, ic], k) =>
      `<div class="row" style="top:${k * 140}px">${ico(ic)}<span>${n}</span><div class="track"><div class="knob"></div></div></div>`).join('')}</div>`,
      `left:170px;top:${y}px`);
    const tracks = [...card.querySelectorAll('.track')], knobs = [...card.querySelectorAll('.knob')];
    const ym = y + filas.length * 70;
    const svg = mk(`<svg width="1080" height="1920" style="position:absolute;left:0;top:0" fill="none" stroke="${TM.lineas}" stroke-opacity=".75" stroke-width="3" stroke-linecap="round">
      <path class="cA" d="${filas.map((_, k) => `M138 ${y + 80 + k * 136} C156 ${y + 80 + k * 136} 152 ${ym} 170 ${ym}`).join(' ')}"/>
      <path class="cB" d="${avatares.length ? `M670 ${ym} C705 ${ym} 700 ${ym - 130} 774 ${ym - 130} M670 ${ym} L730 ${ym} M670 ${ym} C705 ${ym} 700 ${ym + 142} 774 ${ym + 142}` : `M670 ${ym} L730 ${ym}`}"/></svg>`);
    const pA = svg.querySelector('.cA'), pB = svg.querySelector('.cB');
    pA.style.strokeDasharray = 900; pB.style.strokeDasharray = 520;
    const avs = avatares.map((img, k) => mk(`<img class="av" src="${IMG(img)}">`, `left:776px;top:${ym - 186 + k * 272}px`));
    const pill = mk(`<div class="chip" style="height:70px;font-size:31px;padding:0 26px 0 20px">${etiqueta}
       <span class="badge" style="width:40px;height:40px;box-shadow:none"><svg class="i" viewBox="0 0 24 24" style="width:24px;height:24px;stroke-width:3.2">${IC.check}</svg></span></div>`,
      `left:730px;top:${ym - 35}px`);
    const OFF = [227, 218, 211], ON = TM.on;
    R.push(t => {
      pon(card, ap(t, tin, tout, { dy: 70, din: .65 }));
      for (const ti of tiles) pon(ti.el, ap(t, tin + .05 + .06 * ti.k, tout, { dx: -40, dy: 0 }));
      const vis = t >= tin && t < tout + .3;
      pon(svg, { o: vis ? (t >= tout ? 1 - sale((t - tout) / .3) : 1) : 0 });
      if (!vis) { avs.forEach(a => pon(a, { o: 0 })); pon(pill, { o: 0 }); return; }
      pA.style.strokeDashoffset = (900 * (1 - suave((t - tin - .12) / .45))).toFixed(1);
      pB.style.strokeDashoffset = (520 * (1 - suave((t - tDerecha + .14) / .4))).toFixed(1);
      SIG.push(pA.style.strokeDashoffset + pB.style.strokeDashoffset);
      filas.forEach(([, , ton], k) => {
        const p = spring((t - ton) / .45, .75, 7.6), c = suave((t - ton) / .22);
        knobs[k].style.transform = `translateX(${(48 * p).toFixed(2)}px)`;
        tracks[k].style.background = `rgb(${lerp(OFF[0], ON[0], c) | 0},${lerp(OFF[1], ON[1], c) | 0},${lerp(OFF[2], ON[2], c) | 0})`;
        SIG.push(knobs[k].style.transform + tracks[k].style.background);
      });
      avs.forEach((a, k) => pon(a, ap(t, tDerecha + .08 * k, tout, { dx: 40, dy: 0 })));
      pon(pill, ap(t, tDerecha + .04, tout, { dx: 40, dy: 0 }));
    });
  }
  function lineaIcono({ icono, texto, tin, tout, x = 60, y = 250 }) {
    const e = mk(`<div style="display:flex;align-items:center;gap:20px"><div class="badge" style="width:68px;height:68px">${ico(icono)}</div>
       <span style="font:700 44px Inter;color:#fff;letter-spacing:-.6px;text-shadow:0 3px 18px var(--sombra)">${texto}</span></div>`, `left:${x}px;top:${y}px`);
    R.push(t => pon(e, ap(t, tin, tout, { dx: -50, dy: 0 })));
  }
  function etiquetas({ items, tout, x = 60, y = 1150, paso = 112 }) {
    const els = items.map(([img, n, s, t], k) => ({ e: mk(`<div class="tag"><img src="${IMG(img)}"><div><b>${n}</b><i>${s}</i></div></div>`, `left:${x}px;top:${y + k * paso}px`), t }));
    R.push(t => { for (const g of els) pon(g.e, ap(t, g.t - .03, tout, { dx: -70, dy: 0, din: .62, odx: -30, ody: 0, rot: -4 })); });
  }
  function tarjetaRuta({ tin, tout, titulo, direccion, hitos, calles = [], apunte, y = 1000 }) {
    const n = ++SERIE;
    const ap0 = apunte ? mk(apunte[0], `left:96px;top:${y - 130}px;font:400 104px Script;filter:drop-shadow(0 4px 14px var(--sombra))`, 'a scr acento') : null;
    const tD = hitos[0][1], tM = hitos[1] ? hitos[1][1] : tD, tI = hitos[hitos.length - 1][1];
    const card = mk(`<div class="card nav" style="position:relative">
      <svg width="900" height="360" style="position:absolute;left:0;top:0">
        <defs><linearGradient id="fade${n}" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="1"/><stop offset=".42" stop-color="#fff" stop-opacity=".92"/><stop offset=".62" stop-color="#fff" stop-opacity="0"/></linearGradient>
        <filter id="glow${n}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9"/></filter></defs>
        <rect width="900" height="360" fill="#F6F1EC"/>
        <g stroke="#E4DCD4" stroke-width="16" stroke-linecap="square">
          <path d="M380 70 L900 -10"/><path d="M380 190 L900 110"/><path d="M380 310 L900 230"/><path d="M380 400 L900 350"/>
          <path d="M520 -20 L600 380"/><path d="M700 -20 L780 380"/><path d="M860 -20 L940 380"/></g>
        <g font-family="Inter" font-size="21" font-weight="500" fill="#B4A69B">${calles.map(([tx, cx, cy, g]) =>
          `<text x="${cx}" y="${cy}" transform="rotate(${g} ${cx} ${cy})">${tx}</text>`).join('')}</g>
        <path class="rutaG" d="M560 380 L612 250 L700 160 L738 56" stroke="${TM.ruta}" stroke-opacity=".55" stroke-width="30" fill="none" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow${n})"/>
        <path class="ruta" d="M560 380 L612 250 L700 160 L738 56" stroke="${TM.ruta}" stroke-width="22" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
        <rect width="900" height="360" fill="url(#fade${n})"/>
        <g stroke="${TM.ruta}" stroke-width="3" stroke-dasharray="9 9"><path d="M65 62 V318"/></g>
        <g class="pinS" transform="translate(738 56)"><ellipse rx="22" ry="7" fill="#000" fill-opacity=".18"/></g>
        <g class="pin" transform="translate(738 56)"><path d="M0 0 C-18 -26 -30 -40 -30 -58 A30 30 0 1 1 30 -58 C30 -40 18 -26 0 0 Z" fill="${TM.ruta}" stroke="#fff" stroke-width="4"/><circle cy="-58" r="11" fill="#fff"/></g>
        <g class="flecha"><path d="M0 -30 L22 22 L0 10 L-22 22 Z" fill="${TM.ruta}" stroke="#fff" stroke-width="5" stroke-linejoin="round"/></g>
      </svg>
      ${hitos.map(([tx], k) => `<div class="hito" style="top:${44 + k * (240 / Math.max(1, hitos.length - 1))}px"><div class="dot${k > 0 && k < hitos.length - 1 ? ' ring2' : ''}"></div>${tx}</div>`).join('')}
      <h3>${titulo}</h3><p>${direccion}</p></div>`, `left:90px;top:${y}px`);
    const ruta = card.querySelector('.ruta'), rutaG = card.querySelector('.rutaG'), flecha = card.querySelector('.flecha');
    const pin = card.querySelector('.pin'), pinS = card.querySelector('.pinS');
    const LEN = ruta.getTotalLength();
    ruta.style.strokeDasharray = rutaG.style.strokeDasharray = LEN;
    const hs = [...card.querySelectorAll('.hito')];
    const keys = [[tin, 0], [tin + .3, .12], [tI, .40], [tM, .70], [tD, 1]];
    const progreso = t => {
      let v = 0;
      for (let k = 1; k < keys.length; k++) if (t >= keys[k - 1][0]) v = keys[k - 1][1] + (keys[k][1] - keys[k - 1][1]) * spring((t - keys[k - 1][0]) / .7, .78, 7.6);
      return clamp(v, 0, 1.02);
    };
    R.push(t => {
      if (ap0) pon(ap0, { ...ap(t, apunte[1], tout, { dy: 26 }), r: -6 - 6 * (1 - spring((t - apunte[1]) / .6)) });
      pon(card, ap(t, tin, tout, { dy: 90, din: .7 }));
      if (t < tin || t > tout + .35) return;
      const P = progreso(t), off = (LEN * (1 - clamp(P))).toFixed(1);
      ruta.style.strokeDashoffset = rutaG.style.strokeDashoffset = off;
      const L1 = clamp(P) * LEN, pt = ruta.getPointAtLength(L1), pt2 = ruta.getPointAtLength(Math.min(LEN, L1 + 2));
      flecha.setAttribute('transform', `translate(${pt.x.toFixed(1)} ${pt.y.toFixed(1)}) rotate(${(Math.atan2(pt2.y - pt.y, pt2.x - pt.x) * 180 / Math.PI + 90).toFixed(1)})`);
      flecha.setAttribute('opacity', (1 - suave((t - tD) / .25)).toFixed(3));
      const pp = spring((t - tD) / .6, .62, 7.6), po = clamp((t - tD) / .1);
      pin.setAttribute('transform', `translate(738 ${(56 - 150 * (1 - pp)).toFixed(1)})`);
      pin.setAttribute('opacity', po.toFixed(3)); pinS.setAttribute('opacity', (po * clamp(pp)).toFixed(3));
      SIG.push(off + flecha.getAttribute('transform') + pin.getAttribute('transform') + po);
      hs.forEach((h, k) => { const o = (.32 + .68 * suave((t - hitos[k][1] + .03) / .25)).toFixed(3); h.style.opacity = o; SIG.push(o); });
    });
  }
  function tarjetasProducto({ rects, contenidos, tin, tout }) {
    const cs = rects.map(([x, y, w, h, r], k) => mk(contenidos[k],
      `left:${x}px;top:${y}px;width:${w}px;height:${h}px;border-radius:${r}px;overflow:hidden;background:#fff;box-shadow:0 22px 60px var(--sombra)`));
    R.push(t => cs.forEach((c, k) => pon(c, ap(t, tin + .1 + .08 * k, tout, { dy: 160, din: .72, fin: .1, dout: .42, ody: 700, ry: -75 }))));
  }
  const prodImg = src => `<img src="${IMG(src)}" style="width:100%;height:100%;object-fit:cover;display:block">`;
  const prodGrande = (grande, kick, sub, icono = 'cal') => `<div class="prod"><div class="badge">${ico(icono)}</div><div class="big">${grande}</div><div class="kick">${kick}</div><div class="sub">${sub}</div></div>`;
  const prodTexto = (texto, sub, icono = 'pin') => `<div class="prod"><div class="badge">${ico(icono)}</div><div style="font:800 38px/1.1 Inter;letter-spacing:-.8px">${texto}</div><div class="sub">${sub}</div></div>`;
  function checks({ items, tout, x = 80, y = 1170, paso = 122 }) {
    const els = items.map(([txt, t], k) => {
      const e = mk(`<div class="check"><div class="badge"><svg class="i" viewBox="0 0 24 24">${IC.check}</svg></div>${txt}</div>`, `left:${x}px;top:${y + k * paso}px`);
      return { e, p: e.querySelector('path'), t };
    });
    R.push(t => {
      for (const c of els) {
        pon(c.e, ap(t, c.t, tout, { dx: -50, dy: 0 }));
        if (t >= c.t - .1 && t <= tout + .4) { const o = (30 * (1 - suave((t - c.t - .12) / .3))).toFixed(1); c.p.style.strokeDashoffset = o; SIG.push(o); }
      }
    });
  }
  function chipSuelto({ texto, icono, t, tout, y, x = null, grande = false }) {
    const st = grande ? 'height:88px;font-size:40px;padding:0 38px 0 28px' : '';
    const e = mk(`<div class="chip" style="${st}">${icono ? ico(icono) : ''}${texto}</div>`,
      x === null ? `top:${y}px;width:1080px;display:flex;justify-content:center` : `left:${x}px;top:${y}px`);
    R.push(tt => pon(e, ap(tt, t, tout, { dy: 30, din: .55, rot: -4 })));
  }
  function avion({ t0, dur = .95, d = 'M150 1392 C 400 1520, 700 1480, 880 1360 S 1080 1150, 1180 1080' }) {
    const id = `mv${t0 | 0}_${++SERIE}`;
    const svg = mk(`<svg width="1080" height="1920" style="position:absolute;left:0;top:0">
       <defs><mask id="${id}" maskUnits="userSpaceOnUse"><path class="vm" d="${d}" fill="none" stroke="#fff" stroke-width="18"/></mask></defs>
       <path d="${d}" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round" stroke-dasharray="1 18" stroke-opacity=".95" mask="url(#${id})"/>
       <g class="avion"><g transform="scale(3.4) translate(-12 -12)">
         <path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z" fill="#fff" stroke="${TM.ruta}" stroke-width="1.4" stroke-linejoin="round"/>
         <path d="m21.854 2.147-10.94 10.939" fill="none" stroke="${TM.ruta}" stroke-width="1.4" stroke-linecap="round"/></g></g></svg>`);
    const vm = svg.querySelector('.vm'), av = svg.querySelector('.avion'), LV = vm.getTotalLength();
    vm.style.strokeDasharray = LV;
    R.push(t => {
      const vis = t >= t0 && t < t0 + dur + .3;
      pon(svg, { o: vis ? (t > t0 + dur - .1 ? 1 - sale((t - t0 - dur + .1) / .35) : 1) : 0 });
      if (!vis) return;
      const L1 = sale((t - t0) / dur) * LV, a = vm.getPointAtLength(L1), b = vm.getPointAtLength(Math.min(LV, L1 + 2));
      av.setAttribute('transform', `translate(${a.x.toFixed(1)} ${a.y.toFixed(1)}) rotate(${(Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI + 45).toFixed(1)})`);
      vm.style.strokeDashoffset = (LV - L1).toFixed(1);
      SIG.push(av.getAttribute('transform') + L1.toFixed(1));
    });
  }
  function logoCierre({ img, t, rect = [350, 330, 380, 480] }) {
    const [x, y, w, h] = rect;
    const e = mk(prodImg(img), `left:${x}px;top:${y}px;width:${w}px;height:${h}px;border-radius:40px;overflow:hidden;box-shadow:0 26px 70px var(--sombra)`);
    R.push(tt => pon(e, ap(tt, t, 99, { dy: -90, din: .7, fin: .2 })));
  }

  return {
    api: { rotulo, hook, barrido, etiqueta, notificacion, degradado, tarjetaInferior, orbita, avataresArco, filaEtiqueta, alerta, interruptores,
           lineaIcono, etiquetas, tarjetaRuta, tarjetasProducto, prodImg, prodGrande, prodTexto, checks, chipSuelto, avion, logoCierre, spring },
    render: (t: number) => { SIG = []; for (const f of R) f(t); return SIG.join('|'); },
    subs: (t: number) => BARRIDOS.some(tc => t > tc - .5 && t < tc + .8) ? 12 : 5,
  };
}
