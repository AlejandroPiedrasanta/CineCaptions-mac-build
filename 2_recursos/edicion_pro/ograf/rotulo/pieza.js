// CineCaptions · Edición PRO — «Rótulo»: una frase que tiene que quedarse, en bloques que se levantan (la segunda línea, en el acento).
import { PiezaPro, el, esc, tiempos, clamp, P, E, FAMILIA, PESO, sobre } from './lib/motor.js';

export default class Rotulo extends PiezaPro {
  static DEFAULTS = {
    linea1: 'Una frase', linea2: 'QUE SE QUEDA', acentoLinea: 2, tiempos: '0,0.6', fuente: 'serif',
    acento: '#c9a46a', colorTexto: '#ffffff', colorBloque: '#141210', escala: 1, x: 50, y: 22, inclinacion: 0,
  };
  static SALIDA = 0.35;
  static CSS = `
  .rot{display:flex;flex-direction:column;align-items:center;gap:calc(var(--u)*14);perspective:calc(var(--u)*1400)}
  .bl{white-space:nowrap;line-height:1;padding:calc(var(--u)*16) calc(var(--u)*32) calc(var(--u)*20);border-radius:calc(var(--u)*14);
      box-shadow:0 calc(var(--u)*30) calc(var(--u)*70) calc(var(--u)*-24) rgba(0,0,0,.85);transform-origin:50% 100%}`;

  construir(s) {
    const fam = s.fuente in FAMILIA ? s.fuente : 'serif', peso = PESO[fam];
    this.caja = el('div', 'L rot', this._escena);
    const max = 86 * this.U * (+s.escala || 1) * (this.vertical ? 1 : 1.1), ancho = this.W * 0.82;
    this.bl = [];
    [s.linea1, s.linea2].forEach((txt, i) => {
      txt = String(txt || '').trim();
      if (!txt) return;
      const ac = +s.acentoLinea === i + 1;
      const b = el('div', 'bl', this.caja, esc(txt));
      Object.assign(b.style, { fontFamily: FAMILIA[fam], fontWeight: peso, fontSize: this.encajar(txt, max, ancho, fam, peso) + 'px',
        background: ac ? s.acento : s.colorBloque, color: ac ? sobre(s.acento) : s.colorTexto });
      this.bl.push(b);
    });
    this.ts = tiempos(s.tiempos, this.bl.length, 0.5);
  }

  pintar(t, q, s) {
    if (!this.caja) return;
    this.bl.forEach((b, i) => {
      const p = P(t, this.ts[i] - 0.04, 0.45, E.out4);
      b.style.transform = `rotateX(${((1 - p) * 85).toFixed(2)}deg) translateY(${((1 - p) * 30 * this.U).toFixed(1)}px)`;
      b.style.opacity = clamp(p * 2.5).toFixed(3);
    });
    this.put(this.caja, { x: this.W * (+s.x / 100), y: this.H * (+s.y / 100) - q * 20 * this.U, o: 1 - q, b: q * 8 * this.U, r: +s.inclinacion || 0 });
  }
}
