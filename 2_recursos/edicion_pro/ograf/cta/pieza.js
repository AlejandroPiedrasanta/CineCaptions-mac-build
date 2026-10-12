// CineCaptions · Edición PRO — «Llamada a la acción»: la ficha del final (título, hasta tres datos dichos en el video y un botón).
import { PiezaPro, el, esc, tiempos, P, E, FAMILIA, PESO, clamp, icono, bump, sobre } from './lib/motor.js';

export default class Cta extends PiezaPro {
  static DEFAULTS = {
    kicker: '', titulo: 'Título', fila1: '', fila2: '', fila3: '', boton: 'Escríbenos', tiempos: '0,0.25,0.5,0.75,1.0,1.3',
    fuente: 'serif', acento: '#c9a46a', colorTexto: '#ffffff', colorPanel: '#121110', escala: 1, x: 50, y: 62, icono: 'check',
  };
  static SALIDA = 0.4;
  static CSS = `
  .card{border-radius:calc(var(--u)*18);overflow:hidden;box-shadow:0 calc(var(--u)*60) calc(var(--u)*120) calc(var(--u)*-30) rgba(0,0,0,.9)}
  .bar{height:calc(var(--u)*10);transform-origin:0 50%}
  .in{padding:calc(var(--u)*30) calc(var(--u)*44) calc(var(--u)*36)}
  .k{font-family:'CCMono',monospace;font-weight:500;letter-spacing:.3em;text-transform:uppercase;white-space:nowrap}
  .t{line-height:1;margin:calc(var(--u)*12) 0 calc(var(--u)*16);white-space:nowrap}
  .row{display:flex;align-items:center;gap:calc(var(--u)*18);padding:calc(var(--u)*12) 0;border-top:1px solid rgba(255,255,255,.1);white-space:nowrap}
  .row i{display:flex}
  .btn{margin-top:calc(var(--u)*22);border-radius:calc(var(--u)*12);display:flex;align-items:center;justify-content:center;gap:calc(var(--u)*14);white-space:nowrap}`;

  construir(s) {
    const fam = s.fuente in FAMILIA ? s.fuente : 'serif', peso = PESO[fam], k = +s.escala || 1;
    const ancho = Math.min(this.W * 0.84, 880 * this.U * k), interior = ancho - 88 * this.U;
    this.caja = el('div', 'L card', this._escena);
    Object.assign(this.caja.style, { width: ancho + 'px', background: s.colorPanel, border: `1.5px solid ${s.acento}55` });
    this.bar = el('div', 'bar', this.caja); this.bar.style.background = s.acento;
    const inn = el('div', 'in', this.caja);
    this.k = el('div', 'k', inn, esc(s.kicker || ''));
    Object.assign(this.k.style, { fontSize: Math.max(13, 24 * this.U * k) + 'px', color: s.acento, display: s.kicker ? 'block' : 'none' });
    this.t = el('div', 't', inn, esc(s.titulo || ''));
    Object.assign(this.t.style, { fontFamily: FAMILIA[fam], fontWeight: peso, color: s.colorTexto, fontSize: this.encajar(s.titulo || '', 92 * this.U * k, interior, fam, peso) + 'px' });
    this.rows = [s.fila1, s.fila2, s.fila3].map(x => String(x || '').trim()).filter(Boolean).map(txt => {
      const r = el('div', 'row', inn, `<i>${icono(s.icono in { check: 1, estrella: 1, corazon: 1, pin: 1 } ? s.icono : 'check', 32 * this.U * k, 2.4)}</i><span>${esc(txt)}</span>`);
      r.querySelector('i').style.color = s.acento;
      Object.assign(r.style, { fontFamily: "'CCGrotesk', Arial, sans-serif", fontWeight: 500, color: s.colorTexto,
        fontSize: this.encajar(txt, 34 * this.U * k, interior - 50 * this.U, 'grotesk', 500) + 'px' });
      return r;
    });
    this.btn = el('div', 'btn', inn, `<span>${esc(s.boton || '')}</span>${icono('flecha', 38 * this.U * k, 2.4)}`);
    Object.assign(this.btn.style, { height: 88 * this.U * k + 'px', background: s.acento, color: sobre(s.acento),
      fontFamily: "'CCGrotesk', Arial, sans-serif", fontWeight: 700, fontSize: this.encajar(s.boton || '', 40 * this.U * k, interior - 80 * this.U, 'grotesk', 700) + 'px',
      display: s.boton ? 'flex' : 'none' });
    this.ts = tiempos(s.tiempos, 6, 0.25);
  }

  pintar(t, q, s) {
    if (!this.caja) return;
    const p = P(t, this.ts[0] - 0.06, 0.6, E.out4);
    this.bar.style.transform = `scaleX(${Math.max(0.001, P(t, this.ts[0] + 0.1, 0.6, E.io3)).toFixed(3)})`;
    const sube = (e, t0) => { const pe = P(t, t0, 0.45, E.out4); e.style.opacity = clamp(pe * 1.7).toFixed(3); e.style.transform = `translateY(${((1 - pe) * 18 * this.U).toFixed(1)}px)`; };
    sube(this.k, this.ts[0] + 0.05); sube(this.t, this.ts[1]);
    this.rows.forEach((r, i) => sube(r, this.ts[2 + i]));
    sube(this.btn, this.ts[5]);
    const g = bump(t, this.ts[5] + 0.55, 0.5);
    this.btn.style.boxShadow = `0 0 ${(40 * g * this.U).toFixed(1)}px ${s.acento}`;
    this.put(this.caja, { x: this.W * (+s.x / 100), y: this.H * (+s.y / 100) + (1 - p) * 60 * this.U, s: 1 + 0.012 * g, o: p * (1 - q), b: (1 - p) * 8 * this.U + q * 6 * this.U });
  }
}
