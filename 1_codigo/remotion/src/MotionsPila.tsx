// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/MotionsPila.tsx — v5.82: los motions de la referencia del Estilo 4 («Pila lima») para la Edición PRO. Medidos cuadro a
// cuadro en la referencia y aprobados en su previa: el avión de papel que se posa junto a la línea de abajo, el visor REC, el tachado rojo de la
// palabra grande, el aro de luz en la cara con su mini píldora y las persianas en un corte.
// Todos a pantalla completa con fondo transparente; x / y en % del cuadro (los pone edicion_pro_pila.py con los captions, las caras y los cortes).
import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion';
import { FAMILIA, clamp, useFuentes } from './comun';

const ease = (x: number) => 1 - Math.pow(1 - clamp(x), 3);
const suave = (x: number) => { const v = clamp(x); return v * v * (3 - 2 * v); };
/** La unidad de diseño: 1 px de un vertical de 1080 (en horizontal, el de un 9:16 del mismo alto; en 4K, el doble). */
const unidad = (w: number, h: number) => Math.min(w, (h * 9) / 16) / 1080;

// ------------------------------------------------------------------------------------------------ avión de papel
// Las poses MEDIDAS de la referencia (30 fps, 1,833-2,867 s; ajustar_flecha.py): u = s desde el primer asomo, dx/dy = px de un cuadro de 720
// respecto del reposo, rumbo de la punta (°, y hacia abajo: −90 = arriba), escala, pliegue de las alas, perspectiva. Entra por abajo, barre a la
// izquierda en un arco amplio con la punta por delante, sube girando a la derecha y se posa apuntando arriba-derecha (−46°). Quieto después.
const POSES: number[][] = [[0.0, 340.69, 593.12, -50.0, 1.1537, 1.14, 1.0037], [0.033, 369.79, 520.46, -50.0, 1.1537, 1.14, 1.0037],
  [0.067, 398.9, 447.79, -97.25, 1.2207, 1.1266, 0.9568], [0.1, 367.75, 367.0, -128.67, 1.2585, 1.08, 0.9531],
  [0.133, 300.83, 307.16, -143.53, 1.266, 1.0256, 0.962], [0.167, 235.2, 268.35, -148.54, 1.2852, 0.9725, 0.9381],
  [0.2, 181.69, 241.37, -148.44, 1.3344, 0.9116, 0.8856], [0.233, 135.43, 218.99, -145.62, 1.3666, 0.87, 0.8481],
  [0.267, 97.2, 200.78, -141.5, 1.3544, 0.8638, 0.8448], [0.3, 64.84, 183.88, -136.62, 1.3267, 0.8688, 0.8551],
  [0.333, 37.55, 168.28, -130.47, 1.2892, 0.8797, 0.8757], [0.367, 14.62, 155.1, -122.19, 1.2299, 0.91, 0.9123],
  [0.4, -4.68, 141.62, -112.84, 1.1685, 0.9506, 0.9507], [0.433, -18.68, 128.88, -103.45, 1.1193, 0.9866, 0.9854],
  [0.467, -32.07, 115.54, -93.86, 1.0858, 1.0062, 1.0091], [0.5, -39.81, 101.69, -85.53, 1.079, 0.9997, 1.0058],
  [0.533, -44.43, 87.87, -78.84, 1.0891, 0.9797, 0.9862], [0.567, -45.56, 75.13, -73.01, 1.0945, 0.9675, 0.9721],
  [0.6, -44.12, 63.34, -68.39, 1.0907, 0.9644, 0.9681], [0.633, -40.43, 53.37, -64.81, 1.0846, 0.96, 0.9686],
  [0.667, -36.89, 44.23, -61.75, 1.0877, 0.9469, 0.962], [0.7, -31.87, 37.05, -59.11, 1.1069, 0.9244, 0.9409],
  [0.733, -28.05, 30.53, -56.42, 1.1315, 0.9012, 0.9161], [0.767, -23.95, 24.31, -54.06, 1.143, 0.8909, 0.903],
  [0.8, -19.99, 20.43, -52.45, 1.127, 0.905, 0.9128], [0.833, -16.44, 15.69, -51.09, 1.0818, 0.9434, 0.9491],
  [0.867, -13.15, 12.54, -50.03, 1.0404, 0.9756, 0.9829], [0.9, -9.94, 9.25, -49.09, 1.0378, 0.9709, 0.9824],
  [0.933, -6.99, 6.22, -47.91, 1.0513, 0.9531, 0.9683], [0.967, -5.52, 4.17, -46.88, 1.0448, 0.9572, 0.9709],
  [1.0, -3.11, 2.16, -46.47, 1.0248, 0.9753, 0.9842], [1.033, -1.67, 1.02, -46.31, 1.0094, 0.9875, 0.9948],
  [1.067, 0.0, 0.0, -46.0, 1.0, 0.99, 1.0]];
const GEO = { A: 57.5, B: 14.15, C: 36.75, trazo: 5.375, halo: 0.8375, radio: 5.0 };   // px de 720: punta, alas, semienvergadura, trazo, halo
const OBT = 1.0;                                                                        // obturación (fracción del cuadro) del desenfoque de movimiento
const REPOSO = [236.48, 768.7];                                                        // donde se posa en la referencia (px de 720 × 1280)
export const VUELO_AVION_S = POSES[POSES.length - 1][0];

const poseEn = (u: number): number[] => {
  if (u <= POSES[0][0]) return POSES[0].slice(1);
  for (let i = 0; i < POSES.length - 1; i++) {
    const a = POSES[i], b = POSES[i + 1];
    if (u <= b[0]) {
      const f = (u - a[0]) / Math.max(1e-6, b[0] - a[0]);
      return a.slice(1).map((v, j) => v + (b[j + 1] - v) * f);
    }
  }
  return POSES[POSES.length - 1].slice(1);
};

/** Los 4 puntos del icono «enviar» (punta, ala 1, interior, ala 2) con su pose: centro, rumbo, escala (px), pliegue y perspectiva. */
const puntosAvion = (cx: number, cy: number, th: number, s: number, k: number, p: number) => {
  const { A, B, C } = GEO;
  const ix = -(A - 2 * B) / 3;
  const loc = [[ix + A, 0], [ix - B, -C * k], [ix, 0], [ix - B, C * k]];
  const c = Math.cos((th * Math.PI) / 180), sn = Math.sin((th * Math.PI) / 180);
  return loc.map(([x, y]) => [cx + s * (x * p * c - y * sn), cy + s * (x * p * sn + y * c)]);
};

type AvionProps = { x?: number; y?: number; esc?: number; color?: string; entra?: number };

export const AvionPapel: React.FC<AvionProps> = ({ x = 30, y = 62, esc = 1, color = '#E0FB58', entra = 0 }) => {
  const frame = useCurrentFrame();
  const { fps, width: W, height: H } = useVideoConfig();
  const F = (unidad(W, H) * 1080) / 720;                         // px del cuadro por px de la referencia (720 de ancho)
  const u = frame / fps - entra;
  if (u < 0) return null;
  const dx = (x / 100) * W / F - REPOSO[0], dy = (y / 100) * H / F - REPOSO[1];
  // si el sitio queda más a la derecha que el de la referencia, la entrada sale de más cerca para asomar por abajo y no por el borde;
  // si queda más arriba, entra por donde en la referencia (por abajo) y en 0,15 s ya sigue el camino trasladado
  const xMax4 = Math.max(...POSES.slice(0, 4).map(q => REPOSO[0] + q[1]));
  const wx0 = dx <= 0 ? 1 : clamp(1 - (xMax4 + dx - 0.92 * (W / F)) / dx);
  const wy0 = dy >= 0 ? 1 : 0;
  const donde = (v: number) => {
    const q = poseEn(v);
    const e = suave(v / 0.15);
    return { q, cx: (REPOSO[0] + q[0] + dx * (wx0 + (1 - wx0) * e)) * F, cy: (REPOSO[1] + q[1] + dy * (wy0 + (1 - wy0) * e)) * F };
  };
  const m = 0.5 / fps;
  const P = donde(u), Pa = donde(Math.max(0, u - m)), Pb = donde(u + m);
  const vx = Pb.cx - Pa.cx, vy = Pb.cy - Pa.cy, giro = Pb.q[2] - Pa.q[2];
  const largo = Math.max(Math.abs(vx), Math.abs(vy)) * OBT + Math.abs(giro) * OBT * 0.6;
  const n = largo < 1.5 ? 1 : Math.min(25, 1 + 2 * Math.ceil(largo / 1.6));
  const s = P.q[3] * F * esc;
  const ancho = Math.max(1, GEO.trazo * s);
  const copias = Array.from({ length: n }, (_, i) => {
    const t = n === 1 ? 0 : (i / (n - 1) - 0.5) * OBT;
    const pts = puntosAvion(P.cx + vx * t, P.cy + vy * t, P.q[2] + giro * t, s, P.q[4], P.q[5]);
    const d = `M${pts[0][0]},${pts[0][1]} L${pts[1][0]},${pts[1][1]} L${pts[2][0]},${pts[2][1]} L${pts[3][0]},${pts[3][1]} Z M${pts[2][0]},${pts[2][1]} L${pts[0][0]},${pts[0][1]}`;
    return <path key={i} d={d} fill="none" stroke={color} strokeWidth={ancho} strokeLinejoin="round" strokeLinecap="round"
                 opacity={1 / n} style={{ mixBlendMode: n > 1 ? 'plus-lighter' : 'normal' }} />;
  });
  return (
    <AbsoluteFill>
      <svg width={W} height={H} style={{ position: 'absolute', inset: 0, overflow: 'visible' }}>
        <defs>
          <filter id="halo-avion" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation={GEO.radio * F * esc} /></filter>
        </defs>
        <g filter="url(#halo-avion)" opacity={GEO.halo}><g style={{ isolation: 'isolate' }}>{copias}</g></g>
        <g style={{ isolation: 'isolate' }}>{copias}</g>
      </svg>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------------------------------------ visor REC
type VisorProps = { x0?: number; y0?: number; x1?: number; y1?: number; texto?: string; _dur?: number };

/** Esquinas de cámara y «● REC» que parpadea (la referencia: en el borde del cuadro; en vertical, la PRO lo pone en la zona segura). */
export const VisorRec: React.FC<VisorProps> = ({ x0 = 5.5, y0 = 4.5, x1 = 94.5, y1 = 95.5, texto = 'REC', _dur }) => {
  useFuentes();
  const frame = useCurrentFrame();
  const { fps, width: W, height: H, durationInFrames } = useVideoConfig();
  const U = unidad(W, H);
  const t = frame / fps, dur = Number(_dur) || durationInFrames / fps;
  const a = ease(t / 0.25) * (1 - ease((t - (dur - 0.2)) / 0.2));
  const X0 = (x0 / 100) * W, Y0 = (y0 / 100) * H, X1 = (x1 / 100) * W, Y1 = (y1 / 100) * H;
  const L = 64 * U, g = 4 * U;
  const blanco = `rgba(255,255,255,${(0.86 * a).toFixed(3)})`;
  const esquina = (x: number, y: number, sx: number, sy: number) => `M${x},${y + sy * L} L${x},${y} L${x + sx * L},${y}`;
  const luz = Math.floor(t * 2) % 2 === 0;
  return (
    <AbsoluteFill>
      <svg width={W} height={H} style={{ position: 'absolute', inset: 0 }}>
        {[esquina(X0, Y0, 1, 1), esquina(X1, Y0, -1, 1), esquina(X0, Y1, 1, -1), esquina(X1, Y1, -1, -1)].map((d, i) => (
          <path key={i} d={d} fill="none" stroke={blanco} strokeWidth={g} strokeLinecap="square" />
        ))}
        {luz && <circle cx={X0 + 36 * U} cy={Y0 + 44 * U} r={10 * U} fill={`rgba(240,30,40,${a.toFixed(3)})`} />}
      </svg>
      <div style={{ position: 'absolute', left: X0 + 58 * U, top: Y0 + 44 * U, transform: 'translateY(-50%)', fontFamily: FAMILIA.inter, fontWeight: 700,
                    fontSize: 34 * U, letterSpacing: '0.02em', color: blanco, lineHeight: 1 }}>{texto}</div>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------------------------------------ tachado rojo
type TachadoProps = { x0?: number; yc?: number; x1?: number; yb?: number; color?: string; entra?: number; lim0?: number; lim1?: number; muestra?: string };

/** La línea roja de la referencia: nace arriba a la izquierda y baja cruzando la palabra grande hasta pasarse por la derecha (0,2 s).
 *  x0 / x1 = izquierda y derecha de la grande, yc = su altura de mayúsculas y yb = su línea de base (% del cuadro); lim0 / lim1 = hasta
 *  dónde puede llegar la línea (la zona segura: lo que se pasa de la palabra se recorta ahí). */
export const TachadoRojo: React.FC<TachadoProps> = ({ x0 = 20, yc = 52, x1 = 80, yb = 58, color = '#E21C2E', entra = 0, lim0 = 0, lim1 = 100, muestra }) => {
  useFuentes();
  const frame = useCurrentFrame();
  const { fps, width: W, height: H } = useVideoConfig();
  const U = unidad(W, H);
  const k = ease((frame / fps - entra) / 0.2);
  // `muestra`: solo para la miniatura del carrusel (en el timeline la palabra es el caption de verdad, que va debajo)
  const palabra = muestra ? (
    <div style={{ position: 'absolute', left: (x0 / 100) * W, width: ((x1 - x0) / 100) * W, top: (yc / 100) * H, height: ((yb - yc) / 100) * H,
                  display: 'flex', alignItems: 'flex-end', justifyContent: 'center', fontFamily: FAMILIA.inter, fontWeight: 800, color: '#E0FB58',
                  fontSize: (((yb - yc) / 100) * H) / 0.727, lineHeight: 0.8, letterSpacing: '-0.045em' }}>{muestra}</div>
  ) : null;
  if (k <= 0) return palabra ? <AbsoluteFill>{palabra}</AbsoluteFill> : null;
  const cap = ((yb - yc) / 100) * H;
  const xa0 = (x0 / 100) * W - 0.018 * W, xb0 = (x1 / 100) * W + 0.05 * W;
  const ya0 = (yc / 100) * H - 0.12 * cap, yb0 = (yb / 100) * H - 0.3 * cap;
  const yEn = (x: number) => ya0 + ((yb0 - ya0) * (x - xa0)) / Math.max(1, xb0 - xa0);     // (recortada, la línea sigue la misma recta)
  const xa = Math.max(xa0, (lim0 / 100) * W), xb = Math.min(xb0, (lim1 / 100) * W);
  const ya = yEn(xa), yB = yEn(xb);
  const d = `M${xa},${ya} L${xa + (xb - xa) * k},${ya + (yB - ya) * k}`;
  return (
    <AbsoluteFill>
      {palabra}
      <svg width={W} height={H} style={{ position: 'absolute', inset: 0, overflow: 'visible' }}>
        <defs><filter id="brillo-tachado" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation={5 * U} /></filter></defs>
        <path d={d} stroke={color} strokeWidth={12 * U} strokeLinecap="butt" filter="url(#brillo-tachado)" />
        <path d={d} stroke={color} strokeWidth={12 * U} strokeLinecap="butt" />
      </svg>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------------------------------------ aro de luz en la cara
type AroProps = { cx?: number; cy?: number; r?: number; texto?: string; lado?: 'der' | 'izq'; aro?: string; pildora?: string };

/** Un aro de luz cálida que se dibuja alrededor de la cara en 0,45 s y, a los 0,35 s, una mini píldora salmón arriba que se escribe palabra a
 *  palabra (cada palabra cae, pequeña, a su sitio). cx / cy en % del cuadro, r en % del ANCHO; lado: hacia dónde sale la píldora. */
export const AroCara: React.FC<AroProps> = ({ cx = 50, cy = 32, r = 22, texto = '', lado = 'der', aro = '#FFE4BA', pildora = '#CD6860' }) => {
  useFuentes();
  const frame = useCurrentFrame();
  const { fps, width: W, height: H } = useVideoConfig();
  const U = unidad(W, H);
  const t = frame / fps;
  const X = (cx / 100) * W, Y = (cy / 100) * H, R = (r / 100) * W;
  const k = ease(t / 0.45);
  const largo = 2 * Math.PI * R;
  const arco = { cx: X, cy: Y, r: R, fill: 'none', stroke: aro, strokeWidth: 5 * U, strokeDasharray: `${largo} ${largo}`,
                 strokeDashoffset: largo * (1 - k), transform: `rotate(-90 ${X} ${Y})` };
  const tp = 0.35, kp = ease((t - tp) / 0.22);
  const palabras = texto.split(/\s+/).filter(Boolean);
  const [pr, pg, pb] = [1, 3, 5].map(i => parseInt(pildora.slice(i, i + 2), 16));
  const px = lado === 'der' ? X + R * 0.5 : X - R * 0.5, py = Y - R * 1.02;
  return (
    <AbsoluteFill>
      <svg width={W} height={H} style={{ position: 'absolute', inset: 0, overflow: 'visible' }}>
        <defs><filter id="luz-aro" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation={10 * U} /></filter></defs>
        <circle {...arco} filter="url(#luz-aro)" />
        <circle {...arco} />
      </svg>
      {palabras.length > 0 && t >= tp && (
        <div style={{ position: 'absolute', top: py, left: lado === 'der' ? px : undefined, right: lado === 'izq' ? W - px : undefined, height: 58 * U,
                      display: 'flex', alignItems: 'center', padding: `0 ${24 * U}px`, whiteSpace: 'nowrap' }}>
          <div style={{ position: 'absolute', inset: 0, borderRadius: 29 * U, background: `rgba(${pr},${pg},${pb},${(0.88 * kp).toFixed(3)})`,
                        border: `${2 * U}px solid rgba(255,190,180,${(0.59 * kp).toFixed(3)})`, transformOrigin: lado === 'der' ? 'left center' : 'right center',
                        transform: `scaleX(${(0.4 + 0.6 * kp).toFixed(3)})` }} />
          {palabras.map((w, j) => {
            const kw = (t - (tp + 0.12 + j * 0.16)) / 0.16;
            const e = ease(kw);
            return (
              <span key={j} style={{ position: 'relative', fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 30 * U, color: '#fff', lineHeight: 1,
                                     marginRight: j < palabras.length - 1 ? 8 * U : 0, opacity: clamp(kw * 1.5),
                                     transform: `translateY(${(-16 * U * (1 - e)).toFixed(2)}px) scale(${(0.6 + 0.4 * e).toFixed(3)})`, display: 'inline-block' }}>{w}</span>
            );
          })}
        </div>
      )}
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------------------------------------ persianas en un corte
type PersianasProps = { corte?: number; periodo?: number; _dur?: number };

/** Como la referencia: barras OSCURAS finas sobre el plano que se va, BLANCAS anchas que lo tapan casi todo (ahí cae el corte) y, ya en el
 *  plano nuevo, grises que se adelgazan hasta desaparecer, con un velo claro que lava el video (0,40 s en total). `corte` en s del clip. */
export const Persianas: React.FC<PersianasProps> = ({ corte, periodo = 36, _dur }) => {
  const frame = useCurrentFrame();
  const { fps, width: W, height: H, durationInFrames } = useVideoConfig();
  const U = unidad(W, H);
  const t = frame / fps;
  const c = typeof corte === 'number' ? corte : (Number(_dur) || durationInFrames / fps) / 2;
  const k = (t - (c - 0.2)) / 0.4;
  if (!(k > 0 && k < 1)) return null;
  const llena = Math.sin(Math.PI * k);
  const per = periodo * U;
  let color: string, ancho: number;
  if (k < 0.3) { color = 'rgba(24,24,26,0.67)'; ancho = per * (0.25 + 1.2 * k); }
  else if (k < 0.62) { color = 'rgba(238,238,240,0.96)'; ancho = per * 0.86; }
  else { const f = (1 - k) / 0.38; color = `rgba(205,205,210,${(0.86 * f).toFixed(3)})`; ancho = per * 0.75 * f; }
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ background: `rgba(200,200,204,${(0.42 * llena).toFixed(3)})` }} />
      {k >= 0.3 && k < 0.62 && <AbsoluteFill style={{ background: 'rgba(255,255,255,0.24)' }} />}
      <AbsoluteFill style={{ background: `repeating-linear-gradient(90deg, ${color} 0px, ${color} ${ancho.toFixed(2)}px, transparent ${ancho.toFixed(2)}px, transparent ${per.toFixed(2)}px)` }} />
    </AbsoluteFill>
  );
};
