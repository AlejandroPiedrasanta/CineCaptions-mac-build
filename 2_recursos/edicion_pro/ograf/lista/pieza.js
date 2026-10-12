// CineCaptions · Edición PRO — «Lista»: pasos, datos o ventajas que se van sumando con la voz (en columna o en fichas).
import { PiezaPro, el, esc, tiempos, P, E, FAMILIA, PESO, clamp, icono, bump, sobre } from './lib/motor.js';

export default class Lista extends PiezaPro {
  static DEFAULTS = {
    titulo: '', item1: 'Uno', item2: 'Dos', item3: '', item4: '', tiempos: '0,0.4,0.8,1.2,1.6', icono: 'check',
    disposicion: 'columna', fuente: 'grotesk', acento: '#c9a46a', colorTexto: '#ffffff', colorPanel: '#121212', escala: 1, x: 50, y: 28,
  };
  static SALIDA = 0.4;
  static CSS = `
  .lst{display:flex;flex-direction:column;align-items:stretch}
  .kick{font-family:'CCMono',monospace;font-weight:500;letter-spacing:.26em;text-transform:uppercase;white-space:nowrap;text-shadow:0 2px 12px rgba(0,0,0,.7)}
  .col{border-radius:calc(var(--u)*18);overflow:hidden;box-shadow:0 calc(var(--u)*40) calc(var(--u)*90) calc(var(--u)*-30) rgba(0,0,0,.9)}
  .col .bar{height:calc(var(--u)*8)}
  .row{display:flex;align-items:center;gap:calc(var(--u)*22);padding:calc(var(--u)*18) calc(var(--u)*30);border-top:1px solid rgba(255,255,255,.08)}
  .row:first-of-type{border-top:0}
  .ic{flex:none;display:flex;align-items:center;justify-content:center;border-radius:50%}
  .tx{white-space:nowrap;line-height:1.1}
  .fil{display:flex;gap:calc(var(--u)*20);justify-content:center}
  .tile{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:calc(var(--u)*16);border-radius:calc(var(--u)*16);
        padding:calc(var(--u)*26) calc(var(--u)*18);box-shadow:0 calc(var(--u)*30) calc(var(--u)*70) calc(var(--u)*-24) rgba(0,0,0,.85)}`;

  construir(s) {
    const fam = s.fuente in FAMILIA ? s.fuente : 'grotesk', peso = PESO[fam], k = +s.escala || 1;
    const items = [s.item1, s.item2, s.item3, s.item4].map(x => String(x || '').trim()).filter(Boolean);
    this.caja = el('div', 'L lst', this._escena);
    this.kick = el('div', 'kick', this.caja, esc(s.titulo || ''));
    Object.assign(this.kick.style, { fontSize: Math.max(14, 28 * this.U * k) + 'px', color: s.acento, marginBottom: 16 * this.U + 'px' });
    this.kick.style.display = s.titulo ? 'block' : 'none';
    this.filas = [];
    const icoHtml = (i, tam) => s.icono === 'numero' ? `<b style="font:600 ${tam * 0.55}px 'CCMono',monospace">${i + 1}</b>`
      : s.icono === 'punto' ? `<i style="display:block;width:${tam * 0.32}px;height:${tam * 0.32}px;border-radius:50%;background:currentColor"></i>` : icono(s.icono in { check: 1, estrella: 1, corazon: 1 } ? s.icono : 'check', tam * 0.58, 2.6);
    if (s.disposicion === 'fila' && items.length) {
      const fil = el('div', 'fil', this.caja);
      const tw = Math.min(260 * this.U * k, (this.W * 0.9 - (items.length - 1) * 20 * this.U) / items.length);
      items.forEach((txt, i) => {
        const tile = el('div', 'tile', fil);
        Object.assign(tile.style, { width: tw + 'px', background: s.colorPanel, borderTop: `${6 * this.U}px solid ${s.acento}`, color: s.acento });
        el('div', 'ic', tile, icoHtml(i, 70 * this.U * k));
        const tx = el('div', 'tx', tile, esc(txt));
        const px = this.encajar(txt, 40 * this.U * k, tw - 30 * this.U, fam, peso);
        Object.assign(tx.style, { fontFamily: FAMILIA[fam], fontWeight: peso, fontSize: px + 'px', color: s.colorTexto });
        this.filas.push(tile);
      });
    } else {
      const ancho = Math.min(this.W * 0.86, 900 * this.U * k);
      const col = el('div', 'col', this.caja);
      Object.assign(col.style, { width: ancho + 'px', background: s.colorPanel });
      el('div', 'bar', col).style.background = s.acento;
      const tam = 52 * this.U * k;
      items.forEach((txt, i) => {
        const row = el('div', 'row', col);
        const ic = el('div', 'ic', row, icoHtml(i, tam));
        Object.assign(ic.style, { width: tam + 'px', height: tam + 'px', background: s.acento, color: sobre(s.acento) });
        const tx = el('div', 'tx', row, esc(txt));
        const px = this.encajar(txt, 40 * this.U * k, ancho - tam - 100 * this.U, fam, peso);
        Object.assign(tx.style, { fontFamily: FAMILIA[fam], fontWeight: peso, fontSize: px + 'px', color: s.colorTexto });
        this.filas.push(row);
      });
    }
    this.ts = tiempos(s.tiempos, this.filas.length + 1, 0.4);
  }

  pintar(t, q, s) {
    if (!this.caja) return;
    const pk = P(t, this.ts[0] - 0.04, 0.45, E.out4);
    this.kick.style.opacity = pk.toFixed(3);
    this.filas.forEach((f, i) => {
      const p = P(t, this.ts[i + 1] - 0.04, 0.5, E.out4), w = bump(t, this.ts[this.ts.length - 1] + 0.5 + i * 0.07, 0.3);
      f.style.opacity = clamp(p * 1.8).toFixed(3);
      f.style.transform = `translateY(${((1 - p) * 34 * this.U - 8 * this.U * w).toFixed(1)}px) scale(${(0.94 + 0.06 * p).toFixed(4)})`;
    });
    this.put(this.caja, { x: this.W * (+s.x / 100), y: this.H * (+s.y / 100) - q * 24 * this.U, o: 1 - q, b: q * 6 * this.U });
  }
}
