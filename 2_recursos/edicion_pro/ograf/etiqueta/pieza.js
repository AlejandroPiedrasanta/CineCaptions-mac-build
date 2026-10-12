// CineCaptions · Edición PRO — «Etiqueta»: pie de foto numerado, ubicación con pin o rótulo de nombre (una línea grande + antetítulo).
import { PiezaPro, el, esc, tiempos, P, E, FAMILIA, PESO, clamp, icono } from './lib/motor.js';

export default class Etiqueta extends PiezaPro {
  static DEFAULTS = {
    kicker: '', texto: 'Etiqueta', indice: '', icono: 'ninguno', alinear: 'izq', fuente: 'serif',
    acento: '#c9a46a', colorTexto: '#ffffff', escala: 1, x: 7, y: 74, tiempos: '0',
  };
  static SALIDA = 0.3;
  static CSS = `
  .et{display:flex;flex-direction:column;gap:calc(var(--u)*10)}
  .k{font-family:'CCMono',monospace;font-weight:500;letter-spacing:.26em;text-transform:uppercase;white-space:nowrap;text-shadow:0 2px 12px rgba(0,0,0,.75)}
  .f{display:flex;align-items:center;gap:calc(var(--u)*20);white-space:nowrap}
  .n{font-family:'CCMono',monospace;font-weight:500;letter-spacing:.12em;text-shadow:0 2px 10px rgba(0,0,0,.8)}
  .r{height:2px;transform-origin:0 50%}
  .t{line-height:1;text-shadow:0 calc(var(--u)*3) calc(var(--u)*20) rgba(0,0,0,.8)}
  .p{display:flex;filter:drop-shadow(0 calc(var(--u)*6) calc(var(--u)*10) rgba(0,0,0,.6))}`;

  construir(s) {
    const fam = s.fuente in FAMILIA ? s.fuente : 'serif', peso = PESO[fam], k = +s.escala || 1;
    const italica = fam === 'serif';
    this.caja = el('div', 'L et', this._escena);
    this.caja.style.alignItems = s.alinear === 'der' ? 'flex-end' : s.alinear === 'centro' ? 'center' : 'flex-start';
    this.k = el('div', 'k', this.caja, esc(s.kicker || ''));
    Object.assign(this.k.style, { fontSize: Math.max(13, 28 * this.U * k) + 'px', color: s.acento, display: s.kicker ? 'block' : 'none' });
    const f = el('div', 'f', this.caja);
    if (s.alinear === 'der') f.style.flexDirection = 'row-reverse';
    this.n = null; this.r = null; this.p = null;
    if (s.icono === 'pin') { this.p = el('div', 'p', f, icono('pin', 58 * this.U * k, 2)); this.p.style.color = s.acento; }
    if (String(s.indice || '').trim()) {
      this.n = el('span', 'n', f, esc(s.indice));
      Object.assign(this.n.style, { fontSize: 32 * this.U * k + 'px', color: s.acento });
      this.r = el('span', 'r', f);
      Object.assign(this.r.style, { width: 80 * this.U * k + 'px', background: s.acento });
    }
    this.t = el('span', 't', f, esc(s.texto || ''));
    const px = this.encajar(s.texto || '', 80 * this.U * k, this.W * 0.8, fam, peso, italica ? 'italic' : 'normal');
    Object.assign(this.t.style, { fontFamily: FAMILIA[fam], fontWeight: peso, fontStyle: italica ? 'italic' : 'normal', fontSize: px + 'px', color: s.colorTexto });
    this.ts = tiempos(s.tiempos, 1);
  }

  pintar(t, q, s) {
    if (!this.caja) return;
    const t0 = this.ts[0], p = P(t, t0, 0.5, E.out4);
    this.k.style.opacity = P(t, t0, 0.4).toFixed(3);
    if (this.r) this.r.style.transform = `scaleX(${Math.max(0.001, P(t, t0, 0.45, E.io3)).toFixed(3)})`;
    if (this.n) this.n.style.opacity = P(t, t0, 0.35).toFixed(3);
    if (this.p) { const pp = clamp((t - t0) / 0.5); this.p.style.transform = `translateY(${((1 - E.out4(pp)) * -60 * this.U).toFixed(1)}px)`; this.p.style.opacity = clamp(pp * 3).toFixed(3); }
    const pt = P(t, t0 + 0.12, 0.5, E.out4);
    this.t.style.opacity = clamp(pt * 1.6).toFixed(3);
    this.t.style.transform = `translateY(${((1 - pt) * 22 * this.U).toFixed(1)}px)`;
    const ax = s.alinear === 'der' ? 100 : s.alinear === 'centro' ? 50 : 0;
    this.put(this.caja, { x: this.W * (+s.x / 100), y: this.H * (+s.y / 100), ax, ay: 50, o: (p > 0 ? 1 : 0) * (1 - q), b: q * 4 * this.U });
  }
}
