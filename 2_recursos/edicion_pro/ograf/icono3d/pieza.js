// CineCaptions · Edición PRO — «Icono 3D»: un icono 3D (3dicons, CC0) que FLOTA junto a los captions o dentro de un motion graphic, en vez del
// emoji plano: entra con un resorte de Motion (crece desde 0 girando un poco), sube y baja despacio, se balancea, lleva un resplandor del
// color del video detrás y un destello de luz que lo recorre al entrar y cada pocos segundos. Todo depende solo de t (determinista).
import { PiezaPro, el, S, P, E, clamp, rgb, IMG3D } from './lib/motor.js';

export default class Icono3D extends PiezaPro {
  static DEFAULTS = { imagen: 'fire-front-color', tamano: 16, brillo: 0.7, acento: '#ffb020', flotar: 1, giro: 8, x: 82, y: 30, tiempos: '0' };
  static SALIDA = 0.3;
  static FUENTES = [];
  static CSS = `
  .i3{position:absolute;left:0;top:0}
  .i3 .halo{position:absolute;left:50%;top:55%;border-radius:50%;transform:translate(-50%,-50%)}
  .i3 img{position:absolute;left:0;top:0;width:100%;height:100%;object-fit:contain}
  .i3 .luz{position:absolute;left:0;top:0;width:100%;height:100%;-webkit-mask-size:contain;mask-size:contain;-webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;
           -webkit-mask-position:center;mask-position:center;mix-blend-mode:screen}`;

  construir(s) {
    const d = this.H * clamp(+s.tamano || 16, 3, 60) / 100;           // tamaño = % del alto del cuadro
    const url = IMG3D(s.imagen || 'fire-front-color');
    this.d = d;
    this.caja = el('div', 'L i3', this._escena);
    Object.assign(this.caja.style, { width: d + 'px', height: d + 'px' });
    const [r, g, b] = rgb(s.acento || '#ffb020');
    this.halo = el('div', 'halo', this.caja);
    Object.assign(this.halo.style, { width: d * 1.15 + 'px', height: d * 1.15 + 'px',
      background: `radial-gradient(circle, rgba(${r},${g},${b},0.55) 0%, rgba(${r},${g},${b},0.18) 45%, rgba(${r},${g},${b},0) 70%)` });
    this.img = el('img', '', this.caja);
    this.img.src = url;
    this.img.style.filter = `drop-shadow(0 ${0.06 * d}px ${0.08 * d}px rgba(0,0,0,.45)) drop-shadow(0 0 ${0.06 * d}px rgba(${r},${g},${b},${(0.6 * (+s.brillo || 0)).toFixed(2)}))`;
    this.luz = el('div', 'luz', this.caja);
    this.luz.style.webkitMaskImage = this.luz.style.maskImage = `url("${url}")`;
    this.t0 = parseFloat(String(s.tiempos || '0').split(',')[0]) || 0;
  }

  pintar(t, q, s) {
    if (!this.caja) return;
    const tt = t - this.t0, k = +s.brillo || 0;
    const pop = S(t, this.t0, 'rebote', 0.85);                          // resorte de Motion: crece, se pasa y vuelve
    const flota = (+s.flotar || 0) * this.d * 0.05 * Math.sin(tt * 2.1);
    const giro = (+s.giro || 0) * (Math.sin(tt * 1.3) * 0.6 + (1 - clamp(pop)) * -2.5);
    this.halo.style.opacity = (k * (0.75 + 0.25 * Math.sin(tt * 3.0)) * clamp(pop)).toFixed(3);
    // destello: una banda de luz cruza el icono al entrar y luego cada 2,6 s
    const ciclo = tt < 0.9 ? tt / 0.9 : ((tt - 0.9) % 2.6) / 0.7;
    const x = -60 + 220 * clamp(ciclo);
    this.luz.style.background = ciclo <= 1 && k > 0
      ? `linear-gradient(115deg, rgba(255,255,255,0) ${x - 25}%, rgba(255,255,255,${(0.75 * k).toFixed(2)}) ${x}%, rgba(255,255,255,0) ${x + 25}%)` : 'none';
    this.put(this.caja, { x: this.W * (+s.x / 100), y: this.H * (+s.y / 100) + flota - q * this.d * 0.15, r: giro, s: Math.max(0.001, pop) * (1 - 0.25 * q),
                          o: (tt >= -0.02 ? 1 : 0) * (1 - q) });
  }
}
