// CineCaptions · By Cinema Productions
// 1_codigo/remotion/galeria.mjs — un fotograma de cada plantilla del catálogo (para revisarlas o enseñarlas): node galeria.mjs <galeria.json>
// galeria.json = {"bundle", "navegador", "fondo": imagen de fondo opcional, "trabajos": [{"id", "props", "frame", "salida": .png}]}
import { openBrowser, renderStill, selectComposition } from '@remotion/renderer';
import { readFileSync, existsSync } from 'node:fs';

const g = JSON.parse(readFileSync(process.argv[2], 'utf8'));
// v5.53: el navegador como en render.mjs (gl 'angle' en Windows; si no abre o una plantilla falla con él, sin gl), para que las previas salgan
// iguales que lo que renderiza el programa. CC_REMOTION_GL=no la apaga.
const pedido = process.env.CC_REMOTION_GL;
const GL = pedido === 'no' ? undefined : (pedido || (process.platform === 'win32' ? 'angle' : undefined));
const abrir = (gl) => openBrowser('chrome', { ...(g.navegador && existsSync(g.navegador) ? { browserExecutable: g.navegador } : {}),
                                               ...(gl ? { chromiumOptions: { gl } } : {}) });
let nav = GL ? await abrir(GL).catch(() => null) : null;
let gl = nav ? GL : undefined;
if (!nav) nav = await abrir(undefined);
const hacer = async (t) => {
  const composition = await selectComposition({ serveUrl: g.bundle, id: t.id, inputProps: t.props, puppeteerInstance: nav });
  await renderStill({ composition, serveUrl: g.bundle, output: t.salida, frame: Math.min(composition.durationInFrames - 1, t.frame), inputProps: t.props,
                      puppeteerInstance: nav, imageFormat: 'png', logLevel: 'error' });
  console.log(JSON.stringify({ hecho: t.salida }));
};
const fallidos = [];
for (const t of g.trabajos) {
  try {
    await hacer(t);
  } catch (e) {
    if (gl) fallidos.push(t); else console.log(JSON.stringify({ error: String(e && e.message || e).slice(0, 300), id: t.id }));
  }
}
if (fallidos.length) {
  await nav.close({ silent: true }).catch(() => {});
  gl = undefined;
  nav = await abrir(undefined);
  for (const t of fallidos) {
    try {
      await hacer(t);
    } catch (e) {
      console.log(JSON.stringify({ error: String(e && e.message || e).slice(0, 300), id: t.id }));
    }
  }
}
await nav.close({ silent: true }).catch(() => {});
