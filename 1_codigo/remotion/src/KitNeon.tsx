// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/KitNeon.tsx — v5.5.13: el Tema 1 NEÓN con el motor del kit del usuario (kitneon/motor.ts = Escritorio/TEMA 1/graficos/motor.js):
// captions «hook» y motions (notificación, órbita, interruptores, ruta, checks, cortinillas…) idénticos a entregas/3_neon_kinetic_hook.mp4.
// props: escena = [{fn: 'hook' | 'notificacion' | …, a: {…argumentos del kit…} | args: […]}] (tiempos en s del VIDEO), o `codigo` (JS que llama a esas
// funciones, como un escenas.js del kit, con `L` = datos); imagenes = {nombre: data URI}; t0 = s del video en el fotograma 0 del clip; tema = 'neon';
// subs = subfotogramas del desenfoque de movimiento (kit: 5, obturador de 180°; 1 = sin desenfoque).
// El escenario es de 1080×1920 (el del kit) y se escala al ancho del timeline.
// Desenfoque de movimiento como el renderizador del kit (promedio de subfotogramas): `subs` escenarios idénticos, cada uno en su instante del
// obturador, apilados con opacidad 1, 1/2, 1/3… (así cada uno pesa lo mismo); si en este fotograma nada se mueve (la firma del motor es la misma en
// todos los subfotogramas) se enseña uno solo.
import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { AbsoluteFill, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { crearMotor } from './kitneon/motor';
import { BASE, FUENTES_KIT, TEMA_CSS } from './kitneon/estilos';

type Llamada = { fn: string; a?: Record<string, unknown>; args?: unknown[]; escala?: number; cx?: number; cy?: number };
export type KitNeonProps = { escena?: Llamada[]; codigo?: string; L?: Record<string, unknown>; imagenes?: Record<string, string>; t0?: number; tema?: string;
                             subs?: number; fondo?: string };

// v5.5.17, «Motions completo» del Tema 1: el fondo OPACO del kit (morado con el velo radial) y dos brillos, magenta y lima, que derivan despacio
const FondoNeon: React.FC<{ t: number; escala: number }> = ({ t, escala }) => {
  const b1x = 300 + 140 * Math.sin(t * 0.21), b1y = 560 + 110 * Math.cos(t * 0.17);
  const b2x = 780 + 120 * Math.cos(t * 0.19), b2y = 1420 + 130 * Math.sin(t * 0.23);
  return (
    <div style={{ position: 'absolute', left: 0, top: 0, width: 1080, height: 1920, transform: `scale(${escala})`, transformOrigin: '0 0', overflow: 'hidden',
                  background: 'radial-gradient(circle at 540px 860px, #5B2AB0 0, #3A1A78 320px, #1E0E42 700px, #0E081A 1150px)' }}>
      <div style={{ position: 'absolute', left: b1x - 420, top: b1y - 420, width: 840, height: 840, borderRadius: '50%', opacity: 0.32,
                    background: 'radial-gradient(circle, rgba(255,45,203,.9) 0, rgba(255,45,203,0) 70%)', filter: 'blur(30px)' }} />
      <div style={{ position: 'absolute', left: b2x - 380, top: b2y - 380, width: 760, height: 760, borderRadius: '50%', opacity: 0.18,
                    background: 'radial-gradient(circle, rgba(214,255,59,.9) 0, rgba(214,255,59,0) 70%)', filter: 'blur(36px)' }} />
      <div style={{ position: 'absolute', inset: 0, opacity: 0.18, backgroundSize: '22px 22px',
                    backgroundImage: 'radial-gradient(circle, rgba(255,255,255,.35) 1px, transparent 1.6px)' }} />
    </div>
  );
};
type Motor = ReturnType<typeof crearMotor>;

let fuentes: Promise<void> | null = null;
const cargar = () => {
  fuentes = fuentes || Promise.all(FUENTES_KIT.map(async ([n, f, d]) => {
    const ff = new FontFace(n, `url(${staticFile(f)})`, d);
    await ff.load();
    document.fonts.add(ff);
  })).then(() => undefined);
  return fuentes;
};

const imagenesListas = (raiz: HTMLElement) => Promise.all([...raiz.querySelectorAll('img')].map(i => (i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; }))));

const montar = (raiz: HTMLElement, tema: string, imagenes: Record<string, string>, codigo: string, L: Record<string, unknown>, escena: Llamada[]): Motor => {
  const img = (s: string) => (s && imagenes[s]) || (s && /^(data:|https?:)/.test(s) ? s : s ? staticFile(s) : '');
  const m = crearMotor(raiz, tema, img);
  if (codigo) {
    const nombres = Object.keys(m.api);
    // eslint-disable-next-line no-new-func
    new Function(...nombres, 'L', codigo)(...nombres.map(k => (m.api as Record<string, unknown>)[k]), L);
  }
  for (const ll of escena) {
    const f = (m.api as Record<string, (...x: unknown[]) => unknown>)[ll.fn];
    let a = ll.a || {};
    const g = a.glide as { t?: number; dy?: number } | undefined;
    if (g && typeof g === 'object') {         // el «glide» del kit (escenas.js: t => 430 * spring((t - 8.0) / .65, .75, 7.6)), desde JSON
      const sp = (m.api as unknown as { spring: (p: number, z?: number, w?: number) => number }).spring;
      a = { ...a, glide: (t: number) => Number(g.dy || 0) * sp((t - Number(g.t || 0)) / 0.65, 0.75, 7.6) };
    }
    if (ll.fn === 'tarjetasProducto' && Array.isArray(a.contenidos)) {   // contenidos desde JSON: {img} | {grande, kick, sub, icono} | {texto, sub, icono}
      const api = m.api as unknown as Record<string, (...x: unknown[]) => string>;
      a = { ...a, contenidos: (a.contenidos as Record<string, string>[]).map(c => (typeof c === 'string' ? c
        : c.img ? api.prodImg(c.img) : c.grande ? api.prodGrande(c.grande, c.kick || '', c.sub || '', c.icono || 'cal') : api.prodTexto(c.texto || '', c.sub || '', c.icono || 'pin'))) };
    }
    if (typeof f !== 'function') continue;
    const antes = new Set(Array.from(raiz.children));
    f(...(ll.args || [a]));
    const e = Number(ll.escala || 0);
    if (e && Math.abs(e - 1) > 1e-3) {      // v5.5.17 (Motions completo del Tema 1): la pieza, más grande desde (cx, cy); su animación no cambia
      const nuevos = Array.from(raiz.children).filter(n => !antes.has(n));
      if (nuevos.length) {
        const caja = document.createElement('div');
        caja.style.cssText = `position:absolute;left:0;top:0;width:1080px;height:1920px;transform:scale(${e});`
          + `transform-origin:${Number(ll.cx ?? 540)}px ${Number(ll.cy ?? 960)}px;pointer-events:none;`;
        raiz.appendChild(caja);
        nuevos.forEach(n => caja.appendChild(n));
      }
    }
  }
  return m;
};

export const KitNeon: React.FC<KitNeonProps> = ({ escena = [], codigo = '', L = {}, imagenes = {}, t0 = 0, tema = 'neon', subs = 5, fondo = '' }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const n = Math.max(1, Math.min(8, Math.round(subs)));
  const raices = useRef<(HTMLDivElement | null)[]>([]);
  const capas = useRef<(HTMLDivElement | null)[]>([]);
  const motores = useRef<Motor[]>([]);
  const t = frame / fps + t0;
  const tRef = useRef(t);
  tRef.current = t;
  const [listo, setListo] = useState(false);
  const [h] = useState(() => delayRender('kit neón'));

  const pintar = (tt: number) => {
    const ms = motores.current;
    if (!ms.length) return;
    // los instantes del obturador de 180° alrededor del fotograma (el kit: t + SHUTTER * (k + 0.5) / SUB, SHUTTER = 0,5 / fps)
    const firmas = ms.map((m, k) => m.render(n > 1 ? tt + (0.5 / fps) * (k + 0.5) / n : tt));
    // v5.5.18: la MEDIA de verdad de los subfotogramas: cada copia a 1/N con mezcla aditiva («plus-lighter» suma color y alfa
    // premultiplicados) dentro de un grupo aislado. Antes se apilaban encima (1, 1/2, 1/3…): sobre fondo transparente eso ENGORDA el alfa de
    // sombras, brillos y bordes mientras hay movimiento y lo adelgaza de golpe al parar (−13 % de tinta medido): sombras que se pierden,
    // letras que tiemblan y un tirón cada vez que el texto se queda quieto o empieza a salir. Y SIEMPRE la misma mezcla (también quieto):
    // cambiar de una copia a la media redondeaba distinto los bordes finos (−5 % en «¿VIVES O ESTÁS»: las letras pequeñas «respiraban»)
    const quieto = n <= 1 && firmas.every(f => f === firmas[0]);
    const N = Math.max(1, ms.length);
    capas.current.forEach((c, k) => {
      if (!c) return;
      c.style.opacity = quieto ? (k === 0 ? '1' : '0') : (1 / N).toFixed(5);
      c.style.mixBlendMode = quieto ? 'normal' : 'plus-lighter';
      // v5.5.17: OCULTAS con visibility (no display:none): oculta, la copia no tiene medidas y el aro de un caption se medía 0 × 0 =
      // un aro pequeño suelto en la esquina que salía al moverse el texto (la salida), cuando estas copias se ven
      c.style.visibility = quieto && k > 0 ? 'hidden' : 'visible';
    });
  };

  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        await cargar();
        await document.fonts.ready;
        if (!vivo) return;
        motores.current = raices.current.slice(0, n).filter((r): r is HTMLDivElement => !!r).map(r => montar(r, tema, imagenes, codigo, L, escena));
        await Promise.all(raices.current.filter((r): r is HTMLDivElement => !!r).map(imagenesListas));
        pintar(tRef.current);
        setListo(true);
      } finally {
        continueRender(h);
      }
    })();
    return () => { vivo = false; };
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  useLayoutEffect(() => {
    if (listo) pintar(t);
  }, [listo, t]);  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <AbsoluteFill style={{ backgroundColor: fondo ? '#0E081A' : 'transparent' }}>
      <style>{BASE + (TEMA_CSS[tema] || TEMA_CSS.neon)}</style>
      {fondo === 'neon' && <FondoNeon t={t} escala={width / 1080} />}
      <div style={{ position: 'absolute', inset: 0, isolation: 'isolate' }}>
        {Array.from({ length: n }, (_, k) => (
          <div key={k} ref={el => { capas.current[k] = el; }}
               style={{ position: 'absolute', left: 0, top: 0, width: 1080, height: 1920, transform: `scale(${width / 1080})`, transformOrigin: '0 0' }}>
            <div className="st" ref={el => { raices.current[k] = el; }} />
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
