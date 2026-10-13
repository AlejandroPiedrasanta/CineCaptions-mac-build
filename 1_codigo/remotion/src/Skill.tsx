// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/Skill.tsx — las animaciones del Tema 5, con el sistema de la skill «Edit VIRAL Reels with AI» (skill videos/: el video editado
// de referencia y su tablero de inspiración). Mismo lenguaje en todo: papel claro con cuadrícula, tinta oscura, UNA sola tinta de acento, Inter +
// DM Serif Text cursiva, sombras suaves, cristal oscuro sobre el video y el fondo oscurecido detrás de lo que aparece encima.
//   PasosT5      indicador 1–2–3 sobre el video (en el gancho, en rojo; luego marca el paso en que va)            · elemento en pantalla
//   DeslizadorT5 «Principiante ●──── Profesional»: el punto recorre la barra                                    · elemento en pantalla
//   EscenaT5     papel a pantalla completa o en la mitad de arriba (pantalla dividida: la persona abajo), con un icono 3D en su
//              tarjeta, una cifra en serif o una foto del propio video; el texto lo ponen los captions (tinta oscura)
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { FAMILIA, clamp, rgb, useFuentes } from './comun';
import { App, Avatares, Barra, Calendario, Cifra, Comparacion, Estado, Ficha, Grafica, Lista, Muestra, Objeto, Ojo, Pieza, Precio, Pregunta, Reloj, TEMA_CLARO, TEMA_MELOCOTON, TEMA_OSCURO, TemaCtx, sombra } from './Objetos';

const PAPEL = '#F2F1EC';
const TINTA = '#1D1D21';
const easeOut = (q: number) => 1 - Math.pow(1 - clamp(q), 3);
const easeInOut = (q: number) => { const x = clamp(q); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };

/** Entrada y salida comunes: [0..1] al entrar (0,35 s) y al salir (los últimos 0,3 s). */
const useVida = (entra = 0.35, sale = 0.3) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps, fin = durationInFrames / fps;
  return { t, fin, e: easeOut(t / entra), s: easeOut((t - (fin - sale)) / sale) };
};

/** Oscurece el video detrás de lo que aparece encima (la skill: «darken and blur the background behind it»). */
const Sombra: React.FC<{ y: number; fuerza: number }> = ({ y, fuerza }) => (
  <AbsoluteFill style={{ background: `radial-gradient(ellipse 95% 46% at 50% ${y}%, rgba(0,0,0,${(0.68 * fuerza).toFixed(3)}), rgba(0,0,0,${(0.36 * fuerza).toFixed(3)}) 55%, rgba(0,0,0,${(0.12 * fuerza).toFixed(3)}) 100%)` }} />
);

/** Cristal oscuro (las tarjetas que flotan sobre el video). */
const cristal = (U: number): React.CSSProperties => ({
  background: 'linear-gradient(180deg, rgba(34,37,48,.78), rgba(18,20,28,.78))', border: `${Math.max(1, U * 1.4)}px solid rgba(255,255,255,.10)`,
  boxShadow: `0 ${U * 18}px ${U * 48}px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.08)`,
});

/* ----------------------------------------------------------------------------------------------- Pasos */
export type PasosProps = { n?: number; actual?: number; gancho?: boolean; y?: number; acento?: string };
export const PasosT5: React.FC<PasosProps> = ({ n = 3, actual = 0, gancho = false, y = 64 }) => {
  useFuentes();
  const { width, height } = useVideoConfig();
  const U = Math.min(width, height) / 1080;
  const { t, e, s } = useVida();
  const vis = e * (1 - s);
  const d = 58 * U, linea = 64 * U, pad = 22 * U;
  const ancho = n * d + (n - 1) * linea + 2 * pad;
  const rojo = '#FF4B55';
  return (
    <AbsoluteFill>
      <Sombra y={y} fuerza={vis} />
      <div style={{ position: 'absolute', left: (width - ancho) / 2, top: (y / 100) * height - (d + 2 * pad) / 2, width: ancho, height: d + 2 * pad,
                    borderRadius: (d + 2 * pad) / 2, ...cristal(U), opacity: vis, transform: `translateY(${((1 - e) * 14 * U).toFixed(2)}px) scale(${(0.97 + 0.03 * e).toFixed(4)})`,
                    display: 'flex', alignItems: 'center', padding: `0 ${pad}px` }}>
        {Array.from({ length: n }, (_, i) => {
          const k = i + 1;
          const hecho = !gancho && k < actual, ahora = !gancho && k === actual;
          const pi = gancho ? easeOut((t - 0.15 - i * 0.16) / 0.3) : 1;
          const pa = ahora ? easeOut((t - 0.25) / 0.35) : 0;                        // el paso de ahora se rellena
          const lleno = hecho || pa > 0.5;
          const anillo = ahora ? clamp((t - 0.25) / 0.6) : 0;
          const color = gancho ? rojo : lleno ? '#FFFFFF' : 'rgba(255,255,255,.38)';
          return (
            <div key={k} style={{ display: 'flex', alignItems: 'center' }}>
              {i > 0 && <div style={{ width: linea, height: Math.max(1.5, 2.6 * U), background: gancho ? 'rgba(255,75,85,.45)' : k <= actual ? 'rgba(255,255,255,.85)' : 'rgba(255,255,255,.2)' }} />}
              <div style={{ position: 'relative', width: d, height: d, borderRadius: '50%', border: `${Math.max(1.5, 3 * U)}px solid ${color}`, boxSizing: 'border-box',
                            background: lleno ? '#FFFFFF' : 'transparent', opacity: pi, transform: `scale(${(0.7 + 0.3 * pi).toFixed(3)})`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: FAMILIA.inter, fontWeight: 700, fontSize: 24 * U,
                            color: gancho ? rojo : lleno ? TINTA : 'rgba(255,255,255,.55)' }}>
                {k}
                {ahora && anillo > 0 && anillo < 1 && (
                  <div style={{ position: 'absolute', inset: -2 * U, borderRadius: '50%', border: `${2 * U}px solid rgba(255,255,255,${(0.7 * (1 - anillo)).toFixed(3)})`,
                                transform: `scale(${(1 + anillo * 0.55).toFixed(3)})` }} />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ----------------------------------------------------------------------------------------------- Deslizador */
export type DeslizadorProps = { izq?: string; der?: string; y?: number; acento?: string };
export const DeslizadorT5: React.FC<DeslizadorProps> = ({ izq = 'Principiante', der = 'Profesional', y = 63, acento = '#4C7DFF' }) => {
  useFuentes();
  const { width, height } = useVideoConfig();
  const U = Math.min(width, height) / 1080;
  const { t, fin, e, s } = useVida();
  const vis = e * (1 - s);
  const w = 0.6 * Math.min(width, height), hgt = 118 * U, pad = 30 * U;
  const p = easeInOut((t - 0.35) / Math.max(0.6, fin - 0.95));
  const [r, g, b] = rgb(acento);
  const pista = w - 2 * pad, x = pad + pista * p;
  return (
    <AbsoluteFill>
      <Sombra y={y} fuerza={vis} />
      <div style={{ position: 'absolute', left: (width - w) / 2, top: (y / 100) * height - hgt / 2, width: w, height: hgt, borderRadius: 26 * U, ...cristal(U),
                    opacity: vis, transform: `translateY(${((1 - e) * 16 * U).toFixed(2)}px)` }}>
        <div style={{ position: 'absolute', left: pad, right: pad, top: 26 * U, display: 'flex', justifyContent: 'space-between', fontFamily: FAMILIA.inter,
                      fontWeight: 500, fontSize: 21 * U, color: 'rgba(255,255,255,.72)', letterSpacing: '0.01em' }}>
          <span style={{ color: p < 0.5 ? '#fff' : undefined }}>{izq}</span><span style={{ color: p >= 0.5 ? '#fff' : undefined }}>{der}</span>
        </div>
        <div style={{ position: 'absolute', left: pad, width: pista, top: 74 * U, height: 8 * U, borderRadius: 4 * U, background: 'rgba(255,255,255,.14)' }} />
        <div style={{ position: 'absolute', left: pad, width: Math.max(0, x - pad), top: 74 * U, height: 8 * U, borderRadius: 4 * U,
                      background: `linear-gradient(90deg, rgba(${r},${g},${b},.55), rgb(${r},${g},${b}))` }} />
        <div style={{ position: 'absolute', left: x - 15 * U, top: 78 * U - 15 * U, width: 30 * U, height: 30 * U, borderRadius: '50%', background: '#fff',
                      boxShadow: `0 0 ${18 * U}px rgba(${r},${g},${b},.9), 0 ${4 * U}px ${10 * U}px rgba(0,0,0,.35)` }} />
      </div>
    </AbsoluteFill>
  );
};

/* ----------------------------------------------------------------------------------------------- Escena (papel) */
// Los objetos (Objetos.tsx) ilustran lo que se dice y entran en el momento en que se nombran. Disposición: 'objeto' (uno, al centro de la zona),
// 'fila' (muestras en fila; 4 → 2×2) o 'fichas' (alrededor de la frase, que va al centro). Entrada: corte seco con un zoom que se asienta
// (1,06 → 1, desenfoque → nítido); durante la escena la «cámara» se acerca un poco; al salir los objetos se dispersan y el papel sube.
export type EscenaProps = { variante?: 'texto' | 'icono' | 'cifra' | 'tarjeta' | 'objetos'; mitad?: 'completa' | 'arriba' | 'encima'; icono?: string; cifra?: string; etiqueta?: string;
                            imagen?: string; acento?: string; objetos?: Objeto[]; disposicion?: 'objeto' | 'fila' | 'fichas'; fondo?: 'papel' | 'cristal' | 'melocoton'; y?: number };
const ESCALA_OBJ: Record<string, number> = { ficha: 1.35, avatares: 1.3, estado: 1.45, reloj: 1.25, barra: 1.12, precio: 1.15, muestra: 1.1, grafica: 1.1, app: 1.05,
                                              lista: 1.35, comparacion: 1.35, pregunta: 1.3, icono3d: 1.1 };
const HUECOS_FICHAS: [number, number][] = [[-0.24, -0.2], [0.26, -0.15], [0.3, 0.14], [-0.3, 0.13], [0.12, 0.25], [-0.14, 0.27], [0.02, -0.3], [-0.33, -0.3]];
export const EscenaT5: React.FC<EscenaProps> = ({ variante = 'texto', mitad = 'completa', icono = '', cifra = '', etiqueta = '', imagen = '', acento = '#4C7DFF',
                                                  objetos = [], disposicion = 'objeto', fondo = 'papel', y = 68 }) => {
  useFuentes();
  const { width, height } = useVideoConfig();
  const U = Math.min(width, height) / 1080;
  const { t, fin, e, s } = useVida(0.3, 0.3);
  const arriba = mitad === 'arriba', encima = mitad === 'encima', cristal = fondo === 'cristal' || encima;
  const melocoton = fondo === 'melocoton' && !encima && !arriba;     // Tema 6: melocotón cálido, cartas blancas, entra y sale con un destello blanco
  const alto = arriba ? height * 0.5 : height;
  const paso = 54 * U;
  const salida = clamp((t - (fin - 0.3)) / 0.3);
  // entrada: la mitad de arriba baja como una persiana; la completa es un corte con zoom que se asienta. Salida: el papel sube.
  const corte = arriba ? `inset(0 0 ${((1 - e) * 100 + s * 100).toFixed(2)}% 0)` : `inset(0 0 ${(s * 100).toFixed(2)}% 0)`;
  const zoom = (arriba ? 1 : 1.06 - 0.06 * e) * (1 + 0.03 * clamp(t / Math.max(1, fin)));
  const desenfoque = arriba ? 0 : (1 - e) * 8;
  const cy = encima ? (y / 100) * height : arriba ? alto * 0.58 : disposicion === 'fichas' ? height * 0.46 : height * 0.56;
  const po = easeOut((t - 0.22) / 0.55);
  const flota = Math.sin(t * 1.6) * 6 * U;
  const objeto = (o: Objeto, x: number, y: number, fuera: [number, number] = [0, -1]) => {
    const C: Record<string, React.ReactNode> = {
      muestra: <Muestra o={o} U={U} />, ficha: <Ficha o={o} U={U} />, app: <App o={o} U={U} acento={acento} />, ojo: <Ojo o={o} U={U} acento={acento} />,
      barra: <Barra o={o} U={U} acento={acento} />, precio: <Precio o={o} U={U} acento={acento} />, grafica: <Grafica o={o} U={U} acento={acento} />,
      reloj: <Reloj o={o} U={U} acento={acento} />, avatares: <Avatares o={o} U={U} acento={acento} />, calendario: <Calendario o={o} U={U} acento={acento} />,
      estado: <Estado o={o} U={U} />, cifra: <Cifra o={o} U={U} acento={acento} />, lista: <Lista o={o} U={U} acento={acento} />,
      comparacion: <Comparacion o={o} U={U} acento={acento} />, pregunta: <Pregunta o={o} U={U} acento={acento} />,
      icono3d: <div style={{ width: 340 * U, height: 340 * U, borderRadius: 75 * U, background: 'linear-gradient(180deg,#FFFFFF,#F4F5F8)', boxShadow: sombra(U), display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Img src={staticFile(`iconos3d/${o.icono}.png`)} style={{ width: 210 * U, height: 210 * U, objectFit: 'contain' }} /></div>,
    };
    const k = (ESCALA_OBJ[o.tipo] ?? 1) * ((arriba || encima) && ['ojo', 'precio', 'grafica', 'calendario', 'barra', 'lista', 'pregunta'].includes(o.tipo) ? 0.8 : 1) * (encima ? 0.86 : 1);
    return (
      <Pieza key={`${o.tipo}${x}${y}`} x={x} y={y} t0={o.t} U={U} salida={salida} fuera={fuera} flota={o.tipo === 'barra' ? 0.3 : 1}>
        <div style={{ transform: `scale(${k})` }}>{C[o.tipo] || null}</div>
      </Pieza>
    );
  };
  let contenido: React.ReactNode = null;
  if (objetos.length) {
    if (disposicion === 'fichas') {
      contenido = objetos.map((o, i) => {
        const [fx, fy] = HUECOS_FICHAS[i % HUECOS_FICHAS.length];
        return objeto(o, width / 2 + fx * width, cy + fy * height * (arriba ? 0.5 : 0.62), [Math.sign(fx) || 1, fy < 0 ? -0.6 : 0.6]);
      });
    } else if (disposicion === 'fila') {
      const n = objetos.length, cols = n === 4 ? 2 : n, filas = Math.ceil(n / cols);
      const dx = 250 * U * (arriba && n > 2 ? 0.88 : 1), dy = 300 * U;
      contenido = objetos.map((o, i) => {
        const c = i % cols, f = Math.floor(i / cols);
        return objeto(o, width / 2 + (c - (cols - 1) / 2) * dx, cy + (f - (filas - 1) / 2) * dy, [0, -1]);
      });
    } else {
      contenido = objetos.map(o => objeto(o, width / 2, cy));
    }
  } else if (variante === 'icono') {
    const lado = (arriba ? 300 : 360) * U;
    contenido = (
      <div style={{ position: 'absolute', left: width / 2 - lado / 2, top: cy - lado / 2 + flota, width: lado, height: lado, borderRadius: lado * 0.22,
                    background: 'linear-gradient(180deg, #FFFFFF, #F4F5F8)', boxShadow: sombra(U), opacity: po * (1 - salida),
                    transform: `translateY(${((1 - po) * 40 * U).toFixed(1)}px) scale(${(0.92 + 0.08 * po).toFixed(4)})`, display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center', gap: lado * 0.06 }}>
        {icono && <Img src={staticFile(`iconos3d/${icono}.png`)} style={{ width: lado * 0.56, height: lado * 0.56, objectFit: 'contain' }} />}
        <div style={{ width: lado * 0.46, height: lado * 0.035, borderRadius: lado, background: '#E6E8EE' }} />
        <div style={{ width: lado * 0.3, height: lado * 0.035, borderRadius: lado, background: '#EEF0F4' }} />
      </div>
    );
  } else if (variante === 'cifra') {
    contenido = objeto({ tipo: 'cifra', t: 0.22, valor: cifra, etiqueta }, width / 2, cy);
  } else if (variante === 'tarjeta' && imagen) {
    const w = (arriba ? 330 : 470) * U, h = w * 1.42;
    contenido = (
      <div style={{ position: 'absolute', left: width / 2 - w / 2, top: cy - h / 2 + flota, width: w, height: h, borderRadius: 28 * U, overflow: 'hidden',
                    border: `${8 * U}px solid #fff`, boxShadow: `0 ${30 * U}px ${70 * U}px rgba(20,25,40,.25)`, opacity: po * (1 - salida),
                    transform: `translateY(${((1 - po) * 90 * U).toFixed(1)}px) rotate(${(-3 + (1 - po) * -4).toFixed(2)}deg) scale(${(0.6 + 0.4 * po).toFixed(3)})` }}>
        <Img src={imagen} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      </div>
    );
  }
  const [ar, ag, ab] = rgb(acento);
  if (melocoton) {
    // el destello: los primeros 0,22 s el video (debajo) se quema a blanco; luego el melocotón, con el blanco que se va; al salir, otra vez blanco
    const pre = 0.22;
    const quema = clamp(t / pre), aparece = clamp((t - pre) / 0.05), blanco = t < pre ? 0.95 * quema * quema : 0.95 * (1 - easeOut((t - pre) / 0.4));
    const sale = clamp((t - (fin - 0.25)) / 0.25);
    return (
      <AbsoluteFill>
        <AbsoluteFill style={{ opacity: aparece * (1 - sale), fontSynthesis: 'none' }}>
          <AbsoluteFill style={{ background: 'linear-gradient(165deg, #FCE2D2 0%, #FFF4EE 46%, #FDE6D8 100%)' }} />
          <AbsoluteFill style={{ background: `radial-gradient(ellipse 70% 45% at ${(30 + 8 * Math.sin(t * 0.5)).toFixed(2)}% 22%, rgba(255,255,255,.75), rgba(255,255,255,0) 70%)` }} />
          <div style={{ position: 'absolute', inset: 0, transform: `scale(${(1 + 0.025 * clamp(t / Math.max(1, fin))).toFixed(4)})` }}>
            <TemaCtx.Provider value={TEMA_MELOCOTON}>{contenido}</TemaCtx.Provider>
          </div>
        </AbsoluteFill>
        <AbsoluteFill style={{ background: '#FFFBF7', opacity: Math.max(blanco, 0.85 * Math.sin(sale * Math.PI)) }} />
      </AbsoluteFill>
    );
  }
  if (encima) {                                                    // sobre el propio video: oscurecido detrás (la skill), los objetos en cristal oscuro
    const vis = e * (1 - s);
    return (
      <AbsoluteFill>
        <AbsoluteFill style={{ background: `radial-gradient(ellipse 90% 40% at 50% ${y}%, rgba(0,0,0,${(0.62 * vis).toFixed(3)}), rgba(0,0,0,${(0.3 * vis).toFixed(3)}) 60%, rgba(0,0,0,${(0.14 * vis).toFixed(3)}) 100%)` }} />
        <TemaCtx.Provider value={TEMA_OSCURO}>{contenido}</TemaCtx.Provider>
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: 0, top: 0, width, height: alto, overflow: 'hidden', clipPath: corte,
                    background: cristal ? `radial-gradient(ellipse 80% 60% at 50% 40%, rgba(${ar},${ag},${ab},.22), rgba(${ar},${ag},${ab},0) 70%), linear-gradient(180deg, #121626, #0A0D18)` : PAPEL,
                    boxShadow: arriba ? `0 ${10 * U}px ${30 * U}px rgba(0,0,0,.35)` : undefined }}>
        <div style={{ position: 'absolute', inset: 0, transform: `scale(${zoom.toFixed(4)})`, filter: desenfoque > 0.05 ? `blur(${desenfoque.toFixed(2)}px)` : undefined }}>
          <div style={{ position: 'absolute', inset: '-4%', backgroundImage: cristal
                          ? `linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px)`
                          : `linear-gradient(rgba(20,20,40,.045) 1px, transparent 1px), linear-gradient(90deg, rgba(20,20,40,.045) 1px, transparent 1px)`,
                        backgroundSize: `${paso}px ${paso}px`, backgroundPosition: `${(width / 2) % paso}px 0` }} />
          {!cristal && <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse 85% 70% at 50% 45%, rgba(255,255,255,.55), rgba(0,0,0,.035) 100%)' }} />}
          <TemaCtx.Provider value={cristal ? TEMA_OSCURO : TEMA_CLARO}>{contenido}</TemaCtx.Provider>
        </div>
      </div>
    </AbsoluteFill>
  );
};
