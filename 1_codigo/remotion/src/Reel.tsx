// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/Reel.tsx — v5.5.9 el ESTILO REEL (el usuario: «agarra el minuto 3:03–3:22 con su audio y replícalo tal cual para todas mis
// animaciones; nada de muñecos ni imágenes de referencia: ese estilo»). Estudiado fotograma a fotograma: fondo lavanda claro, titular grande
// arriba (clave en cursiva serif azul, tachado rojo, gris apagado, recuadro de selección o píldora lavanda) y UNA tarjeta de interfaz que explica
// la frase, con un cursor morado que hace clic, estrellas doradas y resortes con rebote. Las tarjetas (cada una es una metáfora que sirve para
// cualquier video; los textos llegan por props):
//   RecW (grabar: visor azul REC)  RelojW (horas: reloj que corre)  ArchivosW (material: fotos que salen de la carpeta)  BuscarW (encontrar: clip
//   elegido)  CortarW (cortar: línea de tiempo y tijeras)  LargoW (largo/aburrido: reproductor gris)  MovilW (la gente lo entiende: móvil y
//   reacciones)  ChatW (lo que te dicen: mensaje)  VersionesW (versiones A/B/C)  IdeasW (ideas: nube que suelta iconos y contadores)
//   y, para cualquier tema: FechaW  LugarW  EntradaW  PersonasW  MusicaW  PremioW  CompartirW  AvisoW (la general)
import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion';
import { FAMILIA, clamp, useResorte } from './comun';
import { EmojiAnimado } from './Emoji';

export type PalabraR = { t: number; texto: string; estilo?: 'clave' | 'tachado' | 'gris' | 'caja' | 'pildora' | 'azul' };
// v5.5.9: el color de cada tarjeta es una variable CSS (--cc-azul, --cc-lila, --cc-lilaf) que pone MotionsCompleto por tarjeta (azul, naranja, morado,
// verde, rosa): la misma tarjeta no sale siempre igual. Sin variable, el azul y el lila del reel de referencia.
const AZUL = 'var(--cc-azul, #2F5BE7)', LILA = 'var(--cc-lila, #7B5CF5)', LILA_F = 'var(--cc-lilaf, #ECE8FF)', ROJO = '#F0473C', ORO = '#F7B731', TINTA = '#15161C', OSCURO = '#26283A';
const CURSOR = '#7B5CF5';
const easeOut = (q: number) => 1 - Math.pow(1 - clamp(q), 3);
const suave = (q: number) => { const x = clamp(q); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const useT = () => { const f = useCurrentFrame(); const { fps } = useVideoConfig(); return f / fps; };
const useU = () => { const { width, height } = useVideoConfig(); return Math.min(width, height) / 1080; };
const SOMBRA = (U: number) => `0 ${34 * U}px ${80 * U}px rgba(60,60,130,.18), 0 ${6 * U}px ${16 * U}px rgba(60,60,130,.08)`;

/* ------------------------------------------------------------------------------------------------ piezas comunes */
export const Estrella: React.FC<{ x: number; y: number; lado: number; t0: number }> = ({ x, y, lado, t0 }) => {
  const t = useT();
  const q = useResorte()(t0, { damping: 9, stiffness: 180 });
  const brillo = 0.85 + 0.15 * Math.sin(t * 4 + x);
  return (
    <svg width={lado} height={lado} viewBox="0 0 24 24" style={{ position: 'absolute', left: x - lado / 2, top: y - lado / 2, transform: `scale(${Math.max(0, q) * brillo}) rotate(${(t * 20) % 360}deg)` }}>
      <path d="M12 1 L14.6 9.4 L23 12 L14.6 14.6 L12 23 L9.4 14.6 L1 12 L9.4 9.4 Z" fill={ORO} stroke="#FFFFFF" strokeWidth={1.6} strokeLinejoin="round" />
    </svg>
  );
};

/* el cursor morado de las referencias: llega en arco y hace clic (se encoge y suelta una onda) */
export const CursorR: React.FC<{ desde: [number, number]; hasta: [number, number]; t0: number; t1: number; onda?: boolean }> = ({ desde, hasta, t0, t1, onda = true }) => {
  const t = useT();
  const U = useU();
  if (t < t0 - 0.05) return null;
  const q = suave((t - t0) / Math.max(0.1, t1 - t0));
  const arco = Math.sin(Math.PI * q) * 70 * U;
  const x = desde[0] + (hasta[0] - desde[0]) * q, y = desde[1] + (hasta[1] - desde[1]) * q - arco;
  const c = clamp((t - t1) / 0.45);
  const pres = t > t1 && t < t1 + 0.12 ? 0.82 : 1;
  return (
    <>
      {onda && t > t1 && c < 1 && <div style={{ position: 'absolute', left: hasta[0] - 80 * U * c, top: hasta[1] - 80 * U * c, width: 160 * U * c, height: 160 * U * c,
                                                borderRadius: '50%', border: `${5 * U}px solid rgba(123,92,245,${(0.6 * (1 - c)).toFixed(3)})`, background: `rgba(123,92,245,${(0.12 * (1 - c)).toFixed(3)})` }} />}
      <svg width={58 * U} height={58 * U} viewBox="0 0 24 24" style={{ position: 'absolute', left: x - 6 * U, top: y - 4 * U, transform: `scale(${pres}) rotate(-8deg)`, transformOrigin: '20% 15%',
                                                                     filter: 'drop-shadow(0 6px 10px rgba(70,40,160,.35))', opacity: clamp((t - t0 + 0.05) / 0.15) }}>
        <path d="M3 2 L21 10.5 L13.2 12.8 L10 21 Z" fill={CURSOR} stroke="#FFFFFF" strokeWidth={1.8} strokeLinejoin="round" />
      </svg>
    </>
  );
};

const Pastilla: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => {
  const U = useU();
  return <div style={{ display: 'inline-flex', alignItems: 'center', gap: 14 * U, padding: `${14 * U}px ${30 * U}px`, borderRadius: 999, background: '#FFFFFF',
                       boxShadow: SOMBRA(U), fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 40 * U, color: TINTA, ...style }}>{children}</div>;
};

/* ------------------------------------------------------------------------------------------------ el titular de las referencias */
export const RTitular: React.FC<{ palabras: PalabraR[]; arriba?: string; top: number; claro?: boolean }> = ({ palabras, arriba, top, claro = true }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const largo = palabras.reduce((n, p) => n + p.texto.length + 1, 0);
  const tam = Math.max(92, Math.min(132, (width / U) * 2.6 / Math.max(10, largo))) * U;
  const qa = R(0.0, { damping: 13, stiffness: 160 });
  return (
    <div style={{ position: 'absolute', top, left: 0, right: 0, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      {arriba && (
        <div style={{ marginBottom: 26 * U, transform: `scale(${Math.max(0, qa).toFixed(4)})` }}>
          <Pastilla style={{ background: LILA_F, color: LILA, border: `${3 * U}px solid #D7CEFF`, fontSize: 60 * U, padding: `${18 * U}px ${40 * U}px` }}>{arriba}</Pastilla>
        </div>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', alignItems: 'baseline', padding: `0 ${70 * U}px`, rowGap: 4 * U, maxWidth: width }}>
        {palabras.map((p, i) => {
          const q = easeOut((t - p.t + 0.05) / 0.3);
          const e = p.estilo;
          const base: React.CSSProperties = {
            display: 'inline-block', margin: `0 ${tam * 0.13}px`, position: 'relative', lineHeight: 1.1, fontSize: tam,
            fontFamily: FAMILIA.inter, fontWeight: 800, color: claro ? TINTA : '#FFFFFF', letterSpacing: '-0.03em',
            opacity: clamp(q * 1.3), transform: `translateY(${((1 - q) * tam * 0.3).toFixed(1)}px)`, filter: q < 1 ? `blur(${((1 - q) * 9).toFixed(1)}px)` : undefined,
          };
          const azul = claro ? AZUL : 'var(--cc-azul-claro, #9DB4FF)';           // (v5.20: con un color fijo de Efectos, el suyo)
          if (e === 'clave') Object.assign(base, { fontFamily: FAMILIA.display, fontStyle: 'italic', fontWeight: 400, color: azul, fontSize: tam * 1.1, letterSpacing: '0' });
          if (e === 'azul') Object.assign(base, { color: azul });
          if (e === 'gris') Object.assign(base, { color: '#9A9CA8', fontWeight: 600, opacity: clamp(q * 1.3) * (0.55 + 0.45 * (1 - easeOut((t - p.t - 0.5) / 0.6))) });
          if (e === 'pildora') Object.assign(base, { color: LILA, background: LILA_F, borderRadius: 999, padding: `${2 * U}px ${tam * 0.22}px`, border: `${3 * U}px solid #D7CEFF` });
          const tacha = easeOut((t - p.t - 0.35) / 0.3);
          const caja = easeOut((t - p.t + 0.05) / 0.3);
          return (
            <span key={i} style={base}>
              {p.texto}
              {e === 'tachado' && <span style={{ position: 'absolute', left: -4 * U, top: '52%', height: 9 * U, borderRadius: 5 * U, background: ROJO, width: `calc(${(tacha * 100).toFixed(1)}% + ${8 * U}px)` }} />}
              {e === 'caja' && (
                <span style={{ position: 'absolute', left: -14 * U, right: -14 * U, top: -6 * U, bottom: -10 * U, border: `${3 * U}px solid ${AZUL}`, borderRadius: 6 * U,
                               background: 'rgba(47,91,231,.08)', opacity: caja, transform: `scale(${(0.9 + 0.1 * caja).toFixed(4)})` }}>
                  {[[0, 0], [1, 0], [0, 1], [1, 1]].map(([a, b], k) => (
                    <span key={k} style={{ position: 'absolute', left: `calc(${a * 100}% - ${8 * U}px)`, top: `calc(${b * 100}% - ${8 * U}px)`, width: 14 * U, height: 14 * U,
                                           background: '#FFFFFF', border: `${3 * U}px solid ${AZUL}`, borderRadius: 3 * U }} />
                  ))}
                </span>
              )}
            </span>
          );
        })}
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------------------------------------ 1. grabar: el visor azul REC */
export const RecW: React.FC<{ cy: number; nombre?: string; foto?: string }> = ({ cy, nombre, foto }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = 600 * U, h = 740 * U, x0 = width / 2 - w / 2, y0 = cy - h / 2;
  const q = R(0.05, { damping: 12, stiffness: 130 });
  const seg = Math.floor(t * 30) % 30, s = 13 + Math.floor(t);
  const parpadeo = Math.sin(t * 8) > 0 ? 1 : 0.35;
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, borderRadius: 56 * U, border: `${10 * U}px solid #FFFFFF`, boxShadow: SOMBRA(U), overflow: 'hidden',
                    background: 'linear-gradient(180deg, #5C8BFF 0%, #2448C9 100%)', transform: `scale(${Math.max(0.001, q).toFixed(4)}) rotate(${((1 - q) * -4).toFixed(2)}deg)` }}>
        {Array.from({ length: 14 }).map((_, i) => (
          <div key={i} style={{ position: 'absolute', left: w / 2 - 6 * U, top: h * 0.35, width: 12 * U, height: h, transformOrigin: '50% 0', background: 'rgba(255,255,255,.08)',
                                transform: `rotate(${(-80 + i * 12 + Math.sin(t * 0.8) * 3).toFixed(1)}deg)` }} />
        ))}
        {foto ? <Foto src={foto} /> : <div style={{ position: 'absolute', left: w / 2 - 100 * U, top: h * 0.3, width: 200 * U, height: 200 * U, borderRadius: '50%', background: 'linear-gradient(180deg,#E8EEFF,#B9C9F7)' }} />}
        <div style={{ position: 'absolute', left: w / 2 - 230 * U, top: h * 0.62, width: 460 * U, height: 420 * U, borderRadius: '50%', background: 'linear-gradient(180deg,#E8EEFF,#AFC0F3)' }} />
        {[[0.22, 0.26, 0, 0], [0.78, 0.26, 1, 0], [0.22, 0.6, 0, 1], [0.78, 0.6, 1, 1]].map(([a, b, c2, d2], k) => (
          <div key={k} style={{ position: 'absolute', left: w * a - 30 * U, top: h * b - 30 * U, width: 60 * U, height: 60 * U,
                                borderLeft: c2 ? 'none' : `${6 * U}px solid #F5C451`, borderRight: c2 ? `${6 * U}px solid #F5C451` : 'none',
                                borderTop: d2 ? 'none' : `${6 * U}px solid #F5C451`, borderBottom: d2 ? `${6 * U}px solid #F5C451` : 'none' }} />
        ))}
        <div style={{ position: 'absolute', left: 26 * U, top: 26 * U, padding: `${8 * U}px ${18 * U}px`, borderRadius: 14 * U, background: 'rgba(15,25,70,.55)', color: '#fff',
                      fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 26 * U, display: 'flex', alignItems: 'center', gap: 10 * U }}>
          <span style={{ width: 16 * U, height: 16 * U, borderRadius: '50%', background: ROJO, opacity: parpadeo }} />REC 00:00:{String(s).padStart(2, '0')}:{String(seg).padStart(2, '0')}
        </div>
        <div style={{ position: 'absolute', right: 26 * U, top: 26 * U, padding: `${8 * U}px ${16 * U}px`, borderRadius: 14 * U, background: 'rgba(255,255,255,.18)', color: '#fff',
                      fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 24 * U }}>4K · 60</div>
      </div>
      <div style={{ position: 'absolute', left: width / 2 - 70 * U, top: y0 + h - 40 * U, width: 140 * U, height: 140 * U, borderRadius: '50%', background: '#FFFFFF', boxShadow: SOMBRA(U),
                    display: 'flex', alignItems: 'center', justifyContent: 'center', transform: `scale(${Math.max(0, R(0.25, { damping: 11 })).toFixed(4)})` }}>
        <div style={{ width: 66 * U, height: 66 * U, borderRadius: t > 0.9 ? 14 * U : '50%', background: ROJO }} />
      </div>
      <Estrella x={x0 + w + 20 * U} y={y0 + 10 * U} lado={70 * U} t0={0.3} />
      <Estrella x={x0 - 30 * U} y={y0 + h * 0.3} lado={52 * U} t0={0.4} />
      <Estrella x={x0 + w + 30 * U} y={y0 + h * 0.86} lado={54 * U} t0={0.5} />
      <Estrella x={x0 - 20 * U} y={y0 + h * 0.86} lado={40 * U} t0={0.55} />
      <CursorR desde={[width * 0.86, cy + 560 * U]} hasta={[width / 2 + 16 * U, y0 + h + 30 * U]} t0={0.35} t1={0.85} />
      {nombre ? null : null}
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ 2. horas: el reloj que corre */
export const RelojW: React.FC<{ cy: number; desde?: number; hasta?: number; etiqueta?: string }> = ({ cy, desde = 22 * 60 + 30, hasta = 3 * 60 + 14 + 24 * 60, etiqueta = 'Still editing…' }) => {
  const t = useT();
  const U = useU();
  const { width, durationInFrames, fps } = useVideoConfig();
  const R = useResorte();
  const dur = durationInFrames / fps;
  const w = 840 * U, h = 600 * U, x0 = width / 2 - w / 2, y0 = cy - h / 2;
  const q = R(0.05, { damping: 12, stiffness: 120 });
  const min = desde + (hasta - desde) * suave(clamp((t - 0.12) / Math.min(0.8, Math.max(0.5, dur - 0.6))));
  const hh = Math.floor(min / 60) % 24, mm = Math.floor(min % 60);
  const h12 = ((hh + 11) % 12) + 1, ampm = hh >= 12 ? 'PM' : 'AM';
  const rueda = clamp((t - 0.12) / Math.min(0.8, Math.max(0.5, dur - 0.6)));
  const borroso = rueda > 0 && rueda < 1 ? 6 * Math.sin(Math.PI * rueda) : 0;
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, borderRadius: 44 * U, background: '#FFFFFF', boxShadow: SOMBRA(U),
                    transform: `scale(${Math.max(0.001, q).toFixed(4)}) rotate(${((1 - q) * 5).toFixed(2)}deg)` }}>
        <div style={{ position: 'absolute', left: 34 * U, top: 30 * U, display: 'flex', gap: 14 * U }}>
          {['#F0473C', '#F5B82E', '#2FB45A'].map(c => <div key={c} style={{ width: 26 * U, height: 26 * U, borderRadius: '50%', background: c }} />)}
        </div>
        <div style={{ position: 'absolute', left: 30 * U, right: 30 * U, top: 86 * U, bottom: 30 * U, borderRadius: 24 * U, background: '#F4F5FA',
                      backgroundImage: 'radial-gradient(rgba(70,80,140,.12) 2px, transparent 2px)', backgroundSize: `${22 * U}px ${22 * U}px` }} />
        <div style={{ position: 'absolute', left: 80 * U, right: 80 * U, top: 160 * U, height: 300 * U, border: `${3 * U}px solid ${AZUL}`, borderRadius: 4 * U,
                      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 40 * U, color: '#2340C8' }}>{ampm}</div>
          <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 190 * U, color: TINTA, letterSpacing: '-0.04em', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
            {String(h12).padStart(2, '0')}:<span style={{ filter: `blur(${borroso.toFixed(1)}px)` }}>{String(mm).padStart(2, '0')}</span>
          </div>
          {[[0, 0], [1, 0], [0, 1], [1, 1]].map(([a, b], k) => (
            <div key={k} style={{ position: 'absolute', left: `calc(${a * 100}% - ${9 * U}px)`, top: `calc(${b * 100}% - ${9 * U}px)`, width: 16 * U, height: 16 * U, background: '#FFFFFF',
                                  border: `${3 * U}px solid ${AZUL}`, borderRadius: 3 * U }} />
          ))}
        </div>
      </div>
      <div style={{ position: 'absolute', left: x0 + w - 190 * U, top: y0 - 110 * U, transform: `scale(${Math.max(0, R(0.3, { damping: 10 })).toFixed(4)}) rotate(${Math.sin(t * 1.5) * 4}deg)` }}>
        <EmojiAnimado id="crescent_moon" lado={210 * U} />
      </div>
      <div style={{ position: 'absolute', left: x0 + w - 270 * U, top: y0 - 30 * U, opacity: 0.95, transform: `translateX(${Math.sin(t * 0.9) * 10 * U}px)` }}><EmojiAnimado id="cloud" lado={130 * U} /></div>
      <div style={{ position: 'absolute', left: x0 + w - 40 * U, top: y0 + 30 * U, transform: `translateX(${Math.cos(t * 0.8) * 8 * U}px)` }}><EmojiAnimado id="cloud" lado={100 * U} /></div>
      <div style={{ position: 'absolute', left: width / 2 - 20 * U, top: y0 + h + 30 * U, transform: `scale(${Math.max(0, R(0.6, { damping: 12 })).toFixed(4)})`, transformOrigin: 'left center' }}>
        <Pastilla style={{ background: LILA_F, color: LILA, fontSize: 34 * U, padding: `${10 * U}px ${24 * U}px`, border: `${3 * U}px solid #D7CEFF` }}>{etiqueta}</Pastilla>
      </div>
      <CursorR desde={[width * 0.85, cy + 520 * U]} hasta={[width / 2 - 50 * U, y0 + h - 40 * U]} t0={0.3} t1={0.8} onda={false} />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ 3. material: fotos que salen de la carpeta */
export const ArchivosW: React.FC<{ cy: number; titulo?: string; sub?: string }> = ({ cy, titulo = 'Raw footage', sub = '47 clips · 3h 12m' }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = 680 * U, h = 330 * U, x0 = width / 2 - w / 2, y0 = cy + 40 * U;
  const qc = R(0.05, { damping: 13, stiffness: 130 });
  const fotos = [['#FF9A62', '#FFC48E', -16, -150], ['#5A86FF', '#8FB0FF', -4, -10], ['#8E6BFF', '#B79CFF', 12, 140]];
  return (
    <AbsoluteFill>
      {fotos.map(([c1, c2, rot, dx], i) => {
        const q = R(0.12 + i * 0.08, { damping: 11, stiffness: 150 });
        return (
          <div key={i} style={{ position: 'absolute', left: width / 2 - 140 * U + (dx as number) * U * q, top: y0 - 60 * U - q * 170 * U, width: 280 * U, height: 200 * U, borderRadius: 26 * U,
                                background: `linear-gradient(160deg, ${c1}, ${c2})`, border: `${7 * U}px solid #FFFFFF`, boxShadow: SOMBRA(U),
                                transform: `rotate(${((rot as number) * q).toFixed(2)}deg)`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ width: 70 * U, height: 70 * U, borderRadius: '50%', background: 'rgba(255,255,255,.85)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ width: 0, height: 0, borderTop: `${14 * U}px solid transparent`, borderBottom: `${14 * U}px solid transparent`, borderLeft: `${22 * U}px solid ${c1}`, marginLeft: 6 * U }} />
            </div>
          </div>
        );
      })}
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, borderRadius: 40 * U, background: '#FFFFFF', boxShadow: SOMBRA(U),
                    transform: `scale(${Math.max(0.001, qc).toFixed(4)})`, padding: `${40 * U}px ${44 * U}px`, boxSizing: 'border-box' }}>
        <div style={{ position: 'absolute', left: 44 * U, bottom: 90 * U, fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 50 * U, color: TINTA, letterSpacing: '-0.02em' }}>{titulo}</div>
        <div style={{ position: 'absolute', left: 44 * U, bottom: 46 * U, fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 30 * U, color: '#8A8E9C' }}>{sub}</div>
        <div style={{ position: 'absolute', right: 40 * U, bottom: 40 * U, width: 100 * U, height: 100 * U, borderRadius: '50%', background: TINTA, color: '#fff',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 50 * U, fontWeight: 800, fontFamily: FAMILIA.inter }}>↗</div>
      </div>
      <CursorR desde={[width * 0.9, cy + 520 * U]} hasta={[x0 + w - 90 * U, y0 + h - 90 * U]} t0={0.12} t1={0.5} />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ 4. encontrar: el clip elegido */
export const BuscarW: React.FC<{ cy: number; etiqueta?: string; foto?: string }> = ({ cy, etiqueta = 'Story found', foto }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const clips = [['#FFB199', '#FFD5C4', '12:06'], ['#4F7BFF', '#8BAAFF', '08:41'], ['#B9A4FF', '#DCD2FF', '23:17']];
  const sel = R(0.4, { damping: 12, stiffness: 140 });
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: width / 2 - 330 * U, top: cy - 330 * U, width: 660 * U, height: 660 * U, borderRadius: '50%',
                    background: `radial-gradient(circle, rgba(79,123,255,${(0.35 * sel).toFixed(3)}) 0%, rgba(79,123,255,0) 65%)` }} />
      {clips.map(([c1, c2, d], i) => {
        const q = R(0.1 + i * 0.1, { damping: 12, stiffness: 150 });
        const centro = i === 1;
        const w = (centro ? 300 : 250) * U * (centro ? 1 + 0.08 * sel : 1), h = w * 0.7;
        const x = width / 2 + (i - 1) * 330 * U;
        return (
          <div key={i} style={{ position: 'absolute', left: x - w / 2, top: cy - h / 2, width: w, height: h, borderRadius: 22 * U, background: `linear-gradient(160deg, ${c1}, ${c2})`,
                                border: `${6 * U}px solid #FFFFFF`, boxShadow: SOMBRA(U), transform: `scale(${Math.max(0.001, q).toFixed(4)})`, opacity: centro ? 1 : 1 - 0.35 * sel }}>
            {centro && foto ? <Foto src={foto} style={{ borderRadius: 16 * U }} /> : null}
            <div style={{ position: 'absolute', left: '50%', top: '42%', transform: 'translate(-50%,-50%)', width: 56 * U, height: 56 * U, borderRadius: '50%', background: 'rgba(255,255,255,.8)' }} />
            <div style={{ position: 'absolute', right: 12 * U, bottom: 10 * U, padding: `${2 * U}px ${8 * U}px`, borderRadius: 8 * U, background: 'rgba(0,0,0,.35)', color: '#fff',
                          fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 20 * U }}>{d}</div>
            {centro && <div style={{ position: 'absolute', inset: -22 * U, border: `${3 * U}px solid ${AZUL}`, borderRadius: 6 * U, opacity: sel }}>
              {[[0, 0], [1, 0], [0, 1], [1, 1]].map(([a, b], k) => <div key={k} style={{ position: 'absolute', left: `calc(${a * 100}% - ${9 * U}px)`, top: `calc(${b * 100}% - ${9 * U}px)`,
                                                                                         width: 16 * U, height: 16 * U, background: '#fff', border: `${3 * U}px solid ${AZUL}`, borderRadius: 3 * U }} />)}
            </div>}
          </div>
        );
      })}
      <div style={{ position: 'absolute', left: width / 2, top: cy + 190 * U, transform: `translateX(-50%) scale(${Math.max(0, R(0.5, { damping: 11 })).toFixed(4)})` }}>
        <Pastilla style={{ color: '#2340C8' }}>✦ {etiqueta}</Pastilla>
      </div>
      <CursorR desde={[width * 0.82, cy + 480 * U]} hasta={[width / 2 + 40 * U, cy + 40 * U]} t0={0.05} t1={0.4} />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ 5. cortar: línea de tiempo y tijeras */
export const CortarW: React.FC<{ cy: number; titulo?: string }> = ({ cy, titulo = 'Timeline' }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = 940 * U, h = 420 * U, x0 = width / 2 - w / 2, y0 = cy - h / 2;
  const q = R(0.05, { damping: 13, stiffness: 130 });
  const cab = x0 + 60 * U + (w - 120 * U) * suave(clamp((t - 0.08) / 0.7));
  const corte = clamp((t - 0.45) / 0.4);
  const barras = (n: number, semilla: number) => Array.from({ length: n }).map((_, i) => 0.25 + 0.75 * Math.abs(Math.sin(i * 1.7 + semilla)));
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, borderRadius: 40 * U, background: '#FFFFFF', boxShadow: SOMBRA(U), transform: `scale(${Math.max(0.001, q).toFixed(4)})` }}>
        <div style={{ position: 'absolute', left: 36 * U, top: 28 * U, fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 36 * U, color: TINTA }}>{titulo}</div>
        <div style={{ position: 'absolute', right: 40 * U, top: 32 * U, fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 28 * U, color: '#555A6A', display: 'flex', alignItems: 'center', gap: 8 * U }}>
          <span style={{ width: 12 * U, height: 12 * U, borderRadius: '50%', background: ROJO }} />00:{String(14 + Math.floor(t)).padStart(2, '0')}:{String(Math.floor(t * 30) % 30).padStart(2, '0')}
        </div>
        {[0, 1, 2, 3].map(i => {
          const fuera = i === 3;
          const caida = fuera ? corte : 0;
          return (
            <div key={i} style={{ position: 'absolute', left: 60 * U + i * 210 * U, top: 120 * U + caida * 300 * U, width: 196 * U, height: 150 * U, borderRadius: 14 * U,
                                  background: fuera ? '#C9CEDA' : '#3D6BF0', opacity: 1 - caida, transform: `rotate(${(caida * 25).toFixed(1)}deg)`, display: 'flex', alignItems: 'center',
                                  justifyContent: 'space-evenly', padding: `0 ${8 * U}px` }}>
              {barras(12, i).map((b, k) => <div key={k} style={{ width: 5 * U, height: 80 * U * b, borderRadius: 3 * U, background: 'rgba(255,255,255,.85)' }} />)}
            </div>
          );
        })}
        <div style={{ position: 'absolute', left: 60 * U, right: 60 * U, top: 310 * U, height: 64 * U, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          {barras(46, 3).map((b, k) => <div key={k} style={{ width: 5 * U, height: 40 * U * b, borderRadius: 3 * U, background: '#8B7BF0', opacity: 0.8 }} />)}
        </div>
      </div>
      <div style={{ position: 'absolute', left: cab - 2 * U, top: y0 + 20 * U, width: 4 * U, height: h - 40 * U, background: TINTA }} />
      <div style={{ position: 'absolute', left: cab - 40 * U, top: y0 - 10 * U, width: 80 * U, height: 80 * U, borderRadius: '50%', background: TINTA, color: '#fff', display: 'flex',
                    alignItems: 'center', justifyContent: 'center', fontSize: 42 * U, transform: `rotate(${(t > 0.45 && t < 0.7 ? -25 : 0)}deg)` }}>✂</div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ 6. largo / aburrido: el reproductor gris */
export const LargoW: React.FC<{ cy: number; duracion?: string; foto?: string }> = ({ cy, duracion = '2h 47m', foto }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = width * 1.02, h = 470 * U, y0 = cy - h / 2 - 40 * U;
  const q = R(0.05, { damping: 14, stiffness: 110 });
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: (width - w) / 2, top: y0, width: w, height: h, background: 'linear-gradient(180deg,#C7C9CF,#A9ACB4)', borderTop: `${8 * U}px solid #FFFFFF`,
                    borderBottom: `${8 * U}px solid #FFFFFF`, boxShadow: SOMBRA(U), transform: `scaleX(${(0.6 + 0.4 * q).toFixed(4)})`, opacity: clamp(q * 1.5), overflow: 'hidden' }}>
        <div style={{ position: 'absolute', left: width / 2 - 70 * U, top: h * 0.2, width: 140 * U, height: 140 * U, borderRadius: '50%', background: '#D9DBE0' }} />
        <div style={{ position: 'absolute', left: width / 2 - 200 * U, top: h * 0.62, width: 400 * U, height: 300 * U, borderRadius: '50%', background: '#D9DBE0' }} />
        <Foto src={foto} gris style={{ opacity: 0.85 }} />
        <div style={{ position: 'absolute', left: width / 2 - 45 * U, top: h * 0.29, width: 90 * U, height: 90 * U, borderRadius: '50%', background: 'rgba(255,255,255,.75)' }} />
      </div>
      {[0, 1].map(k => {
        const u = ((t * 0.5 + k * 0.5) % 1);
        return <div key={k} style={{ position: 'absolute', left: width * 0.78 + u * 30 * U, top: y0 - 40 * U - u * 120 * U, fontFamily: FAMILIA.inter, fontWeight: 800,
                                     fontSize: (40 - k * 10) * U, color: '#9A9CA8', opacity: 1 - u }}>z</div>;
      })}
      <div style={{ position: 'absolute', left: width / 2, top: y0 + h + 50 * U, transform: `translateX(-50%) scale(${Math.max(0, R(0.45, { damping: 11 })).toFixed(4)})` }}>
        <Pastilla style={{ fontSize: 40 * U }}><span style={{ color: ROJO }}>◷</span>{duracion}</Pastilla>
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ 7. la gente lo entiende: móvil y reacciones */
export const MovilW: React.FC<{ cy: number; titulo?: string; cursiva?: string; sub?: string; boton?: string; pct?: number; etiqueta?: string; foto?: string }> =
  ({ cy, titulo = 'Your story,', cursiva = 'finally.', sub = 'Tight, clear, and actually worth watching.', boton = 'Watch now', pct = 96, etiqueta = 'Watch-through', foto }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = 500 * U, h = 760 * U, x0 = width / 2 - w / 2 + 20 * U, y0 = cy - h / 2 + 20 * U;
  const q = R(0.05, { damping: 12, stiffness: 120 });
  const reacciones = ['light_bulb', 'smiling_face_with_heart_eyes', 'thumbs_up', 'raising_hands', 'exploding_head'];
  const pos = [[0.95, 0.06], [1.15, 0.0], [1.42, 0.0], [1.05, 0.2], [1.38, 0.24]];
  const n = Math.round(pct * suave(clamp((t - 0.6) / 1.1)));
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, borderRadius: 40 * U, border: `${8 * U}px solid #FFFFFF`, boxShadow: SOMBRA(U), overflow: 'hidden',
                    background: 'linear-gradient(180deg,#2C5BE8 0%,#0E2A7A 100%)', transform: `scale(${Math.max(0.001, q).toFixed(4)}) rotate(${((1 - q) * 4).toFixed(2)}deg)` }}>
        {Array.from({ length: 10 }).map((_, i) => <div key={i} style={{ position: 'absolute', left: w / 2 - 4 * U, top: h * 0.25, width: 8 * U, height: h, transformOrigin: '50% 0',
                                                                        background: 'rgba(255,255,255,.06)', transform: `rotate(${(-60 + i * 13)}deg)` }} />)}
        {foto ? <><Foto src={foto} /><div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(14,42,122,.15) 0%, rgba(14,42,122,.55) 45%, rgba(10,24,70,.92) 100%)' }} /></> : null}
        <div style={{ position: 'absolute', left: w / 2 - 34 * U, top: h * 0.2, width: 68 * U, height: 68 * U, borderRadius: '50%', background: 'rgba(255,255,255,.85)' }} />
        <div style={{ position: 'absolute', left: 0, right: 0, top: h * 0.4, textAlign: 'center', color: '#fff', padding: `0 ${30 * U}px` }}>
          <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 50 * U, lineHeight: 1.05 }}>{titulo}</div>
          <div style={{ fontFamily: FAMILIA.display, fontStyle: 'italic', fontSize: 54 * U, lineHeight: 1.05 }}>{cursiva}</div>
          <div style={{ marginTop: 16 * U, fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 24 * U, opacity: 0.8 }}>{sub}</div>
          <div style={{ display: 'inline-block', marginTop: 22 * U, padding: `${12 * U}px ${30 * U}px`, borderRadius: 999, background: '#fff', color: TINTA, fontFamily: FAMILIA.inter,
                        fontWeight: 700, fontSize: 26 * U }}>{boton}</div>
        </div>
      </div>
      {reacciones.map((r, i) => {
        const qr = R(0.5 + i * 0.12, { damping: 9, stiffness: 170 });
        const [a, b] = pos[i];
        const lado = (i === 1 ? 120 : 92) * U;
        return (
          <div key={r} style={{ position: 'absolute', left: x0 + w * a - lado / 2, top: y0 + h * b - lado / 2 + Math.sin(t * 2 + i) * 8 * U, width: lado, height: lado, borderRadius: '50%',
                                background: '#FFFFFF', boxShadow: SOMBRA(U), display: 'flex', alignItems: 'center', justifyContent: 'center', transform: `scale(${Math.max(0, qr).toFixed(4)})` }}>
            <EmojiAnimado id={r} lado={lado * 0.7} />
          </div>
        );
      })}
      <div style={{ position: 'absolute', left: x0 - 230 * U, top: y0 + 20 * U, transform: `scale(${Math.max(0, R(0.4, { damping: 11 })).toFixed(4)})`, transformOrigin: 'left center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 18 * U, padding: `${18 * U}px ${34 * U}px ${18 * U}px ${18 * U}px`, borderRadius: 999, background: OSCURO, boxShadow: SOMBRA(U) }}>
          <svg width={86 * U} height={86 * U} viewBox="0 0 40 40">
            <circle cx={20} cy={20} r={15} fill="none" stroke="rgba(255,255,255,.15)" strokeWidth={5} />
            <circle cx={20} cy={20} r={15} fill="none" stroke="#2FD27A" strokeWidth={5} strokeLinecap="round" strokeDasharray={94.2} strokeDashoffset={94.2 * (1 - n / 100)} transform="rotate(-90 20 20)" />
          </svg>
          <div>
            <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 52 * U, color: '#fff', lineHeight: 1 }}>{n}%</div>
            <div style={{ fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 22 * U, color: 'rgba(255,255,255,.65)' }}>{etiqueta}</div>
          </div>
        </div>
      </div>
      <Estrella x={x0 - 40 * U} y={y0 + h - 20 * U} lado={46 * U} t0={0.8} />
      <Estrella x={x0 + w + 40 * U} y={y0 + h - 60 * U} lado={40 * U} t0={0.9} />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ 8. lo que te dicen: el mensaje */
export const ChatW: React.FC<{ cy: number; nombre?: string; rol?: string; responder?: string; iconos?: string[]; cita: { texto: string; resalta?: boolean; t: number }[] }> =
  ({ cy, nombre = '', rol = '', responder = 'Reply', iconos, cita }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const q1 = R(0.05, { damping: 12, stiffness: 150 }), q2 = R(0.25, { damping: 12, stiffness: 120 });
  const w = 900 * U;
  const emojis = [...(iconos || []), 'grinning_face_with_sweat', 'thinking_face', 'clapper_board'].filter((x, i, a) => a.indexOf(x) === i).slice(0, 3);
  return (
    <AbsoluteFill>
      {nombre ? (
      <div style={{ position: 'absolute', left: width / 2 - 260 * U, top: cy - 420 * U, transform: `scale(${(Math.max(0.001, q1) * 1.3).toFixed(4)})` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 * U, padding: `${18 * U}px ${22 * U}px`, width: 520 * U, borderRadius: 999, background: '#FFFFFF', boxShadow: SOMBRA(U), boxSizing: 'border-box' }}>
          <div style={{ width: 70 * U, height: 70 * U, borderRadius: '50%', background: '#F26B4E', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 36 * U }}>{nombre.slice(0, 1).toUpperCase()}</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 34 * U, color: TINTA }}>{nombre}</div>
            <div style={{ fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 22 * U, color: '#9A9CA8' }}>{rol}</div>
          </div>
          <div style={{ padding: `${10 * U}px ${22 * U}px`, borderRadius: 14 * U, background: '#E6EDFF', color: AZUL, fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 26 * U }}>{responder}</div>
        </div>
      </div>
      ) : null}
      <div style={{ position: 'absolute', left: width / 2 - w / 2, top: cy - 220 * U, width: w, borderRadius: 40 * U, background: '#FFFFFF', boxShadow: SOMBRA(U), overflow: 'hidden',
                    border: `${6 * U}px solid #FFFFFF`, transform: `translateY(${((1 - q2) * 80 * U).toFixed(1)}px) scale(${(0.9 + 0.1 * q2).toFixed(4)})`, opacity: clamp(q2 * 1.5) }}>
        <div style={{ height: 210 * U, background: 'linear-gradient(180deg,#D7E3FF,#E9EEFF)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 24 * U }}>
          {emojis.map((e, i) => {
            const qe = R(0.5 + i * 0.12, { damping: 10 });
            const lado = (i === 1 ? 150 : 100) * U;
            return <div key={e} style={{ width: lado, height: lado, borderRadius: '50%', background: '#FFFFFF', display: 'flex', alignItems: 'center', justifyContent: 'center',
                                         boxShadow: SOMBRA(U), transform: `scale(${Math.max(0, qe).toFixed(4)})` }}><EmojiAnimado id={e} lado={lado * 0.72} /></div>;
          })}
        </div>
        <div style={{ padding: `${36 * U}px ${46 * U}px ${46 * U}px`, textAlign: 'center', fontFamily: FAMILIA.inter, fontWeight: 600, fontSize: 62 * U, color: TINTA, lineHeight: 1.18 }}>
          “{cita.map((p, i) => {
            const v = clamp((t - p.t + 0.05) / 0.2);
            return <span key={i} style={{ opacity: 0.25 + 0.75 * v, color: p.resalta ? '#2048D8' : TINTA, background: p.resalta ? `rgba(120,160,255,${(0.35 * v).toFixed(3)})` : 'transparent',
                                         borderRadius: 6 * U, padding: `0 ${4 * U}px` }}>{p.texto} </span>;
          })}”
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ 9. versiones A/B/C */
export const VersionesW: React.FC<{ cy: number; etiquetas?: string[]; boton?: string; version?: string }> =
  ({ cy, etiquetas = ['Punchy cut', 'Story-first', 'Minimal'], boton = 'New version', version = 'VERSION' }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const abre = R(0.45, { damping: 12, stiffness: 120 });
  const cartas = [['A', '#3E6BF5', '#6E92FF'], ['B', '#FF7A45', '#FFB177'], ['C', '#1E1F29', '#3A3C4C']];
  const giro = suave(clamp((t - 0.7) / 0.55));
  return (
    <AbsoluteFill>
      {cartas.map(([l, c1, c2], i) => {
        const q = R(0.05 + i * 0.06, { damping: 12, stiffness: 140 });
        const k = ((i + 2) % 3) - 1;
        const kk = (i - 1) * (1 - giro) + k * giro;
        const delante = 1 - Math.min(1, Math.abs(kk));
        const w = 320 * U, h = 450 * U;
        return (
          <div key={l} style={{ position: 'absolute', left: width / 2 - w / 2 + kk * 280 * U * abre, top: cy - h / 2 + (1 - q) * 300 * U + Math.abs(kk) * 30 * U * abre, width: w, height: h,
                                borderRadius: 30 * U, background: `linear-gradient(160deg, ${c1}, ${c2})`, border: `${6 * U}px solid #FFFFFF`, boxShadow: SOMBRA(U),
                                transform: `rotate(${(kk * 12 * abre).toFixed(2)}deg) scale(${(1 + 0.1 * delante).toFixed(4)})`, zIndex: Math.round(delante * 10), opacity: clamp(q * 1.5) }}>
            <div style={{ position: 'absolute', left: 22 * U, top: 18 * U, fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 20 * U, color: 'rgba(255,255,255,.75)', letterSpacing: '0.1em' }}>{version}</div>
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: FAMILIA.display, fontSize: 230 * U,
                          color: l === 'C' ? '#2FE0A0' : '#FFFFFF' }}>{l}</div>
            <div style={{ position: 'absolute', left: '50%', bottom: 22 * U, transform: 'translateX(-50%)', padding: `${6 * U}px ${18 * U}px`, borderRadius: 999,
                          background: 'rgba(255,255,255,.2)', color: '#fff', fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 22 * U, whiteSpace: 'nowrap' }}>{etiquetas[i] || ''}</div>
          </div>
        );
      })}
      <div style={{ position: 'absolute', left: width / 2, top: cy + 300 * U, transform: `translateX(-50%) scale(${Math.max(0, R(0.3, { damping: 11 })).toFixed(4)})` }}>
        <Pastilla style={{ background: TINTA, color: '#fff' }}>+ {boton}</Pastilla>
      </div>
      <CursorR desde={[width * 0.85, cy + 640 * U]} hasta={[width / 2 + 40 * U, cy + 340 * U]} t0={0.25} t1={0.65} />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ 10. ideas: la nube que suelta iconos y los contadores */
export const IdeasW: React.FC<{ cy: number; n1?: number | string; e1?: string; n2?: string; e2?: string }> = ({ cy, n1 = 249, e1 = 'Video ideas', n2 = '24 hrs', e2 = 'In a day' }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const qn = R(0.05, { damping: 11, stiffness: 140 });
  const iconos = ['#FF6B4A', '#7B5CF5', '#1E1F29', '#FF9A62', '#2FB45A', '#3E6BF5', '#8A8E9C'];
  const cuenta = typeof n1 === 'number' ? `${Math.round(n1 * (0.85 + 0.15 * suave(clamp((t - 0.6) / 1.4))))}+` : String(n1);
  const pill = (y: number, color: string, grande: string, chico: string, t0: number) => {
    const q = R(t0, { damping: 12, stiffness: 150 });
    return (
      <div style={{ position: 'absolute', left: width / 2 - 280 * U, top: y, width: 560 * U, transform: `scale(${Math.max(0, q).toFixed(4)})` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 28 * U, padding: `${30 * U}px ${40 * U}px`, borderRadius: 999, background: OSCURO, boxShadow: SOMBRA(U) }}>
          <div style={{ width: 100 * U, height: 100 * U, borderRadius: '50%', border: `${12 * U}px solid ${color}`, boxSizing: 'border-box', borderRightColor: 'rgba(255,255,255,.12)',
                        transform: `rotate(${(t * 90) % 360}deg)` }} />
          <div>
            <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 64 * U, color: '#fff', lineHeight: 1 }}>{grande}</div>
            <div style={{ fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 28 * U, color: 'rgba(255,255,255,.6)' }}>{chico}</div>
          </div>
        </div>
      </div>
    );
  };
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: width / 2 - 180 * U, top: cy - 330 * U, width: 360 * U, height: 230 * U, transform: `scale(${(Math.max(0.001, qn) * 1.2).toFixed(4)})` }}>
        <svg width={360 * U} height={230 * U} viewBox="0 0 120 76">
          <path d="M30 70 Q8 70 8 52 Q8 36 26 34 Q28 12 52 12 Q72 12 78 30 Q96 26 104 42 Q116 46 112 60 Q110 70 96 70 Z" fill="#FFFFFF" stroke="#DDE3FF" strokeWidth={2} />
        </svg>
        <div style={{ position: 'absolute', left: 120 * U, top: 60 * U }}><EmojiAnimado id="light_bulb" lado={120 * U} /></div>
      </div>
      {iconos.map((c, i) => {
        const lado = (i % 2 ? 1 : -1);
        const u = clamp((t - 0.3 - i * 0.08) / 1.0);
        const e = easeOut(u);
        const x = width / 2 + lado * (140 + 260 * e + (i % 3) * 30) * U;
        const y = cy - 190 * U - Math.sin(e * Math.PI * 0.8) * (60 + i * 10) * U + (i % 3 - 1) * 70 * U * e;
        return <div key={i} style={{ position: 'absolute', left: x - 40 * U, top: y - 30 * U, width: 80 * U, height: 60 * U, borderRadius: 14 * U, background: c, boxShadow: SOMBRA(U),
                                     transform: `rotate(${(lado * (8 + i * 3) * e).toFixed(1)}deg) scale(${(0.4 + 0.6 * e).toFixed(3)})`, opacity: clamp(u * 3),
                                     display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ width: 0, height: 0, borderTop: `${10 * U}px solid transparent`, borderBottom: `${10 * U}px solid transparent`, borderLeft: `${16 * U}px solid #fff`, marginLeft: 4 * U }} />
        </div>;
      })}
      {pill(cy + 10 * U, '#2FD27A', cuenta, e1, 0.55)}
      {n2 ? pill(cy + 220 * U, '#E64BD8', n2, e2, 0.75) : null}
    </AbsoluteFill>
  );
};

/* ================================================================================================================================================
   v5.5.9 · MÁS TARJETAS EN EL MISMO IDIOMA VISUAL, para cualquier tema (el reel de referencia solo hablaba de editar videos): fecha, lugar, entrada,
   personas, música, premio, compartir y el aviso (la general). Blancas, redondeadas, con su sombra suave, el cursor morado y los resortes. */
const Boton: React.FC<{ texto: string; oscuro?: boolean; style?: React.CSSProperties }> = ({ texto, oscuro = true, style }) => {
  const U = useU();
  return <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 12 * U, padding: `${18 * U}px ${34 * U}px`, borderRadius: 999,
                       background: oscuro ? TINTA : AZUL, color: '#fff', fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 32 * U, whiteSpace: 'nowrap', ...style }}>{texto}</div>;
};

/* fecha: la hoja del calendario (el día rueda hasta su número), la hora y «añadir al calendario» con su clic */
export const FechaW: React.FC<{ cy: number; dia?: string; mes?: string; semana?: string; hora?: string; boton?: string }> =
  ({ cy, dia = '10', mes = 'OCT', semana = '', hora = '', boton = 'Add to calendar' }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = 520 * U, h = 560 * U, x0 = width / 2 - w / 2, y0 = cy - h / 2 - 60 * U;
  const q = R(0.05, { damping: 12, stiffness: 130 });
  const rueda = easeOut((t - 0.15) / 0.5);
  const hecho = t > 0.95;
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, borderRadius: 48 * U, background: '#FFFFFF', boxShadow: SOMBRA(U), overflow: 'hidden',
                    transform: `scale(${Math.max(0.001, q).toFixed(4)}) rotate(${((1 - q) * -5).toFixed(2)}deg)` }}>
        <div style={{ height: 140 * U, background: `linear-gradient(135deg, ${ROJO}, #FF7A59)`, display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 64 * U, letterSpacing: '0.12em', color: '#fff' }}>{mes.toUpperCase()}</div>
        <div style={{ position: 'absolute', left: 0, right: 0, top: 140 * U, bottom: semana ? 90 * U : 30 * U, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 250 * U, color: TINTA, letterSpacing: '-0.05em', lineHeight: 1,
                        transform: `translateY(${((1 - rueda) * 160 * U).toFixed(1)}px)`, filter: rueda < 1 ? `blur(${((1 - rueda) * 8).toFixed(1)}px)` : undefined, opacity: clamp(rueda * 2) }}>{dia}</div>
        </div>
        {semana && <div style={{ position: 'absolute', left: 0, right: 0, bottom: 40 * U, textAlign: 'center', fontFamily: FAMILIA.inter, fontWeight: 600, fontSize: 40 * U, color: '#8A8E9C' }}>{semana}</div>}
      </div>
      {hora && <div style={{ position: 'absolute', left: x0 + w - 90 * U, top: y0 - 30 * U, transform: `scale(${Math.max(0, R(0.35, { damping: 10 })).toFixed(4)})` }}>
        <Pastilla style={{ fontSize: 40 * U }}><span style={{ color: AZUL }}>◷</span>{hora}</Pastilla>
      </div>}
      <div style={{ position: 'absolute', left: width / 2, top: y0 + h + 50 * U, transform: `translateX(-50%) scale(${Math.max(0, R(0.45, { damping: 11 })).toFixed(4)})` }}>
        <Boton texto={(hecho ? '✓ ' : '+ ') + boton} oscuro={!hecho} />
      </div>
      <Estrella x={x0 - 30 * U} y={y0 + 60 * U} lado={56 * U} t0={0.3} />
      <Estrella x={x0 + w + 20 * U} y={y0 + h - 40 * U} lado={44 * U} t0={0.45} />
      <CursorR desde={[width * 0.86, cy + 640 * U]} hasta={[width / 2 + 60 * U, y0 + h + 90 * U]} t0={0.45} t1={0.9} />
    </AbsoluteFill>
  );
};

/* lugar: el mapa, la ruta que se dibuja, el alfiler que cae y «cómo llegar» */
export const LugarW: React.FC<{ cy: number; nombre?: string; sub?: string; boton?: string }> = ({ cy, nombre = '', sub = '', boton = 'Directions' }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = 840 * U, h = 640 * U, x0 = width / 2 - w / 2, y0 = cy - h / 2;
  const q = R(0.05, { damping: 13, stiffness: 120 });
  const pin = R(0.45, { damping: 9, stiffness: 160 });
  const ruta = easeOut((t - 0.15) / 0.7);
  const px = w * 0.62, py = h * 0.36;
  const pulso = (t * 0.9) % 1;
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, borderRadius: 48 * U, background: '#FFFFFF', boxShadow: SOMBRA(U), overflow: 'hidden',
                    transform: `scale(${Math.max(0.001, q).toFixed(4)})` }}>
        <div style={{ position: 'absolute', left: 0, top: 0, width: w, height: h * 0.68, background: '#EEF1F8' }}>
          <svg width={w} height={h * 0.68} viewBox="0 0 100 68" preserveAspectRatio="none" style={{ position: 'absolute', inset: 0 }}>
            <path d="M-5 50 Q30 40 50 52 T105 44" stroke="#BFD3FF" strokeWidth={6} fill="none" />
            <ellipse cx={20} cy={18} rx={14} ry={9} fill="#D5F0DC" />
            {[[0, 22, 100, 30], [0, 8, 100, 4], [30, 0, 26, 68], [70, 0, 78, 68], [50, 0, 46, 68]].map(([a, b, c2, d], i) =>
              <line key={i} x1={a} y1={b} x2={c2} y2={d} stroke="#FFFFFF" strokeWidth={2.4} />)}
            <path d="M8 60 C 20 40, 40 46, 46 30 S 58 26, 62 36" stroke={AZUL} strokeWidth={1.8} fill="none" strokeLinecap="round" strokeDasharray="120" strokeDashoffset={120 * (1 - ruta)} style={{ stroke: AZUL }} />
            <circle cx={8} cy={60} r={2.2} style={{ fill: AZUL }} opacity={clamp(ruta * 4)} />
          </svg>
          <div style={{ position: 'absolute', left: px - 60 * U * (0.4 + pulso), top: py + 34 * U - 30 * U * (0.4 + pulso), width: 120 * U * (0.4 + pulso), height: 60 * U * (0.4 + pulso),
                        borderRadius: '50%', border: `${3 * U}px solid rgba(240,71,60,${(0.5 * (1 - pulso) * clamp(pin)).toFixed(3)})` }} />
          <svg width={86 * U} height={110 * U} viewBox="0 0 24 30" style={{ position: 'absolute', left: px - 43 * U, top: py - 80 * U - (1 - pin) * 220 * U, opacity: clamp(pin * 3),
                                                                           filter: 'drop-shadow(0 8px 10px rgba(160,30,30,.3))' }}>
            <path d="M12 29 C 12 29, 2 17, 2 11 A 10 10 0 0 1 22 11 C 22 17, 12 29, 12 29 Z" fill={ROJO} stroke="#fff" strokeWidth={1.6} />
            <circle cx={12} cy={11} r={4} fill="#fff" />
          </svg>
        </div>
        <div style={{ position: 'absolute', left: 44 * U, right: 44 * U, bottom: 36 * U, height: h * 0.32 - 50 * U, display: 'flex', alignItems: 'center', gap: 20 * U }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 44 * U, color: TINTA, lineHeight: 1.1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{nombre}</div>
            {sub && <div style={{ fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 30 * U, color: '#8A8E9C', marginTop: 6 * U }}>{sub}</div>}
          </div>
          <Boton texto={'➤ ' + boton} oscuro={false} style={{ fontSize: 28 * U, padding: `${14 * U}px ${26 * U}px` }} />
        </div>
      </div>
      <CursorR desde={[width * 0.9, cy + 600 * U]} hasta={[x0 + w - 130 * U, y0 + h - 90 * U]} t0={0.55} t1={1.0} />
    </AbsoluteFill>
  );
};

/* entrada: el boleto con su precio (o GRATIS) y el sello que cae */
export const EntradaW: React.FC<{ cy: number; valor?: string; titulo?: string; sub?: string; sello?: string }> = ({ cy, valor = 'FREE', titulo = 'Ticket', sub = '', sello = '' }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = 860 * U, h = 360 * U, x0 = width / 2 - w / 2, y0 = cy - h / 2;
  const q = R(0.05, { damping: 12, stiffness: 120 });
  const s = R(0.6, { damping: 10, stiffness: 200 });
  const corte = w * 0.64;
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, transform: `scale(${Math.max(0.001, q).toFixed(4)}) rotate(${((1 - q) * 6 - 3).toFixed(2)}deg)`,
                    filter: 'drop-shadow(0 30px 50px rgba(60,60,130,.22))' }}>
        <div style={{ position: 'absolute', inset: 0, borderRadius: 40 * U, background: '#FFFFFF',
                      WebkitMaskImage: `radial-gradient(circle at ${corte}px 0, transparent ${30 * U}px, #000 ${31 * U}px), radial-gradient(circle at ${corte}px ${h}px, transparent ${30 * U}px, #000 ${31 * U}px)`,
                      WebkitMaskComposite: 'source-in', maskComposite: 'intersect' } as React.CSSProperties} />
        <div style={{ position: 'absolute', left: corte - 2 * U, top: 40 * U, bottom: 40 * U, borderLeft: `${4 * U}px dashed #D9DCE6` }} />
        <div style={{ position: 'absolute', left: 50 * U, top: 50 * U, width: corte - 100 * U }}>
          <div style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 34 * U, letterSpacing: '0.16em', color: '#8A8E9C' }}>{titulo.toUpperCase()}</div>
          <div style={{ marginTop: 14 * U, fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 52 * U, color: TINTA, lineHeight: 1.08 }}>{sub}</div>
          <div style={{ position: 'absolute', top: 210 * U, display: 'flex', gap: 6 * U }}>
            {Array.from({ length: 22 }).map((_, i) => <div key={i} style={{ width: (i % 3 ? 6 : 12) * U, height: 60 * U, background: TINTA, opacity: 0.85 }} />)}
          </div>
        </div>
        <div style={{ position: 'absolute', left: corte, right: 0, top: 0, bottom: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: (valor.length > 6 ? 54 : 74) * U, color: '#1FAF62', letterSpacing: '-0.02em' }}>{valor}</div>
        </div>
      </div>
      {sello && <div style={{ position: 'absolute', left: x0 + w - 300 * U, top: y0 - 70 * U, padding: `${10 * U}px ${26 * U}px`, borderRadius: 18 * U, border: `${6 * U}px solid ${ROJO}`,
                              color: ROJO, fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 52 * U, transform: `rotate(-12deg) scale(${(2.2 - 1.2 * clamp(s)).toFixed(3)})`, opacity: clamp(s * 2),
                              background: 'rgba(255,255,255,.85)' }}>{sello}</div>}
      <Estrella x={x0 - 20 * U} y={y0 + h + 20 * U} lado={56 * U} t0={0.5} />
      <Estrella x={x0 + w + 10 * U} y={y0 + h - 20 * U} lado={44 * U} t0={0.65} />
      <Estrella x={x0 + 120 * U} y={y0 - 50 * U} lado={36 * U} t0={0.75} />
    </AbsoluteFill>
  );
};

/* personas: las caras que van saliendo, sus nombres y «+N» */
const COLORES_CARA = [['#FF9A62', '#FF6B4A'], ['#6E92FF', '#3E6BF5'], ['#B79CFF', '#7B5CF5'], ['#5BD68E', '#1FAF62']];
export const PersonasW: React.FC<{ cy: number; nombres?: string[]; etiqueta?: string; extra?: string }> = ({ cy, nombres = [], etiqueta = '', extra = '' }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const n = Math.max(3, Math.min(4, nombres.length || 3));
  const w = 820 * U, h = 520 * U, x0 = width / 2 - w / 2, y0 = cy - h / 2;
  const q = R(0.05, { damping: 13, stiffness: 120 });
  const lado = 170 * U;
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, borderRadius: 48 * U, background: '#FFFFFF', boxShadow: SOMBRA(U), transform: `scale(${Math.max(0.001, q).toFixed(4)})` }}>
        <div style={{ position: 'absolute', left: 0, right: 0, top: 70 * U, display: 'flex', justifyContent: 'center' }}>
          {Array.from({ length: n }).map((_, i) => {
            const qi = R(0.15 + i * 0.1, { damping: 10, stiffness: 170 });
            const nombre = nombres[i] || '';
            const [c1, c2] = COLORES_CARA[i % 4];
            return (
              <div key={i} style={{ width: lado, height: lado, marginLeft: i ? -34 * U : 0, borderRadius: '50%', border: `${8 * U}px solid #FFFFFF`, boxSizing: 'border-box',
                                    background: `linear-gradient(160deg, ${c1}, ${c2})`, boxShadow: SOMBRA(U), transform: `scale(${Math.max(0, qi).toFixed(4)}) translateY(${(Math.sin(t * 2 + i) * 4 * U).toFixed(1)}px)`,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 70 * U, zIndex: n - i }}>
                {nombre ? nombre.slice(0, 1).toUpperCase() : <svg width={lado * 0.5} height={lado * 0.5} viewBox="0 0 24 24"><circle cx={12} cy={8} r={5} fill="rgba(255,255,255,.9)" /><path d="M2 23 Q12 10 22 23 Z" fill="rgba(255,255,255,.9)" /></svg>}
              </div>
            );
          })}
          {extra && <div style={{ width: lado, height: lado, marginLeft: -34 * U, borderRadius: '50%', border: `${8 * U}px solid #FFFFFF`, boxSizing: 'border-box', background: LILA_F,
                                  color: LILA, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 52 * U,
                                  transform: `scale(${Math.max(0, R(0.5, { damping: 10 })).toFixed(4)})` }}>{extra}</div>}
        </div>
        <div style={{ position: 'absolute', left: 30 * U, right: 30 * U, top: 290 * U, display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 12 * U }}>
          {nombres.slice(0, 4).map((x, i) => (
            <div key={i} style={{ padding: `${10 * U}px ${22 * U}px`, borderRadius: 999, background: '#F2F3F8', fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 30 * U, color: TINTA,
                                  opacity: clamp((t - 0.35 - i * 0.1) / 0.2), transform: `translateY(${((1 - easeOut((t - 0.35 - i * 0.1) / 0.3)) * 20 * U).toFixed(1)}px)` }}>{x}</div>
          ))}
        </div>
        {etiqueta && <div style={{ position: 'absolute', left: 0, right: 0, bottom: 44 * U, textAlign: 'center', fontFamily: FAMILIA.inter, fontWeight: 600, fontSize: 34 * U, color: '#8A8E9C' }}>{etiqueta}</div>}
      </div>
      {['red_heart', 'clapping_hands', 'fire'].map((e, i) => {
        const u = ((t - 0.4 - i * 0.25) * 0.55) % 1;
        if (t < 0.4 + i * 0.25) return null;
        return <div key={e} style={{ position: 'absolute', left: x0 + w - 60 * U + i * 30 * U, top: y0 + 80 * U - u * 260 * U, opacity: 1 - u, transform: `scale(${(0.6 + 0.4 * (1 - u)).toFixed(3)})` }}>
          <EmojiAnimado id={e} lado={80 * U} /></div>;
      })}
    </AbsoluteFill>
  );
};

/* música: «sonando ahora» con su portada, el ecualizador, la barra que avanza y el botón que se pulsa */
export const MusicaW: React.FC<{ cy: number; titulo?: string; sub?: string }> = ({ cy, titulo = '', sub = 'Live' }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = 860 * U, h = 380 * U, x0 = width / 2 - w / 2, y0 = cy - h / 2;
  const q = R(0.05, { damping: 12, stiffness: 120 });
  const suena = t > 0.75;
  const lado = 250 * U;
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, borderRadius: 48 * U, background: '#FFFFFF', boxShadow: SOMBRA(U), transform: `scale(${Math.max(0.001, q).toFixed(4)})` }}>
        <div style={{ position: 'absolute', left: 50 * U, top: (h - lado) / 2, width: lado, height: lado, borderRadius: 32 * U, background: 'linear-gradient(150deg,#7B5CF5,#2F5BE7 60%,#1FB5E8)',
                      display: 'flex', alignItems: 'flex-end', justifyContent: 'center', gap: 10 * U, padding: `0 0 ${50 * U}px`, boxSizing: 'border-box', overflow: 'hidden' }}>
          {Array.from({ length: 5 }).map((_, i) => <div key={i} style={{ width: 18 * U, borderRadius: 9 * U, background: 'rgba(255,255,255,.9)',
                                                                         height: (40 + 90 * Math.abs(Math.sin(t * (suena ? 7 : 1.5) + i * 1.3))) * U }} />)}
        </div>
        <div style={{ position: 'absolute', left: 50 * U + lado + 40 * U, right: 160 * U, top: 80 * U }}>
          <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 50 * U, color: TINTA, lineHeight: 1.08, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' } as React.CSSProperties}>{titulo}</div>
          <div style={{ marginTop: 12 * U, display: 'flex', alignItems: 'center', gap: 10 * U, fontFamily: FAMILIA.inter, fontWeight: 600, fontSize: 30 * U, color: '#8A8E9C' }}>
            <span style={{ width: 14 * U, height: 14 * U, borderRadius: '50%', background: ROJO, opacity: Math.sin(t * 8) > 0 ? 1 : 0.4 }} />{sub}
          </div>
          <div style={{ marginTop: 34 * U, height: 10 * U, borderRadius: 5 * U, background: '#ECEDF3' }}>
            <div style={{ width: `${(20 + 60 * clamp((t - 0.75) / 3)).toFixed(1)}%`, height: '100%', borderRadius: 5 * U, background: AZUL }} />
          </div>
        </div>
        <div style={{ position: 'absolute', right: 44 * U, top: h / 2 - 50 * U, width: 100 * U, height: 100 * U, borderRadius: '50%', background: TINTA, color: '#fff',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 40 * U, fontFamily: FAMILIA.inter, fontWeight: 800 }}>{suena ? '❚❚' : '▶'}</div>
      </div>
      {[0, 1, 2].map(i => {
        const u = ((t * 0.5 + i * 0.33) % 1);
        return <div key={i} style={{ position: 'absolute', left: x0 + 80 * U + i * 110 * U + Math.sin(u * 6) * 20 * U, top: y0 - 30 * U - u * 220 * U, opacity: (1 - u) * clamp((t - 0.3) * 3),
                                     fontSize: (60 - i * 8) * U, color: [LILA, AZUL, '#1FB5E8'][i] }}>♪</div>;
      })}
      <CursorR desde={[width * 0.88, cy + 560 * U]} hasta={[x0 + w - 94 * U, y0 + h / 2 + 4 * U]} t0={0.3} t1={0.72} />
    </AbsoluteFill>
  );
};

/* premio: el trofeo en su halo dorado, el confeti y la tarjeta con lo que se gana */
export const PremioW: React.FC<{ cy: number; titulo?: string; sub?: string; icono?: string }> = ({ cy, titulo = '', sub = '', icono = 'trophy' }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const q = R(0.05, { damping: 9, stiffness: 150 });
  const qc = R(0.3, { damping: 12, stiffness: 130 });
  const cx = width / 2, ty = cy - 170 * U;
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: cx - 260 * U, top: ty - 260 * U, width: 520 * U, height: 520 * U, borderRadius: '50%',
                    background: 'radial-gradient(circle, rgba(247,183,49,.45) 0%, rgba(247,183,49,0) 66%)', transform: `scale(${(0.9 + 0.1 * Math.sin(t * 2.5)).toFixed(4)})` }} />
      {Array.from({ length: 18 }).map((_, i) => {
        const a = (i / 18) * Math.PI * 2 + 0.3;
        const u = easeOut((t - 0.2) / 1.1);
        const d = (120 + (i % 3) * 70) * U * u;
        return <div key={i} style={{ position: 'absolute', left: cx + Math.cos(a) * d, top: ty + Math.sin(a) * d + u * u * 120 * U, width: 18 * U, height: 30 * U, borderRadius: 4 * U,
                                     background: [ORO, LILA, AZUL, ROJO, '#2FD27A'][i % 5], opacity: (1 - clamp((t - 1.2) / 0.8)) * clamp(u * 5),
                                     transform: `rotate(${(a * 57 + t * 360 * (i % 2 ? 1 : -1)).toFixed(0)}deg)` }} />;
      })}
      <div style={{ position: 'absolute', left: cx - 160 * U, top: ty - 160 * U, transform: `scale(${Math.max(0.001, q).toFixed(4)}) rotate(${(Math.sin(t * 2) * 4).toFixed(2)}deg)` }}>
        <EmojiAnimado id={icono} lado={320 * U} />
      </div>
      <div style={{ position: 'absolute', left: cx - 400 * U, top: cy + 60 * U, width: 800 * U, padding: `${36 * U}px ${44 * U}px`, borderRadius: 44 * U, background: '#FFFFFF',
                    boxShadow: SOMBRA(U), boxSizing: 'border-box', textAlign: 'center', transform: `translateY(${((1 - qc) * 120 * U).toFixed(1)}px)`, opacity: clamp(qc * 1.5) }}>
        <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 56 * U, color: TINTA, lineHeight: 1.08 }}>{titulo}</div>
        {sub && <div style={{ marginTop: 10 * U, fontFamily: FAMILIA.inter, fontWeight: 600, fontSize: 32 * U, color: '#8A8E9C' }}>{sub}</div>}
      </div>
      <Estrella x={cx - 300 * U} y={ty - 120 * U} lado={60 * U} t0={0.25} />
      <Estrella x={cx + 290 * U} y={ty - 40 * U} lado={48 * U} t0={0.35} />
      <Estrella x={cx + 230 * U} y={ty + 150 * U} lado={36 * U} t0={0.45} />
    </AbsoluteFill>
  );
};

/* compartir: la hoja de compartir, las apps, el toque y «enviado» */
export const CompartirW: React.FC<{ cy: number; titulo?: string; listo?: string; iconos?: string[] }> = ({ cy, titulo = 'Share', listo = 'Sent', iconos }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = 860 * U, h = 520 * U, x0 = width / 2 - w / 2, y0 = cy - h / 2;
  const q = R(0.05, { damping: 14, stiffness: 120 });
  const apps = [...(iconos || []), 'speech_balloon', 'camera', 'red_heart', 'sparkles'].filter((x, i, a) => a.indexOf(x) === i).slice(0, 4);
  const fondos = ['#E7F8EE', '#FFF0E6', '#FDEBF1', '#ECE8FF'];
  const hecho = R(1.0, { damping: 11 });
  const paso = 170 * U;
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, borderRadius: 48 * U, background: '#FFFFFF', boxShadow: SOMBRA(U),
                    transform: `translateY(${((1 - q) * 200 * U).toFixed(1)}px)`, opacity: clamp(q * 1.6) }}>
        <div style={{ position: 'absolute', left: w / 2 - 50 * U, top: 22 * U, width: 100 * U, height: 10 * U, borderRadius: 5 * U, background: '#E2E4EC' }} />
        <div style={{ position: 'absolute', left: 50 * U, top: 60 * U, fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 46 * U, color: TINTA }}>{titulo}</div>
        <div style={{ position: 'absolute', left: 50 * U, right: 50 * U, top: 150 * U, display: 'flex', justifyContent: 'space-between' }}>
          {apps.map((e, i) => {
            const qi = R(0.15 + i * 0.07, { damping: 10, stiffness: 170 });
            return <div key={e} style={{ width: 150 * U, height: 150 * U, borderRadius: 40 * U, background: fondos[i], display: 'flex', alignItems: 'center', justifyContent: 'center',
                                         transform: `scale(${(Math.max(0, qi) * (i === 0 && t > 0.68 && t < 0.8 ? 0.9 : 1)).toFixed(4)})` }}><EmojiAnimado id={e} lado={96 * U} /></div>;
          })}
        </div>
        <div style={{ position: 'absolute', left: 50 * U, right: 50 * U, top: 340 * U, height: 110 * U, borderRadius: 28 * U, background: '#F2F3F8', display: 'flex', alignItems: 'center',
                      padding: `0 ${30 * U}px`, gap: 16 * U, boxSizing: 'border-box' }}>
          {[0, 1, 2, 3, 4].map(i => <div key={i} style={{ width: 64 * U, height: 64 * U, borderRadius: '50%', background: `linear-gradient(160deg, ${COLORES_CARA[i % 4][0]}, ${COLORES_CARA[i % 4][1]})`,
                                                          border: `${4 * U}px solid #fff`, marginLeft: i ? -20 * U : 0 }} />)}
          <div style={{ marginLeft: 'auto', fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 30 * U, color: '#8A8E9C' }}>+24</div>
        </div>
      </div>
      <div style={{ position: 'absolute', left: width / 2, top: y0 - 110 * U, transform: `translateX(-50%) scale(${Math.max(0, hecho).toFixed(4)})` }}>
        <Pastilla style={{ color: '#1FAF62' }}>✓ {listo}</Pastilla>
      </div>
      <CursorR desde={[width * 0.86, cy + 580 * U]} hasta={[x0 + 50 * U + 75 * U, y0 + 150 * U + 75 * U]} t0={0.25} t1={0.68} />
      {paso ? null : null}
    </AbsoluteFill>
  );
};

/* el aviso (la general): una notificación con su icono, quién/qué y lo importante; detrás, dos más apiladas; la campana con su número */
export const AvisoW: React.FC<{ cy: number; icono?: string; app?: string; hora?: string; titulo?: string; cuerpo?: string }> =
  ({ cy, icono = 'bell', app = '', hora = '', titulo = '', cuerpo = '' }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = 900 * U, h = 300 * U, x0 = width / 2 - w / 2, y0 = cy - h / 2;
  const q = R(0.1, { damping: 12, stiffness: 140 });
  const qb = R(0.02, { damping: 8, stiffness: 160 });
  const tarjeta = (k: number) => {
    const qk = k === 0 ? q : R(0.02 + 0.05 * k, { damping: 14, stiffness: 120 });
    return (
      <div key={k} style={{ position: 'absolute', left: x0 + k * 30 * U, top: y0 + k * 34 * U, width: w - k * 60 * U, height: h, borderRadius: 44 * U,
                            background: k === 0 ? '#FFFFFF' : `rgba(255,255,255,${(0.75 - 0.25 * k).toFixed(2)})`, boxShadow: k === 0 ? SOMBRA(U) : 'none',
                            transform: `translateY(${((1 - qk) * -160 * U).toFixed(1)}px)`, opacity: clamp(qk * 1.5), zIndex: 5 - k }}>
        {k === 0 && <>
          <div style={{ position: 'absolute', left: 40 * U, top: 50 * U, width: 170 * U, height: 170 * U, borderRadius: 44 * U, background: LILA_F, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <EmojiAnimado id={icono} lado={124 * U} />
          </div>
          <div style={{ position: 'absolute', left: 240 * U, right: 44 * U, top: 52 * U }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: FAMILIA.inter, fontWeight: 600, fontSize: 26 * U, color: '#9A9CA8', letterSpacing: '0.04em' }}>
              <span>{app.toUpperCase()}</span><span>{hora}</span>
            </div>
            <div style={{ marginTop: 8 * U, fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 58 * U, color: TINTA, lineHeight: 1.1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{titulo}</div>
            <div style={{ marginTop: 6 * U, fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 38 * U, color: '#6B6F7D', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{cuerpo}</div>
          </div>
        </>}
      </div>
    );
  };
  return (
    <AbsoluteFill>
      {[2, 1, 0].map(tarjeta)}
      <div style={{ position: 'absolute', left: x0 + w - 120 * U, top: y0 - 190 * U, transform: `scale(${Math.max(0, qb).toFixed(4)}) rotate(${(Math.sin(t * 9) * 12 * Math.max(0, 1 - t / 1.2)).toFixed(2)}deg)`,
                    transformOrigin: '50% 10%' }}>
        <EmojiAnimado id="bell" lado={150 * U} />
        <div style={{ position: 'absolute', right: -6 * U, top: 4 * U, minWidth: 54 * U, height: 54 * U, borderRadius: 27 * U, background: ROJO, color: '#fff', display: 'flex',
                      alignItems: 'center', justifyContent: 'center', fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 32 * U, border: `${4 * U}px solid #fff`,
                      transform: `scale(${Math.max(0, R(0.4, { damping: 9 })).toFixed(4)})` }}>3</div>
      </div>
      <Estrella x={x0 - 10 * U} y={y0 - 60 * U} lado={48 * U} t0={0.4} />
    </AbsoluteFill>
  );
};

/* ================================================================================================================================================
   v5.5.9 · MÁS TARJETAS GENERALES (el usuario: «repite mucho los motions completo»): las de relleno ya no son siempre las mismas tres.
   Lista con ✓, buscador, publicación, encuesta, carga, nota, antes/después, cuenta atrás, gráfica y el GOLPE (solo la palabra, enorme). */

/* foto (un fotograma del video del usuario) que cubre su caja, o nada */
const Foto: React.FC<{ src?: string; style?: React.CSSProperties; gris?: boolean }> = ({ src, style, gris }) =>
  src ? <img src={src} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', filter: gris ? 'grayscale(1) contrast(.9) brightness(.95)' : undefined, ...style }} /> : null;

/* lista con ✓: las cosas que se nombran, marcándose una a una */
export const ListaW: React.FC<{ cy: number; titulo?: string; items?: string[] }> = ({ cy, titulo = '', items = [] }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const filas = items.slice(0, 4);
  const w = 820 * U, fila = 108 * U, h = 140 * U + filas.length * fila, x0 = width / 2 - w / 2, y0 = cy - h / 2;
  const q = R(0.05, { damping: 13, stiffness: 130 });
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, borderRadius: 46 * U, background: '#FFFFFF', boxShadow: SOMBRA(U), transform: `scale(${Math.max(0.001, q).toFixed(4)})` }}>
        <div style={{ position: 'absolute', left: 50 * U, top: 44 * U, fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 44 * U, color: TINTA }}>{titulo}</div>
        {filas.map((x, i) => {
          const t0 = 0.25 + i * 0.22;
          const marca = easeOut((t - t0 - 0.12) / 0.25);
          const entra = easeOut((t - t0) / 0.3);
          return (
            <div key={i} style={{ position: 'absolute', left: 50 * U, right: 50 * U, top: 130 * U + i * fila, height: fila - 20 * U, display: 'flex', alignItems: 'center', gap: 26 * U,
                                  opacity: clamp(entra * 1.4), transform: `translateX(${((1 - entra) * 40 * U).toFixed(1)}px)` }}>
              <div style={{ width: 62 * U, height: 62 * U, borderRadius: 18 * U, border: `${4 * U}px solid ${marca > 0.5 ? AZUL : '#D9DCE6'}`, background: marca > 0.5 ? AZUL : '#fff',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 40 * U, fontWeight: 800, transform: `scale(${(1 + 0.18 * Math.sin(Math.PI * marca)).toFixed(3)})` }}>
                {marca > 0.5 ? '✓' : ''}
              </div>
              <div style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 44 * U, color: marca > 0.5 ? '#8A8E9C' : TINTA, position: 'relative' }}>
                {x}
                <span style={{ position: 'absolute', left: 0, top: '54%', height: 4 * U, background: '#B9BDCB', width: `${(clamp((marca - 0.5) * 2) * 100).toFixed(1)}%` }} />
              </div>
            </div>
          );
        })}
      </div>
      <Estrella x={x0 + w + 10 * U} y={y0 + 30 * U} lado={50 * U} t0={0.3} />
    </AbsoluteFill>
  );
};

/* buscador: lo que se dice se escribe en la barra, y caen los resultados */
export const BuscadorW: React.FC<{ cy: number; consulta?: string; resultados?: string[] }> = ({ cy, consulta = '', resultados = [] }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = 860 * U, x0 = width / 2 - w / 2, y0 = cy - 300 * U;
  const q = R(0.05, { damping: 13, stiffness: 140 });
  const n = Math.round(consulta.length * clamp((t - 0.15) / Math.max(0.4, consulta.length * 0.035)));
  const escrito = consulta.slice(0, n);
  const fin = 0.15 + Math.max(0.4, consulta.length * 0.035);
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: 130 * U, borderRadius: 65 * U, background: '#FFFFFF', boxShadow: SOMBRA(U), display: 'flex', alignItems: 'center',
                    gap: 24 * U, padding: `0 ${40 * U}px`, boxSizing: 'border-box', transform: `scale(${Math.max(0.001, q).toFixed(4)})` }}>
        <svg width={52 * U} height={52 * U} viewBox="0 0 24 24"><circle cx={10} cy={10} r={7} fill="none" stroke="#8A8E9C" strokeWidth={2.6} /><line x1={15} y1={15} x2={22} y2={22} stroke="#8A8E9C" strokeWidth={2.6} strokeLinecap="round" /></svg>
        <div style={{ flex: 1, fontFamily: FAMILIA.inter, fontWeight: 600, fontSize: 46 * U, color: TINTA, whiteSpace: 'nowrap', overflow: 'hidden' }}>
          {escrito}<span style={{ display: 'inline-block', width: 4 * U, height: 52 * U, marginLeft: 4 * U, verticalAlign: 'middle', background: AZUL, opacity: Math.sin(t * 9) > 0 ? 1 : 0 }} />
        </div>
      </div>
      {resultados.slice(0, 3).map((x, i) => {
        const e = easeOut((t - fin - 0.1 - i * 0.12) / 0.35);
        return (
          <div key={i} style={{ position: 'absolute', left: x0 + 20 * U, width: w - 40 * U, top: y0 + 170 * U + i * 140 * U, height: 118 * U, borderRadius: 30 * U, background: '#FFFFFF',
                                boxShadow: SOMBRA(U), display: 'flex', alignItems: 'center', gap: 24 * U, padding: `0 ${32 * U}px`, boxSizing: 'border-box',
                                opacity: clamp(e * 1.5), transform: `translateY(${((1 - e) * -40 * U).toFixed(1)}px)` }}>
            <div style={{ width: 64 * U, height: 64 * U, borderRadius: 18 * U, background: [LILA_F, '#E7F8EE', '#FFF0E6'][i], display: 'flex', alignItems: 'center', justifyContent: 'center',
                          color: [LILA, '#1FAF62', '#F26B1D'][i], fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 34 * U }}>{x.slice(0, 1).toUpperCase()}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 38 * U, color: i === 0 ? AZUL : TINTA }}>{x}</div>
              <div style={{ marginTop: 8 * U, height: 12 * U, width: `${70 - i * 14}%`, borderRadius: 6 * U, background: '#ECEDF3' }} />
            </div>
          </div>
        );
      })}
      <CursorR desde={[width * 0.86, cy + 560 * U]} hasta={[x0 + 200 * U, y0 + 230 * U]} t0={fin} t1={fin + 0.4} />
    </AbsoluteFill>
  );
};

/* publicación: la foto (del video), el corazón que late y los «me gusta» que suben */
export const PostW: React.FC<{ cy: number; usuario?: string; texto?: string; likes?: number; foto?: string; megusta?: string }> =
  ({ cy, usuario = '', texto = '', likes = 1240, foto, megusta = 'likes' }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = 680 * U, h = 860 * U, x0 = width / 2 - w / 2, y0 = cy - h / 2 + 20 * U;
  const q = R(0.05, { damping: 12, stiffness: 120 });
  const late = R(0.6, { damping: 8, stiffness: 220 });
  const n = Math.round(likes * (0.6 + 0.4 * suave(clamp((t - 0.6) / 1.2))));
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, borderRadius: 44 * U, background: '#FFFFFF', boxShadow: SOMBRA(U), overflow: 'hidden',
                    transform: `scale(${Math.max(0.001, q).toFixed(4)}) rotate(${((1 - q) * -4).toFixed(2)}deg)` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 18 * U, padding: `${26 * U}px ${30 * U}px` }}>
          <div style={{ width: 64 * U, height: 64 * U, borderRadius: '50%', background: `linear-gradient(135deg, #F7B731, #F0473C, ${LILA})`, padding: 4 * U, boxSizing: 'border-box' }}>
            <div style={{ width: '100%', height: '100%', borderRadius: '50%', background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: FAMILIA.inter,
                          fontWeight: 800, fontSize: 26 * U, color: TINTA }}>{(usuario || '·').slice(0, 1).toUpperCase()}</div>
          </div>
          <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 32 * U, color: TINTA }}>{usuario}</div>
        </div>
        <div style={{ position: 'relative', height: h * 0.62, background: `linear-gradient(160deg, ${AZUL}, ${LILA})`, overflow: 'hidden' }}>
          <Foto src={foto} />
          <div style={{ position: 'absolute', left: '50%', top: '50%', transform: `translate(-50%,-50%) scale(${(Math.max(0, late) * (t < 1.4 ? 1 : 0)).toFixed(3)})`, opacity: clamp((1.4 - t) * 3) }}>
            <EmojiAnimado id="red_heart" lado={220 * U} />
          </div>
        </div>
        <div style={{ padding: `${24 * U}px ${30 * U}px` }}>
          <div style={{ display: 'flex', gap: 26 * U, fontSize: 48 * U }}>
            <span style={{ color: t > 0.6 ? ROJO : TINTA, transform: `scale(${(1 + 0.3 * Math.sin(Math.PI * clamp((t - 0.6) / 0.3))).toFixed(3)})`, display: 'inline-block' }}>{t > 0.6 ? '♥' : '♡'}</span>
            <span style={{ color: TINTA }}>💬</span><span style={{ color: TINTA }}>➤</span>
          </div>
          <div style={{ marginTop: 12 * U, fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 34 * U, color: TINTA }}>{n.toLocaleString('en-US')} {megusta}</div>
          <div style={{ marginTop: 6 * U, fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 30 * U, color: '#555A6A', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{texto}</div>
        </div>
      </div>
      {[0, 1, 2, 3].map(i => {
        const u = ((t - 0.7 - i * 0.2) * 0.7) % 1;
        if (t < 0.7 + i * 0.2) return null;
        return <div key={i} style={{ position: 'absolute', left: x0 + w - 40 * U + Math.sin(u * 7 + i) * 30 * U, top: y0 + h * 0.75 - u * 420 * U, opacity: 1 - u, fontSize: (54 - i * 6) * U, color: ROJO }}>♥</div>;
      })}
    </AbsoluteFill>
  );
};

/* encuesta: dos opciones, el clic y las barras que se llenan */
export const EncuestaW: React.FC<{ cy: number; pregunta?: string; opciones?: string[]; pcts?: number[] }> = ({ cy, pregunta = '', opciones = ['A', 'B'], pcts = [64, 36] }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = 840 * U, h = 520 * U, x0 = width / 2 - w / 2, y0 = cy - h / 2;
  const q = R(0.05, { damping: 13, stiffness: 130 });
  const llena = suave(clamp((t - 0.75) / 0.7));
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, borderRadius: 46 * U, background: '#FFFFFF', boxShadow: SOMBRA(U), transform: `scale(${Math.max(0.001, q).toFixed(4)})` }}>
        <div style={{ position: 'absolute', left: 50 * U, right: 50 * U, top: 44 * U, fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 44 * U, color: TINTA, lineHeight: 1.1 }}>{pregunta}</div>
        {opciones.slice(0, 2).map((o, i) => {
          const p = pcts[i] ?? 50;
          const gana = p >= (pcts[1 - i] ?? 0);
          return (
            <div key={i} style={{ position: 'absolute', left: 50 * U, right: 50 * U, top: 190 * U + i * 140 * U, height: 110 * U, borderRadius: 30 * U, background: '#F2F3F8', overflow: 'hidden',
                                  border: `${4 * U}px solid ${gana && llena > 0 ? AZUL : 'transparent'}` }}>
              <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${(p * llena).toFixed(1)}%`, background: gana ? LILA_F : '#E4E6EE' }} />
              <div style={{ position: 'absolute', left: 30 * U, right: 30 * U, top: 0, bottom: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                            fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 40 * U, color: TINTA }}>
                <span>{o}</span><span style={{ opacity: clamp(llena * 3), color: gana ? AZUL : '#8A8E9C' }}>{Math.round(p * llena)}%</span>
              </div>
            </div>
          );
        })}
      </div>
      <CursorR desde={[width * 0.86, cy + 560 * U]} hasta={[x0 + w - 160 * U, y0 + 245 * U]} t0={0.25} t1={0.7} />
    </AbsoluteFill>
  );
};

/* carga: la barra que avanza con su %, el texto de lo que se está haciendo y el ✓ al final */
export const CargaW: React.FC<{ cy: number; etiqueta?: string; pct?: number }> = ({ cy, etiqueta = '', pct = 100 }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = 840 * U, h = 330 * U, x0 = width / 2 - w / 2, y0 = cy - h / 2;
  const q = R(0.05, { damping: 13, stiffness: 130 });
  const v = pct * suave(clamp((t - 0.2) / 1.3));
  const listo = v >= 99.5;
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, borderRadius: 46 * U, background: '#FFFFFF', boxShadow: SOMBRA(U), transform: `scale(${Math.max(0.001, q).toFixed(4)})` }}>
        <div style={{ position: 'absolute', left: 50 * U, right: 50 * U, top: 50 * U, display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <div style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 40 * U, color: TINTA }}>{etiqueta}</div>
          <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 64 * U, color: listo ? '#1FAF62' : AZUL, fontVariantNumeric: 'tabular-nums' }}>{listo ? '✓' : `${Math.round(v)}%`}</div>
        </div>
        <div style={{ position: 'absolute', left: 50 * U, right: 50 * U, top: 190 * U, height: 44 * U, borderRadius: 22 * U, background: '#ECEDF3', overflow: 'hidden' }}>
          <div style={{ width: `${v.toFixed(2)}%`, height: '100%', borderRadius: 22 * U, background: listo ? '#1FAF62' : `linear-gradient(90deg, ${AZUL}, ${LILA})`,
                        backgroundImage: listo ? undefined : `repeating-linear-gradient(-45deg, rgba(255,255,255,.18) 0 ${14 * U}px, transparent ${14 * U}px ${28 * U}px), linear-gradient(90deg, ${AZUL}, ${LILA})`,
                        backgroundPosition: `${(t * 60 * U).toFixed(1)}px 0` }} />
        </div>
      </div>
      {listo && <Estrella x={x0 + w - 40 * U} y={y0 - 10 * U} lado={60 * U} t0={1.5} />}
    </AbsoluteFill>
  );
};

/* nota: el papelito amarillo con lo importante, a mano, y la chincheta */
export const NotaW: React.FC<{ cy: number; lineas?: string[] }> = ({ cy, lineas = [] }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = 640 * U, h = 640 * U, x0 = width / 2 - w / 2, y0 = cy - h / 2;
  const q = R(0.05, { damping: 10, stiffness: 140 });
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, background: 'linear-gradient(170deg,#FFF3A8,#FFE36E)', borderRadius: 10 * U,
                    boxShadow: `0 ${30 * U}px ${60 * U}px rgba(120,100,20,.25)`, transform: `rotate(${(-3 + (1 - q) * -10).toFixed(2)}deg) scale(${Math.max(0.001, q).toFixed(4)})`,
                    padding: `${110 * U}px ${56 * U}px`, boxSizing: 'border-box' }}>
        {lineas.slice(0, 4).map((x, i) => {
          const e = clamp((t - 0.25 - i * 0.28) / 0.3);
          return (
            <div key={i} style={{ fontFamily: FAMILIA.mano, fontSize: 76 * U, color: '#3B3315', lineHeight: 1.15, clipPath: `inset(0 ${((1 - e) * 100).toFixed(1)}% 0 0)` }}>
              {i === 0 ? <span style={{ background: `linear-gradient(transparent 60%, rgba(240,71,60,.35) 60%)` }}>{x}</span> : x}
            </div>
          );
        })}
      </div>
      <div style={{ position: 'absolute', left: width / 2 - 34 * U, top: y0 - 30 * U, transform: `scale(${Math.max(0, R(0.15, { damping: 9 })).toFixed(4)})` }}>
        <svg width={68 * U} height={68 * U} viewBox="0 0 24 24"><circle cx={12} cy={10} r={8} fill={ROJO} stroke="#fff" strokeWidth={1.5} /><circle cx={9.5} cy={7.5} r={2.4} fill="rgba(255,255,255,.6)" /></svg>
      </div>
    </AbsoluteFill>
  );
};

/* antes / después: el mismo fotograma apagado y vivo, con el deslizador que pasa */
export const AntesDespuesW: React.FC<{ cy: number; foto?: string; antes?: string; despues?: string }> = ({ cy, foto, antes = 'Before', despues = 'After' }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = 840 * U, h = 680 * U, x0 = width / 2 - w / 2, y0 = cy - h / 2;
  const q = R(0.05, { damping: 13, stiffness: 120 });
  const corte = 0.92 - 0.84 * suave(clamp((t - 0.35) / 1.1));
  const fondo = foto ? undefined : `linear-gradient(160deg, ${AZUL}, ${LILA})`;
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, borderRadius: 46 * U, overflow: 'hidden', boxShadow: SOMBRA(U), border: `${8 * U}px solid #fff`,
                    transform: `scale(${Math.max(0.001, q).toFixed(4)})`, background: fondo }}>
        <Foto src={foto} />
        <div style={{ position: 'absolute', inset: 0, clipPath: `inset(0 ${((1 - corte) * 100).toFixed(2)}% 0 0)`, background: foto ? undefined : '#B9BDCB' }}>
          <Foto src={foto} gris />
        </div>
        <div style={{ position: 'absolute', top: 0, bottom: 0, left: `${(corte * 100).toFixed(2)}%`, width: 6 * U, marginLeft: -3 * U, background: '#fff' }} />
        <div style={{ position: 'absolute', top: '50%', left: `${(corte * 100).toFixed(2)}%`, width: 90 * U, height: 90 * U, marginLeft: -45 * U, marginTop: -45 * U, borderRadius: '50%',
                      background: '#fff', boxShadow: SOMBRA(U), display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 40 * U, color: TINTA, fontWeight: 800 }}>⟷</div>
        <div style={{ position: 'absolute', left: 30 * U, top: 30 * U }}><Pastilla style={{ fontSize: 30 * U, padding: `${8 * U}px ${22 * U}px`, color: '#555A6A' }}>{antes}</Pastilla></div>
        <div style={{ position: 'absolute', right: 30 * U, top: 30 * U, opacity: clamp((t - 0.6) * 3) }}>
          <Pastilla style={{ fontSize: 30 * U, padding: `${8 * U}px ${22 * U}px`, color: '#fff', background: AZUL }}>{despues}</Pastilla>
        </div>
      </div>
      <Estrella x={x0 + w - 20 * U} y={y0 + h - 10 * U} lado={52 * U} t0={1.2} />
    </AbsoluteFill>
  );
};

/* cuenta atrás: los números que caen en su sitio */
export const CuentaW: React.FC<{ cy: number; valores?: string[]; etiquetas?: string[] }> = ({ cy, valores = ['03', '12', '45'], etiquetas = ['days', 'hrs', 'min'] }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const n = Math.min(3, valores.length);
  const lado = 230 * U, sep = 30 * U, total = n * lado + (n - 1) * sep, x0 = width / 2 - total / 2;
  return (
    <AbsoluteFill>
      {valores.slice(0, n).map((v, i) => {
        const q = R(0.05 + i * 0.1, { damping: 12, stiffness: 150 });
        const ultimo = i === n - 1;
        const s = ultimo ? Math.max(0, parseInt(v, 10) - Math.floor(Math.max(0, t - 0.6) * 1.6)) : null;
        const txt = ultimo && s !== null && !isNaN(s) ? String(s).padStart(2, '0') : v;
        const tic = ultimo ? (t * 1.6) % 1 : 1;
        return (
          <div key={i} style={{ position: 'absolute', left: x0 + i * (lado + sep), top: cy - lado / 2 - 40 * U, width: lado, transform: `translateY(${((1 - q) * 200 * U).toFixed(1)}px)`, opacity: clamp(q * 1.5) }}>
            <div style={{ height: lado, borderRadius: 40 * U, background: i === n - 1 ? TINTA : '#FFFFFF', boxShadow: SOMBRA(U), display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 130 * U, color: i === n - 1 ? '#fff' : TINTA, fontVariantNumeric: 'tabular-nums', overflow: 'hidden' }}>
              <span style={{ transform: `translateY(${(ultimo && tic < 0.25 ? (1 - tic / 0.25) * -40 * U : 0).toFixed(1)}px)`, display: 'inline-block' }}>{txt}</span>
            </div>
            <div style={{ marginTop: 18 * U, textAlign: 'center', fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 32 * U, color: '#8A8E9C', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{etiquetas[i] || ''}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

/* gráfica: barras que suben, la última del color, la flecha y el número */
export const GraficaW: React.FC<{ cy: number; valor?: string; etiqueta?: string }> = ({ cy, valor = '+40%', etiqueta = '' }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const w = 840 * U, h = 620 * U, x0 = width / 2 - w / 2, y0 = cy - h / 2;
  const q = R(0.05, { damping: 13, stiffness: 130 });
  const alturas = [0.28, 0.4, 0.36, 0.55, 0.68, 0.95];
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: x0, top: y0, width: w, height: h, borderRadius: 46 * U, background: '#FFFFFF', boxShadow: SOMBRA(U), transform: `scale(${Math.max(0.001, q).toFixed(4)})` }}>
        <div style={{ position: 'absolute', left: 50 * U, top: 40 * U, fontFamily: FAMILIA.inter, fontWeight: 600, fontSize: 32 * U, color: '#8A8E9C' }}>{etiqueta}</div>
        <div style={{ position: 'absolute', left: 50 * U, top: 84 * U, fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 84 * U, color: '#1FAF62', opacity: clamp((t - 0.9) * 3) }}>{valor} ↗</div>
        <div style={{ position: 'absolute', left: 60 * U, right: 60 * U, bottom: 60 * U, height: 330 * U, display: 'flex', alignItems: 'flex-end', gap: 26 * U }}>
          {alturas.map((a, i) => {
            const e = R(0.2 + i * 0.09, { damping: 12, stiffness: 140 });
            return <div key={i} style={{ flex: 1, height: `${(a * 100 * Math.max(0, e)).toFixed(1)}%`, borderRadius: 18 * U,
                                         background: i === alturas.length - 1 ? `linear-gradient(180deg, ${AZUL}, ${LILA})` : '#E4E6EE' }} />;
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* el GOLPE: solo la palabra clave, enorme, en cursiva, con su subrayado que se dibuja y destellos (los momentos fuertes; pocos) */
export const GolpeW: React.FC<{ cy: number; palabra?: string; antes?: string }> = ({ cy, palabra = '', antes = '' }) => {
  const t = useT();
  const U = useU();
  const { width } = useVideoConfig();
  const R = useResorte();
  const q = R(0.0, { damping: 9, stiffness: 170 });
  const largo = Math.max(3, palabra.length);
  const tam = Math.min(300, (width / U) * 1.55 / largo) * U;
  const raya = easeOut((t - 0.25) / 0.45);
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ position: 'absolute', top: cy - tam * 0.95, left: 0, right: 0, textAlign: 'center' }}>
        {antes && <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 70 * U, color: TINTA, opacity: clamp(q * 2), marginBottom: 10 * U }}>{antes}</div>}
        <div style={{ display: 'inline-block', position: 'relative', fontFamily: FAMILIA.display, fontStyle: 'italic', fontSize: tam, lineHeight: 1, color: AZUL,
                      transform: `scale(${(0.6 + 0.4 * Math.max(0, q)).toFixed(4)}) rotate(${((1 - Math.min(1, q)) * -6).toFixed(2)}deg)`, opacity: clamp(q * 2),
                      filter: q < 0.9 ? `blur(${((1 - q) * 10).toFixed(1)}px)` : undefined }}>
          {palabra}
          <svg width="100%" height={tam * 0.32} viewBox="0 0 100 20" preserveAspectRatio="none" style={{ position: 'absolute', left: 0, bottom: -tam * 0.2 }}>
            <path d="M2 14 Q 30 4, 55 11 T 98 8" fill="none" stroke={ORO} strokeWidth={4} strokeLinecap="round" strokeDasharray="110" strokeDashoffset={110 * (1 - raya)} />
          </svg>
        </div>
      </div>
      <Estrella x={width / 2 - tam * largo * 0.24} y={cy - tam * 0.9} lado={70 * U} t0={0.2} />
      <Estrella x={width / 2 + tam * largo * 0.25} y={cy - tam * 0.2} lado={56 * U} t0={0.3} />
      <Estrella x={width / 2 + tam * largo * 0.18} y={cy - tam * 1.1} lado={40 * U} t0={0.38} />
    </AbsoluteFill>
  );
};
