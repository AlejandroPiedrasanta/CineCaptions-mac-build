// CineCaptions · Edición PRO — «Órbita»: los iconos del tema giran alrededor de la cabeza (el gancho de la skill con Magic Mask). Se ponen DOS:
// la mitad de atrás (mitad=atras) DEBAJO de la persona recortada y la de delante (mitad=delante) encima; las dos hacen la MISMA cuenta, así que
// un icono pasa de una a otra justo en los lados de la elipse (fuera de la silueta) y no se nota el cambio. Lo de delante pasa un poco más
// grande y más brillante (profundidad); lo de atrás, más pequeño y apagado. Entra con un resorte de Motion (el radio crece desde la cabeza).
// v5.20 (página Efectos › Gancho del inicio): `estilo` dibuja el trazo de la órbita (la mitad de su lado): limpio (sin trazo, el de siempre) ·
// rastro · anillo · neon · chips · cometa · doble · puntos · halo · cinta; `colorAnillo` y `acento2` los puede elegir el usuario.
import { PiezaPro, el, S, P, E, clamp, icono, IMG3D } from './lib/motor.js';

const NS = 'http://www.w3.org/2000/svg';

export default class Orbita extends PiezaPro {
  static DEFAULTS = { iconos: 'casa,key,bed,waves', imagenes: '', mitad: 'todo', acento: '#c9a46a', colorTexto: '#ffffff', estilo: 'limpio',
                      acento2: '#ff7a1a', colorAnillo: '#ffffff', x: 50, y: 30, rx: 22, ry: 4.5, inclinacion: -8, vueltas: 0.32, escala: 1, tiempos: '0' };
  static SALIDA = 0.35;
  static FUENTES = [];
  static CSS = `
  .ic{display:flex;align-items:center;justify-content:center;border-radius:50%;border-style:solid}
  .ic svg{display:block}
  .anillo{position:absolute;left:0;top:0;overflow:visible}
  .chip{position:absolute;left:0;top:0;border-radius:50%;box-sizing:border-box}`;

  construir(s) {
    const k = +s.escala || 1, d = 104 * this.U * k;
    this._trazo(s);
    const imgs = String(s.imagenes || '').split(',').map(x => x.trim()).filter(Boolean).slice(0, 6);
    if (imgs.length >= 3) {                                          // iconos 3D: más grandes, flotando, con su sombra
      const d3 = d * 1.7;
      this.ics = imgs.map(n => {
        if (s.estilo === 'chips') this._chip(d3 * 1.2, s);
        const e = el('div', 'L', this._escena);
        const im = el('img', '', e);
        im.src = IMG3D(n);
        Object.assign(e.style, { width: d3 + 'px', height: d3 + 'px' });
        Object.assign(im.style, { width: '100%', height: '100%', objectFit: 'contain', filter: `drop-shadow(0 ${8 * this.U}px ${14 * this.U}px rgba(0,0,0,.5))` });
        return e;
      });
      this.t0 = parseFloat(String(s.tiempos || '0').split(',')[0]) || 0;
      return;
    }
    this.lista = String(s.iconos || '').split(',').map(x => x.trim()).filter(Boolean).slice(0, 6);
    if (!this.lista.length) this.lista = ['estrella'];
    this.ics = this.lista.map(n => {
      if (s.estilo === 'chips') this._chip(d * 1.25, s);
      const e = el('div', 'L ic', this._escena, icono(n, d * 0.5, 1.8));
      Object.assign(e.style, { width: d + 'px', height: d + 'px', borderWidth: Math.max(1.5, 3 * this.U * k) + 'px', borderColor: s.acento,
                               color: s.colorTexto, background: 'rgba(10,10,12,0.55)', boxShadow: `0 ${8 * this.U}px ${28 * this.U}px rgba(0,0,0,.45)` });
      return e;
    });
    this.t0 = parseFloat(String(s.tiempos || '0').split(',')[0]) || 0;
  }

  _chip(lado, s) {                                                    // la burbuja de cristal de cada icono (estilo chips), detrás de él
    const c = el('div', 'chip', this._escena);
    Object.assign(c.style, { width: lado + 'px', height: lado + 'px', background: 'linear-gradient(160deg, rgba(255,255,255,.3), rgba(255,255,255,.08))',
                             border: `${2 * this.U}px solid rgba(255,255,255,.5)`, boxShadow: `0 ${14 * this.U}px ${30 * this.U}px rgba(0,0,0,.35), 0 0 ${24 * this.U}px ${s.acento}` });
    (this.chips = this.chips || []).push(c);
  }

  _trazo(s) {
    const st = String(s.estilo || 'limpio');
    this.trazos = [];
    if (st === 'limpio' || st === 'chips') return;
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'anillo');
    svg.setAttribute('width', this.W);
    svg.setAttribute('height', this.H);
    this._escena.appendChild(svg);
    const U = this.U, col = s.colorAnillo || '#ffffff', ac = s.acento || '#ffffff';
    if (st === 'halo') {
      const defs = document.createElementNS(NS, 'defs');
      defs.innerHTML = `<linearGradient id="ccHalo" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="${s.acento2 || '#ff7a1a'}"/><stop offset="1" stop-color="${ac}"/></linearGradient>`;
      svg.appendChild(defs);
    }
    const capa = (color, ancho, op, blur, extra) => {
      const p = document.createElementNS(NS, 'path');
      Object.entries(Object.assign({ fill: 'none', stroke: color, 'stroke-width': ancho, 'stroke-linecap': 'round' }, extra || {}))
        .forEach(([a, v]) => p.setAttribute(a, v));
      if (blur) p.style.filter = `blur(${blur}px)`;
      svg.appendChild(p);
      return p;
    };
    const L = (color, ancho, op, blur, extra, f = 1) => this.trazos.push({ p: capa(color, ancho, op, blur, extra), f, op });
    if (st === 'rastro') { L(ac, 12 * U, 0.35, 6 * U); L(col, 3.5 * U, 0.85, 0, { 'stroke-dasharray': `${14 * U} ${12 * U}` }); }
    else if (st === 'anillo') L(col, 3 * U, 0.9, 0);
    else if (st === 'neon') { L(ac, 14 * U, 0.55, 10 * U); L(ac, 4.5 * U, 1, 0); L('#ffffff', 1.6 * U, 0.85, 0); }
    else if (st === 'cometa') { L(ac, 22 * U, 0.25, 14 * U); }
    else if (st === 'doble') { L(col, 2.5 * U, 0.85, 0); L(col, 2 * U, 0.5, 0, null, 1.25); }
    else if (st === 'puntos') L(col, 8 * U, 0.95, 0, { 'stroke-dasharray': `0 ${20 * U}` });
    else if (st === 'halo') { L('url(#ccHalo)', 16 * U, 0.5, 12 * U); L('url(#ccHalo)', 5 * U, 1, 0); }
    else if (st === 'cinta') { L(col, 42 * U, 0.16, 0); L(col, 2 * U, 0.7, 0); }
  }

  _ruta(cx, cy, rx, ry, ci, si, delante, mitad) {                     // la mitad de la elipse que toca (o entera), girada
    const pasos = 64, out = [];
    const desde = mitad === 'todo' ? 0 : (delante ? 0 : Math.PI), largo = mitad === 'todo' ? 2 * Math.PI : Math.PI;
    for (let i = 0; i <= pasos; i++) {
      const th = desde + (largo * i) / pasos, ex = rx * Math.cos(th), ey = ry * Math.sin(th);
      out.push(`${i ? 'L' : 'M'}${(cx + ex * ci - ey * si).toFixed(1)} ${(cy + ex * si + ey * ci).toFixed(1)}`);
    }
    return out.join(' ');
  }

  pintar(t, q, s) {
    if (!this.ics) return;
    const n = this.ics.length, cx = this.W * (+s.x / 100), cy = this.H * (+s.y / 100);
    const crece = S(t, this.t0, 'rebote', 0.9);                       // el radio se abre con resorte (se pasa un poco y vuelve)
    const rx = this.W * (+s.rx / 100) * crece, ry = this.H * (+s.ry / 100) * crece;
    const inc = (+s.inclinacion || 0) * Math.PI / 180, ci = Math.cos(inc), si = Math.sin(inc);
    const w = 2 * Math.PI * (+s.vueltas || 0.3);
    const entra = P(t, this.t0, 0.35, E.out3);
    (this.trazos || []).forEach(({ p, f, op }) => {
      const inc2 = inc + (f !== 1 ? 0.2 : 0);
      p.setAttribute('d', this._ruta(cx, cy, rx * f, ry * (f !== 1 ? 1.5 : 1), Math.cos(inc2), Math.sin(inc2), s.mitad !== 'atras', s.mitad));
      p.style.opacity = String(op * clamp(entra) * (1 - q));      // (la opacidad de cada capa del trazo × la entrada y la salida)
      if (p.getAttribute('stroke-dasharray')) p.setAttribute('stroke-dashoffset', String(-(t - this.t0) * 60 * this.U));
    });
    this.ics.forEach((e, i) => {
      const th = (2 * Math.PI * i) / n + w * (t - this.t0) - Math.PI / 2;
      const ex = rx * Math.cos(th), ey = ry * Math.sin(th);
      const delante = Math.sin(th) >= 0;                              // la parte baja de la elipse es la que viene hacia la cámara
      const visible = s.mitad === 'todo' || (s.mitad === 'delante') === delante;
      const prof = (Math.sin(th) + 1) / 2;                            // 0 atrás … 1 delante
      const o = { x: cx + ex * ci - ey * si, y: cy + ex * si + ey * ci, s: (0.72 + 0.4 * prof) * (0.6 + 0.4 * entra),
                  o: visible ? clamp(entra * (0.55 + 0.45 * prof)) * (1 - q) : 0 };
      if (this.chips && this.chips[i]) this.put(this.chips[i], o);
      this.put(e, o);
    });
  }
}
