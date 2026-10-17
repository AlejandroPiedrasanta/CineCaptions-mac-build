// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/Pictos3D.tsx — v5.5.9 los PICTOGRAMAS 3D (pedido del usuario con su hoja de estilo y fotogramas de referencia): dos
// maniquíes 3D sin cara, sin ropa y sin detalles —
//   · el MORADO: plástico brillante y reflectante, reflejos magenta → el crecimiento digital, la ayuda, la marca que se transforma;
//   · el BLANCO: mate, suave, gris muy claro → el cliente o su marca —
// que ilustran lo que se dice: AYUDAR a subir (el morado, de rodillas en un escalón, tira del blanco hasta arriba), APRETÓN de manos, mano en el
// HOMBRO, CRECER (suben juntos sobre una gráfica que crece), LEVANTAR la marca (el morado alza el bloque de la marca) y CELEBRAR.
// Three.js de verdad (@remotion/three): el cuerpo son segmentos entre articulaciones; brazos y piernas con IK de dos huesos (las manos se
// agarran, los pies pisan); poses por fotogramas clave con anticipación y asentamiento. Luz de contorno morada, entorno para los reflejos,
// suelo negro brillante con el reflejo morado, estelas de neón y cámara de cine. Todo determinista (useCurrentFrame), relativo a fps,
// duración y tamaño del video.
import React, { useMemo } from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion';
import { ThreeCanvas } from '@remotion/three';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { FAMILIA, clamp, useFuentes } from './comun';

type V = [number, number, number];
const v3 = (a: V) => new THREE.Vector3(a[0], a[1], a[2]);
const ARRIBA = new THREE.Vector3(0, 1, 0);
const EJE_Y = new THREE.Vector3(0, 1, 0);
const suave = (q: number) => { const x = clamp(q); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
// con asentamiento: llega, se pasa un poco y vuelve (peso creíble)
const asienta = (q: number) => { const x = clamp(q); return 1 - Math.pow(1 - x, 3) * (1 + 1.6 * x) + 0.0 * x; };

/* ---------------------------------------------------------------------------------------------------------------- el esqueleto */
const L = { torso: 0.5, cuello: 0.06, cabeza: 0.17, hombro: 0.175, cadera: 0.092, brazo: 0.285, antebrazo: 0.265, muslo: 0.44, pierna: 0.43, tobillo: 0.065 };
type Pose = {
  p: V; yaw: number; lean: number; tilt?: number; giro?: number;       // pelvis, a dónde mira (rad), inclinación del tronco adelante y de lado
  mI: V; mD: V; pI: V; pD: V;                                          // manos y tobillos (mundo)
  cI?: V; cD?: V; rI?: V; rD?: V;                                      // hacia dónde apuntan codos y rodillas (direcciones)
  mira?: V;                                                           // a dónde mira la cabeza
};
type Cuerpo = {
  pelvis: THREE.Vector3; pecho: THREE.Vector3; cabeza: THREE.Vector3; base: THREE.Matrix4;
  hI: THREE.Vector3; hD: THREE.Vector3; cI: THREE.Vector3; cD: THREE.Vector3; mI: THREE.Vector3; mD: THREE.Vector3;
  kI: THREE.Vector3; kD: THREE.Vector3; rI: THREE.Vector3; rD: THREE.Vector3; aI: THREE.Vector3; aD: THREE.Vector3; delante: THREE.Vector3;
};

/* IK de dos huesos: desde S hacia T con largos a y b; el codo/la rodilla sale hacia `polo`. → [articulación media, punta] */
const ik = (S: THREE.Vector3, T: THREE.Vector3, a: number, b: number, polo: THREE.Vector3): [THREE.Vector3, THREE.Vector3] => {
  const dv = T.clone().sub(S);
  let d = dv.length();
  const u = d > 1e-6 ? dv.multiplyScalar(1 / d) : new THREE.Vector3(0, -1, 0);
  d = Math.min(Math.max(d, Math.abs(a - b) + 1e-3), a + b - 1e-3);
  const cosA = (a * a + d * d - b * b) / (2 * a * d);
  const sinA = Math.sqrt(Math.max(0, 1 - cosA * cosA));
  let w = polo.clone().sub(u.clone().multiplyScalar(polo.dot(u)));
  if (w.lengthSq() < 1e-8) w = new THREE.Vector3(1, 0, 0).sub(u.clone().multiplyScalar(u.x));
  w.normalize();
  const E = S.clone().add(u.clone().multiplyScalar(a * cosA)).add(w.multiplyScalar(a * sinA));
  return [E, S.clone().add(u.clone().multiplyScalar(d))];
};

const montar = (P: Pose, k = 1): Cuerpo => {
  const f = new THREE.Vector3(Math.sin(P.yaw), 0, Math.cos(P.yaw));
  const izq = new THREE.Vector3().crossVectors(ARRIBA, f).normalize();         // la izquierda del personaje
  const der = izq.clone().multiplyScalar(-1);
  const espina = ARRIBA.clone().multiplyScalar(Math.cos(P.lean)).add(f.clone().multiplyScalar(Math.sin(P.lean)))
    .add(der.clone().multiplyScalar(Math.sin(P.tilt || 0))).normalize();
  const giro = new THREE.Quaternion().setFromAxisAngle(espina, P.giro || 0);
  const derP = der.clone().sub(espina.clone().multiplyScalar(der.dot(espina))).normalize().applyQuaternion(giro);
  const delanteP = new THREE.Vector3().crossVectors(espina, derP).multiplyScalar(-1).normalize();
  const pelvis = v3(P.p);
  const pecho = pelvis.clone().add(espina.clone().multiplyScalar(L.torso * k));
  const hombroC = pecho.clone().sub(espina.clone().multiplyScalar(0.05 * k));
  const hI = hombroC.clone().sub(derP.clone().multiplyScalar(L.hombro * k));
  const hD = hombroC.clone().add(derP.clone().multiplyScalar(L.hombro * k));
  const cuello = pecho.clone().add(espina.clone().multiplyScalar(L.cuello * k));
  let dirCab = espina.clone();
  if (P.mira) dirCab = dirCab.multiplyScalar(0.8).add(v3(P.mira).sub(cuello).normalize().multiplyScalar(0.35)).normalize();
  const cabeza = cuello.clone().add(dirCab.multiplyScalar(L.cabeza * k));
  const atras = delanteP.clone().multiplyScalar(-1);
  const [cI, mI] = ik(hI, v3(P.mI), L.brazo * k, L.antebrazo * k, P.cI ? v3(P.cI) : atras.clone().add(izq.clone().multiplyScalar(0.35)).add(espina.clone().multiplyScalar(-0.3)));
  const [cD, mD] = ik(hD, v3(P.mD), L.brazo * k, L.antebrazo * k, P.cD ? v3(P.cD) : atras.clone().add(der.clone().multiplyScalar(0.35)).add(espina.clone().multiplyScalar(-0.3)));
  const kI = pelvis.clone().sub(derP.clone().multiplyScalar(L.cadera * k)).sub(espina.clone().multiplyScalar(0.03 * k));
  const kD = pelvis.clone().add(derP.clone().multiplyScalar(L.cadera * k)).sub(espina.clone().multiplyScalar(0.03 * k));
  const [rI, aI] = ik(kI, v3(P.pI), L.muslo * k, L.pierna * k, P.rI ? v3(P.rI) : f.clone().add(izq.clone().multiplyScalar(0.1)));
  const [rD, aD] = ik(kD, v3(P.pD), L.muslo * k, L.pierna * k, P.rD ? v3(P.rD) : f.clone().add(der.clone().multiplyScalar(0.1)));
  const base = new THREE.Matrix4().makeBasis(derP, espina, delanteP);
  return { pelvis, pecho, cabeza, base, hI, hD, cI, cD, mI, mD, kI, kD, rI, rD, aI, aD, delante: f };
};

/* ---------------------------------------------------------------------------------------------------------------- el cuerpo */
const unidad = new THREE.CylinderGeometry(1, 1, 1, 28, 1, true);
const esfera = new THREE.SphereGeometry(1, 40, 28);
const torsoGeo = (() => {
  const perfil = [[0.0, -0.07], [0.1, -0.065], [0.15, -0.02], [0.155, 0.04], [0.135, 0.13], [0.122, 0.2], [0.135, 0.29], [0.162, 0.38], [0.168, 0.44],
                  [0.15, 0.5], [0.1, 0.545], [0.04, 0.565], [0.0, 0.57]].map(([x, y]) => new THREE.Vector2(x, y));
  return new THREE.LatheGeometry(perfil, 48);
})();

const Hueso: React.FC<{ a: THREE.Vector3; b: THREE.Vector3; r1: number; r2: number; mat: THREE.Material }> = ({ a, b, r1, r2, mat }) => {
  const d = b.clone().sub(a);
  const largo = d.length();
  const q = new THREE.Quaternion().setFromUnitVectors(EJE_Y, d.clone().normalize());
  const geo = useMemo(() => new THREE.CylinderGeometry(r2, r1, 1, 28, 1, true), [r1, r2]);
  return <mesh geometry={geo} material={mat} position={a.clone().add(b).multiplyScalar(0.5)} quaternion={q} scale={[1, Math.max(1e-4, largo), 1]} castShadow />;
};
const Bola: React.FC<{ c: THREE.Vector3; r: number | V; mat: THREE.Material; q?: THREE.Quaternion }> = ({ c, r, mat, q }) => (
  <mesh geometry={esfera} material={mat} position={c} scale={typeof r === 'number' ? [r, r, r] : r} quaternion={q} castShadow />
);

/* un maniquí: torso torneado, cabeza ovalada, brazos y piernas que se afinan, manos y pies redondeados; sin cara ni ropa */
const Maniqui: React.FC<{ c: Cuerpo; mat: THREE.Material; k?: number }> = ({ c, mat, k = 1 }) => {
  const qT = new THREE.Quaternion().setFromRotationMatrix(c.base);
  const dirMano = (h: THREE.Vector3, m: THREE.Vector3) => m.clone().sub(h).normalize();
  const mano = (codo: THREE.Vector3, m: THREE.Vector3) => {
    const d = dirMano(codo, m);
    return { c: m.clone().add(d.clone().multiplyScalar(0.055 * k)), q: new THREE.Quaternion().setFromUnitVectors(EJE_Y, d) };
  };
  const pie = (a: THREE.Vector3) => {
    const f = c.delante.clone();
    return { c: a.clone().add(f.clone().multiplyScalar(0.07 * k)).add(new THREE.Vector3(0, -0.035 * k, 0)),
             q: new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), f) };
  };
  const MI = mano(c.cI, c.mI), MD = mano(c.cD, c.mD), PI = pie(c.aI), PD = pie(c.aD);
  const cuello0 = c.pecho.clone().add(c.cabeza.clone().sub(c.pecho).multiplyScalar(0.15));
  return (
    <group>
      <mesh geometry={torsoGeo} material={mat} position={c.pelvis} quaternion={qT} scale={[k * 1.04, k * (L.torso / 0.5), k * 0.74]} castShadow />
      <Bola c={c.pelvis.clone().add(new THREE.Vector3(0, -0.01, 0))} r={[0.158 * k, 0.11 * k, 0.118 * k]} mat={mat} q={qT} />
      <Hueso a={cuello0} b={c.cabeza} r1={0.046 * k} r2={0.042 * k} mat={mat} />
      <Bola c={c.cabeza} r={[0.13 * k, 0.156 * k, 0.14 * k]} mat={mat} q={qT} />
      {/* brazos */}
      <Bola c={c.hI} r={0.07 * k} mat={mat} /><Bola c={c.hD} r={0.07 * k} mat={mat} />
      <Hueso a={c.hI} b={c.cI} r1={0.066 * k} r2={0.05 * k} mat={mat} /><Hueso a={c.hD} b={c.cD} r1={0.066 * k} r2={0.05 * k} mat={mat} />
      <Bola c={c.cI} r={0.05 * k} mat={mat} /><Bola c={c.cD} r={0.05 * k} mat={mat} />
      <Hueso a={c.cI} b={c.mI} r1={0.05 * k} r2={0.038 * k} mat={mat} /><Hueso a={c.cD} b={c.mD} r1={0.05 * k} r2={0.038 * k} mat={mat} />
      <Bola c={c.mI} r={0.038 * k} mat={mat} /><Bola c={c.mD} r={0.038 * k} mat={mat} />
      <Bola c={MI.c} r={[0.045 * k, 0.074 * k, 0.03 * k]} mat={mat} q={MI.q} /><Bola c={MD.c} r={[0.045 * k, 0.074 * k, 0.03 * k]} mat={mat} q={MD.q} />
      {/* piernas */}
      <Bola c={c.kI} r={0.092 * k} mat={mat} /><Bola c={c.kD} r={0.092 * k} mat={mat} />
      <Hueso a={c.kI} b={c.rI} r1={0.095 * k} r2={0.068 * k} mat={mat} /><Hueso a={c.kD} b={c.rD} r1={0.095 * k} r2={0.068 * k} mat={mat} />
      <Bola c={c.rI} r={0.068 * k} mat={mat} /><Bola c={c.rD} r={0.068 * k} mat={mat} />
      <Hueso a={c.rI} b={c.aI} r1={0.066 * k} r2={0.046 * k} mat={mat} /><Hueso a={c.rD} b={c.aD} r1={0.066 * k} r2={0.046 * k} mat={mat} />
      <Bola c={c.aI} r={0.046 * k} mat={mat} /><Bola c={c.aD} r={0.046 * k} mat={mat} />
      <Bola c={PI.c} r={[0.05 * k, 0.042 * k, 0.118 * k]} mat={mat} q={PI.q} /><Bola c={PD.c} r={[0.05 * k, 0.042 * k, 0.118 * k]} mat={mat} q={PD.q} />
    </group>
  );
};

/* ---------------------------------------------------------------------------------------------------------------- poses y claves */
const mezclaV = (a: V, b: V, q: number): V => [a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q, a[2] + (b[2] - a[2]) * q];
const mezclaN = (a: number | undefined, b: number | undefined, q: number) => (a || 0) + ((b || 0) - (a || 0)) * q;
const mezclaPose = (A: Pose, B: Pose, q: number): Pose => {
  const o = (x?: V, y?: V) => (x && y ? mezclaV(x, y, q) : (q < 0.5 ? x : y) || x || y);
  return { p: mezclaV(A.p, B.p, q), yaw: mezclaN(A.yaw, B.yaw, q), lean: mezclaN(A.lean, B.lean, q), tilt: mezclaN(A.tilt, B.tilt, q), giro: mezclaN(A.giro, B.giro, q),
           mI: mezclaV(A.mI, B.mI, q), mD: mezclaV(A.mD, B.mD, q), pI: mezclaV(A.pI, B.pI, q), pD: mezclaV(A.pD, B.pD, q),
           cI: o(A.cI, B.cI), cD: o(A.cD, B.cD), rI: o(A.rI, B.rI), rD: o(A.rD, B.rD), mira: o(A.mira, B.mira) };
};
type Clave = { t: number; m: Pose; b: Pose; ease?: 'suave' | 'asienta' };
const enClaves = (C: Clave[], t: number) => {
  if (t <= C[0].t) return { m: C[0].m, b: C[0].b };
  for (let i = 0; i < C.length - 1; i++) {
    const a = C[i], z = C[i + 1];
    if (t <= z.t) {
      const q0 = (t - a.t) / Math.max(1e-6, z.t - a.t);
      const q = z.ease === 'asienta' ? asienta(q0) : suave(q0);
      return { m: mezclaPose(a.m, z.m, q), b: mezclaPose(a.b, z.b, q) };
    }
  }
  const u = C[C.length - 1];
  return { m: u.m, b: u.b };
};

// de pie, relajado, en (x, z), mirando a yaw; `alto` = el suelo
const dePie = (x: number, z: number, yaw: number, alto = 0, k = 1, extra: Partial<Pose> = {}): Pose => {
  const f = [Math.sin(yaw), 0, Math.cos(yaw)];
  const l = [Math.cos(yaw), 0, -Math.sin(yaw)];                        // la izquierda
  const P = (dl: number, dy: number, df: number): V => [x + l[0] * dl * k + f[0] * df * k, alto + dy * k, z + l[2] * dl * k + f[2] * df * k];
  return { p: P(0, 0.93, 0), yaw, lean: 0.02, mI: P(0.23, 0.56, 0.03), mD: P(-0.23, 0.56, 0.03), pI: P(0.1, 0.07, 0), pD: P(-0.1, 0.07, 0), ...extra };
};
const desde = (yaw: number, k = 1) => {                                // para poner manos/pies relativos a un punto y la orientación
  const f = [Math.sin(yaw), 0, Math.cos(yaw)], l = [Math.cos(yaw), 0, -Math.sin(yaw)];
  return (o: V, dl: number, dy: number, df: number): V => [o[0] + l[0] * dl * k + f[0] * df * k, o[1] + dy * k, o[2] + l[2] * dl * k + f[2] * df * k];
};

/* ---------------------------------------------------------------------------------------------------------------- las acciones */
type Accion = { claves: Clave[]; escalon?: number; grafica?: boolean; bloque?: boolean; cam: { t: number; pos: V; mira: V }[]; k: number };
const PI2 = Math.PI / 2;
const KB = 0.94;                                                        // el blanco, un poco más bajo (como en la hoja de estilo)

const AYUDAR = (): Accion => {
  // escalón de 0,62 m: borde en x = 0 (arriba, x > 0). El morado, de rodillas arriba mirando al borde (−x); el blanco, abajo, trepando.
  const H = 0.62;
  const ym = -PI2, yb = PI2;
  const M = desde(ym), B = desde(yb, KB);
  const agarre0: V = [0.06, 0.92, 0.04], agarre1: V = [0.2, 1.3, 0.03], agarre2: V = [0.42, 1.62, 0.02];
  const mRodilla = (lean: number, p: V, mano: V, extra: Partial<Pose> = {}): Pose => ({
    p, yaw: ym, lean, mI: M(p, 0.25, -0.35, 0.05), mD: mano, pI: [0.36, H + 0.07, 0.18], pD: [0.92, H + 0.11, -0.12], rD: [0, -1, 0], rI: [-1, 0.2, 0], mira: [-0.4, 0.6, 0], ...extra });
  const bTrepa = (p: V, mano: V, pI: V, pD: V, lean: number, extra: Partial<Pose> = {}): Pose => ({
    p, yaw: yb, lean, mI: mano, mD: B(p, -0.26, -0.2, 0.06), pI, pD, rI: [1, 0.3, 0], rD: [1, -0.2, 0], mira: [0.4, 1.4, 0], ...extra });
  const claves: Clave[] = [
    { t: 0.0, m: mRodilla(0.55, [0.62, H + 0.5, 0.02], M([0.62, H + 1.0, 0], -0.1, -0.15, 0.32)),
               b: bTrepa([-0.26, 0.66, 0.06], [-0.06, 1.3, 0.12], [-0.04, 0.42, 0.15], [-0.2, 0.2, -0.12], 0.42, { mD: [0.03, H + 0.03, -0.16] }) },
    { t: 0.16, m: mRodilla(0.95, [0.58, H + 0.46, 0.02], agarre0), b: bTrepa([-0.24, 0.68, 0.06], agarre0, [-0.04, 0.42, 0.15], [-0.2, 0.2, -0.12], 0.45, { mD: [0.03, H + 0.03, -0.16] }), ease: 'asienta' },
    { t: 0.26, m: mRodilla(1.0, [0.6, H + 0.45, 0.02], agarre0, { lean: 1.05 }), b: bTrepa([-0.24, 0.65, 0.06], agarre0, [-0.04, 0.42, 0.15], [-0.2, 0.2, -0.12], 0.48, { mD: [0.03, H + 0.03, -0.16] }) },
    { t: 0.44, m: mRodilla(0.55, [0.78, H + 0.55, 0.02], agarre1), b: bTrepa([-0.24, 0.92, 0.05], agarre1, [0.1, H + 0.07, 0.12], [-0.08, 0.32, -0.06], 0.45) },
    { t: 0.6, m: { ...dePie(1.0, 0.0, ym, H), lean: -0.12, mD: agarre2, mI: M([1.0, H + 0.93, 0], 0.24, -0.38, 0.0) },
              b: bTrepa([0.2, H + 0.78, 0.04], agarre2, [0.22, H + 0.07, 0.12], [0.12, H + 0.1, -0.08], 0.32), ease: 'asienta' },
    { t: 0.72, m: dePie(1.05, 0.0, ym, H), b: dePie(0.38, 0.02, yb, H, KB), ease: 'asienta' },
  ];
  // apretón de manos y, al final, el morado le pasa el brazo por el hombro y miran al frente
  const apr: V = [0.72, H + 1.08, 0.0];
  claves.push({ t: 0.82, m: { ...dePie(1.02, 0.0, ym, H), mD: apr, lean: 0.06 }, b: { ...dePie(0.4, 0.02, yb, H, KB), mD: apr, lean: 0.06 } });
  claves.push({ t: 0.88, m: { ...dePie(1.02, 0.0, ym, H), mD: [0.72, H + 1.02, 0.0], lean: 0.06 }, b: { ...dePie(0.4, 0.02, yb, H, KB), mD: [0.72, H + 1.02, 0.0], lean: 0.06 } });
  claves.push({ t: 0.93, m: { ...dePie(1.02, 0.0, ym, H), mD: apr, lean: 0.06 }, b: { ...dePie(0.4, 0.02, yb, H, KB), mD: apr, lean: 0.06 } });
  claves.push({ t: 1.0, m: dePie(1.04, 0.0, ym, H), b: dePie(0.4, 0.02, yb, H, KB) });
  return { claves, escalon: H, k: 1, cam: [{ t: 0, pos: [-2.1, 2.05, 3.3], mira: [0.2, 0.78, 0] }, { t: 1, pos: [-1.7, 2.25, 3.6], mira: [0.5, 1.05, 0] }] };
};

const APRETON = (): Accion => {
  const ym = -PI2 + 0.25, yb = PI2 - 0.25;
  const m0 = dePie(0.78, -0.06, ym), b0 = dePie(-0.76, 0.06, yb, 0, KB);
  const m1 = dePie(0.36, -0.08, ym), b1 = dePie(-0.34, 0.08, yb, 0, KB);
  const apr: V = [0.0, 1.02, 0.0];
  const pasoM = (q: number): Pose => mezclaPose(m0, m1, q), pasoB = (q: number): Pose => mezclaPose(b0, b1, q);
  const anda = (P: Pose, fase: number, yaw: number): Pose => {     // un paso: el pie de delante se levanta y avanza; el cuerpo sube y baja
    const s = Math.sin(fase * Math.PI);
    const f = [Math.sin(yaw), 0, Math.cos(yaw)];
    return { ...P, p: [P.p[0], P.p[1] + 0.025 * s, P.p[2]], pI: [P.pI[0] + f[0] * 0.12 * s, P.pI[1] + 0.09 * s, P.pI[2] + f[2] * 0.12 * s], lean: 0.08 };
  };
  const claves: Clave[] = [
    { t: 0, m: m0, b: b0 },
    { t: 0.18, m: anda(pasoM(0.45), 1, ym), b: anda(pasoB(0.45), 1, yb) },
    { t: 0.34, m: pasoM(1), b: pasoB(1), ease: 'asienta' },
    { t: 0.46, m: { ...m1, mD: apr, lean: 0.1, mira: [0, 1.5, 0] }, b: { ...b1, mD: apr, lean: 0.1, mira: [0, 1.45, 0] }, ease: 'asienta' },
    { t: 0.56, m: { ...m1, mD: [0, 0.95, 0], lean: 0.1 }, b: { ...b1, mD: [0, 0.95, 0], lean: 0.1 } },
    { t: 0.66, m: { ...m1, mD: apr, lean: 0.1 }, b: { ...b1, mD: apr, lean: 0.1 } },
    { t: 0.76, m: { ...m1, mD: [0, 0.96, 0], lean: 0.08 }, b: { ...b1, mD: [0, 0.96, 0], lean: 0.08 } },
    { t: 0.9, m: { ...m1, mD: apr, lean: 0.06 }, b: { ...b1, mD: apr, lean: 0.06 } },
    { t: 1.0, m: { ...m1, mD: apr }, b: { ...b1, mD: apr } },
  ];
  return { claves, k: 1, cam: [{ t: 0, pos: [-0.9, 1.25, 3.7], mira: [0, 1.0, 0] }, { t: 1, pos: [0.7, 1.35, 3.2], mira: [0, 1.05, 0] }] };
};

const HOMBRO = (alto = 0, sube = 0): Accion => {
  // el morado pasa el brazo por los hombros del blanco; los dos miran al frente (a cámara) y respiran
  const ym = -0.22, yb = 0.1;
  const m = dePie(0.24, -0.04, ym, alto), b = dePie(-0.22, 0.06, yb, alto, KB);
  const hombroB: V = [-0.4, alto + 1.36, 0.0];
  const claves: Clave[] = [
    { t: 0, m: { ...m, mira: [0, 1.4 + alto, 4] }, b: { ...b, mira: [0, 1.4 + alto, 4] } },
    { t: 0.3, m: { ...m, mI: hombroB, lean: 0.03, tilt: -0.08, giro: 0.25, cI: [0.2, 0.3, -1], mira: [-0.5, 1.4 + alto, 3] }, b: { ...b, mira: [0.6, 1.5 + alto, 3] }, ease: 'asienta' },
    { t: 0.6, m: { ...m, mI: hombroB, lean: 0.0, tilt: -0.09, giro: 0.25, cI: [0.2, 0.3, -1], mira: [0, 1.5 + alto, 4] }, b: { ...b, lean: -0.02, mira: [0, 1.5 + alto, 4] } },
    { t: 1, m: { ...m, mI: hombroB, lean: 0.01, tilt: -0.08, giro: 0.25, cI: [0.2, 0.3, -1], mira: [0, 1.5 + alto, 4] }, b: { ...b, lean: 0.0, mira: [0, 1.5 + alto, 4] } },
  ];
  return { claves, k: 1, grafica: sube > 0, cam: [{ t: 0, pos: [0.25, 1.15 + alto * 0.6, 3.6], mira: [0, 1.05 + alto * 0.8, 0] }, { t: 1, pos: [-0.35, 1.05 + alto, 3.0], mira: [0, 1.1 + alto, 0] }] };
};

const CELEBRAR = (): Accion => {
  // los dos saltan: el morado alza la mano del blanco (la marca gana)
  const ym = -0.35, yb = 0.35;
  const m = dePie(0.22, 0, ym), b = dePie(-0.22, 0.03, yb, 0, KB);
  const alza: V = [0.0, 1.92, 0.08];
  const salto = (P: Pose, h: number, brazo?: V): Pose => ({ ...P, p: [P.p[0], P.p[1] + h, P.p[2]], pI: [P.pI[0], P.pI[1] + h + 0.05, P.pI[2] - 0.05],
                                                               pD: [P.pD[0], P.pD[1] + h + 0.08, P.pD[2] - 0.08], ...(brazo ? { mI: brazo } : {}) });
  const agacha = (P: Pose): Pose => ({ ...P, p: [P.p[0], P.p[1] - 0.12, P.p[2]], lean: 0.25 });
  const claves: Clave[] = [
    { t: 0, m, b },
    { t: 0.14, m: agacha(m), b: agacha(b) },
    { t: 0.34, m: { ...salto(m, 0.26, alza), mD: [0.62, 1.86, 0.1], cD: [1, 0.2, -0.5] }, b: { ...salto(b, 0.22), mD: alza, mI: [-0.6, 1.8, 0.1], cI: [-1, 0.2, -0.5] }, ease: 'asienta' },
    { t: 0.52, m: { ...m, mI: alza, mD: [0.6, 1.8, 0.1], cD: [1, 0.2, -0.5] }, b: { ...b, mD: alza, mI: [-0.58, 1.75, 0.1], cI: [-1, 0.2, -0.5] }, ease: 'asienta' },
    { t: 0.64, m: { ...agacha(m), mI: [0.05, 1.7, 0.1], mD: [0.5, 1.6, 0.1] }, b: { ...agacha(b), mD: [-0.05, 1.7, 0.1], mI: [-0.5, 1.6, 0.1] } },
    { t: 0.82, m: { ...salto(m, 0.22, alza), mD: [0.62, 1.86, 0.1], cD: [1, 0.2, -0.5] }, b: { ...salto(b, 0.18), mD: alza, mI: [-0.6, 1.8, 0.1], cI: [-1, 0.2, -0.5] }, ease: 'asienta' },
    { t: 1, m: { ...m, mI: alza, mD: [0.6, 1.8, 0.1], cD: [1, 0.2, -0.5] }, b: { ...b, mD: alza, mI: [-0.58, 1.75, 0.1], cI: [-1, 0.2, -0.5] } },
  ];
  return { claves, k: 1, cam: [{ t: 0, pos: [0, 1.0, 3.9], mira: [0, 1.15, 0] }, { t: 1, pos: [0.3, 0.85, 3.3], mira: [0, 1.25, 0] }] };
};

const LEVANTAR = (): Accion => {
  // el morado levanta el bloque blanco de la marca por encima de la cabeza; el blanco lo mira subir
  const ym = 0.0, yb = 0.6;
  const m = dePie(0.25, 0, ym), b = dePie(-0.55, 0.1, yb, 0, KB);
  const claves: Clave[] = [
    { t: 0, m: { ...m, p: [0.25, 0.7, 0.0], lean: 0.55, mI: [0.42, 0.42, 0.42], mD: [0.08, 0.42, 0.42] }, b: { ...b, mira: [0.25, 0.4, 0.4] } },
    { t: 0.3, m: { ...m, p: [0.25, 0.86, 0.0], lean: 0.18, mI: [0.42, 1.05, 0.32], mD: [0.08, 1.05, 0.32] }, b: { ...b, mira: [0.25, 1.2, 0.4] } },
    { t: 0.55, m: { ...m, lean: -0.05, mI: [0.42, 2.0, 0.1], mD: [0.08, 2.0, 0.1] }, b: { ...b, mira: [0.25, 2.2, 0.3] }, ease: 'asienta' },
    { t: 1, m: { ...m, lean: -0.04, mI: [0.42, 2.02, 0.1], mD: [0.08, 2.02, 0.1] }, b: { ...b, mI: [-0.4, 1.9, 0.3], mira: [0.25, 2.2, 0.3] } },
  ];
  return { claves, k: 1, bloque: true, cam: [{ t: 0, pos: [-0.6, 1.0, 3.6], mira: [0, 1.0, 0] }, { t: 1, pos: [-0.2, 0.75, 3.4], mira: [0, 1.45, 0] }] };
};

const CRECER = (): Accion => {
  const A = HOMBRO(0, 1);
  const mover = (P: Pose, dx: number, mira: V): Pose => {
    const mv = (x?: V): V | undefined => (x ? [x[0] + dx, x[1], x[2]] : x);
    return { ...P, p: mv(P.p)!, mI: mv(P.mI)!, mD: mv(P.mD)!, pI: mv(P.pI)!, pD: mv(P.pD)!, yaw: P.yaw - 0.45, mira };
  };
  A.claves = A.claves.map(c => ({ ...c, m: mover(c.m, 0.2, [-0.7, 1.7, -1.0]), b: mover(c.b, 0.2, [-0.7, 1.7, -1.0]) }));
  A.cam = [{ t: 0, pos: [0.35, 1.35, 4.2], mira: [-0.1, 1.1, -0.4] }, { t: 1, pos: [-0.1, 1.3, 3.7], mira: [-0.15, 1.2, -0.4] }];
  return A;
};

const EXPLICAR = (): Accion => {
  const ym = 0.42, yb = -0.4;
  const m = dePie(-0.3, 0, ym), b = dePie(0.38, 0.12, yb, 0, KB);
  const apunta: V = [0.32, 2.12, 0.42];                                 // arriba a la derecha: donde va el texto de la idea
  const claves: Clave[] = [
    { t: 0, m: { ...m, mira: [0, 1.5, 4] }, b: { ...b, mira: [-0.3, 1.5, 0.2] } },
    { t: 0.12, m: { ...m, mI: [-0.12, 0.95, 0.12], lean: 0.06, mira: [0, 1.5, 4] }, b: { ...b, mira: [-0.3, 1.5, 0.2] } },                 // anticipación
    { t: 0.3, m: { ...m, mI: apunta, lean: -0.05, tilt: 0.05, mira: [0.45, 2.1, 1.2] }, b: { ...b, mira: [0.25, 2.1, 0.6] }, ease: 'asienta' },
    { t: 0.52, m: { ...m, mI: apunta, mD: [-0.62, 1.15, 0.38], cD: [-1, -0.3, -0.4], lean: -0.03, mira: [0, 1.6, 4] }, b: { ...b, mira: [-0.3, 1.55, 0.2] } },
    { t: 0.74, m: { ...m, mI: [-0.02, 1.22, 0.5], mD: [-0.62, 1.18, 0.4], cD: [-1, -0.3, -0.4], lean: 0.02, mira: [0, 1.6, 4] }, b: { ...b, mira: [-0.3, 1.55, 0.2] } },
    { t: 1, m: { ...m, mI: [0.02, 1.18, 0.5], mD: [-0.6, 1.14, 0.42], cD: [-1, -0.3, -0.4], lean: 0.02, mira: [0, 1.6, 4] }, b: { ...b, lean: 0.04, mira: [-0.3, 1.55, 0.2] } },
  ];
  return { claves, k: 1, cam: [{ t: 0, pos: [0.25, 1.3, 4.0], mira: [0.0, 1.2, 0] }, { t: 1, pos: [-0.15, 1.25, 3.5], mira: [0.0, 1.25, 0] }] };
};

const ACCIONES: Record<string, () => Accion> = { ayudar: AYUDAR, apreton: APRETON, hombro: () => HOMBRO(), crecer: CRECER, celebrar: CELEBRAR, levantar: LEVANTAR,
                                                  explicar: EXPLICAR };
export const ACCIONES_3D = Object.keys(ACCIONES);

/* ---------------------------------------------------------------------------------------------------------------- el mundo */
const Entorno: React.FC = () => {
  const { gl, scene } = useThree();
  useMemo(() => {
    const pm = new THREE.PMREMGenerator(gl);
    scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environmentIntensity = 0.42;
    pm.dispose();
  }, [gl, scene]);
  return null;
};

const Camara: React.FC<{ pos: THREE.Vector3; mira: THREE.Vector3; fov: number }> = ({ pos, mira, fov }) => {
  const { camera } = useThree();
  const c = camera as THREE.PerspectiveCamera;
  c.position.copy(pos);
  c.fov = fov;
  c.updateProjectionMatrix();
  c.lookAt(mira);
  return null;
};

/* el halo morado en el suelo, bajo el morado (el reflejo de su color sobre la superficie brillante) */
const texHalo = (() => {
  if (typeof document === 'undefined') return null;
  const cv = document.createElement('canvas');
  cv.width = cv.height = 256;
  const g = cv.getContext('2d')!;
  const gr = g.createRadialGradient(128, 128, 0, 128, 128, 128);
  gr.addColorStop(0, 'rgba(190,60,255,0.85)');
  gr.addColorStop(0.45, 'rgba(150,30,255,0.32)');
  gr.addColorStop(1, 'rgba(120,0,255,0)');
  g.fillStyle = gr;
  g.fillRect(0, 0, 256, 256);
  const t = new THREE.CanvasTexture(cv);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
})();

/* las estelas de neón: curvas de luz morada que se dibujan despacio detrás de la escena */
const Estela: React.FC<{ puntos: V[]; q: number; grosor: number }> = ({ puntos, q, grosor }) => {
  const curva = useMemo(() => new THREE.CatmullRomCurve3(puntos.map(v3)), [puntos]);
  const geo = useMemo(() => new THREE.TubeGeometry(curva, 160, grosor, 10, false), [curva, grosor]);
  const halo = useMemo(() => new THREE.TubeGeometry(curva, 160, grosor * 5, 10, false), [curva, grosor]);
  for (const g of [geo, halo]) {
    const n = g.index ? g.index.count : 0;
    g.setDrawRange(0, Math.floor(n * clamp(q) / 6) * 6);
  }
  return (
    <group>
      <mesh geometry={geo}><meshBasicMaterial color="#E2B8FF" toneMapped={false} /></mesh>
      <mesh geometry={halo}><meshBasicMaterial color="#8A2BE2" transparent opacity={0.28} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} /></mesh>
    </group>
  );
};

export type Pictos3DProps = { accion?: string; texto?: string; salida?: number };
export const Pictos3DE: React.FC<Pictos3DProps> = ({ accion = 'ayudar', texto = '', salida = 0.3 }) => {
  useFuentes();
  const frame = useCurrentFrame();
  const { fps, width: W, height: H, durationInFrames } = useVideoConfig();
  const dur = durationInFrames / fps;
  const t = frame / fps;
  const vertical = H > W;
  const A = useMemo(() => (ACCIONES[accion] || ACCIONES.ayudar)(), [accion]);
  // la acción ocupa el tramo entero (adaptada a su duración), con un respiro al principio y al final
  const q = clamp((t - 0.1) / Math.max(0.6, dur - 0.35));
  const { m, b } = enClaves(A.claves, q);
  const cm = montar(m, A.k), cb = montar(b, KB);
  // la cámara: dolly lento entre sus dos posiciones; en vertical, más lejos (cabe todo)
  const qc = suave(q);
  const c0 = A.cam[0], c1 = A.cam[A.cam.length - 1];
  const lejos = vertical ? 1.45 : 1.0;
  const mira = v3(mezclaV(c0.mira, c1.mira, qc));
  const pos = v3(mezclaV(c0.pos, c1.pos, qc)).sub(mira).multiplyScalar(lejos).add(mira);
  const mats = useMemo(() => ({
    morado: new THREE.MeshPhysicalMaterial({ color: '#9E1CFF', roughness: 0.13, metalness: 0.0, clearcoat: 1, clearcoatRoughness: 0.035, emissive: '#3B0070',
                                             emissiveIntensity: 0.32, envMapIntensity: 1.4, sheen: 0.3, sheenColor: new THREE.Color('#FF66FF') }),
    blanco: new THREE.MeshPhysicalMaterial({ color: '#E9E9EE', roughness: 0.6, metalness: 0.0, clearcoat: 0.08, envMapIntensity: 0.7 }),
    suelo: new THREE.MeshPhysicalMaterial({ color: '#040306', roughness: 0.34, metalness: 0.0, clearcoat: 0.45, clearcoatRoughness: 0.2, envMapIntensity: 0.06 }),
    borde: new THREE.MeshBasicMaterial({ color: '#F0D8FF', toneMapped: false }),
    bloque: new THREE.MeshPhysicalMaterial({ color: '#F4F4F8', roughness: 0.35, clearcoat: 0.6, emissive: '#B266FF', emissiveIntensity: 0.06 }),
    barra: new THREE.MeshPhysicalMaterial({ color: '#2A1240', roughness: 0.2, metalness: 0.3, clearcoat: 1, emissive: '#7A1FE0', emissiveIntensity: 0.25 }),
  }), []);
  const sal = clamp((t - (dur - salida)) / Math.max(0.01, salida));
  const ent = clamp(t / 0.35);
  const halo = (c: Cuerpo, alto: number, s: number) => texHalo && (
    <mesh position={[c.pelvis.x, alto + 0.003, c.pelvis.z]} rotation={[-PI2, 0, 0]}>
      <planeGeometry args={[1.6 * s, 1.6 * s]} />
      <meshBasicMaterial map={texHalo} transparent depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
    </mesh>
  );
  const altoM = A.escalon ? A.escalon : 0;
  const crece = A.grafica ? suave(clamp((q - 0.05) / 0.7)) : 0;
  const estelas: V[][] = [[[-4, 3.2, -3], [-1.5, 2.6, -2.6], [1.2, 3.1, -2.4], [4, 2.2, -2.8]], [[-4.2, 0.9, -2.5], [-2, 1.6, -2.2], [0.6, 0.7, -2.6], [4, 1.4, -2.2]]];
  return (
    <AbsoluteFill style={{ background: 'radial-gradient(110% 80% at 60% 38%, #1A0B2A 0%, #07050B 55%, #020203 100%)', opacity: ent * (1 - sal) }}>
      <ThreeCanvas width={W} height={H} shadows gl={{ antialias: true, alpha: true, preserveDrawingBuffer: true }} camera={{ fov: 32, near: 0.05, far: 60 }}>
        <Entorno />
        <fog attach="fog" args={['#040306', 4.5, 11]} />
        <Camara pos={pos} mira={mira} fov={vertical ? 30 : 32} />
        <ambientLight intensity={0.12} />
        <directionalLight position={[-2.5, 4.5, 3.5]} intensity={1.6} color="#FFFFFF" castShadow shadow-mapSize={[2048, 2048]} shadow-bias={-0.0004}
                          shadow-camera-left={-3} shadow-camera-right={3} shadow-camera-top={3} shadow-camera-bottom={-3} />
        <pointLight position={[2.6, 2.4, -1.8]} intensity={38} color="#B44CFF" distance={9} decay={2} />
        <pointLight position={[-2.8, 1.8, -1.6]} intensity={30} color="#8A2BE2" distance={9} decay={2} />
        <pointLight position={[0.2, 2.2, 2.4]} intensity={3} color="#D9B3FF" distance={6} decay={2} />
        {/* el suelo y, si toca, el escalón con su borde de luz */}
        <mesh position={[0, -0.001, 0]} rotation={[-PI2, 0, 0]} material={mats.suelo} receiveShadow><planeGeometry args={[30, 30]} /></mesh>
        {A.escalon && (
          <group>
            <mesh position={[2.0, A.escalon / 2, 0]} material={mats.suelo} receiveShadow castShadow><boxGeometry args={[4, A.escalon, 3]} /></mesh>
            <mesh position={[0.002, A.escalon - 0.004, 0]} material={mats.borde}><boxGeometry args={[0.012, 0.012, 3]} /></mesh>
          </group>
        )}
        {A.grafica && [0, 1, 2].map(i => {
          const qi = suave(clamp((q - 0.08 - i * 0.16) / 0.42));
          const h = (0.45 + i * 0.5) * qi + 0.02;
          return (
            <group key={i} position={[-0.95 + i * 0.4, 0, -1.0]}>
              <mesh position={[0, h / 2, 0]} material={mats.barra} castShadow><boxGeometry args={[0.3, h, 0.3]} /></mesh>
              <mesh position={[0, h + 0.006, 0]} material={mats.borde}><boxGeometry args={[0.3, 0.012, 0.3]} /></mesh>
            </group>
          );
        })}
        {A.bloque && (() => {
          const centro = cm.mI.clone().add(cm.mD).multiplyScalar(0.5).add(new THREE.Vector3(0, 0.16, 0.0));
          return <mesh position={centro} rotation={[0, 0.3 + q * 0.6, 0]} material={mats.bloque} castShadow><boxGeometry args={[0.42, 0.32, 0.42]} /></mesh>;
        })()}
        <Maniqui c={cm} mat={mats.morado} k={A.k} />
        <Maniqui c={cb} mat={mats.blanco} k={KB} />
        {halo(cm, A.escalon && cm.pelvis.x > 0 ? altoM : 0, 1)}
        {estelas.map((e, i) => <Estela key={i} puntos={e} q={clamp((t - 0.1 - i * 0.25) / 1.6)} grosor={0.012 + i * 0.006} />)}
      </ThreeCanvas>
      {texto && (() => {
        const U = Math.min(W, H) / 1080;
        const qt = clamp((t - 0.3) / 0.35);
        const barra = suave(clamp((t - 0.55) / 0.5));
        return (
          <div style={{ position: 'absolute', left: 0, right: 0, top: vertical ? H * 0.1 : H * 0.08, display: 'flex', flexDirection: 'column', alignItems: 'center',
                        opacity: qt, transform: `translateY(${((1 - qt) * 30 * U).toFixed(1)}px)` }}>
            <div style={{ fontFamily: FAMILIA.inter, fontWeight: 800, fontSize: Math.min(accion === 'explicar' ? 130 : 110, 1250 / Math.max(6, texto.length)) * U,
                          color: '#FFFFFF', letterSpacing: '-0.02em', textTransform: 'uppercase', textShadow: '0 0 40px rgba(170,60,255,.6)', textAlign: 'center',
                          padding: `0 ${50 * U}px` }}>{texto}</div>
            <div style={{ marginTop: 16 * U, height: 8 * U, width: Math.min(W * 0.6, texto.length * 46 * U) * barra, borderRadius: 4 * U, background: '#B44CFF',
                          boxShadow: `0 0 ${24 * U}px #B44CFF` }} />
          </div>
        );
      })()}
    </AbsoluteFill>
  );
};
