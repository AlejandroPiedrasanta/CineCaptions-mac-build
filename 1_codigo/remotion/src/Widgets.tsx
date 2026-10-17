// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/Widgets.tsx — v5.5.9 los WIDGETS de «Motions completo» (referencias del usuario: los reels del minuto 3:04–3:22 de
// «ChatGPT vs Claude Motion Graphics» y sus capturas de Tidio, «Smart Navigation» y el panel de reservas). Estilo «Apple»: blanco limpio (o
// oscuro), tarjetas redondeadas con sombra suave, tipografía nítida, un acento; cada cosa entra con un resorte con un poco de rebote y una sola
// acción a la vez. Arriba, el TITULAR de lo que se dice, palabra a palabra cuando se dice, con la palabra clave en cursiva serif del acento.
//   Titular · OrbitaMC (iconos en órbita alrededor de la idea) · RutaMC (tarjeta con puntos de control y la ruta que se dibuja)
//   ConectoresMC (entradas → tarjeta de interruptores → resultado con ✓) · ContadorMC (anillo que se llena y el número que sube)
//   VersionesMC (cartas A/B/C en abanico; el cursor elige una) · Cursor (flecha que viaja en arco y hace clic con una onda)
import React from 'react';
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { FAMILIA, clamp, rgb, useResorte } from './comun';
import { EmojiAnimado } from './Emoji';

export type Ic = { emoji?: string; img?: string };
export type Cosa = { texto: string; icono?: Ic };
export type PalabraT = { t: number; texto: string; clave?: boolean };

const easeOut = (q: number) => 1 - Math.pow(1 - clamp(q), 3);
const suave = (q: number) => { const x = clamp(q); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };

export type Tema = { claro: boolean; tarjeta: string; tinta: string; suave: string; linea: string; sombra: string; borde: string };
export const tema = (claro: boolean): Tema => claro
  ? { claro, tarjeta: '#FFFFFF', tinta: '#111318', suave: '#8A8F9C', linea: 'rgba(20,30,60,.13)', sombra: '0 30px 80px rgba(40,50,100,.16), 0 6px 18px rgba(40,50,100,.08)', borde: 'rgba(20,30,60,.06)' }
  : { claro, tarjeta: 'rgba(255,255,255,.07)', tinta: '#F5F6FA', suave: 'rgba(255,255,255,.55)', linea: 'rgba(255,255,255,.16)', sombra: '0 30px 80px rgba(0,0,0,.55)', borde: 'rgba(255,255,255,.14)' };

const useUni = () => { const { width, height } = useVideoConfig(); return Math.min(width, height) / 1080; };

export const IconoW: React.FC<{ ic?: Ic; lado: number; style?: React.CSSProperties }> = ({ ic, lado, style }) => {
  if (!ic) return null;
  if (ic.emoji) return <EmojiAnimado id={ic.emoji} lado={lado} style={style} />;
  if (ic.img) return <Img src={staticFile(ic.img)} style={{ width: lado, height: lado, objectFit: 'contain', ...style }} />;
  return null;
};

/* ------------------------------------------------------------------------------------------------ el titular, palabra a palabra */
export const Titular: React.FC<{ palabras: PalabraT[]; acento: string; T: Tema; top: number }> = ({ palabras, acento, T, top }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const U = useUni();
  const t = frame / fps;
  const ps = palabras.slice(0, 7);
  const largo = ps.reduce((n, p) => n + p.texto.length + 1, 0);
  const tam = Math.max(74, Math.min(124, (width / U) * 2.1 / Math.max(8, largo))) * U;
  return (
    <div style={{ position: 'absolute', top, left: 0, right: 0, display: 'flex', flexWrap: 'wrap', justifyContent: 'center', alignItems: 'baseline',
                  padding: `0 ${70 * U}px`, rowGap: 6 * U }}>
      {ps.map((p, i) => {
        const q = easeOut((t - p.t + 0.06) / 0.3);
        const clave = !!p.clave;
        return (
          <span key={i} style={{ display: 'inline-block', margin: `0 ${tam * 0.14}px`, opacity: clamp(q * 1.3), transform: `translateY(${((1 - q) * tam * 0.35).toFixed(1)}px)`,
                                 filter: q < 1 ? `blur(${((1 - q) * 8).toFixed(1)}px)` : 'none', position: 'relative',
                                 fontFamily: clave ? FAMILIA.display : FAMILIA.inter, fontStyle: clave ? 'italic' : 'normal', fontWeight: clave ? 400 : 700,
                                 fontSize: clave ? tam * 1.12 : tam, color: clave ? acento : T.tinta, letterSpacing: clave ? '0' : '-0.025em', lineHeight: 1.12 }}>
            {p.texto}
            {clave && <span style={{ position: 'absolute', left: 0, bottom: -tam * 0.06, height: tam * 0.07, borderRadius: tam, background: acento, opacity: 0.35,
                                     width: `${(easeOut((t - p.t - 0.15) / 0.4) * 100).toFixed(1)}%` }} />}
          </span>
        );
      })}
    </div>
  );
};

/* ------------------------------------------------------------------------------------------------ el cursor */
export const Cursor: React.FC<{ desde: [number, number]; hasta: [number, number]; t0: number; t1: number; T: Tema; acento: string }> = ({ desde, hasta, t0, t1, T, acento }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const U = useUni();
  const t = frame / fps;
  if (t < t0 - 0.2) return null;
  const q = suave((t - t0) / Math.max(0.1, t1 - t0));
  const arco = Math.sin(Math.PI * q) * 90 * U;
  const x = desde[0] + (hasta[0] - desde[0]) * q, y = desde[1] + (hasta[1] - desde[1]) * q - arco;
  const clic = clamp((t - t1) / 0.35);
  const pres = t > t1 && t < t1 + 0.14 ? 0.86 : 1;
  return (
    <>
      {t > t1 && clic < 1 && (
        <div style={{ position: 'absolute', left: hasta[0] - 70 * U * clic, top: hasta[1] - 70 * U * clic, width: 140 * U * clic, height: 140 * U * clic, borderRadius: '50%',
                      border: `${4 * U}px solid ${acento}`, opacity: 1 - clic }} />
      )}
      <svg width={54 * U} height={64 * U} viewBox="0 0 27 32" style={{ position: 'absolute', left: x, top: y, transform: `scale(${pres})`, transformOrigin: '0 0',
                                                                          filter: 'drop-shadow(0 6px 10px rgba(0,0,0,.28))', opacity: clamp((t - t0 + 0.2) / 0.2) }}>
        <path d="M2 2 L2 25 L8.5 19 L13 29 L17 27 L12.6 17.4 L21.5 17.4 Z" fill={T.claro ? '#111318' : '#FFFFFF'} stroke={T.claro ? '#FFFFFF' : '#111318'} strokeWidth={1.6} strokeLinejoin="round" />
      </svg>
    </>
  );
};

/* ------------------------------------------------------------------------------------------------ órbita (Tidio) */
export const OrbitaMC: React.FC<{ centro: Cosa; items: Cosa[]; acento: string; T: Tema; cy: number }> = ({ centro, items, acento, T, cy }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const U = useUni();
  const t = frame / fps;
  const R = useResorte();
  const cx = width / 2;
  const r0 = R(0.05, { damping: 13, stiffness: 140 });
  const [ar, ag, ab] = rgb(acento);
  const anillos = [360, 490].map(r => r * U);
  const n = Math.min(6, items.length);
  return (
    <AbsoluteFill>
      {[0, 1, 2].map(k => {                                                 // ondas suaves que salen del centro
        const u = ((t * 0.45 + k / 3) % 1);
        return <div key={k} style={{ position: 'absolute', left: cx - 200 * U * (1 + u), top: cy - 200 * U * (1 + u), width: 400 * U * (1 + u), height: 400 * U * (1 + u),
                                     borderRadius: '50%', background: `radial-gradient(circle, rgba(${ar},${ag},${ab},${(0.1 * (1 - u)).toFixed(3)}) 40%, rgba(${ar},${ag},${ab},0) 70%)` }} />;
      })}
      {anillos.map((r, k) => (
        <div key={k} style={{ position: 'absolute', left: cx - r, top: cy - r, width: 2 * r, height: 2 * r, borderRadius: '50%', border: `${2 * U}px solid ${T.linea}`,
                              transform: `scale(${(0.6 + 0.4 * easeOut((t - 0.1 - k * 0.12) / 0.5)).toFixed(4)})`, opacity: easeOut((t - 0.1 - k * 0.12) / 0.4) }} />
      ))}
      <div style={{ position: 'absolute', left: cx - 175 * U, top: cy - 175 * U, width: 350 * U, height: 350 * U, borderRadius: '50%', background: T.tarjeta,
                    border: `${1.5 * U}px solid ${T.borde}`, boxShadow: T.sombra, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                    transform: `scale(${Math.max(0.001, r0).toFixed(4)})`, backdropFilter: T.claro ? undefined : 'blur(20px)' }}>
        {centro.icono && <IconoW ic={centro.icono} lado={130 * U} />}
        <div style={{ marginTop: 8 * U, fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: Math.min(54, 520 / Math.max(5, centro.texto.length)) * U, color: T.tinta,
                      letterSpacing: '-0.02em', textAlign: 'center', padding: `0 ${20 * U}px` }}>{centro.texto}</div>
      </div>
      {items.slice(0, n).map((it, i) => {
        const r = anillos[i % 2];
        const ang = -Math.PI / 2 + (i / n) * Math.PI * 2 + t * 0.12 * (i % 2 ? -1 : 1);
        const q = R(0.45 + i * 0.16, { damping: 11, stiffness: 160 });
        const x = cx + Math.cos(ang) * r, y = cy + Math.sin(ang) * r;
        const lado = 156 * U;
        return (
          <div key={i} style={{ position: 'absolute', left: x - lado / 2, top: y - lado / 2, width: lado, height: lado, transform: `scale(${Math.max(0.001, q).toFixed(4)})` }}>
            <div style={{ width: lado, height: lado, borderRadius: lado * 0.32, background: T.tarjeta, border: `${1.5 * U}px solid ${T.borde}`, boxShadow: T.sombra,
                          display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {it.icono ? <IconoW ic={it.icono} lado={lado * 0.6} /> : <div style={{ width: lado * 0.3, height: lado * 0.3, borderRadius: '50%', background: acento }} />}
            </div>
            {it.texto && <div style={{ position: 'absolute', top: lado + 10 * U, left: -lado * 0.6, width: lado * 2.2, textAlign: 'center', fontFamily: FAMILIA.inter, fontWeight: 700,
                                        fontSize: 36 * U, color: T.suave, whiteSpace: 'nowrap', opacity: clamp((q - 0.6) * 3) }}>{it.texto}</div>}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ ruta (Smart Navigation) */
export const RutaMC: React.FC<{ pasos: Cosa[]; titulo: string; acento: string; T: Tema; cy: number }> = ({ pasos, titulo, acento, T, cy }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const U = useUni();
  const t = frame / fps;
  const R = useResorte();
  const w = Math.min(width * 0.84, 900 * U), h = 1000 * U;
  const x0 = (width - w) / 2, y0 = cy - h / 2;
  const entra = R(0.05, { damping: 15, stiffness: 120 });
  const mapaH = h * 0.66;
  const ps = pasos.slice(0, 3);
  // la ruta: una curva que sube por el mapa
  const pts = [[0.86, 1.05], [0.78, 0.7], [0.64, 0.52], [0.7, 0.28], [0.58, -0.05]].map(([a, b]) => [w * a, mapaH * b]);
  const d = `M ${pts[0][0]} ${pts[0][1]} C ${pts[1][0]} ${pts[1][1]}, ${pts[2][0]} ${pts[2][1]}, ${pts[2][0]} ${pts[2][1]} S ${pts[3][0]} ${pts[3][1]}, ${pts[4][0]} ${pts[4][1]}`;
  const q = suave((t - 0.45) / 1.6);
  const [ar, ag, ab] = rgb(acento);
  return (
    <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, borderRadius: 52 * U, background: T.tarjeta, boxShadow: T.sombra, border: `${1.5 * U}px solid ${T.borde}`,
                  overflow: 'hidden', transform: `translateY(${((1 - entra) * 160 * U).toFixed(1)}px) scale(${(0.92 + 0.08 * entra).toFixed(4)})`, opacity: clamp(entra * 1.5) }}>
      <svg width={w} height={mapaH} style={{ position: 'absolute', left: 0, top: 0 }}>
        {[0.2, 0.42, 0.63, 0.85].map((k, i) => <line key={'h' + i} x1={w * 0.42} y1={mapaH * k} x2={w} y2={mapaH * k - 40 * U} stroke={T.linea} strokeWidth={10 * U} />)}
        {[0.55, 0.75, 0.92].map((k, i) => <line key={'v' + i} x1={w * k} y1={0} x2={w * k + 30 * U} y2={mapaH} stroke={T.linea} strokeWidth={8 * U} />)}
        <path d={d} fill="none" stroke={`rgba(${ar},${ag},${ab},.25)`} strokeWidth={46 * U} strokeLinecap="round" pathLength={1} strokeDasharray="1" strokeDashoffset={(1 - q).toFixed(4)}
              style={{ filter: `blur(${10 * U}px)` }} />
        <path d={d} fill="none" stroke={acento} strokeWidth={22 * U} strokeLinecap="round" pathLength={1} strokeDasharray="1" strokeDashoffset={(1 - q).toFixed(4)} />
      </svg>
      {/* los puntos de control, con su línea punteada */}
      <div style={{ position: 'absolute', left: 50 * U, top: 50 * U, width: w * 0.5 }}>
        {ps.map((p, i) => {
          const qi = R(0.3 + i * 0.35, { damping: 12, stiffness: 170 });
          const activo = q > (i + 0.5) / ps.length;
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 22 * U, height: mapaH / 3.2, opacity: clamp(qi * 1.5), transform: `translateX(${((1 - qi) * -40 * U).toFixed(1)}px)` }}>
              <div style={{ position: 'relative', width: 56 * U, height: 56 * U, borderRadius: '50%', border: `${6 * U}px solid rgba(${ar},${ag},${ab},.25)`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{ width: 28 * U, height: 28 * U, borderRadius: '50%', background: activo ? acento : T.tarjeta, border: `${4 * U}px solid ${acento}` }} />
                {i < ps.length - 1 && <div style={{ position: 'absolute', top: 56 * U, left: 25 * U, width: 0, height: mapaH / 3.2 - 56 * U, borderLeft: `${3 * U}px dashed rgba(${ar},${ag},${ab},.55)` }} />}
              </div>
              <div style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 40 * U, color: T.tinta, whiteSpace: 'nowrap' }}>{p.texto}</div>
            </div>
          );
        })}
      </div>
      <div style={{ position: 'absolute', left: 56 * U, right: 56 * U, top: mapaH + 50 * U }}>
        <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 64 * U, color: T.tinta, letterSpacing: '-0.025em', opacity: easeOut((t - 0.8) / 0.4) }}>{titulo}</div>
        <div style={{ marginTop: 18 * U, height: 14 * U, width: '62%', borderRadius: 8 * U, background: T.linea, opacity: easeOut((t - 1.0) / 0.4) }} />
        <div style={{ marginTop: 14 * U, height: 14 * U, width: '44%', borderRadius: 8 * U, background: T.linea, opacity: easeOut((t - 1.1) / 0.4) }} />
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------------------------------------ conectores (panel de reservas) */
export const ConectoresMC: React.FC<{ entradas: Cosa[]; opciones: Cosa[]; resultado: Cosa; acento: string; T: Tema; cy: number }> = ({ entradas, opciones, resultado, acento, T, cy }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const U = useUni();
  const t = frame / fps;
  const R = useResorte();
  const ops = opciones.slice(0, 4), ens = entradas.slice(0, 3);
  const cw = 560 * U, fila = 104 * U, ch = ops.length * fila + 40 * U;
  const cx = width / 2 - cw / 2 + 20 * U, top = cy - ch / 2;
  const ix = cx - 230 * U, lado = 150 * U;
  const ox = cx + cw + 70 * U;
  const linea = (x1: number, y1: number, x2: number, y2: number, q: number, k: string) => (
    <path key={k} d={`M ${x1} ${y1} C ${(x1 + x2) / 2} ${y1}, ${(x1 + x2) / 2} ${y2}, ${x2} ${y2}`} fill="none" stroke={T.linea} strokeWidth={5 * U} strokeLinecap="round"
          pathLength={1} strokeDasharray="1" strokeDashoffset={(1 - clamp(q)).toFixed(4)} />
  );
  const fin = 0.7 + ops.length * 0.42;
  const qr = R(fin + 0.25, { damping: 11, stiffness: 160 });
  const yRes = cy;
  return (
    <AbsoluteFill>
      <svg width={width} height={cy * 2 + 400 * U} style={{ position: 'absolute', left: 0, top: 0 }}>
        {ens.map((_, i) => {
          const y = cy + (i - (ens.length - 1) / 2) * (lado + 34 * U);
          return linea(ix + lado, y, cx, cy, easeOut((t - 0.35 - i * 0.1) / 0.5), 'e' + i);
        })}
        {linea(cx + cw, cy, ox, yRes, easeOut((t - fin) / 0.4), 'r')}
      </svg>
      {ens.map((e, i) => {
        const y = cy + (i - (ens.length - 1) / 2) * (lado + 34 * U);
        const q = R(0.1 + i * 0.12, { damping: 12, stiffness: 160 });
        return (
          <div key={i} style={{ position: 'absolute', left: ix, top: y - lado / 2, width: lado, height: lado, borderRadius: lado * 0.28, background: T.tarjeta, boxShadow: T.sombra,
                                border: `${1.5 * U}px solid ${T.borde}`, display: 'flex', alignItems: 'center', justifyContent: 'center', transform: `scale(${Math.max(0.001, q).toFixed(4)})` }}>
            <IconoW ic={e.icono} lado={lado * 0.58} />
          </div>
        );
      })}
      <div style={{ position: 'absolute', left: cx, top, width: cw, height: ch, borderRadius: 40 * U, background: T.tarjeta, boxShadow: T.sombra, border: `${1.5 * U}px solid ${T.borde}`,
                    padding: `${20 * U}px ${34 * U}px`, opacity: clamp(R(0.25, { damping: 15 }) * 1.4), transform: `scale(${(0.9 + 0.1 * R(0.25, { damping: 15 })).toFixed(4)})` }}>
        {ops.map((o, i) => {
          const on = clamp((t - (0.75 + i * 0.42)) / 0.18);
          return (
            <div key={i} style={{ height: fila, display: 'flex', alignItems: 'center', gap: 22 * U, borderBottom: i < ops.length - 1 ? `${1.5 * U}px solid ${T.linea}` : 'none' }}>
              {o.icono ? <IconoW ic={o.icono} lado={50 * U} /> : <div style={{ width: 22 * U, height: 22 * U, borderRadius: 6 * U, border: `${3 * U}px solid ${T.suave}` }} />}
              <div style={{ flex: 1, fontFamily: FAMILIA.inter, fontWeight: 600, fontSize: 40 * U, color: T.tinta, whiteSpace: 'nowrap', overflow: 'hidden' }}>{o.texto}</div>
              <div style={{ width: 96 * U, height: 54 * U, borderRadius: 27 * U, background: on > 0.5 ? acento : T.linea, position: 'relative', transition: 'none' }}>
                <div style={{ position: 'absolute', top: 6 * U, left: (6 + 42 * easeOut(on)) * U, width: 42 * U, height: 42 * U, borderRadius: '50%', background: '#FFFFFF',
                              boxShadow: '0 3px 8px rgba(0,0,0,.25)' }} />
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ position: 'absolute', left: ox, top: yRes - 56 * U, height: 112 * U, padding: `0 ${34 * U}px`, borderRadius: 56 * U, background: T.tarjeta, boxShadow: T.sombra,
                    border: `${1.5 * U}px solid ${T.borde}`, display: 'flex', alignItems: 'center', gap: 16 * U, transform: `scale(${Math.max(0.001, qr).toFixed(4)})`, transformOrigin: 'left center' }}>
        {resultado.icono && <IconoW ic={resultado.icono} lado={54 * U} />}
        <div style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 42 * U, color: T.tinta, whiteSpace: 'nowrap' }}>{resultado.texto}</div>
        <div style={{ position: 'absolute', top: -26 * U, right: 10 * U, width: 58 * U, height: 40 * U, borderRadius: 14 * U, background: '#2FCB6B', color: '#fff',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 30 * U, fontWeight: 900, fontFamily: FAMILIA.inter }}>✓</div>
      </div>
      <Cursor desde={[width * 0.8, cy + 520 * U]} hasta={[cx + cw - 70 * U, top + 20 * U + fila * 0.5]} t0={0.45} t1={0.75} T={T} acento={acento} />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ contador en anillo */
export const ContadorMC: React.FC<{ valor: number; sufijo?: string; prefijo?: string; etiqueta?: string; acento: string; T: Tema; cy: number }> =
  ({ valor, sufijo = '', prefijo = '', etiqueta = '', acento, T, cy }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const U = useUni();
  const t = frame / fps;
  const R = useResorte();
  const q = suave((t - 0.25) / 1.4);
  const r = 230 * U, grosor = 34 * U;
  const n = Math.round(valor * q);
  const entra = R(0.05, { damping: 13, stiffness: 140 });
  const [ar, ag, ab] = rgb(acento);
  const circ = 2 * Math.PI * r;
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: width / 2 - r - 60 * U, top: cy - r - 60 * U, width: 2 * r + 120 * U, height: 2 * r + 120 * U, borderRadius: '50%',
                    background: T.tarjeta, boxShadow: T.sombra, border: `${1.5 * U}px solid ${T.borde}`, transform: `scale(${Math.max(0.001, entra).toFixed(4)})` }}>
        <svg width={2 * r + 120 * U} height={2 * r + 120 * U} style={{ position: 'absolute', inset: 0, transform: 'rotate(-90deg)' }}>
          <circle cx={r + 60 * U} cy={r + 60 * U} r={r} fill="none" stroke={T.linea} strokeWidth={grosor} />
          <circle cx={r + 60 * U} cy={r + 60 * U} r={r} fill="none" stroke={acento} strokeWidth={grosor} strokeLinecap="round" strokeDasharray={circ}
                  strokeDashoffset={circ * (1 - 0.92 * q)} style={{ filter: `drop-shadow(0 0 ${14 * U}px rgba(${ar},${ag},${ab},.6))` }} />
        </svg>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: Math.min(150, 760 / Math.max(3, (prefijo + n + sufijo).length)) * U, color: T.tinta, letterSpacing: '-0.04em',
                        fontVariantNumeric: 'tabular-nums' }}>{prefijo}{n.toLocaleString('es')}{sufijo}</div>
          {etiqueta && <div style={{ marginTop: 6 * U, fontFamily: FAMILIA.inter, fontWeight: 600, fontSize: 38 * U, color: T.suave, opacity: easeOut((t - 0.6) / 0.4) }}>{etiqueta}</div>}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ versiones A/B/C */
export const VersionesMC: React.FC<{ cartas: Cosa[]; acento: string; T: Tema; cy: number }> = ({ cartas, acento, T, cy }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const U = useUni();
  const t = frame / fps;
  const R = useResorte();
  const cs = cartas.slice(0, 3);
  const w = 280 * U, h = 380 * U;
  const elegida = Math.min(1, cs.length - 1);
  const tClic = 1.35;
  const sel = R(tClic, { damping: 12, stiffness: 160 });
  const colores = ['#FF7A59', acento, '#111318'];
  return (
    <AbsoluteFill>
      {cs.map((c, i) => {
        const q = R(0.15 + i * 0.14, { damping: 12, stiffness: 150 });
        const k = i - (cs.length - 1) / 2;
        const esta = i === elegida;
        const ang = k * 9 * (1 - (t > tClic ? sel : 0) * (esta ? 1 : 0.4));
        const dx = k * (w * 0.78) * (1 + (t > tClic ? 0.15 * sel : 0));
        const s = (0.85 + 0.15 * q) * (t > tClic ? (esta ? 1 + 0.12 * sel : 1 - 0.1 * sel) : 1);
        const op = t > tClic && !esta ? 1 - 0.45 * sel : 1;
        return (
          <div key={i} style={{ position: 'absolute', left: width / 2 - w / 2 + dx, top: cy - h / 2 + (1 - q) * 160 * U - Math.abs(k) * 18 * U, width: w, height: h, borderRadius: 36 * U,
                                background: colores[i % 3], boxShadow: T.sombra, transform: `rotate(${ang.toFixed(2)}deg) scale(${s.toFixed(4)})`, opacity: clamp(q * 1.5) * op,
                                zIndex: esta ? 3 : 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#FFFFFF' }}>
            <div style={{ fontFamily: FAMILIA.inter, fontWeight: 900, fontSize: 170 * U, lineHeight: 1 }}>{String.fromCharCode(65 + i)}</div>
            <div style={{ marginTop: 18 * U, padding: `${8 * U}px ${22 * U}px`, borderRadius: 30 * U, background: 'rgba(255,255,255,.18)', fontFamily: FAMILIA.inter, fontWeight: 700,
                          fontSize: 34 * U, maxWidth: w - 30 * U, whiteSpace: 'nowrap', overflow: 'hidden' }}>{c.texto}</div>
            {esta && t > tClic && <div style={{ position: 'absolute', top: -24 * U, right: -24 * U, width: 70 * U, height: 70 * U, borderRadius: '50%', background: '#2FCB6B',
                                                 display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 40 * U, fontWeight: 900, transform: `scale(${sel.toFixed(4)})` }}>✓</div>}
          </div>
        );
      })}
      <Cursor desde={[width * 0.82, cy + 560 * U]} hasta={[width / 2 + 30 * U, cy + 40 * U]} t0={0.95} t1={tClic} T={T} acento={acento} />
    </AbsoluteFill>
  );
};
