// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/MotionsCompleto.tsx — v5.5.8 «Motions completo»: UN video de SOLO motions a pantalla completa para TODO el video. Va en
// PRO-MOTIONS, encima de todo; el usuario lo corta para que se vea su video debajo. Qué motion va en cada tramo lo decide motions_completo.py.
// Segundo pedido del usuario: «demasiados captions, no hay animaciones ni iconos… usa todos los motions, gráficos, píldoras, iconos, fotos y
// videos del tema, explicaciones visuales». Así que aquí NO hay texto de la frase: cada tramo es uno de
//   'comp'      una pieza del kit (Kit7/Kit8), una escena a pantalla completa (Escenas9) o una plantilla (Plantillas/Saas), con sus props
//   'objeto'    un dato de Objetos.tsx (precio, gráfica, reloj, lista, cifra, comparación, ficha…)
//   'pildoras'  2–4 píldoras con icono animado (lo que se nombra)          'diagrama'  A → B → C con iconos y flechas que se dibujan
//   'icono'     el icono animado (Lottie) grande con su palabra              'foto' / 'video'  la foto o el video del tema con un rótulo corto
// fondos: 'oscuro' | 'acento' | 'claro' | 'foto' (la foto del tema, desenfocada). Entre tramos, un barrido del color de acento.
import React from 'react';
import { AbsoluteFill, Img, OffthreadVideo, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { FAMILIA, clamp, rgb, useFuentes, useResorte } from './comun';
import { EmojiAnimado } from './Emoji';
import {
  App, Avatares, Barra, Calendario, Cifra, Comparacion, Estado, Ficha, Grafica, Lista, Muestra, Objeto, Ojo, Precio, Pregunta, Reloj, TEMA_CLARO,
  TEMA_OSCURO, TemaCtx,
} from './Objetos';
import { AbanicoK, ConceptoK, ListaRazonesK, MisterioK, MixtoK, RuedaK, RutaK, TituloNeonK } from './Kit7';
import { CalendarioK, RecorteK, RedNeonK, SeleccionK } from './Kit8';
import { ChatE, CollageE, CuadernoE, FechaE, FotoE, MovilE, PictogramaE, PolaroidE, TableroE, TijerasE, VidrioE } from './Escenas9';
import { Capitulos, Comentario, Encuesta, Fecha, Ninas, Pareja, Pastilla, Saludo, Sesion, Titulo } from './Plantillas';
import { Grafica as GraficaS, Interruptor, Notificacion, Pasos, Tarjeta } from './Saas';
import { Pictos3DE } from './Pictos3D';
import { ConectoresMC, ContadorMC, Cosa as CosaW, OrbitaMC, PalabraT, RutaMC, VersionesMC, tema as temaW } from './Widgets';
import { AntesDespuesW, ArchivosW, AvisoW, BuscadorW, BuscarW, CargaW, ChatW, CompartirW, CortarW, CuentaW, EncuestaW, EntradaW, FechaW, GolpeW, GraficaW,
         IdeasW, LargoW, ListaW, LugarW, MovilW, MusicaW, NotaW, PalabraR, PersonasW, PostW, PremioW, RTitular, RecW, RelojW, VersionesW } from './Reel';

type Ic = { emoji?: string; img?: string };
type Cosa = { texto: string; icono?: Ic };
type EscenaMC = {
  ini: number; fin: number; tipo: string; fondo?: 'claro' | 'oscuro' | 'acento' | 'foto'; fondo_foto?: number; titulo?: string; foto?: number;
  video?: string; inicio?: number; icono?: Ic; objeto?: Objeto; comp?: string; props?: Record<string, unknown>; pantalla?: boolean;
  items?: Cosa[]; nodos?: Cosa[];
  // v5.5.9: el titular de lo que se dice (palabra a palabra) y los widgets (órbita, ruta, conectores, contador, versiones)
  // v5.5.9 estilo reel: tipo 'reel' + reel (rec, reloj, archivos, buscar, cortar, largo, movil, chat, abc, ideas) + wp (sus textos); arriba = píldora
  reel?: string; wp?: Record<string, any>; arriba?: string;
  // v5.5.9 contra la repetición: el color de la tarjeta, de qué lado entra, el fotograma del video (índice en fotos) y desde cuándo la cámara se acerca
  paleta?: string; lado?: number; img?: number; empuje?: number;
  titular?: (PalabraT & { estilo?: PalabraR['estilo'] })[]; centro?: CosaW; pasos?: CosaW[]; entradas?: CosaW[]; opciones?: CosaW[]; resultado?: CosaW; cartas?: CosaW[];
  valor?: number; sufijo?: string; prefijo?: string; etiqueta?: string;
};
export type TitularMC = { ini: number; fin: number; titular?: (PalabraT & { estilo?: PalabraR['estilo'] })[]; arriba?: string };
export type MotionsProps = { escenas?: EscenaMC[]; fotos?: string[]; acento?: string; tema?: 'claro' | 'oscuro'; titulares?: TitularMC[] };

// las piezas que se pueden incrustar a pantalla completa (mismos nombres que en Root.tsx)
const COMPS: Record<string, React.FC<any>> = {
  ListaRazonesK, MisterioK, RuedaK, AbanicoK, RutaK, TituloNeonK, ConceptoK, MixtoK, RecorteK, SeleccionK, CalendarioK, RedNeonK, PictogramaE, TableroE,
  PolaroidE, CuadernoE, FechaE, VidrioE, ChatE, CollageE, MovilE, TijerasE, FotoE, Titulo, Saludo, Capitulos, Fecha, Pareja, Pastilla, Encuesta,
  Comentario, Sesion, Ninas, Notificacion, Tarjeta, Grafica: GraficaS, Pasos, Interruptor, Pictos3DE,
};

const easeOut = (q: number) => 1 - Math.pow(1 - clamp(q), 3);
// los objetos pequeños (un estado, una ficha, una muestra de color) se ven más grandes a pantalla completa
const ESCALA_MC: Record<string, number> = { estado: 2.1, ficha: 1.9, muestra: 1.7, app: 1.55, ojo: 1.35, avatares: 1.4, reloj: 1.3, cifra: 1.25 };

type Colores = { fondo: string; tinta: string; suave: string; clave: string; trama: string; oscuro: boolean; vidrio: string; borde: string };
const colores = (fondo: string, acento: string): Colores => {
  const [r, g, b] = rgb(acento);
  if (fondo === 'claro') return { fondo: 'radial-gradient(130% 90% at 50% 18%, #FFFFFF 0%, #F2F2F9 48%, #E4E5F3 100%)', tinta: '#15161B', suave: 'rgba(20,22,30,.6)', clave: acento,
                                  trama: 'rgba(20,30,60,.045)', oscuro: false, vidrio: 'rgba(255,255,255,.92)', borde: 'rgba(20,30,60,.08)' };
  if (fondo === 'acento') return { fondo: `linear-gradient(160deg, rgb(${r},${g},${b}) 0%, rgb(${Math.round(r * 0.45)},${Math.round(g * 0.45)},${Math.round(b * 0.45)}) 100%)`,
                                   tinta: '#FFFFFF', suave: 'rgba(255,255,255,.8)', clave: '#FFFFFF', trama: 'rgba(255,255,255,.07)', oscuro: true,
                                   vidrio: 'rgba(255,255,255,.16)', borde: 'rgba(255,255,255,.28)' };
  return { fondo: 'radial-gradient(120% 80% at 50% 35%, #1B1E2B 0%, #08090D 72%)', tinta: '#F5F6FA', suave: 'rgba(255,255,255,.6)', clave: acento,
           trama: 'rgba(255,255,255,.035)', oscuro: true, vidrio: 'rgba(255,255,255,.08)', borde: 'rgba(255,255,255,.16)' };
};

/* el icono: emoji animado (Lottie si lo hay, si no su PNG 3D) o una imagen del paquete (recorte de revista, icono 3D) */
const Icono3: React.FC<{ ic?: Ic; lado: number; style?: React.CSSProperties }> = ({ ic, lado, style }) => {
  if (!ic) return null;
  if (ic.emoji) return <EmojiAnimado id={ic.emoji} lado={lado} style={style} />;
  if (ic.img) return <Img src={staticFile(ic.img)} style={{ width: lado, height: lado, objectFit: 'contain', ...style }} />;
  return null;
};

/* el fondo: degradado con dos manchas de luz que se mueven despacio y una trama; o la foto del tema, desenfocada y oscurecida */
const Fondo: React.FC<{ c: Colores; acento: string; foto?: string }> = ({ c, acento, foto }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;
  const [r, g, b] = rgb(acento);
  if (foto) {
    return (
      <AbsoluteFill style={{ background: '#05060A', overflow: 'hidden' }}>
        <Img src={foto} style={{ position: 'absolute', inset: -60, width: width + 120, height: height + 120, objectFit: 'cover', filter: 'blur(38px) saturate(1.25) brightness(.42)',
                                 transform: `scale(${(1.12 + 0.04 * Math.sin(t * 0.4)).toFixed(4)})` }} />
        <AbsoluteFill style={{ background: `radial-gradient(90% 60% at 50% 45%, rgba(${r},${g},${b},.18) 0%, rgba(0,0,0,0) 70%)` }} />
      </AbsoluteFill>
    );
  }
  const m = Math.min(width, height);
  const mancha = (x: number, y: number, s: number, a: number) => (
    <div style={{ position: 'absolute', left: x - s / 2, top: y - s / 2, width: s, height: s, borderRadius: '50%',
                  background: `radial-gradient(circle, rgba(${r},${g},${b},${a}) 0%, rgba(${r},${g},${b},0) 68%)` }} />
  );
  return (
    <AbsoluteFill style={{ background: c.fondo, overflow: 'hidden' }}>
      {!c.oscuro && mancha(width * (0.2 + 0.06 * Math.sin(t * 0.4)), height * (0.18 + 0.04 * Math.cos(t * 0.35)), m * 1.3, 0.1)}
      {!c.oscuro && mancha(width * (0.85 + 0.05 * Math.cos(t * 0.3)), height * (0.8 + 0.04 * Math.sin(t * 0.33)), m * 1.2, 0.08)}
      {c.oscuro && mancha(width * (0.25 + 0.08 * Math.sin(t * 0.5)), height * (0.28 + 0.05 * Math.cos(t * 0.4)), m * 1.1, c.clave === '#FFFFFF' ? 0.0 : 0.22)}
      {c.oscuro && mancha(width * (0.78 + 0.06 * Math.cos(t * 0.45)), height * (0.72 + 0.05 * Math.sin(t * 0.35)), m * 0.9, c.clave === '#FFFFFF' ? 0.0 : 0.16)}
      <AbsoluteFill style={{ backgroundImage: `linear-gradient(${c.trama} 1px, transparent 1px), linear-gradient(90deg, ${c.trama} 1px, transparent 1px)`,
                             backgroundSize: '72px 72px', backgroundPosition: `0 ${(frame * 0.4) % 72}px` }} />
    </AbsoluteFill>
  );
};

/* un rótulo corto (1–3 palabras) con su barra de acento que se dibuja */
const Rotulo: React.FC<{ texto: string; acento: string; top: number; t0?: number }> = ({ texto, acento, top, t0 = 0.25 }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const U = width / 1080;
  const t = frame / fps;
  const q = easeOut((t - t0) / 0.42);
  const barra = easeOut((t - t0 - 0.12) / 0.4);
  const tam = Math.min(150 * U, (width * 0.9) / Math.max(4, texto.length * 0.5));
  return (
    <div style={{ position: 'absolute', top, left: 0, right: 0, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <div style={{ fontFamily: FAMILIA.condensada, fontSize: tam, color: '#fff', textTransform: 'uppercase', lineHeight: 0.95, textAlign: 'center', padding: `0 ${50 * U}px`,
                    textShadow: `0 ${6 * U}px ${30 * U}px rgba(0,0,0,.55)`, opacity: q, transform: `translateY(${((1 - q) * 40 * U).toFixed(1)}px)`,
                    clipPath: `inset(0 ${((1 - q) * 100).toFixed(1)}% 0 0)` }}>{texto}</div>
      <div style={{ marginTop: 18 * U, height: 12 * U, width: Math.min(width * 0.6, tam * texto.length * 0.42) * barra, background: acento, borderRadius: 6 * U,
                    boxShadow: `0 0 ${30 * U}px ${acento}` }} />
    </div>
  );
};

/* foto del tema: a pantalla completa con un zoom lento y paneo, o (una de cada dos) en tarjeta sobre su copia desenfocada */
const FotoMC: React.FC<{ e: EscenaMC; src?: string; acento: string; n: number }> = ({ e, src, acento, n }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const U = width / 1080;
  const dur = Math.max(0.5, e.fin - e.ini);
  const p = clamp(frame / fps / dur);
  const tarjeta = n % 2 === 1;
  const r = useResorte()(0.05, { damping: 15, stiffness: 120 });
  if (!src) return null;
  if (tarjeta) {
    const w = width * 0.8, h = height * (height > width ? 0.52 : 0.62);
    return (
      <AbsoluteFill>
        <Fondo c={colores('oscuro', acento)} acento={acento} foto={src} />
        <div style={{ position: 'absolute', left: (width - w) / 2, top: height * 0.4 - h / 2, width: w, height: h, borderRadius: 40 * U, overflow: 'hidden',
                      boxShadow: `0 ${40 * U}px ${90 * U}px rgba(0,0,0,.55)`, border: `${6 * U}px solid rgba(255,255,255,.9)`,
                      transform: `translateY(${((1 - r) * 120 * U).toFixed(1)}px) rotate(${((1 - r) * -6 + Math.sin(p * 3) * 0.6).toFixed(2)}deg) scale(${(0.9 + 0.1 * r).toFixed(4)})` }}>
          <Img src={src} style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${(1.1 - 0.08 * p).toFixed(4)})` }} />
        </div>
        {e.titulo && <Rotulo texto={e.titulo} acento={acento} top={height * 0.4 + h / 2 + 60 * U} t0={0.35} />}
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{ background: '#000', overflow: 'hidden' }}>
      <Img src={src} style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${(1.16 - 0.12 * p).toFixed(4)}) translateX(${((p - 0.5) * 3).toFixed(2)}%)` }} />
      <AbsoluteFill style={{ background: 'linear-gradient(180deg, rgba(0,0,0,.6) 0%, rgba(0,0,0,0) 34%, rgba(0,0,0,0) 60%, rgba(0,0,0,.65) 100%)' }} />
      {e.titulo && <Rotulo texto={e.titulo} acento={acento} top={height * 0.11} />}
    </AbsoluteFill>
  );
};

/* video del tema (stock, Pexels/Pixabay): a pantalla completa, sin sonido, con su rótulo */
const VideoMC: React.FC<{ e: EscenaMC; acento: string }> = ({ e, acento }) => {
  const { fps, height } = useVideoConfig();
  if (!e.video) return null;
  return (
    <AbsoluteFill style={{ background: '#000' }}>
      <OffthreadVideo src={e.video} muted startFrom={Math.round((e.inicio || 0) * fps)} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      <AbsoluteFill style={{ background: 'linear-gradient(180deg, rgba(0,0,0,.55) 0%, rgba(0,0,0,0) 32%, rgba(0,0,0,0) 62%, rgba(0,0,0,.55) 100%)' }} />
      {e.titulo && <Rotulo texto={e.titulo} acento={acento} top={height * 0.11} />}
    </AbsoluteFill>
  );
};

/* las píldoras: lo que se nombra (lugares, personas, cosas), cada una con su icono animado, entran una a una y flotan */
const PildorasMC: React.FC<{ e: EscenaMC; c: Colores; acento: string }> = ({ e, c, acento }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const U = Math.min(width, height) / 1080;
  const t = frame / fps;
  const resorte = useResorte();
  const items = (e.items || []).slice(0, 4);
  const vertical = height > width;
  const k = vertical ? (items.length <= 2 ? 1.5 : 1.3) : 1.1;               // a pantalla completa, grandes: se leen de un vistazo
  const [r, g, b] = rgb(acento);
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ display: 'flex', flexDirection: vertical ? 'column' : 'row', flexWrap: 'wrap', gap: 40 * U * k, alignItems: 'center', justifyContent: 'center',
                    maxWidth: width * 0.92 }}>
        {items.map((it, i) => {
          const q = resorte(0.12 + i * 0.22, { damping: 12, stiffness: 150 });
          const flota = Math.sin(t * 1.6 + i * 1.3) * 8 * U;
          const lado = 118 * U * k;
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 26 * U * k, padding: `${22 * U * k}px ${46 * U * k}px ${22 * U * k}px ${22 * U * k}px`, borderRadius: 999,
                                  background: c.vidrio, border: `${2 * U}px solid ${c.borde}`, boxShadow: c.oscuro ? `0 ${20 * U}px ${50 * U}px rgba(0,0,0,.35), inset 0 0 ${30 * U}px rgba(${r},${g},${b},.18)`
                                                                                             : `0 ${18 * U}px ${44 * U}px rgba(20,30,60,.14)`,
                                  opacity: clamp(q * 1.5), transform: `translateY(${((1 - q) * 60 * U + flota).toFixed(1)}px) scale(${(0.7 + 0.3 * q).toFixed(4)}) rotate(${((1 - q) * (i % 2 ? 4 : -4)).toFixed(2)}deg)` }}>
              <div style={{ width: lado, height: lado, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                            background: `radial-gradient(circle at 35% 30%, rgba(${r},${g},${b},.95), rgba(${Math.round(r * 0.5)},${Math.round(g * 0.5)},${Math.round(b * 0.5)},.95))` }}>
                {it.icono ? <Icono3 ic={it.icono} lado={lado * 0.74} /> : <div style={{ fontFamily: FAMILIA.inter, fontWeight: 900, fontSize: 56 * U, color: '#fff' }}>{i + 1}</div>}
              </div>
              <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 58 * U * k, color: c.tinta, letterSpacing: '-0.02em', whiteSpace: 'nowrap' }}>{it.texto}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* el diagrama: A → B (→ C), cada nodo con su icono en un círculo; las flechas se dibujan entre uno y otro */
const DiagramaMC: React.FC<{ e: EscenaMC; c: Colores; acento: string }> = ({ e, c, acento }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const U = Math.min(width, height) / 1080;
  const t = frame / fps;
  const resorte = useResorte();
  const nodos = (e.nodos || []).slice(0, 3);
  const vertical = height > width;
  const n = nodos.length;
  const lado = (n === 3 ? 250 : 300) * U;
  const paso = vertical ? Math.min(height * 0.27, 520 * U) : Math.min(width * 0.3, 620 * U);
  const pos = (i: number) => {
    const d = (i - (n - 1) / 2) * paso;
    return vertical ? { x: width / 2, y: height * 0.47 + d } : { x: width / 2 + d, y: height * 0.46 };
  };
  const [r, g, b] = rgb(acento);
  return (
    <AbsoluteFill>
      <svg width={width} height={height} style={{ position: 'absolute', inset: 0 }}>
        <defs>
          <marker id="mcFlecha" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill={acento} />
          </marker>
        </defs>
        {nodos.slice(1).map((_, i) => {
          const a = pos(i), z = pos(i + 1);
          const k = (lado / 2 + 26 * U) / Math.hypot(z.x - a.x, z.y - a.y);
          const x1 = a.x + (z.x - a.x) * k, y1 = a.y + (z.y - a.y) * k, x2 = z.x - (z.x - a.x) * k, y2 = z.y - (z.y - a.y) * k;
          const largo = Math.hypot(x2 - x1, y2 - y1);
          const q = easeOut((t - 0.5 - i * 0.75) / 0.42);
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={acento} strokeWidth={12 * U} strokeLinecap="round" markerEnd={q > 0.9 ? 'url(#mcFlecha)' : undefined}
                       strokeDasharray={largo} strokeDashoffset={largo * (1 - q)} style={{ filter: `drop-shadow(0 0 ${14 * U}px rgba(${r},${g},${b},.8))` }} />;
        })}
      </svg>
      {nodos.map((nd, i) => {
        const p = pos(i);
        const q = resorte(0.12 + i * 0.75, { damping: 11, stiffness: 150 });
        const pulso = 1 + 0.03 * Math.sin(t * 2.2 + i);
        return (
          <div key={i} style={{ position: 'absolute', left: p.x - lado / 2, top: p.y - lado / 2, width: lado, height: lado, opacity: clamp(q * 1.6),
                                transform: `scale(${((0.4 + 0.6 * q) * pulso).toFixed(4)})` }}>
            <div style={{ width: lado, height: lado, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: c.vidrio,
                          border: `${8 * U}px solid ${acento}`, boxShadow: `0 0 ${50 * U}px rgba(${r},${g},${b},.45), 0 ${24 * U}px ${50 * U}px rgba(0,0,0,${c.oscuro ? 0.4 : 0.15})` }}>
              {nd.icono ? <Icono3 ic={nd.icono} lado={lado * 0.62} /> : <div style={{ fontFamily: FAMILIA.inter, fontWeight: 900, fontSize: lado * 0.36, color: c.clave }}>{i + 1}</div>}
            </div>
            <div style={{ position: 'absolute', top: vertical ? lado * 0.5 - 30 * U : lado + 22 * U, left: vertical ? lado + 30 * U : -lado * 0.4,
                          width: vertical ? width * 0.42 : lado * 1.8, textAlign: vertical ? 'left' : 'center', fontFamily: FAMILIA.inter, fontWeight: 800,
                          fontSize: 54 * U, color: c.tinta, letterSpacing: '-0.02em', lineHeight: 1.05 }}>{nd.texto}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

/* el icono animado (Lottie) del concepto, grande, con un anillo que gira, destellos y su palabra en una píldora del acento */
const IconoMC: React.FC<{ e: EscenaMC; c: Colores; acento: string }> = ({ e, c, acento }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const U = Math.min(width, height) / 1080;
  const t = frame / fps;
  const r = useResorte()(0.05, { damping: 10, stiffness: 140 });
  const [ar, ag, ab] = rgb(acento);
  const lado = 500 * U;
  const cy = height * 0.42;
  const flota = Math.sin(t * 1.7) * 14 * U;
  const q = easeOut((t - 0.35) / 0.4);
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: width / 2 - lado * 0.85, top: cy - lado * 0.85, width: lado * 1.7, height: lado * 1.7, borderRadius: '50%',
                    background: `radial-gradient(circle, rgba(${ar},${ag},${ab},${c.oscuro ? 0.5 : 0.25}) 0%, rgba(${ar},${ag},${ab},0) 65%)`, opacity: clamp(r) }} />
      <div style={{ position: 'absolute', left: width / 2 - lado * 0.66, top: cy - lado * 0.66, width: lado * 1.32, height: lado * 1.32, borderRadius: '50%',
                    border: `${5 * U}px dashed rgba(${ar},${ag},${ab},.7)`, transform: `rotate(${(t * 24).toFixed(2)}deg) scale(${(0.6 + 0.4 * r).toFixed(4)})`, opacity: clamp(r) }} />
      {[0, 1, 2, 3, 4, 5].map(i => {
        const ang = (i / 6) * Math.PI * 2 + t * 0.6;
        const d = lado * (0.78 + 0.04 * Math.sin(t * 2 + i));
        const s = (10 + (i % 3) * 5) * U;
        return <div key={i} style={{ position: 'absolute', left: width / 2 + Math.cos(ang) * d - s / 2, top: cy + Math.sin(ang) * d - s / 2, width: s, height: s,
                                     borderRadius: '50%', background: i % 2 ? '#fff' : acento, opacity: 0.8 * clamp(r), boxShadow: `0 0 ${16 * U}px ${acento}` }} />;
      })}
      <div style={{ position: 'absolute', left: width / 2 - lado / 2, top: cy - lado / 2 + flota, transform: `scale(${(0.5 + 0.5 * r).toFixed(4)})`,
                    filter: `drop-shadow(0 ${30 * U}px ${40 * U}px rgba(0,0,0,${c.oscuro ? 0.5 : 0.22}))` }}>
        <Icono3 ic={e.icono} lado={lado} />
      </div>
      {e.titulo && (
        <div style={{ position: 'absolute', top: cy + lado * 0.68, left: 0, right: 0, display: 'flex', justifyContent: 'center', opacity: q,
                      transform: `translateY(${((1 - q) * 40 * U).toFixed(1)}px) scale(${(0.85 + 0.15 * q).toFixed(4)})` }}>
          <div style={{ padding: `${18 * U}px ${48 * U}px`, borderRadius: 999, background: acento, color: '#fff', fontFamily: FAMILIA.inter, fontWeight: 900,
                        fontSize: Math.min(84 * U, (width * 0.8) / Math.max(4, e.titulo.length * 0.6)), letterSpacing: '-0.01em', textTransform: 'uppercase',
                        boxShadow: `0 ${16 * U}px ${40 * U}px rgba(${ar},${ag},${ab},.45)` }}>{e.titulo}</div>
        </div>
      )}
    </AbsoluteFill>
  );
};

/* un objeto de Objetos.tsx (precio, gráfica, reloj, lista, cifra…), centrado y grande, con el tema del fondo */
const ObjetoMC: React.FC<{ e: EscenaMC; c: Colores; acento: string }> = ({ e, c, acento }) => {
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
        <div style={{ transform: `scale(${(o && ESCALA_MC[o.tipo]) || 1.18})` }}>{o ? C[o.tipo] || null : null}</div>
      </AbsoluteFill>
    </TemaCtx.Provider>
  );
};

/* ---------------------------------------------------------------------------------------------------------------------------------------------
   LAS TRANSICIONES — aprendidas de los reels de referencia (minuto 3:03–3:22 de «ChatGPT vs Claude Motion Graphics»), a 10 fotogramas por segundo:
   · el FONDO no cambia nunca (uno por video: lavanda claro tipo Apple, u oscuro) y el TITULAR se queda arriba;
   · lo que sale se cubre con un VELO esmerilado: se desenfoca, se desvanece en el fondo y se encoge un poco (SAL s, solapado con lo que entra);
   · lo nuevo entra DESDE ABAJO con desenfoque de movimiento, más pequeño y un poco girado, se pasa un poco y se ASIENTA (resorte con rebote);
   · las palabras del titular viejo se difuminan y las nuevas entran una a una cuando se dicen (la clave en cursiva del acento o en píldora);
   · todo es una TARJETA sobre ese fondo (las fotos, los videos y las piezas de pantalla completa también) y, dentro del tramo, flota. */
const SAL = 0.3;

const FondoTema: React.FC<{ claro: boolean; acento: string }> = ({ claro, acento }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;
  const U = Math.min(width, height) / 1080;
  const [r, g, b] = rgb(acento);
  const m = Math.min(width, height);
  const mancha = (x: number, y: number, s: number, c: string) => (
    <div style={{ position: 'absolute', left: x - s / 2, top: y - s / 2, width: s, height: s, borderRadius: '50%', background: `radial-gradient(circle, ${c} 0%, rgba(0,0,0,0) 68%)` }} />
  );
  return (
    <AbsoluteFill style={{ background: claro ? 'radial-gradient(130% 90% at 50% 18%, #FFFFFF 0%, #F3F2FA 46%, #E6E3F4 100%)'
                                             : 'radial-gradient(120% 85% at 50% 30%, #17142A 0%, #0A0912 60%, #050409 100%)', overflow: 'hidden' }}>
      {mancha(width * (0.5 + 0.05 * Math.sin(t * 0.3)), height * (0.5 + 0.03 * Math.cos(t * 0.25)), m * 1.25, `rgba(${r},${g},${b},${claro ? 0.13 : 0.22})`)}
      {mancha(width * (0.15 + 0.04 * Math.cos(t * 0.27)), height * (0.12 + 0.03 * Math.sin(t * 0.31)), m * 1.1, claro ? 'rgba(190,175,255,.22)' : 'rgba(120,80,255,.16)')}
      {mancha(width * (0.88 + 0.03 * Math.sin(t * 0.22)), height * (0.86 + 0.03 * Math.cos(t * 0.29)), m * 1.1, claro ? 'rgba(170,190,255,.2)' : 'rgba(60,90,255,.14)')}
      <AbsoluteFill style={{ backgroundImage: `radial-gradient(${claro ? 'rgba(70,80,140,.13)' : 'rgba(255,255,255,.07)'} ${2 * U}px, transparent ${2.2 * U}px)`,
                             backgroundSize: `${34 * U}px ${34 * U}px`, backgroundPosition: `0 ${(-t * 6 * U).toFixed(1)}px` }} />
    </AbsoluteFill>
  );
};

/* la vida de un tramo: entra desde abajo (desenfoque de movimiento, giro, resorte con rebote), flota y, al acabar, se va bajo el velo */
const Vida: React.FC<{ dur: number; lado?: number; empuje?: number; children: React.ReactNode }> = ({ dur, lado = 0, empuje, children }) => {
  const frame = useCurrentFrame();
  const { fps, height: H, width: W } = useVideoConfig();
  const U = Math.min(W, H) / 1080;
  const t = frame / fps;
  const conf = { damping: 13, stiffness: 115, mass: 0.9 };
  const s = spring({ frame, fps, config: conf });
  const s0 = spring({ frame: Math.max(0, frame - 1), fps, config: conf });
  const vel = Math.abs(s - s0) * fps;                                  // la velocidad: de ahí el desenfoque de movimiento
  const q = easeOut((t - dur) / SAL);                                  // el velo de salida
  const blur = Math.min(18, vel * 9) + q * 16;
  const y = (1 - s) * H * (lado ? 0.24 : 0.42) + Math.sin(t * 1.25) * 7 * U - q * H * 0.03;
  const x = (1 - s) * W * 0.32 * lado;                                 // v5.5.9: unas entran desde abajo a la izquierda o a la derecha
  const rot = (1 - s) * (lado ? 7 * lado : -6) + Math.sin(t * 0.9) * 0.45;
  const acerca = typeof empuje === 'number' ? 0.12 * easeOut((t - empuje) / 1.6) : 0;   // la misma tarjeta sigue y la cámara se acerca
  const sc = (0.84 + 0.16 * s) * (1 - 0.05 * q) * (1 + acerca);
  return (
    <AbsoluteFill style={{ transform: `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) rotate(${rot.toFixed(3)}deg) scale(${sc.toFixed(4)})`, opacity: clamp(s * 2.2) * (1 - q),
                           filter: blur > 0.4 ? `blur(${blur.toFixed(1)}px)` : undefined }}>
      {children}
    </AbsoluteFill>
  );
};

/* el titular de un tramo: entra palabra a palabra (Titular) y, al cambiar de tramo, se difumina hacia arriba */
const TitularVida: React.FC<{ palabras: (PalabraT & { estilo?: PalabraR['estilo'] })[]; arriba?: string; dur: number; claro: boolean }> = ({ palabras, arriba, dur, claro }) => {
  const frame = useCurrentFrame();
  const { fps, height: H, width: W } = useVideoConfig();
  const q = easeOut((frame / fps - dur) / 0.22);
  return (
    <AbsoluteFill style={{ opacity: 1 - q, filter: q > 0.02 ? `blur(${(q * 12).toFixed(1)}px)` : undefined, transform: `translateY(${(-q * H * 0.015).toFixed(1)}px)` }}>
      <RTitular palabras={palabras.map(p => ({ t: p.t, texto: p.texto, estilo: p.estilo || (p.clave ? 'clave' : undefined) }))} arriba={arriba} claro={claro} top={H * (H > W ? 0.15 : 0.08)} />
    </AbsoluteFill>
  );
};

/* una tarjeta grande y redondeada sobre el fondo: dentro va la pieza a pantalla completa (foto, video, escena, kit), escalada a su ancho */
const TarjetaMC: React.FC<{ oscura?: boolean; children: React.ReactNode }> = ({ oscura = true, children }) => {
  const { width: W, height: H } = useVideoConfig();
  const U = Math.min(W, H) / 1080;
  const vertical = H > W;
  const cw = W * (vertical ? 0.86 : 0.58), ch = H * (vertical ? 0.64 : 0.74);
  const k = Math.max(cw / W, ch / H);
  return (
    <div style={{ position: 'absolute', left: (W - cw) / 2, top: H * (vertical ? 0.57 : 0.56) - ch / 2, width: cw, height: ch, borderRadius: 64 * U, overflow: 'hidden',
                  background: oscura ? '#0B0B12' : '#FFFFFF', boxShadow: `0 ${40 * U}px ${110 * U}px rgba(30,30,80,.28), 0 ${8 * U}px ${24 * U}px rgba(30,30,80,.12)`,
                  border: `${3 * U}px solid rgba(255,255,255,.75)` }}>
      <div style={{ position: 'absolute', left: (cw - W * k) / 2, top: (ch - H * k) / 2, width: W, height: H, transform: `scale(${k.toFixed(5)})`, transformOrigin: '0 0' }}>
        {children}
      </div>
    </div>
  );
};

const REEL: Record<string, React.FC<any>> = { rec: RecW, reloj: RelojW, archivos: ArchivosW, buscar: BuscarW, cortar: CortarW, largo: LargoW, movil: MovilW,
                                              chat: ChatW, abc: VersionesW, ideas: IdeasW, fecha: FechaW, lugar: LugarW, entrada: EntradaW,
                                              personas: PersonasW, musica: MusicaW, premio: PremioW, compartir: CompartirW, aviso: AvisoW,
                                              lista: ListaW, buscador: BuscadorW, post: PostW, encuesta: EncuestaW, carga: CargaW, nota: NotaW,
                                              antesdespues: AntesDespuesW, cuenta: CuentaW, grafica: GraficaW, golpe: GolpeW };
const PALETAS: Record<string, [string, string, string]> = {
  azul: ['#2F5BE7', '#7B5CF5', '#ECE8FF'], naranja: ['#F26B1D', '#FF9A62', '#FFF0E6'], morado: ['#7B5CF5', '#B79CFF', '#F0EBFF'],
  verde: ['#1FAF62', '#5BD68E', '#E7F8EE'], rosa: ['#E64B8B', '#FF8FB8', '#FDEBF1'] };

const Escena: React.FC<{ e: EscenaMC; acento: string; fotos: string[]; n: number; claro: boolean }> = ({ e, acento, fotos, n, claro }) => {
  const { height: H, width: W } = useVideoConfig();
  const T = temaW(claro);
  const c = colores(claro ? 'claro' : 'oscuro', acento);
  const cy = H * 0.57;
  const W5: Record<string, () => React.ReactNode> = {
    orbita: () => <OrbitaMC centro={e.centro || { texto: '' }} items={e.items || []} acento={acento} T={T} cy={cy} />,
    ruta: () => <RutaMC pasos={e.pasos || []} titulo={e.titulo || ''} acento={acento} T={T} cy={cy} />,
    conectores: () => <ConectoresMC entradas={e.entradas || []} opciones={e.opciones || []} resultado={e.resultado || { texto: '' }} acento={acento} T={T} cy={cy} />,
    contador: () => <ContadorMC valor={e.valor || 0} sufijo={e.sufijo} prefijo={e.prefijo} etiqueta={e.etiqueta} acento={acento} T={T} cy={cy} />,
    versiones: () => <VersionesMC cartas={e.cartas || []} acento={acento} T={T} cy={cy} />,
  };
  if (W5[e.tipo]) return <>{W5[e.tipo]()}</>;
  if (e.tipo === 'reel' && e.reel && REEL[e.reel]) {
    const R = REEL[e.reel];
    const [a, b, c2] = PALETAS[e.paleta || 'azul'] || PALETAS.azul;
    const foto = typeof e.img === 'number' ? fotos[e.img] : undefined;
    return (
      <AbsoluteFill style={{ ['--cc-azul' as any]: a, ['--cc-lila' as any]: b, ['--cc-lilaf' as any]: c2, transform: `translateX(${((e.lado || 0) * W * 0.035).toFixed(1)}px)` }}>
        <R cy={H * (H > W ? 0.63 : 0.6)} {...(e.wp || {})} foto={foto} />
      </AbsoluteFill>
    );
  }
  const conTitular = !!(e.titular && e.titular.length);
  if (e.tipo === 'comp' && e.comp && COMPS[e.comp]) {
    const C = COMPS[e.comp];
    return (
      <TarjetaMC>
        {!e.pantalla && <Fondo c={colores('oscuro', acento)} acento={acento} foto={typeof e.fondo_foto === 'number' ? fotos[e.fondo_foto] : undefined} />}
        <AbsoluteFill><C {...(e.props || {})} salida={0.01} /></AbsoluteFill>
      </TarjetaMC>
    );
  }
  if (e.tipo === 'foto' && typeof e.foto === 'number') {
    return <TarjetaMC><FotoMC e={conTitular ? { ...e, titulo: '' } : e} src={fotos[e.foto]} acento={acento} n={0} /></TarjetaMC>;
  }
  if (e.tipo === 'video' && e.video) return <TarjetaMC><VideoMC e={conTitular ? { ...e, titulo: '' } : e} acento={acento} /></TarjetaMC>;
  let cuerpo: React.ReactNode = null;
  if (e.tipo === 'objeto' && e.objeto) cuerpo = <ObjetoMC e={e} c={c} acento={acento} />;
  else if (e.tipo === 'pildoras') cuerpo = <PildorasMC e={e} c={c} acento={acento} />;
  else if (e.tipo === 'diagrama') cuerpo = <DiagramaMC e={e} c={c} acento={acento} />;
  else if (e.tipo === 'icono' && e.icono) cuerpo = <IconoMC e={e} c={c} acento={acento} />;
  return <AbsoluteFill style={{ transform: `translateY(${(H * 0.09).toFixed(1)}px)` }}>{cuerpo}</AbsoluteFill>;
};

export const MotionsCompleto: React.FC<MotionsProps> = ({ escenas = [], fotos = [], acento = '#4C7DFF', tema = 'claro', titulares }) => {
  useFuentes();
  const { fps } = useVideoConfig();
  const claro = tema !== 'oscuro';
  return (
    <AbsoluteFill>
      <FondoTema claro={claro} acento={acento} />
      {escenas.map((e, i) => {
        const ultimo = i === escenas.length - 1;
        const desde = Math.round(e.ini * fps);
        const largo = Math.max(1, Math.round((e.fin - e.ini + (ultimo ? 0 : SAL)) * fps));
        return (
          <Sequence key={i} from={desde} durationInFrames={largo}>
            <Vida dur={ultimo ? 1e9 : e.fin - e.ini} lado={e.lado || 0} empuje={e.empuje}><Escena e={e} acento={acento} fotos={fotos} n={i} claro={claro} /></Vida>
          </Sequence>
        );
      })}
      {((titulares && titulares.length ? titulares : escenas) as TitularMC[]).map((e, i) => ((e.titular && e.titular.length) || e.arriba ? (
        <Sequence key={`t${i}`} from={Math.round(e.ini * fps)} durationInFrames={Math.max(1, Math.round((e.fin - e.ini + 0.25) * fps))}>
          <TitularVida palabras={e.titular || []} arriba={e.arriba} dur={e.fin - e.ini} claro={claro} />
        </Sequence>
      ) : null))}
    </AbsoluteFill>
  );
};
