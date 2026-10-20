// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/Efectos5.tsx — las mejoras de motion graphics del Tema 5 (pedido del usuario, v5.4.52):
//   TarjetaT5  la tarjeta de cristal ENCIMA de la cabeza (la persona sigue a la vista): 'mapa' (vuela al país, se ilumina, cae el pin, bandera),
//              'grafica' (las barras crecen y la cifra que se dijo cuenta), 'tachado' (la frase que se dice mal, tachada en rojo), 'lista' (cada
//              cosa entra y se marca cuando se nombra). Nunca enseña un dato que no se dijo (las barras no llevan años ni valores inventados).
//   OrbitaT5   un icono 3D gira alrededor de la cabeza: el programa la renderiza DOS veces ('atras' va debajo de la persona del Magic Mask,
//              'delante' encima), así pasa por detrás de la cabeza y por delante del pecho.
//   StickerT5  la imagen se congela, el fondo se apaga y la persona se despega con borde blanco, como un sticker (el recorte lo hace la IA local).
//   FinalT5    la pantalla final cuando se pide seguir: tu cara en un círculo, tu @usuario y el botón que se pulsa.
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { FAMILIA, clamp, rgb, useFuentes } from './comun';
import { Bandera, useMapa } from './Ubicacion';
import { EmojiAnimado } from './Emoji';

const easeOut = (q: number) => 1 - Math.pow(1 - clamp(q), 3);
const easeInOut = (q: number) => { const x = clamp(q); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const resorte = (q: number) => { const x = clamp(q); return 1 - Math.exp(-6 * x) * Math.cos(9 * x); };

/** '3d:fire-front-color' (3dicons) · 'emoji:house' (Fluent 3D) · sin prefijo: 3dicons. */
const urlIcono = (s: string) => {
  const [tipo, n] = s.includes(':') ? s.split(':') : ['3d', s];
  return tipo === 'emoji' ? staticFile(`stickers/rcs_emoji_${n}.png`) : staticFile(`iconos3d/${n}.png`);
};

const useTiempo = () => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  return { t: frame / fps, fin: durationInFrames / fps, W: width, H: height };
};

const Cursor: React.FC<{ U: number; clic: number }> = ({ U, clic }) => (
  <svg width={46 * U} height={56 * U} viewBox="0 0 36 44" style={{ transform: `scale(${(1 - 0.14 * Math.sin(clamp(clic) * Math.PI)).toFixed(3)})`,
                                                                  filter: `drop-shadow(0 ${4 * U}px ${6 * U}px rgba(0,0,0,.45))` }}>
    <path d="M4 2 L4 34 L13 26 L19 40 L25 37 L19 24 L31 24 Z" fill="#fff" stroke="#111" strokeWidth="2" strokeLinejoin="round" />
  </svg>
);

/* ------------------------------------------------------------------------------------------------ la tarjeta encima de la cabeza */
export type TarjetaProps = {
  tipo?: 'mapa' | 'grafica' | 'tachado' | 'lista'; x?: number; y?: number; escala?: number; acento?: string; aspecto?: 'cristal' | 'blanco';
  pais?: string; nombre?: string; kicker?: string; valor?: string; signo?: string; sube?: number; etiqueta?: string; texto?: string; t_tachar?: number;
  items?: string[]; tiempos?: number[];
};

export const TarjetaT5: React.FC<TarjetaProps> = ({ tipo = 'grafica', x = 50, y = 20, escala = 1, acento = '#4C7DFF', aspecto = 'cristal', pais = '', nombre = '',
                                                     kicker = '', valor = '', signo = '', sube = 0, etiqueta = '', texto = '', t_tachar = 0.6,
                                                     items = [], tiempos = [] }) => {
  useFuentes();
  const m = useMapa();
  const { t, fin, W, H } = useTiempo();
  const U = (Math.min(W, H) / 1080) * escala;
  const [r, g, b] = rgb(acento);
  const oscuro = aspecto !== 'blanco';
  const tinta = oscuro ? '#F5F6FA' : '#1D1D21', gris = oscuro ? 'rgba(255,255,255,.58)' : '#8B8B95', suave = oscuro ? 'rgba(255,255,255,.10)' : '#EEF0F4';
  const e = resorte(t / 0.55), s = easeOut((t - (fin - 0.3)) / 0.3);
  const ancho = Math.min(W * 0.88, 920 * U), pad = 34 * U;
  const carta: React.CSSProperties = {
    width: ancho, boxSizing: 'border-box', padding: pad, borderRadius: 40 * U, position: 'relative', overflow: 'hidden',
    background: oscuro ? 'linear-gradient(180deg, rgba(38,42,58,.90), rgba(16,18,28,.90))' : 'rgba(255,255,255,.97)',
    border: `${1.5 * U}px solid ${oscuro ? 'rgba(255,255,255,.12)' : 'rgba(0,0,0,.05)'}`,
    boxShadow: oscuro ? `0 ${24 * U}px ${60 * U}px rgba(0,0,0,.5), 0 0 ${50 * U}px rgba(${r},${g},${b},.16)` : `0 ${24 * U}px ${60 * U}px rgba(20,30,60,.25)`,
  };
  const chico: React.CSSProperties = { fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 22 * U, letterSpacing: '0.16em', color: gris, textTransform: 'uppercase' };
  let cuerpo: React.ReactNode = null;

  if (tipo === 'mapa') {
    const p = m?.paises[(pais || '').toLowerCase()];
    const mw = ancho - 2 * pad, mh = 300 * U;
    let vb = [0, 0, 1000, 1000 * mh / mw];
    let luz = 0, pin = 0, px = 0, py = 0;
    if (p) {
      const [x0, y0, x1, y1] = p.caja;
      const fin2 = Math.max(26, (x1 - x0) * 3.4, (y1 - y0) * 3.4 * mw / mh);
      const vw = fin2 * (1 + 5 * (1 - easeInOut((t - 0.1) / 1.2)));
      const vh = vw * mh / mw;
      vb = [p.centro[0] - vw / 2, p.centro[1] - vh / 2, vw, vh];
      luz = clamp((t - 0.9) / 0.4);
      pin = resorte((t - 1.15) / 0.5);
      px = (p.centro[0] - vb[0]) / vb[2] * mw;
      py = (p.centro[1] - vb[1]) / vb[3] * mh;
    }
    const nombreTxt = nombre || p?.es || '';
    cuerpo = (
      <div style={carta}>
        <div style={{ position: 'relative', width: mw, height: mh, borderRadius: 24 * U, overflow: 'hidden', background: oscuro ? 'rgba(0,0,0,.25)' : '#F3F5F9' }}>
          <svg width={mw} height={mh} viewBox={vb.map(v => v.toFixed(3)).join(' ')} style={{ position: 'absolute', inset: 0 }}>
            {m && Object.entries(m.paises).map(([k, v]) => (
              <path key={k} d={v.d} fill={oscuro ? 'rgba(255,255,255,0.09)' : '#DDE1EA'} stroke={oscuro ? 'rgba(255,255,255,0.22)' : '#FFFFFF'} strokeWidth={vb[2] / 500} />
            ))}
            {p && <path d={p.d} fill={`rgba(${r},${g},${b},${(0.92 * luz).toFixed(3)})`} stroke={acento} strokeWidth={vb[2] / 260}
                        style={{ filter: `drop-shadow(0 0 ${(14 * U * luz).toFixed(1)}px rgba(${r},${g},${b},.8))` }} />}
            {p && t > 1.3 && [0, 0.5].map((o, i) => {
              const q = ((t - 1.3 - o) % 1.2 + 1.2) % 1.2;
              return <circle key={i} cx={p.centro[0]} cy={p.centro[1]} r={(vb[2] / 9) * q / 1.2} fill="none" stroke={acento} strokeWidth={vb[2] / 300} opacity={(1 - q / 1.2) * 0.8} />;
            })}
          </svg>
          {p && (
            <svg width={64 * U} height={84 * U} viewBox="0 0 24 31" style={{ position: 'absolute', left: px - 32 * U, top: py - 84 * U - (1 - clamp(pin, 0, 1.2)) * 160 * U,
                                                                             opacity: clamp(pin * 3), filter: `drop-shadow(0 ${8 * U}px ${10 * U}px rgba(0,0,0,.5))` }}>
              <path d="M12 0C5.4 0 0 5.2 0 11.7 0 20.4 12 31 12 31s12-10.6 12-19.3C24 5.2 18.6 0 12 0z" fill="#FF3B4D" />
              <circle cx="12" cy="11.5" r="4.6" fill="#fff" />
            </svg>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 22 * U, marginTop: 24 * U, opacity: clamp((t - 1.0) / 0.3),
                      transform: `translateY(${((1 - easeOut((t - 1.0) / 0.45)) * 24 * U).toFixed(1)}px)` }}>
          {pais && <div style={{ borderRadius: 8 * U, overflow: 'hidden', flex: 'none' }}><Bandera iso={pais.toLowerCase()} ancho={92 * U} t={t} /></div>}
          <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.05 }}>
            {kicker && <span style={chico}>{kicker}</span>}
            <span style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 52 * U, color: tinta }}>{nombreTxt}</span>
          </div>
        </div>
      </div>
    );
  } else if (tipo === 'grafica') {
    const limpio = String(valor || '').replace(/,/g, '');
    const v = parseFloat(limpio), dec = (limpio.split('.')[1] || '').length;
    const q = easeOut((t - 0.35) / 1.1);
    const n = isFinite(v) ? (v * q).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec }) : valor;
    const pre = (sube > 0 ? '+' : sube < 0 ? '−' : '') + (signo && signo !== '%' ? signo : ''), post = signo === '%' ? '%' : '';   // v5.5.8: cualquier moneda (₦, Q, R$…)
    const alturas = sube < 0 ? [1, 0.82, 0.7, 0.52, 0.34] : [0.34, 0.46, 0.58, 0.76, 1];
    const altoG = 210 * U, anchoB = 92 * U, hueco = (ancho - 2 * pad - 5 * anchoB) / 4;
    const puntos = alturas.map((h, i) => [i * (anchoB + hueco) + anchoB / 2, altoG - h * altoG * easeOut((t - 0.25 - i * 0.12) / 0.6) - 18 * U]);
    const linea = clamp((t - 0.9) / 0.7);
    cuerpo = (
      <div style={carta}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 22 * U }}>
          <span style={{ ...chico, maxWidth: ancho * 0.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{etiqueta}</span>
          <span style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 92 * U, lineHeight: 0.9, color: `rgb(${r},${g},${b})`, letterSpacing: '-0.02em' }}>{pre}{n}{post}</span>
        </div>
        <div style={{ position: 'relative', height: altoG }}>
          {alturas.map((h, i) => {
            const k = easeOut((t - 0.25 - i * 0.12) / 0.6);
            const ultimo = sube < 0 ? i === 0 : i === alturas.length - 1;
            return <div key={i} style={{ position: 'absolute', bottom: 0, left: i * (anchoB + hueco), width: anchoB, height: Math.max(2, h * altoG * k), borderRadius: 16 * U,
                                         background: ultimo ? `linear-gradient(180deg, rgb(${r},${g},${b}), rgba(${r},${g},${b},.75))` : suave }} />;
          })}
          <svg width={ancho - 2 * pad} height={altoG} style={{ position: 'absolute', inset: 0, overflow: 'visible' }}>
            <polyline points={puntos.map(p => p.map(x => x.toFixed(1)).join(',')).join(' ')} fill="none" stroke={tinta} strokeWidth={5 * U} strokeLinecap="round" strokeLinejoin="round"
                      pathLength={1} strokeDasharray="1" strokeDashoffset={(1 - linea).toFixed(4)} />
            {puntos.map(([x, yy], i) => <circle key={i} cx={x} cy={yy} r={8 * U} fill={tinta} opacity={clamp((linea - i / 5) * 5)} />)}
          </svg>
        </div>
      </div>
    );
  } else if (tipo === 'tachado') {
    const q = easeInOut((t - t_tachar) / 0.38);
    const x = resorte((t - t_tachar - 0.3) / 0.45);
    cuerpo = (
      <div style={{ ...carta, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 * U }}>
        {kicker && <span style={{ ...chico, color: '#FF5A5F' }}>{kicker}</span>}
        <div style={{ position: 'relative', padding: `0 ${10 * U}px` }}>
          <span style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: (texto.length > 26 ? 44 : 54) * U, color: tinta, opacity: 1 - 0.45 * q, textAlign: 'center', display: 'block' }}>{texto}</span>
          <div style={{ position: 'absolute', left: -6 * U, top: '52%', height: 9 * U, width: `calc(${(q * 100).toFixed(2)}% + ${(12 * q * U).toFixed(1)}px)`,
                        borderRadius: 5 * U, background: '#FF3B4D', transform: 'rotate(-2deg)', transformOrigin: '0 50%',
                        boxShadow: `0 ${2 * U}px ${8 * U}px rgba(255,59,77,.45)`, opacity: q > 0 ? 1 : 0 }} />
          <Img src={staticFile('stickers/rcs_emoji_cross_mark.png')} style={{ position: 'absolute', right: -46 * U, top: -40 * U, width: 76 * U, height: 76 * U, opacity: clamp(x * 2),
                                                                             transform: `scale(${(0.3 + 0.7 * x).toFixed(3)}) rotate(${((1 - clamp(x)) * -40).toFixed(1)}deg)` }} />
        </div>
      </div>
    );
  } else if (tipo === 'lista') {
    const lista = (items || []).slice(0, 4);
    cuerpo = (
      <div style={{ ...carta, display: 'flex', flexDirection: 'column', gap: 22 * U }}>
        {kicker && <span style={chico}>{kicker}</span>}
        {lista.map((it, i) => {
          const t0 = Number(tiempos[i] ?? i * 0.6);
          const entra = easeOut((t - t0) / 0.35), marca = easeOut((t - t0 - 0.22) / 0.3), pop = resorte((t - t0 - 0.22) / 0.45);
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 26 * U, height: 76 * U }}>
              <div style={{ width: 70 * U, height: 70 * U, borderRadius: 20 * U, flex: 'none', boxSizing: 'border-box', position: 'relative',
                            border: `${4 * U}px solid ${marca > 0 ? `rgb(${r},${g},${b})` : gris}`, background: `rgba(${r},${g},${b},${marca.toFixed(3)})`,
                            transform: `scale(${(0.85 + 0.15 * clamp(pop, 0, 1.15)).toFixed(3)})` }}>
                <svg width="100%" height="100%" viewBox="0 0 24 24" style={{ position: 'absolute', inset: 0 }}>
                  <path d="M6 12.5 L10.2 16.5 L18 8" fill="none" stroke={oscuro ? '#141621' : '#fff'} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"
                        pathLength={1} strokeDasharray="1" strokeDashoffset={(1 - marca).toFixed(4)} />
                </svg>
              </div>
              {entra > 0 ? (
                <span style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 52 * U, color: tinta, opacity: entra,
                               transform: `translateX(${((1 - entra) * 30 * U).toFixed(1)}px)`, whiteSpace: 'nowrap' }}>{it}</span>
              ) : (
                <div style={{ width: (180 + 60 * (i % 2)) * U, height: 22 * U, borderRadius: 11 * U, background: suave }} />
              )}
            </div>
          );
        })}
      </div>
    );
  }
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: (x / 100) * W - ancho / 2, width: ancho, top: (y / 100) * H, display: 'flex', justifyContent: 'center', opacity: clamp(t / 0.18) * (1 - s),
                    transform: `translateY(${((1 - e) * 60 * U - s * 30 * U).toFixed(1)}px) scale(${(0.93 + 0.07 * clamp(e)).toFixed(4)})`,
                    filter: `blur(${((1 - clamp(e * 1.4)) * 10 + s * 8).toFixed(2)}px)` }}>
        <div style={{ transform: 'translateY(-50%)' }}>{cuerpo}</div>
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ la órbita (detrás / delante) */
// v5.20 (página Efectos › Gancho del inicio: 10 estilos; estilos_pro.py): `estilo` = rastro (el de siempre) · anillo · neon · chips · limpio ·
// cometa · doble · puntos · halo · cinta; `acento2` (el segundo color del halo) y `tinta` (el color del anillo) los puede poner el usuario.
export type OrbitaProps = { lado?: 'atras' | 'delante'; x?: number; y?: number; rx?: number; ry?: number; iconos?: string[]; vuelta?: number;
  inclinacion?: number; acento?: string; escala?: number; estilo?: string; acento2?: string; tinta?: string };

export const OrbitaT5: React.FC<OrbitaProps> = ({ lado = 'delante', x: cx = 50, y: cy = 30, rx = 30, ry = 5, iconos = [], vuelta = 2.8, inclinacion = -6,
                                                   acento = '#4C7DFF', escala = 1, estilo = 'rastro', acento2 = '#FF7A1A', tinta = '#FFFFFF' }) => {
  const { t, fin, W, H } = useTiempo();
  const U = (Math.min(W, H) / 1080) * escala;
  const [r, g, b] = rgb(acento);
  const [tr, tg, tb] = rgb(tinta);
  const X = (cx / 100) * W, Y = (cy / 100) * H, RX = (rx / 100) * W, RY = (ry / 100) * H;
  const inc = (inclinacion * Math.PI) / 180;
  const punto = (th: number) => {
    const x = RX * Math.cos(th), yy = RY * Math.sin(th);
    return [X + x * Math.cos(inc) - yy * Math.sin(inc), Y + x * Math.sin(inc) + yy * Math.cos(inc)];
  };
  const atras = lado === 'atras';
  const entra = easeOut(t / 0.5), sale = easeOut((t - (fin - 0.4)) / 0.4);
  // el rastro: la mitad de la elipse de este lado (atrás = la de arriba, sin θ < 0), que se dibuja al empezar
  const pasos = 48;
  const ruta = Array.from({ length: pasos + 1 }, (_, i) => punto((atras ? Math.PI : 0) + (Math.PI * i) / pasos))
    .map(([x, yy], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${yy.toFixed(1)}`).join(' ');
  const lista = (iconos.length ? iconos : ['3d:star-dynamic-color']).slice(0, 2);
  const th0 = Math.PI * 0.62;                                                 // empieza a la izquierda, un poco por delante
  const dibuja = (1 - entra).toFixed(4);
  const anillo = (d: string, k: string) => {                                  // el trazo de la órbita según el estilo
    if (estilo === 'limpio' || estilo === 'chips' || estilo === 'cometa') return null;
    if (estilo === 'anillo') return <path key={k} d={d} fill="none" stroke={`rgba(${tr},${tg},${tb},.9)`} strokeWidth={3 * U} strokeLinecap="round" pathLength={1} strokeDasharray="1" strokeDashoffset={dibuja} />;
    if (estilo === 'neon') return (
      <g key={k}>
        <path d={d} fill="none" stroke={`rgb(${r},${g},${b})`} strokeWidth={14 * U} strokeLinecap="round" opacity={0.55} pathLength={1} strokeDasharray="1" strokeDashoffset={dibuja} style={{ filter: `blur(${10 * U}px)` }} />
        <path d={d} fill="none" stroke={`rgb(${r},${g},${b})`} strokeWidth={4.5 * U} strokeLinecap="round" pathLength={1} strokeDasharray="1" strokeDashoffset={dibuja} />
        <path d={d} fill="none" stroke="rgba(255,255,255,.85)" strokeWidth={1.6 * U} strokeLinecap="round" pathLength={1} strokeDasharray="1" strokeDashoffset={dibuja} />
      </g>
    );
    if (estilo === 'puntos') return <path key={k} d={d} fill="none" stroke={`rgba(${tr},${tg},${tb},.95)`} strokeWidth={8 * U} strokeLinecap="round" strokeDasharray={`0 ${20 * U}`} strokeDashoffset={-t * 40 * U} opacity={entra} />;
    if (estilo === 'halo') return (
      <g key={k}>
        <defs><linearGradient id={`og${k}`} x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor={acento2} /><stop offset="1" stopColor={acento} /></linearGradient></defs>
        <path d={d} fill="none" stroke={`url(#og${k})`} strokeWidth={16 * U} strokeLinecap="round" opacity={0.5} pathLength={1} strokeDasharray="1" strokeDashoffset={dibuja} style={{ filter: `blur(${12 * U}px)` }} />
        <path d={d} fill="none" stroke={`url(#og${k})`} strokeWidth={5 * U} strokeLinecap="round" pathLength={1} strokeDasharray="1" strokeDashoffset={dibuja} />
      </g>
    );
    if (estilo === 'cinta') return (
      <g key={k}>
        <path d={d} fill="none" stroke={`rgba(${tr},${tg},${tb},.16)`} strokeWidth={42 * U} strokeLinecap="round" pathLength={1} strokeDasharray="1" strokeDashoffset={dibuja} />
        <path d={d} fill="none" stroke={`rgba(${tr},${tg},${tb},.7)`} strokeWidth={2 * U} strokeLinecap="round" pathLength={1} strokeDasharray="1" strokeDashoffset={dibuja} />
      </g>
    );
    return (                                                                    // 'rastro' (y 'doble'): el de siempre
      <g key={k}>
        <path d={d} fill="none" stroke={`rgba(${r},${g},${b},.35)`} strokeWidth={12 * U} strokeLinecap="round" pathLength={1} strokeDasharray="1"
              strokeDashoffset={dibuja} style={{ filter: `blur(${6 * U}px)` }} />
        <path d={d} fill="none" stroke={`rgba(${tr},${tg},${tb},.85)`} strokeWidth={3.5 * U} strokeLinecap="round" strokeDasharray={`${14 * U} ${12 * U}`}
              strokeDashoffset={-t * 60 * U} opacity={entra} />
      </g>
    );
  };
  const ruta2 = estilo === 'doble' ? Array.from({ length: pasos + 1 }, (_, i) => {           // la segunda órbita, más ancha y con otra inclinación
    const th = (atras ? Math.PI : 0) + (Math.PI * i) / pasos, inc2 = inc + 0.2;
    const x = RX * 1.22 * Math.cos(th), yy = RY * 1.5 * Math.sin(th);
    return [X + x * Math.cos(inc2) - yy * Math.sin(inc2), Y + x * Math.sin(inc2) + yy * Math.cos(inc2)];
  }).map(([x, yy], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${yy.toFixed(1)}`).join(' ') : '';
  const nFantasmas = estilo === 'cometa' ? [0.04, 0.08, 0.12, 0.16, 0.2] : estilo === 'limpio' || estilo === 'chips' ? [] : [0.08, 0.16];
  return (
    <AbsoluteFill style={{ opacity: 1 - sale }}>
      <svg width={W} height={H} style={{ position: 'absolute', inset: 0 }}>
        {anillo(ruta, 'a')}
        {ruta2 && <path d={ruta2} fill="none" stroke={`rgba(${tr},${tg},${tb},.55)`} strokeWidth={2 * U} strokeLinecap="round" pathLength={1} strokeDasharray="1" strokeDashoffset={dibuja} />}
      </svg>
      {lista.map((ic, i) => {
        const th = th0 + (2 * Math.PI * Math.max(0, t - 0.1)) / vuelta + i * Math.PI;
        const detras = Math.sin(th) < 0;
        if (detras !== atras) return null;
        const prof = 0.72 + 0.28 * (Math.sin(th) + 1) / 2;                        // delante, más grande
        const pop = resorte((t - 0.08 - i * 0.18) / 0.5);
        const lado2 = 160 * U * prof * clamp(pop, 0, 1.15);
        const [x, yy] = punto(th);
        const fantasmas = nFantasmas.map(d => punto(th - (2 * Math.PI * d) / vuelta));
        return (
          <div key={i}>
            {estilo === 'chips' && (
              <div style={{ position: 'absolute', left: x - lado2 * 0.62, top: yy - lado2 * 0.62, width: lado2 * 1.24, height: lado2 * 1.24, borderRadius: '50%',
                            background: 'linear-gradient(160deg, rgba(255,255,255,.3), rgba(255,255,255,.08))', border: `${2 * U}px solid rgba(255,255,255,.5)`,
                            boxShadow: `0 ${14 * U}px ${30 * U}px rgba(0,0,0,.35), 0 0 ${24 * U}px rgba(${r},${g},${b},.45)` }} />
            )}
            {fantasmas.map(([fx, fy], k) => (
              <Img key={k} src={urlIcono(ic)} style={{ position: 'absolute', left: fx - lado2 / 2, top: fy - lado2 / 2, width: lado2, height: lado2,
                                                       opacity: estilo === 'cometa' ? 0.32 - k * 0.06 : 0.22 - k * 0.1, filter: `blur(${(4 + 4 * k) * U}px)` }} />
            ))}
            {ic.startsWith('emoji:') ? (
              <EmojiAnimado id={ic} lado={lado2} style={{ position: 'absolute', left: x - lado2 / 2, top: yy - lado2 / 2, transform: `rotate(${(Math.cos(th) * 12).toFixed(1)}deg)`,
                                                        filter: `drop-shadow(0 ${14 * U}px ${18 * U}px rgba(0,0,0,.4)) brightness(${(0.8 + 0.2 * prof).toFixed(3)})` }} />
            ) : (
              <Img src={urlIcono(ic)} style={{ position: 'absolute', left: x - lado2 / 2, top: yy - lado2 / 2, width: lado2, height: lado2,
                                               transform: `rotate(${(Math.cos(th) * 12).toFixed(1)}deg)`,
                                               filter: `drop-shadow(0 ${14 * U}px ${18 * U}px rgba(0,0,0,.4)) brightness(${(0.8 + 0.2 * prof).toFixed(3)})` }} />
            )}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ el sticker (imagen congelada) */
export type StickerProps = { fondo?: string; recorte?: string; caja?: number[]; zoom?: number; acento?: string; giro?: number };

export const StickerT5: React.FC<StickerProps> = ({ fondo = '', recorte = '', caja = [0.25, 0.2, 0.75, 1], zoom = 1, acento = '#4C7DFF', giro = -4 }) => {
  const { t, fin, W, H } = useTiempo();
  const U = Math.min(W, H) / 1080;
  const [r, g, b] = rgb(acento);
  const q = resorte((t - 0.08) / 0.6), k = clamp(q, 0, 1.1);
  const apaga = easeOut((t - 0.05) / 0.4);
  const flash = Math.max(0, 1 - Math.abs(t - 0.05) / 0.16) * 0.55 + Math.max(0, 1 - Math.abs(t - fin) / 0.14) * 0.45;
  const [x0, y0, x1, y1] = caja;
  const borde = 9 * U * clamp(q * 1.4);
  const halo = [[1, 0], [-1, 0], [0, 1], [0, -1], [0.7, 0.7], [-0.7, 0.7], [0.7, -0.7], [-0.7, -0.7]]
    .map(([dx, dy]) => `drop-shadow(${(dx * borde).toFixed(1)}px ${(dy * borde).toFixed(1)}px 0 #fff)`).join(' ');
  return (
    <AbsoluteFill style={{ background: '#000', overflow: 'hidden' }}>
      {fondo && <Img src={fondo} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'fill',     // ya viene en el encuadre del timeline
                                          transform: `scale(${(zoom * (1 + 0.06 * apaga)).toFixed(4)})`,
                                          filter: `blur(${(16 * U * apaga).toFixed(1)}px) brightness(${(1 - 0.55 * apaga).toFixed(3)}) saturate(${(1 - 0.85 * apaga).toFixed(3)})` }} />}
      <AbsoluteFill style={{ background: `radial-gradient(60% 45% at 50% 55%, rgba(${r},${g},${b},${(0.22 * apaga).toFixed(3)}), rgba(0,0,0,0) 70%)` }} />
      {recorte && (
        <div style={{ position: 'absolute', left: x0 * W, top: y0 * H, width: (x1 - x0) * W, height: (y1 - y0) * H, transformOrigin: '50% 70%',
                      transform: `translateY(${(-0.03 * H * k).toFixed(1)}px) scale(${(zoom * (1 + 0.12 * k)).toFixed(4)}) rotate(${(giro * k).toFixed(2)}deg)` }}>
          <Img src={recorte} style={{ width: '100%', height: '100%', objectFit: 'fill',
                                      filter: `${halo} drop-shadow(0 ${(22 * U * k).toFixed(1)}px ${(34 * U).toFixed(1)}px rgba(0,0,0,${(0.55 * clamp(k)).toFixed(3)}))` }} />
        </div>
      )}
      <AbsoluteFill style={{ background: '#fff', opacity: flash }} />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ la pantalla final */
export type FinalProps = { fondo?: string; cara?: string; usuario?: string; titulo?: string; boton?: string; hecho?: string; acento?: string };

export const FinalT5: React.FC<FinalProps> = ({ fondo = '', cara = '', usuario = '', titulo = '', boton = 'Seguir', hecho = 'Siguiendo', acento = '#4C7DFF' }) => {
  useFuentes();
  const { t, fin, W, H } = useTiempo();
  const U = Math.min(W, H) / 1080;
  const [r, g, b] = rgb(acento);
  const vertical = H > W;
  const entra = easeOut(t / 0.45), sale = easeOut((t - (fin - 0.3)) / 0.3);
  const av = resorte((t - 0.1) / 0.6), anillo = easeInOut((t - 0.2) / 0.8);
  const clicT = Math.min(1.25, Math.max(0.8, fin - 1.1));
  const clic = clamp((t - clicT) / 0.18), pulsado = t > clicT + 0.08;
  const cursor = easeOut((t - (clicT - 0.55)) / 0.5);
  const lado = (vertical ? 420 : 300) * U;
  const cyA = H * (vertical ? 0.36 : 0.34);
  const chispas = Array.from({ length: 10 }, (_, i) => i);
  return (
    <AbsoluteFill style={{ background: '#05060A', opacity: 1 - sale }}>
      {fondo && <Img src={fondo} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', transform: 'scale(1.12)',
                                          filter: `blur(${(28 * U).toFixed(1)}px) brightness(${(1 - 0.6 * entra).toFixed(3)}) saturate(0.8)` }} />}
      <AbsoluteFill style={{ background: `radial-gradient(55% 40% at 50% 38%, rgba(${r},${g},${b},${(0.28 * entra).toFixed(3)}), rgba(0,0,0,0) 70%)` }} />
      <div style={{ position: 'absolute', left: W / 2 - lado / 2, top: cyA - lado / 2, width: lado, height: lado, transform: `scale(${clamp(av, 0, 1.12).toFixed(4)})` }}>
        <svg width={lado} height={lado} viewBox="0 0 100 100" style={{ position: 'absolute', inset: 0, overflow: 'visible' }}>
          <circle cx="50" cy="50" r="53" fill="none" stroke={acento} strokeWidth="3.2" pathLength={1} strokeDasharray="1" strokeDashoffset={(1 - anillo).toFixed(4)}
                  transform="rotate(-90 50 50)" style={{ filter: `drop-shadow(0 0 ${(10 * U).toFixed(1)}px rgba(${r},${g},${b},.9))` }} />
          {t > 1.0 && <circle cx="50" cy="50" r={53 + 14 * (((t - 1.0) % 1.4) / 1.4)} fill="none" stroke={acento} strokeWidth="1.4" opacity={1 - ((t - 1.0) % 1.4) / 1.4} />}
        </svg>
        {cara && <Img src={cara} style={{ position: 'absolute', inset: lado * 0.035, width: lado * 0.93, height: lado * 0.93, borderRadius: '50%', objectFit: 'cover',
                                          boxShadow: `0 ${20 * U}px ${50 * U}px rgba(0,0,0,.5)` }} />}
      </div>
      <div style={{ position: 'absolute', left: 0, width: W, top: cyA + lado * 0.62, textAlign: 'center', opacity: clamp((t - 0.35) / 0.3),
                    transform: `translateY(${((1 - easeOut((t - 0.35) / 0.5)) * 30 * U).toFixed(1)}px)` }}>
        {(usuario || titulo) && <div style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 70 * U, color: '#fff', letterSpacing: '-0.01em' }}>{usuario || titulo}</div>}
        {usuario && titulo && <div style={{ fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 40 * U, color: 'rgba(255,255,255,.7)', marginTop: 8 * U }}>{titulo}</div>}
      </div>
      <div style={{ position: 'absolute', left: W / 2, top: cyA + lado * 0.62 + (usuario && titulo ? 215 : 150) * U, transform: `translateX(-50%) scale(${(clamp(resorte((t - 0.55) / 0.5), 0, 1.1) * (1 - 0.08 * Math.sin(clic * Math.PI))).toFixed(4)})` }}>
        <div style={{ padding: `${28 * U}px ${84 * U}px`, borderRadius: 999, fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 54 * U, whiteSpace: 'nowrap',
                      background: pulsado ? 'rgba(255,255,255,.14)' : `rgb(${r},${g},${b})`, color: pulsado ? '#fff' : '#0E1016',
                      boxShadow: pulsado ? 'none' : `0 ${14 * U}px ${40 * U}px rgba(${r},${g},${b},.45)` }}>
          {pulsado ? `${hecho} ✓` : boton}
        </div>
        {chispas.map(i => {
          const a = (i / chispas.length) * Math.PI * 2, d = easeOut((t - clicT - 0.05) / 0.5);
          return t > clicT ? <div key={i} style={{ position: 'absolute', left: '50%', top: '50%', width: 12 * U, height: 12 * U, borderRadius: '50%', background: acento,
                                                   opacity: 1 - d, transform: `translate(${(Math.cos(a) * 220 * U * d - 6 * U).toFixed(1)}px, ${(Math.sin(a) * 90 * U * d - 6 * U).toFixed(1)}px)` }} /> : null;
        })}
        <div style={{ position: 'absolute', left: `calc(55% + ${((1 - cursor) * 240 * U).toFixed(1)}px)`, top: `calc(45% + ${((1 - cursor) * 180 * U).toFixed(1)}px)`,
                      opacity: clamp((t - (clicT - 0.55)) / 0.2) * (1 - clamp((t - clicT - 0.6) / 0.3)) }}>
          <Cursor U={U} clic={clic} />
        </div>
      </div>
    </AbsoluteFill>
  );
};
