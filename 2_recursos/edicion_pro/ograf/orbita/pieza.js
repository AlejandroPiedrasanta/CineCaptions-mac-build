// CineCaptions · Edición PRO — «Órbita»: los iconos del tema giran alrededor de la cabeza (el gancho de la skill con Magic Mask). Se ponen DOS:
// la mitad de atrás (mitad=atras) DEBAJO de la persona recortada y la de delante (mitad=delante) encima; las dos hacen la MISMA cuenta, así que
// un icono pasa de una a otra justo en los lados de la elipse (fuera de la silueta) y no se nota el cambio. Lo de delante pasa un poco más
// grande y más brillante (profundidad); lo de atrás, más pequeño y apagado. Entra con un resorte de Motion (el radio crece desde la cabeza).
import { PiezaPro, el, S, P, E, clamp, icono, IMG3D } from './lib/motor.js';

export default class Orbita extends PiezaPro {
  static DEFAULTS = { iconos: 'casa,key,bed,waves', imagenes: '', mitad: 'todo', acento: '#c9a46a', colorTexto: '#ffffff', x: 50, y: 30, rx: 22, ry: 4.5,
                      inclinacion: -8, vueltas: 0.32, escala: 1, tiempos: '0' };
  static SALIDA = 0.35;
  static FUENTES = [];
  static CSS = `
  .ic{display:flex;align-items:center;justify-content:center;border-radius:50%;border-style:solid}
  .ic svg{display:block}`;

  construir(s) {
    const k = +s.escala || 1, d = 104 * this.U * k;
    const imgs = String(s.imagenes || '').split(',').map(x => x.trim()).filter(Boolean).slice(0, 6);
    if (imgs.length >= 3) {                                          // iconos 3D: más grandes, flotando, con su sombra
      const d3 = d * 1.7;
      this.ics = imgs.map(n => {
        const e = el('div', 'L', this._escena);
        const im = el('img', '', e);
        im.src = IMG3D(n);
        Object.assign(e.style, { width: d3 + 'px', height: d3 + 'px' });
        Object.assign(im.style, { width: '100%', height: '100%', objectFit: 'contain', filter: `drop-shadow(0 ${8 * this.U}px ${14 * this.U}px rgba(0,0,0,.5))` });
        return e;
      });
      this.t0 = parseFloat(String(s.tiempos || '0').split(',')[0]) || 0;
      return;
    }
    this.lista = String(s.iconos || '').split(',').map(x => x.trim()).filter(Boolean).slice(0, 6);
    if (!this.lista.length) this.lista = ['estrella'];
    this.ics = this.lista.map(n => {
      const e = el('div', 'L ic', this._escena, icono(n, d * 0.5, 1.8));
      Object.assign(e.style, { width: d + 'px', height: d + 'px', borderWidth: Math.max(1.5, 3 * this.U * k) + 'px', borderColor: s.acento,
                               color: s.colorTexto, background: 'rgba(10,10,12,0.55)', boxShadow: `0 ${8 * this.U}px ${28 * this.U}px rgba(0,0,0,.45)` });
      return e;
    });
    this.t0 = parseFloat(String(s.tiempos || '0').split(',')[0]) || 0;
  }

  pintar(t, q, s) {
    if (!this.ics) return;
    const n = this.ics.length, cx = this.W * (+s.x / 100), cy = this.H * (+s.y / 100);
    const crece = S(t, this.t0, 'rebote', 0.9);                       // el radio se abre con resorte (se pasa un poco y vuelve)
    const rx = this.W * (+s.rx / 100) * crece, ry = this.H * (+s.ry / 100) * crece;
    const inc = (+s.inclinacion || 0) * Math.PI / 180, ci = Math.cos(inc), si = Math.sin(inc);
    const w = 2 * Math.PI * (+s.vueltas || 0.3);
    const entra = P(t, this.t0, 0.35, E.out3);
    this.ics.forEach((e, i) => {
      const th = (2 * Math.PI * i) / n + w * (t - this.t0) - Math.PI / 2;
      const ex = rx * Math.cos(th), ey = ry * Math.sin(th);
      const delante = Math.sin(th) >= 0;                              // la parte baja de la elipse es la que viene hacia la cámara
      const visible = s.mitad === 'todo' || (s.mitad === 'delante') === delante;
      const prof = (Math.sin(th) + 1) / 2;                            // 0 atrás … 1 delante
      this.put(e, { x: cx + ex * ci - ey * si, y: cy + ex * si + ey * ci, s: (0.72 + 0.4 * prof) * (0.6 + 0.4 * entra),
                    o: visible ? clamp(entra * (0.55 + 0.45 * prof)) * (1 - q) : 0 });
    });
  }
}
