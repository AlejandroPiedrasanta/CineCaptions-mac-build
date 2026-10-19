// CineCaptions · By Cinema Productions
// 1_codigo/remotion/src/kitneon/estilos.ts — v5.5.13: los estilos del kit «TEMA 1» (graficos/base.css + tema-neon.css), tal cual, para KitNeon.tsx.
// Las fuentes (las del kit: Cond = Helvetica Neue LT Std 107 Extra Black Condensed, Thin, Inter variable, Script = Yellowtail, Serif = DM Serif Text
// Italic) las copia empaquetar.mjs a public/fuentes/kit/.

export const BASE = `
html, body { margin: 0; background: transparent; overflow: hidden; }
.st { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }
.a { position: absolute; left: 0; top: 0; will-change: transform, opacity; }
svg.i { fill: none; stroke: currentColor; stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round; }
.cap { width: 1000px; left: 40px; text-align: center; }
.sm { font: 600 46px/1.15 Inter; color: #fff; letter-spacing: -0.4px; text-shadow: 0 3px 18px var(--sombra); margin-bottom: 10px; }
.sm span, .ln span { display: inline-block; }
.ln { font-family: Cond; font-size: 150px; line-height: .9; color: #fff; text-transform: uppercase; letter-spacing: 1px;
      text-shadow: 0 6px 30px var(--sombra-suave); white-space: nowrap; }
.ln .w { margin: 0 .09em; }
.ln.thin { font-family: Thin; font-size: 92px; text-transform: none; letter-spacing: 0; line-height: 1.15; text-shadow: 0 3px 20px var(--sombra); }
.boxw { display: inline-block; position: relative; padding: 14px 28px 2px; text-shadow: none; }
.boxw.blanco { color: var(--acento); }
.bxbg { position: absolute; inset: 0; background: var(--acento); border-radius: 20px; box-shadow: 0 14px 34px var(--sombra-suave); transform-origin: 0 50%; z-index: 0; }
.boxw.blanco .bxbg { background: #fff; }
.lnw { position: relative; display: inline-block; }
.mk { display: inline-block; overflow: hidden; vertical-align: bottom; position: relative; z-index: 1; padding: .26em .12em .18em; margin: -.26em -.12em -.18em; }
.mk .in { display: inline-block; transform-origin: 0 100%; }
.subr { position: absolute; left: .1em; right: .1em; bottom: -4px; height: 14px; border-radius: 7px; background: var(--acento);
        transform-origin: 0 50%; box-shadow: 0 6px 16px var(--sombra-suave); }
.hk { width: 1000px; left: 40px; text-align: center; }
.hk > div { line-height: 1; }
.hk .cnt { display: inline-block; position: relative; }
.hl-esp { font: 800 34px Inter; letter-spacing: .42em; color: #fff; text-transform: uppercase; margin-bottom: 10px; filter: drop-shadow(0 3px 10px var(--sombra)); }
.hl-esp .cnt { margin-right: -.42em; }
.hl-big { font-family: Cond; line-height: .86; text-transform: uppercase; color: #fff; filter: drop-shadow(0 8px 22px var(--sombra)); }
.hl-serif { font-family: Serif; color: #fff; line-height: 1.04; filter: drop-shadow(0 4px 14px var(--sombra)); }
.hl-script { font-family: Script; line-height: .95; }
.scr { padding: 0 .14em; filter: drop-shadow(0 4px 12px var(--sombra)); }
.stk { font-family: Cond; text-transform: uppercase; line-height: 1; padding: .12em .32em .03em; border-radius: 8px; box-shadow: 0 14px 32px var(--sombra); }
.f-lima, .f-acento, .f-mag, .f-acento2, .f-blanco { -webkit-background-clip: text; background-clip: text; color: transparent; }
.noti { width: 940px; height: 150px; border-radius: 40px; background: rgba(255,255,255,.97); box-shadow: 0 22px 54px var(--sombra);
        display: flex; align-items: center; gap: 24px; padding: 0 34px 0 24px; box-sizing: border-box; }
.noti .nic { width: 98px; height: 98px; border-radius: 26px; overflow: hidden; flex: none; }
.noti .nic img { width: 100%; height: 100%; object-fit: cover; }
.noti .ntx { flex: 1; }
.noti b { display: block; font: 800 36px/1.15 Inter; color: var(--tinta); letter-spacing: -.5px; }
.noti span { display: block; font: 500 30px/1.25 Inter; color: var(--gris); }
.noti em { font: 500 26px Inter; color: var(--gris); font-style: normal; align-self: flex-start; margin-top: 32px; }
.chip { display: inline-flex; align-items: center; gap: 14px; height: 78px; padding: 0 32px 0 22px; border-radius: 39px; background: #fff;
        color: var(--tinta); font: 600 34px Inter; letter-spacing: -.3px; box-shadow: 0 10px 28px var(--sombra-suave); white-space: nowrap; }
.chip svg { width: 36px; height: 36px; color: var(--acento); stroke-width: 2.4; }
.chip.hl { background: var(--chip-hl-bg); color: var(--chip-hl-tx); font-weight: 800; }
.chip.hl svg { color: var(--chip-hl-tx); }
.badge { width: 84px; height: 84px; border-radius: 50%; background: var(--acento); display: grid; place-items: center; color: #fff; box-shadow: 0 10px 26px var(--sombra-suave); }
.badge svg { width: 44px; height: 44px; stroke-width: 2.6; }
.badge.blanco { background: #fff; color: var(--acento); }
.tag { display: inline-flex; align-items: center; gap: 16px; height: 92px; padding: 0 34px 0 9px; border-radius: 46px; background: #fff;
       box-shadow: 0 12px 30px var(--sombra-suave); white-space: nowrap; }
.tag img { width: 74px; height: 74px; border-radius: 50%; object-fit: cover; }
.tag b { display: block; font: 800 32px/1.05 Inter; color: var(--tinta); letter-spacing: -.4px; }
.tag i { display: block; font: 500 25px/1.2 Inter; font-style: normal; color: var(--gris); }
.grad { width: 1080px; height: 1150px; top: 770px; background: var(--grad); }
.veil { width: 1080px; height: 1920px; background: var(--veil); }
.ring { border-radius: 50%; box-sizing: border-box; }
.disco { border-radius: 50%; }
.centro { width: 320px; height: 320px; border-radius: 50%; background: #fff; box-shadow: var(--centro-sombra); display: grid; place-items: center; }
.centro img { width: 284px; height: 284px; border-radius: 50%; object-fit: cover; }
.ico { width: 124px; height: 124px; border-radius: 50%; background: #fff; display: grid; place-items: center; color: var(--acento); box-shadow: 0 16px 36px var(--sombra-suave); }
.ico svg { width: 54px; height: 54px; stroke-width: 2.2; }
.card { background: #fff; border-radius: 40px; box-shadow: 0 22px 60px var(--sombra); overflow: hidden; }
.tile { width: 108px; height: 108px; border-radius: 30px; background: #fff; display: grid; place-items: center; color: var(--tinta); box-shadow: 0 12px 30px var(--sombra-suave); }
.tile svg { width: 50px; height: 50px; stroke-width: 2; }
.row { position: absolute; left: 0; width: 100%; height: 140px; display: flex; align-items: center; gap: 22px; padding: 0 34px; box-sizing: border-box; }
.row + .row { border-top: 2px solid #EFE7E1; }
.row svg { width: 40px; height: 40px; color: #6E5E55; stroke-width: 2; }
.row span { flex: 1; font: 600 42px Inter; color: var(--tinta); letter-spacing: -.5px; }
.track { width: 104px; height: 56px; border-radius: 28px; background: #E3DAD3; position: relative; }
.knob { position: absolute; left: 5px; top: 5px; width: 46px; height: 46px; border-radius: 50%; background: #fff; box-shadow: 0 3px 8px rgba(0,0,0,.2); }
.av { width: 112px; height: 112px; border-radius: 50%; border: 6px solid #fff; box-shadow: 0 12px 28px var(--sombra-suave); object-fit: cover; box-sizing: border-box; }
.nav { width: 900px; height: 560px; }
.nav h3 { position: absolute; left: 50px; top: 388px; margin: 0; font: 800 52px Inter; color: var(--tinta); letter-spacing: -1px; }
.nav p { position: absolute; left: 50px; top: 458px; margin: 0; font: 500 30px/1.32 Inter; color: #7E6E64; }
.hito { position: absolute; left: 50px; display: flex; align-items: center; gap: 26px; font: 600 34px Inter; color: var(--tinta); letter-spacing: -.4px; }
.dot { width: 30px; height: 30px; border-radius: 50%; background: var(--acento); position: relative; flex: none; }
.dot::after { content: ""; position: absolute; inset: -10px; border-radius: 50%; background: var(--acento-suave); }
.dot.ring2 { background: #fff; border: 6px solid var(--acento); box-sizing: border-box; }
.prod { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; color: var(--tinta); height: 100%; }
.prod .badge { width: 74px; height: 74px; margin-bottom: 14px; }
.prod .badge svg { width: 38px; height: 38px; }
.big { font-family: Cond; font-size: 168px; line-height: .86; color: var(--tinta); }
.kick { font: 800 30px Inter; letter-spacing: .14em; color: var(--acento); }
.sub { font: 500 26px/1.25 Inter; color: var(--gris); margin-top: 8px; }
.check { display: flex; align-items: center; gap: 28px; font: 800 64px Inter; color: #fff; letter-spacing: -1px; text-shadow: 0 4px 22px var(--sombra); white-space: nowrap; }
.check .badge svg path { stroke-dasharray: 30; }
`;

export const TEMA_CSS: Record<string, string> = {
  neon: `
:root, .st {
  --acento: #FF2DCB; --acento2: #D6FF3B; --rojo: #EE2B36; --tinta: #14101E; --gris: #776C85;
  --acento-suave: rgba(255,45,203,.22);
  --sombra: rgba(10,5,22,.6); --sombra-suave: rgba(16,8,32,.28);
  --chip-hl-bg: #D6FF3B; --chip-hl-tx: #14101E;
  --grad: linear-gradient(to top, rgba(26,10,50,.97) 0%, rgba(78,26,168,.8) 32%, rgba(107,43,242,.42) 62%, rgba(107,43,242,0) 100%);
  --veil: radial-gradient(circle at 540px 800px, rgba(140,70,240,.62) 0, rgba(80,32,160,.76) 260px, rgba(34,14,68,.88) 560px, rgba(14,8,26,.94) 1000px);
  --centro-sombra: 0 0 70px rgba(255,45,203,.55), 0 24px 60px rgba(0,0,0,.4);
}
.f-lima, .f-acento { background-image: linear-gradient(180deg, #F4FF72 0%, #D6FF3B 52%, #9BE81C 100%); }
.f-mag, .f-acento2 { background-image: linear-gradient(180deg, #FF7BE6 0%, #FF2DCB 48%, #7A2BF2 100%); }
.f-blanco { background-image: radial-gradient(circle, rgba(30,14,60,.24) 1.4px, transparent 1.9px), linear-gradient(180deg, #fff 35%, #E4DEF3 100%); background-size: 8px 8px, auto; }
.scr.lima, .scr.acento { color: #D6FF3B; } .scr.mag, .scr.acento2 { color: #FF2DCB; }
.stk-rojo { background: #EE2B36; color: #fff; } .stk-lima, .stk-acento { background: #D6FF3B; color: #14101E; }
.stk-mag, .stk-acento2 { background: #FF2DCB; color: #fff; } .stk-blanco { background: #fff; color: #14101E; }
`,
};

export const FUENTES_KIT: [string, string, FontFaceDescriptors][] = [
  ['Cond', 'fuentes/kit/cond.ttf', {}],
  ['Thin', 'fuentes/kit/thin.otf', {}],
  ['Inter', 'fuentes/kit/inter.ttf', { weight: '100 900' }],
  ['Script', 'fuentes/kit/script.ttf', {}],
  ['Serif', 'fuentes/kit/serif.ttf', {}],
];
