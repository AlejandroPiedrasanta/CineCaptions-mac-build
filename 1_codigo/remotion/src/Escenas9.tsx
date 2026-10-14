// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/Escenas9.tsx — v5.5.3: escenas de motion graphics a PANTALLA COMPLETA (B-roll ilustrado) para explicar lo que se dice,
// de las referencias del autor. Tapan el video entero unos segundos (opacas), entran con un iris y salen con un fundido. Todo sale de las props;
// `variante` cambia el diseño (VARIANTES en edicion_pro_escenas.py). Imágenes: 'stickers/…' (Fluent), 'fluent/…' (Fluent extra), 'recortes/…'
// o una foto 'data:image/…' (un fotograma del propio video).
//   PictogramaE  un personaje-pictograma que hace lo que se dice (trabaja, piensa, celebra, corre, cae, sube, señala, le gritan) + título y,
//                si se nombra, una línea que baja hasta un icono 3D («EDITOR» → cerebro). Variante neón: el personaje de luz roja.
//   TableroE     el tablero de detective: fotos con chincheta unidas por hilo rojo y el título en estarcido en el centro
//   PolaroidE    una polaroid colgada de una cuerda con una pinza (un fotograma del video), su pie escrito a mano y la palabra gigante detrás
//   CuadernoE    el cuaderno sobre la mesa: el título a máquina, la palabra clave rodeada en rojo, la nota con chincheta y el sello
//   FechaE       el calendario en cuadrícula: el día que se dice se enciende, vuelan papeles y la nota rodeada
//   VidrioE      un icono de cristal que gira en 3D con su brillo y el título
//   ChatE        dos burbujas de cristal: «escribiendo…» y el mensaje que se dice
//   CollageE     collage de revista: el recorte en trama, formas de color y la frase con la palabra clave en rojo
//   MovilE       el móvil con un perfil: las cifras cuentan, se pulsa «Seguir» y la frase al lado
//   TijerasE     un clip de video que se vuelve cinta, unas tijeras lo cortan y salen los clips
import React from 'react';
import { AbsoluteFill, Img, staticFile, useVideoConfig } from 'remotion';
import { FAMILIA, clamp, useFuentes, useResorte, useU } from './comun';
import { easeOut, mezcla, suave, useVida } from './Kit7';
import GLIFOS from './glifos.json';

type Base = { variante?: string; acento?: string; salida?: number; idioma?: string };
const esHex = (h?: string) => /^#?[0-9a-fA-F]{6}$/.test(String(h || ''));
const hex = (h: string | undefined, def: string) => (esHex(h) ? '#' + String(h).replace('#', '') : def);
const azar = (i: number) => { const x = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); };
const lista = (s?: string) => String(s || '').split('|').map(x => x.trim()).filter(Boolean);
const src = (s?: string) => (!s ? '' : /^(data:|https?:)/.test(s) ? s : staticFile(s));
const entre = (a: number, b: number, q: number) => a + (b - a) * q;

/** Un icono plano de Tabler (MIT): relleno si existe y se pide, si no de línea. */
const Glifo: React.FC<{ nombre: string; lado: number; color: string; relleno?: boolean; grosor?: number; style?: React.CSSProperties }> =
  ({ nombre, lado, color, relleno = true, grosor = 2, style }) => {
    const G = GLIFOS as unknown as { o: Record<string, [string, Record<string, string>][]>; f: Record<string, [string, Record<string, string>][]> };
    const lleno = relleno && G.f[nombre];
    const nodos = (lleno ? G.f[nombre] : G.o[nombre] || G.o['star'] || []) as [string, Record<string, string>][];
    return (
      <svg width={lado} height={lado} viewBox="0 0 24 24" style={style} fill={lleno ? color : 'none'} stroke={lleno ? 'none' : color}
           strokeWidth={grosor} strokeLinecap="round" strokeLinejoin="round">
        {nodos.map(([tag, at], i) => React.createElement(tag, { key: i, ...at, ...(lleno ? { fill: color } : {}) }))}
      </svg>
    );
  };

/** Grano de papel/película (SVG). */
const Grano: React.FC<{ op?: number; frec?: number; id: string }> = ({ op = 0.08, frec = 0.85, id }) => (
  <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: op, mixBlendMode: 'multiply' }}>
    <filter id={id}><feTurbulence type="fractalNoise" baseFrequency={frec} numOctaves={2} stitchTiles="stitch" /><feColorMatrix type="saturate" values="0" /></filter>
    <rect width="100%" height="100%" filter={`url(#${id})`} />
  </svg>
);

/** Entrada en iris (círculo que crece desde `ox, oy` en %) y salida con fundido. Todas las escenas van dentro. */
const Escena: React.FC<{ fondo: string; salida?: number; ox?: number; oy?: number; children: React.ReactNode }> = ({ fondo, salida = 0.3, ox = 50, oy = 55, children }) => {
  const { t, q } = useVida(salida);
  const r = easeOut(t / 0.32) * 150;
  return (
    <AbsoluteFill style={{ opacity: 1 - q, clipPath: r < 149 ? `circle(${r.toFixed(2)}% at ${ox}% ${oy}%)` : undefined, background: fondo, overflow: 'hidden',
                           transform: `scale(${(1 + 0.04 * q).toFixed(4)})` }}>
      {children}
    </AbsoluteFill>
  );
};

/* ================================================================================================ PictogramaE */
type Pose = { inc: number; bL: [number, number]; bR: [number, number]; pL: [number, number]; pR: [number, number]; cab?: number };
// ángulos en grados con 0 = hacia abajo, 90 = hacia la derecha de la pantalla, 180 = hacia arriba (absolutos, no relativos)
const POSES: Record<string, Pose> = {
  parado: { inc: 0, bL: [-10, -5], bR: [10, 5], pL: [-5, -2], pR: [5, 2] },
  pensando: { inc: -3, bL: [-10, -4], bR: [40, 165], pL: [-5, -2], pR: [5, 2], cab: 10 },
  celebrando: { inc: 0, bL: [-148, -168], bR: [148, 168], pL: [-16, -4], pR: [16, 4] },
  corriendo: { inc: 14, bL: [-50, 20], bR: [50, 120], pL: [-40, 10], pR: [45, -15] },
  senalando: { inc: -2, bL: [-25, 35], bR: [94, 92], pL: [-6, -2], pR: [8, 3] },
  cayendo: { inc: 72, bL: [-165, -135], bR: [150, 118], pL: [-150, -172], pR: [165, 178] },
  subiendo: { inc: 8, bL: [-35, 10], bR: [35, 85], pL: [-30, 15], pR: [60, -20] },
  gritando: { inc: 0, bL: [-130, -172], bR: [130, 172], pL: [-7, -3], pR: [7, 3] },
  sentado: { inc: 4, bL: [55, 98], bR: [62, 100], pL: [92, 2], pR: [88, -4] },
};
const dir = (a: number): [number, number] => [Math.sin((a * Math.PI) / 180), Math.cos((a * Math.PI) / 180)];
const mezclaPose = (A: Pose, B: Pose, q: number): Pose => ({
  inc: entre(A.inc, B.inc, q), cab: entre(A.cab || 0, B.cab || 0, q),
  bL: [entre(A.bL[0], B.bL[0], q), entre(A.bL[1], B.bL[1], q)], bR: [entre(A.bR[0], B.bR[0], q), entre(A.bR[1], B.bR[1], q)],
  pL: [entre(A.pL[0], B.pL[0], q), entre(A.pL[1], B.pL[1], q)], pR: [entre(A.pR[0], B.pR[0], q), entre(A.pR[1], B.pR[1], q)],
});
/** El pictograma: tronco-cápsula, cabeza redonda, brazos y piernas gruesos con puntas redondas (estilo señalética). */
const Monigote: React.FC<{ pose: Pose; F: number; color: string; x: number; y: number; boca?: boolean; gafas?: boolean }> = ({ pose, F, color, x, y, boca, gafas }) => {
  const Lt = 0.36 * F, Lu = 0.17 * F, Lf = 0.16 * F, Lm = 0.21 * F, Ls = 0.21 * F, r = 0.088 * F;
  const td: [number, number] = [Math.sin((pose.inc * Math.PI) / 180), -Math.cos((pose.inc * Math.PI) / 180)];
  const cuello: [number, number] = [x + td[0] * Lt, y + td[1] * Lt];
  const hombro: [number, number] = [x + td[0] * Lt * 0.9, y + td[1] * Lt * 0.9];
  const ca = ((pose.inc + (pose.cab || 0)) * Math.PI) / 180;
  const cabeza: [number, number] = [cuello[0] + Math.sin(ca) * r * 1.45, cuello[1] - Math.cos(ca) * r * 1.45];
  const seg = (o: [number, number], a: number, L: number): [number, number] => { const d = dir(a); return [o[0] + d[0] * L, o[1] + d[1] * L]; };
  const brazo = (b: [number, number]) => { const c = seg(hombro, b[0], Lu); return [hombro, c, seg(c, b[1], Lf)]; };
  const pierna = (p: [number, number]) => { const c = seg([x, y], p[0], Lm); return [[x, y] as [number, number], c, seg(c, p[1], Ls)]; };
  const linea = (pts: [number, number][], w: number, k: string) => (
    <polyline key={k} points={pts.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')} fill="none" stroke={color} strokeWidth={w} strokeLinecap="round" strokeLinejoin="round" />
  );
  return (
    <g>
      {linea(pierna(pose.pL), 0.095 * F, 'pl')}{linea(pierna(pose.pR), 0.095 * F, 'pr')}
      {linea([[x, y], cuello], 0.2 * F, 't')}
      {linea(brazo(pose.bL), 0.075 * F, 'bl')}{linea(brazo(pose.bR), 0.075 * F, 'br')}
      <circle cx={cabeza[0]} cy={cabeza[1]} r={r} fill={color} />
      {boca && <ellipse cx={cabeza[0] + r * 0.15} cy={cabeza[1] + r * 0.25} rx={r * 0.32} ry={r * 0.4} fill="#000" opacity={0.85} />}
      {gafas && <g fill="none" stroke="#000" strokeWidth={r * 0.12} opacity={0.85}><circle cx={cabeza[0] - r * 0.3} cy={cabeza[1] - r * 0.05} r={r * 0.28} /><circle cx={cabeza[0] + r * 0.32} cy={cabeza[1] - r * 0.05} r={r * 0.28} /></g>}
    </g>
  );
};

export type PictogramaProps = Base & { pose?: string; texto?: string; sub?: string; imagen?: string };
export const PictogramaE: React.FC<PictogramaProps> = ({ pose = 'trabajando', texto = 'EDITOR', sub = '', imagen = '', variante = 'oscuro', acento, salida = 0.3 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU(), S = useResorte();
  const { t } = useVida(salida);
  const vert = H >= W;
  const claro = variante === 'claro', neon = variante === 'neon';
  const tinta = claro ? '#141414' : '#FFFFFF';
  const fondo = claro ? 'radial-gradient(ellipse at 50% 40%, #F2F2F0 0%, #DCDCDA 75%)' : neon ? '#050505' : 'radial-gradient(ellipse at 50% 32%, #101010 0%, #000 70%)';
  const ac = hex(acento, neon ? '#FF2A2A' : '#FFFFFF');
  const F = (vert ? 640 : 560) * U;
  const cx = vert ? W / 2 : W * 0.34, cy = vert ? H * 0.43 : H * 0.6;
  const q = easeOut((t - 0.15) / 0.5);
  const fase = t * Math.PI * 2 * 1.7;
  let figura: React.ReactNode = null;
  const base = POSES.parado;
  const conTexto = !!texto;
  if (!neon) {
    const nombre = pose === 'trabajando' || pose === 'gritando' ? 'sentado' : pose in POSES ? pose : 'parado';   // al que le gritan, sentado a su mesa
    let P = mezclaPose(base, POSES[nombre], q);
    let dy = 0;
    if (pose === 'corriendo') {
      const s = Math.sin(fase);
      P = { ...P, bL: [-50 * s, -50 * s + 70], bR: [50 * s, 50 * s + 70], pL: [-40 * s, -40 * s + (s > 0 ? 40 : 0)], pR: [40 * s, 40 * s + (s < 0 ? 40 : 0)] };
      dy = -Math.abs(Math.cos(fase)) * 0.03 * F;
    } else if (pose === 'celebrando') {
      dy = -Math.abs(Math.sin(t * Math.PI * 2.4)) * 0.08 * F * q;
    } else if (pose === 'trabajando' || pose === 'gritando') {
      const tecleo = Math.sin(t * 40) * 3;
      P = { ...P, bL: [P.bL[0], P.bL[1] + tecleo], bR: [P.bR[0], P.bR[1] - tecleo] };
    } else if (pose === 'subiendo') {
      const s = Math.sin(fase * 0.7);
      P = { ...P, pL: [-30 + 30 * s, 15], pR: [60 - 30 * s, -20] };
    }
    const sentado = pose === 'trabajando' || pose === 'gritando';
    const hx = sentado ? cx + (pose === 'gritando' ? 0.25 * F : -0.1 * F) : cx, hy = sentado ? cy + 0.12 * F : cy + 0.18 * F + dy;
    const pc = sentado ? S(0.05, { damping: 16 }) : 1;
    figura = (
      <svg width={W} height={H} style={{ position: 'absolute', inset: 0, overflow: 'visible', filter: claro ? 'none' : `drop-shadow(0 0 ${18 * U}px rgba(255,255,255,.45))` }}>
        {sentado && (
          <g opacity={clamp(pc * 2)} transform={`translate(0 ${((1 - clamp(pc)) * 60 * U).toFixed(1)})`}>
            {/* silla, mesa y portátil */}
            <rect x={hx - 0.2 * F} y={hy - 0.02 * F} width={0.24 * F} height={0.05 * F} rx={0.02 * F} fill={tinta} />
            <rect x={hx - 0.21 * F} y={hy - 0.32 * F} width={0.05 * F} height={0.32 * F} rx={0.02 * F} fill={tinta} />
            <line x1={hx - 0.08 * F} y1={hy + 0.03 * F} x2={hx - 0.08 * F} y2={hy + 0.28 * F} stroke={tinta} strokeWidth={0.035 * F} />
            <path d={`M${hx - 0.2 * F} ${hy + 0.3 * F} h${0.24 * F}`} stroke={tinta} strokeWidth={0.03 * F} strokeLinecap="round" />
            <rect x={hx + 0.18 * F} y={hy - 0.1 * F} width={0.62 * F} height={0.06 * F} rx={0.01 * F} fill={tinta} />
            <rect x={hx + 0.22 * F} y={hy - 0.04 * F} width={0.04 * F} height={0.34 * F} fill={tinta} />
            <rect x={hx + 0.72 * F} y={hy - 0.04 * F} width={0.04 * F} height={0.34 * F} fill={tinta} />
            <path d={`M${hx + 0.42 * F} ${hy - 0.1 * F} l${0.08 * F} ${-0.2 * F} h${0.22 * F} l${-0.02 * F} ${0.2 * F} z`} fill={tinta} />
            <circle cx={hx + 0.62 * F} cy={hy - 0.2 * F} r={0.012 * F} fill={claro ? '#DCDCDA' : '#000'} />
          </g>
        )}
        <Monigote pose={P} F={F} color={tinta} x={hx} y={hy} gafas={sentado} />
        {pose === 'gritando' && (
          <g opacity={clamp((t - 0.25) / 0.2)}>
            <Monigote pose={mezclaPose(base, POSES.gritando, q)} F={F * 1.02} color={tinta} x={hx - 0.62 * F} y={cy + 0.18 * F + Math.sin(t * 22) * 0.008 * F} boca />
            {[0, 1, 2].map(k => (
              <line key={k} x1={hx - 0.5 * F + k * 0.06 * F} y1={hy - 0.6 * F} x2={hx - 0.46 * F + k * 0.1 * F} y2={hy - 0.7 * F - (k === 1 ? 0.05 * F : 0)}
                    stroke={tinta} strokeWidth={0.02 * F} strokeLinecap="round" opacity={0.5 + 0.5 * Math.sin(t * 18 + k)} />
            ))}
          </g>
        )}
        {pose === 'pensando' && [0, 1, 2].map(k => {
          const pk = clamp((t - 0.5 - k * 0.25) / 0.3);
          return (
            <text key={k} x={hx + (0.12 + k * 0.12) * F} y={hy - (0.58 + k * 0.09) * F - Math.sin(t * 2 + k) * 6 * U} fontFamily={FAMILIA.redonda} fontWeight={800}
                  fontSize={(0.1 + k * 0.035) * F} fill={tinta} opacity={pk}>?</text>
          );
        })}
        {(pose === 'corriendo' || pose === 'cayendo') && [0, 1, 2, 3].map(k => (
          <line key={k} x1={hx - (0.35 + 0.05 * k) * F} y1={hy - (0.55 - k * 0.12) * F} x2={hx - (0.6 + 0.05 * k) * F - ((t * 900) % 80) * U} y2={hy - (0.55 - k * 0.12) * F}
                stroke={tinta} strokeWidth={0.02 * F} strokeLinecap="round" opacity={0.35} />
        ))}
        {pose === 'subiendo' && [0, 1, 2, 3, 4].map(k => (
          <rect key={k} x={hx - 0.3 * F + k * 0.22 * F} y={hy + 0.42 * F - k * 0.14 * F} width={0.24 * F} height={0.14 * F + k * 0.14 * F} fill={tinta} opacity={0.18} />
        ))}
        {pose === 'senalando' && (
          <g opacity={clamp((t - 0.55) / 0.15)}>
            {[0, 1, 2, 3, 4].map(k => {
              const a = (-40 + k * 20) * (Math.PI / 180), r0 = 0.05 * F, r1 = 0.1 * F + 0.03 * F * Math.sin(t * 9);
              const px = hx + 0.4 * F, py = hy - 0.33 * F;
              return <line key={k} x1={px + Math.cos(a) * r0} y1={py + Math.sin(a) * r0} x2={px + Math.cos(a) * r1} y2={py + Math.sin(a) * r1} stroke={tinta} strokeWidth={0.018 * F} strokeLinecap="round" />;
            })}
          </g>
        )}
      </svg>
    );
  } else {
    // el personaje de luz: cabeza y cuerpo en óvalo, rojo brillante, ojos que parpadean, sobre una rejilla que ondula
    const parp = (t % 2.4) > 2.25 ? 0.12 : 1;
    const bob = Math.sin(t * 2.2) * 8 * U;
    const pe = S(0.1, { damping: 13 });
    figura = (
      <div style={{ position: 'absolute', left: cx - 260 * U, top: cy - 300 * U + bob, width: 520 * U, height: 900 * U, transform: `scale(${Math.max(0.001, pe).toFixed(4)})`,
                    filter: `drop-shadow(0 0 ${40 * U}px ${ac}) drop-shadow(0 0 ${90 * U}px ${ac})` }}>
        <div style={{ position: 'absolute', left: 150 * U, top: 0, width: 220 * U, height: 220 * U, borderRadius: '50%', background: `radial-gradient(circle at 40% 35%, ${mezcla(ac, [255, 255, 255], 0.35)}, ${ac} 70%)` }}>
          {[0, 1].map(k => <div key={k} style={{ position: 'absolute', left: (78 + k * 46) * U, top: 92 * U, width: 16 * U, height: 34 * U, borderRadius: 8 * U, background: '#FFF', transform: `scaleY(${parp})` }} />)}
        </div>
        <div style={{ position: 'absolute', left: 60 * U, top: 240 * U, width: 400 * U, height: 640 * U, borderRadius: '50% 50% 46% 46% / 42% 42% 58% 58%',
                      background: `radial-gradient(ellipse at 50% 30%, ${mezcla(ac, [255, 255, 255], 0.25)}, ${ac} 60%, ${mezcla(ac, [0, 0, 0], 0.25)} 100%)` }} />
      </div>
    );
  }
  // la línea que baja hasta el icono 3D (o de lado en horizontal)
  const pl = easeOut((t - 0.75) / 0.6), pi = S(1.25, { damping: 11, stiffness: 170 });
  const ix = vert ? W / 2 : W * 0.76, iy = vert ? H * 0.7 : H * 0.56, li = (vert ? 300 : 360) * U;      // (vertical: por encima de los captions, que bajan al 86 %)
  const curva = vert ? `M ${W / 2} ${H * 0.565} C ${W / 2 + 70 * U} ${H * 0.58}, ${W / 2 - 50 * U} ${H * 0.6}, ${W / 2} ${iy - li * 0.5}`
                     : `M ${W * 0.48} ${H * 0.52} C ${W * 0.55} ${H * 0.4}, ${W * 0.6} ${H * 0.66}, ${ix - li * 0.5} ${iy}`;
  return (
    <Escena fondo={fondo} salida={salida}>
      {claro && Array.from({ length: 22 }).map((_, i) => (
        <div key={i} style={{ position: 'absolute', left: azar(i) * W, top: (azar(i + 40) * H + t * 20 * U * (azar(i + 9) - 0.5)) % H, width: (6 + azar(i + 3) * 26) * U,
                              height: (6 + azar(i + 3) * 26) * U, borderRadius: '50%', background: '#111', opacity: 0.08 + 0.5 * azar(i + 5) }} />
      ))}
      {claro && conTexto && (
        <div style={{ position: 'absolute', left: -W * 0.1 + t * 30 * U, top: H * 0.72, fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 300 * U, color: 'transparent',
                      WebkitTextStroke: `${3 * U}px rgba(0,0,0,.12)`, whiteSpace: 'nowrap', letterSpacing: '-0.02em' }}>{texto} {texto}</div>
      )}
      {!claro && !neon && (
        <svg style={{ position: 'absolute', inset: 0, width: W, height: H }}>
          {Array.from({ length: Math.ceil(W / (170 * U)) + 1 }).map((_, i) => <line key={'v' + i} x1={i * 170 * U} y1={0} x2={i * 170 * U} y2={H} stroke="#262626" strokeWidth={2 * U} />)}
          {Array.from({ length: Math.ceil(H / (170 * U)) + 1 }).map((_, i) => <line key={'h' + i} x1={0} y1={i * 170 * U} x2={W} y2={i * 170 * U} stroke="#262626" strokeWidth={2 * U} />)}
        </svg>
      )}
      {neon && (
        <svg style={{ position: 'absolute', inset: 0, width: W, height: H }}>
          {Array.from({ length: 9 }).map((_, i) => {
            const x0 = (i / 8) * W;
            const d = Array.from({ length: 13 }).map((__, k) => `${k ? 'L' : 'M'} ${(x0 + Math.sin(k * 0.9 + t * 1.3 + i) * 14 * U).toFixed(1)} ${((k / 12) * H).toFixed(1)}`).join(' ');
            return <path key={'v' + i} d={d} stroke="rgba(255,255,255,.55)" strokeWidth={2.5 * U} fill="none" />;
          })}
          {Array.from({ length: 14 }).map((_, i) => {
            const y0 = (i / 13) * H;
            const d = Array.from({ length: 9 }).map((__, k) => `${k ? 'L' : 'M'} ${((k / 8) * W).toFixed(1)} ${(y0 + Math.sin(k * 1.1 + t * 1.1 + i) * 14 * U).toFixed(1)}`).join(' ');
            return <path key={'h' + i} d={d} stroke="rgba(255,255,255,.55)" strokeWidth={2.5 * U} fill="none" />;
          })}
        </svg>
      )}
      {!claro && !neon && (
        <div style={{ position: 'absolute', left: cx - 420 * U, top: cy - 420 * U, width: 840 * U, height: 840 * U, borderRadius: '50%',
                      background: 'radial-gradient(circle, rgba(255,255,255,.22) 0%, rgba(255,255,255,0) 65%)' }} />
      )}
      {figura}
      {conTexto && (
        <div style={{ position: 'absolute', left: 0, width: vert ? W : W * 0.68, top: vert ? H * 0.12 : H * 0.12, textAlign: 'center', fontFamily: FAMILIA.redonda, fontWeight: 800,
                      fontSize: Math.min(150, 1300 / Math.max(5, texto.length)) * U, color: neon ? '#FFF' : tinta, letterSpacing: `${(0.01 + 0.12 * (1 - easeOut((t - 0.2) / 0.5))).toFixed(3)}em`,
                      opacity: clamp((t - 0.2) / 0.25), textShadow: claro ? 'none' : `0 0 ${24 * U}px rgba(255,255,255,.35)`, textTransform: 'uppercase' }}>{texto}</div>
      )}
      {sub && (
        <div style={{ position: 'absolute', left: 0, width: vert ? W : W * 0.68, top: vert ? H * 0.12 + 170 * U : H * 0.12 + 160 * U, textAlign: 'center', fontFamily: FAMILIA.inter,
                      fontWeight: 500, fontSize: 48 * U, color: claro ? '#444' : 'rgba(255,255,255,.75)', opacity: clamp((t - 0.45) / 0.3) }}>{sub}</div>
      )}
      {imagen && !neon && (
        <>
          <svg style={{ position: 'absolute', inset: 0, width: W, height: H, overflow: 'visible' }}>
            <path d={curva} fill="none" stroke={tinta} strokeWidth={5 * U} strokeLinecap="round" pathLength={1} strokeDasharray="1" strokeDashoffset={(1 - pl).toFixed(4)} opacity={0.9} />
          </svg>
          <Img src={src(imagen)} style={{ position: 'absolute', left: ix - li / 2, top: iy - li / 2, width: li, height: li, objectFit: 'contain',
                                           transform: `scale(${Math.max(0.001, pi).toFixed(4)}) rotate(${(Math.sin(t * 2) * 3).toFixed(2)}deg)`,
                                           filter: `drop-shadow(0 ${16 * U}px ${30 * U}px rgba(0,0,0,.35))` }} />
        </>
      )}
    </Escena>
  );
};

/* ================================================================================================ TableroE */
export type TableroProps = Base & { titulo?: string; sub?: string; items?: string; imagenes?: string };
export const TableroE: React.FC<TableroProps> = ({ titulo = 'UN AÑO', sub = '', items = 'Idea|Equipo|Clientes|Resultados', imagenes = '', variante = 'gris', acento, salida = 0.3 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU(), S = useResorte();
  const { t } = useVida(salida);
  const vert = H >= W;
  const rojo = hex(acento, '#D3202E');
  const fondos: Record<string, string> = { gris: 'radial-gradient(ellipse at 50% 45%, #E4E4E2 0%, #B9B9B7 100%)', corcho: 'radial-gradient(ellipse at 50% 45%, #CFA574 0%, #9C7246 100%)',
                                            oscuro: 'radial-gradient(ellipse at 50% 45%, #2A2A2D 0%, #111113 100%)' };
  const its = lista(items).slice(0, 5), imgs = lista(imagenes);
  const n = Math.max(2, its.length);
  const cx = W / 2, cy = H * (vert ? 0.45 : 0.52);
  const R = 0.36 * Math.min(W, H) * (vert ? 1.15 : 1.25);
  const pos = its.map((_, i) => {
    const a = -Math.PI / 2 + (i / n) * Math.PI * 2 + 0.35;
    return [cx + Math.cos(a) * R * (vert ? 0.95 : 1.45), cy + Math.sin(a) * R * (vert ? 1.22 : 0.82)] as [number, number];
  });
  const cw = 270 * U, chh = 320 * U;
  const ptitulo = S(0.25 + n * 0.16 + 0.35, { damping: 10, stiffness: 200 });
  const hilo = (k: number) => easeOut((t - 0.3 - n * 0.16 - k * 0.12) / 0.4);
  const alfiler = (x: number, y: number, s: number, k: string) => (
    <Img key={k} src={staticFile('stickers/rcs_emoji_pushpin.png')} style={{ position: 'absolute', left: x - 34 * U, top: y - 60 * U, width: 72 * U, height: 72 * U,
                                                                           transform: `scale(${Math.max(0.001, s).toFixed(4)}) rotate(20deg)`, filter: `drop-shadow(${3 * U}px ${6 * U}px ${4 * U}px rgba(0,0,0,.35))` }} />
  );
  return (
    <Escena fondo={fondos[variante] || fondos.gris} salida={salida}>
      <Grano id="gtab" op={variante === 'oscuro' ? 0.25 : 0.18} frec={0.9} />
      <svg style={{ position: 'absolute', inset: 0, width: W, height: H, overflow: 'visible' }}>
        {pos.map((p, i) => {
          const q = pos[(i + 1) % pos.length];
          const k = hilo(i);
          const mx = (p[0] + q[0]) / 2, my = (p[1] + q[1]) / 2 + 40 * U;
          return <path key={i} d={`M ${p[0]} ${p[1] - chh * 0.42} Q ${mx} ${my} ${q[0]} ${q[1] - chh * 0.42}`} fill="none" stroke={rojo} strokeWidth={6 * U}
                       pathLength={1} strokeDasharray="1" strokeDashoffset={(1 - k).toFixed(4)} style={{ filter: `drop-shadow(0 ${3 * U}px ${3 * U}px rgba(0,0,0,.3))` }} />;
        })}
        {pos.map((p, i) => {
          const k = hilo(i + 1);
          return <path key={'c' + i} d={`M ${p[0]} ${p[1] - chh * 0.42} Q ${(p[0] + cx) / 2} ${(p[1] + cy) / 2 + 50 * U} ${cx} ${cy - 120 * U}`} fill="none" stroke={rojo}
                       strokeWidth={5 * U} pathLength={1} strokeDasharray="1" strokeDashoffset={(1 - k).toFixed(4)} opacity={0.9} />;
        })}
      </svg>
      {pos.map((p, i) => {
        const pc = S(0.2 + i * 0.16, { damping: 12, stiffness: 190 });
        const giro = (azar(i + 3) - 0.5) * 16;
        const img = imgs[i % Math.max(1, imgs.length)];
        return (
          <div key={i} style={{ position: 'absolute', left: p[0] - cw / 2, top: p[1] - chh / 2, width: cw, height: chh, background: '#F8F7F3', padding: 14 * U, boxSizing: 'border-box',
                                transform: `rotate(${(giro + (1 - clamp(pc)) * 20).toFixed(2)}deg) scale(${(1.35 - 0.35 * clamp(pc)).toFixed(4)})`, opacity: clamp(pc * 3),
                                boxShadow: `0 ${10 * U}px ${24 * U}px rgba(0,0,0,.35)` }}>
            <div style={{ width: '100%', height: chh * 0.66, background: img ? '#222' : `linear-gradient(135deg, ${mezcla(rojo, [0, 0, 0], 0.55)}, ${mezcla(rojo, [0, 0, 0], 0.2)})`,
                          overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {img && <Img src={src(img)} style={{ width: img.startsWith('data:') ? '100%' : '72%', height: img.startsWith('data:') ? '100%' : '72%', objectFit: img.startsWith('data:') ? 'cover' : 'contain',
                                                      filter: img.startsWith('data:') ? 'grayscale(.25) contrast(1.05)' : 'none' }} />}
            </div>
            <div style={{ fontFamily: FAMILIA.mano, fontWeight: 700, fontSize: 50 * U, color: '#1B1B1B', textAlign: 'center', marginTop: 6 * U, lineHeight: 1 }}>{its[i]}</div>
            {alfiler(cw / 2, 10 * U, S(0.3 + i * 0.16, { damping: 12 }), 'a' + i)}
          </div>
        );
      })}
      <div style={{ position: 'absolute', left: 0, width: W, top: cy - 130 * U, textAlign: 'center', transform: `scale(${(1.5 - 0.5 * clamp(ptitulo)).toFixed(4)})`, opacity: clamp(ptitulo * 3) }}>
        <div style={{ display: 'inline-block', position: 'relative', fontFamily: FAMILIA.estarcido, fontSize: Math.min(200, 1300 / Math.max(4, titulo.length)) * U, color: rojo,
                      lineHeight: 1, textShadow: `0 ${6 * U}px ${14 * U}px rgba(0,0,0,.35)` }}>
          {titulo}
          {alfiler(0, 0, ptitulo, 'tt')}
        </div>
        {sub && <div style={{ fontFamily: FAMILIA.mano, fontWeight: 700, fontSize: 64 * U, color: variante === 'oscuro' ? '#EEE' : '#1C1C1C', marginTop: 6 * U }}>{sub}</div>}
      </div>
    </Escena>
  );
};

/* ================================================================================================ PolaroidE */
export type PolaroidProps = Base & { foto?: string; imagen?: string; pie?: string; palabra?: string; numero?: string };
export const PolaroidE: React.FC<PolaroidProps> = ({ foto = '', imagen = 'stickers/rcs_emoji_camera.png', pie = 'Un gran momento', palabra = 'RECUERDOS', numero = '',
                                                     variante = 'rojo', acento, salida = 0.3 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU(), S = useResorte();
  const { t } = useVida(salida);
  const vert = H >= W;
  const tonos: Record<string, [string, string]> = { rojo: ['#E5262E', '#9E0F16'], crema: ['#EFE6D6', '#CDBE9F'], azul: ['#2B5BD7', '#0E2A73'] };
  const [c1, c2] = tonos[variante] || tonos.rojo;
  const clara = variante === 'crema';
  const ac = hex(acento, clara ? '#C0392B' : '#FFFFFF');
  const cuerdaY = H * (vert ? 0.2 : 0.16);
  const pw = (vert ? 640 : 520) * U, ph = pw * 1.18;
  const cx = W / 2;
  const caida = S(0.12, { damping: 9, stiffness: 120 });
  const vaiven = Math.sin(t * 3.1) * 5 * Math.exp(-t * 0.9) + (1 - clamp(caida)) * 12;
  const top = cuerdaY + 40 * U - (1 - clamp(caida)) * 500 * U;
  const pinza = S(0.35, { damping: 13 });
  const pn = S(0.95, { damping: 10 });
  const cuerda = `M ${-50} ${cuerdaY - 30 * U} Q ${W / 2} ${cuerdaY + 70 * U} ${W + 50} ${cuerdaY - 40 * U}`;
  return (
    <Escena fondo={`radial-gradient(ellipse at 50% 40%, ${c1} 0%, ${c2} 100%)`} salida={salida} oy={30}>
      <Grano id="gpol" op={0.22} frec={0.95} />
      <div style={{ position: 'absolute', left: -W * 0.1 - t * 25 * U, top: H * 0.06, fontFamily: FAMILIA.condensada, fontSize: (vert ? 420 : 380) * U, lineHeight: 0.9,
                    color: clara ? 'rgba(120,90,60,.16)' : 'rgba(0,0,0,.14)', whiteSpace: 'nowrap', transform: 'rotate(-12deg)', filter: `blur(${2 * U}px)` }}>{palabra} {palabra}</div>
      <svg style={{ position: 'absolute', inset: 0, width: W, height: H, overflow: 'visible' }}>
        <path d={cuerda} fill="none" stroke="#7B5A36" strokeWidth={14 * U} strokeLinecap="round" />
        <path d={cuerda} fill="none" stroke="#B68B5A" strokeWidth={14 * U} strokeDasharray={`${10 * U} ${10 * U}`} strokeLinecap="butt" opacity={0.8} />
      </svg>
      {/* polaroids desenfocadas delante: profundidad */}
      {[0, 1].map(k => (
        <div key={k} style={{ position: 'absolute', left: k ? W * 0.74 : -W * 0.16, top: k ? H * 0.8 : H * 0.84, width: pw * 0.62, height: ph * 0.62, background: '#F4F3EF',
                              transform: `rotate(${k ? 14 : -10}deg) translateY(${(Math.sin(t + k) * 10 * U).toFixed(1)}px)`, filter: `blur(${18 * U}px)`, opacity: 0.5 }} />
      ))}
      <div style={{ position: 'absolute', left: cx - pw / 2, top, width: pw, height: ph, transformOrigin: '50% 0%', transform: `rotate(${vaiven.toFixed(3)}deg)` }}>
        <div style={{ position: 'absolute', inset: 0, background: '#FBFAF7', boxShadow: `0 ${26 * U}px ${50 * U}px rgba(0,0,0,.4)`, padding: `${26 * U}px ${26 * U}px 0`, boxSizing: 'border-box' }}>
          <div style={{ width: '100%', height: pw - 52 * U, background: foto ? '#000' : `linear-gradient(160deg, ${mezcla(c1, [255, 255, 255], 0.35)}, ${c2})`, overflow: 'hidden',
                        display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Img src={src(foto || imagen)} style={foto ? { width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${(1.08 - 0.06 * clamp(t / 3)).toFixed(4)})` }
                                                   : { width: '62%', height: '62%', objectFit: 'contain' }} />
          </div>
          <div style={{ height: ph - pw + 26 * U, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: FAMILIA.mano, fontWeight: 700,
                        fontSize: Math.min(76, 1100 / Math.max(6, pie.length)) * U, color: '#1F1F1F', opacity: clamp((t - 0.7) / 0.3) }}>{pie}</div>
        </div>
        <svg width={70 * U} height={150 * U} viewBox="0 0 70 150" style={{ position: 'absolute', left: pw / 2 - 35 * U, top: -95 * U, transform: `scale(${Math.max(0.001, pinza).toFixed(4)})`,
                                                                          filter: `drop-shadow(${3 * U}px ${5 * U}px ${4 * U}px rgba(0,0,0,.35))` }}>
          <rect x="6" y="0" width="28" height="150" rx="6" fill="#C8955B" /><rect x="36" y="0" width="28" height="150" rx="6" fill="#B07D45" />
          <rect x="4" y="62" width="62" height="14" rx="3" fill="#8D8D8D" /><rect x="12" y="10" width="6" height="120" rx="3" fill="#D9A86E" opacity="0.7" />
        </svg>
        {numero && (
          <div style={{ position: 'absolute', right: -40 * U, bottom: ph * 0.06, width: 170 * U, height: 170 * U, borderRadius: '50%', background: clara ? '#B83227' : '#C9252C',
                        color: '#FFF', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: FAMILIA.condensada, fontSize: 92 * U,
                        boxShadow: `0 ${8 * U}px ${16 * U}px rgba(0,0,0,.35)`, transform: `scale(${Math.max(0.001, pn).toFixed(4)}) rotate(-8deg)` }}>{numero}</div>
        )}
      </div>
    </Escena>
  );
};

/* ================================================================================================ CuadernoE */
export type CuadernoProps = Base & { titulo?: string; clave?: string; nota?: string; sello?: string; lista?: string };
export const CuadernoE: React.FC<CuadernoProps> = ({ titulo = 'Próximamente', clave = '', nota = '12 junio', sello = 'IMPORTANTE', lista: items = '', variante = 'verde', acento, salida = 0.3 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU(), S = useResorte();
  const { t } = useVida(salida);
  const vert = H >= W;
  const mesas: Record<string, string> = { verde: 'radial-gradient(ellipse at 40% 35%, #2E5240 0%, #12241B 100%)', madera: 'linear-gradient(160deg, #7A5232, #3F2614)',
                                          gris: 'radial-gradient(ellipse at 40% 35%, #5B5E63 0%, #26282B 100%)' };
  const rojo = hex(acento, '#D0312D');
  const pw = (vert ? 880 : 900) * U, ph = (vert ? 1180 : 860) * U;
  const px = W / 2 - pw / 2 + (vert ? 30 : -80) * U, py = H / 2 - ph / 2 - (vert ? 40 : 10) * U;
  const pe = S(0.02, { damping: 16 });
  const letras = Array.from(titulo);
  const vel = Math.max(0.025, Math.min(0.06, 0.9 / Math.max(1, letras.length)));
  const escritas = clamp(Math.floor((t - 0.35) / vel), 0, letras.length);
  const pal = titulo.split(/(\s+)/);
  let cuenta = 0;
  const tc = 0.35 + letras.length * vel;
  const circulo = easeOut((t - tc - 0.1) / 0.45);
  const subrayado = easeOut((t - tc - 0.35) / 0.35);
  const ps = S(tc + 0.55, { damping: 9, stiffness: 240 });
  const pn = S(0.6, { damping: 14 });
  const its = lista(items).slice(0, 4);
  const tam = Math.min(150, 1700 / Math.max(6, titulo.length)) * U;
  return (
    <Escena fondo={mesas[variante] || mesas.verde} salida={salida}>
      <div style={{ position: 'absolute', inset: 0, background: 'repeating-linear-gradient(115deg, rgba(255,255,255,0) 0 160px, rgba(255,255,255,.06) 160px 260px)', opacity: 0.8 }} />
      <Grano id="gcua" op={0.2} />
      <div style={{ position: 'absolute', left: px, top: py, width: pw, height: ph, transform: `rotate(-3deg) scale(${(0.92 + 0.08 * clamp(pe)).toFixed(4)})`, opacity: clamp(pe * 2) }}>
        <div style={{ position: 'absolute', inset: 0, background: '#F7F5EF', borderRadius: 10 * U, boxShadow: `0 ${30 * U}px ${60 * U}px rgba(0,0,0,.45)`,
                      backgroundImage: `repeating-linear-gradient(180deg, rgba(0,0,0,0) 0 ${62 * U}px, rgba(70,110,160,.18) ${62 * U}px ${64 * U}px)` }} />
        {Array.from({ length: Math.floor(ph / (58 * U)) }).map((_, i) => (
          <div key={i} style={{ position: 'absolute', left: -26 * U, top: 40 * U + i * 58 * U, width: 58 * U, height: 22 * U, borderRadius: 11 * U, border: `${5 * U}px solid #9DA1A6`,
                                boxSizing: 'border-box', background: 'transparent' }} />
        ))}
        <div style={{ position: 'absolute', left: 80 * U, right: 50 * U, top: 90 * U, fontFamily: FAMILIA.maquina, fontSize: tam, lineHeight: 1.05, color: '#151515' }}>
          {pal.map((w, i) => {
            const desde = cuenta;
            cuenta += w.length;
            const vis = w.slice(0, clamp(escritas - desde, 0, w.length));
            const esClave = clave && w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '') === clave.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
            if (/^\s+$/.test(w)) return <span key={i}>{vis ? ' ' : ''}</span>;
            return (
              <span key={i} style={{ position: 'relative', display: 'inline-block' }}>
                {vis}
                {esClave && vis.length === w.length && (
                  <svg style={{ position: 'absolute', left: '-12%', top: '-18%', width: '124%', height: '136%', overflow: 'visible' }} viewBox="0 0 100 100" preserveAspectRatio="none">
                    <path d="M 8 50 C 8 14, 92 10, 95 48 C 98 86, 10 92, 6 52 C 4 30, 30 16, 52 14" fill="none" stroke={rojo} strokeWidth={3.2} vectorEffect="non-scaling-stroke"
                          pathLength={1} strokeDasharray="1" strokeDashoffset={(1 - circulo).toFixed(4)} style={{ strokeWidth: 7 * U }} strokeLinecap="round" />
                  </svg>
                )}
              </span>
            );
          })}
          {escritas < letras.length && <span style={{ opacity: (t * 3) % 1 > 0.5 ? 1 : 0 }}>|</span>}
        </div>
        <div style={{ position: 'absolute', left: 80 * U, top: 90 * U + tam * 1.12 * Math.max(1, Math.ceil(titulo.length * tam * 0.6 / (pw - 130 * U))) + 10 * U,
                      width: (pw - 200 * U) * subrayado, height: 8 * U, borderRadius: 4 * U, background: rojo, transform: 'rotate(-1deg)' }} />
        {its.length > 0 && (
          <div style={{ position: 'absolute', left: pw * 0.5, top: ph * 0.6, width: pw * 0.46, background: '#FFFFFF', padding: 26 * U, boxShadow: `0 ${10 * U}px ${22 * U}px rgba(0,0,0,.25)`,
                        transform: `rotate(5deg) translateY(${((1 - easeOut((t - 0.8) / 0.4)) * 60 * U).toFixed(1)}px)`, opacity: clamp((t - 0.8) / 0.2) }}>
            <div style={{ fontFamily: FAMILIA.maquina, fontSize: 46 * U, color: '#111', borderBottom: `${4 * U}px solid ${rojo}`, display: 'inline-block', marginBottom: 10 * U }}>lista</div>
            {its.map((x, i) => (
              <div key={i} style={{ fontFamily: FAMILIA.maquina, fontSize: 38 * U, color: '#222', opacity: clamp((t - 1.0 - i * 0.15) / 0.2) }}>• {x}</div>
            ))}
            <Img src={staticFile('fluent/paperclip.png')} style={{ position: 'absolute', right: 20 * U, top: -50 * U, width: 90 * U, height: 90 * U, transform: 'rotate(20deg)' }} />
          </div>
        )}
        {sello && (
          <div style={{ position: 'absolute', right: 40 * U, top: ph * (its.length ? 0.38 : 0.52), padding: `${10 * U}px ${26 * U}px`, border: `${8 * U}px solid ${rojo}`, borderRadius: 10 * U,
                        fontFamily: FAMILIA.estarcido, fontSize: Math.min(84, 900 / Math.max(5, sello.length)) * U, color: rojo, opacity: clamp(ps * 2) * 0.88,
                        transform: `rotate(-9deg) scale(${(1.7 - 0.7 * clamp(ps)).toFixed(4)})`, mixBlendMode: 'multiply' }}>{sello}</div>
        )}
      </div>
      {nota && (
        <div style={{ position: 'absolute', left: px + (vert ? 40 : 60) * U, top: py + ph * (vert ? 0.58 : 0.55), width: 420 * U, height: 360 * U, background: '#F3F1E8',
                      boxShadow: `0 ${16 * U}px ${30 * U}px rgba(0,0,0,.35)`, transform: `rotate(-6deg) scale(${Math.max(0.001, pn).toFixed(4)})`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: FAMILIA.maquina, fontSize: Math.min(110, 900 / Math.max(4, nota.length)) * U, color: '#151515',
                      textAlign: 'center', lineHeight: 1 }}>
          {nota}
          <Img src={staticFile('stickers/rcs_emoji_pushpin.png')} style={{ position: 'absolute', left: 170 * U, top: -40 * U, width: 80 * U, height: 80 * U }} />
        </div>
      )}
      {/* objetos desenfocados delante (profundidad) */}
      <Img src={staticFile('stickers/rcs_emoji_alarm_clock.png')} style={{ position: 'absolute', right: -120 * U, bottom: -60 * U + Math.sin(t) * 10 * U, width: 520 * U, height: 520 * U,
                                                                            filter: `blur(${14 * U}px) grayscale(.6) brightness(.8)`, opacity: 0.9 }} />
      <Img src={staticFile('stickers/rcs_emoji_camera.png')} style={{ position: 'absolute', left: -130 * U, top: -80 * U + Math.cos(t) * 8 * U, width: 420 * U, height: 420 * U,
                                                                       filter: `blur(${12 * U}px) grayscale(.7) brightness(.7)`, opacity: 0.85 }} />
    </Escena>
  );
};

/* ================================================================================================ FechaE */
const MESES: Record<string, string[]> = { es: ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE'] };
export type FechaProps = Base & { dia?: number; mes?: string; semana?: string; nota?: string };
export const FechaE: React.FC<FechaProps> = ({ dia = 17, mes = 'OCTUBRE', semana = 'VIE', nota = '', variante = 'naranja', acento, salida = 0.3 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU(), S = useResorte();
  const { t } = useVida(salida);
  const P: Record<string, { fondo: string; celda: string; num: string; foco: [string, string]; tinta: string; linea: string }> = {
    naranja: { fondo: 'radial-gradient(ellipse at 50% 45%, #13306B 0%, #050B1C 100%)', celda: 'rgba(8,22,58,.85)', num: '#E8513A', foco: ['#FF8A1F', '#F05A0F'], tinta: '#14204A', linea: '#FFFFFF' },
    dorado: { fondo: 'radial-gradient(ellipse at 50% 45%, #1A1A1A 0%, #050505 100%)', celda: 'rgba(20,20,20,.9)', num: '#C99A2E', foco: ['#F4EEE2', '#E2D6BF'], tinta: '#C08A1E', linea: '#3A3A3A' },
    rojo: { fondo: 'radial-gradient(ellipse at 50% 45%, #3B0B0E 0%, #120203 100%)', celda: 'rgba(40,6,8,.9)', num: '#FF5A5A', foco: ['#FF3B3B', '#B3121A'], tinta: '#FFFFFF', linea: '#FFFFFF' },
  };
  const E = P[variante] || P.naranja;
  const foco0 = esHex(acento) && variante === 'naranja' ? [hex(acento, E.foco[0]), mezcla(hex(acento, E.foco[0]), [0, 0, 0], 0.15)] : E.foco;
  const L = 360 * U, gap = 14 * U;
  const cam = easeOut(t / 1.2);
  const escala = 1.35 - 0.3 * cam, giro = -9 + 4 * cam;
  const pf = S(0.35, { damping: 12, stiffness: 170 });
  const celdas = [];
  for (let f = -2; f <= 2; f++) for (let c = -1; c <= 1; c++) celdas.push([f, c]);
  const d0 = Math.max(1, Math.min(31, Math.round(Number(dia) || 1)));
  const papeles = [0, 1, 2, 3, 4, 5];
  const pc = easeOut((t - 0.8) / 0.5);
  return (
    <Escena fondo={E.fondo} salida={salida}>
      <div style={{ position: 'absolute', left: W / 2, top: H / 2, transform: `rotate(${giro.toFixed(3)}deg) scale(${escala.toFixed(4)})` }}>
        {celdas.map(([f, c], i) => {
          const centro = f === 0 && c === 0;
          const n = d0 + f * 3 + c;
          const x = c * (L + gap) - L / 2, y = f * (L + gap) - L / 2;
          return (
            <div key={i} style={{ position: 'absolute', left: x, top: y, width: L, height: L, background: centro ? `linear-gradient(150deg, ${foco0[0]}, ${foco0[1]})` : E.celda,
                                  outline: `${gap / 2}px solid ${E.linea}`, overflow: 'hidden',
                                  transform: centro ? `scale(${(0.9 + 0.1 * clamp(pf) + 0.04 * Math.max(0, pf - 1)).toFixed(4)})` : 'none', zIndex: centro ? 2 : 1,
                                  boxShadow: centro ? `0 0 ${60 * U}px rgba(255,140,40,${(0.5 * clamp(pf)).toFixed(3)})` : 'none' }}>
              {(!centro || pf > 0.05) && (
                <div style={{ position: 'absolute', left: 30 * U, bottom: 30 * U, fontFamily: FAMILIA.condensada, lineHeight: 0.85, color: centro ? E.tinta : E.num,
                              opacity: centro ? 1 : 0.35, fontSize: (centro ? 210 : 190) * U }}>
                  {n > 0 && n <= 31 ? n : ''}
                  <div style={{ fontSize: (centro ? Math.min(72, 560 / Math.max(4, mes.length)) : 44) * U, letterSpacing: '0.02em' }}>{mes}</div>
                </div>
              )}
              <div style={{ position: 'absolute', right: 24 * U, top: 18 * U, fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 44 * U, color: centro ? E.tinta : E.num, opacity: centro ? 0.95 : 0.4 }}>
                {centro ? semana : ''}
              </div>
              {centro && <Grano id="gfec" op={0.25} frec={0.7} />}
            </div>
          );
        })}
      </div>
      {papeles.map(k => {
        const a = (k / papeles.length) * Math.PI * 2 + 0.4, p = easeOut((t - 0.45 - k * 0.04) / 0.7);
        if (p <= 0 || p >= 1) return null;
        return (
          <div key={k} style={{ position: 'absolute', left: W / 2 + Math.cos(a) * p * W * 0.7 - 110 * U, top: H / 2 + Math.sin(a) * p * H * 0.55 - 70 * U, width: 220 * U, height: 140 * U,
                                background: 'linear-gradient(90deg, rgba(255,255,255,.95), rgba(220,220,220,.9))', opacity: (1 - p) * 0.95,
                                transform: `rotate(${(a * 57 + p * 200).toFixed(1)}deg) scale(${(0.6 + p * 1.2).toFixed(3)})`, filter: `blur(${(2 + p * 10) * U}px)` }} />
        );
      })}
      {nota && (
        <div style={{ position: 'absolute', left: W / 2 - 300 * U, width: 600 * U, top: H / 2 + L * 0.75, textAlign: 'center', opacity: clamp((t - 0.8) / 0.3) }}>
          <svg style={{ position: 'absolute', left: -40 * U, top: -40 * U, width: 680 * U, height: 220 * U, overflow: 'visible' }} viewBox="0 0 680 220">
            <ellipse cx="340" cy="110" rx="320" ry="80" fill="none" stroke="#FFFFFF" strokeWidth="5" pathLength={1} strokeDasharray="1" strokeDashoffset={(1 - pc).toFixed(4)}
                     style={{ filter: 'drop-shadow(0 0 10px rgba(255,255,255,.8))' }} transform="rotate(-6 340 110)" />
          </svg>
          <div style={{ position: 'relative', display: 'inline-block', padding: `${10 * U}px ${26 * U}px`, borderRadius: 40 * U, background: 'rgba(5,10,25,.82)',
                        fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 48 * U, color: hex(acento, '#FF8A1F'), letterSpacing: '0.04em', lineHeight: 1.1, textTransform: 'uppercase' }}>{nota}</div>
        </div>
      )}
    </Escena>
  );
};
export const nombreMes = (m: number, idioma = 'es') => (MESES[idioma] || MESES.es)[Math.max(0, Math.min(11, m - 1))];

/* ================================================================================================ VidrioE */
export type VidrioProps = Base & { icono?: string; titulo?: string; sub?: string };
export const VidrioE: React.FC<VidrioProps> = ({ icono = 'users', titulo = 'COMUNIDAD', sub = '', variante = 'morado', acento, salida = 0.3 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU(), S = useResorte();
  const { t } = useVida(salida);
  const F: Record<string, [string, string, string]> = { morado: ['#2B1D63', '#0D0920', '#B9A6FF'], azul: ['#123A73', '#050F22', '#8CC8FF'], negro: ['#1C1C22', '#030304', '#E6E6FF'] };
  const [f1, f2, luz0] = F[variante] || F.morado;
  const luz = hex(acento, luz0);
  const L = 480 * U, cx = W / 2, cy = H * (H >= W ? 0.44 : 0.42);
  const p = S(0.08, { damping: 13, stiffness: 120 });
  const ry = -38 * (1 - clamp(p)) + Math.sin(t * 1.4) * 7, rx = 16 * (1 - clamp(p)) + Math.cos(t * 1.1) * 4;
  const brillo = clamp((t - 0.7) / 0.6);
  const late = 0.75 + 0.25 * Math.sin(t * 3);
  return (
    <Escena fondo={`radial-gradient(ellipse at 50% 42%, ${f1} 0%, ${f2} 75%)`} salida={salida}>
      {[0, 1, 2].map(k => (
        <div key={k} style={{ position: 'absolute', left: W * (0.2 + 0.3 * k) + Math.sin(t * 0.7 + k) * 60 * U, top: H * (0.25 + 0.25 * (k % 2)) + Math.cos(t * 0.6 + k) * 50 * U,
                              width: 520 * U, height: 520 * U, borderRadius: '50%', background: `radial-gradient(circle, ${luz}33 0%, ${luz}00 70%)` }} />
      ))}
      <div style={{ position: 'absolute', left: cx - L / 2, top: cy - L / 2, width: L, height: L, perspective: 1400 * U }}>
        <div style={{ position: 'absolute', inset: 0, borderRadius: 110 * U, transform: `rotateY(${ry.toFixed(2)}deg) rotateX(${rx.toFixed(2)}deg) scale(${(0.7 + 0.3 * clamp(p)).toFixed(4)})`,
                      background: 'linear-gradient(160deg, rgba(255,255,255,.16) 0%, rgba(255,255,255,.04) 45%, rgba(255,255,255,.08) 100%)',
                      border: `${3 * U}px solid rgba(255,255,255,.38)`, boxShadow: `0 ${40 * U}px ${80 * U}px rgba(0,0,0,.55), inset 0 0 ${40 * U}px rgba(255,255,255,.06), 0 ${2 * U}px 0 ${luz}66`,
                      overflow: 'hidden', opacity: clamp(p * 2) }}>
          <div style={{ position: 'absolute', left: '-10%', right: '-10%', top: '38%', height: '40%', background: 'rgba(255,255,255,.06)', borderRadius: '50%', transform: 'rotate(-8deg)' }} />
          <div style={{ position: 'absolute', top: '-20%', bottom: '-20%', width: '30%', left: `${(-40 + 180 * brillo).toFixed(1)}%`, transform: 'rotate(20deg)',
                        background: 'linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,.28), rgba(255,255,255,0))' }} />
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        filter: `drop-shadow(0 0 ${16 * U * late}px ${luz}) drop-shadow(0 0 ${36 * U * late}px ${luz}AA)` }}>
            <Glifo nombre={icono} lado={L * 0.52} color={mezcla(luz, [255, 255, 255], 0.75)} />
          </div>
        </div>
      </div>
      <div style={{ position: 'absolute', left: 0, width: W, top: cy + L / 2 + 70 * U, textAlign: 'center', fontFamily: FAMILIA.inter, fontWeight: 700,
                    fontSize: Math.min(96, 1200 / Math.max(5, titulo.length)) * U, letterSpacing: `${(0.02 + 0.1 * (1 - easeOut((t - 0.45) / 0.5))).toFixed(3)}em`, color: '#FFFFFF',
                    opacity: clamp((t - 0.45) / 0.3), textShadow: `0 0 ${20 * U}px ${luz}88` }}>{titulo}</div>
      {sub && <div style={{ position: 'absolute', left: 0, width: W, top: cy + L / 2 + 190 * U, textAlign: 'center', fontFamily: FAMILIA.inter, fontWeight: 400, fontSize: 46 * U,
                            color: mezcla(luz, [255, 255, 255], 0.4), opacity: clamp((t - 0.7) / 0.3) }}>{sub}</div>}
    </Escena>
  );
};

/* ================================================================================================ ChatE */
export type ChatProps = Base & { mensaje?: string; respuesta?: string; etiqueta?: string };
export const ChatE: React.FC<ChatProps> = ({ mensaje = '¿Cuánto cuesta?', respuesta = '', etiqueta = '', variante = 'morado', acento, salida = 0.3 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU(), S = useResorte();
  const { t } = useVida(salida);
  const wa = variante === 'whatsapp';
  const ac = hex(acento, wa ? '#25D366' : variante === 'oscuro' ? '#5E8BFF' : '#A23BFF');
  const fondo = wa ? 'radial-gradient(ellipse at 50% 40%, #12302A 0%, #050B09 80%)' : '#000000';
  const cx = W / 2, cy = H * 0.42;
  const BW = 560 * U, BH = 340 * U;
  const p1 = S(0.08, { damping: 14 }), p2 = S(0.22, { damping: 14 });
  const tEsc = 1.0;
  const escribe = clamp((t - tEsc) / Math.max(0.5, mensaje.length * 0.045));
  const visibles = mensaje.slice(0, Math.floor(mensaje.length * escribe));
  const crece = easeOut((t - tEsc + 0.15) / 0.35);
  const pr = respuesta ? S(tEsc + mensaje.length * 0.045 + 0.4, { damping: 13 }) : 0;
  const ancho = entre(BW, Math.min(W * 0.84, Math.max(BW, mensaje.length * 34 * U + 120 * U)), crece);
  return (
    <Escena fondo={fondo} salida={salida}>
      <div style={{ position: 'absolute', left: cx - 600 * U, top: cy - 400 * U, width: 1200 * U, height: 900 * U, background: `radial-gradient(ellipse, ${ac}22 0%, ${ac}00 65%)` }} />
      {etiqueta && <div style={{ position: 'absolute', left: 70 * U, top: 90 * U, fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 40 * U, color: '#FFFFFF', opacity: 0.9 }}>{etiqueta}</div>}
      {/* la burbuja de atrás (color) */}
      <div style={{ position: 'absolute', left: cx - BW * 0.2, top: cy - BH * 0.05, width: BW, height: BH, borderRadius: 70 * U, opacity: clamp(p2 * 2),
                    background: `linear-gradient(135deg, ${mezcla(ac, [255, 255, 255], 0.15)}, ${ac})`, transform: `scale(${(0.7 + 0.3 * clamp(p2)).toFixed(4)})`,
                    boxShadow: `0 0 ${60 * U}px ${ac}66` }}>
        <div style={{ position: 'absolute', right: 90 * U, bottom: -46 * U, width: 0, height: 0, borderLeft: `${50 * U}px solid transparent`, borderTop: `${60 * U}px solid ${ac}` }} />
      </div>
      {/* la de delante (cristal oscuro): escribiendo… y luego el mensaje */}
      <div style={{ position: 'absolute', left: cx - BW * 0.82 - (ancho - BW) * 0.3, top: cy - BH * 0.62, width: ancho, minHeight: BH * 0.94, borderRadius: 70 * U, opacity: clamp(p1 * 2),
                    background: 'linear-gradient(135deg, rgba(40,40,46,.92), rgba(18,18,22,.86))', border: `${2 * U}px solid rgba(255,255,255,.22)`,
                    boxShadow: `0 ${30 * U}px ${60 * U}px rgba(0,0,0,.6), inset ${-60 * U}px 0 ${90 * U}px ${ac}55`, transform: `scale(${(0.7 + 0.3 * clamp(p1)).toFixed(4)})`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', padding: `${40 * U}px ${50 * U}px`, boxSizing: 'border-box' }}>
        {t < tEsc + 0.05 ? (
          <div style={{ display: 'flex', gap: 26 * U }}>
            {[0, 1, 2].map(k => <div key={k} style={{ width: 52 * U, height: 52 * U, borderRadius: '50%', background: '#FFF', transform: `translateY(${(Math.sin(t * 9 - k * 0.8) * 10 * U).toFixed(1)}px)` }} />)}
          </div>
        ) : (
          <div style={{ fontFamily: FAMILIA.inter, fontWeight: 600, fontSize: Math.min(72, 1500 / Math.max(10, mensaje.length)) * U, color: '#FFFFFF', lineHeight: 1.15, textAlign: 'left' }}>
            {visibles}<span style={{ opacity: escribe < 1 && (t * 3) % 1 > 0.5 ? 1 : 0 }}>|</span>
          </div>
        )}
        <div style={{ position: 'absolute', left: 90 * U, bottom: -46 * U, width: 0, height: 0, borderRight: `${50 * U}px solid transparent`, borderTop: `${60 * U}px solid rgba(26,26,30,.9)` }} />
      </div>
      {respuesta && pr > 0.01 && (
        <div style={{ position: 'absolute', right: W * 0.08, top: cy + BH * 0.75, maxWidth: W * 0.7, borderRadius: 60 * U, padding: `${34 * U}px ${46 * U}px`, background: ac,
                      fontFamily: FAMILIA.inter, fontWeight: 600, fontSize: 56 * U, color: '#FFFFFF', transform: `scale(${Math.max(0.001, pr).toFixed(4)})`, transformOrigin: '100% 0%',
                      boxShadow: `0 0 ${40 * U}px ${ac}88` }}>{respuesta}</div>
      )}
    </Escena>
  );
};

/* ================================================================================================ CollageE */
export type CollageProps = Base & { imagen?: string; linea1?: string; clave?: string; linea2?: string };
export const CollageE: React.FC<CollageProps> = ({ imagen = 'recortes/trama/money_bag.webp', linea1 = 'Y la audiencia', clave = 'dinero', linea2 = 'es lo que vale', variante = 'claro',
                                                   acento, salida = 0.3 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU(), S = useResorte();
  const { t } = useVida(salida);
  const vert = H >= W;
  const oscuro = variante === 'oscuro', menta = variante === 'menta';
  const rojo = hex(acento, oscuro ? '#FF1E2D' : '#E0262E');
  const forma = menta ? '#7CC9AD' : oscuro ? '#2A2A2A' : '#F1C94B';
  const fondo = oscuro ? 'radial-gradient(ellipse at 50% 45%, #1A1A1A 0%, #000 75%)' : menta ? '#FFFFFF' : 'radial-gradient(ellipse at 50% 40%, #F7F4EE 0%, #E9E5DC 100%)';
  const tinta = oscuro ? '#FFFFFF' : '#151515';
  const pi = S(0.1, { damping: 12, stiffness: 150 });
  const ps = easeOut((t - 0.05) / 0.6);
  const L = (vert ? 720 : 640) * U;
  const ix = vert ? W / 2 : W * 0.33, iy = vert ? H * 0.33 : H * 0.5;
  const tx = vert ? W / 2 : W * 0.7, ty = vert ? H * 0.62 : H * 0.42;
  return (
    <Escena fondo={fondo} salida={salida}>
      <Grano id="gcol" op={oscuro ? 0.3 : 0.12} />
      {!oscuro && (
        <svg style={{ position: 'absolute', inset: 0, width: W, height: H }}>
          <path d={`M ${W * 0.62} ${-50} C ${W * 0.35} ${H * 0.25}, ${W * 1.05} ${H * 0.45}, ${W * 0.7} ${H + 50}`} fill="none" stroke="rgba(150,150,150,.35)" strokeWidth={150 * U}
                pathLength={1} strokeDasharray="1" strokeDashoffset={(1 - ps).toFixed(4)} />
          {Array.from({ length: 9 }).map((_, i) => <line key={i} x1={W * 0.08 + i * 9 * U} y1={H * 0.06} x2={W * 0.08 + i * 9 * U} y2={H * 0.06 + 70 * U} stroke="#111" strokeWidth={(azar(i) * 5 + 2) * U} opacity={0.8} />)}
        </svg>
      )}
      <div style={{ position: 'absolute', left: ix + (vert ? 120 : 140) * U - 260 * U + Math.sin(t) * 12 * U, top: iy - 330 * U, width: 520 * U, height: 520 * U, borderRadius: '50%', background: forma,
                    transform: `scale(${(0.3 + 0.7 * easeOut((t - 0.2) / 0.5)).toFixed(4)})`, opacity: oscuro ? 0.9 : 1 }} />
      <div style={{ position: 'absolute', left: ix - 330 * U, top: iy + 120 * U, width: 0, height: 0, borderLeft: `${120 * U}px solid transparent`, borderRight: `${120 * U}px solid transparent`,
                    borderBottom: `${200 * U}px solid ${menta ? forma : rojo}`, transform: `rotate(${(-12 + Math.sin(t * 0.8) * 4).toFixed(2)}deg) scale(${easeOut((t - 0.35) / 0.4).toFixed(4)})`, opacity: 0.95 }} />
      {oscuro && <div style={{ position: 'absolute', left: ix - L * 0.7, top: iy - L * 0.7, width: L * 1.4, height: L * 1.4, borderRadius: '50%', background: 'radial-gradient(circle, rgba(255,255,255,.18), rgba(255,255,255,0) 65%)' }} />}
      <Img src={src(imagen)} style={{ position: 'absolute', left: ix - L / 2, top: iy - L / 2, width: L, height: L, objectFit: 'contain',
                                      transform: `scale(${(1.4 - 0.4 * clamp(pi)).toFixed(4)}) rotate(${((1 - clamp(pi)) * -14 - 4 + Math.sin(t * 1.2) * 1.5).toFixed(2)}deg)`, opacity: clamp(pi * 3),
                                      filter: `drop-shadow(${10 * U}px ${20 * U}px ${20 * U}px rgba(0,0,0,${oscuro ? 0.6 : 0.3}))` }} />
      <div style={{ position: 'absolute', left: tx - W * 0.45, width: W * 0.9, top: ty - 100 * U, textAlign: vert ? 'center' : 'left' }}>
        {linea1 && <div style={{ fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 64 * U, color: tinta, opacity: clamp((t - 0.35) / 0.3), letterSpacing: '-0.02em' }}>{linea1}</div>}
        <div style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: Math.min(170, 1500 / Math.max(5, clave.length)) * U, lineHeight: 1, letterSpacing: '-0.045em', color: rojo,
                      transform: `scale(${(1.2 - 0.2 * easeOut((t - 0.55) / 0.35)).toFixed(4)})`, transformOrigin: vert ? '50% 50%' : '0% 50%', opacity: clamp((t - 0.55) / 0.15),
                      textShadow: oscuro ? `0 0 ${18 * U}px ${rojo}, 0 0 ${50 * U}px ${rojo}88` : 'none' }}>{clave}</div>
        {linea2 && <div style={{ fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 60 * U, color: tinta, opacity: clamp((t - 0.85) / 0.3), letterSpacing: '-0.02em' }}>{linea2}</div>}
      </div>
    </Escena>
  );
};

/* ================================================================================================ MovilE */
export type MovilProps = Base & { usuario?: string; seguidores?: string; titulo?: string; clave?: string; accion?: string; imagenes?: string };
export const MovilE: React.FC<MovilProps> = ({ usuario = '@tu_marca', seguidores = '12,4K', titulo = 'Tu perfil no está listo', clave = 'perfil', accion = 'seguir', imagenes = '',
                                               variante = 'oscuro', idioma = 'es', acento, salida = 0.3 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU(), S = useResorte();
  const { t } = useVida(salida);
  const vert = H >= W;
  const claro = variante === 'claro', rojoV = variante === 'rojo';
  const ac = hex(acento, '#E3262F');
  const fondo = claro ? '#F5F5F5' : rojoV ? 'radial-gradient(ellipse at 50% 40%, #B3121B 0%, #4A0408 100%)' : 'radial-gradient(ellipse at 50% 40%, #1A1A1D 0%, #060607 80%)';
  const tinta = claro ? '#111' : '#FFF';
  const PW = 560 * U, PH = 1120 * U;
  const px = vert ? W / 2 - PW / 2 : W * 0.62 - PW / 2, py = vert ? H * 0.36 - PH / 2 + 240 * U : H / 2 - PH / 2;
  const pe = S(0.05, { damping: 15, stiffness: 120 });
  const ry = -22 * (1 - clamp(pe)) - 8 + Math.sin(t * 1.2) * 3;
  const cuenta = easeOut((t - 0.6) / 1.0);
  const num = (s: string, q: number) => {
    const m = String(s).match(/^([\d.,]+)(.*)$/);
    if (!m) return s;
    const v = parseFloat(m[1].replace(',', '.')) || 0;
    const dec = (m[1].split(/[.,]/)[1] || '').length;
    return (v * q).toFixed(dec).replace('.', m[1].includes(',') ? ',' : '.') + m[2];
  };
  const tPulsa = 1.5;
  const pulsado = t > tPulsa;
  const anillo = clamp((t - tPulsa) / 0.4);
  const imgs = lista(imagenes);
  const etiquetas = idioma.startsWith('en') ? ['posts', 'followers', 'following', accion === 'like' ? 'Like' : 'Follow', 'Following']
                                            : ['publicaciones', 'seguidores', 'seguidos', accion === 'like' ? 'Me gusta' : 'Seguir', 'Siguiendo'];
  const palabras = titulo.split(/\s+/);
  const ck = clave.toLowerCase();
  return (
    <Escena fondo={fondo} salida={salida}>
      {!claro && <div style={{ position: 'absolute', inset: 0, backgroundImage: `linear-gradient(rgba(255,255,255,.04) ${2 * U}px, transparent ${2 * U}px), linear-gradient(90deg, rgba(255,255,255,.04) ${2 * U}px, transparent ${2 * U}px)`,
                                backgroundSize: `${150 * U}px ${150 * U}px` }} />}
      {claro && <div style={{ position: 'absolute', inset: 0, backgroundImage: `linear-gradient(rgba(0,0,0,.06) ${2 * U}px, transparent ${2 * U}px), linear-gradient(90deg, rgba(0,0,0,.06) ${2 * U}px, transparent ${2 * U}px)`,
                               backgroundSize: `${150 * U}px ${150 * U}px` }} />}
      <svg style={{ position: 'absolute', inset: 0, width: W, height: H }}>
        <path d={`M ${-40} ${H * 0.72} C ${W * 0.3} ${H * 0.55}, ${W * 0.55} ${H * 0.95}, ${W + 40} ${H * 0.62}`} fill="none" stroke={ac} strokeWidth={10 * U} strokeLinecap="round"
              pathLength={1} strokeDasharray="1" strokeDashoffset={(1 - easeOut((t - 0.3) / 0.8)).toFixed(4)} opacity={0.85} />
      </svg>
      <div style={{ position: 'absolute', left: px, top: py, width: PW, height: PH, perspective: 1600 * U }}>
        <div style={{ position: 'absolute', inset: 0, borderRadius: 80 * U, background: '#0B0B0C', border: `${10 * U}px solid #2A2A2E`, boxSizing: 'border-box', overflow: 'hidden',
                      transform: `rotateY(${ry.toFixed(2)}deg) translateY(${((1 - clamp(pe)) * 300 * U).toFixed(1)}px)`, boxShadow: `0 ${40 * U}px ${80 * U}px rgba(0,0,0,.55)` }}>
          <div style={{ position: 'absolute', inset: 10 * U, borderRadius: 66 * U, background: claro ? '#FFFFFF' : '#121214', overflow: 'hidden', padding: `${70 * U}px ${34 * U}px`, boxSizing: 'border-box',
                        fontFamily: FAMILIA.inter, color: claro ? '#111' : '#FFF' }}>
            <div style={{ position: 'absolute', left: '50%', top: 18 * U, width: 150 * U, height: 36 * U, marginLeft: -75 * U, borderRadius: 18 * U, background: '#000' }} />
            <div style={{ fontWeight: 700, fontSize: 34 * U, marginBottom: 26 * U }}>{usuario}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 26 * U }}>
              <div style={{ width: 150 * U, height: 150 * U, borderRadius: '50%', padding: 7 * U, background: 'linear-gradient(45deg,#F58529,#DD2A7B,#8134AF)', boxSizing: 'border-box' }}>
                <div style={{ width: '100%', height: '100%', borderRadius: '50%', background: ac, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 60 * U, color: '#FFF',
                              border: `${5 * U}px solid ${claro ? '#FFF' : '#121214'}` }}>{(usuario.replace('@', '')[0] || 'C').toUpperCase()}</div>
              </div>
              {[[num('48', cuenta), etiquetas[0]], [num(seguidores, cuenta), etiquetas[1]], [num('312', cuenta), etiquetas[2]]].map(([a, b], i) => (
                <div key={i} style={{ textAlign: 'center' }}>
                  <div style={{ fontWeight: 700, fontSize: 34 * U }}>{a}</div>
                  <div style={{ fontSize: 22 * U, opacity: 0.7 }}>{b}</div>
                </div>
              ))}
            </div>
            {[0.85, 0.65, 0.75].map((w, i) => <div key={i} style={{ width: `${w * 100}%`, height: 16 * U, borderRadius: 8 * U, background: claro ? '#E2E2E2' : '#2A2A2E', marginTop: (i ? 12 : 28) * U }} />)}
            <div style={{ position: 'relative', marginTop: 28 * U, height: 64 * U, borderRadius: 16 * U, background: pulsado ? (claro ? '#E9E9E9' : '#2A2A2E') : '#0A84FF', display: 'flex',
                          alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 30 * U, color: pulsado ? (claro ? '#111' : '#FFF') : '#FFF',
                          transform: `scale(${(1 - 0.06 * Math.sin(Math.PI * clamp((t - tPulsa + 0.1) / 0.2))).toFixed(4)})` }}>
              {pulsado ? etiquetas[4] : etiquetas[3]}
              {anillo > 0 && anillo < 1 && <div style={{ position: 'absolute', left: '50%', top: '50%', width: 300 * U * anillo, height: 300 * U * anillo, marginLeft: -150 * U * anillo,
                                                         marginTop: -150 * U * anillo, borderRadius: '50%', border: `${4 * U}px solid rgba(255,255,255,${(1 - anillo).toFixed(3)})` }} />}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 * U, marginTop: 30 * U }}>
              {Array.from({ length: 9 }).map((_, i) => {
                const img = imgs[i % Math.max(1, imgs.length)];
                const pk = clamp((t - 0.5 - i * 0.06) / 0.25);
                return (
                  <div key={i} style={{ aspectRatio: '1', background: img ? '#000' : `linear-gradient(${45 + i * 30}deg, ${mezcla(ac, [255, 255, 255], 0.2 + 0.06 * i)}, ${mezcla(ac, [0, 0, 0], 0.15 + 0.07 * (i % 4))})`,
                                        overflow: 'hidden', opacity: pk, transform: `scale(${(0.8 + 0.2 * pk).toFixed(3)})` }}>
                    {img && <Img src={src(img)} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
        {t > tPulsa - 0.5 && t < tPulsa + 0.7 && (
          <Img src={staticFile('stickers/rcs_emoji_backhand_index_pointing_up.png')}
               style={{ position: 'absolute', left: PW * 0.48, top: PH * 0.45 + (1 - easeOut((t - tPulsa + 0.5) / 0.4)) * 200 * U - (t > tPulsa ? 10 * U : 0), width: 150 * U, height: 150 * U,
                        transform: 'rotate(-8deg)', filter: `drop-shadow(0 ${8 * U}px ${12 * U}px rgba(0,0,0,.5))` }} />
        )}
      </div>
      <div style={{ position: 'absolute', left: vert ? 70 * U : W * 0.06, width: vert ? W - 140 * U : W * 0.36, top: vert ? H * 0.06 : H * 0.36, textAlign: vert ? 'center' : 'left' }}>
        {palabras.map((w, i) => {
          const es = w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '') === ck;
          const p = easeOut((t - 0.25 - i * 0.08) / 0.35);
          return (
            <span key={i} style={{ display: 'inline-block', marginRight: '0.22em', fontFamily: es ? FAMILIA.display : FAMILIA.inter, fontStyle: es ? 'italic' : 'normal', fontWeight: es ? 400 : 700,
                                   fontSize: (es ? 104 : 80) * U, lineHeight: 1.05, color: es ? ac : tinta, opacity: p, transform: `translateY(${((1 - p) * 20 * U).toFixed(1)}px)` }}>{w}</span>
          );
        })}
      </div>
    </Escena>
  );
};

/* ================================================================================================ TijerasE */
export type TijerasProps = Base & { titulo?: string };
export const TijerasE: React.FC<TijerasProps> = ({ titulo = '', variante = 'neon', salida = 0.3 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU(), S = useResorte();
  const { t } = useVida(salida);
  const claro = variante === 'claro';
  const fondo = claro ? '#F2F2F0' : '#151515';
  const tinta = claro ? '#151515' : '#FFFFFF';
  const grad = 'linear-gradient(110deg, #F2E43A 0%, #9DF3D8 45%, #E7A6FF 75%, #D946EF 100%)';
  const cx = W / 2, cy = H * 0.46;
  const CW = 760 * U, CH = 440 * U;
  const fase1 = easeOut(t / 0.35);
  const aCinta = suave((t - 0.75) / 0.35);                                   // la tarjeta se vuelve cinta ondulada
  const corte1 = 1.25, corte2 = 1.55;
  const sep = suave((t - 1.85) / 0.5);                                      // los trozos se separan y se vuelven clips
  const tijera = (x: number, tc: number, desdeArriba: boolean, k: string) => {
    const llega = easeOut((t - (tc - 0.35)) / 0.3);
    const cierra = clamp((t - tc) / 0.12);
    const va = clamp((t - tc - 0.15) / 0.3);
    if (llega <= 0 || va >= 1) return null;
    const y = cy + (desdeArriba ? -1 : 1) * ((1 - llega) * 600 * U + va * 700 * U) + (desdeArriba ? -80 * U : 80 * U);
    const ab = 22 * (1 - cierra) + 4;
    return (
      <div key={k} style={{ position: 'absolute', left: x - 90 * U, top: y - 180 * U, width: 180 * U, height: 360 * U, transform: `rotate(${desdeArriba ? 180 : 0}deg)` }}>
        <div style={{ position: 'absolute', inset: 0, transformOrigin: '50% 45%', transform: `rotate(${-ab}deg)` }}><Glifo nombre="scissors" lado={180 * U} color={tinta} relleno={false} grosor={1.6} /></div>
        <div style={{ position: 'absolute', inset: 0, transformOrigin: '50% 45%', transform: `rotate(${ab}deg) scaleX(-1)`, opacity: 0.85 }}><Glifo nombre="scissors" lado={180 * U} color={tinta} relleno={false} grosor={1.6} /></div>
      </div>
    );
  };
  const trozos = [0, 1, 2];
  return (
    <Escena fondo={fondo} salida={salida}>
      {titulo && <div style={{ position: 'absolute', left: 0, width: W, top: H * 0.1, textAlign: 'center', fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 110 * U, color: tinta,
                               opacity: clamp((t - 0.2) / 0.3), letterSpacing: '0.04em' }}>{titulo}</div>}
      {aCinta < 0.999 && (
        <div style={{ position: 'absolute', left: cx - CW / 2, top: cy - CH / 2, width: CW, height: CH, borderRadius: 30 * U, background: grad, overflow: 'hidden',
                      transform: `scale(${(0.6 + 0.4 * fase1).toFixed(4)}) scaleY(${(1 - 0.55 * aCinta).toFixed(4)})`, opacity: (1 - aCinta) * clamp(fase1 * 2),
                      boxShadow: `0 ${20 * U}px ${50 * U}px rgba(0,0,0,.45)` }}>
          <div style={{ position: 'absolute', left: '50%', top: '50%', width: 0, height: 0, marginLeft: -30 * U, marginTop: -45 * U, borderTop: `${45 * U}px solid transparent`,
                        borderBottom: `${45 * U}px solid transparent`, borderLeft: `${75 * U}px solid rgba(255,255,255,.95)` }} />
          <div style={{ position: 'absolute', left: 40 * U, right: 40 * U, bottom: 34 * U, height: 6 * U, background: 'rgba(255,255,255,.4)', borderRadius: 3 * U }}>
            <div style={{ width: `${(clamp(t / 0.75) * 100).toFixed(1)}%`, height: '100%', background: '#FFF', borderRadius: 3 * U }} />
          </div>
        </div>
      )}
      {aCinta > 0.001 && (
        <svg style={{ position: 'absolute', inset: 0, width: W, height: H, overflow: 'visible' }}>
          <defs><linearGradient id="gcinta" x1="0" x2="1"><stop offset="0" stopColor="#F2E43A" /><stop offset=".45" stopColor="#9DF3D8" /><stop offset=".75" stopColor="#E7A6FF" /><stop offset="1" stopColor="#D946EF" /></linearGradient></defs>
          {trozos.map(k => {
            const x0 = cx - CW / 2 + (k * CW) / 3, x1 = x0 + CW / 3;
            const corte = (k > 0 && t > corte1) || (k > 1 && t > corte2) || (k === 0 && t > corte1);
            const dx = (k - 1) * sep * 260 * U, dy = -sep * (80 + k * 40) * U + (k === 1 ? sep * 120 * U : 0);
            const rot = sep * (k - 1) * 14;
            const ond = (x: number) => Math.sin((x / CW) * Math.PI * 3 + t * 3) * 34 * U * (1 - sep);
            const alto = CH * 0.45 * (1 - sep) + 230 * U * sep;
            const pts = Array.from({ length: 9 }).map((_, j) => { const x = x0 + ((x1 - x0) * j) / 8; return [x, cy + ond(x)]; });
            const d = 'M ' + pts.map(p => `${p[0].toFixed(1)} ${(p[1] - alto / 2).toFixed(1)}`).join(' L ') + ' L ' +
                      [...pts].reverse().map(p => `${p[0].toFixed(1)} ${(p[1] + alto / 2).toFixed(1)}`).join(' L ') + ' Z';
            return (
              <g key={k} transform={`translate(${dx.toFixed(1)} ${dy.toFixed(1)}) rotate(${rot.toFixed(2)} ${(x0 + x1) / 2} ${cy})`} opacity={aCinta}>
                <path d={d} fill="url(#gcinta)" stroke={corte ? (claro ? '#F2F2F0' : '#151515') : 'none'} strokeWidth={6 * U} />
                {sep > 0.3 && <path d={`M ${(x0 + x1) / 2 - 20 * U} ${cy - 30 * U} L ${(x0 + x1) / 2 + 30 * U} ${cy} L ${(x0 + x1) / 2 - 20 * U} ${cy + 30 * U} Z`} fill="#FFF" opacity={(sep - 0.3) / 0.7} />}
              </g>
            );
          })}
          {sep > 0.05 && Array.from({ length: 14 }).map((_, i) => (
            <circle key={i} cx={cx + (azar(i) - 0.5) * CW * 1.3 * sep} cy={cy + (azar(i + 7) - 0.5) * 420 * U * sep - sep * 60 * U} r={(6 + azar(i + 3) * 10) * U}
                    fill={['#F2E43A', '#9DF3D8', '#E7A6FF', '#7CF29B'][i % 4]} opacity={sep * 0.8} />
          ))}
        </svg>
      )}
      {tijera(cx - CW / 6, corte1, true, 'a')}
      {tijera(cx + CW / 6, corte2, false, 'b')}
    </Escena>
  );
};

/* ================================================================================================ FotoE (v5.5.3: foto de internet con licencia) */
// La foto que se busca en internet (fuentes_web.py: Openverse, Wikimedia Commons, Pexels, Pixabay) para lo que se nombra: a pantalla completa con
// un movimiento lento de cámara (Ken Burns), enmarcada sobre su propia versión desenfocada, o en un círculo. La palabra dicha encima y el crédito
// (obligatorio en las CC BY) en letra pequeña abajo a la izquierda.
export type FotoProps = Base & { foto?: string; palabra?: string; credito?: string };
export const FotoE: React.FC<FotoProps> = ({ foto = '', palabra = '', credito = '', variante = 'completa', acento, salida = 0.3 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU(), S = useResorte();
  const { t, fin } = useVida(salida);
  const vert = H >= W;
  const ac = hex(acento, '#FFD23F');
  const q = clamp(t / Math.max(1, fin));
  const zoom = 1.16 - 0.12 * suave(q), dx = (azar(palabra.length) - 0.5) * 60 * U * q, dy = -30 * U * q;
  const pp = easeOut((t - 0.25) / 0.45);
  const etiqueta = palabra && (
    <div style={{ position: 'absolute', left: 0, width: W, top: vert ? H * 0.12 : H * 0.1, textAlign: 'center', opacity: pp, transform: `translateY(${((1 - pp) * 30 * U).toFixed(1)}px)` }}>
      <span style={{ display: 'inline-block', fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: Math.min(150, 1400 / Math.max(5, palabra.length)) * U, color: '#FFFFFF',
                     letterSpacing: '0.02em', textTransform: 'uppercase', textShadow: `0 ${6 * U}px ${28 * U}px rgba(0,0,0,.65)`, padding: `0 ${20 * U}px`,
                     borderBottom: `${10 * U}px solid ${ac}` }}>{palabra}</span>
    </div>
  );
  const pie = credito && (
    <div style={{ position: 'absolute', left: 28 * U, bottom: 26 * U, maxWidth: W * 0.8, fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 20 * U, color: 'rgba(255,255,255,.72)',
                  textShadow: `0 ${1 * U}px ${4 * U}px rgba(0,0,0,.8)` }}>{credito}</div>
  );
  if (variante === 'marco' || variante === 'circulo') {
    const circ = variante === 'circulo';
    const L = circ ? Math.min(W, H) * 0.78 : Math.min(W * 0.84, H * 0.5);
    const pc = S(0.08, { damping: 13, stiffness: 150 });
    return (
      <Escena fondo="#0B0B0D" salida={salida}>
        {foto && <Img src={src(foto)} style={{ position: 'absolute', inset: -60 * U, width: W + 120 * U, height: H + 120 * U, objectFit: 'cover', filter: `blur(${36 * U}px) brightness(.55) saturate(1.2)`,
                                               transform: `scale(${zoom.toFixed(4)})` }} />}
        {circ && (
          <svg style={{ position: 'absolute', inset: 0, width: W, height: H }}>
            <circle cx={W / 2} cy={H * (vert ? 0.46 : 0.5)} r={L / 2 + 22 * U} fill="none" stroke={ac} strokeWidth={8 * U} pathLength={1} strokeDasharray="1"
                    strokeDashoffset={(1 - easeOut((t - 0.15) / 0.6)).toFixed(4)} style={{ filter: `drop-shadow(0 0 ${16 * U}px ${ac})` }} />
          </svg>
        )}
        <div style={{ position: 'absolute', left: W / 2 - L / 2, top: H * (vert ? 0.46 : 0.5) - (circ ? L / 2 : L * 0.62), width: L, height: circ ? L : L * 1.24,
                      borderRadius: circ ? '50%' : 8 * U, overflow: 'hidden', background: '#222', border: circ ? 'none' : `${18 * U}px solid #FAFAF7`, boxSizing: 'border-box',
                      boxShadow: `0 ${30 * U}px ${70 * U}px rgba(0,0,0,.6)`, opacity: clamp(pc * 2),
                      transform: `rotate(${circ ? 0 : (-3 + (1 - clamp(pc)) * -10).toFixed(2)}deg) scale(${(0.8 + 0.2 * clamp(pc)).toFixed(4)})` }}>
          {foto && <Img src={src(foto)} style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${zoom.toFixed(4)}) translate(${dx.toFixed(1)}px, ${dy.toFixed(1)}px)` }} />}
        </div>
        {!circ && (
          <div style={{ position: 'absolute', left: W / 2 - 110 * U, top: H * (vert ? 0.46 : 0.5) - L * 0.62 - 30 * U, width: 220 * U, height: 60 * U, background: 'rgba(238,226,196,.85)',
                        transform: `rotate(-4deg) scaleX(${easeOut((t - 0.3) / 0.25).toFixed(4)})`, boxShadow: `0 ${2 * U}px ${6 * U}px rgba(0,0,0,.25)` }} />
        )}
        {etiqueta}
        {pie}
      </Escena>
    );
  }
  return (
    <Escena fondo="#000" salida={salida}>
      {foto && <Img src={src(foto)} style={{ position: 'absolute', inset: 0, width: W, height: H, objectFit: 'cover',
                                             transform: `scale(${zoom.toFixed(4)}) translate(${dx.toFixed(1)}px, ${dy.toFixed(1)}px)` }} />}
      <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(0,0,0,.55) 0%, rgba(0,0,0,0) 32%, rgba(0,0,0,0) 62%, rgba(0,0,0,.5) 100%)' }} />
      <Grano id="gfoto" op={0.12} frec={0.9} />
      {etiqueta}
      {pie}
    </Escena>
  );
};
