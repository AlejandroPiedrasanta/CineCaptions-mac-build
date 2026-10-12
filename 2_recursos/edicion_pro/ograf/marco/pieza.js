// CineCaptions · Edición PRO — «Marco»: el cuadro se convierte en otra cosa (visor de cámara, marco elegante, ventana, película, brillo).
// Va delante de todo y no tapa nada importante: solo líneas finas en los bordes.
import { PiezaPro, el, esc, tiempos, P, E, clamp } from './lib/motor.js';

const SVG = 'http://www.w3.org/2000/svg';

export default class Marco extends PiezaPro {
  static DEFAULTS = { estilo: 'elegante', texto: '', acento: '#c9a46a', colorTexto: '#ffffff', margen: 5, grosor: 1, tiempos: '0', tcInicio: 0, fps: 30 };
  static SALIDA = 0.35;
  static CSS = `
  svg.m{position:absolute;left:0;top:0;overflow:visible}
  svg.m path,svg.m line,svg.m rect,svg.m circle{fill:none;stroke-linecap:square}
  .lb{font-family:'CCMono',monospace;font-weight:500;letter-spacing:.18em;white-space:nowrap;text-shadow:0 2px 10px rgba(0,0,0,.7)}
  .tx{font-family:'CCSerif',serif;font-style:italic;white-space:nowrap;text-shadow:0 3px 18px rgba(0,0,0,.7)}
  .dot{display:inline-block;border-radius:50%;background:#ff3b30;margin-right:.5em;vertical-align:middle}`;

  construir(s) {
    const W = this.W, H = this.H, U = this.U, m = Math.min(W, H) * clamp(+s.margen || 5, 1, 20) / 100;
    const g = Math.max(1.5, 3 * U * (+s.grosor || 1));
    const svg = document.createElementNS(SVG, 'svg');
    svg.setAttribute('class', 'm'); svg.setAttribute('width', W); svg.setAttribute('height', H);
    this._escena.appendChild(svg);
    this.trazos = [];
    const traza = (d, w = g, color = s.acento) => {
      const p = document.createElementNS(SVG, 'path');
      p.setAttribute('d', d); p.setAttribute('pathLength', '1'); p.setAttribute('stroke', color); p.setAttribute('stroke-width', w);
      svg.appendChild(p); this.trazos.push(p); return p;
    };
    const x0 = m, y0 = m + (this.vertical ? H * 0.06 : 0), x1 = W - m, y1 = H - m - (this.vertical ? H * 0.08 : 0), cx = W / 2;
    const rect = (a, b, c, d) => { traza(`M${cx} ${b} H${a} V${d} H${cx}`); traza(`M${cx} ${b} H${c} V${d} H${cx}`); };
    this.labels = [];
    const label = (html, x, y, ax, cls, px) => { const e = el('div', 'L ' + cls, this._escena, html); e._p = { x, y, ax, ay: 50 }; e.style.fontSize = px + 'px'; this.labels.push(e); return e; };
    const estilo = s.estilo;
    if (estilo === 'visor') {
      const L = Math.min(W, H) * 0.09;
      for (const [x, y, dx, dy] of [[x0, y0, 1, 1], [x1, y0, -1, 1], [x0, y1, 1, -1], [x1, y1, -1, -1]]) traza(`M${x} ${y + dy * L} V${y} H${x + dx * L}`, g * 1.4, s.colorTexto);
      label(`<span class="dot" style="width:${16 * U}px;height:${16 * U}px"></span>REC`, x0 + 10 * U, y0 + 34 * U, 0, 'lb', 26 * U).style.color = s.colorTexto;
      this.tc = label('00:00:00:00', x1 - 10 * U, y0 + 34 * U, 100, 'lb', 26 * U); this.tc.style.color = s.colorTexto;
      if (s.texto) label(esc(s.texto), x0 + 10 * U, y1 - 30 * U, 0, 'lb', 22 * U).style.color = s.acento;
    } else if (estilo === 'cinta') {
      const hueco = 22 * U, paso = 44 * U, lado = this.vertical ? 'v' : 'h';
      const n = Math.floor((lado === 'v' ? H : W) / paso);
      for (let i = 0; i < n; i++) {
        const a = i * paso + paso / 2;
        if (lado === 'v') { traza(`M${m * 0.4} ${a - hueco / 3} h${hueco * 0.7} v${hueco * 0.6} h${-hueco * 0.7} z`, g * 0.8, s.colorTexto); traza(`M${W - m * 0.4} ${a - hueco / 3} h${-hueco * 0.7} v${hueco * 0.6} h${hueco * 0.7} z`, g * 0.8, s.colorTexto); }
        else { traza(`M${a - hueco / 3} ${m * 0.4} v${hueco * 0.7} h${hueco * 0.6} v${-hueco * 0.7} z`, g * 0.8, s.colorTexto); traza(`M${a - hueco / 3} ${H - m * 0.4} v${-hueco * 0.7} h${hueco * 0.6} v${hueco * 0.7} z`, g * 0.8, s.colorTexto); }
      }
      if (s.texto) label(esc(s.texto), W / 2, y1 - 20 * U, 50, 'lb', 24 * U).style.color = s.acento;
    } else {
      rect(x0, y0, x1, y1);
      if (estilo !== 'simple') rect(x0 + 16 * U, y0 + 16 * U, x1 - 16 * U, y1 - 16 * U);
      if (estilo === 'elegante' || estilo === 'brillo') {
        const r = 12 * U;
        for (const [x, y] of [[cx, y0], [cx, y1]]) traza(`M${x} ${y - r} L${x + r} ${y} L${x} ${y + r} L${x - r} ${y} Z`, g);
      }
      if (estilo === 'brillo') {
        this.estrellas = [[x0 + 50 * U, y0 + 60 * U, 1], [x1 - 60 * U, y0 + 90 * U, 0.7], [x1 - 50 * U, y1 - 70 * U, 1], [x0 + 70 * U, y1 - 110 * U, 0.6]].map(([x, y, k]) => {
          const e = el('div', 'L', this._escena, `<svg width="${60 * U * k}" height="${60 * U * k}" viewBox="-10 -10 20 20"><path d="M0 -10 C1 -2 2 -1 10 0 C2 1 1 2 0 10 C-1 2 -2 1 -10 0 C-2 -1 -1 -2 0 -10Z" fill="${s.acento}"/></svg>`);
          e._p = { x, y, k }; return e;
        });
      }
      if (s.texto) label(esc(s.texto), cx, y1 - 56 * U, 50, 'tx', 54 * U).style.color = s.colorTexto;
    }
    this.ts = tiempos(s.tiempos, 1);
  }

  pintar(t, q, s) {
    const t0 = this.ts[0];
    this.trazos.forEach((p, i) => { const d = P(t, t0 + (i % 6) * 0.04, 0.8, E.io3); p.style.strokeDasharray = `${d.toFixed(4)} 1`; p.style.opacity = (1 - q).toFixed(3); });
    this.labels.forEach((e, i) => { const p = P(t, t0 + 0.3 + i * 0.1, 0.45, E.out3); this.put(e, { ...e._p, o: p * (1 - q) }); });
    if (this.tc) {
      const fps = Math.max(1, Math.round(+s.fps || 30)), f = Math.floor((t + (+s.tcInicio || 0)) * fps + 1e-6);
      const ss = Math.floor(f / fps), dd = n => String(n).padStart(2, '0');
      this.tc.textContent = `${dd(Math.floor(ss / 3600))}:${dd(Math.floor(ss / 60) % 60)}:${dd(ss % 60)}:${dd(f % fps)}`;
    }
    (this.estrellas || []).forEach((e, i) => {
      const p = P(t, t0 + 0.5 + i * 0.18, 0.6, E.back), resp = 0.85 + 0.15 * Math.sin((t + i) * 1.6);
      this.put(e, { x: e._p.x, y: e._p.y, s: Math.max(0.001, p * resp), r: 25 * Math.sin(t * 0.7 + i), o: clamp(p) * (1 - q) });
    });
  }
}
