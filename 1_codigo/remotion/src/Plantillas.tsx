// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/Plantillas.tsx — la biblioteca de plantillas Remotion para eventos sociales, fotografía y bodas (van ENCIMA del video, con
// alfa): Titulo (momento: «Casa de la novia», «La ceremonia»…), Saludo («¡Hola amigos!»), Capitulos (la línea del día), Fecha (save the date),
// Pareja (Ana & Luis), Pastilla («MOMENTO DEL DÍA»), Encuesta, Comentario (caja que se escribe y se envía), Sesion (sesión fotográfica) y Ninas.
// Todas reciben `y` (centro, % del alto) y `escala`: el programa las coloca sin tapar caras. Stickers: Fluent Emoji 3D (MIT) e iconos 3dicons (CC0).
import { AbsoluteFill, Img, interpolate, random, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { FAMILIA, clamp, rgb, useFuentes, useResorte, useU } from './comun';

export type Estilo = 'dorado' | 'rosa' | 'blanco' | 'noche' | 'editorial' | 'esmeralda' | 'lila';
const ESTILOS: Record<Estilo, { acento: string; texto: string; sombra: string; tarjeta: string }> = {
  dorado: { acento: '#E9C67D', texto: '#FFF8EA', sombra: 'rgba(40,22,0,.55)', tarjeta: 'rgba(24,18,10,.42)' },
  rosa: { acento: '#F6A9C8', texto: '#FFFFFF', sombra: 'rgba(60,10,30,.5)', tarjeta: 'rgba(40,12,26,.40)' },
  blanco: { acento: '#FFFFFF', texto: '#FFFFFF', sombra: 'rgba(0,0,0,.55)', tarjeta: 'rgba(0,0,0,.30)' },
  noche: { acento: '#8EC5FF', texto: '#F2F7FF', sombra: 'rgba(0,10,40,.6)', tarjeta: 'rgba(6,14,36,.45)' },
  editorial: { acento: '#111111', texto: '#111111', sombra: 'rgba(0,0,0,.18)', tarjeta: 'rgba(255,255,255,.92)' },
  esmeralda: { acento: '#7EE6C0', texto: '#F2FFF9', sombra: 'rgba(0,30,20,.55)', tarjeta: 'rgba(6,26,20,.40)' },
  lila: { acento: '#C9B2FF', texto: '#FBF8FF', sombra: 'rgba(25,10,60,.55)', tarjeta: 'rgba(20,10,40,.42)' },
};
type Base = { estilo?: Estilo; y?: number; escala?: number; sticker?: string; salida?: number };
const est = (e?: string) => ESTILOS[(e as Estilo)] || ESTILOS.dorado;

/** Las URL de un sticker: 'emoji:waving_hand' (Fluent 3D) o '3d:fire-front-color' (3dicons). */
const urlSticker = (s?: string) => {
  if (!s) return '';
  const [tipo, n] = s.includes(':') ? s.split(':') : ['emoji', s];
  return tipo === '3d' ? staticFile(`iconos3d/${n}.png`) : staticFile(`stickers/rcs_emoji_${n}.png`);
};

/** Salida común: los últimos `salida` segundos se desvanece subiendo un poco. */
const useSalida = (salida = 0.35) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps, fin = durationInFrames / fps;
  return { t, q: clamp((t - (fin - salida)) / salida), fin };
};

/** Bokeh / pétalos / destellos que flotan (deterministas por semilla). */
export const Particulas: React.FC<{ n?: number; color: string; tipo?: 'bokeh' | 'petalos' | 'destellos'; semilla?: string }> = ({ n = 18, color, tipo = 'bokeh', semilla = 'p' }) => {
  const frame = useCurrentFrame();
  const { fps, width: W, height: H } = useVideoConfig();
  const U = Math.min(W, H) / 1080, t = frame / fps;
  const [r, g, b] = rgb(color);
  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      {Array.from({ length: n }).map((_, i) => {
        const x = random(`${semilla}x${i}`) * W, y0 = random(`${semilla}y${i}`) * H, v = 18 + random(`${semilla}v${i}`) * 40;
        const tam = (tipo === 'destellos' ? 10 : 14) * U + random(`${semilla}s${i}`) * 34 * U;
        const y = ((y0 - t * v * U) % H + H) % H, osc = Math.sin(t * 1.3 + i) * 18 * U;
        const brillo = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(t * 2.4 + i * 1.7));
        if (tipo === 'petalos')
          return <div key={i} style={{ position: 'absolute', left: x + osc, top: y, width: tam, height: tam * 0.62, borderRadius: '60% 0 60% 0',
                                        background: `rgba(${r},${g},${b},${0.55 * brillo})`, transform: `rotate(${(t * 40 + i * 37) % 360}deg)` }} />;
        if (tipo === 'destellos')
          return <svg key={i} width={tam} height={tam} viewBox="0 0 10 10" style={{ position: 'absolute', left: x + osc, top: y, opacity: brillo }}>
                   <path d="M5 0 L6 4 L10 5 L6 6 L5 10 L4 6 L0 5 L4 4 Z" fill={`rgb(${r},${g},${b})`} /></svg>;
        return <div key={i} style={{ position: 'absolute', left: x + osc, top: y, width: tam, height: tam, borderRadius: '50%',
                                     background: `radial-gradient(circle, rgba(${r},${g},${b},${0.5 * brillo}) 0%, rgba(${r},${g},${b},0) 70%)` }} />;
      })}
    </AbsoluteFill>
  );
};

/** Un sticker 3D que entra con resorte, flota y se balancea. */
const Sticker: React.FC<{ src: string; tam: number; t0: number; x: number; y: number; saluda?: boolean }> = ({ src, tam, t0, x, y, saluda }) => {
  const S = useResorte();
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps, p = S(t0, { damping: 9, stiffness: 170 });
  if (!src || t < t0 - 0.05) return null;
  const giro = saluda ? Math.sin((t - t0) * 9) * 16 : Math.sin((t - t0) * 1.6) * 6;
  return <Img src={src} style={{ position: 'absolute', left: x - tam / 2, top: y - tam / 2 + Math.sin((t - t0) * 2) * tam * 0.04, width: tam, height: tam,
                                 transform: `scale(${Math.max(0.001, p).toFixed(3)}) rotate(${giro.toFixed(1)}deg)`, transformOrigin: saluda ? '70% 85%' : '50% 50%',
                                 filter: `drop-shadow(0 ${tam * 0.06}px ${tam * 0.09}px rgba(0,0,0,.4))` }} />;
};

/** Un halo oscuro y suave detrás de un texto (elipse difuminada): legibilidad sobre planos claros sin caja. */
const Halo: React.FC<{ x: number; y: number; w: number; h: number; fuerza?: number; p?: number }> = ({ x, y, w, h, fuerza = 0.42, p = 1 }) => (
  <div style={{ position: 'absolute', left: x - w / 2, top: y - h / 2, width: w, height: h, borderRadius: '50%', opacity: clamp(p),
                background: `radial-gradient(closest-side, rgba(0,0,0,${fuerza}), rgba(0,0,0,${fuerza * 0.45}) 55%, rgba(0,0,0,0))` }} />
);

/** Texto que «se escribe» de izquierda a derecha (máscara) con un leve desenfoque que se aclara. */
const Escrito: React.FC<{ texto: string; t0: number; dur?: number; style: React.CSSProperties }> = ({ texto, t0, dur = 0.9, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = clamp((frame / fps - t0) / dur);
  const e = 1 - Math.pow(1 - p, 3);
  return <div style={{ ...style, clipPath: `inset(-20% ${((1 - e) * 100).toFixed(2)}% -30% -5%)`, filter: `blur(${((1 - e) * 6).toFixed(2)}px)` }}>{texto}</div>;
};

/* ------------------------------------------------------------------------------------------------ Titulo de momento */
export type TituloProps = Base & { kicker?: string; titulo: string; subtitulo?: string; letra?: 'script' | 'serif' | 'sans'; adorno?: 'lineas' | 'destellos' | 'petalos' | 'bokeh' | 'ninguno'; tarjeta?: boolean };
export const Titulo: React.FC<TituloProps> = ({ kicker = '', titulo, subtitulo = '', estilo = 'dorado', letra = 'script', adorno = 'lineas', tarjeta = false, sticker = '', y = 30, escala = 1, salida = 0.4 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { t, q } = useSalida(salida);
  const E = est(estilo);
  const fam = letra === 'sans' ? FAMILIA.grotesk : FAMILIA.serif;
  const tam = Math.min(150 * U, (W * 0.86) / Math.max(4, titulo.length) * (letra === 'sans' ? 1.75 : 2.05));
  const linea = S(0.15, { damping: 18 }), k = S(0.05, { damping: 16 }), sub = S(0.75, { damping: 16 });
  const cy = H * y / 100;
  return (
    <AbsoluteFill style={{ opacity: 1 - q, transform: `translateY(${(-q * 30 * U).toFixed(1)}px)` }}>
      {!tarjeta && estilo !== 'editorial' && <Halo x={W / 2} y={cy} w={Math.min(W * 1.05, tam * titulo.length * 0.62 + 320 * U)} h={tam * 2.6 + (subtitulo ? 90 * U : 0)} p={k * 1.5} />}
      {adorno !== 'lineas' && adorno !== 'ninguno' && <Particulas color={E.acento} tipo={adorno === 'petalos' ? 'petalos' : adorno === 'destellos' ? 'destellos' : 'bokeh'} n={adorno === 'bokeh' ? 14 : 22} semilla={titulo} />}
      <div style={{ position: 'absolute', left: W / 2, top: cy, transform: 'translate(-50%,-50%)', display: 'flex', flexDirection: 'column', alignItems: 'center',
                    gap: 14 * U, padding: tarjeta ? `${34 * U}px ${56 * U}px` : 0, borderRadius: 28 * U, background: tarjeta ? E.tarjeta : 'transparent',
                    backdropFilter: tarjeta ? 'blur(10px)' : undefined, border: tarjeta ? `${1.5 * U}px solid ${E.acento}55` : 'none' }}>
        {kicker && <div style={{ fontFamily: FAMILIA.mono, fontSize: 28 * U, letterSpacing: `${(0.5 - 0.2 * clamp(k)) .toFixed(3)}em`, color: E.acento,
                                 opacity: clamp(k), textTransform: 'uppercase', textShadow: `0 2px 12px ${E.sombra}` }}>{kicker}</div>}
        {adorno === 'lineas' && <div style={{ width: 260 * U * clamp(linea), height: 2 * U, background: `linear-gradient(90deg, transparent, ${E.acento}, transparent)` }} />}
        <Escrito texto={titulo} t0={0.25} dur={letra === 'script' ? 1.0 : 0.6}
                 style={{ fontFamily: fam, fontStyle: letra === 'sans' ? 'normal' : 'italic', fontWeight: letra === 'sans' ? 700 : 400, fontSize: tam, lineHeight: 1.05,
                          color: E.texto, whiteSpace: 'nowrap', textShadow: `0 ${3 * U}px ${8 * U}px rgba(0,0,0,.45), 0 ${6 * U}px ${26 * U}px ${E.sombra}, 0 0 ${30 * U}px ${E.acento}55` }} />
        {subtitulo && <div style={{ fontFamily: FAMILIA.grotesk, fontWeight: 500, fontSize: 40 * U, letterSpacing: '0.08em', color: E.texto, opacity: clamp(sub),
                                    transform: `translateY(${((1 - clamp(sub)) * 16 * U).toFixed(1)}px)`, textShadow: `0 2px 14px ${E.sombra}` }}>{subtitulo}</div>}
        {adorno === 'lineas' && <div style={{ width: 160 * U * clamp(linea), height: 2 * U, background: `linear-gradient(90deg, transparent, ${E.acento}, transparent)` }} />}
      </div>
      {sticker && <Sticker src={urlSticker(sticker)} tam={150 * U} t0={0.9} x={W / 2 + Math.min(W * 0.36, tam * titulo.length * 0.26)} y={cy - tam * 0.75} />}
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ Saludo */
export type SaludoProps = Base & { linea1?: string; linea2?: string };
export const Saludo: React.FC<SaludoProps> = ({ linea1 = '¡Hola', linea2 = 'amigos!', estilo = 'rosa', sticker = 'emoji:waving_hand', y = 24, escala = 1, salida = 0.4 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { q } = useSalida(salida);
  const E = est(estilo);
  const p2 = S(0.75, { damping: 11, stiffness: 150 });
  const cy = H * y / 100;
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <Halo x={W / 2} y={cy} w={W * 0.95} h={360 * U} />
      <Particulas color={E.acento} tipo="destellos" n={14} semilla={linea1 + linea2} />
      <div style={{ position: 'absolute', left: W / 2, top: cy, transform: 'translate(-50%,-50%)', textAlign: 'center' }}>
        <Escrito texto={linea1} t0={0.1} dur={0.7} style={{ fontFamily: FAMILIA.serif, fontStyle: 'italic', fontSize: 150 * U, color: E.texto, lineHeight: 1,
                                                           textShadow: `0 ${6 * U}px ${24 * U}px ${E.sombra}` }} />
        <div style={{ fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 132 * U, color: E.acento, lineHeight: 1, letterSpacing: '0.01em',
                      transform: `scale(${Math.max(0.001, p2).toFixed(3)})`, textShadow: `0 ${6 * U}px ${24 * U}px ${E.sombra}` }}>{linea2}</div>
      </div>
      <Sticker src={urlSticker(sticker)} tam={190 * U} t0={0.45} x={W / 2 + 330 * U} y={cy - 120 * U} saluda />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ Capítulos del día */
export type CapitulosProps = Base & { capitulos?: string; actual?: number };
export const Capitulos: React.FC<CapitulosProps> = ({ capitulos = 'Maquillaje,Ceremonia,Fiesta,El show', actual = 0, estilo = 'blanco', y = 12, escala = 1, salida = 0.35 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { t, q } = useSalida(salida);
  const E = est(estilo);
  const lista = capitulos.split(',').map(x => x.trim()).filter(Boolean).slice(0, 6);
  const entra = S(0.05, { damping: 16 });
  const ancho = Math.min(W * 0.9, 220 * U * lista.length), paso = ancho / Math.max(1, lista.length - 1 || 1);
  const avance = clamp(interpolate(t, [0.4, 1.4], [Math.max(0, actual - 1), actual], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) / Math.max(1, lista.length - 1));
  return (
    <AbsoluteFill style={{ opacity: (1 - q) * clamp(entra * 1.5) }}>
      <div style={{ position: 'absolute', left: (W - ancho) / 2, top: H * y / 100, width: ancho, transform: `translateY(${((1 - clamp(entra)) * -30 * U).toFixed(1)}px)` }}>
        <div style={{ position: 'absolute', top: 18 * U, left: 0, width: ancho, height: 3 * U, background: 'rgba(255,255,255,.25)', borderRadius: 3 * U }} />
        <div style={{ position: 'absolute', top: 18 * U, left: 0, width: ancho * avance, height: 3 * U, background: E.acento, borderRadius: 3 * U, boxShadow: `0 0 ${12 * U}px ${E.acento}` }} />
        {lista.map((c, i) => {
          const on = i <= actual, x = lista.length > 1 ? i * paso : ancho / 2;
          return (
            <div key={i} style={{ position: 'absolute', left: x, top: 0, transform: 'translateX(-50%)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 * U }}>
              <div style={{ width: 38 * U, height: 38 * U, borderRadius: '50%', background: on ? E.acento : 'rgba(0,0,0,.35)', border: `${3 * U}px solid ${on ? E.acento : 'rgba(255,255,255,.6)'}`,
                            boxShadow: i === actual ? `0 0 ${24 * U}px ${E.acento}` : 'none', transform: i === actual ? `scale(${(1 + 0.12 * Math.sin(t * 5)).toFixed(3)})` : 'none' }} />
              <div style={{ fontFamily: FAMILIA.mono, fontSize: 24 * U, letterSpacing: '0.14em', color: on ? '#fff' : 'rgba(255,255,255,.65)', textTransform: 'uppercase',
                            whiteSpace: 'nowrap', textShadow: '0 2px 10px rgba(0,0,0,.7)', fontWeight: i === actual ? 700 : 400 }}>{c}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ Fecha (save the date) */
export type FechaProps = Base & { dia?: string; mes?: string; anio?: string; texto?: string };
export const Fecha: React.FC<FechaProps> = ({ dia = '25', mes = 'OCTUBRE', anio = '2026', texto = 'SAVE THE DATE', estilo = 'dorado', sticker = 'emoji:two_hearts', y = 30, escala = 1, salida = 0.4 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { q } = useSalida(salida);
  const E = est(estilo);
  const gira = S(0.1, { damping: 13, stiffness: 120 }), num = S(0.5, { damping: 10 });
  const cw = 380 * U, cy = H * y / 100;
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <div style={{ position: 'absolute', left: W / 2, top: cy, transform: `translate(-50%,-50%) perspective(${1400 * U}px) rotateX(${((1 - clamp(gira, 0, 1.2)) * 80).toFixed(2)}deg)`,
                    width: cw, borderRadius: 30 * U, overflow: 'hidden', background: 'rgba(255,255,255,.95)', boxShadow: `0 ${30 * U}px ${70 * U}px rgba(0,0,0,.4), 0 0 ${50 * U}px ${E.acento}55` }}>
        <div style={{ background: E.acento === '#FFFFFF' ? '#111' : E.acento, color: '#fff', fontFamily: FAMILIA.mono, fontSize: 30 * U, letterSpacing: '0.24em', textAlign: 'center', padding: `${16 * U}px 0` }}>{mes}</div>
        <div style={{ fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 210 * U, color: '#151515', textAlign: 'center', lineHeight: 1.05,
                      transform: `scale(${Math.max(0.001, num).toFixed(3)})` }}>{dia}</div>
        <div style={{ fontFamily: FAMILIA.grotesk, fontSize: 34 * U, color: '#444', textAlign: 'center', paddingBottom: 18 * U, letterSpacing: '0.2em' }}>{anio}</div>
      </div>
      <div style={{ position: 'absolute', left: W / 2, top: cy + 330 * U, transform: 'translateX(-50%)', fontFamily: FAMILIA.serif, fontStyle: 'italic', fontSize: 70 * U,
                    color: E.texto === '#111111' ? '#fff' : E.texto, whiteSpace: 'nowrap', textShadow: `0 4px 18px ${E.sombra}`, opacity: clamp(S(0.8)) }}>{texto}</div>
      <Sticker src={urlSticker(sticker)} tam={130 * U} t0={0.9} x={W / 2 + cw * 0.5} y={cy - 250 * U} />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ Pareja */
export type ParejaProps = Base & { nombre1?: string; nombre2?: string; texto?: string };
export const Pareja: React.FC<ParejaProps> = ({ nombre1 = 'Ana', nombre2 = 'Luis', texto = '', estilo = 'dorado', sticker = 'emoji:gem_stone', y = 28, escala = 1, salida = 0.45 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { q } = useSalida(salida);
  const E = est(estilo);
  const amp = S(0.55, { damping: 8, stiffness: 140 });
  const cy = H * y / 100;
  const fs = Math.min(140 * U, (W * 0.42) / Math.max(3, Math.max(nombre1.length, nombre2.length)) * 2.1);
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <Halo x={W / 2} y={cy} w={W * 0.98} h={fs * 2.6} />
      <Particulas color={E.acento} tipo="petalos" n={16} semilla={nombre1 + nombre2} />
      <div style={{ position: 'absolute', left: W / 2, top: cy, transform: 'translate(-50%,-50%)', display: 'flex', alignItems: 'center', gap: 24 * U }}>
        <Escrito texto={nombre1} t0={0.1} style={{ fontFamily: FAMILIA.serif, fontStyle: 'italic', fontSize: fs, color: E.texto, textShadow: `0 6px 24px ${E.sombra}`, whiteSpace: 'nowrap' }} />
        <div style={{ fontFamily: FAMILIA.serif, fontSize: fs * 1.25, color: E.acento, transform: `scale(${Math.max(0.001, amp).toFixed(3)})`, textShadow: `0 0 ${30 * U}px ${E.acento}` }}>&amp;</div>
        <Escrito texto={nombre2} t0={0.7} style={{ fontFamily: FAMILIA.serif, fontStyle: 'italic', fontSize: fs, color: E.texto, textShadow: `0 6px 24px ${E.sombra}`, whiteSpace: 'nowrap' }} />
      </div>
      {texto && <div style={{ position: 'absolute', left: W / 2, top: cy + fs * 0.95, transform: 'translateX(-50%)', fontFamily: FAMILIA.mono, fontSize: 26 * U, letterSpacing: '0.3em',
                              color: E.acento, opacity: clamp(S(1.2)), whiteSpace: 'nowrap' }}>{texto.toUpperCase()}</div>}
      <Sticker src={urlSticker(sticker)} tam={110 * U} t0={1.1} x={W / 2} y={cy - fs * 1.05} />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ Pastilla («MOMENTO DEL DÍA») */
export type PastillaProps = Base & { texto?: string };
export const Pastilla: React.FC<PastillaProps> = ({ texto = 'MOMENTO DEL DÍA', estilo = 'dorado', sticker = 'emoji:sparkles', y = 18, escala = 1, salida = 0.3 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { t, q } = useSalida(salida);
  const E = est(estilo);
  const p = S(0.05, { damping: 12, stiffness: 180 });
  const brillo = 0.5 + 0.5 * Math.sin(t * 4);
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <div style={{ position: 'absolute', left: W / 2, top: H * y / 100, transform: `translate(-50%,-50%) scale(${Math.max(0.001, p).toFixed(3)})`, display: 'flex', alignItems: 'center',
                    gap: 14 * U, padding: `${14 * U}px ${30 * U}px ${14 * U}px ${18 * U}px`, borderRadius: 999, background: E.tarjeta, border: `${2 * U}px solid ${E.acento}`,
                    boxShadow: `0 0 ${(20 + 20 * brillo) * U}px ${E.acento}88, 0 ${10 * U}px ${30 * U}px rgba(0,0,0,.35)` }}>
        {sticker && <Img src={urlSticker(sticker)} style={{ width: 54 * U, height: 54 * U, transform: `rotate(${(Math.sin(t * 3) * 10).toFixed(1)}deg)` }} />}
        <div style={{ fontFamily: FAMILIA.grotesk, fontWeight: 700, fontSize: 34 * U, letterSpacing: '0.16em', color: E.texto === '#111111' ? '#111' : '#fff', whiteSpace: 'nowrap' }}>{texto}</div>
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ Encuesta */
export type EncuestaProps = Base & { pregunta?: string; op1?: string; op2?: string; pct1?: number };
export const Encuesta: React.FC<EncuestaProps> = ({ pregunta = '¿Qué prefieres?', op1 = 'Sí, todos', op2 = 'Tranquila', pct1 = 68, estilo = 'blanco', y = 70, escala = 1, salida = 0.35 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { t, q } = useSalida(salida);
  const E = est(estilo);
  const p = S(0.05, { damping: 15 }), barra = clamp(interpolate(t, [0.9, 1.8], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }));
  const ancho = Math.min(W * 0.86, 820 * U);
  const opc = (txt: string, pct: number, i: number) => (
    <div key={i} style={{ position: 'relative', height: 92 * U, borderRadius: 20 * U, overflow: 'hidden', background: 'rgba(255,255,255,.12)', border: `${2 * U}px solid rgba(255,255,255,.35)`,
                          opacity: clamp(S(0.35 + i * 0.15) * 2) }}>
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${(pct * barra).toFixed(1)}%`, background: i === 0 ? `${E.acento === '#FFFFFF' ? '#ffffff' : E.acento}55` : 'rgba(255,255,255,.18)' }} />
      <div style={{ position: 'absolute', left: 28 * U, top: 0, bottom: 0, display: 'flex', alignItems: 'center', fontFamily: FAMILIA.grotesk, fontWeight: 600, fontSize: 38 * U, color: '#fff' }}>{txt}</div>
      <div style={{ position: 'absolute', right: 28 * U, top: 0, bottom: 0, display: 'flex', alignItems: 'center', fontFamily: FAMILIA.mono, fontSize: 34 * U, color: '#fff', opacity: barra }}>{Math.round(pct * barra)}%</div>
    </div>
  );
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <div style={{ position: 'absolute', left: W / 2, top: H * y / 100, width: ancho, transform: `translate(-50%,-50%) translateY(${((1 - clamp(p)) * 60 * U).toFixed(1)}px)`, padding: 30 * U,
                    borderRadius: 30 * U, background: 'rgba(12,12,16,.55)', backdropFilter: 'blur(12px)', border: `${1.5 * U}px solid rgba(255,255,255,.25)`, display: 'flex', flexDirection: 'column', gap: 18 * U }}>
        <div style={{ fontFamily: FAMILIA.grotesk, fontWeight: 700, fontSize: 44 * U, color: '#fff' }}>{pregunta}</div>
        {opc(op1, pct1, 0)}
        {opc(op2, 100 - pct1, 1)}
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ Comentario (CTA) */
export type ComentarioProps = Base & { palabra?: string; texto?: string; hecho?: string };
export const Comentario: React.FC<ComentarioProps> = ({ palabra = 'BODA', texto = 'Comenta', hecho = 'Te mando la info', estilo = 'blanco', y = 72, escala = 1, salida = 0.35 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { t, q } = useSalida(salida);
  const E = est(estilo);
  const p = S(0.05, { damping: 15 });
  const n = Math.floor(clamp((t - 0.6) / (0.11 * Math.max(1, palabra.length))) * palabra.length);
  const enviado = t > 0.75 + 0.11 * palabra.length + 0.35;
  const ancho = Math.min(W * 0.88, 840 * U);
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <div style={{ position: 'absolute', left: W / 2, top: H * y / 100, width: ancho, transform: `translate(-50%,-50%) translateY(${((1 - clamp(p)) * 70 * U).toFixed(1)}px)`, display: 'flex', flexDirection: 'column', gap: 16 * U }}>
        <div style={{ fontFamily: FAMILIA.grotesk, fontWeight: 600, fontSize: 36 * U, color: '#fff', textShadow: '0 2px 12px rgba(0,0,0,.6)' }}>
          {texto} <span style={{ color: E.acento === '#FFFFFF' ? '#FFD34D' : E.acento, fontWeight: 800 }}>«{palabra}»</span></div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 18 * U, padding: `${18 * U}px ${22 * U}px`, borderRadius: 999, background: 'rgba(255,255,255,.96)', boxShadow: `0 ${16 * U}px ${40 * U}px rgba(0,0,0,.35)` }}>
          <div style={{ width: 56 * U, height: 56 * U, borderRadius: '50%', background: `linear-gradient(135deg, #f9ce34, #ee2a7b, #6228d7)` }} />
          <div style={{ flex: 1, fontFamily: FAMILIA.grotesk, fontSize: 38 * U, color: n ? '#111' : '#999' }}>{n ? palabra.slice(0, n) : 'Añade un comentario…'}
            {n > 0 && !enviado && <span style={{ opacity: Math.floor(t * 3) % 2 ? 1 : 0 }}>|</span>}</div>
          <div style={{ fontFamily: FAMILIA.grotesk, fontWeight: 700, fontSize: 34 * U, color: '#0095f6', transform: `scale(${enviado ? 1 : 1 + 0.08 * Math.sin(t * 8)})` }}>{enviado ? '✓' : 'Publicar'}</div>
        </div>
        {enviado && <div style={{ fontFamily: FAMILIA.grotesk, fontWeight: 600, fontSize: 32 * U, color: '#7CFFB2', textShadow: '0 2px 10px rgba(0,0,0,.6)', opacity: clamp((t - (0.75 + 0.11 * palabra.length + 0.35)) * 4) }}>✓ {hecho}</div>}
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ Sesión fotográfica */
export type SesionProps = Base & { titulo?: string; kicker?: string };
export const Sesion: React.FC<SesionProps> = ({ titulo = 'Sesión fotográfica', kicker = 'BEHIND THE SCENES', estilo = 'blanco', sticker = 'emoji:camera', y = 26, escala = 1, salida = 0.4 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { t, q } = useSalida(salida);
  const E = est(estilo);
  const flash = clamp(1 - Math.abs(t - 0.18) / 0.18) * 0.85;
  const marco = S(0.25, { damping: 14 });
  const cy = H * y / 100, mw = Math.min(W * 0.8, 820 * U), mh = 300 * U;
  const esquina = (x: number, yy: number, r: number) => <div style={{ position: 'absolute', left: x, top: yy, width: 46 * U, height: 46 * U, borderLeft: `${4 * U}px solid ${E.acento}`,
                                                                       borderTop: `${4 * U}px solid ${E.acento}`, transform: `rotate(${r}deg)`, transformOrigin: '50% 50%' }} />;
  const sep = (1 - clamp(marco)) * 60 * U;
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <AbsoluteFill style={{ background: `rgba(255,255,255,${flash.toFixed(3)})` }} />
      <Halo x={W / 2} y={cy} w={mw * 1.15} h={mh * 1.5} p={marco * 1.5} />
      <div style={{ position: 'absolute', left: W / 2 - mw / 2, top: cy - mh / 2, width: mw, height: mh, opacity: clamp(marco * 2) }}>
        {esquina(-sep, -sep, 0)}{esquina(mw - 46 * U + sep, -sep, 90)}{esquina(mw - 46 * U + sep, mh - 46 * U + sep, 180)}{esquina(-sep, mh - 46 * U + sep, 270)}
        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12 * U }}>
          <div style={{ fontFamily: FAMILIA.mono, fontSize: 26 * U, letterSpacing: '0.3em', color: E.acento === '#FFFFFF' ? '#fff' : E.acento }}>{kicker}</div>
          <Escrito texto={titulo} t0={0.4} dur={0.8} style={{ fontFamily: FAMILIA.serif, fontStyle: 'italic', fontSize: Math.min(110 * U, mw / Math.max(5, titulo.length) * 1.9),
                                                              color: '#fff', whiteSpace: 'nowrap', textShadow: '0 6px 24px rgba(0,0,0,.55)' }} />
        </div>
      </div>
      <Sticker src={urlSticker(sticker)} tam={130 * U} t0={0.8} x={W / 2 + mw / 2 - 10 * U} y={cy - mh / 2 - 10 * U} />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ Las niñas (letras que rebotan) */
export type NinasProps = Base & { texto?: string; sub?: string };
export const Ninas: React.FC<NinasProps> = ({ texto = 'Las niñas', sub = '', estilo = 'lila', sticker = 'emoji:unicorn', y = 26, escala = 1, salida = 0.4 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { t, q } = useSalida(salida);
  const E = est(estilo);
  const letras = [...texto];
  const tam = Math.min(150 * U, (W * 0.86) / Math.max(4, letras.length) * 1.7);
  const colores = [E.acento, '#FFD1E8', '#FFF3A6', '#B8F2FF', '#D7C2FF'];
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <Halo x={W / 2} y={H * y / 100} w={W * 0.98} h={tam * 2.4} fuerza={0.3} />
      <Particulas color={E.acento} tipo="destellos" n={20} semilla={texto} />
      <div style={{ position: 'absolute', left: W / 2, top: H * y / 100, transform: 'translate(-50%,-50%)', display: 'flex', whiteSpace: 'pre' }}>
        {letras.map((c, i) => {
          const p = S(0.1 + i * 0.06, { damping: 7, stiffness: 190 });
          return <span key={i} style={{ display: 'inline-block', fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: tam, color: colores[i % colores.length],
                                        transform: `translateY(${((1 - p) * -120 * U + Math.sin(t * 4 + i) * 5 * U).toFixed(1)}px) rotate(${(Math.sin(t * 3 + i) * 4).toFixed(1)}deg)`,
                                        opacity: clamp(p * 3), WebkitTextStroke: `${3 * U}px rgba(0,0,0,.15)`, textShadow: `0 ${6 * U}px 0 rgba(0,0,0,.18), 0 ${10 * U}px ${24 * U}px ${E.sombra}` }}>{c}</span>;
        })}
      </div>
      {sub && <div style={{ position: 'absolute', left: W / 2, top: H * y / 100 + tam * 0.8, transform: 'translateX(-50%)', fontFamily: FAMILIA.serif, fontStyle: 'italic', fontSize: 52 * U,
                            color: '#fff', opacity: clamp(S(0.9)), textShadow: `0 4px 16px ${E.sombra}`, whiteSpace: 'nowrap' }}>{sub}</div>}
      <Sticker src={urlSticker(sticker)} tam={150 * U} t0={0.9} x={W / 2 - Math.min(W * 0.38, tam * letras.length * 0.32)} y={H * y / 100 - tam * 0.9} />
    </AbsoluteFill>
  );
};
