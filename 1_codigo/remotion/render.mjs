// CineCaptions · By Cinema Productions
// render.mjs — renderiza las animaciones Remotion de la Edición PRO en el PC del usuario (lo llama 1_codigo/edicion_pro_remotion.py).
//     node render.mjs <trabajos.json>
// trabajos.json = {"bundle": carpeta empaquetada, "navegador": chrome-headless-shell (opcional), "trabajos": [{"id": composición, "props": {...},
//                  "salida": .mov}]}. Cada trabajo sale en ProRes 4444 con alfa (Resolve lo pone encima del video tal cual). Una línea JSON por
// trabajo terminado: {"hecho": salida, "s": segundos} o {"error": ..., "salida": ...}. Un solo navegador para todos (más rápido).
// v5.4.52: varios clips A LA VEZ (los captions del Tema 5/6 son decenas de clips cortos: preparar cada uno pesaba más que pintarlo).
import { openBrowser, renderMedia, selectComposition } from '@remotion/renderer';
import { readFileSync, existsSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const tareas = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const serveUrl = tareas.bundle;
// v5.53: CON LA GPU. Hasta ahora el navegador se abría sin gl (el chromiumOptions de renderMedia no cuenta cuando se le pasa puppeteerInstance)
// y Chrome pintaba por software, con todos los núcleos: en Windows se abre con gl 'angle' (D3D11), ~3× más rápido. Si no abre, como antes (sin
// gl). Los clips que fallen con la GPU se repiten AL FINAL con un navegador sin gl (el compartido no se cierra a mitad: lo usan 2-4 clips a la
// vez). CC_REMOTION_GL=no la apaga; otro valor lo usa como gl (pruebas).
const pedido = process.env.CC_REMOTION_GL;
const GL = pedido === 'no' ? undefined : (pedido || (process.platform === 'win32' ? 'angle' : undefined));
const abrir = (gl) => openBrowser('chrome', { ...(tareas.navegador && existsSync(tareas.navegador) ? { browserExecutable: tareas.navegador } : {}),
                                               ...(gl ? { chromiumOptions: { gl } } : {}) });
let navegador = GL ? await abrir(GL).catch(() => null) : null;
let gl = navegador ? GL : undefined;
if (!navegador) navegador = await abrir(undefined);
const nucleos = os.cpus().length;
const paralelo = Math.max(1, Math.min(4, Math.floor(nucleos / 6)));            // clips a la vez (3 en un equipo de 18-23 hilos)
const hilos = Math.max(1, Math.min(8, Math.floor(nucleos / (2 * paralelo)) + 1)); // fotogramas a la vez dentro de cada clip
const cola = [...(tareas.trabajos || [])];
const fallidos = [];
const fallo = (t, e) => console.log(JSON.stringify({ error: String(e && e.message || e).slice(0, 400), salida: t.salida }));

const hacer = async (t, nav, gl) => {
  const t0 = Date.now();
  const opciones = gl ? { chromiumOptions: { gl } } : {};
  mkdirSync(path.dirname(t.salida), { recursive: true });
  const composition = await selectComposition({ serveUrl, id: t.id, inputProps: t.props, puppeteerInstance: nav });
  if (t.opaco) {
    // v5.5.8, «Motions completo»: un video ENTERO y opaco (va encima de todo): H.264 de alta calidad (ProRes 4444 pesaría varios GB),
    // con todos los hilos para él y su avance (una línea {"progreso"} cada ~5 %)
    let ultimo = -1;
    await renderMedia({ composition, serveUrl, codec: 'h264', crf: 16, x264Preset: 'veryfast', imageFormat: 'jpeg', jpegQuality: 92,
                        pixelFormat: 'yuv420p', muted: true,   // v5.5.9: «veryfast» = misma calidad (CRF 16), menos espera
                        outputLocation: t.salida, inputProps: t.props, puppeteerInstance: nav, concurrency: Math.max(2, Math.min(16, Math.floor(nucleos / 2))),
                        overwrite: true, ...opciones, logLevel: 'error',
                        onProgress: ({ progress }) => { const p = Math.floor(progress * 20); if (p > ultimo) { ultimo = p; console.log(JSON.stringify({ progreso: progress, salida: t.salida })); } } });
  } else {
    await renderMedia({ composition, serveUrl, codec: 'prores', proResProfile: '4444', imageFormat: 'png', pixelFormat: 'yuva444p10le',
                        outputLocation: t.salida, inputProps: t.props, puppeteerInstance: nav, concurrency: hilos, overwrite: true,
                        ...opciones, logLevel: 'error' });
  }
  console.log(JSON.stringify({ hecho: t.salida, s: (Date.now() - t0) / 1000 }));
};

const trabajador = async () => {
  while (cola.length) {
    const t = cola.shift();
    try {
      await hacer(t, navegador, gl);
    } catch (e) {
      if (gl) fallidos.push(t); else fallo(t, e);
    }
  }
};
await Promise.all(Array.from({ length: paralelo }, trabajador));
if (fallidos.length) {                                   // la GPU falló en alguno: esos, de uno en uno con un navegador sin gl
  await navegador.close({ silent: true }).catch(() => {});
  gl = undefined;
  navegador = await abrir(undefined).catch((e) => { for (const t of fallidos.splice(0)) fallo(t, e); return null; });
  for (const t of fallidos) {
    try {
      await hacer(t, navegador, undefined);
    } catch (e) {
      fallo(t, e);
    }
  }
}
if (navegador) await navegador.close({ silent: true }).catch(() => {});
