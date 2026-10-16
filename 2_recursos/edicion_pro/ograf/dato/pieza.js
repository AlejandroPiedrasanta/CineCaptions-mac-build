// CineCaptions · Edición PRO — «Dato» (v5.5.8): la tarjeta de precio / cifra / gráfica del Tema 5 y 6, EDITABLE en el Inspector de Resolve
// (pedido: «los motions que el usuario pueda retocarlos en el Inspector sin afectar el motion»). Antes era un video de Remotion; ahora el
// texto, la moneda, los colores, la tipografía, la posición y el tamaño se cambian en el Inspector y la animación se recalcula sola.
// Mismo aspecto que Objetos.tsx (Precio, Grafica, Cifra): carta de cristal oscuro o blanca, cifra grande, línea o barras que se dibujan.
// La cifra sale ENTERA (nunca intermedias: un fotograma pausado parecería un dato real).
import { PiezaPro, el, esc, tiempos, P, E, S, FAMILIA, PESO, clamp } from './lib/motor.js';

const D_OSCURO = { carta: 'linear-gradient(180deg, rgba(40,44,60,.94), rgba(20,22,32,.94))', borde: 'rgba(255,255,255,.12)', gris: '#9AA1B4',
                 suave: 'rgba(255,255,255,.08)', sombra: '0 24px 60px rgba(0,0,0,.45)', punto: '#1B1E29' };
const D_CLARO = { carta: '#FFFFFF', borde: 'rgba(0,0,0,.05)', gris: '#8B8B95', suave: '#EEF0F4', sombra: '0 24px 60px rgba(30,40,80,.16)', punto: '#FFFFFF' };
const D_TEXTO_OSCURO = '#f4f5f9', D_TINTA = '#1d1d21';

const aRgb = (hex) => { const h = String(hex || '#4c7dff').replace('#', ''); return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16) || 0); };

export default class Dato extends PiezaPro {
  static DEFAULTS = {
    tipo: 'precio', valor: '80', signo: '$', etiqueta: 'TOTAL', tendencia: 'sube', tema: 'oscuro', acento: '#4c7dff', colorTexto: '#f4f5f9',
    fuente: 'grotesk', tiempos: '0.1', escala: 1, x: 50, y: 73,
  };
  static SALIDA = 0.35;
  static CSS = `
  .carta{position:absolute;left:0;top:0;box-sizing:border-box;display:flex;flex-direction:column}
  .cab{display:flex;justify-content:space-between;align-items:flex-end;gap:calc(var(--u)*18)}
  .et{font-weight:700;letter-spacing:.14em;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .ranura{overflow:hidden;line-height:1.02;padding-bottom:.04em}
  .num{display:block;letter-spacing:-.03em;white-space:nowrap}
  .graf{position:relative;overflow:visible}
  .barra{position:absolute;bottom:0;border-radius:calc(var(--u)*16)}`;

  construir(s) {
    const k = +s.escala || 1, U = this.U * k, T = s.tema === 'claro' ? D_CLARO : D_OSCURO;
    const fam = s.fuente in FAMILIA ? s.fuente : 'grotesk';
    // el texto por defecto es el del cristal oscuro: con la carta blanca, tinta oscura (salvo que el usuario lo haya cambiado)
    const texto = s.tema === 'claro' && String(s.colorTexto).toLowerCase() === D_TEXTO_OSCURO ? D_TINTA : s.colorTexto;
    const tipo = ['precio', 'grafica', 'cifra'].includes(s.tipo) ? s.tipo : 'precio';
    const ancho = (tipo === 'grafica' ? 700 : tipo === 'cifra' ? 560 : 640) * U, pad = 34 * U;
    this.U2 = U; this.tipo = tipo; this.ancho = ancho;
    this.carta = el('div', 'carta', this._escena);
    Object.assign(this.carta.style, { width: ancho + 'px', padding: pad + 'px', borderRadius: 32 * U + 'px', background: tipo === 'cifra' ? 'transparent' : T.carta,
                                      border: tipo === 'cifra' ? 'none' : `${1.2 * U}px solid ${T.borde}`, boxShadow: tipo === 'cifra' ? 'none' : T.sombra });
    const signo = String(s.signo || '').trim(), valor = String(s.valor || '').trim();
    const sube = s.tendencia === 'baja' ? -1 : s.tendencia === 'sube' ? 1 : 0;
    let numero;
    if (tipo === 'grafica') {
      const pct = signo === '%';
      numero = (sube > 0 ? '+' : sube < 0 ? '−' : '') + (pct ? '' : signo) + valor + (pct ? '%' : '');
    } else if (tipo === 'precio') numero = signo + valor;
    else numero = valor + (signo === '%' ? '%' : '');
    const cab = el('div', 'cab', this.carta);
    if (tipo === 'cifra') { cab.style.flexDirection = 'column'; cab.style.alignItems = 'center'; }
    const r = el('div', 'ranura', tipo === 'cifra' ? cab : cab);
    this.num = el('span', 'num', r, esc(numero));
    const [ar, ag, ab] = aRgb(s.acento);
    Object.assign(this.num.style, {
      fontFamily: tipo === 'cifra' ? FAMILIA.serif : FAMILIA[fam], fontWeight: tipo === 'cifra' ? 400 : PESO[fam], fontStyle: tipo === 'cifra' ? 'italic' : 'normal',
      fontSize: (tipo === 'cifra' ? 250 : 92) * U + 'px', color: tipo === 'precio' ? texto : s.acento,
      textShadow: tipo === 'cifra' ? `0 ${8 * U}px ${36 * U}px rgba(0,0,0,.35)` : 'none',
    });
    this.et = el('div', 'et', cab, esc(s.etiqueta || ''));
    Object.assign(this.et.style, { fontFamily: FAMILIA[fam], fontSize: (tipo === 'cifra' ? 40 : 15) * U + 'px', color: tipo === 'cifra' ? texto : T.gris,
                                   maxWidth: (tipo === 'cifra' ? ancho * 1.4 : ancho * 0.55) + 'px', whiteSpace: tipo === 'cifra' ? 'normal' : 'nowrap',
                                   textAlign: tipo === 'cifra' ? 'center' : 'left', lineHeight: tipo === 'cifra' ? '1.15' : '1',
                                   letterSpacing: tipo === 'cifra' ? '0' : '.14em', fontWeight: tipo === 'cifra' ? 500 : 700,
                                   textTransform: tipo === 'cifra' ? 'none' : 'uppercase', marginTop: tipo === 'cifra' ? 8 * U + 'px' : '0' });
    if (tipo !== 'cifra') cab.insertBefore(this.et, r);                       // etiqueta a la izquierda, cifra a la derecha
    if (tipo === 'precio') { cab.style.flexDirection = 'column'; cab.style.alignItems = 'flex-start'; cab.style.gap = 2 * U + 'px'; }
    this.et.style.display = s.etiqueta ? 'block' : 'none';
    // la gráfica: línea con su área (precio) o cinco barras con la línea encima (gráfica)
    this.linea = this.area = this.punto = null; this.barras = [];
    if (tipo !== 'cifra') {
      const w = ancho - 2 * pad, h = (tipo === 'grafica' ? 210 : 150) * U;
      const g = el('div', 'graf', this.carta);
      Object.assign(g.style, { width: w + 'px', height: h + 'px', marginTop: (tipo === 'grafica' ? 22 : 18) * U + 'px' });
      const svgNS = 'http://www.w3.org/2000/svg';
      if (tipo === 'grafica') {
        const alt = sube < 0 ? [1, 0.82, 0.7, 0.52, 0.34] : [0.34, 0.46, 0.58, 0.76, 1];
        const anchoB = 92 * U, hueco = (w - 5 * anchoB) / 4;
        this.alturas = alt; this.altoG = h;
        alt.forEach((a, i) => {
          const b = el('div', 'barra', g);
          const ultimo = sube < 0 ? i === 0 : i === alt.length - 1;
          Object.assign(b.style, { left: i * (anchoB + hueco) + 'px', width: anchoB + 'px', height: '2px',
                                   background: ultimo ? `linear-gradient(180deg, rgb(${ar},${ag},${ab}), rgba(${ar},${ag},${ab},.75))` : T.suave });
          this.barras.push(b);
        });
        this.puntos = alt.map((a, i) => [i * (anchoB + hueco) + anchoB / 2, h - a * h - 18 * U]);
      } else {
        const ys = [0.82, 0.74, 0.78, 0.62, 0.66, 0.5, 0.54, 0.36, 0.3, 0.12];
        this.puntos = ys.map((y, i) => [(i / (ys.length - 1)) * w, (sube < 0 ? 1 - y : y) * h]);
      }
      const svg = document.createElementNS(svgNS, 'svg');
      svg.setAttribute('width', w); svg.setAttribute('height', h);
      svg.style.overflow = 'visible'; svg.style.position = 'absolute'; svg.style.left = '0'; svg.style.top = '0';
      const d = this.puntos.map((q, i) => (i ? 'L' : 'M') + q[0].toFixed(1) + ' ' + q[1].toFixed(1)).join(' ');
      const idg = 'ccDatoArea';                                           // fijo: cada pieza vive en su Shadow DOM (y así el render es determinista)
      svg.innerHTML = (tipo === 'precio'
        ? `<defs><linearGradient id="${idg}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="rgba(${ar},${ag},${ab},.28)"/><stop offset="1" stop-color="rgba(${ar},${ag},${ab},0)"/></linearGradient></defs>
           <path class="area" d="${d} L${w} ${h} L0 ${h} Z" fill="url(#${idg})"/>` : '')
        + `<path class="linea" d="${d}" pathLength="1" fill="none" stroke="${tipo === 'grafica' ? texto : s.acento}" stroke-width="${(tipo === 'grafica' ? 5 : 4) * U}" stroke-linecap="round" stroke-linejoin="round"/>
           <circle class="punto" r="${8 * U}" fill="${T.punto}" stroke="${s.acento}" stroke-width="${4 * U}"/>`;
      g.appendChild(svg);
      this.area = svg.querySelector('.area'); this.linea = svg.querySelector('.linea'); this.punto = svg.querySelector('.punto');
    }
    this.ts = tiempos(s.tiempos, 1, 0.1);
  }

  pintar(t, q, s) {
    if (!this.carta) return;
    const t0 = this.ts[0], U = this.U2;
    const pe = S(t, t0, 'rebote', 0.9);                                       // la carta entra con un resorte de Motion
    const pn = S(t, t0 + 0.12, 'firme');
    this.num.style.transform = `translateY(${((1 - clamp(pn, 0, 1.2)) * 105).toFixed(2)}%)`;
    this.et.style.opacity = clamp((t - t0 - 0.2) / 0.3).toFixed(3);
    const pl = P(t, t0 + (this.tipo === 'grafica' ? 0.9 : 0.25), this.tipo === 'grafica' ? 0.7 : 1.2, E.io3);
    if (this.linea) this.linea.style.strokeDasharray = `${pl.toFixed(4)} 1`;
    if (this.area) this.area.style.clipPath = `inset(0 ${((1 - pl) * 100).toFixed(2)}% 0 0)`;
    if (this.punto) {
      const i = Math.max(0, Math.min(this.puntos.length - 1, Math.round(pl * (this.puntos.length - 1))));
      this.punto.setAttribute('cx', this.puntos[i][0].toFixed(1)); this.punto.setAttribute('cy', this.puntos[i][1].toFixed(1));
      this.punto.style.opacity = pl > 0.05 ? '1' : '0';
    }
    this.barras.forEach((b, i) => {
      const k = E.out3(clamp((t - t0 - 0.25 - i * 0.12) / 0.6));
      b.style.height = Math.max(2, this.alturas[i] * this.altoG * k).toFixed(1) + 'px';
    });
    const flota = Math.sin(t * 1.6) * 6 * U;                                   // centro de la carta en (x, y) %, escalando desde su centro
    this.put(this.carta, { x: this.W * (+s.x / 100), y: this.H * (+s.y / 100) + flota + (1 - clamp(pe, 0, 1)) * 40 * U - q * 30 * U,
                           s: 0.86 + 0.14 * clamp(pe, 0, 1.15), o: clamp(pe * 2.2) * (1 - q), b: q * 7 * U });
  }
}
