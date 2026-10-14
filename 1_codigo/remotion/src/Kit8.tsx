// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/Kit8.tsx — v5.5.3: cuatro motions nuevos del kit (referencias del autor: recortes de revista, texto seleccionado
// del iPhone, calendario que se arranca y red de neón con interruptor). Mismas reglas que Kit7: todo sale de las props, `y` (centro, % del
// alto), `escala`, `salida` (s del fundido final), `variante` (ver VARIANTES en edicion_pro_kit7.py) y `acento` (color del video).
//   RecorteK     un concepto recortado de revista: trama de puntos con borde rasgado y chincheta, sticker a color con cinta, o neón
//   SeleccionK   la palabra clave «seleccionada» como en el iPhone: resalte, tiradores y el menú Copiar / Seleccionar todo / Compartir
//   CalendarioK  el calendario de «DÍA N» que va arrancando hojas hasta el número que se dice (cuenta atrás o reto de N días)
//   RedNeonK     las redes de neón conectadas a «TÚ» y el interruptor que pasa de CONSUMIENDO (rojo) a CREANDO (verde)
import { AbsoluteFill, Img, staticFile, useVideoConfig } from 'remotion';
import { FAMILIA, clamp, useFuentes, useResorte, useU } from './comun';
import { EmojiAnimado } from './Emoji';
import { easeOut, mezcla, suave, useVida } from './Kit7';

type Base = { x?: number; y?: number; escala?: number; salida?: number; variante?: string; acento?: string; tema?: string };
const esHex = (h?: string) => /^#?[0-9a-fA-F]{6}$/.test(String(h || ''));
const hex = (h: string | undefined, def: string) => (esHex(h) ? '#' + String(h).replace('#', '') : def);
const rgba = (h: string, a: number) => {
  const n = parseInt(h.replace('#', ''), 16) || 0;
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};

/* ------------------------------------------------------------------------------------------------ RecorteK */
export type RecorteProps = Base & { icono?: string; palabra?: string };
export const RecorteK: React.FC<RecorteProps> = ({ icono = 'light_bulb', palabra = '', x = 50, y = 40, escala = 1, salida = 0.35, variante = 'trama', acento }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { t, q } = useVida(salida);
  const cx = (W * x) / 100, cy = (H * y) / 100, lado = 430 * U;
  const neon = variante === 'neon', conColor = variante === 'color';
  const brilloNeon = hex(acento, '#3DFF8B');
  const p = S(0.02, { damping: 10, stiffness: 190 });
  const giroFinal = conColor ? 5 : -6;
  const vaiven = Math.sin(t * 1.6) * 1.3, flota = Math.sin(t * 1.25) * 4 * U;
  // el neón «se enciende» con parpadeos; el papel entra de golpe (escala que rebota)
  const parpadeo = neon ? (t < 0.08 ? 0 : t < 0.12 ? 1 : t < 0.16 ? 0.15 : t < 0.25 ? 1 : t < 0.28 ? 0.35 : 1) : 1;
  const late = 0.82 + 0.18 * Math.sin(t * 5.2);
  const escalaIn = neon ? 0.96 + 0.04 * easeOut(t / 0.3) : 1.55 - 0.55 * p;
  const giro = neon ? 0 : giroFinal - 16 * (1 - clamp(p)) + vaiven;
  const sombra = neon ? '' : `drop-shadow(${(6 + 14 * (1 - clamp(p))) * U}px ${(14 + 20 * (1 - clamp(p))) * U}px ${(14 + 10 * (1 - clamp(p))) * U}px rgba(0,0,0,.45))`;
  const url = staticFile(`recortes/${neon ? 'linea' : conColor ? 'color' : 'trama'}/${icono}.webp`);
  // la chincheta cae y se clava (trama); la cinta se estira en la esquina (color)
  const pc = S(0.32, { damping: 12, stiffness: 220 });
  const pt = easeOut((t - 0.3) / 0.22);
  const pl = easeOut((t - 0.38) / 0.35);
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <div style={{ position: 'absolute', left: cx - lado / 2, top: cy - lado / 2 + flota, width: lado, height: lado, opacity: neon ? parpadeo : clamp(p * 3),
                    transform: `rotate(${giro.toFixed(3)}deg) scale(${Math.max(0.001, escalaIn).toFixed(4)})`, filter: sombra || 'none' }}>
        {neon ? (
          <div style={{ position: 'absolute', inset: 0, filter: `drop-shadow(0 0 ${7 * U * late}px ${brilloNeon}) drop-shadow(0 0 ${24 * U * late}px ${brilloNeon})` }}>
            <div style={{ position: 'absolute', inset: 0, background: mezcla(brilloNeon, [255, 255, 255], 0.55),
                          WebkitMaskImage: `url(${url})`, maskImage: `url(${url})`, WebkitMaskSize: '100% 100%', maskSize: '100% 100%' }} />
          </div>
        ) : (
          <Img src={url} style={{ width: lado, height: lado }} />
        )}
        {!neon && !conColor && (
          <Img src={staticFile('stickers/rcs_emoji_pushpin.png')}
               style={{ position: 'absolute', left: lado / 2 - 48 * U, top: -30 * U - (1 - clamp(pc)) * 160 * U, width: 96 * U, height: 96 * U, opacity: clamp(pc * 4),
                        transform: `rotate(${18 - 10 * (1 - clamp(pc))}deg) scale(${(1.25 - 0.25 * clamp(pc)).toFixed(4)})`,
                        filter: `drop-shadow(${4 * U}px ${7 * U}px ${5 * U}px rgba(0,0,0,.35))` }} />
        )}
        {conColor && (
          <div style={{ position: 'absolute', left: -22 * U, top: 34 * U, width: 190 * U, height: 54 * U, transformOrigin: '0% 50%',
                        transform: `rotate(-38deg) scaleX(${pt.toFixed(4)})`, background: 'rgba(238,226,196,.82)',
                        clipPath: 'polygon(0% 8%, 4% 0%, 8% 10%, 12% 2%, 88% 0%, 92% 9%, 96% 1%, 100% 10%, 100% 90%, 96% 100%, 92% 91%, 88% 99%, 12% 100%, 8% 90%, 4% 99%, 0% 92%)',
                        boxShadow: `0 ${2 * U}px ${6 * U}px rgba(0,0,0,.18)` }} />
        )}
      </div>
      {palabra && (
        <div style={{ position: 'absolute', left: cx - W / 2, width: W, top: cy + lado * 0.47 + flota, display: 'flex', justifyContent: 'center' }}>
          {neon ? (
            <div style={{ fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 92 * U, letterSpacing: '0.04em', color: mezcla(brilloNeon, [255, 255, 255], 0.6),
                          textShadow: `0 0 ${10 * U * late}px ${brilloNeon}, 0 0 ${30 * U * late}px ${brilloNeon}`, opacity: parpadeo * clamp((t - 0.2) / 0.1),
                          textTransform: 'uppercase' }}>{palabra}</div>
          ) : conColor ? (
            <div style={{ fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 96 * U, color: '#FFFFFF', WebkitTextStroke: `${10 * U}px #141416`,
                          paintOrder: 'stroke fill', textTransform: 'uppercase', transform: `scale(${(0.6 + 0.4 * S(0.36, { damping: 11 })).toFixed(4)}) rotate(-3deg)`,
                          opacity: clamp((t - 0.36) / 0.08), filter: `drop-shadow(0 ${6 * U}px ${10 * U}px rgba(0,0,0,.4))` }}>{palabra}</div>
          ) : (
            <div style={{ fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 70 * U, color: '#F6F4EE', background: '#141416', padding: `${8 * U}px ${26 * U}px`,
                          letterSpacing: '0.08em', textTransform: 'uppercase', transform: 'rotate(-3deg)',
                          clipPath: `inset(0 ${((1 - pl) * 100).toFixed(2)}% 0 0)`, boxShadow: `0 ${8 * U}px ${18 * U}px rgba(0,0,0,.35)` }}>{palabra}</div>
          )}
        </div>
      )}
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ SeleccionK */
const MENU: Record<string, string[]> = { es: ['Copiar', 'Seleccionar todo', 'Compartir'], en: ['Copy', 'Select All', 'Share'], pt: ['Copiar', 'Selecionar tudo', 'Compartilhar'],
                                          fr: ['Copier', 'Tout sélectionner', 'Partager'], it: ['Copia', 'Seleziona tutto', 'Condividi'], de: ['Kopieren', 'Alles auswählen', 'Teilen'] };
export type SeleccionProps = Base & { arriba?: string; palabra?: string; abajo?: string; idioma?: string };
export const SeleccionK: React.FC<SeleccionProps> = ({ arriba = 'La acción crea', palabra = 'claridad.', abajo = '', idioma = 'es', x = 50, y = 46, escala = 1, salida = 0.35,
                                                       variante = 'azul', acento }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { t, q } = useVida(salida);
  const rosa = variante === 'rosa', oscuro = variante === 'oscuro';
  const tirador = rosa ? '#E06FA6' : oscuro ? hex(acento, '#FFD60A') : '#0A84FF';
  const resalte = rosa ? 'rgba(240,168,204,.6)' : oscuro ? rgba(hex(acento, '#FFD60A'), 0.3) : 'rgba(10,132,255,.36)';
  const tinta = rosa ? '#232326' : '#FFFFFF';
  const sombraTexto = rosa ? 'none' : `0 ${3 * U}px ${16 * U}px rgba(0,0,0,.55)`;
  const cx = (W * x) / 100, cy = (H * y) / 100;
  const tam = Math.min(200, 1500 / Math.max(4, String(palabra).length)) * U;   // la palabra grande cabe sin salirse
  const pa = String(arriba || '').split(/\s+/).filter(Boolean);
  const pw = S(0.22, { damping: 15, stiffness: 170 });
  const barrido = suave((t - 0.5) / 0.38);
  const pm = S(0.95, { damping: 13, stiffness: 210 });
  const pchispa = S(1.1, { damping: 10 });
  const opciones = MENU[String(idioma).slice(0, 2)] || MENU.es;
  const tarjeta = rosa ? S(0.0, { damping: 18 }) : 0;
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      {rosa && (
        <div style={{ position: 'absolute', left: cx - W * 0.44, width: W * 0.88, top: cy - 300 * U, height: 600 * U, borderRadius: 44 * U, background: 'rgba(244,243,240,.96)',
                      boxShadow: `0 ${24 * U}px ${60 * U}px rgba(0,0,0,.35)`, opacity: clamp(tarjeta * 1.4), transform: `scale(${(0.94 + 0.06 * clamp(tarjeta)).toFixed(4)})` }} />
      )}
      <div style={{ position: 'absolute', left: cx - W / 2, width: W, top: cy - 200 * U, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        {pa.length > 0 && (
          <div style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 66 * U, letterSpacing: '-0.025em', color: tinta, textShadow: sombraTexto,
                        textDecoration: 'underline', textDecorationThickness: 5 * U, textUnderlineOffset: 10 * U, marginBottom: 6 * U }}>
            {pa.map((w, i) => {
              const p = easeOut((t - 0.04 - i * 0.07) / 0.3);
              return <span key={i} style={{ display: 'inline-block', marginRight: '0.24em', opacity: p, transform: `translateY(${((1 - p) * 14 * U).toFixed(2)}px)` }}>{w}</span>;
            })}
          </div>
        )}
        <div style={{ position: 'relative', display: 'inline-block', padding: `0 ${18 * U}px`, opacity: clamp(pw * 2), transform: `scale(${(1.12 - 0.12 * clamp(pw)).toFixed(4)})` }}>
          <div style={{ position: 'absolute', left: 0, top: tam * 0.1, height: tam * 0.92, width: `${(barrido * 100).toFixed(2)}%`, background: resalte }} />
          {barrido > 0.01 && (
            <>
              <div style={{ position: 'absolute', left: -3 * U, top: tam * 0.06, width: 7 * U, height: tam * 1.0, borderRadius: 4 * U, background: tirador }}>
                <div style={{ position: 'absolute', left: -12 * U, top: -24 * U, width: 31 * U, height: 31 * U, borderRadius: '50%', background: tirador }} />
              </div>
              <div style={{ position: 'absolute', left: `calc(${(barrido * 100).toFixed(2)}% - ${4 * U}px)`, top: tam * 0.06, width: 7 * U, height: tam * 1.0, borderRadius: 4 * U, background: tirador }}>
                <div style={{ position: 'absolute', left: -12 * U, bottom: -24 * U, width: 31 * U, height: 31 * U, borderRadius: '50%', background: tirador }} />
              </div>
            </>
          )}
          <div style={{ position: 'relative', fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: tam, lineHeight: 1.08, letterSpacing: '-0.05em', color: tinta, textShadow: sombraTexto,
                        filter: `blur(${((1 - clamp(pw)) * 8 * U).toFixed(2)}px)` }}>{palabra}</div>
          {pm > 0.01 && (
            <div style={{ position: 'absolute', left: '50%', top: (pa.length ? -208 : -112) * U, transform: `translateX(-50%) scale(${Math.max(0.001, 0.6 + 0.4 * pm).toFixed(4)})`, transformOrigin: '50% 100%',
                          opacity: clamp(pm * 2), display: 'flex', alignItems: 'center', background: '#FFFFFF', borderRadius: 18 * U, whiteSpace: 'nowrap',
                          boxShadow: `0 ${10 * U}px ${30 * U}px rgba(0,0,0,.28)`, fontFamily: FAMILIA.inter, fontWeight: 500, fontSize: 34 * U, color: '#1C1C1E' }}>
              {opciones.map((o, i) => (
                <div key={i} style={{ padding: `${18 * U}px ${26 * U}px`, borderLeft: i ? `${1.5 * U}px solid rgba(60,60,67,.22)` : 'none' }}>{o}</div>
              ))}
              <div style={{ padding: `${18 * U}px ${20 * U}px`, borderLeft: `${1.5 * U}px solid rgba(60,60,67,.22)`, fontWeight: 700 }}>›</div>
              <div style={{ position: 'absolute', left: '50%', bottom: -13 * U, marginLeft: -14 * U, width: 0, height: 0, borderLeft: `${14 * U}px solid transparent`,
                            borderRight: `${14 * U}px solid transparent`, borderTop: `${14 * U}px solid #FFFFFF` }} />
            </div>
          )}
          {pchispa > 0.01 && (
            <div style={{ position: 'absolute', right: -tam * 0.86, top: -tam * 0.14, transform: `scale(${Math.max(0.001, pchispa).toFixed(4)}) rotate(${(Math.sin(t * 3) * 6).toFixed(2)}deg)` }}>
              <EmojiAnimado id="sparkles" lado={tam * 0.9} />
            </div>
          )}
          {rosa && (
            <div style={{ position: 'absolute', left: -tam * 0.55, top: -tam * 0.12, width: tam * 0.52, height: tam * 0.36, borderRadius: tam * 0.18, background: '#B9B9BE',
                          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: tam * 0.05, opacity: clamp((t - 0.7) / 0.15) }}>
              {[0, 1, 2].map(k => (
                <div key={k} style={{ width: tam * 0.07, height: tam * 0.07, borderRadius: '50%', background: '#2B2B2E', opacity: 0.45 + 0.55 * (0.5 + 0.5 * Math.sin(t * 7 - k * 0.9)) }} />
              ))}
            </div>
          )}
        </div>
        {abajo && (
          <div style={{ fontFamily: FAMILIA.inter, fontWeight: 400, fontSize: 58 * U, letterSpacing: '-0.02em', color: tinta, textShadow: sombraTexto, marginTop: 14 * U,
                        opacity: easeOut((t - 0.72) / 0.35), transform: `translateY(${((1 - easeOut((t - 0.72) / 0.35)) * 16 * U).toFixed(2)}px)` }}>{abajo}</div>
        )}
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ CalendarioK */
const ESTILO_CAL: Record<string, { cuerpo: string; cabeza: string; numero: string; etiqueta: string; anillas: string }> = {
  rojo: { cuerpo: '#FFFFFF', cabeza: '#E3262E', numero: '#111114', etiqueta: '#FFFFFF', anillas: '#3A3A40' },
  oscuro: { cuerpo: '#17171C', cabeza: '#7C5CFF', numero: '#FFFFFF', etiqueta: '#FFFFFF', anillas: '#C9C9D2' },
  papel: { cuerpo: '#F4EFE6', cabeza: '#1D1D21', numero: '#1D1D21', etiqueta: '#F4EFE6', anillas: '#8A8378' },
};
export type CalendarioProps = Base & { desde?: number; hasta?: number; etiqueta?: string; final?: string };
export const CalendarioK: React.FC<CalendarioProps> = ({ desde = 10, hasta = 1, etiqueta = 'DÍA', final = 'check', x = 50, y = 40, escala = 1, salida = 0.35,
                                                         variante = 'rojo', acento }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { t, fin, q } = useVida(salida);
  const E = { ...(ESTILO_CAL[variante] || ESTILO_CAL.rojo) };
  if (variante === 'oscuro' && esHex(acento)) E.cabeza = hex(acento, E.cabeza);
  const a = Math.round(Number(desde) || 1), b = Math.round(Number(hasta) || 1);
  const pasos = Math.abs(b - a);
  const cuantos = Math.min(pasos, 9);                                       // como mucho 9 hojas: un reto de 30 días salta de 4 en 4
  const valores = Array.from({ length: cuantos + 1 }, (_, i) => Math.round(a + ((b - a) * i) / Math.max(1, cuantos)));
  const t0 = 0.4, dt = clamp((fin - salida - 1.0 - t0) / Math.max(1, cuantos), 0.13, 0.3), vuelo = 0.3;
  const lado = 340 * U, cx = (W * x) / 100, cy = (H * y) / 100;
  const pe = S(0.02, { damping: 13, stiffness: 180 });
  const dos = (n: number) => String(Math.abs(n)).padStart(2, '0');
  const Hoja: React.FC<{ n: number; style?: React.CSSProperties }> = ({ n, style }) => (
    <div style={{ position: 'absolute', inset: 0, borderRadius: 50 * U, background: E.cuerpo, overflow: 'hidden', ...style }}>
      <div style={{ height: lado * 0.3, background: E.cabeza, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: FAMILIA.redonda,
                    fontWeight: 800, fontSize: 66 * U, letterSpacing: '0.06em', color: E.etiqueta }}>{etiqueta}</div>
      <div style={{ height: lado * 0.7, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: FAMILIA.redonda, fontWeight: 800,
                    fontSize: 190 * U, lineHeight: 1, letterSpacing: '-0.03em', color: E.numero }}>{dos(n)}</div>
    </div>
  );
  // la hoja que se está arrancando (vuela girando desde la esquina) y la que queda debajo
  const k = clamp(Math.floor((t - t0) / dt), -1, cuantos);
  const actual = valores[Math.max(0, Math.min(cuantos, k + 1))];
  const arrancada = k >= 0 && k < cuantos ? valores[k] : null;
  const pv = arrancada !== null ? clamp((t - (t0 + k * dt)) / vuelo) : 1;
  const tFinal = t0 + cuantos * dt;
  const pcheck = final === 'check' ? S(tFinal + 0.15, { damping: 11, stiffness: 200 }) : 0;
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <div style={{ position: 'absolute', left: cx - lado / 2, top: cy - lado / 2, width: lado, height: lado, opacity: clamp(pe * 2),
                    transform: `scale(${Math.max(0.001, 0.55 + 0.45 * pe).toFixed(4)})`, filter: `drop-shadow(0 ${16 * U}px ${22 * U}px rgba(0,0,0,.38))` }}>
        <Hoja n={t < t0 ? valores[0] : actual} />
        {arrancada !== null && pv < 1 && (
          <Hoja n={arrancada} style={{ transformOrigin: '0% 0%', opacity: 1 - pv * pv,
                                       transform: `translate(${(pv * 240 * U).toFixed(2)}px, ${(-pv * 40 * U + pv * pv * 260 * U).toFixed(2)}px) rotate(${(pv * 52).toFixed(2)}deg)` }} />
        )}
        {[0.22, 0.4, 0.6, 0.78].map((f, i) => (
          <div key={i} style={{ position: 'absolute', left: lado * f - 7 * U, top: -20 * U, width: 14 * U, height: 46 * U, borderRadius: 7 * U, background: E.anillas }} />
        ))}
        {pcheck > 0.01 && (
          <div style={{ position: 'absolute', right: -44 * U, top: -44 * U, width: 120 * U, height: 120 * U, borderRadius: '50%', background: '#2BD46A',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', transform: `scale(${Math.max(0.001, pcheck).toFixed(4)})`,
                        boxShadow: `0 ${8 * U}px ${18 * U}px rgba(0,0,0,.3)` }}>
            <svg width={70 * U} height={70 * U} viewBox="0 0 24 24"><path d="M4 12.5 L9.5 18 L20 6.5" fill="none" stroke="#FFFFFF" strokeWidth="3.4" strokeLinecap="round"
              strokeLinejoin="round" strokeDasharray="30" strokeDashoffset={(30 * (1 - easeOut((t - tFinal - 0.2) / 0.3))).toFixed(2)} /></svg>
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ RedNeonK */
const RED: Record<string, { color: string; glow: string }> = {
  facebook: { color: '#1877F2', glow: '#3B8BFF' }, instagram: { color: '#DD2A7B', glow: '#FF4FA0' }, youtube: { color: '#FF0000', glow: '#FF3B3B' },
  tiktok: { color: '#111111', glow: '#E8E8E8' },
};
const Logo: React.FC<{ red: string; lado: number }> = ({ red, lado }) => (
  <svg width={lado} height={lado} viewBox="0 0 24 24">
    {red === 'instagram' ? (
      <>
        <defs><linearGradient id="kigrad" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stopColor="#F58529" /><stop offset=".5" stopColor="#DD2A7B" /><stop offset="1" stopColor="#515BD4" /></linearGradient></defs>
        <circle cx="12" cy="12" r="12" fill="url(#kigrad)" />
        <rect x="6" y="6" width="12" height="12" rx="3.6" fill="none" stroke="#FFF" strokeWidth="1.6" /><circle cx="12" cy="12" r="2.9" fill="none" stroke="#FFF" strokeWidth="1.6" />
        <circle cx="15.6" cy="8.4" r=".9" fill="#FFF" />
      </>
    ) : red === 'youtube' ? (
      <>
        <circle cx="12" cy="12" r="12" fill="#FF0000" /><rect x="5.2" y="7.6" width="13.6" height="8.8" rx="2.6" fill="#FFF" /><path d="M10.4 9.7 L14.4 12 L10.4 14.3 Z" fill="#FF0000" />
      </>
    ) : red === 'tiktok' ? (
      <>
        <circle cx="12" cy="12" r="12" fill="#111" />
        {[['#25F4EE', -0.5], ['#FE2C55', 0.5], ['#FFFFFF', 0]].map(([c, d], i) => (
          <path key={i} transform={`translate(${d} ${d})`} fill={String(c)}
                d="M15.6 6.4c-.6-.6-.9-1.4-.9-2.2h-2.1v8.6c0 1-.8 1.7-1.7 1.7s-1.7-.8-1.7-1.7.8-1.7 1.7-1.7c.2 0 .4 0 .5.1V9.1h-.5c-2.1 0-3.9 1.7-3.9 3.9s1.7 3.9 3.9 3.9 3.9-1.7 3.9-3.9V8.6c.8.6 1.8.9 2.9.9V7.4c-.8 0-1.5-.3-2.1-1z" />
        ))}
      </>
    ) : (
      <>
        <circle cx="12" cy="12" r="12" fill="#1877F2" />
        <path d="M13.3 19.5v-6.1h2l.3-2.4h-2.3V9.5c0-.7.2-1.2 1.2-1.2h1.3V6.2c-.2 0-1-.1-1.9-.1-1.9 0-3.1 1.1-3.1 3.2v1.7H8.7v2.4h2.1v6.1z" fill="#FFF" />
      </>
    )}
  </svg>
);
export type RedNeonProps = Base & { centro?: string; izq?: string; der?: string; redes?: string };
export const RedNeonK: React.FC<RedNeonProps> = ({ centro = 'TÚ', izq = 'CONSUMIENDO', der = 'CREANDO', redes = 'facebook,instagram,youtube,tiktok', x = 50, y = 40, escala = 1,
                                                  salida = 0.35, variante = 'interruptor' }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { t, fin, q } = useVida(salida);
  const cx = (W * x) / 100, cy = (H * y) / 100;
  const lista = String(redes || '').split(/[|,]/).map(s => s.trim().toLowerCase()).filter(r => r in RED).slice(0, 4);
  const nodos = lista.length ? lista : ['facebook', 'instagram', 'youtube', 'tiktok'];
  const sitios = nodos.length === 4 ? [[-360, -40], [-145, -210], [145, -210], [360, -40]] : nodos.length === 3 ? [[-330, -60], [0, -230], [330, -60]] : [[-240, -160], [240, -160]];
  const centroY = cy + 170 * U, rC = 88 * U, rN = 70 * U;
  const tCambio = Math.max(1.4, (fin - salida) * 0.55);                // da tiempo a leer el primer estado
  const pk = suave((t - tCambio) / 0.35);                                   // 0 = consumiendo (rojo), 1 = creando (verde)
  const colorPill = pk < 0.5 ? mezcla('#FF2D3D', [255, 196, 0], pk * 2) : mezcla('#FFC400', [61, 255, 110], (pk - 0.5) * 2);
  const conDinero = variante !== 'simple';                               // «simple»: sin los $ que salen de las redes
  const pe = (i: number) => S(0.05 + i * 0.09, { damping: 12, stiffness: 170 });
  const pill = S(0.3, { damping: 14 });
  const etiqueta = pk < 0.5 ? izq : der;
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <svg width={W} height={H} style={{ position: 'absolute', left: 0, top: 0, overflow: 'visible' }}>
        {sitios.map(([dx, dy], i) => {
          const x1 = cx + dx * U, y1 = cy + dy * U, x2 = cx, y2 = centroY;
          const largo = Math.hypot(x2 - x1, y2 - y1);
          const dibujo = easeOut((t - 0.25 - i * 0.06) / 0.5);
          // los puntos de luz viajan hacia «TÚ» (consumir) y, tras el cambio, salen de «TÚ» hacia las redes (crear)
          const ida = pk < 0.5;
          const f = ((t * 0.9 + i * 0.27) % 1);
          const pos = ida ? f : 1 - f;
          const px = x1 + (x2 - x1) * pos, py = y1 + (y2 - y1) * pos;
          return (
            <g key={i}>
              <line x1={x1} y1={y1} x2={x1 + (x2 - x1) * dibujo} y2={y1 + (y2 - y1) * dibujo} stroke="rgba(255,255,255,.85)" strokeWidth={3 * U}
                    strokeDasharray={`${10 * U} ${12 * U}`} strokeDashoffset={(-t * 40 * U * (ida ? 1 : -1)).toFixed(1)} />
              {dibujo > 0.98 && largo > 0 && (
                <circle cx={px} cy={py} r={9 * U} fill="#FFFFFF" style={{ filter: `drop-shadow(0 0 ${8 * U}px #FFF) drop-shadow(0 0 ${16 * U}px ${ida ? '#FF5A5A' : '#5CFF8F'})` }} />
              )}
            </g>
          );
        })}
      </svg>
      {sitios.map(([dx, dy], i) => {
        const p = pe(i), info = RED[nodos[i]];
        const dinero = conDinero && pk > 0.6 ? clamp((t - tCambio - 0.3 - i * 0.12) / 0.8) : 0;
        return (
          <div key={i} style={{ position: 'absolute', left: cx + dx * U - rN, top: cy + dy * U - rN, width: rN * 2, height: rN * 2 }}>
            <div style={{ width: rN * 2, height: rN * 2, borderRadius: '50%', transform: `scale(${Math.max(0.001, p).toFixed(4)})`,
                          filter: `drop-shadow(0 0 ${12 * U}px ${info.glow}) drop-shadow(0 0 ${30 * U}px ${info.glow})` }}>
              <Logo red={nodos[i]} lado={rN * 2} />
            </div>
            {dinero > 0 && dinero < 1 && (
              <div style={{ position: 'absolute', left: rN * 0.6 + (i % 2 ? 30 : -30) * U, top: -dinero * 120 * U, fontFamily: FAMILIA.redonda, fontWeight: 800,
                            fontSize: 64 * U, color: '#4DFF7A', opacity: Math.sin(dinero * Math.PI), textShadow: `0 0 ${12 * U}px #2BFF6A, 0 0 ${26 * U}px #2BFF6A` }}>$</div>
            )}
          </div>
        );
      })}
      <div style={{ position: 'absolute', left: cx - rC, top: centroY - rC, width: rC * 2, height: rC * 2, borderRadius: '50%', background: '#FFFFFF',
                    boxShadow: `0 0 ${16 * U}px rgba(255,255,255,.9), 0 0 ${40 * U}px ${pk > 0.5 ? 'rgba(80,255,130,.7)' : 'rgba(255,255,255,.5)'}`,
                    transform: `scale(${Math.max(0.001, S(0.02, { damping: 12 })).toFixed(4)})`, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <svg width={rC * 1.05} height={rC * 0.9} viewBox="0 0 24 20"><circle cx="12" cy="6" r="4.6" fill="#111" /><path d="M2.5 20 Q3 11.5 12 11.5 Q21 11.5 21.5 20 Z" fill="#111" /></svg>
        <div style={{ fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 28 * U, color: '#111', marginTop: -4 * U }}>{centro}</div>
      </div>
      <div style={{ position: 'absolute', left: cx - 230 * U, top: centroY + rC + 64 * U, width: 460 * U, height: 96 * U, borderRadius: 48 * U, background: colorPill,
                    boxShadow: `0 0 ${18 * U}px ${colorPill}, 0 0 ${46 * U}px ${colorPill}`, opacity: clamp(pill * 2), transform: `scale(${Math.max(0.001, 0.7 + 0.3 * pill).toFixed(4)})` }}>
        <div style={{ position: 'absolute', top: 13 * U, left: 13 * U + pk * (460 - 26 - 70) * U, width: 70 * U, height: 70 * U, borderRadius: '50%', background: '#FFFFFF',
                      boxShadow: `0 ${3 * U}px ${8 * U}px rgba(0,0,0,.3)` }} />
        {etiqueta && (
          <div style={{ position: 'absolute', top: 0, height: 96 * U, display: 'flex', alignItems: 'center', fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 38 * U,
                        letterSpacing: '0.04em', color: '#FFFFFF', textShadow: `0 ${1 * U}px ${4 * U}px rgba(0,0,0,.35)`,
                        left: pk < 0.5 ? 100 * U : 30 * U, right: pk < 0.5 ? 26 * U : 100 * U, justifyContent: 'center', opacity: Math.abs(pk - 0.5) * 2 }}>{etiqueta}</div>
        )}
      </div>
    </AbsoluteFill>
  );
};
