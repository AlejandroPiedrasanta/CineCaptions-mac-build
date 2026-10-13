// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/Objetos.tsx — los objetos de las escenas del Tema 5 (lo que ILUSTRA lo que se dice, como en el video de referencia de la
// skill): muestra de color · ficha de marca · icono de reproducir (que se encoge con su marco de selección) · ojo con tarjetas de interfaz · barra de
// uso · tarjeta de precio · gráfica que sube · reloj · avatares · calendario · estado (mal / bien) · cifra.
// Todos dibujados con CSS/SVG (nítidos a cualquier tamaño), con el mismo lenguaje: blanco, sombras suaves, tinta oscura, UNA tinta de acento.
// Cada uno entra en su `t` (cuando se dice su palabra): escala + desenfoque → nítido, sin rebotes; y flota muy poco.
import { createContext, useContext } from 'react';
import { useCurrentFrame, useVideoConfig } from 'remotion';
import { FAMILIA, clamp, rgb } from './comun';

export const TINTA = '#1D1D21';
export const GRIS = '#8B8B95';
const easeOut = (q: number) => 1 - Math.pow(1 - clamp(q), 3);
const easeInOut = (q: number) => { const x = clamp(q); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };

export type Objeto = { tipo: string; t: number; [k: string]: any };

/** El aspecto de los objetos: claro (papel, la referencia) u oscuro (cristal oscuro con brillo, el tablero de inspiración / encima del video). */
export type TemaObj = { oscuro: boolean; carta: string; tinta: string; gris: string; suave: string; linea: string; borde: string; letra?: string };
export const TEMA_CLARO: TemaObj = { oscuro: false, carta: '#FFFFFF', tinta: TINTA, gris: GRIS, suave: '#EEF0F4', linea: '#E4E6EC', borde: 'transparent' };
export const TEMA_OSCURO: TemaObj = { oscuro: true, carta: 'linear-gradient(180deg, rgba(40,44,60,.94), rgba(20,22,32,.94))', tinta: '#F4F5F9', gris: '#9AA1B4',
                                      suave: 'rgba(255,255,255,.08)', linea: 'rgba(255,255,255,.14)', borde: 'rgba(255,255,255,.12)' };
/** Tema 6 («Editorial»): fondo melocotón, cartas blancas con un borde cálido y la serif alta y fina (Instrument Serif), sin negritas. */
export const TEMA_MELOCOTON: TemaObj = { oscuro: false, carta: '#FFFFFF', tinta: '#2E2622', gris: '#9A8A80', suave: '#FBEDE5', linea: '#F1DFD4',
                                         borde: 'rgba(214,170,140,.38)', letra: FAMILIA.serif };
export const TemaCtx = createContext<TemaObj>(TEMA_CLARO);
export const useTema = () => useContext(TemaCtx);

/** Tiempo del objeto: su entrada [0..1] y los segundos desde que entró. */
export const useEntrada = (t0: number, dura = 0.42) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  return { t, dt: t - t0, e: easeOut((t - t0) / dura) };
};

export const sombra = (U: number, k = 1) => `0 ${24 * U * k}px ${60 * U * k}px rgba(30,40,80,.14), 0 ${2 * U}px ${6 * U}px rgba(30,40,80,.06)`;

/** Envoltorio común: posición (centro), entrada (escala + desenfoque), flotación suave y salida (se va hacia `fuera`). */
export const Pieza: React.FC<{ x: number; y: number; t0: number; U: number; salida: number; fuera?: [number, number]; flota?: number; children: React.ReactNode }> = (
  { x, y, t0, U, salida, fuera = [0, -1], flota = 1, children }) => {
  const { dt, e } = useEntrada(t0);
  if (dt < -0.02) return null;
  const f = Math.sin(dt * 1.5 + x * 0.01) * 5 * U * flota;
  const s = easeOut(salida);
  return (
    <div style={{ position: 'absolute', left: x, top: y, transform: `translate(-50%, -50%) translate(${(fuera[0] * s * 140 * U).toFixed(1)}px, ${(f + fuera[1] * s * 140 * U + (1 - e) * 26 * U).toFixed(1)}px) scale(${(0.78 + 0.22 * e).toFixed(4)})`,
                  opacity: e * (1 - s), filter: `blur(${((1 - e) * 10 + s * 8).toFixed(2)}px)` }}>
      {children}
    </div>
  );
};

/* ------------------------------------------------------------------------------------------------ muestra de color */
export const Muestra: React.FC<{ o: Objeto; U: number }> = ({ o, U }) => {
  const T = useTema();
  const lado = 200 * U;
  const claro = rgb(o.color).reduce((a, b) => a + b, 0) > 600;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 * U }}>
      <div style={{ width: lado, height: lado, borderRadius: 40 * U, background: `linear-gradient(160deg, rgba(255,255,255,.16), rgba(255,255,255,0) 45%), ${o.color}`,
                    boxShadow: sombra(U) + (claro ? `, inset 0 0 0 ${1.5 * U}px rgba(0,0,0,.06)` : '') }} />
      <div style={{ textAlign: 'center', lineHeight: 1.25 }}>
        <div style={{ fontFamily: (T.letra || FAMILIA.inter), fontWeight: 700, fontSize: 17 * U, letterSpacing: '0.09em', color: T.tinta }}>{o.etiqueta}</div>
        <div style={{ fontFamily: (T.letra || FAMILIA.inter), fontWeight: 500, fontSize: 15 * U, letterSpacing: '0.06em', color: T.gris }}>{o.hex}</div>
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------------------------------------ ficha de marca */
export const Ficha: React.FC<{ o: Objeto; U: number }> = ({ o, U }) => {
  const T = useTema();
  return (
  <div style={{ padding: `${18 * U}px ${30 * U}px`, borderRadius: 16 * U, background: T.carta, border: `${1.2 * U}px solid ${T.borde}`, boxShadow: sombra(U, 0.7), whiteSpace: 'nowrap', display: 'flex',
                alignItems: 'center', gap: 12 * U }}>
    {!o.serif && <div style={{ width: 14 * U, height: 14 * U, borderRadius: 7 * U, background: o.color }} />}
    <span style={{ fontFamily: o.serif ? FAMILIA.serif : (T.letra || FAMILIA.inter), fontWeight: o.serif ? 400 : 700, fontSize: (o.serif ? 34 : 30) * U,
                   letterSpacing: o.serif ? '0.06em' : '-0.01em', color: o.serif ? (T.oscuro ? T.tinta : (o.color || TINTA)) : T.tinta }}>{o.texto}</span>
  </div>
  );
};

/* ------------------------------------------------------------------------------------------------ icono de reproducir (y se encoge) */
export const App: React.FC<{ o: Objeto; U: number; acento: string }> = ({ o, U, acento }) => {
  const T = useTema();
  const { dt } = useEntrada(o.t);
  const escala = typeof o.escala === 'number' ? o.escala : 1;
  const te = typeof o.t_escala === 'number' ? o.t_escala - o.t : 1.2;
  const pe = easeInOut((dt - te) / 0.7);
  const k = 1 + (escala - 1) * pe;
  const lado = 340 * U;
  const [r, g, b] = rgb(acento);
  const marco = escala < 1 || escala > 1 ? clamp((dt - te + 0.2) / 0.25) : 0;
  const ins = easeOut((dt - te - 0.35) / 0.35);
  return (
    <div style={{ position: 'relative', width: lado, height: lado }}>
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${k.toFixed(4)})` }}>
        <div style={{ position: 'absolute', inset: 0, borderRadius: lado * 0.22, background: T.oscuro ? T.carta : 'linear-gradient(180deg,#FFFFFF,#F3F4F8)', border: `${1.2 * U}px solid ${T.borde}`, boxShadow: sombra(U),
                      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: lado * 0.07 }}>
          <div style={{ width: lado * 0.52, height: lado * 0.52, borderRadius: lado * 0.13, background: `linear-gradient(160deg, rgb(${Math.min(255, r + 40)},${Math.min(255, g + 70)},255), rgb(${r},${g},${b}) 60%, rgb(${Math.max(0, r - 30)},${Math.max(0, g - 40)},${Math.max(0, b - 40)}))`,
                        boxShadow: `0 ${10 * U}px ${26 * U}px rgba(${r},${g},${b},.45), inset 0 ${3 * U}px ${6 * U}px rgba(255,255,255,.35)`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width={lado * 0.22} height={lado * 0.22} viewBox="0 0 100 100"><path d="M30 18 Q30 10 38 14 L84 44 Q92 50 84 56 L38 86 Q30 90 30 82 Z" fill="#fff" /></svg>
          </div>
          <div style={{ width: lado * 0.42, height: lado * 0.035, borderRadius: lado, background: T.linea }} />
          <div style={{ width: lado * 0.26, height: lado * 0.035, borderRadius: lado, background: T.linea }} />
        </div>
        {marco > 0 && (
          <div style={{ position: 'absolute', inset: -16 * U, border: `${1.6 * U}px solid rgba(${r},${g},${b},${(0.9 * marco).toFixed(3)})`, borderRadius: 12 * U }}>
            {[[0, 0], [1, 0], [0, 1], [1, 1]].map(([px, py], i) => (
              <div key={i} style={{ position: 'absolute', left: `calc(${px * 100}% - ${6 * U}px)`, top: `calc(${py * 100}% - ${6 * U}px)`, width: 12 * U, height: 12 * U,
                                    background: T.oscuro ? '#1B1E29' : '#fff', border: `${1.6 * U}px solid rgb(${r},${g},${b})`, opacity: marco }} />
            ))}
          </div>
        )}
      </div>
      {o.insignia && ins > 0 && (
        <div style={{ position: 'absolute', right: -lado * 0.18 + (1 - k) * lado * 0.5, top: -lado * 0.16 + (1 - k) * lado * 0.5, padding: `${8 * U}px ${18 * U}px`,
                      borderRadius: 30 * U, background: `rgb(${r},${g},${b})`, color: '#fff', fontFamily: (T.letra || FAMILIA.inter), fontWeight: 700, fontSize: 24 * U,
                      opacity: ins, transform: `scale(${(0.7 + 0.3 * ins).toFixed(3)})`, boxShadow: `0 ${8 * U}px ${18 * U}px rgba(${r},${g},${b},.35)` }}>{o.insignia}</div>
      )}
      {o.insignia && Array.from({ length: 12 }, (_, i) => {                      // motas que se escapan al encoger
        const a = (i / 12) * Math.PI * 2 + 0.4, d = lado * (0.62 + 0.25 * ((i * 37) % 10) / 10) * (0.8 + 0.4 * pe);
        return <div key={i} style={{ position: 'absolute', left: lado / 2 + Math.cos(a) * d, top: lado / 2 + Math.sin(a) * d, width: 5 * U, height: 5 * U, borderRadius: 3 * U,
                                     background: i % 3 ? `rgba(${r},${g},${b},.75)` : TINTA, opacity: pe * (1 - clamp((dt - te - 1.2) / 1.5)) }} />;
      })}
    </div>
  );
};

/* ------------------------------------------------------------------------------------------------ ojo con tarjetas de interfaz */
export const Ojo: React.FC<{ o: Objeto; U: number; acento: string }> = ({ o, U, acento }) => {
  const T = useTema();
  const { dt } = useEntrada(o.t);
  const d = 440 * U, iris = d * 0.44;
  const mx = Math.sin(dt * 0.9) * d * 0.035, my = Math.cos(dt * 0.7) * d * 0.02;
  const [r, g, b] = rgb(acento);
  const c1 = easeOut((dt - 0.45) / 0.4), c2 = easeOut((dt - 0.8) / 0.4);
  return (
    <div style={{ position: 'relative', width: d, height: d }}>
      <div style={{ position: 'absolute', inset: -d * 0.18, borderRadius: '50%', background: `radial-gradient(circle, rgba(${r},${g},${b},.16), rgba(${r},${g},${b},0) 70%)` }} />
      <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', overflow: 'hidden',
                    background: 'radial-gradient(circle at 38% 32%, #FFFFFF 0%, #F6F1EC 38%, #E6D9CF 62%, #C9B2A3 82%, #A88C7C 100%)',
                    boxShadow: `0 ${30 * U}px ${70 * U}px rgba(60,40,30,.25)` }}>
        <svg style={{ position: 'absolute', inset: 0 }} viewBox="0 0 100 100" width={d} height={d}>
          {[[2, 48, 22, 44, 30, 50], [98, 52, 80, 58, 70, 52], [50, 98, 46, 82, 52, 72], [10, 20, 24, 30, 32, 40], [90, 80, 78, 70, 68, 64], [80, 12, 70, 26, 64, 36]].map((p, i) => (
            <path key={i} d={`M${p[0]} ${p[1]} Q${p[2]} ${p[3]} ${p[4]} ${p[5]}`} stroke="rgba(190,60,60,.28)" strokeWidth={0.5} fill="none" />
          ))}
        </svg>
        <div style={{ position: 'absolute', left: d / 2 - iris / 2 + mx, top: d / 2 - iris / 2 + my, width: iris, height: iris, borderRadius: '50%',
                      background: 'repeating-conic-gradient(from 0deg, #2E6F86 0deg 4deg, #5FA4B9 4deg 7deg, #1F5468 7deg 11deg)',
                      boxShadow: `inset 0 0 ${iris * 0.12}px ${iris * 0.06}px rgba(10,30,40,.85)` }}>
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'radial-gradient(circle, rgba(200,170,90,.55) 0%, rgba(200,170,90,0) 42%, rgba(0,0,0,0) 60%, rgba(10,25,35,.55) 100%)' }} />
          <div style={{ position: 'absolute', left: iris * 0.32, top: iris * 0.32, width: iris * 0.36, height: iris * 0.36, borderRadius: '50%', background: '#06080A' }} />
          <div style={{ position: 'absolute', left: iris * 0.56, top: iris * 0.24, width: iris * 0.14, height: iris * 0.14, borderRadius: '50%', background: 'rgba(255,255,255,.85)' }} />
        </div>
      </div>
      <div style={{ position: 'absolute', left: -d * 0.42, top: -d * 0.02, width: d * 0.62, padding: 14 * U, borderRadius: 16 * U, background: T.carta, border: `${1.2 * U}px solid ${T.borde}`, boxShadow: sombra(U, 0.7),
                    opacity: c1, transform: `translateY(${((1 - c1) * 20 * U).toFixed(1)}px) scale(${(0.9 + 0.1 * c1).toFixed(3)})` }}>
        <div style={{ fontFamily: (T.letra || FAMILIA.inter), fontWeight: 700, fontSize: 11 * U, letterSpacing: '0.1em', color: T.gris, marginBottom: 8 * U }}>TIMELINE</div>
        {[0.8, 0.55, 0.7].map((w, i) => (
          <div key={i} style={{ height: 9 * U, width: `${w * 100}%`, marginLeft: `${i * 8}%`, borderRadius: 5 * U, marginBottom: 6 * U, background: i === 1 ? acento : T.linea }} />
        ))}
      </div>
      <div style={{ position: 'absolute', right: -d * 0.36, bottom: d * 0.04, width: d * 0.62, padding: 14 * U, borderRadius: 16 * U, background: T.carta, border: `${1.2 * U}px solid ${T.borde}`, boxShadow: sombra(U, 0.7),
                    opacity: c2, transform: `translateY(${((1 - c2) * 20 * U).toFixed(1)}px) scale(${(0.9 + 0.1 * c2).toFixed(3)})` }}>
        <div style={{ fontFamily: (T.letra || FAMILIA.inter), fontWeight: 700, fontSize: 11 * U, letterSpacing: '0.1em', color: T.gris, marginBottom: 8 * U }}>SOUND FX</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 3 * U, height: 44 * U }}>
          {Array.from({ length: 26 }, (_, i) => (
            <div key={i} style={{ width: 4 * U, borderRadius: 2 * U, background: acento, height: (8 + 34 * Math.abs(Math.sin(i * 1.7 + dt * 6))) * U * (0.4 + 0.6 * Math.abs(Math.sin(i * 0.5))) }} />
          ))}
        </div>
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------------------------------------ barra de uso (segmentos) */
export const Barra: React.FC<{ o: Objeto; U: number; acento: string }> = ({ o, U, acento }) => {
  const T = useTema();
  const { dt } = useEntrada(o.t);
  const n = 10, w = 760 * U, seg = 56 * U, gap = 10 * U;
  const llena = clamp(dt / 0.9) * n;
  const pos = 7 - 4 * easeInOut((dt - 1.0) / 1.4);                          // el bloque marcado baja: «menos es más»
  const [r, g, b] = rgb(acento);
  return (
    <div style={{ width: w, padding: `${22 * U}px ${26 * U}px ${26 * U}px`, borderRadius: 30 * U, background: T.carta, border: `${1.2 * U}px solid ${T.borde}`, boxShadow: sombra(U) }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: (T.letra || FAMILIA.inter), fontWeight: 700, fontSize: 14 * U, letterSpacing: '0.1em', color: T.gris, marginBottom: 16 * U }}>
        <span>{o.etiqueta || 'EFFECT USAGE'}</span><span style={{ color: acento }}>{Math.max(1, Math.round(pos))} / {n}</span>
      </div>
      <div style={{ display: 'flex', gap }}>
        {Array.from({ length: n }, (_, i) => {
          const on = i < llena;
          const marca = Math.max(0, 1 - Math.abs(i - pos));
          return (
            <div key={i} style={{ width: (w - 52 * U - gap * (n - 1)) / n, height: seg * 1.25, borderRadius: 12 * U,
                                  background: marca > 0.01 ? `rgba(${r},${g},${b},${(0.35 + 0.65 * marca).toFixed(3)})` : on ? T.linea : T.suave,
                                  boxShadow: marca > 0.4 ? `0 0 ${24 * U * marca}px rgba(${r},${g},${b},.55)` : undefined, transition: 'none' }} />
          );
        })}
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------------------------------------ tarjeta de precio */
const contar = (valor: string, q: number) => {
  const limpio = String(valor || '').replace(/,/g, '');
  const v = parseFloat(limpio);
  if (!isFinite(v)) return valor;
  const dec = (limpio.split('.')[1] || '').length;
  return (v * q).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
};

const Linea: React.FC<{ w: number; h: number; p: number; acento: string; U: number; sube?: boolean }> = ({ w, h, p, acento, U, sube = true }) => {
  const T = useTema();
  const pts = [0.82, 0.74, 0.78, 0.62, 0.66, 0.5, 0.54, 0.36, 0.3, 0.12].map((y, i, a) => [(i / (a.length - 1)) * w, (sube ? y : 1 - y) * h]);
  const d = pts.map((q, i) => (i ? 'L' : 'M') + q[0].toFixed(1) + ' ' + q[1].toFixed(1)).join(' ');
  const largo = w * 1.6;
  const fin = pts[Math.max(0, Math.min(pts.length - 1, Math.round(p * (pts.length - 1))))];
  const [r, g, b] = rgb(acento);
  return (
    <svg width={w} height={h} style={{ overflow: 'visible' }}>
      <defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={`rgba(${r},${g},${b},.28)`} /><stop offset="1" stopColor={`rgba(${r},${g},${b},0)`} /></linearGradient></defs>
      <path d={d + ` L${w} ${h} L0 ${h} Z`} fill="url(#area)" style={{ clipPath: `inset(0 ${((1 - p) * 100).toFixed(2)}% 0 0)` }} />
      <path d={d} fill="none" stroke={acento} strokeWidth={4 * U} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={largo} strokeDashoffset={largo * (1 - p)} />
      {p > 0.05 && <circle cx={fin[0]} cy={fin[1]} r={8 * U} fill={T.oscuro ? '#1B1E29' : '#fff'} stroke={acento} strokeWidth={4 * U} />}
    </svg>
  );
};

export const Precio: React.FC<{ o: Objeto; U: number; acento: string }> = ({ o, U, acento }) => {
  const T = useTema();
  const { dt } = useEntrada(o.t);
  const q = easeOut((dt - 0.1) / 1.0);
  const w = 640 * U;
  return (
    <div style={{ width: w, padding: 34 * U, borderRadius: 32 * U, background: T.carta, border: `${1.2 * U}px solid ${T.borde}`, boxShadow: sombra(U) }}>
      <div style={{ fontFamily: (T.letra || FAMILIA.inter), fontWeight: 700, fontSize: 14 * U, letterSpacing: '0.12em', color: T.gris }}>TOTAL</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 16 * U }}>
        <div style={{ fontFamily: (T.letra || FAMILIA.inter), fontWeight: 700, fontSize: 92 * U, letterSpacing: '-0.03em', color: T.tinta }}>
          {o.signo || '$'}{o.valor ? contar(o.valor, q) : ''}
        </div>

      </div>
      <div style={{ marginTop: 18 * U }}><Linea w={w - 68 * U} h={150 * U} p={easeInOut((dt - 0.2) / 1.2)} acento={acento} U={U} /></div>
    </div>
  );
};

export const Grafica: React.FC<{ o: Objeto; U: number; acento: string }> = ({ o, U, acento }) => {
  const T = useTema();
  const { dt } = useEntrada(o.t);
  const w = 700 * U;
  const p = easeInOut((dt - 0.15) / 1.3);
  return (
    <div style={{ width: w, padding: 32 * U, borderRadius: 32 * U, background: T.carta, border: `${1.2 * U}px solid ${T.borde}`, boxShadow: sombra(U), position: 'relative' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div style={{ fontFamily: (T.letra || FAMILIA.inter), fontWeight: 700, fontSize: 14 * U, letterSpacing: '0.12em', color: T.gris }}>GROWTH</div>
        {o.valor && <div style={{ fontFamily: FAMILIA.display, fontStyle: 'italic', fontSize: 76 * U, color: acento, opacity: clamp((dt - 0.9) / 0.4) }}>+{contar(o.valor, easeOut((dt - 0.9) / 0.8))}{o.signo}</div>}
      </div>
      <div style={{ marginTop: 14 * U }}><Linea w={w - 64 * U} h={230 * U} p={p} acento={acento} U={U} /></div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10 * U, fontFamily: (T.letra || FAMILIA.inter), fontWeight: 500, fontSize: 14 * U, color: T.gris }}>
        {['Q1', 'Q2', 'Q3', 'Q4'].map(x => <span key={x}>{x}</span>)}
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------------------------------------ reloj */
export const Reloj: React.FC<{ o: Objeto; U: number; acento: string }> = ({ o, U, acento }) => {
  const T = useTema();
  const { dt } = useEntrada(o.t);
  const d = 330 * U, sw = 16 * U, rr = (d - sw) / 2, largo = 2 * Math.PI * rr;
  const p = easeInOut((dt - 0.1) / 1.3);
  return (
    <div style={{ position: 'relative', width: d, height: d, borderRadius: '50%', background: T.carta, border: `${1.2 * U}px solid ${T.borde}`, boxShadow: sombra(U) }}>
      <svg width={d} height={d} style={{ position: 'absolute', inset: 0, transform: 'rotate(-90deg)' }}>
        <circle cx={d / 2} cy={d / 2} r={rr - 14 * U} fill="none" stroke={T.suave} strokeWidth={sw} />
        <circle cx={d / 2} cy={d / 2} r={rr - 14 * U} fill="none" stroke={acento} strokeWidth={sw} strokeLinecap="round" strokeDasharray={largo} strokeDashoffset={largo * (1 - 0.82 * p)} />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ fontFamily: (T.letra || FAMILIA.inter), fontWeight: 700, fontSize: 104 * U, letterSpacing: '-0.04em', color: T.tinta, lineHeight: 1 }}>{contar(o.valor, easeOut((dt - 0.05) / 1.0))}</div>
        <div style={{ fontFamily: (T.letra || FAMILIA.inter), fontWeight: 700, fontSize: 20 * U, letterSpacing: '0.14em', color: T.gris, marginTop: 6 * U }}>{String(o.unidad || '').toUpperCase()}</div>
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------------------------------------ avatares */
const PALETA = [['#FFB199', '#FF6A88'], ['#9AD0FF', '#4C7DFF'], ['#B8F2C0', '#3CC985'], ['#FFE08A', '#F5A524'], ['#D4B8FF', '#8B5CF6']];
export const Avatares: React.FC<{ o: Objeto; U: number; acento: string }> = ({ o, U, acento }) => {
  const T = useTema();
  const { dt } = useEntrada(o.t);
  const d = 132 * U;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 22 * U }}>
      <div style={{ display: 'flex' }}>
        {PALETA.map(([a, b], i) => {
          const e = easeOut((dt - 0.08 * i) / 0.35);
          return (
            <div key={i} style={{ width: d, height: d, marginLeft: i ? -d * 0.28 : 0, borderRadius: '50%', border: `${6 * U}px solid ${T.oscuro ? '#1B1E29' : '#fff'}`, boxShadow: sombra(U, 0.6),
                                  background: `linear-gradient(150deg, ${a}, ${b})`, opacity: e, transform: `translateY(${((1 - e) * 24 * U).toFixed(1)}px) scale(${(0.8 + 0.2 * e).toFixed(3)})`,
                                  display: 'flex', alignItems: 'flex-end', justifyContent: 'center', overflow: 'hidden' }}>
              <div style={{ width: d * 0.5, height: d * 0.5, borderRadius: '50%', background: 'rgba(255,255,255,.55)', marginBottom: -d * 0.12 }} />
            </div>
          );
        })}
        <div style={{ width: d, height: d, marginLeft: -d * 0.28, borderRadius: '50%', border: `${6 * U}px solid ${T.oscuro ? '#1B1E29' : '#fff'}`, background: acento, color: '#fff', boxShadow: sombra(U, 0.6),
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: (T.letra || FAMILIA.inter), fontWeight: 700, fontSize: 32 * U,
                      opacity: easeOut((dt - 0.45) / 0.35) }}>{o.valor ? '+' + contar(String(o.valor), easeOut((dt - 0.45) / 1.0)) : '+'}</div>
      </div>
      {o.etiqueta && <div style={{ fontFamily: (T.letra || FAMILIA.inter), fontWeight: 600, fontSize: 26 * U, color: T.tinta, opacity: easeOut((dt - 0.3) / 0.4) }}>{o.etiqueta}</div>}
    </div>
  );
};

/* ------------------------------------------------------------------------------------------------ calendario */
export const Calendario: React.FC<{ o: Objeto; U: number; acento: string }> = ({ o, U, acento }) => {
  const T = useTema();
  const { dt } = useEntrada(o.t);
  const dias = ['L', 'M', 'X', 'J', 'V', 'S', 'D'];
  const col = Math.max(0, dias.indexOf(o.dia || 'V'));
  const c = 64 * U;
  const mark = easeOut((dt - 0.6) / 0.35);
  return (
    <div style={{ padding: 30 * U, borderRadius: 32 * U, background: T.carta, border: `${1.2 * U}px solid ${T.borde}`, boxShadow: sombra(U) }}>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(7, ${c}px)`, gap: 8 * U }}>
        {dias.map(x => <div key={x} style={{ textAlign: 'center', fontFamily: (T.letra || FAMILIA.inter), fontWeight: 700, fontSize: 15 * U, color: T.gris, letterSpacing: '0.08em' }}>{x}</div>)}
        {Array.from({ length: 35 }, (_, i) => {
          const n = i - 1, sel = Math.floor(i / 7) === 2 && i % 7 === col;
          const e = easeOut((dt - 0.015 * i) / 0.25);
          return (
            <div key={i} style={{ height: c, borderRadius: 14 * U, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: (T.letra || FAMILIA.inter), fontWeight: 600,
                                  fontSize: 22 * U, opacity: n < 1 || n > 30 ? 0 : e, background: sel ? `color-mix(in srgb, ${acento} ${Math.round(mark * 100)}%, #F4F5F8)` : T.suave,
                                  color: sel && mark > 0.5 ? '#fff' : T.tinta, transform: sel ? `scale(${(1 + 0.12 * Math.sin(clamp((dt - 0.6) / 0.5) * Math.PI)).toFixed(3)})` : undefined }}>
              {n >= 1 && n <= 30 ? n : ''}
            </div>
          );
        })}
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------------------------------------ estado: mal / bien */
export const Estado: React.FC<{ o: Objeto; U: number }> = ({ o, U }) => {
  const T = useTema();
  const { dt } = useEntrada(o.t);
  const color = o.bien ? '#18C964' : '#FF3B4D';
  const trazo = easeOut((dt - 0.2) / 0.4);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 22 * U, padding: `${24 * U}px ${36 * U}px ${24 * U}px ${24 * U}px`, borderRadius: 30 * U, background: T.carta, border: `${1.2 * U}px solid ${T.borde}`, boxShadow: sombra(U) }}>
      <div style={{ width: 92 * U, height: 92 * U, borderRadius: '50%', background: `${color}26`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <svg width={50 * U} height={50 * U} viewBox="0 0 50 50">
          {o.bien ? <path d="M10 26 L21 37 L41 14" fill="none" stroke={color} strokeWidth={6} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={60} strokeDashoffset={60 * (1 - trazo)} />
            : <path d="M13 13 L37 37 M37 13 L13 37" fill="none" stroke={color} strokeWidth={6} strokeLinecap="round" strokeDasharray={70} strokeDashoffset={70 * (1 - trazo)} />}
        </svg>
      </div>
      <div style={{ fontFamily: (T.letra || FAMILIA.inter), fontWeight: 700, fontSize: 34 * U, letterSpacing: '0.02em', color: T.tinta }}>{o.etiqueta}</div>
    </div>
  );
};

/* ------------------------------------------------------------------------------------------------ cifra */
export const Cifra: React.FC<{ o: Objeto; U: number; acento: string }> = ({ o, U, acento }) => {
  const T = useTema();
  return (
  <div style={{ textAlign: 'center' }}>
    <div style={{ fontFamily: FAMILIA.display, fontStyle: 'italic', fontSize: 250 * U, lineHeight: 1, color: acento, letterSpacing: '-0.02em' }}>{o.valor}</div>
    {o.etiqueta && <div style={{ fontFamily: (T.letra || FAMILIA.inter), fontWeight: 500, fontSize: 40 * U, color: T.tinta, marginTop: 8 * U }}>{o.etiqueta}</div>}
  </div>
  );
};

/* ------------------------------------------------------------------------------------------------ lista (cada cosa con su check, cuando se nombra) */
export const Lista: React.FC<{ o: Objeto; U: number; acento: string }> = ({ o, U, acento }) => {
  const T = useTema();
  const { dt } = useEntrada(o.t);
  const items: string[] = o.items || [];
  const tiempos: number[] = o.tiempos || items.map((_, i) => i * 0.45);
  return (
    <div style={{ width: 640 * U, padding: `${26 * U}px ${30 * U}px`, borderRadius: 30 * U, background: T.carta, border: `${1.2 * U}px solid ${T.borde}`, boxShadow: sombra(U), display: 'flex', flexDirection: 'column', gap: 16 * U }}>
      {items.map((x, i) => {
        const e = easeOut((dt - (tiempos[i] || 0)) / 0.35);
        const c = easeOut((dt - (tiempos[i] || 0) - 0.15) / 0.3);
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 18 * U, opacity: 0.25 + 0.75 * e, transform: `translateX(${((1 - e) * 18 * U).toFixed(1)}px)` }}>
            <div style={{ width: 40 * U, height: 40 * U, borderRadius: 12 * U, background: c > 0.5 ? acento : T.suave, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width={22 * U} height={22 * U} viewBox="0 0 24 24"><path d="M5 12.5 L10 17 L19 7" fill="none" stroke="#fff" strokeWidth={3.2} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={24} strokeDashoffset={24 * (1 - c)} /></svg>
            </div>
            <div style={{ fontFamily: (T.letra || FAMILIA.inter), fontWeight: 600, fontSize: 34 * U, color: T.tinta }}>{x}</div>
          </div>
        );
      })}
    </div>
  );
};

/* ------------------------------------------------------------------------------------------------ comparación A / B */
export const Comparacion: React.FC<{ o: Objeto; U: number; acento: string }> = ({ o, U, acento }) => {
  const T = useTema();
  const { dt } = useEntrada(o.t);
  const tb = typeof o.t_b === 'number' ? o.t_b : 0.8;
  const ea = easeOut(dt / 0.35), eb = easeOut((dt - tb) / 0.35);
  const tarjeta = (texto: string, e: number, bueno: boolean) => (
    <div style={{ width: 300 * U, padding: `${30 * U}px ${20 * U}px`, borderRadius: 28 * U, background: bueno ? acento : T.carta, boxShadow: sombra(U),
                  opacity: 0.2 + 0.8 * e, transform: `translateY(${((1 - e) * 24 * U).toFixed(1)}px) scale(${(0.92 + 0.08 * e).toFixed(3)})`, textAlign: 'center' }}>
      <div style={{ fontFamily: (T.letra || FAMILIA.inter), fontWeight: 700, fontSize: 13 * U, letterSpacing: '0.14em', color: bueno ? 'rgba(255,255,255,.75)' : GRIS, marginBottom: 10 * U }}>{bueno ? 'B' : 'A'}</div>
      <div style={{ fontFamily: bueno ? FAMILIA.display : (T.letra || FAMILIA.inter), fontStyle: bueno ? 'italic' : 'normal', fontWeight: bueno ? 400 : 700, fontSize: (bueno ? 50 : 38) * U,
                    color: bueno ? '#fff' : T.tinta, lineHeight: 1.05 }}>{texto}</div>
    </div>
  );
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 22 * U }}>
      {tarjeta(o.a, ea, false)}
      <div style={{ fontFamily: (T.letra || FAMILIA.inter), fontWeight: 700, fontSize: 30 * U, color: T.gris, opacity: eb }}>→</div>
      {tarjeta(o.b, eb, true)}
    </div>
  );
};

/* ------------------------------------------------------------------------------------------------ pregunta (encuesta) */
export const Pregunta: React.FC<{ o: Objeto; U: number; acento: string }> = ({ o, U, acento }) => {
  const T = useTema();
  const { dt } = useEntrada(o.t);
  const ops: string[] = o.opciones || [];
  const pct = [62, 38, 21];
  return (
    <div style={{ width: 660 * U, padding: 30 * U, borderRadius: 30 * U, background: T.carta, border: `${1.2 * U}px solid ${T.borde}`, boxShadow: sombra(U) }}>
      <div style={{ fontFamily: (T.letra || FAMILIA.inter), fontWeight: 700, fontSize: 34 * U, color: T.tinta, marginBottom: 20 * U }}>{o.pregunta}</div>
      {ops.map((x, i) => {
        const p = easeOut((dt - 0.5 - i * 0.15) / 0.9) * pct[i % 3];
        return (
          <div key={i} style={{ position: 'relative', height: 70 * U, borderRadius: 18 * U, background: T.suave, marginBottom: 12 * U, overflow: 'hidden' }}>
            <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${p}%`, background: i === 0 ? acento : T.linea, opacity: i === 0 ? 0.9 : 1 }} />
            <div style={{ position: 'absolute', inset: 0, display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: `0 ${22 * U}px`,
                          fontFamily: (T.letra || FAMILIA.inter), fontWeight: 600, fontSize: 28 * U, color: i === 0 && p > 30 ? '#fff' : T.tinta }}>
              <span>{x}</span><span>{Math.round(p)}%</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};
