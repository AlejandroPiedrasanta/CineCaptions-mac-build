// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/Kit7.tsx — v5.5.2: el kit de motion graphics de la skill (referencias nuevas de skill videos/inspiration: listas de razones,
// misterio numerado, rueda de hooks, abanico de cartas, ruta numerada, título neón, tarjeta de concepto y tipografía mixta). Piezas REUTILIZABLES:
// todo sale de las props (cuántos, textos, tema de color, posición), sin nada fijo de un video. Mismas reglas que las demás plantillas:
// `y` (centro, % del alto), `escala`, `tema`, `salida` (s del fundido final). Sin velos oscuros ovalados detrás (el brillo es del propio gráfico).
//   ListaRazonesK  píldoras negras con punto rojo que entran de una en una («RAZÓN 1 · RAZÓN 2 · RAZÓN 3»)
//   MisterioK      esferas brillantes con «?» y su número (lo que aún no se cuenta)
//   RuedaK         rueda de N sectores que gira hasta el número + título («CONVIERTE 1 IDEA / EN 7 HOOKS»)
//   AbanicoK       N cartas que se reparten en abanico (número o icono) + título con el número grande
//   RutaK          un trazo (gancho, ola o subida) que se dibuja y va marcando los puntos 1…N + título
//   TituloNeonK    número gigante con brillo + título y subtítulo («8 LECCIONES NO OBVIAS»)
//   ConceptoK      placa con icono + palabra («ÉXITO», «FRACASO») y la gráfica de neón que sube o baja
//   MixtoK         tipografía mixta: una línea en cursiva serif + otra en negrita con la palabra clave en color y aberración cromática
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion';
import { FAMILIA, clamp, useFuentes, useResorte, useU } from './comun';
import { EmojiAnimado } from './Emoji';

export type Paleta = { a: string; b: string; glow: string; texto: string; punto: string; carta: [string, string]; placa: string; suave: string };
const PALETAS: Record<string, Paleta> = {
  neon: { a: '#9B5CFF', b: '#E07BFF', glow: '155,92,255', texto: '#FFFFFF', punto: '#FF2D3D', carta: ['#3B1A8F', '#8A45FF'], placa: 'rgba(16,9,30,.94)', suave: 'rgba(255,255,255,.72)' },
  rojo: { a: '#FF3344', b: '#FF8A5C', glow: '255,51,68', texto: '#FFFFFF', punto: '#FF2D3D', carta: ['#5E0A13', '#D3202F'], placa: 'rgba(28,6,9,.94)', suave: 'rgba(255,255,255,.72)' },
  azul: { a: '#2EA8FF', b: '#8BE6FF', glow: '46,168,255', texto: '#FFFFFF', punto: '#2EA8FF', carta: ['#0B2E66', '#1F7BE0'], placa: 'rgba(6,14,28,.94)', suave: 'rgba(255,255,255,.72)' },
  oro: { a: '#E9B949', b: '#FFE7A3', glow: '233,185,73', texto: '#FFFFFF', punto: '#E9B949', carta: ['#4A330A', '#B9851B'], placa: 'rgba(22,16,6,.94)', suave: 'rgba(255,255,255,.75)' },
  editorial: { a: '#1D1D21', b: '#B8894A', glow: '0,0,0', texto: '#1D1D21', punto: '#E2483D', carta: ['#F2F1EC', '#E4DFD2'], placa: 'rgba(242,241,236,.97)', suave: 'rgba(29,29,33,.65)' },
  // v5.5.13: el neón del Tema 1 (kit TEMA 1/graficos/tema-neon.css): magenta, lima y cartas moradas; fijo, no se rehace con el acento del video
  neoncc: { a: '#FF2DCB', b: '#D6FF3B', glow: '255,45,203', texto: '#FFFFFF', punto: '#D6FF3B', carta: ['#2A1258', '#7A35F5'], placa: 'rgba(20,16,30,.94)', suave: 'rgba(255,255,255,.74)' },
};
const esHex = (h?: string) => /^#?[0-9a-fA-F]{6}$/.test(String(h || ''));
const hexRgb = (h: string): [number, number, number] => {
  const n = parseInt(String(h).replace('#', ''), 16) || 0;
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};
export const mezcla = (h: string, con: [number, number, number], t: number) =>
  '#' + hexRgb(h).map((v, i) => Math.round(v + (con[i] - v) * t).toString(16).padStart(2, '0')).join('');
/** v5.5.2: la paleta. Con `acento` (el color que sale del propio video, edicion_pro_kit7.paleta_de_video) se construye una a medida (claro,
 *  oscuro y brillo del mismo color); si no, la del `tema`. El tema «editorial» (papel claro) se respeta siempre. */
export const pal = (t?: string, acento?: string, acento2?: string): Paleta => {
  const base = PALETAS[String(t || 'neon')] || PALETAS.neon;
  if (!esHex(acento) || String(t) === 'editorial' || String(t) === 'neoncc') return base;
  const a = '#' + String(acento).replace('#', '');
  const b = esHex(acento2) ? '#' + String(acento2).replace('#', '') : mezcla(a, [255, 255, 255], 0.45);
  const [r, g, bb] = hexRgb(a);
  return { ...base, a, b, glow: `${r},${g},${bb}`, carta: [mezcla(a, [0, 0, 0], 0.62), mezcla(a, [0, 0, 0], 0.12)],
           placa: `rgba(${Math.round(r * 0.09)},${Math.round(g * 0.09)},${Math.round(bb * 0.09)},.94)` };
};
const claro = (t?: string) => String(t) === 'editorial';

/** `variante`: el diseño de la pieza (cada una tiene varios: ver VARIANTES en edicion_pro_kit7.py); `acento` / `acento2`: colores a medida. */
type Base = { x?: number; y?: number; escala?: number; tema?: string; salida?: number; variante?: string; acento?: string; acento2?: string };

export const suave = (q: number) => { const x = clamp(q); return x * x * (3 - 2 * x); };
export const easeOut = (q: number) => 1 - Math.pow(1 - clamp(q), 3);

/** Tiempo y fundido de salida (0 → 1 en los últimos `salida` s). */
export const useVida = (salida = 0.35) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps, fin = durationInFrames / fps;
  return { t, fin, q: suave((t - (fin - salida)) / Math.max(0.05, salida)) };
};

export const brillo = (P: Paleta, U: number, k = 1) =>
  P.glow === '0,0,0' ? `0 ${6 * U}px ${18 * U}px rgba(0,0,0,.18)` : `0 0 ${16 * U * k}px rgba(${P.glow},.75), 0 0 ${44 * U * k}px rgba(${P.glow},.38)`;
export const textoBrillo = (P: Paleta, U: number, k = 1) =>
  P.glow === '0,0,0' ? 'none' : `0 0 ${12 * U * k}px rgba(${P.glow},.85), 0 0 ${34 * U * k}px rgba(${P.glow},.45)`;
const lista = (s?: string) => String(s || '').split(/[|,]/).map(x => x.trim()).filter(Boolean);
const entero = (v: unknown, def: number, a: number, b: number) => Math.max(a, Math.min(b, Math.round(Number(v) || def)));

/** Número grande con degradado + título + subtítulo (lo usan Abanico, Ruta y TituloNeon). */
const Encabezado: React.FC<{ numero?: string; titulo?: string; subtitulo?: string; P: Paleta; U: number; t: number; t0?: number; tam?: number; ed?: boolean }> =
  ({ numero, titulo, subtitulo, P, U, t, t0 = 0.05, tam = 1, ed = false }) => {
    if (!numero && !titulo) return null;
    const pn = easeOut((t - t0) / 0.45), pt = easeOut((t - t0 - 0.12) / 0.45), ps = easeOut((t - t0 - 0.3) / 0.45);
    const grande = 210 * U * tam, medio = 74 * U * tam;
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 22 * U * tam }}>
        {numero && (
          <div style={{ fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: grande, lineHeight: 0.86, letterSpacing: '-0.04em',
                        background: ed ? P.a : `linear-gradient(180deg, ${P.b}, ${P.a})`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
                        filter: ed ? 'none' : `drop-shadow(0 0 ${18 * U}px rgba(${P.glow},.7))`,
                        opacity: pn, transform: `scale(${(1.35 - 0.35 * pn).toFixed(4)})`, transformOrigin: '50% 60%' }}>{numero}</div>
        )}
        {(titulo || subtitulo) && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: numero ? 'flex-start' : 'center', maxWidth: 760 * U * tam }}>
            {titulo && (
              <div style={{ fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: medio, lineHeight: 0.98, color: ed ? P.texto : '#FFFFFF', textTransform: 'uppercase',
                            textShadow: textoBrillo(P, U, 0.6), opacity: pt, letterSpacing: `${(0.06 * (1 - pt)).toFixed(3)}em`,
                            transform: `translateX(${((1 - pt) * 30 * U).toFixed(2)}px)`, textAlign: numero ? 'left' : 'center' }}>{titulo}</div>
            )}
            {subtitulo && (
              <div style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 38 * U * tam, color: ed ? P.suave : 'rgba(255,255,255,.88)', marginTop: 6 * U, opacity: ps,
                            textShadow: ed ? 'none' : `0 ${2 * U}px ${10 * U}px rgba(0,0,0,.55)`,
                            textAlign: numero ? 'left' : 'center' }}>{subtitulo}</div>
            )}
          </div>
        )}
      </div>
    );
  };

/* ------------------------------------------------------------------------------------------------ ListaRazonesK */
export type ListaRazonesProps = Base & { items?: string; n?: number; prefijo?: string; actual?: number; cada?: number };
export const ListaRazonesK: React.FC<ListaRazonesProps> = ({ items = '', n = 3, prefijo = 'RAZÓN', actual = 0, cada = 0.22, x = 50, y = 62, escala = 1, tema = 'neon',
                                                             salida = 0.35, variante = 'pildora', acento, acento2 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { t, q } = useVida(salida);
  const P = pal(tema, acento, acento2), ed = claro(tema);
  const textos = lista(items).length ? lista(items) : Array.from({ length: entero(n, 3, 1, 6) }, (_, k) => `${prefijo} ${k + 1}`);
  const v = ['pildora', 'cristal', 'linea', 'tarjeta'].includes(variante) ? variante : 'pildora';
  const alto = 96 * U, hueco = (v === 'linea' ? 10 : 18) * U, ancho = Math.min(W * 0.78, 640 * U);
  const total = textos.length * alto + (textos.length - 1) * hueco;
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <div style={{ position: 'absolute', left: (W * x) / 100 - ancho / 2, top: (H * y) / 100 - total / 2, width: ancho, display: 'flex', flexDirection: 'column', gap: hueco }}>
        {textos.map((txt, k) => {
          const p = S(0.1 + k * cada, { damping: 14, stiffness: 170 });
          const marcada = actual > 0 && k + 1 === actual, apagada = actual > 0 && !marcada;
          const late = 0.5 + 0.5 * Math.sin(t * 5 + k);
          const claroFondo = ed || v === 'tarjeta';
          // cada variante: su fondo, su borde y su marca (punto rojo, número en círculo, número grande o barra de color)
          const fondo = v === 'pildora' ? (ed ? '#FFFFFF' : 'linear-gradient(180deg, #17171D, #0A0A0E)')
            : v === 'cristal' ? 'linear-gradient(180deg, rgba(255,255,255,.22), rgba(255,255,255,.10))'
            : v === 'tarjeta' ? '#FFFFFF' : 'transparent';
          const borde = v === 'linea' ? 'none'
            : `${1.6 * U}px solid ${marcada ? P.a : v === 'cristal' ? 'rgba(255,255,255,.42)' : claroFondo ? 'rgba(0,0,0,.08)' : 'rgba(255,255,255,.09)'}`;
          const marca = v === 'pildora' ? (
            <div style={{ width: 28 * U, height: 28 * U, borderRadius: '50%', background: P.punto, flex: 'none',
                          boxShadow: `0 0 ${(10 + 10 * late) * U}px ${P.punto}`, transform: `scale(${(0.9 + 0.15 * late).toFixed(3)})` }} />
          ) : v === 'cristal' ? (
            <div style={{ width: 54 * U, height: 54 * U, borderRadius: '50%', background: P.a, flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 30 * U, color: '#FFFFFF', boxShadow: brillo(P, U, 0.5) }}>{k + 1}</div>
          ) : v === 'linea' ? (
            <div style={{ fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 70 * U, lineHeight: 1, color: P.a, flex: 'none', minWidth: 54 * U,
                          textShadow: ed ? 'none' : textoBrillo(P, U, 0.5) }}>{k + 1}</div>
          ) : (
            <div style={{ width: 10 * U, alignSelf: 'stretch', margin: `${16 * U}px 0`, borderRadius: 6 * U, background: P.a, flex: 'none' }} />
          );
          return (
            <div key={k} style={{ height: alto, borderRadius: v === 'tarjeta' ? 20 * U : alto / 2, display: 'flex', alignItems: 'center', gap: 26 * U,
                                  padding: v === 'linea' ? 0 : `0 ${34 * U}px`, background: fondo, border: borde,
                                  boxShadow: v === 'linea' ? 'none' : (marcada ? brillo(P, U, 1) + ', ' : '') + `0 ${12 * U}px ${30 * U}px rgba(0,0,0,${claroFondo ? 0.14 : 0.45})`,
                                  opacity: clamp(p) * (apagada ? 0.5 : 1),
                                  transform: `translateX(${((1 - clamp(p)) * -60 * U).toFixed(2)}px) scale(${((0.9 + 0.1 * p) * (marcada ? 1.05 : 1)).toFixed(4)})` }}>
              {marca}
              <div style={{ position: 'relative', fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 46 * U, letterSpacing: '0.02em', textTransform: 'uppercase',
                            color: claroFondo ? (ed ? P.texto : '#1D1D21') : '#FFFFFF', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                            textShadow: v === 'linea' && !ed ? `0 ${3 * U}px ${12 * U}px rgba(0,0,0,.55)` : 'none' }}>
                {txt}
                {v === 'linea' && <div style={{ position: 'absolute', left: 0, bottom: -6 * U, height: 6 * U, borderRadius: 3 * U, background: P.a,
                                                width: `${(100 * easeOut((t - 0.25 - k * cada) / 0.5)).toFixed(1)}%` }} />}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ MisterioK */
export type MisterioProps = Base & { n?: number; revelar?: number; texto?: string };
export const MisterioK: React.FC<MisterioProps> = ({ n = 3, revelar = 0, texto = '', x = 50, y = 58, escala = 1, tema = 'neon', salida = 0.35,
                                                     variante = 'esferas', acento, acento2 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { t, q } = useVida(salida);
  const P = pal(tema === 'editorial' ? 'neon' : tema, acento, acento2);
  const v = ['esferas', 'cajas', 'contorno'].includes(variante) ? variante : 'esferas';
  const radio = v === 'cajas' ? '24%' : '50%';
  const N = entero(n, 3, 1, 5), hueco = 24 * U;
  const lado = Math.min(220 * U, (Math.min(W * 0.9, 980 * U) - hueco * (N - 1)) / N);
  const total = N * lado + (N - 1) * hueco;
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      {Array.from({ length: N }, (_, k) => {
        const p = S(0.08 + k * 0.14, { damping: 11, stiffness: 170 });
        const flota = Math.sin(t * 2.2 + k * 1.3) * 7 * U;
        const rev = revelar === k + 1 ? easeOut((t - 0.9) / 0.4) : 0;
        const cx = (W * x) / 100 - total / 2 + k * (lado + hueco) + lado / 2, cy = (H * y) / 100 + flota;
        return (
          <div key={k} style={{ position: 'absolute', left: cx - lado / 2, top: cy - lado / 2, width: lado, height: lado,
                                transform: `scale(${(Math.max(0.001, p) * (1 + 0.1 * rev)).toFixed(4)})` }}>
            <div style={{ position: 'absolute', inset: 0, borderRadius: radio, transform: v === 'cajas' ? `rotate(${(Math.sin(t * 1.6 + k) * 4).toFixed(2)}deg)` : undefined,
                          background: v === 'contorno' ? 'rgba(10,6,20,.35)' : v === 'cajas' ? `linear-gradient(150deg, ${P.b}, ${P.a} 55%, ${P.carta[0]})`
                            : `radial-gradient(circle at 36% 30%, ${P.b} 0%, ${P.a} 42%, ${P.carta[0]} 100%)`,
                          border: v === 'contorno' ? `${6 * U}px solid ${P.a}` : 'none',
                          boxShadow: `0 0 ${(30 + 30 * rev) * U}px rgba(${P.glow},.75), 0 0 ${90 * U}px rgba(${P.glow},.35)` +
                                     (v === 'contorno' ? `, inset 0 0 ${26 * U}px rgba(${P.glow},.55)` : `, inset 0 ${-14 * U}px ${30 * U}px rgba(0,0,0,.35), inset 0 ${8 * U}px ${18 * U}px rgba(255,255,255,.25)`) }} />
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: FAMILIA.redonda, fontWeight: 800,
                          fontSize: lado * 0.62, color: v === 'contorno' ? P.b : '#FFFFFF', opacity: 1 - rev,
                          textShadow: v === 'contorno' ? textoBrillo(P, U, 0.8) : `0 ${4 * U}px ${10 * U}px rgba(0,0,0,.35)` }}>?</div>
            {texto && rev > 0 && (
              <div style={{ position: 'absolute', inset: lado * 0.1, display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center',
                            fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: lado * 0.17, lineHeight: 1, color: '#FFFFFF', opacity: rev }}>{texto}</div>
            )}
            <div style={{ position: 'absolute', left: lado / 2 - lado * 0.15, top: lado * 0.86, width: lado * 0.3, height: lado * 0.3, borderRadius: '50%',
                          background: P.carta[0], border: `${3 * U}px solid rgba(255,255,255,.9)`, display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: lado * 0.17, color: '#FFFFFF', boxShadow: brillo(P, U, 0.6) }}>{k + 1}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ RuedaK */
export type RuedaProps = Base & { n?: number; actual?: number; titulo?: string; subtitulo?: string };
export const RuedaK: React.FC<RuedaProps> = ({ n = 7, actual = 0, titulo = 'CONVIERTE 1 IDEA', subtitulo = 'EN 7 HOOKS', x = 50, y = 56, escala = 1, tema = 'neon',
                                                 salida = 0.35, variante = 'rueda', acento, acento2 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { t, q } = useVida(salida);
  const P = pal(tema === 'editorial' ? 'neon' : tema, acento, acento2);
  const arco = variante === 'arco';                                    // «arco»: medio círculo arriba que se va ENCENDIENDO del 1 al N (sin girar)
  const N = entero(n, 7, 3, 12), sel0 = entero(actual || N, N, 1, N);
  const R = 240 * U, r = 132 * U, paso = (arco ? 180 : 360) / N, inicio = arco ? -180 : -90 - paso / 2;
  const giro = S(0.15, { damping: 18, stiffness: 60 });
  const sel = arco ? Math.max(1, Math.ceil(sel0 * easeOut((t - 0.25) / 1.2))) : sel0;
  const rot = arco ? 0 : -((sel - 1) * paso + paso / 2) * clamp(giro) + (1 - clamp(giro)) * 120;   // el sector elegido acaba ARRIBA
  const aparece = easeOut(t / 0.4);
  const cx = (W * x) / 100, cy = (H * y) / 100 + 90 * U;                               // `y` = centro del conjunto (rueda + títulos)
  const sector = (k: number) => {
    const a0 = ((k * paso + inicio) * Math.PI) / 180, a1 = (((k + 1) * paso + inicio) * Math.PI) / 180;
    const p = (rr: number, a: number) => `${(R + rr * Math.cos(a)).toFixed(2)} ${(R + rr * Math.sin(a)).toFixed(2)}`;
    return `M ${p(r, a0)} L ${p(R - 4 * U, a0)} A ${R - 4 * U} ${R - 4 * U} 0 0 1 ${p(R - 4 * U, a1)} L ${p(r, a1)} A ${r} ${r} 0 0 0 ${p(r, a0)} Z`;
  };
  const brilloSel = clamp((t - 0.8) / 0.4);
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <svg width={2 * R} height={2 * R} style={{ position: 'absolute', left: cx - R, top: cy - R * (arco ? 1.12 : 1.55), opacity: aparece, overflow: 'visible' }}>
        <defs>
          <linearGradient id="kitRuedaFade" x1="0" y1="0" x2="0" y2="1"><stop offset="0.42" stopColor="#fff" stopOpacity="1" /><stop offset="0.9" stopColor="#fff" stopOpacity="0" /></linearGradient>
          <mask id="kitRuedaMask"><rect x="0" y="0" width={2 * R} height={2 * R} fill="url(#kitRuedaFade)" /></mask>
          <linearGradient id="kitRuedaSel" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={P.b} /><stop offset="1" stopColor={P.a} /></linearGradient>
        </defs>
        <g mask={arco ? undefined : 'url(#kitRuedaMask)'} transform={`rotate(${rot.toFixed(3)} ${R} ${R})`}>
          {Array.from({ length: N }, (_, k) => {
            const es = k + 1 === sel, encendido = arco && k + 1 < sel;
            const am = ((k * paso + inicio + paso / 2) * Math.PI) / 180, rm = (R + r) / 2;
            return (
              <g key={k}>
                <path d={sector(k)} fill={es ? 'url(#kitRuedaSel)' : encendido ? `rgba(${P.glow},.45)` : 'rgba(18,10,36,.62)'}
                      stroke={es || encendido ? P.b : 'rgba(255,255,255,.28)'} strokeWidth={1.5 * U}
                      style={es ? { filter: `drop-shadow(0 0 ${(10 + 18 * brilloSel) * U}px rgba(${P.glow},.9))` } : undefined} />
                <text x={R + rm * Math.cos(am)} y={R + rm * Math.sin(am)} fill={es ? '#FFFFFF' : 'rgba(255,255,255,.62)'} fontFamily={FAMILIA.redonda} fontWeight={800}
                      fontSize={(es ? 64 : 40) * U} textAnchor="middle" dominantBaseline="central"
                      transform={`rotate(${(-rot).toFixed(3)} ${R + rm * Math.cos(am)} ${R + rm * Math.sin(am)})`}>{k + 1}</text>
              </g>
            );
          })}
        </g>
      </svg>
      <div style={{ position: 'absolute', left: cx - W / 2, width: W, top: cy + 10 * U, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        {titulo && (
          <div style={{ fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 86 * U, lineHeight: 1, color: '#FFFFFF', textTransform: 'uppercase', textAlign: 'center',
                        textShadow: `0 ${6 * U}px ${22 * U}px rgba(0,0,0,.45)`, opacity: easeOut((t - 0.25) / 0.4),
                        transform: `translateY(${((1 - easeOut((t - 0.25) / 0.4)) * 24 * U).toFixed(2)}px)` }}>{titulo}</div>
        )}
        {subtitulo && (
          <div style={{ fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 86 * U, lineHeight: 1.05, textTransform: 'uppercase', textAlign: 'center',
                        background: `linear-gradient(90deg, ${P.b}, ${P.a})`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
                        filter: `drop-shadow(0 0 ${14 * U}px rgba(${P.glow},.65))`, transform: `skewX(-9deg) scale(${(0.9 + 0.1 * easeOut((t - 0.45) / 0.4)).toFixed(4)})`,
                        opacity: easeOut((t - 0.45) / 0.4) }}>{subtitulo}</div>
        )}
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ AbanicoK */
export type AbanicoProps = Base & { n?: number; iconos?: string; numero?: string; titulo?: string; subtitulo?: string; actual?: number };
export const AbanicoK: React.FC<AbanicoProps> = ({ n = 3, iconos = '', numero = '', titulo = '', subtitulo = '', actual = 0, x = 50, y = 56, escala = 1, tema = 'neon',
                                                   salida = 0.35, variante = 'abanico', acento, acento2 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { t, q } = useVida(salida);
  const P = pal(tema, acento, acento2), ed = claro(tema);
  const N = entero(n, 3, 2, 8), ics = lista(iconos);
  const v = ['abanico', 'fila', 'pila'].includes(variante) ? variante : 'abanico';
  // «fila»: cartas en línea con una ligera inclinación alterna; «pila»: un mazo escalonado (asoman todas); «abanico»: en arco
  const w = (v === 'fila' ? Math.min(230, 900 / N) : N <= 3 ? 230 : N <= 5 ? 170 : 132) * U, h = w * 1.42;
  const abre = Math.min(64, 11 * (N - 1)), Rf = w * 2.9;
  const cx = (W * x) / 100, base = (H * y) / 100 + (numero || titulo ? 150 * U : 0);     // `y` = centro del conjunto (título + cartas)
  const cabeza = numero || titulo;
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      {cabeza && (
        <div style={{ position: 'absolute', left: cx - W / 2, width: W, top: base - h / 2 - 300 * U, display: 'flex', justifyContent: 'center' }}>
          <Encabezado numero={numero} titulo={titulo} subtitulo={subtitulo} P={P} U={U} t={t} tam={0.85} ed={ed} />
        </div>
      )}
      {Array.from({ length: N }, (_, k) => {
        const p = S(0.18 + k * 0.08, { damping: 15, stiffness: 140 });
        let ang = N === 1 ? 0 : -abre / 2 + (k * abre) / (N - 1);
        const rad = (ang * Math.PI) / 180;
        let fx = cx + Math.sin(rad) * Rf, fy = base + (1 - Math.cos(rad)) * Rf;
        if (v === 'fila') {
          const hueco = 18 * U;
          fx = cx - ((N - 1) * (w + hueco)) / 2 + k * (w + hueco);
          fy = base;
          ang = k % 2 ? 4 : -4;
        } else if (v === 'pila') {
          fx = cx + (k - (N - 1) / 2) * w * 0.22;
          fy = base + (k - (N - 1) / 2) * w * 0.07;
          ang = (k - (N - 1) / 2) * 3;
        }
        const sx = cx, sy = base + H * 0.18;
        const px = sx + (fx - sx) * clamp(p), py = sy + (fy - sy) * clamp(p);
        const marcada = actual > 0 && k + 1 === actual;
        const sube = marcada ? easeOut((t - 0.9) / 0.35) * 46 * U : 0;
        return (
          <div key={k} style={{ position: 'absolute', left: px - w / 2, top: py - h / 2 - sube, width: w, height: h, borderRadius: 24 * U,
                                background: ed ? `linear-gradient(160deg, #FFFFFF, ${P.carta[1]})` : `linear-gradient(160deg, ${P.carta[1]}, ${P.carta[0]})`,
                                border: `${2 * U}px solid ${ed ? 'rgba(0,0,0,.08)' : 'rgba(255,255,255,.22)'}`,
                                boxShadow: `${brillo(P, U, marcada ? 1.3 : 0.55)}, 0 ${16 * U}px ${36 * U}px rgba(0,0,0,.4)`,
                                transform: `rotate(${(ang * clamp(p)).toFixed(3)}deg) scale(${(0.82 + 0.18 * clamp(p)).toFixed(4)})`, opacity: clamp(p * 1.4),
                                display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
            {ics[k % Math.max(1, ics.length)] ? (
              <>
                <div style={{ position: 'absolute', left: 16 * U, top: 10 * U, fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: w * 0.3, color: ed ? P.a : '#FFFFFF' }}>{k + 1}</div>
                <EmojiAnimado id={ics[k % ics.length]} lado={w * 0.56} style={{ position: 'absolute', left: w * 0.22, top: h * 0.36, opacity: 0.9 }} />
              </>
            ) : (
              <div style={{ fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: w * (N <= 3 ? 0.62 : 0.5), color: ed ? P.a : '#FFFFFF',
                            textShadow: ed ? 'none' : `0 ${4 * U}px ${14 * U}px rgba(0,0,0,.35)` }}>{k + 1}</div>
            )}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ RutaK */
type Pt = [number, number];
const bez = (p0: Pt, p1: Pt, p2: Pt, p3: Pt, s: number): Pt => {
  const m = 1 - s;
  return [m * m * m * p0[0] + 3 * m * m * s * p1[0] + 3 * m * s * s * p2[0] + s * s * s * p3[0], m * m * m * p0[1] + 3 * m * m * s * p1[1] + 3 * m * s * s * p2[1] + s * s * s * p3[1]];
};
const FORMAS: Record<string, [Pt, Pt, Pt, Pt][]> = {                      // en una caja 0..1 (x a la derecha, y hacia abajo)
  gancho: [[[0.78, 0.02], [0.78, 0.3], [0.8, 0.55], [0.78, 0.7]], [[0.78, 0.7], [0.74, 1.02], [0.3, 1.02], [0.24, 0.72]], [[0.24, 0.72], [0.22, 0.6], [0.16, 0.56], [0.12, 0.6]]],
  ola: [[[0.04, 0.55], [0.2, 0.05], [0.32, 0.05], [0.5, 0.5]], [[0.5, 0.5], [0.68, 0.95], [0.8, 0.95], [0.96, 0.45]]],
  subida: [[[0.04, 0.92], [0.2, 0.9], [0.24, 0.62], [0.38, 0.66]], [[0.38, 0.66], [0.52, 0.7], [0.56, 0.36], [0.7, 0.4]], [[0.7, 0.4], [0.84, 0.44], [0.86, 0.08], [0.96, 0.06]]],
  escalera: [[[0.04, 0.95], [0.16, 0.95], [0.2, 0.95], [0.24, 0.72]], [[0.24, 0.72], [0.36, 0.72], [0.42, 0.72], [0.46, 0.5]],
             [[0.46, 0.5], [0.58, 0.5], [0.64, 0.5], [0.68, 0.28]], [[0.68, 0.28], [0.8, 0.28], [0.88, 0.28], [0.96, 0.05]]],
};
const muestrear = (forma: string, cw: number, ch: number, por = 60) => {
  const pts: Pt[] = [];
  for (const seg of FORMAS[forma] || FORMAS.ola) {
    for (let i = 0; i <= por; i++) {
      if (pts.length && i === 0) continue;
      const [px, py] = bez(seg[0], seg[1], seg[2], seg[3], i / por);
      pts.push([px * cw, py * ch]);
    }
  }
  const acum = [0];
  for (let i = 1; i < pts.length; i++) acum.push(acum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  return { pts, acum, largo: acum[acum.length - 1] };
};
export type RutaProps = Base & { n?: number; forma?: string; numero?: string; titulo?: string; subtitulo?: string };
export const RutaK: React.FC<RutaProps> = ({ n = 4, forma: forma0 = 'gancho', numero = '4', titulo = 'ERRORES', subtitulo = '', x = 50, y = 58, escala = 1, tema = 'azul',
                                               salida = 0.35, variante = '', acento, acento2 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala;
  const { t, q } = useVida(salida);
  const P = pal(tema, acento, acento2), ed = claro(tema);
  const forma = FORMAS[variante] ? variante : FORMAS[forma0] ? forma0 : 'ola';         // la variante ES la forma del trazo
  const N = entero(n, 4, 2, 7);
  const cw = Math.min(W * 0.66, 700 * U), ch = forma === 'gancho' ? cw * 0.95 : cw * 0.62;
  const ox = (W * x) / 100 - cw / 2, oy = (H * y) / 100 - ch / 2 + (numero || titulo ? 135 : 0) * U;   // `y` = centro del conjunto
  const { pts, acum, largo } = muestrear(forma, cw, ch);
  const prog = easeOut((t - 0.3) / 1.4) * largo;
  const hasta = pts.filter((_, i) => acum[i] <= prog);
  const linea = (arr: Pt[]) => arr.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const desplazados = pts.map((p, i) => {                                // la línea discontinua, paralela por fuera
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
    const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1;
    return [p[0] - (dy / l) * 26 * U, p[1] + (dx / l) * 26 * U] as Pt;
  });
  const marcas = Array.from({ length: N }, (_, k) => {
    const objetivo = largo * (0.1 + (0.8 * k) / Math.max(1, N - 1));
    let i = acum.findIndex(v => v >= objetivo);
    if (i < 0) i = pts.length - 1;
    return { i, p: desplazados[i], visible: clamp((prog - objetivo) / (0.08 * largo)) };
  });
  const trazo = ed ? P.a : '#E9EEF5';
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      {(numero || titulo) && (
        <div style={{ position: 'absolute', left: 0, width: W, top: oy - 270 * U, display: 'flex', justifyContent: 'center' }}>
          <Encabezado numero={numero} titulo={titulo} subtitulo={subtitulo} P={P} U={U} t={t} tam={0.8} ed={ed} />
        </div>
      )}
      <svg width={W} height={H} style={{ position: 'absolute', left: 0, top: 0, overflow: 'visible' }}>
        <g transform={`translate(${ox.toFixed(1)} ${oy.toFixed(1)})`}>
          <polyline points={linea(desplazados.filter((_, i) => acum[i] <= prog))} fill="none" stroke={P.b} strokeWidth={4 * U} strokeDasharray={`${12 * U} ${10 * U}`} opacity={0.95}
                    style={{ filter: `drop-shadow(0 0 ${3 * U}px rgba(0,0,0,.5))` }} />
          <polyline points={linea(hasta)} fill="none" stroke="rgba(0,0,0,.35)" strokeWidth={22 * U} strokeLinecap="round" strokeLinejoin="round" />
          <polyline points={linea(hasta)} fill="none" stroke={trazo} strokeWidth={14 * U} strokeLinecap="round" strokeLinejoin="round"
                    style={{ filter: ed ? 'none' : `drop-shadow(0 0 ${10 * U}px rgba(255,255,255,.55))` }} />
          {marcas.map((m, k) => m.visible > 0 && (
            <g key={k} opacity={m.visible} transform={`translate(${m.p[0].toFixed(1)} ${m.p[1].toFixed(1)}) scale(${(0.6 + 0.4 * m.visible).toFixed(3)})`}>
              <circle r={16 * U} fill={P.b} stroke="#FFFFFF" strokeWidth={3 * U} style={{ filter: `drop-shadow(0 0 ${10 * U}px ${P.b})` }} />
              <text x={34 * U} y={0} fill={ed ? P.a : '#FFFFFF'} stroke={ed ? 'none' : P.a} strokeWidth={2 * U} paintOrder="stroke" fontFamily={FAMILIA.redonda} fontWeight={800}
                    fontSize={64 * U} dominantBaseline="central" style={{ filter: ed ? 'none' : `drop-shadow(0 0 ${8 * U}px rgba(${P.glow},.9))` }}>{k + 1}</text>
            </g>
          ))}
        </g>
      </svg>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ TituloNeonK */
export type TituloNeonProps = Base & { numero?: string; titulo?: string; subtitulo?: string };
export const TituloNeonK: React.FC<TituloNeonProps> = ({ numero = '8', titulo = 'LECCIONES NO OBVIAS', subtitulo = 'para crecer de 0 a 250.000', x = 50, y = 30, escala = 1,
                                                         tema = 'neon', salida = 0.35, variante = 'neon', acento, acento2 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala;
  const { t, q } = useVida(salida);
  const P = pal(tema, acento, acento2), ed = claro(tema);
  const limpio = variante === 'limpio';                                  // «limpio»: sin la mancha de luz, con una barra de color que se dibuja debajo
  const late = 0.5 + 0.5 * Math.sin(t * 1.6);
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      {limpio && (
        <div style={{ position: 'absolute', left: (W * x) / 100 - 260 * U, top: (H * y) / 100 + 112 * U, height: 10 * U, borderRadius: 5 * U, background: P.a,
                      width: 520 * U * easeOut((t - 0.35) / 0.6), boxShadow: ed ? 'none' : brillo(P, U, 0.5) }} />
      )}
      {!ed && !limpio && (
        <div style={{ position: 'absolute', left: (W * x) / 100 - 330 * U, top: (H * y) / 100 - 260 * U, width: 420 * U, height: 420 * U, borderRadius: '50%',
                      background: `radial-gradient(circle, rgba(${P.glow},.55) 0%, rgba(${P.glow},.18) 45%, rgba(${P.glow},0) 70%)`,
                      transform: `scale(${(0.85 + 0.15 * late + 0.2 * (1 - easeOut(t / 0.6))).toFixed(4)})`, opacity: easeOut(t / 0.5) }} />
      )}
      <div style={{ position: 'absolute', left: (W * x) / 100 - W / 2, width: W, top: (H * y) / 100 - 110 * U, display: 'flex', justifyContent: 'center' }}>
        <Encabezado numero={numero} titulo={titulo} subtitulo={subtitulo} P={P} U={U} t={t} ed={ed} />
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ ConceptoK */
const Icono: React.FC<{ tipo: string; lado: number; P: Paleta; U: number }> = ({ tipo, lado, P, U }) => {
  if (tipo.startsWith('emoji:')) return <EmojiAnimado id={tipo} lado={lado * 0.62} />;
  const plata = 'url(#kitPlata)';
  return (
    <svg width={lado * 0.62} height={lado * 0.62} viewBox="0 0 100 100" style={{ overflow: 'visible' }}>
      <defs><linearGradient id="kitPlata" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#FFFFFF" /><stop offset="1" stopColor="#B9BEC8" /></linearGradient></defs>
      {tipo === 'personas' ? (
        <g fill={plata}>
          <circle cx="24" cy="38" r="11" /><circle cx="76" cy="38" r="11" /><circle cx="50" cy="30" r="14" />
          <path d="M6 82 Q8 56 24 54 Q40 56 42 82 Z" /><path d="M58 82 Q60 56 76 54 Q92 56 94 82 Z" /><path d="M26 90 Q28 50 50 48 Q72 50 74 90 Z" />
        </g>
      ) : tipo === 'persona' ? (
        <g fill={plata}><circle cx="50" cy="30" r="18" /><path d="M18 92 Q20 52 50 50 Q80 52 82 92 Z" /></g>
      ) : tipo === 'rayo' ? (
        <path d="M58 4 L22 56 L46 56 L38 96 L80 40 L54 40 Z" fill={P.b} />
      ) : (
        <g style={{ filter: `drop-shadow(0 0 ${6 * U}px ${P.a})` }}>
          <path d="M50 6 L86 50 L50 94 L14 50 Z" fill={P.a} /><path d="M50 6 L86 50 L50 50 Z" fill={P.b} opacity={0.7} />
        </g>
      )}
    </svg>
  );
};
export type ConceptoProps = Base & { palabra?: string; sub?: string; icono?: string; grafica?: string; tarjeta?: boolean };
export const ConceptoK: React.FC<ConceptoProps> = ({ palabra = 'ÉXITO', sub = '', icono = 'diamante', grafica = 'sube', tarjeta: conTarjeta = true, x = 50, y = 50, escala = 1,
                                                     tema = 'rojo', salida = 0.35, variante = 'tarjeta', acento, acento2 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte();
  const { t, q } = useVida(salida);
  const P = pal(tema, acento, acento2), ed = claro(tema);
  // «tarjeta»: la placa oscura; «flotante»: lo mismo sin placa, sobre el video; «linea»: sin icono, la palabra grande y la gráfica
  const tarjeta = conTarjeta && variante !== 'flotante' && variante !== 'linea', conIcono = variante !== 'linea';
  const cw = Math.min(W * 0.84, 820 * U), chh = cw * 1.12;
  const cx = (W * x) / 100, cy = (H * y) / 100;
  const pc = S(0.02, { damping: 16, stiffness: 150 }), pi = S(0.2, { damping: 11 }), pw = easeOut((t - 0.35) / 0.4);
  const zig = grafica === 'baja'
    ? [[0, 0.06], [0.12, 0.2], [0.2, 0.14], [0.34, 0.36], [0.44, 0.3], [0.58, 0.55], [0.66, 0.48], [0.8, 0.74], [0.88, 0.68], [1, 0.96]]
    : [[0, 0.96], [0.12, 0.8], [0.2, 0.86], [0.34, 0.62], [0.44, 0.68], [0.58, 0.42], [0.66, 0.5], [0.8, 0.24], [0.88, 0.3], [1, 0.04]];
  const gw = cw * 0.92, gh = chh * 0.42;
  const pg = easeOut((t - 0.55) / 1.1);
  const pts = zig.map(([a, b]) => [a * gw, b * gh]);
  const acum = [0];
  for (let i = 1; i < pts.length; i++) acum.push(acum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  const L = acum[acum.length - 1] * pg;
  const visibles: number[][] = [];
  for (let i = 0; i < pts.length; i++) {
    if (acum[i] <= L) visibles.push(pts[i]);
    else { const f = (L - acum[i - 1]) / (acum[i] - acum[i - 1]); visibles.push([pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * f, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f]); break; }
  }
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <div style={{ position: 'absolute', left: cx - cw / 2, top: cy - chh / 2, width: cw, height: chh, borderRadius: 40 * U,
                    background: tarjeta ? (ed ? P.placa : `radial-gradient(ellipse 90% 60% at 50% 22%, rgba(${P.glow},.22), rgba(0,0,0,0) 70%), ${P.placa}`) : 'transparent',
                    border: tarjeta ? `${1.5 * U}px solid ${ed ? 'rgba(0,0,0,.08)' : 'rgba(255,255,255,.08)'}` : 'none',
                    boxShadow: tarjeta ? `0 ${24 * U}px ${60 * U}px rgba(0,0,0,.45)` : 'none', overflow: 'hidden',
                    opacity: clamp(pc * 1.3), transform: `scale(${(0.94 + 0.06 * clamp(pc)).toFixed(4)})` }}>
        {conIcono && (
          <div style={{ position: 'absolute', left: cw / 2 - 74 * U, top: chh * 0.12, width: 148 * U, height: 148 * U, borderRadius: '50%',
                        border: `${4 * U}px solid ${P.a}`, boxShadow: brillo(P, U, 1), display: 'flex', alignItems: 'center', justifyContent: 'center',
                        background: ed ? '#FFFFFF' : 'rgba(0,0,0,.35)', transform: `scale(${Math.max(0.001, pi).toFixed(4)})` }}>
            <Icono tipo={icono} lado={148 * U} P={P} U={U} />
          </div>
        )}
        <div style={{ position: 'absolute', left: 0, right: 0, top: chh * 0.12 + (conIcono ? 176 : 40) * U, textAlign: 'center', fontFamily: FAMILIA.redonda, fontWeight: 800,
                      fontSize: (conIcono ? 84 : 120) * U, color: ed ? P.texto : '#FFFFFF', textTransform: 'uppercase', letterSpacing: `${(0.02 + 0.1 * (1 - pw)).toFixed(3)}em`,
                      textShadow: ed ? 'none' : tarjeta ? `0 0 ${18 * U}px rgba(255,255,255,.35)` : `0 ${4 * U}px ${18 * U}px rgba(0,0,0,.6), 0 0 ${18 * U}px rgba(${P.glow},.5)`,
                      opacity: pw }}>{palabra}</div>
        {sub && (
          <div style={{ position: 'absolute', left: 40 * U, right: 40 * U, top: chh * 0.12 + (conIcono ? 278 : 180) * U, textAlign: 'center', fontFamily: FAMILIA.inter, fontWeight: 500,
                        fontSize: 32 * U, color: P.suave, opacity: easeOut((t - 0.6) / 0.4) }}>{sub}</div>
        )}
        {grafica !== 'ninguna' && (
          <svg width={gw} height={gh} style={{ position: 'absolute', left: (cw - gw) / 2, top: chh - gh - 40 * U, overflow: 'visible' }}>
            <polyline points={visibles.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')} fill="none" stroke={P.a} strokeWidth={8 * U}
                      strokeLinejoin="round" strokeLinecap="round" style={{ filter: ed ? 'none' : `drop-shadow(0 0 ${12 * U}px ${P.a})` }} />
          </svg>
        )}
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ MixtoK */
export type MixtoProps = Base & { linea1?: string; linea2?: string; clave?: string; aberracion?: boolean };
export const MixtoK: React.FC<MixtoProps> = ({ linea1 = 'No es decoración,', linea2 = 'es una herramienta de ritmo', clave = 'ritmo', aberracion = true, x = 50, y = 46,
                                               escala = 1, tema = 'rojo', salida = 0.35, variante = 'glitch', acento, acento2 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala;
  const { t, q } = useVida(salida);
  const P = pal(tema, acento, acento2), ed = claro(tema);
  const rotulador = variante === 'rotulador';                           // «rotulador»: sin aberración; la palabra clave, subrayada con un trazo de color
  const ab = aberracion && !ed && !rotulador ? (2 + 7 * (1 - easeOut((t - 0.3) / 0.5))) * U : 0;
  const marca = easeOut((t - 0.75) / 0.45);
  const rgbSplit = ab > 0 ? `${-ab}px 0 rgba(255,0,70,.55), ${ab}px 0 rgba(0,220,255,.55)` : '';
  const pal1 = String(linea1 || '').split(/\s+/).filter(Boolean), pal2 = String(linea2 || '').split(/\s+/).filter(Boolean);
  const plegar = (s: string) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^\p{L}\p{N}]/gu, '');
  const k = plegar(clave);
  const p2 = easeOut((t - 0.3) / 0.45);
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <div style={{ position: 'absolute', left: (W * x) / 100 - W * 0.45, width: W * 0.9, top: (H * y) / 100 - 120 * U, textAlign: 'center' }}>
        <div style={{ fontFamily: FAMILIA.display, fontStyle: 'italic', fontSize: 70 * U, lineHeight: 1.05, color: ed ? P.texto : '#FFFFFF' }}>
          {pal1.map((w, i) => {
            const p = easeOut((t - 0.05 - i * 0.07) / 0.35);
            return <span key={i} style={{ display: 'inline-block', marginRight: '0.25em', opacity: p, filter: `blur(${((1 - p) * 8 * U).toFixed(2)}px)` }}>{w}</span>;
          })}
        </div>
        <div style={{ fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 96 * U, lineHeight: 1.02, marginTop: 10 * U, opacity: p2,
                      transform: `scale(${(1.14 - 0.14 * p2).toFixed(4)})`, filter: `blur(${((1 - p2) * 10 * U).toFixed(2)}px)` }}>
          {pal2.map((w, i) => {
            const es = k && plegar(w) === k;
            const color = es && !rotulador ? P.a : ed ? P.texto : '#FFFFFF';
            const sombra = [rgbSplit, es && !ed && !rotulador ? textoBrillo(P, U, 1) : '', !es || rotulador ? `0 ${3 * U}px ${14 * U}px rgba(0,0,0,${ed ? 0 : 0.5})` : '']
              .filter(Boolean).join(', ') || 'none';
            const resalte = es && rotulador ? { background: `linear-gradient(${P.a}, ${P.a}) no-repeat 0 88% / ${(100 * marca).toFixed(1)}% 34%`, padding: `0 ${6 * U}px` } : {};
            return <span key={i} style={{ display: 'inline-block', marginRight: '0.22em', color, textShadow: sombra, ...resalte }}>{w}</span>;
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
