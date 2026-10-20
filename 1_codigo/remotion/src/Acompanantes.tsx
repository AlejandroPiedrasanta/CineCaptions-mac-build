// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/Acompanantes.tsx — los ACOMPAÑANTES del Tema 5: animaciones pequeñas JUSTO DEBAJO del caption que ilustran lo que se dice
// en ese momento (pedido del usuario: «hoy estamos en Guatemala → la animación abajo de los captions»; «hola amigos → un motion relacionado»).
//   lugar    pin que cae, bandera que ondea y «Estamos en · Guatemala»
//   saludo   la mano que saluda (emoji 3D) y «¡Hola amigos!» con destellos
//   sticker  el emoji 3D del concepto que se nombra (boda, maquillaje, iglesia, dinero, lluvia…) y su palabra
//   redes    el botón que se pulsa: Seguir, Me gusta (corazón que se llena), Suscribirse (campana), Comentar, Compartir, Guardar
//   cifra    la cifra que se dice, contando, con una barrita que se llena · tiempo (reloj que gira) · dinero (la cantidad)
// Dos aspectos (los elige el programa por video): 'cristal' (oscuro, como los elementos en pantalla de la referencia) o 'blanco'.
// Entra desde abajo con resorte suave y desenfoque, vive un poco (flota) y se va hacia abajo. Nunca dice algo que no se dijo.
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { FAMILIA, clamp, rgb, useFuentes } from './comun';
import { EmojiAnimado } from './Emoji';

const easeOut = (q: number) => 1 - Math.pow(1 - clamp(q), 3);
const resorte = (q: number) => { const x = clamp(q); return 1 - Math.exp(-6 * x) * Math.cos(9 * x); };   // asienta con un pequeño rebote

export type AcompananteProps = {
  tipo?: 'lugar' | 'saludo' | 'sticker' | 'redes' | 'cifra' | 'tiempo' | 'dinero';
  texto?: string; kicker?: string; valor?: string; unidad?: string; signo?: string; pais?: string; sticker?: string; accion?: string;
  aspecto?: 'cristal' | 'blanco'; y?: number; acento?: string; escala?: number;
  // v5.20 (página Efectos › Píldora bajo captions: 10 estilos y los colores del usuario; estilos_pro.py). Sin `variante`, la de `aspecto`.
  variante?: string; fondo?: string; tinta?: string; acento2?: string;
};

const HEX = /^#?[0-9a-fA-F]{6}$/;
const hex = (h?: string) => (h && HEX.test(h) ? '#' + h.replace('#', '') : '');
const claroDe = (h: string) => { const [r, g, b] = rgb(h); return 0.299 * r + 0.587 * g + 0.114 * b > 150; };

/** El aspecto de la píldora (v5.20): fondo, borde, sombra, radio, tinta y si es oscura (los iconos de dentro). `fondo`/`tinta` del usuario mandan. */
const vestido = (variante: string, U: number, acento: string, acento2: string, fondoU: string, tintaU: string) => {
  const [r, g, b] = rgb(acento);
  const [r2, g2, b2] = rgb(acento2);
  const sombra = `0 ${16 * U}px ${40 * U}px rgba(0,0,0,.45)`;
  let v: { fondo: string; borde: string; sombra: string; radio: number; oscuro: boolean; giro?: number; barra?: boolean; textoSombra?: string } =
    { fondo: 'linear-gradient(180deg, rgba(38,42,58,.86), rgba(18,20,30,.86))', borde: `${1.3 * U}px solid rgba(255,255,255,.12)`,
      sombra: `${sombra}, 0 0 ${30 * U}px rgba(${r},${g},${b},.18)`, radio: 999, oscuro: true };
  if (variante === 'blanca') v = { fondo: 'rgba(255,255,255,.96)', borde: `${1.3 * U}px solid rgba(0,0,0,.04)`, sombra: `0 ${16 * U}px ${40 * U}px rgba(20,30,60,.22)`, radio: 999, oscuro: false };
  else if (variante === 'transparente') v = { fondo: 'rgba(0,0,0,0)', borde: `${2.4 * U}px solid rgba(255,255,255,.9)`, sombra: 'none', radio: 999, oscuro: true,
                                              textoSombra: `0 ${2 * U}px ${8 * U}px rgba(0,0,0,.7)` };
  else if (variante === 'vidrio') v = { fondo: 'linear-gradient(180deg, rgba(255,255,255,.34), rgba(255,255,255,.16))', borde: `${1.6 * U}px solid rgba(255,255,255,.55)`,
                                        sombra: `0 ${14 * U}px ${36 * U}px rgba(0,0,0,.28), inset 0 ${1.5 * U}px 0 rgba(255,255,255,.6)`, radio: 999, oscuro: true,
                                        textoSombra: `0 ${1.5 * U}px ${6 * U}px rgba(0,0,0,.45)` };
  else if (variante === 'neon') v = { fondo: 'rgba(8,8,16,.82)', borde: `${2.6 * U}px solid rgb(${r},${g},${b})`, radio: 999, oscuro: true,
                                      sombra: `0 0 ${18 * U}px rgba(${r},${g},${b},.85), 0 0 ${50 * U}px rgba(${r},${g},${b},.45), inset 0 0 ${16 * U}px rgba(${r},${g},${b},.35)` };
  else if (variante === 'solida') v = { fondo: `rgb(${r},${g},${b})`, borde: `${1.3 * U}px solid rgba(255,255,255,.18)`, sombra: `0 ${14 * U}px ${36 * U}px rgba(${r},${g},${b},.45)`,
                                        radio: 999, oscuro: !claroDe(acento) };
  else if (variante === 'halo') v = { fondo: `linear-gradient(#0B0C12, #0B0C12) padding-box, linear-gradient(90deg, rgb(${r2},${g2},${b2}), rgb(${r},${g},${b})) border-box`,
                                      borde: `${2.6 * U}px solid transparent`, radio: 999, oscuro: true,
                                      sombra: `-${14 * U}px 0 ${36 * U}px rgba(${r2},${g2},${b2},.45), ${14 * U}px 0 ${36 * U}px rgba(${r},${g},${b},.45)` };
  else if (variante === 'etiqueta') v = { fondo: 'rgba(255,255,255,.97)', borde: 'none', sombra: `inset ${9 * U}px 0 0 rgb(${r},${g},${b}), 0 ${12 * U}px ${30 * U}px rgba(20,30,60,.28)`,
                                          radio: 14 * U, oscuro: false, barra: true };
  else if (variante === 'sticker') v = { fondo: '#FFFFFF', borde: `${6 * U}px solid #FFFFFF`, sombra: `${6 * U}px ${8 * U}px 0 rgba(0,0,0,.35)`, radio: 999, oscuro: false, giro: -3 };
  else if (variante === 'degradado') v = { fondo: `linear-gradient(100deg, rgb(${r},${g},${b}), rgb(${r2},${g2},${b2}))`, borde: `${1.3 * U}px solid rgba(255,255,255,.22)`,
                                           sombra: `0 ${14 * U}px ${40 * U}px rgba(${r},${g},${b},.4)`, radio: 999, oscuro: !(claroDe(acento) && claroDe(acento2)) };
  if (fondoU) {
    v.fondo = variante === 'halo' ? `linear-gradient(${fondoU}, ${fondoU}) padding-box, linear-gradient(90deg, rgb(${r2},${g2},${b2}), rgb(${r},${g},${b})) border-box`
            : variante === 'transparente' ? 'rgba(0,0,0,0)' : fondoU;
    if (variante !== 'transparente') v.oscuro = !claroDe(fondoU);
    if (variante === 'transparente') v.borde = `${2.4 * U}px solid ${fondoU}`;
  }
  const tinta = tintaU || (v.oscuro ? '#F5F6FA' : '#1D1D21');
  const gris = tintaU ? tintaU : v.oscuro ? 'rgba(255,255,255,.66)' : '#8B8B95';
  return { ...v, tinta, gris };
};

export const AcompananteT5: React.FC<AcompananteProps> = ({ tipo = 'sticker', texto = '', kicker = '', valor = '', unidad = '', signo = '', pais = '', sticker = '',
                                                             accion = 'seguir', aspecto = 'cristal', y = 66, acento = '#4C7DFF', escala = 1,
                                                             variante = '', fondo = '', tinta: tintaU = '', acento2 = '' }) => {
  useFuentes();
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const t = frame / fps, fin = durationInFrames / fps;
  const U = (Math.min(width, height) / 1080) * escala;
  const e = resorte(t / 0.5), s = easeOut((t - (fin - 0.28)) / 0.28);
  const vis = clamp(t / 0.18) * (1 - s);
  const acentoH = hex(acento) || '#4C7DFF';
  const V = vestido(variante || (aspecto === 'blanco' ? 'blanca' : 'cristal'), U, acentoH, hex(acento2) || '#FF7A1A', hex(fondo), hex(tintaU));
  const oscuro = V.oscuro;
  const [r, g, b] = rgb(acentoH);
  const tinta = V.tinta, gris = V.gris;
  const marca = variante === 'solida' || variante === 'degradado' ? tinta : `rgb(${r},${g},${b})`;   // (sobre un fondo del acento, la tinta)
  const carta: React.CSSProperties = {
    background: V.fondo, border: V.borde, boxShadow: V.sombra, borderRadius: V.radio,
    display: 'flex', alignItems: 'center', gap: 18 * U, padding: `${14 * U}px ${30 * U}px ${14 * U}px ${(V.barra ? 26 : 16) * U}px`, whiteSpace: 'nowrap',
    position: 'relative', overflow: V.barra ? 'hidden' : undefined, textShadow: V.textoSombra,
    transform: V.giro ? `rotate(${V.giro}deg)` : undefined,
  };
  const flota = Math.sin(t * 2.1) * 4 * U;
  const pop = (t0: number) => resorte((t - t0) / 0.45);
  const icono = (lado: number, contenido: React.ReactNode, fondo = `rgba(${r},${g},${b},.16)`) => (
    <div style={{ width: lado, height: lado, borderRadius: lado / 2, background: fondo, display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>{contenido}</div>
  );
  const textos = (arriba: string, abajo: React.ReactNode, grande = 40) => (
    <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.05 }}>
      {arriba && <span style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 15 * U, letterSpacing: '0.14em', color: gris, textTransform: 'uppercase' }}>{arriba}</span>}
      <span style={{ fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: grande * U, letterSpacing: '-0.01em', color: tinta }}>{abajo}</span>
    </div>
  );
  let cuerpo: React.ReactNode = null;

  if (tipo === 'lugar') {
    const p = pop(0.15), ola = Math.sin(t * 6) * 4;
    const ruta = clamp((t - 0.35) / 0.8);
    cuerpo = (
      <div style={carta}>
        <div style={{ position: 'relative', width: 70 * U, height: 70 * U, flex: 'none' }}>
          <svg width={70 * U} height={70 * U} viewBox="0 0 70 70" style={{ position: 'absolute', inset: 0 }}>
            <circle cx="35" cy="35" r="30" fill="none" stroke={`rgba(${r},${g},${b},.5)`} strokeWidth="2" strokeDasharray="4 6" strokeDashoffset={-t * 12}
                    style={{ opacity: ruta }} />
          </svg>
          <svg width={40 * U} height={52 * U} viewBox="0 0 40 52" style={{ position: 'absolute', left: 15 * U, top: (8 - (1 - p) * 30) * U, opacity: clamp(p * 2) }}>
            <path d="M20 50 C20 50 4 30 4 18 A16 16 0 0 1 36 18 C36 30 20 50 20 50 Z" fill="#FF3B4D" />
            <circle cx="20" cy="18" r="6.5" fill="#fff" />
          </svg>
        </div>
        {pais && (
          <div style={{ width: 84 * U, height: 56 * U, borderRadius: 10 * U, overflow: 'hidden', flex: 'none', boxShadow: `0 ${4 * U}px ${12 * U}px rgba(0,0,0,.3)`,
                        transform: `perspective(${300 * U}px) rotateY(${ola.toFixed(2)}deg) skewY(${(ola * 0.35).toFixed(2)}deg) scale(${(0.6 + 0.4 * pop(0.3)).toFixed(3)})` }}>
            <Img src={staticFile(`mapa/banderas/${pais}.svg`)} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          </div>
        )}
        {textos(kicker, texto, 42)}
      </div>
    );
  } else if (tipo === 'saludo') {
    const giro = Math.sin((t - 0.25) * 11) * 18 * clamp((t - 0.2) / 0.3) * (1 - clamp((t - 1.6) / 0.4));
    cuerpo = (
      <div style={carta}>
        <EmojiAnimado id={sticker || 'waving_hand'} lado={78 * U} style={{ transform: `rotate(${(giro * 0.4).toFixed(1)}deg) scale(${(0.5 + 0.5 * pop(0.1)).toFixed(3)})`,
                                                                      transformOrigin: '70% 85%', filter: `drop-shadow(0 ${6 * U}px ${8 * U}px rgba(0,0,0,.3))` }} />
        {textos(kicker, texto, 44)}
        {[0, 1, 2].map(i => {
          const q = clamp((t - 0.45 - i * 0.12) / 0.6);
          return <div key={i} style={{ position: 'absolute', right: (10 + i * 18) * U, top: (-8 - i * 10) * U, width: 10 * U, height: 10 * U, borderRadius: '50%',
                                       background: marca, opacity: Math.sin(q * Math.PI), transform: `scale(${(0.5 + q).toFixed(2)})` }} />;
        })}
      </div>
    );
  } else if (tipo === 'sticker') {
    cuerpo = (
      <div style={carta}>
        <EmojiAnimado id={sticker} lado={80 * U} style={{ transform: `translateY(${(Math.sin(t * 3) * 3 * U).toFixed(1)}px) scale(${(0.4 + 0.6 * pop(0.08)).toFixed(3)})`,
                                                         filter: `drop-shadow(0 ${6 * U}px ${8 * U}px rgba(0,0,0,.3))` }} />
        {textos(kicker, texto, 40)}
      </div>
    );
  } else if (tipo === 'redes') {
    const clic = clamp((t - 0.55) / 0.18);
    const hecho = t > 0.62;
    const cursor = easeOut((t - 0.1) / 0.45);
    const etiquetas: Record<string, [string, string]> = { seguir: ['Seguir', 'Siguiendo'], follow: ['Follow', 'Following'], like: ['Me gusta', 'Te gusta'],
      suscribir: ['Suscribirse', 'Suscrito'], subscribe: ['Subscribe', 'Subscribed'], comentar: ['Comentar', 'Comentado'], comment: ['Comment', 'Commented'],
      compartir: ['Compartir', 'Compartido'], share: ['Share', 'Shared'], guardar: ['Guardar', 'Guardado'], save: ['Save', 'Saved'] };
    const [antes, despues] = etiquetas[accion] || [texto || 'Seguir', texto || 'Seguir'];
    const esCorazon = accion === 'like';
    const esCampana = accion === 'suscribir' || accion === 'subscribe';
    cuerpo = (
      <div style={{ ...carta, position: 'relative' }}>
        {icono(64 * U, esCorazon ? (
          <svg width={34 * U} height={34 * U} viewBox="0 0 24 24"><path d="M12 21 C12 21 3 14.5 3 8.6 A4.6 4.6 0 0 1 12 6.4 A4.6 4.6 0 0 1 21 8.6 C21 14.5 12 21 12 21 Z"
            fill={hecho ? '#FF3B5C' : 'none'} stroke={hecho ? '#FF3B5C' : tinta} strokeWidth="2" style={{ transform: `scale(${hecho ? 1 + 0.25 * Math.max(0, 1 - (t - 0.62) / 0.3) : 1})`, transformOrigin: 'center' }} /></svg>
        ) : esCampana ? (
          <svg width={34 * U} height={34 * U} viewBox="0 0 24 24" style={{ transform: `rotate(${(hecho ? Math.sin((t - 0.62) * 30) * 14 * Math.max(0, 1 - (t - 0.62) / 0.8) : 0).toFixed(1)}deg)` }}>
            <path d="M6 16 V11 A6 6 0 0 1 18 11 V16 L20 18 H4 Z M10 20 A2 2 0 0 0 14 20" fill={hecho ? `rgb(${r},${g},${b})` : 'none'} stroke={hecho ? `rgb(${r},${g},${b})` : tinta} strokeWidth="2" /></svg>
        ) : (
          <svg width={34 * U} height={34 * U} viewBox="0 0 24 24"><path d={accion.startsWith('coment') || accion === 'comment' ? 'M4 5 H20 V16 H9 L4 20 Z' : accion.startsWith('compart') || accion === 'share' ? 'M14 4 L20 10 L14 16 M20 10 H9 A5 5 0 0 0 4 15 V19' : accion.startsWith('guard') || accion === 'save' ? 'M6 3 H18 V21 L12 16 L6 21 Z' : 'M12 5 V19 M5 12 H19'}
            fill="none" stroke={tinta} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" /></svg>
        ))}
        <div style={{ padding: `${12 * U}px ${26 * U}px`, borderRadius: 999, background: hecho ? (oscuro ? 'rgba(255,255,255,.12)' : '#EEF0F4') : marca,
                      color: hecho ? tinta : (marca === tinta ? `rgb(${r},${g},${b})` : '#fff'), fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 30 * U, transform: `scale(${(1 - 0.08 * Math.sin(clic * Math.PI)).toFixed(3)})` }}>
          {hecho ? despues : antes}
        </div>
        <svg width={36 * U} height={44 * U} viewBox="0 0 36 44" style={{ position: 'absolute', left: (120 + (1 - cursor) * 160) * U, top: (40 + (1 - cursor) * 60) * U, opacity: clamp(t / 0.2) * (1 - clamp((t - 1.2) / 0.3)),
                                                                     transform: `scale(${(1 - 0.12 * Math.sin(clic * Math.PI)).toFixed(3)})`, filter: `drop-shadow(0 ${3 * U}px ${4 * U}px rgba(0,0,0,.4))` }}>
          <path d="M4 2 L4 34 L13 26 L19 40 L25 37 L19 24 L31 24 Z" fill="#fff" stroke="#111" strokeWidth="2" strokeLinejoin="round" />
        </svg>
      </div>
    );
  } else if (tipo === 'cifra' || tipo === 'dinero' || tipo === 'tiempo') {
    const limpio = String(valor || '').replace(/,/g, '');
    const v = parseFloat(limpio);
    const dec = (limpio.split('.')[1] || '').length;
    const q = easeOut((t - 0.15) / 0.9);
    const n = isFinite(v) ? (v * q).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec }) : valor;
    const pre = tipo === 'dinero' ? (signo || '$') : '', post = tipo === 'cifra' && signo === '%' ? '%' : '';
    cuerpo = (
      <div style={carta}>
        {icono(64 * U, tipo === 'tiempo' ? (
          <svg width={36 * U} height={36 * U} viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke={marca} strokeWidth="2.2" />
            <path d={`M12 12 L${(12 + 6 * Math.sin(t * 4)).toFixed(2)} ${(12 - 6 * Math.cos(t * 4)).toFixed(2)}`} stroke={marca} strokeWidth="2.2" strokeLinecap="round" /></svg>
        ) : (
          <span style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: 30 * U, color: marca }}>{tipo === 'dinero' ? (signo || '$') : '#'}</span>
        ))}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 * U }}>
          {textos(kicker, <>{pre}{n}{post}{unidad ? <span style={{ fontWeight: 500, fontSize: 28 * U, color: gris }}> {unidad}</span> : null}</>, 46)}
          {tipo === 'cifra' && signo === '%' && isFinite(v) && (
            <div style={{ width: 200 * U, height: 8 * U, borderRadius: 4 * U, background: oscuro ? 'rgba(255,255,255,.12)' : '#EEF0F4' }}>
              <div style={{ width: `${Math.min(100, v * q)}%`, height: '100%', borderRadius: 4 * U, background: marca }} />
            </div>
          )}
        </div>
      </div>
    );
  }
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: 0, width, top: (y / 100) * height, display: 'flex', justifyContent: 'center', opacity: vis,
                    transform: `translateY(${((1 - e) * 46 * U + s * 30 * U + flota).toFixed(1)}px) scale(${(0.9 + 0.1 * clamp(e)).toFixed(4)})`,
                    filter: `blur(${((1 - clamp(e * 1.4)) * 8 + s * 6).toFixed(2)}px)` }}>
        <div style={{ transform: 'translateY(-50%)' }}>{cuerpo}</div>
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------------------------------------ velo de legibilidad (Temas 1–4) */
// Un velo oscuro y suave DETRÁS de los captions de los Temas 1–4 cuando el video es claro (la skill: «oscurecer lo de detrás»). No cambia el diseño
// del tema: solo le da contraste. `y`/`alto`/`ancho` en % del cuadro (la caja de la pila de captions); entra y sale con un fundido corto.
export type VeloCaptionProps = { y?: number; alto?: number; ancho?: number; fuerza?: number };
export const VeloCaptionT: React.FC<VeloCaptionProps> = ({ y = 60, alto = 14, ancho = 92, fuerza = 0.42 }) => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const t = frame / fps, fin = durationInFrames / fps;
  const vis = clamp(t / 0.15) * (1 - clamp((t - (fin - 0.2)) / 0.2));
  const h = (alto / 100) * height * 1.7, w = (ancho / 100) * width * 1.15;
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: (width - w) / 2, top: (y / 100) * height - h / 2, width: w, height: h, opacity: vis,
                    background: `radial-gradient(closest-side, rgba(0,0,0,${fuerza.toFixed(3)}), rgba(0,0,0,${(fuerza * 0.62).toFixed(3)}) 55%, rgba(0,0,0,0))` }} />
    </AbsoluteFill>
  );
};
