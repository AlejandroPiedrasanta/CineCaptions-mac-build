// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/Ubicacion.tsx — «estamos en Guatemala»: el mundo en un fondo profundo, la cámara vuela hasta el país, el país se enciende
// con el color del video, cae un pin con ondas y entra la bandera ondeando con el nombre. Mapa: Natural Earth 1:110m (dominio público);
// banderas: flag-icons (MIT).
import { AbsoluteFill, Img, continueRender, delayRender, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { useEffect, useState } from 'react';
import { FAMILIA, Familia, clamp, rgb, useFuentes, useResorte, useU } from './comun';

export type UbicacionProps = { pais: string; nombre?: string; kicker?: string; acento?: string; fondo?: string; fuente?: Familia; salida?: number };
type Pais = { es: string; en: string; pt: string; centro: [number, number]; caja: [number, number, number, number]; d: string };
type Mapa = { ancho: number; alto: number; paises: Record<string, Pais> };

let mapa: Promise<Mapa> | null = null;
export const useMapa = () => {
  const [m, setM] = useState<Mapa | null>(null);
  const [h] = useState(() => delayRender('mapa'));
  useEffect(() => {
    mapa = mapa || fetch(staticFile('mapa/paises.json')).then(r => r.json());
    mapa.then(x => { setM(x); continueRender(h); }).catch(() => continueRender(h));
  }, [h]);
  return m;
};

export const Bandera: React.FC<{ iso: string; ancho: number; t: number }> = ({ iso, ancho, t }) => {
  const alto = ancho * 0.75, n = 22, w = ancho / n;
  return (
    <div style={{ position: 'relative', width: ancho, height: alto * 1.12 }}>
      {Array.from({ length: n }).map((_, i) => {
        const fase = (i / n) * Math.PI * 2 - t * 5.2;
        const amp = alto * 0.045 * (0.25 + 0.75 * (i / n));                     // el lado del mástil casi no se mueve
        return (
          <div key={i} style={{ position: 'absolute', left: i * w, top: alto * 0.06 + Math.sin(fase) * amp, width: w + 0.6, height: alto, overflow: 'hidden',
                                filter: `brightness(${(1 + 0.16 * Math.cos(fase)).toFixed(3)})` }}>
            <Img src={staticFile(`mapa/banderas/${iso}.svg`)} style={{ position: 'absolute', left: -i * w, top: 0, width: ancho, height: alto }} />
          </div>
        );
      })}
    </div>
  );
};

export const Ubicacion: React.FC<UbicacionProps> = ({ pais, nombre, kicker = 'UBICACIÓN', acento = '#c9a46a', fondo = '#0a0f1e', fuente = 'grotesk', salida = 0.4 }) => {
  useFuentes();
  const m = useMapa();
  const frame = useCurrentFrame();
  const { fps, width: W, height: H, durationInFrames } = useVideoConfig();
  const U = useU();
  const S = useResorte();
  const t = frame / fps;
  const fin = durationInFrames / fps;
  const q = clamp((t - (fin - salida)) / salida);                                    // salida
  const [ar, ag, ab] = rgb(acento);
  const iso = (pais || '').toLowerCase();
  const p = m?.paises[iso];
  const vertical = H > W;
  // la zona del mapa: arriba en vertical, a la izquierda en horizontal
  const mapW = vertical ? W : W * 0.62, mapH = vertical ? H * 0.58 : H;
  const zoom = S(0.25, { damping: 20, stiffness: 70 });
  let vb = [0, 0, 1000, 1000 * mapH / mapW];
  vb[1] = 250 - vb[3] / 2;
  if (p) {
    const [x0, y0, x1, y1] = p.caja;
    const vw = Math.max(70, Math.min(700, (x1 - x0) * 2.6, (y1 - y0) * 2.6 * mapW / mapH));
    const vh = vw * mapH / mapW;
    const fin2 = [p.centro[0] - vw / 2, p.centro[1] - vh / 2 - vh * 0.08, vw, vh];
    vb = vb.map((v, i) => v + (fin2[i] - v) * clamp(zoom, 0, 1.04));
  }
  const luz = S(0.9, { damping: 16 });
  const pin = S(1.05, { damping: 9, stiffness: 180 });
  const carta = S(1.25, { damping: 15, stiffness: 140 });
  const nombreTxt = (nombre || p?.es || iso.toUpperCase()).toUpperCase();
  const entra = interpolate(t, [0, 0.35], [0, 1], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ opacity: 1 - q, transform: `scale(${1 - 0.04 * q})` }}>
      <AbsoluteFill style={{ background: `radial-gradient(120% 80% at 50% 35%, rgba(${ar},${ag},${ab},0.22), rgba(${ar},${ag},${ab},0) 60%), ${fondo}`,   // base OPACA debajo
                             clipPath: `circle(${(entra * 140).toFixed(2)}% at 50% 108%)` }}>
        {/* haz de luz diagonal, como en las referencias */}
        <AbsoluteFill style={{ background: `linear-gradient(115deg, transparent 30%, rgba(${ar},${ag},${ab},0.10) 48%, transparent 62%)`,
                               transform: `translateX(${Math.sin(t * 0.6) * 6}%)` }} />
        <svg width={mapW} height={mapH} viewBox={vb.map(v => v.toFixed(2)).join(' ')} style={{ position: 'absolute', left: 0, top: vertical ? H * 0.04 : 0 }}>
          <defs>
            <filter id="brillo" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation={Math.max(0.6, vb[2] / 160)} result="b" />
              <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>
          {m && Object.entries(m.paises).map(([k, v]) => (
            <path key={k} d={v.d} fill={k === iso ? 'none' : 'rgba(255,255,255,0.07)'} stroke="rgba(255,255,255,0.16)" strokeWidth={vb[2] / 900} />
          ))}
          {p && <path d={p.d} fill={`rgba(${ar},${ag},${ab},${(0.85 * clamp(luz)).toFixed(3)})`} stroke={acento} strokeWidth={vb[2] / 300}
                      filter="url(#brillo)" />}
          {p && [0, 0.45, 0.9].map((o, i) => {
            const r = ((t - 1.1 - o) % 1.35 + 1.35) % 1.35;                           // ondas que salen del pin
            return t > 1.1 + o ? <circle key={i} cx={p.centro[0]} cy={p.centro[1]} r={(vb[2] / 18) * r} fill="none" stroke={acento}
                                         strokeWidth={vb[2] / 400} opacity={(1 - r / 1.35) * 0.8} /> : null;
          })}
        </svg>
        {p && (() => {                                                                // el pin, en píxeles de pantalla
          const px = (p.centro[0] - vb[0]) / vb[2] * mapW, py = (p.centro[1] - vb[1]) / vb[3] * mapH + (vertical ? H * 0.04 : 0);
          const tam = 90 * U;
          return (
            <svg width={tam} height={tam * 1.3} viewBox="0 0 24 31" style={{ position: 'absolute', left: px - tam / 2, top: py - tam * 1.3 - (1 - clamp(pin, 0, 1.2)) * 260 * U,
                                                                          opacity: clamp(pin * 3), filter: `drop-shadow(0 ${10 * U}px ${14 * U}px rgba(0,0,0,.5))` }}>
              <path d="M12 0C5.4 0 0 5.2 0 11.7 0 20.4 12 31 12 31s12-10.6 12-19.3C24 5.2 18.6 0 12 0z" fill={acento} />
              <circle cx="12" cy="11.5" r="4.6" fill="#fff" />
            </svg>
          );
        })()}
        {/* la ficha con la bandera y el nombre */}
        <div style={{ position: 'absolute', left: vertical ? W / 2 : W * 0.81, top: vertical ? H * 0.69 : H * 0.5,
                      transform: `translate(-50%, -50%) translateY(${((1 - carta) * 180 * U).toFixed(1)}px)`, opacity: clamp(carta * 2),
                      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 26 * U }}>
          <div style={{ fontFamily: FAMILIA.mono, fontSize: 30 * U, letterSpacing: '0.32em', color: acento }}>{(kicker || '').toUpperCase()}</div>
          <div style={{ padding: 14 * U, borderRadius: 22 * U, background: 'rgba(255,255,255,0.06)', border: `${2 * U}px solid rgba(${ar},${ag},${ab},0.55)`,
                        boxShadow: `0 ${30 * U}px ${80 * U}px rgba(0,0,0,.45), 0 0 ${60 * U}px rgba(${ar},${ag},${ab},0.25)` }}>
            <Bandera iso={iso} ancho={(vertical ? 360 : 300) * U} t={t} />
          </div>
          <div style={{ fontFamily: FAMILIA[fuente] || FAMILIA.grotesk, fontWeight: 700, fontSize: Math.min(140 * U, (vertical ? W * 0.9 : W * 0.34) / Math.max(4, nombreTxt.length) * 1.7),
                        color: '#fff', letterSpacing: '0.02em', textShadow: `0 ${8 * U}px ${30 * U}px rgba(0,0,0,.5)` }}>{nombreTxt}</div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
