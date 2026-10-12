// CineCaptions · Edición PRO — «Icono»: el concepto que se nombra («boda», «precio», «clientes»…) como infografía: un icono grande que se
// dibuja dentro de un anillo del acento y la palabra debajo. Va encima del «Fondo» (B-roll de motion graphics) o sobre el video.
import { PiezaPro, el, esc, tiempos, P, E, FAMILIA, PESO, clamp, ICONOS, bump } from './lib/motor.js';

const SVG = 'http://www.w3.org/2000/svg';

export default class Icono extends PiezaPro {
  static DEFAULTS = { icono: 'camera', texto: 'CONCEPTO', kicker: '', fuente: 'grotesk', acento: '#c9a46a', colorTexto: '#ffffff', escala: 1, x: 50, y: 42, tiempos: '0,0.35' };
  static SALIDA = 0.35;
  static CSS = `
  .ic{display:flex;flex-direction:column;align-items:center;gap:calc(var(--u)*26)}
  .ring{position:relative}
  .ring svg{position:absolute;left:0;top:0;overflow:visible}
  .k{font-family:'CCMono',monospace;font-weight:500;letter-spacing:.3em;text-transform:uppercase;white-space:nowrap;text-shadow:0 2px 12px rgba(0,0,0,.7)}
  .tx{white-space:nowrap;line-height:1;text-transform:uppercase;letter-spacing:.02em;text-shadow:0 calc(var(--u)*6) calc(var(--u)*30) rgba(0,0,0,.5)}`;

  construir(s) {
    const fam = s.fuente in FAMILIA ? s.fuente : 'grotesk', peso = PESO[fam], k = +s.escala || 1;
    const D = 380 * this.U * k;
    this.caja = el('div', 'L ic', this._escena);
    this.k = el('div', 'k', this.caja, esc(s.kicker || ''));
    Object.assign(this.k.style, { fontSize: Math.max(13, 28 * this.U * k) + 'px', color: s.acento, display: s.kicker ? 'block' : 'none' });
    const ring = el('div', 'ring', this.caja);
    Object.assign(ring.style, { width: D + 'px', height: D + 'px' });
    const svg = document.createElementNS(SVG, 'svg');
    svg.setAttribute('width', D); svg.setAttribute('height', D); svg.setAttribute('viewBox', '0 0 100 100');
    svg.innerHTML = `<circle cx="50" cy="50" r="47" fill="rgba(255,255,255,0.04)" stroke="${s.acento}" stroke-width="2.2" pathLength="1" transform="rotate(-90 50 50)"/>` +
      `<g transform="translate(26 26) scale(2)" fill="none" stroke="${s.colorTexto}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">${ICONOS[s.icono] || ICONOS.camera}</g>`;
    ring.appendChild(svg);
    this.aro = svg.querySelector('circle');
    this.trazos = [...svg.querySelectorAll('g *')];
    this.trazos.forEach(p => p.setAttribute('pathLength', '1'));
    this.ringEl = ring;
    this.tx = el('div', 'tx', this.caja, esc(s.texto || ''));
    Object.assign(this.tx.style, { fontFamily: FAMILIA[fam], fontWeight: peso, color: s.colorTexto,
      fontSize: this.encajar(String(s.texto || '').toUpperCase(), 110 * this.U * k, this.W * 0.86, fam, peso) + 'px' });
    this.ts = tiempos(s.tiempos, 2, 0.35);
  }

  pintar(t, q, s) {
    if (!this.caja) return;
    const t0 = this.ts[0];
    this.aro.style.strokeDasharray = `${P(t, t0, 0.7, E.io3).toFixed(4)} 1`;
    this.trazos.forEach((p, i) => { p.style.strokeDasharray = `${P(t, t0 + 0.15 + i * 0.06, 0.6, E.io3).toFixed(4)} 1`; });
    const pr = P(t, t0, 0.5, E.back), latido = bump(t, this.ts[1] + 0.5, 0.35);
    this.ringEl.style.transform = `scale(${(lerpS(0.6, 1, pr) * (1 + 0.04 * latido)).toFixed(4)})`;
    const pk = P(t, t0 + 0.05, 0.4, E.out3);
    this.k.style.opacity = pk.toFixed(3);
    const pt = P(t, this.ts[1] - 0.04, 0.45, E.out4);
    this.tx.style.opacity = clamp(pt * 1.6).toFixed(3);
    this.tx.style.transform = `translateY(${((1 - pt) * 26 * this.U).toFixed(1)}px)`;
    this.put(this.caja, { x: this.W * (+s.x / 100), y: this.H * (+s.y / 100) - q * 24 * this.U, o: (t >= t0 - 0.05 ? 1 : 0) * (1 - q), b: q * 6 * this.U });
  }
}

function lerpS(a, b, p) { return a + (b - a) * p; }
