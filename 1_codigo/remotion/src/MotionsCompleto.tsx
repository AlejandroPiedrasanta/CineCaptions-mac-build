// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/MotionsCompleto.tsx — v5.5.8 «Motions completo»: UN video de motions a pantalla completa para TODO el video (pedido del
// usuario, con referencias de videos explicativos: cada frase ilustrada con tipografía, fotos del tema, iconos, cifras, listas, precios). Va en
// PRO-MOTIONS, encima de todo; el usuario lo corta para que se vea su video debajo. Las escenas y su orden los decide motions_completo.py.
//   escenas: [{ini, fin, tipo: 'tipografia'|'foto'|'icono'|'objeto', fondo: 'claro'|'oscuro'|'acento', palabras: [{t, texto, clave}], titulo, foto,
//              icono (3D de iconos3d/), emoji (stickers/), objeto (uno de Objetos.tsx)}] · frases: [{ini, fin, texto}] (la frase pequeña de abajo)
import React from 'react';
import { AbsoluteFill, Img, Sequence, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { FAMILIA, clamp, rgb, useFuentes, useResorte } from './comun';
import {
  App, Avatares, Barra, Calendario, Cifra, Comparacion, Estado, Ficha, Grafica, Lista, Muestra, Objeto, Ojo, Precio, Pregunta, Reloj, TEMA_CLARO,
  TEMA_OSCURO, TemaCtx,
} from './Objetos';

type PalabraMC = { t: number; texto: string; clave?: boolean };
type EscenaMC = {
  ini: number; fin: number; tipo: string; fondo?: 'claro' | 'oscuro' | 'acento'; palabras?: PalabraMC[]; titulo?: string; foto?: string;
  icono?: string; emoji?: string; objeto?: Objeto;
};
type FraseMC = { ini: number; fin: number; texto: string };
export type MotionsProps = { escenas?: EscenaMC[]; frases?: FraseMC[]; acento?: string; subtitulos?: boolean };

const easeOut = (q: number) => 1 - Math.pow(1 - clamp(q), 3);
// los objetos pequeños (un estado, una ficha, una muestra de color) se ven más grandes a pantalla completa
const ESCALA_MC: Record<string, number> = { estado: 2.1, ficha: 1.9, muestra: 1.7, app: 1.55, ojo: 1.35, avatares: 1.4, reloj: 1.3, cifra: 1.25 };

const colores = (fondo: string, acento: string) => {
  const [r, g, b] = rgb(acento);
  if (fondo === 'oscuro') return { fondo: `radial-gradient(120% 80% at 50% 35%, #1B1E2B 0%, #0A0B10 70%)`, tinta: '#F5F6FA', suave: 'rgba(255,255,255,.55)', clave: acento,
                                   trama: 'rgba(255,255,255,.035)', oscuro: true };
  if (fondo === 'acento') return { fondo: `linear-gradient(160deg, rgb(${r},${g},${b}) 0%, rgb(${Math.round(r * 0.55)},${Math.round(g * 0.55)},${Math.round(b * 0.55)}) 100%)`,
                                   tinta: '#FFFFFF', suave: 'rgba(255,255,255,.75)', clave: '#FFFFFF', trama: 'rgba(255,255,255,.06)', oscuro: true };
  return { fondo: 'radial-gradient(120% 80% at 50% 30%, #FFFFFF 0%, #ECEEF3 75%)', tinta: '#15161B', suave: 'rgba(20,22,30,.55)', clave: acento,
           trama: 'rgba(20,30,60,.04)', oscuro: false };
};

/* la escena entra con un resorte (sube y se asienta) y en su último cuarto de segundo se va hacia arriba */
const Entrada: React.FC<{ dur: number; children: React.ReactNode }> = ({ dur, children }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const t = frame / fps;
  const r = useResorte()(0, { damping: 16, stiffness: 170 });
  const sal = easeOut((t - (dur - 0.22)) / 0.22);
  return (
    <AbsoluteFill style={{ opacity: clamp(r * 1.6) * (1 - sal), transform: `translateY(${((1 - r) * height * 0.03 - sal * height * 0.025).toFixed(1)}px) scale(${(0.94 + 0.06 * r + 0.02 * sal).toFixed(4)})` }}>
      {children}
    </AbsoluteFill>
  );
};

const Fondo: React.FC<{ c: ReturnType<typeof colores> }> = ({ c }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: c.fondo }}>
      <AbsoluteFill style={{ backgroundImage: `linear-gradient(${c.trama} 1px, transparent 1px), linear-gradient(90deg, ${c.trama} 1px, transparent 1px)`,
                             backgroundSize: '72px 72px', backgroundPosition: `0 ${(frame * 0.4) % 72}px` }} />
    </AbsoluteFill>
  );
};

/* tipografía cinética: las palabras entran cuando se DICEN; la clave, enorme y en el acento (como «Struggling / TO TURN VIEWS») */
const Tipografia: React.FC<{ e: EscenaMC; c: ReturnType<typeof colores> }> = ({ e, c }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const t = frame / fps;
  const U = width / 1080;
  const ps = (e.palabras || []).slice(0, 14);
  const k = Math.max(0, ps.findIndex(p => p.clave));
  const antes = ps.slice(Math.max(0, k - 5), k), clave = ps[k], despues = ps.slice(k + 1, k + 6);
  const grande = clave ? Math.min(250 * U, (width * 0.88) / Math.max(3, clave.texto.length * 0.5)) : 0;
  const palabra = (p: PalabraMC, tam: number, estilo: React.CSSProperties) => {
    const q = easeOut((t - p.t + 0.08) / 0.32);
    return <span key={`${p.t}${p.texto}`} style={{ display: 'inline-block', margin: `0 ${tam * 0.14}px`, opacity: clamp(q * 1.4),
                                                   transform: `translateY(${((1 - q) * tam * 0.45).toFixed(1)}px)`, filter: q < 1 ? `blur(${((1 - q) * 6).toFixed(1)}px)` : 'none',
                                                   ...estilo }}>{p.texto}</span>;
  };
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', padding: `0 ${60 * U}px`, textAlign: 'center' }}>
      <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 66 * U, color: c.tinta, lineHeight: 1.1, maxWidth: width * 0.9 }}>
        {antes.map(p => palabra(p, 66 * U, {}))}
      </div>
      {clave && <div style={{ fontFamily: FAMILIA.condensada, fontSize: grande, lineHeight: 0.95, color: c.clave, textTransform: 'uppercase', letterSpacing: '-0.01em',
                              textShadow: c.oscuro ? `0 0 ${40 * U}px ${c.clave}55` : 'none', margin: `${10 * U}px 0` }}>{palabra(clave, grande, {})}</div>}
      <div style={{ fontFamily: FAMILIA.inter, fontWeight: 600, fontSize: 56 * U, color: c.suave, lineHeight: 1.15, maxWidth: width * 0.9 }}>
        {despues.map(p => palabra(p, 56 * U, {}))}
      </div>
    </AbsoluteFill>
  );
};

/* foto de internet del tema a pantalla completa, con un zoom lento y el titular arriba */
const Foto: React.FC<{ e: EscenaMC; c: ReturnType<typeof colores> }> = ({ e, c }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const U = width / 1080;
  const dur = Math.max(0.5, e.fin - e.ini);
  const z = 1.14 - 0.12 * clamp(frame / fps / dur);
  const q = easeOut((frame / fps - 0.15) / 0.4);
  return (
    <AbsoluteFill style={{ background: '#000' }}>
      {e.foto && <Img src={e.foto} style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${z.toFixed(4)})` }} />}
      <AbsoluteFill style={{ background: 'linear-gradient(180deg, rgba(0,0,0,.55) 0%, rgba(0,0,0,0) 38%, rgba(0,0,0,0) 62%, rgba(0,0,0,.6) 100%)' }} />
      {e.titulo && <div style={{ position: 'absolute', top: '13%', left: 0, right: 0, textAlign: 'center', padding: `0 ${50 * U}px`, fontFamily: FAMILIA.condensada,
                                 fontSize: Math.min(150 * U, (width * 0.9) / Math.max(4, e.titulo.length * 0.48)), color: '#fff', textTransform: 'uppercase', lineHeight: 0.95,
                                 textShadow: `0 ${6 * U}px ${30 * U}px rgba(0,0,0,.5)`, opacity: q, transform: `translateY(${((1 - q) * 40 * U).toFixed(1)}px)` }}>{e.titulo}</div>}
    </AbsoluteFill>
  );
};

/* el icono 3D (o el emoji) del concepto, flotando con su resplandor y unas copias pequeñas alrededor */
const Icono: React.FC<{ e: EscenaMC; c: ReturnType<typeof colores>; acento: string }> = ({ e, c, acento }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;
  const U = width / 1080;
  const src = e.icono ? staticFile(`iconos3d/${e.icono}.png`) : e.emoji ? staticFile(`stickers/rcs_emoji_${e.emoji}.png`) : '';
  const r = useResorte()(0.05, { damping: 11, stiffness: 140 });
  const [ar, ag, ab] = rgb(acento);
  const lado = 470 * U;
  const flota = Math.sin(t * 1.7) * 14 * U;
  const copias = [[-0.33, -0.3, 0.42], [0.34, -0.22, 0.34], [-0.36, 0.2, 0.3], [0.32, 0.28, 0.4]];
  return (
    <AbsoluteFill>
      {src && copias.map(([x, y, s], i) => (
        <Img key={i} src={src} style={{ position: 'absolute', width: lado * s, height: lado * s, objectFit: 'contain', left: width * (0.5 + x) - lado * s / 2,
                                         top: height * (0.42 + y) - lado * s / 2 + Math.sin(t * 1.3 + i) * 18 * U, opacity: 0.22 * clamp(r), filter: `blur(${2 * U}px)`,
                                         transform: `rotate(${(i % 2 ? 1 : -1) * 14}deg)` }} />
      ))}
      <div style={{ position: 'absolute', left: width / 2 - lado * 0.75, top: height * 0.42 - lado * 0.75, width: lado * 1.5, height: lado * 1.5, borderRadius: '50%',
                    background: `radial-gradient(circle, rgba(${ar},${ag},${ab},${c.oscuro ? 0.45 : 0.22}) 0%, rgba(${ar},${ag},${ab},0) 65%)`, opacity: clamp(r) }} />
      {src && <Img src={src} style={{ position: 'absolute', width: lado, height: lado, objectFit: 'contain', left: width / 2 - lado / 2, top: height * 0.42 - lado / 2 + flota,
                                      transform: `scale(${(0.6 + 0.4 * r).toFixed(4)})`, filter: `drop-shadow(0 ${30 * U}px ${40 * U}px rgba(0,0,0,${c.oscuro ? 0.5 : 0.22}))` }} />}
      {e.titulo && <div style={{ position: 'absolute', top: height * 0.42 + lado * 0.62, left: 0, right: 0, textAlign: 'center', fontFamily: FAMILIA.inter, fontWeight: 800,
                                 fontSize: Math.min(110 * U, (width * 0.86) / Math.max(4, e.titulo.length * 0.58)), color: c.tinta, letterSpacing: '-0.02em',
                                 opacity: clamp((t - 0.3) / 0.3), transform: `translateY(${((1 - easeOut((t - 0.3) / 0.4)) * 30 * U).toFixed(1)}px)` }}>{e.titulo}</div>}
    </AbsoluteFill>
  );
};

/* un objeto de Objetos.tsx (precio, gráfica, reloj, lista, cifra…), centrado y grande, con el tema del fondo */
const ObjetoMC: React.FC<{ e: EscenaMC; c: ReturnType<typeof colores>; acento: string }> = ({ e, c, acento }) => {
  const { width } = useVideoConfig();
  const U = width / 1080;
  const o = e.objeto as Objeto;
  const C: Record<string, React.ReactNode> = {
    precio: <Precio o={o} U={U} acento={acento} />, grafica: <Grafica o={o} U={U} acento={acento} />, reloj: <Reloj o={o} U={U} acento={acento} />,
    avatares: <Avatares o={o} U={U} acento={acento} />, calendario: <Calendario o={o} U={U} acento={acento} />, estado: <Estado o={o} U={U} />,
    cifra: <Cifra o={o} U={U} acento={acento} />, lista: <Lista o={o} U={U} acento={acento} />, comparacion: <Comparacion o={o} U={U} acento={acento} />,
    pregunta: <Pregunta o={o} U={U} acento={acento} />, ficha: <Ficha o={o} U={U} />, app: <App o={o} U={U} acento={acento} />, ojo: <Ojo o={o} U={U} acento={acento} />,
    barra: <Barra o={o} U={U} acento={acento} />, muestra: <Muestra o={o} U={U} />,
  };
  return (
    <TemaCtx.Provider value={c.oscuro ? TEMA_OSCURO : TEMA_CLARO}>
      <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
        {e.titulo && <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 64 * U, color: c.tinta, marginBottom: 46 * U, textAlign: 'center',
                                   padding: `0 ${60 * U}px`, letterSpacing: '-0.02em' }}>{e.titulo}</div>}
        <div style={{ transform: `scale(${(o && ESCALA_MC[o.tipo]) || 1.18})` }}>{o ? C[o.tipo] || null : null}</div>
      </AbsoluteFill>
    </TemaCtx.Provider>
  );
};

const Escena: React.FC<{ e: EscenaMC; acento: string }> = ({ e, acento }) => {
  const c = colores(e.fondo || 'claro', acento);
  const dur = Math.max(0.3, e.fin - e.ini);
  let cuerpo: React.ReactNode;
  if (e.tipo === 'foto' && e.foto) cuerpo = <Foto e={e} c={c} />;
  else if (e.tipo === 'icono' && (e.icono || e.emoji)) cuerpo = <Icono e={e} c={c} acento={acento} />;
  else if (e.tipo === 'objeto' && e.objeto) cuerpo = <ObjetoMC e={e} c={c} acento={acento} />;
  else cuerpo = <Tipografia e={e} c={c} />;
  return (
    <AbsoluteFill>
      {e.tipo !== 'foto' && <Fondo c={c} />}
      <Entrada dur={dur}>{cuerpo}</Entrada>
    </AbsoluteFill>
  );
};

/* la frase que se dice, pequeña y abajo (como en las referencias); su color sigue al fondo de la escena de ese momento */
const Frases: React.FC<{ frases: FraseMC[]; escenas: EscenaMC[] }> = ({ frases, escenas }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;
  const U = width / 1080;
  const f = frases.find(x => x.ini - 0.05 <= t && t < x.fin + 0.15);
  if (!f) return null;
  const e = escenas.find(x => x.ini <= t && t < x.fin);
  const claro = e && (e.fondo || 'claro') === 'claro' && e.tipo !== 'foto';
  const q = clamp((t - f.ini + 0.05) / 0.15) * (1 - clamp((t - f.fin - 0.05) / 0.12));
  return (
    <div style={{ position: 'absolute', left: 0, right: 0, top: height * 0.86, display: 'flex', justifyContent: 'center', opacity: q }}>
      <div style={{ maxWidth: width * 0.84, textAlign: 'center', fontFamily: FAMILIA.inter, fontWeight: 600, fontSize: 34 * U, lineHeight: 1.25,
                    color: claro ? '#1D1E24' : '#FFFFFF', textShadow: claro ? 'none' : `0 ${2 * U}px ${10 * U}px rgba(0,0,0,.6)` }}>{f.texto}</div>
    </div>
  );
};

export const MotionsCompleto: React.FC<MotionsProps> = ({ escenas = [], frases = [], acento = '#4C7DFF', subtitulos = true }) => {
  useFuentes();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: '#0A0B10' }}>
      {escenas.map((e, i) => (
        <Sequence key={i} from={Math.round(e.ini * fps)} durationInFrames={Math.max(1, Math.round((e.fin - e.ini) * fps))}>
          <Escena e={e} acento={acento} />
        </Sequence>
      ))}
      {subtitulos && <Frases frases={frases} escenas={escenas} />}
    </AbsoluteFill>
  );
};
