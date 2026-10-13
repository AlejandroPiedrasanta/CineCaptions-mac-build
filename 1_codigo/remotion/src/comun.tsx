// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/comun.tsx — lo común de las animaciones Remotion de la Edición PRO: fuentes (las mismas OFL de las piezas OGraf),
// unidades (U = lado corto / 1080) y resortes.
import { continueRender, delayRender, staticFile, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { useEffect, useState } from 'react';

export const FAMILIA = {
  serif: "'CCSerif', Georgia, serif",
  grotesk: "'CCGrotesk', 'Segoe UI', sans-serif",
  redonda: "'CCRedonda', 'Segoe UI', sans-serif",
  mono: "'CCMono', Consolas, monospace",
  inter: "'CCInter', 'Segoe UI', sans-serif",
  display: "'CCDisplay', Georgia, serif",
} as const;
export type Familia = keyof typeof FAMILIA;

const FUENTES: [string, string, FontFaceDescriptors][] = [
  ['CCSerif', 'fuentes/serif-400.woff2', { weight: '400' }],
  ['CCSerif', 'fuentes/serif-400i.woff2', { weight: '400', style: 'italic' }],
  ['CCGrotesk', 'fuentes/grotesk.woff2', { weight: '300 700' }],
  ['CCRedonda', 'fuentes/outfit-600.woff2', { weight: '600' }],
  ['CCRedonda', 'fuentes/outfit-800.woff2', { weight: '800' }],
  ['CCMono', 'fuentes/jbmono-500.woff2', { weight: '500' }],
  ['CCInter', 'fuentes/inter-400.ttf', { weight: '400' }],
  ['CCInter', 'fuentes/inter-500.ttf', { weight: '500' }],
  ['CCInter', 'fuentes/inter-700.ttf', { weight: '700' }],
  ['CCDisplay', 'fuentes/dmserif-i.ttf', { weight: '400', style: 'italic' }],
];
let cargadas: Promise<void> | null = null;

/** Las fuentes, una sola vez (quien tenga que MEDIR texto con ellas espera a esta promesa). */
export const cargarFuentes = () => {
  cargadas = cargadas || Promise.all(FUENTES.map(async ([n, f, d]) => {
    const ff = new FontFace(n, `url(${staticFile(f)})`, d);
    await ff.load();
    document.fonts.add(ff);
  })).then(() => undefined);
  return cargadas;
};

/** Carga las fuentes una vez y retiene el render hasta que están (Remotion espera a continueRender). */
export const useFuentes = () => {
  const [h] = useState(() => delayRender('fuentes'));
  useEffect(() => {
    cargarFuentes().then(() => continueRender(h)).catch(() => continueRender(h));
  }, [h]);
};

/** Unidad: 1 en 1080 de lado corto. */
export const useU = () => {
  const { width, height } = useVideoConfig();
  return Math.min(width, height) / 1080;
};

/** Progreso con resorte de Remotion desde el segundo t0 (0 antes; puede pasarse de 1 un poco si rebota). */
export const useResorte = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (t0: number, config: { damping?: number; stiffness?: number; mass?: number } = {}) =>
    spring({ frame: frame - Math.round(t0 * fps), fps, config: { damping: 14, stiffness: 160, mass: 1, ...config } });
};

export const clamp = (v: number, a = 0, b = 1) => Math.max(a, Math.min(b, v));

export const rgb = (hex: string): [number, number, number] => {
  const h = (hex || '#ffffff').replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map(c => c + c).join('') : h.slice(0, 6), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};
