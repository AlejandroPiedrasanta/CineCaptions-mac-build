// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/EmojiPro.tsx — v5.25 «Emojis animados» de la Edición PRO (el usuario: «emojis con diferentes estilos 3D-2D, siempre
// animados, no estáticos, archivo Lottie»). Un emoji en su sitio (x, y en % del cuadro) que SIEMPRE se mueve:
//   2D (Lottie de Google, Noto Emoji Animation, CC BY 4.0): animado · rebote · brillo · burbuja · sticker
//   3D (Fluent de Microsoft, MIT, con movimiento):            3d_salto · 3d_flota · 3d_giro · 3d_gelatina · 3d_estallido
// `fuente` 'lottie' (lottie = los datos, o null = el que trae el programa en public/lottie) o 'png' (imagen = data URL, o null = public/stickers).
// `energia` (la intensidad: 0,7 / 1 / 1,35) escala lo que se mueve; `tamano` = % del lado corto del cuadro. Entra con un resorte y sale con fundido.
import { Lottie, LottieAnimationData } from '@remotion/lottie';
import { AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { EmojiAnimado, idEmoji } from './Emoji';

type Props = {
  id: string; variante?: string; fuente?: string; lottie?: LottieAnimationData | null; imagen?: string | null;
  x?: number; y?: number; tamano?: number; energia?: number; acento?: string;
};

const CHISPAS = ['#FFFFFF', '#FFD54A'];

export const EmojiPro: React.FC<Props> = ({ id, variante = 'rebote', fuente = 'png', lottie = null, imagen = null, x = 50, y = 30, tamano = 16,
                                            energia = 1, acento = '#FFC24D' }) => {
  const f = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const t = f / fps;
  const e = Math.max(0.3, Number(energia) || 1);
  const lado = (Number(tamano) / 100) * Math.min(width, height);
  const n = idEmoji(id);
  const resorte = (amort: number, retraso = 0) => spring({ frame: f - retraso, fps, config: { damping: amort, stiffness: 170, mass: 0.7 } });
  const salida = interpolate(f, [durationInFrames - Math.round(0.28 * fps), durationInFrames - 1], [1, 0],
                             { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  let escala = 1, dx = 0, dy = 0, rot = 0, sx = 1, sy = 1, rotY = 0, sombra = 0;
  let filtro = '';
  let detras: React.ReactNode = null;
  let delante: React.ReactNode = null;
  let interior = 1;                                              // (la burbuja: el emoji, algo más pequeño dentro)
  const salto = (periodo: number, alto: number) => {             // un saltito cada `periodo` s con aplastamiento al caer
    const k = Math.abs(Math.sin((t * Math.PI) / periodo));
    const choque = Math.pow(1 - k, 6);
    return { dy: -k * lado * alto * e, sx: 1 + 0.09 * e * choque, sy: 1 - 0.09 * e * choque, k };
  };
  switch (variante) {
    case 'animado':
      escala = resorte(13);
      dy = Math.sin(t * 2.2) * lado * 0.03 * e;
      break;
    case 'rebote': {
      escala = resorte(7);
      const s = salto(1.1, 0.1);
      dy = s.dy; sx = s.sx; sy = s.sy;
      break;
    }
    case 'brillo': {
      escala = resorte(11);
      dy = Math.sin(t * 2) * lado * 0.025 * e;
      const pulso = 0.55 + 0.25 * Math.sin(t * 4) * Math.min(1.2, e);
      filtro = `drop-shadow(0 0 ${lado * 0.07}px ${acento})`;
      detras = <div style={{ position: 'absolute', left: -lado * 0.45, top: -lado * 0.45, width: lado * 1.9, height: lado * 1.9, borderRadius: '50%',
                             background: `radial-gradient(circle, ${acento} 0%, ${acento}00 64%)`, opacity: pulso }} />;
      break;
    }
    case 'burbuja': {
      escala = resorte(10);
      dy = Math.sin(t * 1.9) * lado * 0.035 * e;
      const w = Math.sin(t * 5) * 0.035 * e;
      interior = 0.74;
      detras = <div style={{ position: 'absolute', left: -lado * 0.21, top: -lado * 0.21, width: lado * 1.42, height: lado * 1.42, borderRadius: '50%',
                             transform: `scale(${1 + w}, ${1 - w})`,
                             background: 'radial-gradient(circle at 34% 28%, rgba(255,255,255,0.58), rgba(255,255,255,0.14) 42%, rgba(255,255,255,0.05) 72%)',
                             border: `${Math.max(2, lado * 0.018)}px solid rgba(255,255,255,0.62)`,
                             boxShadow: `0 ${lado * 0.06}px ${lado * 0.16}px rgba(0,0,0,0.28), inset 0 0 ${lado * 0.12}px rgba(255,255,255,0.35)` }} />;
      break;
    }
    case 'sticker': {
      const ent = resorte(9);
      escala = ent;
      rot = interpolate(ent, [0, 1], [-28, -7]) + Math.sin(t * 2.6) * 3 * e;
      const o = Math.max(2, lado * 0.03);
      filtro = `drop-shadow(${o}px 0 0 #fff) drop-shadow(-${o}px 0 0 #fff) drop-shadow(0 ${o}px 0 #fff) drop-shadow(0 -${o}px 0 #fff) ` +
               `drop-shadow(0 ${o * 2}px ${o * 2.5}px rgba(0,0,0,0.35))`;
      break;
    }
    case '3d_salto': {
      const ent = resorte(8);
      const s = salto(1.25, 0.16);
      dy = interpolate(ent, [0, 1], [lado * 1.2, 0]) + (f > fps * 0.5 ? s.dy : 0);
      sx = s.sx; sy = s.sy;
      sombra = 1 - (f > fps * 0.5 ? s.k * 0.6 : 0.6 * (1 - ent));
      break;
    }
    case '3d_flota':
      escala = resorte(14);
      dy = Math.sin(t * 1.8) * lado * 0.09 * e;
      rot = Math.sin(t * 1.3) * 8 * e;
      sombra = 0.75 - Math.sin(t * 1.8) * 0.25;
      break;
    case '3d_giro': {
      // (siempre girando: entra con una vuelta entera y luego se mece de lado a lado ±35° y flota; nunca de canto —a 90° el PNG desaparece—)
      escala = resorte(12);
      rotY = interpolate(f, [0, Math.round(0.9 * fps)], [-360, 0], { extrapolateRight: 'clamp' }) + Math.sin(t * 2.1) * 35 * Math.min(1.2, e);
      dy = Math.sin(t * 2.4) * lado * 0.05 * e;
      sombra = 0.8;
      break;
    }
    case '3d_gelatina': {
      // (tiembla al entrar y vuelve a temblar cada 1,2 s, con un rebote suave entre medias: siempre se mueve)
      escala = resorte(9);
      const ph = t % 1.2;
      const amp = 0.15 * e * Math.exp(-ph * 1.7);
      sx = 1 + amp * Math.sin(ph * 16);
      sy = 1 - amp * Math.sin(ph * 16);
      dy = -Math.abs(Math.sin((t * Math.PI) / 1.2)) * lado * 0.04 * e;
      sombra = 0.8;
      break;
    }
    case '3d_estallido': {
      // (un estallido al entrar y, después, un pulso claro y chispas pequeñas cada 1,4 s: nunca se queda quieto)
      escala = resorte(6.5) * (1 + 0.07 * Math.sin(t * 5) * e);
      rot = Math.sin(t * 3.1) * 5 * e;
      const re = t > 0.8 ? (t - 0.8) % 1.4 : t;                    // el instante dentro de cada estallido (el primero, el grande)
      const grande = t <= 0.8;
      const onda = interpolate(re, [0, 0.5], [0, 1], { extrapolateRight: 'clamp' }) * (grande ? 1 : 0.75);
      const chispa = interpolate(re, [0, 0.15, 0.75], [0, 1, 0], { extrapolateRight: 'clamp' }) * (grande ? 1 : 0.8);
      delante = (
        <>
          <div style={{ position: 'absolute', left: lado / 2 - lado * 0.8 * onda, top: lado / 2 - lado * 0.8 * onda, width: lado * 1.6 * onda,
                        height: lado * 1.6 * onda, borderRadius: '50%', border: `${Math.max(2, lado * 0.025)}px solid ${acento}`, opacity: 0.85 * (1 - onda) }} />
          {Array.from({ length: 14 }, (_v, i) => {
            const ang = (i / 14) * Math.PI * 2 + 0.3;
            const d = interpolate(t, [0, 0.7], [lado * 0.3, lado * 1.15 * e], { extrapolateRight: 'clamp' });
            const r = lado * (i % 3 === 0 ? 0.075 : 0.05);
            return <div key={i} style={{ position: 'absolute', left: lado / 2 + Math.cos(ang) * d - r / 2, top: lado / 2 + Math.sin(ang) * d - r / 2,
                                         width: r, height: r, borderRadius: '50%', background: i % 3 === 0 ? acento : CHISPAS[i % 2], opacity: chispa,
                                         boxShadow: `0 0 ${r}px ${acento}` }} />;
          })}
        </>
      );
      sombra = 0.7;
      break;
    }
    default:
      escala = resorte(10);
      dy = Math.sin(t * 2) * lado * 0.03 * e;
  }
  const emoji = fuente === 'lottie'
    ? (lottie ? <Lottie animationData={lottie} loop style={{ width: '100%', height: '100%' }} /> : <EmojiAnimado id={n} lado={lado * interior} />)
    : <Img src={imagen || staticFile(`stickers/rcs_emoji_${n}.png`)} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />;
  const cx = (Number(x) / 100) * width;
  const cy = (Number(y) / 100) * height;
  return (
    <AbsoluteFill>
      {sombra > 0 && (                                            // (los 3D: la sombra se queda en el «suelo» mientras el emoji sube)
        <div style={{ position: 'absolute', left: cx - lado * 0.32, top: cy + lado * 0.42, width: lado * 0.64, height: lado * 0.13, borderRadius: '50%',
                      background: 'radial-gradient(ellipse, rgba(0,0,0,0.45), rgba(0,0,0,0) 70%)', opacity: sombra * escala * salida,
                      transform: `scale(${0.75 + 0.25 * sombra})` }} />
      )}
      <div style={{ position: 'absolute', left: cx - lado / 2, top: cy - lado / 2, width: lado, height: lado, opacity: salida,
                    transform: `translate(${dx}px, ${dy}px) perspective(${lado * 5}px) rotateY(${rotY}deg) rotate(${rot}deg) scale(${Math.max(0, escala)})` }}>
        {detras}
        <div style={{ position: 'absolute', left: (lado * (1 - interior)) / 2, top: (lado * (1 - interior)) / 2, width: lado * interior,
                      height: lado * interior, filter: filtro || undefined, transform: `scale(${sx}, ${sy})`, transformOrigin: '50% 90%' }}>
          {emoji}
        </div>
        {delante}
      </div>
    </AbsoluteFill>
  );
};
