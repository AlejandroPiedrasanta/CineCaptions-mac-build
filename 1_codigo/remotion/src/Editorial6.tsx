// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/Editorial6.tsx — los elementos del Tema 6 («Editorial», v5.4.52): blancos, limpios, con sombra cálida, como el video de
// referencia del usuario (captions en serif fina, escenas melocotón):
//   visor   las esquinas de enfoque de la cámara que se cierran sobre la cara («tú mismo», «yourself») con la rejilla de tercios un momento
//   buscar  la barra de búsqueda: se escribe la palabra que hay que comentar y se pulsa el botón (con su onda)
//   perfil  la tarjeta de perfil: la cara, el @usuario (si se puso) y la cifra que se dice contando («100 mil seguidores»)
//   equipo  la píldora con tres caras (emoji 3D) y la palabra («el equipo», «mis clientes»)
// Nunca enseña un dato que no se dijo.
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { FAMILIA, clamp, rgb, useFuentes } from './comun';
import { EmojiAnimado } from './Emoji';

const easeOut = (q: number) => 1 - Math.pow(1 - clamp(q), 3);
const resorte = (q: number) => { const x = clamp(q); return 1 - Math.exp(-6 * x) * Math.cos(9 * x); };

export type EditorialProps = {
  tipo?: 'visor' | 'buscar' | 'perfil' | 'equipo'; y?: number; escala?: number; acento?: string;
  caja?: number[]; texto?: string; kicker?: string; valor?: string; etiqueta?: string; cara?: string; usuario?: string; caras?: string[];
};

const SOMBRA = (U: number) => `0 ${18 * U}px ${46 * U}px rgba(60,35,20,.22), 0 ${2 * U}px ${6 * U}px rgba(60,35,20,.10)`;

export const EditorialT6: React.FC<EditorialProps> = ({ tipo = 'visor', y = 40, escala = 1, acento = '#F26B3A', caja = [0.35, 0.2, 0.65, 0.45], texto = '', kicker = '',
                                                         valor = '', etiqueta = '', cara = '', usuario = '', caras = [] }) => {
  useFuentes();
  const frame = useCurrentFrame();
  const { fps, width: W, height: H, durationInFrames } = useVideoConfig();
  const t = frame / fps, fin = durationInFrames / fps;
  const U = (Math.min(W, H) / 1080) * escala;
  const [r, g, b] = rgb(acento);
  const e = resorte(t / 0.5), s = easeOut((t - (fin - 0.28)) / 0.28);

  if (tipo === 'visor') {
    const [x0, y0, x1, y1] = caja;
    const cx = ((x0 + x1) / 2) * W, cy = ((y0 + y1) / 2) * H;
    const w = (x1 - x0) * W * 1.25, h = (y1 - y0) * H * 1.25;
    const k = 1 + 0.35 * (1 - easeOut(t / 0.35)) + 0.02 * Math.sin(t * 9) * clamp((t - 0.35) / 0.2) * (1 - clamp((t - 0.7) / 0.2));
    const L = Math.min(w, h) * 0.2, grosor = 5 * U;
    const rejilla = clamp(t / 0.2) * (1 - clamp((t - 0.9) / 0.3));
    const esquina = (sx: number, sy: number) => (
      <div style={{ position: 'absolute', left: cx + sx * (w * k) / 2 - (sx > 0 ? L : 0), top: cy + sy * (h * k) / 2 - (sy > 0 ? L : 0), width: L, height: L,
                    borderLeft: sx < 0 ? `${grosor}px solid #fff` : undefined, borderRight: sx > 0 ? `${grosor}px solid #fff` : undefined,
                    borderTop: sy < 0 ? `${grosor}px solid #fff` : undefined, borderBottom: sy > 0 ? `${grosor}px solid #fff` : undefined,
                    borderRadius: 4 * U, filter: `drop-shadow(0 0 ${4 * U}px rgba(0,0,0,.35))` }} />
    );
    return (
      <AbsoluteFill style={{ opacity: clamp(t / 0.12) * (1 - s) }}>
        {[1, 2].map(i => (
          <div key={`v${i}`} style={{ position: 'absolute', left: (W * i) / 3, top: 0, width: 1.5 * U, height: H, background: 'rgba(255,255,255,.35)', opacity: rejilla }} />
        ))}
        {[1, 2].map(i => (
          <div key={`h${i}`} style={{ position: 'absolute', top: (H * i) / 3, left: 0, height: 1.5 * U, width: W, background: 'rgba(255,255,255,.35)', opacity: rejilla }} />
        ))}
        {esquina(-1, -1)}{esquina(1, -1)}{esquina(-1, 1)}{esquina(1, 1)}
        <div style={{ position: 'absolute', left: cx - 9 * U, top: cy - 1 * U, width: 18 * U, height: 2 * U, background: 'rgba(255,255,255,.8)', opacity: rejilla }} />
        <div style={{ position: 'absolute', left: cx - 1 * U, top: cy - 9 * U, width: 2 * U, height: 18 * U, background: 'rgba(255,255,255,.8)', opacity: rejilla }} />
      </AbsoluteFill>
    );
  }

  let cuerpo: React.ReactNode = null;
  if (tipo === 'buscar') {
    const letras = Math.max(0, Math.min(texto.length, Math.floor((t - 0.35) / 0.075)));
    const escrito = texto.slice(0, letras);
    const tClic = 0.35 + texto.length * 0.075 + 0.35;
    const clic = clamp((t - tClic) / 0.16), onda = clamp((t - tClic) / 0.6);
    const ancho = Math.min(W * 0.8, 820 * U), alto = 104 * U;
    cuerpo = (
      <div style={{ position: 'relative', width: ancho, height: alto, borderRadius: alto / 2, background: 'rgba(255,255,255,.97)', boxShadow: SOMBRA(U),
                    display: 'flex', alignItems: 'center', padding: `0 ${14 * U}px 0 ${40 * U}px`, boxSizing: 'border-box' }}>
        <span style={{ flex: 1, fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 44 * U, color: '#1E1A18', whiteSpace: 'nowrap', overflow: 'hidden' }}>
          {escrito}<span style={{ opacity: Math.floor(t * 2.4) % 2 ? 0 : 0.8, marginLeft: 2 * U, color: `rgb(${r},${g},${b})` }}>|</span>
        </span>
        <div style={{ position: 'relative', width: alto - 28 * U, height: alto - 28 * U, flex: 'none' }}>
          {t > tClic && <div style={{ position: 'absolute', left: '50%', top: '50%', width: (alto - 28 * U) * (1 + 1.6 * onda), height: (alto - 28 * U) * (1 + 1.6 * onda),
                                      transform: 'translate(-50%,-50%)', borderRadius: '50%', background: `rgba(${r},${g},${b},${(0.35 * (1 - onda)).toFixed(3)})` }} />}
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: `linear-gradient(160deg, rgb(${Math.min(255, r + 30)},${Math.min(255, g + 30)},${Math.min(255, b + 30)}), rgb(${r},${g},${b}))`,
                        transform: `scale(${(1 - 0.14 * Math.sin(clic * Math.PI)).toFixed(3)})`, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        boxShadow: `0 ${6 * U}px ${14 * U}px rgba(${r},${g},${b},.45)` }}>
            <svg width={34 * U} height={34 * U} viewBox="0 0 24 24"><path d="M6 14 L12 8 L18 14" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </div>
        </div>
      </div>
    );
  } else if (tipo === 'perfil') {
    const limpio = String(valor || '').replace(/,/g, '');
    const m = limpio.match(/^([\d.]+)\s*([kKmM]?)$/);
    const v = m ? parseFloat(m[1]) : NaN, suf = m ? m[2].toUpperCase() : '';
    const dec = m ? (m[1].split('.')[1] || '').length : 0;
    const q = easeOut((t - 0.4) / 1.3);
    const n = isFinite(v) ? (v * q).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec }) + suf : valor;
    cuerpo = (
      <div style={{ display: 'flex', alignItems: 'center', gap: 30 * U, padding: `${26 * U}px ${44 * U}px ${26 * U}px ${26 * U}px`, borderRadius: 34 * U,
                    background: 'rgba(255,255,255,.97)', boxShadow: SOMBRA(U) }}>
        <div style={{ width: 120 * U, height: 120 * U, borderRadius: '50%', overflow: 'hidden', flex: 'none', background: '#F3E6DE',
                      boxShadow: `0 0 0 ${4 * U}px #fff, 0 0 0 ${7 * U}px rgba(${r},${g},${b},.65)` }}>
          {cara && <Img src={cara} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 * U }}>
          {usuario ? <span style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 30 * U, color: '#1E1A18' }}>{usuario}</span>
                   : <div style={{ width: 200 * U, height: 18 * U, borderRadius: 9 * U, background: '#EFE3DB' }} />}
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 14 * U }}>
            <span style={{ fontFamily: FAMILIA.serif, fontSize: 84 * U, lineHeight: 0.9, color: '#1E1A18' }}>{n}</span>
            <span style={{ fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 26 * U, color: '#9A8A80' }}>{etiqueta}</span>
          </div>
        </div>
      </div>
    );
  } else if (tipo === 'equipo') {
    const lista = (caras.length ? caras : ['smiling_face_with_smiling_eyes', 'star_struck', 'smiling_face_with_sunglasses']).slice(0, 3);
    cuerpo = (
      <div style={{ display: 'flex', alignItems: 'center', gap: 18 * U, padding: `${12 * U}px ${30 * U}px ${12 * U}px ${14 * U}px`, borderRadius: 999,
                    background: 'rgba(255,255,255,.97)', boxShadow: SOMBRA(U) }}>
        <div style={{ display: 'flex' }}>
          {lista.map((c, i) => {
            const p = resorte((t - 0.15 - i * 0.12) / 0.45);
            return (
              <div key={i} style={{ width: 64 * U, height: 64 * U, borderRadius: '50%', marginLeft: i ? -18 * U : 0, background: '#FBEDE5', border: `${4 * U}px solid #fff`,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center', transform: `scale(${clamp(p, 0, 1.15).toFixed(3)})`, zIndex: 3 - i }}>
                <EmojiAnimado id={c} lado={46 * U} />
              </div>
            );
          })}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.02 }}>
          {kicker && <span style={{ fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 17 * U, color: '#9A8A80' }}>{kicker}</span>}
          <span style={{ fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 36 * U, color: '#1E1A18' }}>{texto}</span>
        </div>
      </div>
    );
  }
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: 0, width: W, top: (y / 100) * H, display: 'flex', justifyContent: 'center', opacity: clamp(t / 0.16) * (1 - s),
                    transform: `translateY(${((1 - e) * 40 * U + s * 24 * U).toFixed(1)}px) scale(${(0.92 + 0.08 * clamp(e)).toFixed(4)})`,
                    filter: `blur(${((1 - clamp(e * 1.4)) * 8 + s * 6).toFixed(2)}px)` }}>
        <div style={{ transform: 'translateY(-50%)' }}>{cuerpo}</div>
      </div>
    </AbsoluteFill>
  );
};
