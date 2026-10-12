// CineCaptions · Edición PRO — «Cifra»: un dato que se dice (3 acres, 15 años, 40 %): número grande que sube por una ranura, unidad y etiqueta.
// El número sale ENTERO (nunca cifras intermedias: un fotograma pausado parecería un dato real).
import { PiezaPro, el, esc, tiempos, P, E, FAMILIA, PESO, clamp } from './lib/motor.js';

export default class Cifra extends PiezaPro {
  static DEFAULTS = {
    numero: '3', unidad: 'ACRES', etiqueta: '', tiempos: '0,0.3,0.6', fuente: 'grotesk',
    acento: '#c9a46a', colorTexto: '#ffffff', estilo: 'linea', escala: 1, x: 50, y: 28,
  };
  static SALIDA = 0.4;
  static CSS = `
  .cf{display:flex;flex-direction:column;align-items:center}
  .fila{display:flex;align-items:baseline;gap:calc(var(--u)*18);position:relative}
  .ranura{overflow:hidden;line-height:1;padding:0 calc(var(--u)*6)}
  .num{display:block;line-height:1;letter-spacing:-.03em;text-shadow:0 calc(var(--u)*8) calc(var(--u)*36) rgba(0,0,0,.45)}
  .uni{line-height:1;white-space:nowrap;text-shadow:0 calc(var(--u)*4) calc(var(--u)*24) rgba(0,0,0,.5)}
  .et{font-family:'CCMono',monospace;font-weight:500;letter-spacing:.24em;text-transform:uppercase;white-space:nowrap;margin-top:calc(var(--u)*18);text-shadow:0 2px 12px rgba(0,0,0,.7)}
  .deco{position:absolute;left:0;top:0;pointer-events:none}
  .blq{position:absolute;inset:-6% -4%;border-radius:calc(var(--u)*10);transform-origin:0 50%;z-index:-1}`;

  construir(s) {
    const fam = s.fuente in FAMILIA ? s.fuente : 'grotesk', peso = PESO[fam];
    const k = +s.escala || 1;
    this.caja = el('div', 'L cf', this._escena);
    const fila = el('div', 'fila', this.caja);
    const numTxt = String(s.numero || '').trim(), uniTxt = String(s.unidad || '').trim();
    let pxN = 0.36 * Math.min(this.W, this.H) * k, pxU = pxN * 0.34;
    const total = (pxN / 100) * this._ancho(numTxt, fam, peso) + (pxU / 100) * this._ancho(uniTxt, fam, peso) + 30 * this.U;
    const cabe = this.W * 0.86;
    if (total > cabe) { pxN *= cabe / total; pxU *= cabe / total; }
    if (s.estilo === 'bloque') { this.blq = el('div', 'blq', fila); this.blq.style.background = s.acento; }
    const r = el('div', 'ranura', fila);
    this.num = el('span', 'num', r, esc(numTxt));
    Object.assign(this.num.style, { fontFamily: FAMILIA[fam], fontWeight: peso, fontSize: pxN + 'px', color: s.estilo === 'bloque' ? '#111' : s.colorTexto });
    this.uni = el('span', 'uni', fila, esc(uniTxt));
    Object.assign(this.uni.style, { fontFamily: FAMILIA[fam], fontWeight: peso, fontSize: pxU + 'px', color: s.acento });
    this.et = el('div', 'et', this.caja, esc(s.etiqueta || ''));
    Object.assign(this.et.style, { fontSize: Math.max(14, 30 * this.U * k) + 'px', color: s.colorTexto });
    this.et.style.display = s.etiqueta ? 'block' : 'none';
    if (s.estilo === 'linea' || s.estilo === 'anillo') {
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('class', 'deco');
      svg.style.overflow = 'visible';
      const w = pxN * 0.62 * Math.max(1, numTxt.length) + pxU * 0.6 * uniTxt.length, h = pxN;
      svg.setAttribute('width', w); svg.setAttribute('height', h);
      svg.innerHTML = s.estilo === 'anillo'
        ? `<ellipse pathLength="1" cx="${pxN * 0.33 * Math.max(1, numTxt.length)}" cy="${h * 0.52}" rx="${pxN * 0.42 * Math.max(1, numTxt.length * 0.75)}" ry="${h * 0.6}" fill="none" stroke="${s.acento}" stroke-width="${Math.max(2, 6 * this.U)}" stroke-linecap="round" transform="rotate(-8 ${pxN * 0.33} ${h * 0.5})"/>`
        : `<line pathLength="1" x1="0" y1="${h * 1.04}" x2="${w}" y2="${h * 1.04}" stroke="${s.acento}" stroke-width="${Math.max(3, 8 * this.U)}" stroke-linecap="round"/>`;
      fila.appendChild(svg);
      this.trazo = svg.firstChild;
    }
    this.ts = tiempos(s.tiempos, 3, 0.3);
  }
  _ancho(txt, fam, peso) {
    const c = document.createElement('canvas').getContext('2d');
    c.font = `${peso} 100px ${FAMILIA[fam]}`;
    return c.measureText(txt).width;
  }

  pintar(t, q, s) {
    if (!this.caja) return;
    const pn = P(t, this.ts[0] - 0.04, 0.55, E.out4);
    this.num.style.transform = `translateY(${((1 - pn) * 105).toFixed(2)}%)`;
    const pu = P(t, this.ts[1] - 0.04, 0.45, E.out4);
    this.uni.style.opacity = clamp(pu * 2).toFixed(3);
    this.uni.style.transform = `translateX(${((1 - pu) * -24 * this.U).toFixed(1)}px)`;
    const pe = P(t, this.ts[2] - 0.04, 0.45, E.out3);
    this.et.style.opacity = pe.toFixed(3);
    this.et.style.transform = `translateY(${((1 - pe) * 14 * this.U).toFixed(1)}px)`;
    const pd = P(t, this.ts[0] + 0.25, 0.7, E.io3);
    if (this.trazo) this.trazo.style.strokeDasharray = `${pd.toFixed(4)} 1`;
    if (this.blq) this.blq.style.transform = `scaleX(${Math.max(0.001, pd).toFixed(4)})`;
    this.put(this.caja, { x: this.W * (+s.x / 100), y: this.H * (+s.y / 100) - q * 26 * this.U, o: 1 - q, b: q * 7 * this.U });
  }
}
