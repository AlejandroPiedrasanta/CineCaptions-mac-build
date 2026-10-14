// CineCaptions · By Cinema Productions
// 1_codigo/remotion/empaquetar.mjs — prepara las animaciones Remotion para el programa: copia los medios (fuentes OFL, mapa, banderas, iconos 3D)
// a public/ y empaqueta el proyecto (webpack) en 2_recursos/edicion_pro/remotion/bundle, que es lo que usa render.mjs en el PC del usuario.
//     node empaquetar.mjs
import { bundle } from '@remotion/bundler';
import { cpSync, mkdirSync, rmSync, existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(AQUI, '..', '..');
const PRO = path.join(RAIZ, '2_recursos', 'edicion_pro');
const PUBLICO = path.join(AQUI, 'public');
const SALIDA = path.join(PRO, 'remotion', 'bundle');

rmSync(PUBLICO, { recursive: true, force: true });
mkdirSync(PUBLICO, { recursive: true });
cpSync(path.join(PRO, 'ograf', 'lib', 'fonts'), path.join(PUBLICO, 'fuentes'), { recursive: true });
// Tema 5 (skill «Edit VIRAL Reels»): sans Inter + serif cursiva DM Serif Text (OFL, de 2_recursos/fonts)
for (const [o, d] of [['Inter_18pt-Regular.ttf', 'inter-400.ttf'], ['Inter_18pt-Medium.ttf', 'inter-500.ttf'], ['Inter_24pt-Bold.ttf', 'inter-700.ttf'],
                      ['DMSerifText-Italic.ttf', 'dmserif-i.ttf']]) cpSync(path.join(RAIZ, '2_recursos', 'fonts', o), path.join(PUBLICO, 'fuentes', d));
cpSync(path.join(PRO, 'mapa'), path.join(PUBLICO, 'mapa'), { recursive: true });
cpSync(path.join(PRO, 'ograf', 'lib', 'iconos3d'), path.join(PUBLICO, 'iconos3d'), { recursive: true });
cpSync(path.join(RAIZ, '2_recursos', 'emojis', 'png'), path.join(PUBLICO, 'stickers'), { recursive: true, filter: f => !f.endsWith('desktop.ini') });
// v5.4.52: emojis ANIMADOS (Noto Emoji Animation de Google, Lottie, CC BY 4.0): los usa Emoji.tsx (si no hay, el PNG de stickers/)
cpSync(path.join(PRO, 'lottie'), path.join(PUBLICO, 'lottie'), { recursive: true });
// v5.5.3: los «recortes de revista» del RecorteK (trama / color / línea de neón), sacados de Fluent con herramientas_dev/generar_recortes.py
cpSync(path.join(PRO, 'recortes'), path.join(PUBLICO, 'recortes'), { recursive: true });
// v5.5.3: las escenas a pantalla completa (Escenas9.tsx): más Fluent 3D (MIT) y fuentes manuscrita / máquina / estarcido / condensada (OFL, Apache)
cpSync(path.join(PRO, 'fluent_extra'), path.join(PUBLICO, 'fluent'), { recursive: true, filter: f => !f.endsWith('desktop.ini') });
for (const [o, d] of [['Caveat.ttf', 'caveat.ttf'], ['SpecialElite-Regular.ttf', 'especial.ttf'], ['BlackOpsOne-Regular.ttf', 'estarcido.ttf'], ['Anton-Regular.ttf', 'anton.ttf']])
  cpSync(path.join(PRO, 'fuentes_extra', o), path.join(PUBLICO, 'fuentes', d));
if (existsSync(SALIDA)) rmSync(SALIDA, { recursive: true, force: true });
const t0 = Date.now();
const serve = await bundle({ entryPoint: path.join(AQUI, 'src', 'index.ts'), publicDir: PUBLICO, outDir: SALIDA, enableCaching: false,
                            webpackOverride: (c) => ({ ...c, devtool: false }) });   // sin mapas de fuente: el bundle va en el instalador
console.log(JSON.stringify({ bundle: serve, s: (Date.now() - t0) / 1000 }));
