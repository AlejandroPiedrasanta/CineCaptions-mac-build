// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/Subtitulo.tsx — los captions del Tema 5, con el sistema de la skill «Edit VIRAL Reels with AI» (skill videos/):
//   * DOS letras: una sans pequeña (Inter) para lo que se dice y una serif CURSIVA grande (DM Serif Text) para la frase clave, en el color de acento
//     (el que mejor va con el video: azul en planos fríos, ámbar en cálidos…); nada más: sin emojis, sin brillos, sin rebotes.
//   * las palabras entran cuando se dicen, desenfocadas → nítidas (suave, sin saltos); la frase clave un poco más lenta.
//   * la sans y la serif se tocan: la clave en su propia línea (o en la misma, si delante solo hay una o dos palabras cortas).
//   * tinta 'clara' (blanco sobre el video) u 'oscura' (tinta sobre las escenas de papel); modo 'detras': solo la frase clave, enorme, para ir
//     detrás de la persona (Magic Mask encima).
// El programa da `y` (centro del bloque, % del alto) y `escala` para no tapar ninguna cara.
// estilo 'editorial' (Tema 6, v5.4.52): las DOS líneas en una serif alta y fina, recta (Instrument Serif): lo que se dice pequeño y en blanco, la
// frase clave GRANDE en lima o en blanco (lo elige el programa); las palabras entran desenfocadas y con el espaciado cerrándose.
import { AbsoluteFill, continueRender, delayRender, useCurrentFrame, useVideoConfig } from 'remotion';
import { useEffect, useMemo, useState } from 'react';
import { FAMILIA, cargarFuentes, clamp } from './comun';

export type PalabraSub = { texto: string; t: number; clave?: boolean; rol?: string };
export type SubtituloProps = {
  palabras: PalabraSub[];
  modo?: 'normal' | 'detras';
  tinta?: 'clara' | 'oscura';
  y?: number;
  escala?: number;
  acento?: string;
  velo?: boolean;
  estilo?: 'skill' | 'editorial';
};

const SANS = { familia: 'CCInter', peso: 500, estilo: 'normal' as const };
const SERIF = { familia: 'CCDisplay', peso: 400, estilo: 'italic' as const };
const EDITORIAL = { familia: 'CCSerif', peso: 400, estilo: 'normal' as const };
const K_SERIF = 2.4;
const easeIn = (q: number) => q * q;                         // la serif mide 2,15 veces la sans

type Linea = { idx: number[]; serif: boolean };

/** Las líneas: [antes] [frase clave] [después]; lo de antes va en la línea de la clave si es corto. Sin clave: líneas de sans de ~34 letras. */
const lineasDe = (p: PalabraSub[]): Linea[] => {
  const k0 = p.findIndex(w => w.clave), k1 = p.length - 1 - [...p].reverse().findIndex(w => w.clave);
  const sans = (desde: number, hasta: number) => {
    const ls: Linea[] = [];
    let letras = 0;
    for (let i = desde; i < hasta; i++) {
      if (!ls.length || letras + p[i].texto.length > 34) { ls.push({ idx: [], serif: false }); letras = 0; }
      ls[ls.length - 1].idx.push(i);
      letras += p[i].texto.length + 1;
    }
    return ls;
  };
  if (k0 < 0) return sans(0, p.length);
  const antes = sans(0, k0);
  const clave: Linea = { idx: Array.from({ length: k1 - k0 + 1 }, (_, j) => k0 + j), serif: true };
  const letrasAntes = p.slice(0, k0).reduce((a, w) => a + w.texto.length + 1, 0);
  const despues = sans(k1 + 1, p.length);
  if (k0 > 0 && k0 <= 2 && letrasAntes <= 10) return [{ idx: [...antes[0].idx, ...clave.idx], serif: true }, ...despues];
  return [...antes, clave, ...despues];
};

export const Subtitulo: React.FC<SubtituloProps> = ({ palabras = [], modo = 'normal', tinta = 'clara', y = 56, escala = 1, acento = '#4C7DFF', velo = false,
                                                        estilo = 'skill' }) => {
  const ed = estilo === 'editorial';
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const t = frame / fps, fin = durationInFrames / fps;
  const [h] = useState(() => delayRender('medidas del subtítulo'));
  const [listo, setListo] = useState(false);
  useEffect(() => {
    let vivo = true;
    cargarFuentes().catch(() => undefined).then(() => { if (vivo) setListo(true); });
    return () => { vivo = false; };
  }, []);
  useEffect(() => { if (listo) continueRender(h); }, [listo, h]);
  const detras = modo === 'detras';
  const ps = useMemo(() => (detras ? palabras.filter(w => w.clave) : palabras), [palabras, detras]);
  const anchos = useMemo(() => {                                   // ancho de cada palabra a 100 px de su letra
    if (!listo) return [];
    const ctx = document.createElement('canvas').getContext('2d');
    return ps.map(w => {
      const f = ed ? EDITORIAL : w.clave || detras ? SERIF : SANS;
      if (!ctx) return w.texto.length * 52;
      ctx.font = `${f.estilo} ${f.peso} 100px ${f.familia}`;
      return ctx.measureText(w.texto).width;
    });
  }, [listo, ps, detras, ed]);
  if (!listo || !ps.length) return <AbsoluteFill />;

  const corto = Math.min(width, height);
  let S = (ed ? 0.048 : 0.035) * corto * escala;                   // la sans (≈ 38 px en 1080); la serif editorial, algo mayor (es estrecha)
  const lineas: Linea[] = detras ? [{ idx: ps.map((_, i) => i), serif: true }] : lineasDe(ps);
  const tamDe = (i: number) => (ps[i].clave || detras ? (detras ? 2.6 : 1) * (ed ? 2.3 : K_SERIF) * S : S);
  const hueco = (i: number) => 0.27 * tamDe(i);
  const anchoLinea = (l: Linea) => l.idx.reduce((a, i, n) => a + (anchos[i] / 100) * tamDe(i) + (n ? hueco(i) : 0), 0);
  const maxAncho = width * (detras ? 0.8 : 0.86);
  const mayor = Math.max(...lineas.map(anchoLinea));
  if (mayor > maxAncho) S *= maxAncho / mayor;
  else if (detras) S *= Math.min(1.25, maxAncho / mayor);           // detrás: la clave llena el ancho
  const altoLinea = (l: Linea) => (l.serif ? Math.max(...l.idx.map(tamDe)) * (ed ? 0.9 : 0.98) : S * (ed ? 1.18 : 1.32));
  const altos = lineas.map(altoLinea);
  const total = altos.reduce((a, b) => a + b, 0);
  const top0 = (y / 100) * height - total / 2;

  const qs = fin > 0.5 ? clamp((t - (fin - 0.18)) / 0.18) : 0;      // salida: se desvanece y se desenfoca un poco
  const oscura = tinta === 'oscura';
  const sombra = oscura ? undefined : ed ? '0 0.03em 0.3em rgba(0,0,0,.42)' : '0 0.04em 0.22em rgba(0,0,0,.55), 0 0 0.04em rgba(0,0,0,.25)';

  const palabra = (i: number) => {
    const w = ps[i];
    const serif = !!(w.clave || detras);
    const dura = serif ? (ed ? 0.5 : 0.42) : (ed ? 0.34 : 0.28);
    const q = clamp((t - (w.t - 0.03)) / dura);
    const e = 1 - Math.pow(1 - q, 3);                               // ease-out: entra suave y se asienta
    const f = ed ? EDITORIAL : serif ? SERIF : SANS;
    const tam = tamDe(i);
    const tinta = oscura ? (ed ? '#3A2E28' : '#1D1D21') : '#FFFFFF';
    return (
      <span style={{
        display: 'inline-block', fontFamily: ed ? FAMILIA.serif : serif ? FAMILIA.display : FAMILIA.inter, fontWeight: f.peso, fontStyle: f.estilo, fontSize: tam,
        lineHeight: 1, letterSpacing: ed ? `${(-0.015 + (1 - e) * 0.06).toFixed(4)}em` : serif ? '-0.01em' : '-0.005em', whiteSpace: 'pre',
        padding: '0.08em 0.1em 0.16em', margin: '-0.08em -0.1em -0.16em',
        color: serif ? (oscura && ed ? tinta : acento) : tinta, textShadow: sombra,
        opacity: e * (serif ? 1 : oscura ? 0.92 : 0.96),
        filter: `blur(${((1 - e) * (serif ? 12 : 8)).toFixed(2)}px)`,
        transform: `translateY(${((1 - e) * (ed ? 0.08 : 0.14)).toFixed(3)}em)`,
      }}>{w.texto}</span>
    );
  };

  return (
    <AbsoluteFill style={{ opacity: 1 - qs, filter: qs > 0 ? `blur(${(qs * 4).toFixed(2)}px)` : undefined }}>
      {velo && !oscura && !detras && (() => {                        // video claro: un velo oscuro suave detrás (la skill: oscurecer lo de detrás)
        const w = mayor * (mayor > maxAncho ? maxAncho / mayor : 1) + 5 * S, hv = total + 3.2 * S;
        const p0 = easeIn(clamp((t - (ps[0].t - 0.1)) / 0.3));
        return <div style={{ position: 'absolute', left: (width - w) / 2, top: top0 - 1.6 * S, width: w, height: hv, opacity: p0,
                             background: 'radial-gradient(closest-side, rgba(0,0,0,.52), rgba(0,0,0,.34) 55%, rgba(0,0,0,0))' }} />;
      })()}
      {lineas.map((l, n) => (
        <div key={n} style={{ position: 'absolute', left: 0, width, top: top0 + altos.slice(0, n).reduce((a, b) => a + b, 0), height: altos[n],
                              display: 'flex', justifyContent: 'center', alignItems: 'baseline' }}>
          {l.idx.map((i, k) => (
            <span key={i} style={{ marginLeft: k ? hueco(i) : 0 }}>{palabra(i)}</span>
          ))}
        </div>
      ))}
    </AbsoluteFill>
  );
};
