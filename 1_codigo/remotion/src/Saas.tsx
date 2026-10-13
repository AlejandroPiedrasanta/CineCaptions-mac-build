// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/Saas.tsx — plantillas estilo «SaaS» (interfaz de producto: vidrio, degradados, brillo) para negocios y servicios, junto a los
// captions de cualquier Tema: Notificacion (llega un aviso tipo iPhone), Tarjeta (tarjeta de vidrio con icono 3D, título y barra de progreso),
// Grafica (curva que sube con su número), Pasos (1 · 2 · 3 con check) e Interruptor (un toggle que se enciende: «Modo PRO»).
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { FAMILIA, clamp, rgb, useFuentes, useResorte, useU } from './comun';

type Base = { acento?: string; y?: number; escala?: number; salida?: number; icono3d?: string };
const usarSalida = (t: number, fin: number, salida = 0.35) => clamp((t - (fin - salida)) / salida);
const vidrio = (U: number, acento: string, alfa = 0.5): React.CSSProperties => {
  const [r, g, b] = rgb(acento);
  return { background: `linear-gradient(160deg, rgba(255,255,255,0.16), rgba(255,255,255,0.04)), rgba(10,12,24,${alfa})`, backdropFilter: 'blur(14px)',
           border: `${1.5 * U}px solid rgba(255,255,255,0.22)`, boxShadow: `0 ${24 * U}px ${60 * U}px rgba(0,0,0,.45), 0 0 ${50 * U}px rgba(${r},${g},${b},0.25)` };
};
const useT = () => {
  const { fps, durationInFrames } = useVideoConfig();
  return { fps, fin: durationInFrames / fps };
};

/* ------------------------------------------------------------------------------------------------ Notificación */
export type NotificacionProps = Base & { app?: string; titulo?: string; texto?: string; hora?: string };
export const Notificacion: React.FC<NotificacionProps> = ({ app = 'CINECAPTIONS', titulo = '¡Nueva reserva!', texto = 'Ana y Luis reservaron su fecha', hora = 'ahora',
                                                             acento = '#5B8CFF', icono3d = 'bell-dynamic-color', y = 14, escala = 1, salida = 0.35 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte(), frame = useCurrentFrame(), { fps, fin } = useT();
  const t = frame / fps, q = usarSalida(t, fin, salida);
  const p = S(0.05, { damping: 14, stiffness: 170 });
  const ancho = Math.min(W * 0.9, 900 * U);
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <div style={{ position: 'absolute', left: W / 2, top: H * y / 100, width: ancho, transform: `translate(-50%,-50%) translateY(${((1 - clamp(p, 0, 1.1)) * -220 * U - q * 40 * U).toFixed(1)}px)`,
                    borderRadius: 34 * U, padding: `${24 * U}px ${28 * U}px`, display: 'flex', gap: 22 * U, alignItems: 'center', ...vidrio(U, acento, 0.62) }}>
        <div style={{ width: 96 * U, height: 96 * U, borderRadius: 24 * U, background: `linear-gradient(135deg, ${acento}, #111)`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Img src={staticFile(`iconos3d/${icono3d}.png`)} style={{ width: 80 * U, height: 80 * U, transform: `rotate(${(Math.sin(t * 8) * 12 * clamp(1.4 - t)).toFixed(1)}deg)` }} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: FAMILIA.grotesk, fontSize: 24 * U, color: 'rgba(255,255,255,.7)', letterSpacing: '0.08em' }}>
            <span>{app}</span><span>{hora}</span></div>
          <div style={{ fontFamily: FAMILIA.grotesk, fontWeight: 700, fontSize: 40 * U, color: '#fff', marginTop: 4 * U }}>{titulo}</div>
          <div style={{ fontFamily: FAMILIA.grotesk, fontSize: 32 * U, color: 'rgba(255,255,255,.85)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{texto}</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ Tarjeta de vidrio con progreso */
export type TarjetaProps = Base & { kicker?: string; titulo?: string; texto?: string; progreso?: number; boton?: string };
export const Tarjeta: React.FC<TarjetaProps> = ({ kicker = 'PAQUETE', titulo = 'Boda completa', texto = 'Foto + video + dron', progreso = 100, boton = 'Reservar',
                                                   acento = '#7C5CFF', icono3d = 'camera-dynamic-premium', y = 30, escala = 1, salida = 0.35 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte(), frame = useCurrentFrame(), { fps, fin } = useT();
  const t = frame / fps, q = usarSalida(t, fin, salida);
  const p = S(0.05, { damping: 15 }), ic = S(0.35, { damping: 9, stiffness: 170 });
  const barra = clamp(interpolate(t, [0.6, 1.6], [0, progreso / 100], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }));
  const ancho = Math.min(W * 0.82, 760 * U);
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <div style={{ position: 'absolute', left: W / 2, top: H * y / 100, width: ancho, transform: `translate(-50%,-50%) translateY(${((1 - clamp(p)) * 90 * U).toFixed(1)}px) scale(${(0.94 + 0.06 * clamp(p)).toFixed(3)})`,
                    borderRadius: 40 * U, padding: 40 * U, display: 'flex', flexDirection: 'column', gap: 18 * U, ...vidrio(U, acento) }}>
        <Img src={staticFile(`iconos3d/${icono3d}.png`)} style={{ position: 'absolute', right: -30 * U, top: -70 * U, width: 200 * U, height: 200 * U,
                                                                  transform: `scale(${Math.max(0.001, ic).toFixed(3)}) rotate(${(Math.sin(t * 1.6) * 6).toFixed(1)}deg)`,
                                                                  filter: `drop-shadow(0 ${16 * U}px ${24 * U}px rgba(0,0,0,.45))` }} />
        <div style={{ fontFamily: FAMILIA.mono, fontSize: 26 * U, letterSpacing: '0.24em', color: acento }}>{kicker}</div>
        <div style={{ fontFamily: FAMILIA.grotesk, fontWeight: 700, fontSize: 64 * U, color: '#fff', lineHeight: 1.05 }}>{titulo}</div>
        <div style={{ fontFamily: FAMILIA.grotesk, fontSize: 34 * U, color: 'rgba(255,255,255,.8)' }}>{texto}</div>
        <div style={{ height: 14 * U, borderRadius: 14 * U, background: 'rgba(255,255,255,.14)', overflow: 'hidden', marginTop: 8 * U }}>
          <div style={{ width: `${(barra * 100).toFixed(1)}%`, height: '100%', borderRadius: 14 * U, background: `linear-gradient(90deg, ${acento}, #fff)`, boxShadow: `0 0 ${16 * U}px ${acento}` }} /></div>
        {boton && <div style={{ alignSelf: 'flex-start', marginTop: 10 * U, padding: `${16 * U}px ${34 * U}px`, borderRadius: 999, background: '#fff', color: '#111',
                                fontFamily: FAMILIA.grotesk, fontWeight: 700, fontSize: 32 * U, transform: `scale(${(1 + 0.05 * Math.sin(t * 6) * clamp(t - 1.6)).toFixed(3)})`,
                                boxShadow: `0 0 ${30 * U}px ${acento}` }}>{boton}</div>}
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ Gráfica que sube */
export type GraficaProps = Base & { titulo?: string; valor?: string; subtitulo?: string };
export const Grafica: React.FC<GraficaProps> = ({ titulo = 'Reservas', valor = '+240%', subtitulo = 'este año', acento = '#3DDC97', y = 30, escala = 1, salida = 0.35 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte(), frame = useCurrentFrame(), { fps, fin } = useT();
  const t = frame / fps, q = usarSalida(t, fin, salida);
  const p = S(0.05, { damping: 15 });
  const dib = clamp(interpolate(t, [0.4, 1.6], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }));
  const ancho = Math.min(W * 0.84, 800 * U), alto = 420 * U;
  const pts = [0.08, 0.14, 0.12, 0.26, 0.22, 0.4, 0.36, 0.58, 0.7, 0.92];
  const d = pts.map((v, i) => `${i ? 'L' : 'M'}${(i / (pts.length - 1)) * 100},${(1 - v) * 100}`).join(' ');
  const num = Math.round(parseFloat(valor.replace(/[^\d.]/g, '')) * clamp(dib * 1.1) || 0);
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <div style={{ position: 'absolute', left: W / 2, top: H * y / 100, width: ancho, transform: `translate(-50%,-50%) translateY(${((1 - clamp(p)) * 80 * U).toFixed(1)}px)`,
                    borderRadius: 36 * U, padding: 36 * U, ...vidrio(U, acento) }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
          <div style={{ fontFamily: FAMILIA.grotesk, fontWeight: 600, fontSize: 36 * U, color: 'rgba(255,255,255,.85)' }}>{titulo}</div>
          <div style={{ fontFamily: FAMILIA.redonda, fontWeight: 800, fontSize: 72 * U, color: acento, textShadow: `0 0 ${24 * U}px ${acento}` }}>
            {valor.startsWith('+') ? '+' : ''}{num}{valor.includes('%') ? '%' : ''}</div>
        </div>
        <svg width="100%" height={alto} viewBox="0 0 100 100" preserveAspectRatio="none" style={{ marginTop: 10 * U, overflow: 'visible' }}>
          <defs><linearGradient id="relleno" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor={acento} stopOpacity="0.45" /><stop offset="1" stopColor={acento} stopOpacity="0" /></linearGradient></defs>
          {[25, 50, 75].map(v => <line key={v} x1="0" x2="100" y1={v} y2={v} stroke="rgba(255,255,255,.12)" strokeWidth="0.4" />)}
          <path d={`${d} L100,100 L0,100 Z`} fill="url(#relleno)" style={{ clipPath: `inset(0 ${((1 - dib) * 100).toFixed(2)}% 0 0)` }} />
          <path d={d} fill="none" stroke={acento} strokeWidth="1.4" vectorEffect="non-scaling-stroke" pathLength={1} strokeDasharray={`${dib} 1`}
                style={{ filter: `drop-shadow(0 0 6px ${acento})` }} />
        </svg>
        <div style={{ fontFamily: FAMILIA.mono, fontSize: 24 * U, letterSpacing: '0.2em', color: 'rgba(255,255,255,.6)', marginTop: 10 * U }}>{subtitulo.toUpperCase()}</div>
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ Pasos 1 · 2 · 3 */
export type PasosProps = Base & { pasos?: string; titulo?: string };
export const Pasos: React.FC<PasosProps> = ({ pasos = 'Agenda,Sesión,Entrega', titulo = 'Así trabajamos', acento = '#FF8A3D', y = 30, escala = 1, salida = 0.35 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte(), frame = useCurrentFrame(), { fps, fin } = useT();
  const t = frame / fps, q = usarSalida(t, fin, salida);
  const lista = pasos.split(',').map(x => x.trim()).filter(Boolean).slice(0, 4);
  const ancho = Math.min(W * 0.86, 820 * U);
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <div style={{ position: 'absolute', left: W / 2, top: H * y / 100, width: ancho, transform: 'translate(-50%,-50%)', borderRadius: 36 * U, padding: 36 * U,
                    display: 'flex', flexDirection: 'column', gap: 22 * U, ...vidrio(U, acento), opacity: clamp(S(0.05) * 2) }}>
        <div style={{ fontFamily: FAMILIA.grotesk, fontWeight: 700, fontSize: 48 * U, color: '#fff' }}>{titulo}</div>
        {lista.map((p, i) => {
          const e = S(0.35 + i * 0.35, { damping: 14 }), ok = clamp((t - (0.75 + i * 0.35)) * 4);
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 22 * U, opacity: clamp(e * 2), transform: `translateX(${((1 - clamp(e)) * 60 * U).toFixed(1)}px)` }}>
              <div style={{ width: 64 * U, height: 64 * U, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: FAMILIA.grotesk,
                            fontWeight: 700, fontSize: 32 * U, color: ok > 0.5 ? '#111' : '#fff', background: ok > 0.5 ? acento : 'rgba(255,255,255,.12)',
                            border: `${2 * U}px solid ${acento}`, boxShadow: ok > 0.5 ? `0 0 ${22 * U}px ${acento}` : 'none' }}>{ok > 0.5 ? '✓' : i + 1}</div>
              <div style={{ fontFamily: FAMILIA.grotesk, fontWeight: 600, fontSize: 40 * U, color: '#fff' }}>{p}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ Interruptor («Modo PRO») */
export type InterruptorProps = Base & { texto?: string; sub?: string };
export const Interruptor: React.FC<InterruptorProps> = ({ texto = 'Modo PRO', sub = 'activado', acento = '#22D3EE', y = 22, escala = 1, salida = 0.35 }) => {
  useFuentes();
  const { width: W, height: H } = useVideoConfig();
  const U = useU() * escala, S = useResorte(), frame = useCurrentFrame(), { fps, fin } = useT();
  const t = frame / fps, q = usarSalida(t, fin, salida);
  const p = S(0.05, { damping: 14 }), on = S(0.7, { damping: 12, stiffness: 200 });
  const [r, g, b] = rgb(acento);
  return (
    <AbsoluteFill style={{ opacity: 1 - q }}>
      <div style={{ position: 'absolute', left: W / 2, top: H * y / 100, transform: `translate(-50%,-50%) scale(${(0.9 + 0.1 * clamp(p)).toFixed(3)})`, opacity: clamp(p * 2),
                    display: 'flex', alignItems: 'center', gap: 30 * U, padding: `${26 * U}px ${36 * U}px`, borderRadius: 999, ...vidrio(U, acento) }}>
        <div style={{ position: 'relative', width: 150 * U, height: 82 * U, borderRadius: 999, background: `rgba(${r},${g},${b},${(0.15 + 0.85 * clamp(on)).toFixed(3)})`,
                      boxShadow: `0 0 ${40 * U * clamp(on)}px ${acento}` }}>
          <div style={{ position: 'absolute', top: 7 * U, left: 7 * U + clamp(on, 0, 1.08) * 68 * U, width: 68 * U, height: 68 * U, borderRadius: '50%', background: '#fff',
                        boxShadow: '0 4px 12px rgba(0,0,0,.35)' }} />
        </div>
        <div>
          <div style={{ fontFamily: FAMILIA.grotesk, fontWeight: 700, fontSize: 52 * U, color: '#fff', lineHeight: 1 }}>{texto}</div>
          <div style={{ fontFamily: FAMILIA.mono, fontSize: 24 * U, letterSpacing: '0.2em', color: acento, opacity: clamp(on) }}>{sub.toUpperCase()}</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
