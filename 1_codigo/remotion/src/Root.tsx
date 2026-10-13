// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/Root.tsx — las composiciones de la Edición PRO. El tamaño, los fps y la duración llegan en las props
// (`_ancho`, `_alto`, `_fps`, `_dur`): las pone el programa con los del timeline de Resolve.
import { Composition } from 'remotion';
import { Ubicacion } from './Ubicacion';
import { Capitulos, Comentario, Encuesta, Fecha, Ninas, Pareja, Pastilla, Saludo, Sesion, Titulo } from './Plantillas';
import { Grafica, Interruptor, Notificacion, Pasos, Tarjeta } from './Saas';
import { Subtitulo } from './Subtitulo';
import { DeslizadorT5, EscenaT5, PasosT5 } from './Skill';
import { AcompananteT5, VeloCaptionT } from './Acompanantes';
import { FinalT5, OrbitaT5, StickerT5, TarjetaT5 } from './Efectos5';
import { EditorialT6 } from './Editorial6';

const PLANTILLAS: Record<string, React.FC<any>> = { PasosT5, DeslizadorT5, EscenaT5, AcompananteT5, VeloCaptionT, TarjetaT5, OrbitaT5, StickerT5, FinalT5, EditorialT6, Titulo, Saludo, Capitulos, Fecha, Pareja, Pastilla, Encuesta, Comentario, Sesion, Ninas, Notificacion, Tarjeta, Grafica, Pasos, Interruptor };

type Meta = { _ancho?: number; _alto?: number; _fps?: number; _dur?: number };
const medida = ({ props }: { props: Record<string, unknown> & Meta }) => {
  const fps = Number(props._fps) || 30;
  return { width: Number(props._ancho) || 1080, height: Number(props._alto) || 1920, fps, durationInFrames: Math.max(2, Math.round((Number(props._dur) || 3.5) * fps)) };
};

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="Ubicacion" component={Ubicacion as React.FC<Record<string, unknown>>} width={1080} height={1920} fps={30} durationInFrames={105}
                 defaultProps={{ pais: 'gt', kicker: 'ESTAMOS EN', acento: '#c9a46a' }} calculateMetadata={medida} />
    <Composition id="Subtitulo" component={Subtitulo as React.FC<Record<string, unknown>>} width={1080} height={1920} fps={30} durationInFrames={60}
                 defaultProps={{ palabras: [{ texto: 'Esto', t: 0.05 }, { texto: 'es', t: 0.3, rol: 'context' }, { texto: 'increíble', t: 0.5, rol: 'main' }], modo: 'normal' }}
                 calculateMetadata={medida} />
    {Object.entries(PLANTILLAS).map(([id, C]) => (
      <Composition key={id} id={id} component={C} width={1080} height={1920} fps={30} durationInFrames={90} defaultProps={{ titulo: 'Casa de la novia' }} calculateMetadata={medida} />
    ))}
  </>
);
