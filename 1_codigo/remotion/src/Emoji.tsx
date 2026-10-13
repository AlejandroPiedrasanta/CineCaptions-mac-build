// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/Emoji.tsx — el emoji ANIMADO (v5.4.52, pedido del usuario: «iconos mejores y animados»): Noto Emoji Animation de Google
// (Lottie, CC BY 4.0, en public/lottie; los que trae el programa están en public/lottie/indice.json). Si ese emoji no tiene animación, el PNG 3D
// de siempre (Fluent, public/stickers). @remotion/lottie lo lleva fotograma a fotograma: el render es exacto y no depende del tiempo real.
import { Lottie, LottieAnimationData } from '@remotion/lottie';
import { useEffect, useState } from 'react';
import { Img, continueRender, delayRender, staticFile } from 'remotion';

let indice: Promise<string[]> | null = null;
const datos: Record<string, Promise<LottieAnimationData | null>> = {};

/** 'waving_hand', 'rcs_emoji_waving_hand.png' o 'emoji:waving_hand' → 'waving_hand'. */
export const idEmoji = (s: string) => String(s || '').replace(/^emoji:/, '').replace(/^rcs_emoji_/, '').replace(/\.png$/, '');

export const EmojiAnimado: React.FC<{ id: string; lado: number; style?: React.CSSProperties; bucle?: boolean }> = ({ id, lado, style, bucle = true }) => {
  const n = idEmoji(id);
  const [anim, setAnim] = useState<LottieAnimationData | null | undefined>(undefined);
  const [h] = useState(() => delayRender(`emoji ${n}`));
  useEffect(() => {
    let vivo = true;
    indice = indice || fetch(staticFile('lottie/indice.json')).then(r => r.json()).catch(() => []);
    indice.then(ids => {
      if (!ids.includes(n)) return null;
      datos[n] = datos[n] || fetch(staticFile(`lottie/${n}.json`)).then(r => r.json()).catch(() => null);
      return datos[n];
    }).then(d => { if (vivo) setAnim(d || null); continueRender(h); }).catch(() => { if (vivo) setAnim(null); continueRender(h); });
    return () => { vivo = false; };
  }, [n, h]);
  if (anim === undefined) return <div style={{ width: lado, height: lado, ...style }} />;
  if (anim === null) return <Img src={staticFile(`stickers/rcs_emoji_${n}.png`)} style={{ width: lado, height: lado, objectFit: 'contain', ...style }} />;
  return (
    <div style={{ width: lado, height: lado, ...style }}>
      <Lottie animationData={anim} loop={bucle} style={{ width: '100%', height: '100%' }} />
    </div>
  );
};
