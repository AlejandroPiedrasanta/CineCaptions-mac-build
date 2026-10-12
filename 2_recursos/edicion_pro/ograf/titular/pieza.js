// CineCaptions · Edición PRO — «Titular»: titular gigante palabra a palabra (va DETRÁS de la persona: la pista de la persona lo tapa).
import { PiezaPro, el, palabras, tiempos, clamp, FAMILIA, PESO } from './lib/motor.js';

export default class Titular extends PiezaPro {
  static DEFAULTS = {
    linea1: '', linea2: 'TITULAR', linea3: '', tamanos: '0.45,1,0.6', acentoLinea: 2, tiempos: '0,0.3,0.6',
    fuente: 'serif', mayusculas: true, acento: '#c9a46a', colorTexto: '#ffffff', entrada: 'subir',
    escala: 1, x: 50, y: 30, ancho: 92, sombra: true,
  };
  static SALIDA = 0.4;
  static CSS = `
  .tit{display:flex;flex-direction:column;align-items:center;text-align:center}
  .ln{line-height:.9;white-space:nowrap;letter-spacing:-.015em}
  .sombra .ln{text-shadow:0 calc(var(--u)*8) calc(var(--u)*42) rgba(0,0,0,.42)}`;

  construir(s) {
    const fam = s.fuente in FAMILIA ? s.fuente : 'serif', peso = PESO[fam];
    this.caja = el('div', 'L tit' + (s.sombra ? ' sombra' : ''), this._escena);
    const tams = String(s.tamanos).split(/[,; ]+/).map(Number);
    const base = (this.vertical ? 0.22 : 0.14) * this.W * (+s.escala || 1);
    const ancho = this.W * clamp((+s.ancho || 92) / 100, 0.2, 1);
    this.ws = [];
    [s.linea1, s.linea2, s.linea3].forEach((txt, i) => {
      txt = String(txt || '').trim();
      if (!txt) return;
      if (s.mayusculas) txt = txt.toUpperCase();
      const ln = el('div', 'ln', this.caja);
      const px = this.encajar(txt, base * (tams[i] > 0 ? tams[i] : 1), ancho, fam, peso);
      Object.assign(ln.style, { fontFamily: FAMILIA[fam], fontWeight: peso, fontSize: px + 'px', color: +s.acentoLinea === i + 1 ? s.acento : s.colorTexto });
      this.ws.push(...palabras(ln, txt));
    });
    this.ts = tiempos(s.tiempos, this.ws.length, 0.3);
  }

  pintar(t, q, s) {
    if (!this.caja) return;
    this.ws.forEach((w, i) => this.letras(w, t, this.ts[i] - 0.04, s.entrada));
    this.put(this.caja, { x: this.W * (+s.x / 100), y: this.H * (+s.y / 100) - q * 34 * this.U, o: 1 - q, b: q * 9 * this.U });
  }
}
