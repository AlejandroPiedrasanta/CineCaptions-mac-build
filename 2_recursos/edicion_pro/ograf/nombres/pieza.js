// CineCaptions · Edición PRO — «Nombres»: «Ana & Luis», «Mis XV · Valeria»: nombres en cursiva con el conector en el acento y una línea con la fecha.
import { PiezaPro, el, esc, palabras, tiempos, P, E, FAMILIA, PESO, clamp } from './lib/motor.js';

export default class Nombres extends PiezaPro {
  static DEFAULTS = {
    nombre1: 'Ana', conector: '&', nombre2: 'Luis', subtitulo: '', tiempos: '0,0.5,0.9,1.4', fuente: 'serif',
    acento: '#d8b67a', colorTexto: '#ffffff', adorno: 'lineas', escala: 1, x: 50, y: 30,
  };
  static SALIDA = 0.5;
  static CSS = `
  .nm{display:flex;flex-direction:column;align-items:center;text-align:center}
  .n{line-height:.95;white-space:nowrap;text-shadow:0 calc(var(--u)*8) calc(var(--u)*40) rgba(0,0,0,.45)}
  .y{line-height:1;margin:calc(var(--u)*-6) 0}
  .sub{display:flex;align-items:center;gap:calc(var(--u)*18);margin-top:calc(var(--u)*20);font-family:'CCMono',monospace;font-weight:500;letter-spacing:.3em;text-transform:uppercase;white-space:nowrap;text-shadow:0 2px 12px rgba(0,0,0,.7)}
  .sub i{display:block;height:1.5px;transform-origin:50% 50%}`;

  construir(s) {
    const fam = s.fuente in FAMILIA ? s.fuente : 'serif', peso = PESO[fam], k = +s.escala || 1;
    const italica = fam === 'serif' ? 'italic' : 'normal';
    this.caja = el('div', 'L nm', this._escena);
    const base = (this.vertical ? 0.2 : 0.12) * this.W * k, ancho = this.W * 0.88;
    const n1 = String(s.nombre1 || '').trim(), n2 = String(s.nombre2 || '').trim(), cn = String(s.conector || '').trim();
    const linea = (txt, rel, color) => {
      const d = el('div', 'n', this.caja);
      Object.assign(d.style, { fontFamily: FAMILIA[fam], fontWeight: peso, fontStyle: italica, color,
        fontSize: this.encajar(txt, base * rel, ancho, fam, peso, italica) + 'px' });
      return palabras(d, txt);
    };
    this.grupos = [];
    if (n1) this.grupos.push(linea(n1, 1, s.colorTexto));
    if (cn) { const g = linea(cn, 0.55, s.acento); g.forEach(w => w.parentNode.classList.add('y')); this.grupos.push(g); }
    if (n2) this.grupos.push(linea(n2, 1, s.colorTexto));
    this.sub = el('div', 'sub', this.caja);
    const lin = s.adorno === 'lineas' ? `<i style="width:${70 * this.U * k}px;background:${s.acento}"></i>` : '';
    this.sub.innerHTML = `${lin}<span>${esc(s.subtitulo || '')}</span>${lin}`;
    Object.assign(this.sub.style, { fontSize: Math.max(13, 26 * this.U * k) + 'px', color: s.acento, display: s.subtitulo ? 'flex' : 'none' });
    this.ts = tiempos(s.tiempos, 4, 0.45);
  }

  pintar(t, q, s) {
    if (!this.caja) return;
    this.grupos.forEach((ws, i) => ws.forEach(w => this.letras(w, t, this.ts[i], 'desenfoque', 0.55)));
    const ps = P(t, this.ts[3], 0.5, E.out3);
    this.sub.style.opacity = ps.toFixed(3);
    this.sub.querySelectorAll('i').forEach(i => { i.style.transform = `scaleX(${Math.max(0.001, P(t, this.ts[3] + 0.1, 0.6, E.io3)).toFixed(3)})`; });
    this.put(this.caja, { x: this.W * (+s.x / 100), y: this.H * (+s.y / 100) - q * 24 * this.U, o: 1 - q, b: q * 8 * this.U });
  }
}
