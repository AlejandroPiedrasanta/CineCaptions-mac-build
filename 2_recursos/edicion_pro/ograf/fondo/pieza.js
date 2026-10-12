// CineCaptions · Edición PRO — «Fondo»: B-roll de motion graphics. Tapa el video entero con un fondo animado (la paleta del video) para que encima
// se explique algo a pantalla completa (una cifra, una lista, un concepto con su icono). Entra y sale con un iris, una cortina o un fundido.
// Ligero a propósito (Resolve dibuja los OGraf en la CPU en Windows): unos degradados que se mueven, sin filtros caros.
import { PiezaPro, el, clamp, P, E, rgb } from './lib/motor.js';

export default class Fondo extends PiezaPro {
  static DEFAULTS = { estilo: 'aurora', entrada: 'iris', color1: '#c9a46a', color2: '#121110', color3: '#3a2f22', intensidad: 0.75 };
  static SALIDA = 0.35;
  static FUENTES = [];
  static CSS = `
  .f{position:absolute;inset:0}
  .rej{position:absolute;inset:0;opacity:.18}
  .vin{position:absolute;inset:0;background:radial-gradient(130% 95% at 50% 45%,rgba(0,0,0,0) 45%,rgba(0,0,0,.55) 100%)}`;

  construir(s) {
    this.f = el('div', 'f', this._escena);
    this.capa = el('div', 'f', this.f);
    if (s.estilo === 'rejilla' || s.estilo === 'puntos') {
      const r = el('div', 'rej', this.f), [a, b, c] = rgb(s.color1), paso = Math.round(54 * this.U);
      r.style.backgroundImage = s.estilo === 'puntos'
        ? `radial-gradient(circle, rgba(${a},${b},${c},.9) ${Math.max(1, 1.6 * this.U)}px, transparent ${Math.max(1.5, 2.2 * this.U)}px)`
        : `linear-gradient(rgba(${a},${b},${c},.55) 1px, transparent 1px), linear-gradient(90deg, rgba(${a},${b},${c},.55) 1px, transparent 1px)`;
      r.style.backgroundSize = `${paso}px ${paso}px`;
      this.rej = r;
    }
    el('div', 'vin', this.f);
  }

  pintar(t, q, s) {
    if (!this.f) return;
    const [a1, b1, c1] = rgb(s.color1), [a3, b3, c3] = rgb(s.color3), k = clamp(+s.intensidad || 0.75, 0, 1);
    const ox = 50 + 18 * Math.sin(t * 0.35), oy = 38 + 12 * Math.cos(t * 0.28), px = 30 + 20 * Math.cos(t * 0.22), py = 72 + 10 * Math.sin(t * 0.31);
    this.capa.style.background = s.estilo === 'liso'
      ? `linear-gradient(180deg, ${s.color3}, ${s.color2})`
      : `radial-gradient(60% 45% at ${ox.toFixed(1)}% ${oy.toFixed(1)}%, rgba(${a1},${b1},${c1},${(0.55 * k).toFixed(3)}), transparent 70%),` +
        `radial-gradient(55% 40% at ${px.toFixed(1)}% ${py.toFixed(1)}%, rgba(${a3},${b3},${c3},${(0.9 * k).toFixed(3)}), transparent 72%),` +
        `linear-gradient(160deg, ${s.color3}, ${s.color2} 60%)`;
    if (this.rej) this.rej.style.backgroundPosition = `${(t * 8 * this.U).toFixed(1)}px ${(t * 5 * this.U).toFixed(1)}px`;
    // entrada y salida
    const p = P(t, 0, 0.45, E.io3), cierre = q > 0 ? 1 - E.io3(q) : 1, v = Math.min(p, cierre);
    if (s.entrada === 'iris') {                          // el iris nace abajo (no en el centro: ahí está la cara y parecería una mancha)
      this.f.style.clipPath = `circle(${(v * 140).toFixed(2)}% at 50% 108%)`;
      this.f.style.opacity = '1';
    } else if (s.entrada === 'cortina') {
      this.f.style.clipPath = `inset(0 ${((1 - v) * 100).toFixed(2)}% 0 0)`;
      this.f.style.opacity = '1';
    } else {
      this.f.style.clipPath = 'none';
      this.f.style.opacity = v.toFixed(3);
    }
  }
}
