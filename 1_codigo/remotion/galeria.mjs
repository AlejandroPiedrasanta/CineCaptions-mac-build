// CineCaptions · By Cinema Productions
// 1_codigo/remotion/galeria.mjs — un fotograma de cada plantilla del catálogo (para revisarlas o enseñarlas): node galeria.mjs <galeria.json>
// galeria.json = {"bundle", "navegador", "fondo": imagen de fondo opcional, "trabajos": [{"id", "props", "frame", "salida": .png}]}
import { openBrowser, renderStill, selectComposition } from '@remotion/renderer';
import { readFileSync, existsSync } from 'node:fs';

const g = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const nav = await openBrowser('chrome', g.navegador && existsSync(g.navegador) ? { browserExecutable: g.navegador } : {});
for (const t of g.trabajos) {
  try {
    const composition = await selectComposition({ serveUrl: g.bundle, id: t.id, inputProps: t.props, puppeteerInstance: nav });
    await renderStill({ composition, serveUrl: g.bundle, output: t.salida, frame: Math.min(composition.durationInFrames - 1, t.frame), inputProps: t.props,
                        puppeteerInstance: nav, imageFormat: 'png', logLevel: 'error' });
    console.log(JSON.stringify({ hecho: t.salida }));
  } catch (e) {
    console.log(JSON.stringify({ error: String(e && e.message || e).slice(0, 300), id: t.id }));
  }
}
await nav.close({ silent: true });
