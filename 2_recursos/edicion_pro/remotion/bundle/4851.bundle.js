"use strict";
(self["webpackChunkcinecaptions_pro_remotion"] = self["webpackChunkcinecaptions_pro_remotion"] || []).push([[4851],{

/***/ 4851
(__unused_webpack___webpack_module__, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   dropShadow: () => (/* binding */ dropShadow)
/* harmony export */ });
/* harmony import */ var _index_kkvzt8b7_mjs__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(7223);
/* harmony import */ var _index_618ky75w_mjs__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(224);
/* harmony import */ var _index_evy8hyah_mjs__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(9028);
/* harmony import */ var _index_wxhvgv2s_mjs__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(8197);
/* harmony import */ var _index_4fvp93ps_mjs__WEBPACK_IMPORTED_MODULE_4__ = __webpack_require__(4075);
/* harmony import */ var remotion__WEBPACK_IMPORTED_MODULE_5__ = __webpack_require__(3947);






// src/drop-shadow/index.ts


// src/drop-shadow/drop-shadow-runtime.ts


// src/drop-shadow/drop-shadow-shaders.ts
var DROP_SHADOW_VS = `#version 300 es
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aUv;
out vec2 vUv;

void main() {
	vUv = aUv;
	gl_Position = vec4(aPos, 0.0, 1.0);
}
`;
var DROP_SHADOW_EXTRACT_FS = `#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uSource;
uniform vec4 uColor;
uniform float uOpacity;

void main() {
	vec4 source = texture(uSource, vUv);
	float shadowAlpha = source.a * uColor.a * clamp(uOpacity, 0.0, 1.0);

	fragColor = vec4(uColor.rgb * shadowAlpha, shadowAlpha);
}
`;
var DROP_SHADOW_BLUR_FS_HORIZONTAL = (0,_index_evy8hyah_mjs__WEBPACK_IMPORTED_MODULE_2__/* .buildGaussianBlurFs */ .c)("horizontal");
var DROP_SHADOW_BLUR_FS_VERTICAL = (0,_index_evy8hyah_mjs__WEBPACK_IMPORTED_MODULE_2__/* .buildGaussianBlurFs */ .c)("vertical");
var DROP_SHADOW_COMPOSITE_FS = `#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uSource;
uniform sampler2D uShadow;
uniform vec2 uOffset;
uniform vec2 uTexelSize;

void main() {
	vec4 source = texture(uSource, vUv);
	vec2 shadowUv = vUv - vec2(uOffset.x, -uOffset.y) * uTexelSize;
	vec4 shadow = vec4(0.0);

	if (
		shadowUv.x >= 0.0 &&
		shadowUv.x <= 1.0 &&
		shadowUv.y >= 0.0 &&
		shadowUv.y <= 1.0
	) {
		shadow = texture(uShadow, shadowUv);
	}

	fragColor = source + shadow * (1.0 - source.a);
}
`;

// src/drop-shadow/drop-shadow-runtime.ts
var { createWebGL2ContextError } = remotion__WEBPACK_IMPORTED_MODULE_5__.Internals;
var compileShader = (gl, type, source) => {
  const shader = gl.createShader(type);
  if (!shader) {
    throw new Error("Failed to create WebGL shader");
  }
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(shader);
    gl.deleteShader(shader);
    throw new Error(`Drop shadow shader compile failed: ${log ?? "(no log)"}`);
  }
  return shader;
};
var linkProgram = (gl, vs, fs) => {
  const program = gl.createProgram();
  if (!program) {
    throw new Error("Failed to create WebGL program");
  }
  gl.attachShader(program, vs);
  gl.attachShader(program, fs);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const log = gl.getProgramInfoLog(program);
    gl.deleteProgram(program);
    throw new Error(`Drop shadow program link failed: ${log ?? "(no log)"}`);
  }
  return program;
};
var createProgram = (gl, vertexSource, fragmentSource) => {
  const vs = compileShader(gl, gl.VERTEX_SHADER, vertexSource);
  const fs = compileShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
  const program = linkProgram(gl, vs, fs);
  gl.deleteShader(vs);
  gl.deleteShader(fs);
  return program;
};
var createRgbaTexture = (gl) => {
  const texture = gl.createTexture();
  if (!texture) {
    throw new Error("Failed to create WebGL texture");
  }
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.bindTexture(gl.TEXTURE_2D, null);
  return texture;
};
var getBlurUniforms = (gl, program) => ({
  uRadius: gl.getUniformLocation(program, "uRadius"),
  uTexelSize: gl.getUniformLocation(program, "uTexelSize"),
  uSource: gl.getUniformLocation(program, "uSource")
});
var setupDropShadow = (target) => {
  const gl = target.getContext("webgl2", {
    premultipliedAlpha: true,
    alpha: true,
    preserveDrawingBuffer: true
  });
  if (!gl) {
    throw createWebGL2ContextError("drop shadow effect");
  }
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
  const programExtract = createProgram(gl, DROP_SHADOW_VS, DROP_SHADOW_EXTRACT_FS);
  const programHorizontal = createProgram(gl, DROP_SHADOW_VS, DROP_SHADOW_BLUR_FS_HORIZONTAL);
  const programVertical = createProgram(gl, DROP_SHADOW_VS, DROP_SHADOW_BLUR_FS_VERTICAL);
  const programComposite = createProgram(gl, DROP_SHADOW_VS, DROP_SHADOW_COMPOSITE_FS);
  const vao = gl.createVertexArray();
  if (!vao) {
    throw new Error("Failed to create WebGL vertex array");
  }
  gl.bindVertexArray(vao);
  const data = new Float32Array([
    -1,
    -1,
    0,
    0,
    1,
    -1,
    1,
    0,
    -1,
    1,
    0,
    1,
    1,
    1,
    1,
    1
  ]);
  const vbo = gl.createBuffer();
  if (!vbo) {
    throw new Error("Failed to create WebGL buffer");
  }
  gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
  gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 16, 0);
  gl.enableVertexAttribArray(1);
  gl.vertexAttribPointer(1, 2, gl.FLOAT, false, 16, 8);
  gl.bindVertexArray(null);
  const textureSource = createRgbaTexture(gl);
  const textureShadowA = createRgbaTexture(gl);
  const textureShadowB = createRgbaTexture(gl);
  const framebuffer = gl.createFramebuffer();
  if (!framebuffer) {
    throw new Error("Failed to create WebGL framebuffer");
  }
  const colorCanvas = document.createElement("canvas");
  colorCanvas.width = 1;
  colorCanvas.height = 1;
  const colorCtx = colorCanvas.getContext("2d", { willReadFrequently: true });
  if (!colorCtx) {
    throw new Error("Failed to acquire 2D context for color parsing");
  }
  return {
    gl,
    programExtract,
    programHorizontal,
    programVertical,
    programComposite,
    vao,
    vbo,
    textureSource,
    textureShadowA,
    textureShadowB,
    framebuffer,
    extract: {
      uSource: gl.getUniformLocation(programExtract, "uSource"),
      uColor: gl.getUniformLocation(programExtract, "uColor"),
      uOpacity: gl.getUniformLocation(programExtract, "uOpacity")
    },
    horizontal: getBlurUniforms(gl, programHorizontal),
    vertical: getBlurUniforms(gl, programVertical),
    composite: {
      uSource: gl.getUniformLocation(programComposite, "uSource"),
      uShadow: gl.getUniformLocation(programComposite, "uShadow"),
      uOffset: gl.getUniformLocation(programComposite, "uOffset"),
      uTexelSize: gl.getUniformLocation(programComposite, "uTexelSize")
    },
    colorCtx,
    cachedColorStr: "",
    cachedColorRgba: [0, 0, 0, 255]
  };
};
var cleanupDropShadow = ({
  gl,
  programExtract,
  programHorizontal,
  programVertical,
  programComposite,
  vao,
  vbo,
  textureSource,
  textureShadowA,
  textureShadowB,
  framebuffer
}) => {
  gl.deleteFramebuffer(framebuffer);
  gl.deleteTexture(textureSource);
  gl.deleteTexture(textureShadowA);
  gl.deleteTexture(textureShadowB);
  gl.deleteBuffer(vbo);
  gl.deleteProgram(programExtract);
  gl.deleteProgram(programHorizontal);
  gl.deleteProgram(programVertical);
  gl.deleteProgram(programComposite);
  gl.deleteVertexArray(vao);
};
var drawFullscreenQuad = (state) => {
  const { gl, vao } = state;
  gl.bindVertexArray(vao);
  gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  gl.bindVertexArray(null);
};
var setTextureSize = (gl, texture, width, height) => {
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
};
var setFramebufferTexture = (gl, framebuffer, texture) => {
  gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texture, 0);
  const status = gl.checkFramebufferStatus(gl.FRAMEBUFFER);
  if (status !== gl.FRAMEBUFFER_COMPLETE) {
    throw new Error(`Drop shadow framebuffer incomplete: 0x${status.toString(16)}`);
  }
};
var setBlurUniforms = ({
  gl,
  uniforms,
  radius,
  width,
  height
}) => {
  if (uniforms.uSource)
    gl.uniform1i(uniforms.uSource, 0);
  if (uniforms.uRadius)
    gl.uniform1f(uniforms.uRadius, radius);
  if (uniforms.uTexelSize) {
    gl.uniform2f(uniforms.uTexelSize, 1 / width, 1 / height);
  }
};
var normalizedColor = (color) => {
  return [color[0] / 255, color[1] / 255, color[2] / 255, color[3] / 255];
};
var applyDropShadow = ({
  state,
  source,
  width,
  height,
  radius,
  offsetX,
  offsetY,
  opacity,
  color,
  flipSourceY
}) => {
  const {
    gl,
    textureSource,
    textureShadowA,
    textureShadowB,
    framebuffer,
    programExtract,
    programHorizontal,
    programVertical,
    programComposite
  } = state;
  gl.viewport(0, 0, width, height);
  gl.clearColor(0, 0, 0, 0);
  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D, textureSource);
  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, flipSourceY);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source);
  setTextureSize(gl, textureShadowA, width, height);
  setTextureSize(gl, textureShadowB, width, height);
  const [r, g, b, a] = normalizedColor(color);
  setFramebufferTexture(gl, framebuffer, textureShadowA);
  gl.clear(gl.COLOR_BUFFER_BIT);
  gl.useProgram(programExtract);
  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D, textureSource);
  if (state.extract.uSource)
    gl.uniform1i(state.extract.uSource, 0);
  if (state.extract.uColor)
    gl.uniform4f(state.extract.uColor, r, g, b, a);
  if (state.extract.uOpacity)
    gl.uniform1f(state.extract.uOpacity, opacity);
  drawFullscreenQuad(state);
  setFramebufferTexture(gl, framebuffer, textureShadowB);
  gl.clear(gl.COLOR_BUFFER_BIT);
  gl.useProgram(programHorizontal);
  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D, textureShadowA);
  setBlurUniforms({
    gl,
    uniforms: state.horizontal,
    radius,
    width,
    height
  });
  drawFullscreenQuad(state);
  setFramebufferTexture(gl, framebuffer, textureShadowA);
  gl.clear(gl.COLOR_BUFFER_BIT);
  gl.useProgram(programVertical);
  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D, textureShadowB);
  setBlurUniforms({
    gl,
    uniforms: state.vertical,
    radius,
    width,
    height
  });
  drawFullscreenQuad(state);
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  gl.clear(gl.COLOR_BUFFER_BIT);
  gl.useProgram(programComposite);
  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D, textureSource);
  gl.activeTexture(gl.TEXTURE1);
  gl.bindTexture(gl.TEXTURE_2D, textureShadowA);
  if (state.composite.uSource)
    gl.uniform1i(state.composite.uSource, 0);
  if (state.composite.uShadow)
    gl.uniform1i(state.composite.uShadow, 1);
  if (state.composite.uOffset) {
    gl.uniform2f(state.composite.uOffset, offsetX, offsetY);
  }
  if (state.composite.uTexelSize) {
    gl.uniform2f(state.composite.uTexelSize, 1 / width, 1 / height);
  }
  drawFullscreenQuad(state);
  gl.bindTexture(gl.TEXTURE_2D, null);
  gl.useProgram(null);
};

// src/drop-shadow/webgpu-shaders.ts
var DROP_SHADOW_EXTRACT_WEBGPU_SHADER = `
${_index_kkvzt8b7_mjs__WEBPACK_IMPORTED_MODULE_0__/* .WEBGPU_MULTIPASS_BINDINGS */ .NK}
struct Params {color: vec4f, values: vec4f,}
@fragment fn fragment(input: VertexOutput) -> @location(0) vec4f {
 let alpha=textureSampleLevel(source,sourceSampler,input.uv,0).a*params.color.a*clamp(params.values.x,0.0,1.0);
 return vec4f(params.color.rgb*alpha,alpha);
}
`;
var DROP_SHADOW_COMPOSITE_WEBGPU_SHADER = `
${_index_kkvzt8b7_mjs__WEBPACK_IMPORTED_MODULE_0__/* .WEBGPU_MULTIPASS_BINDINGS */ .NK}
struct Params {resolution: vec2f, offset: vec2f,}
@fragment fn fragment(input: VertexOutput) -> @location(0) vec4f {
 let color=textureSampleLevel(source,sourceSampler,input.uv,0);
 let uv=input.uv-params.offset/params.resolution;
 var shadow=vec4f(0);
 if (all(uv >= vec2f(0)) && all(uv <= vec2f(1))) {shadow=textureSampleLevel(secondary,sourceSampler,uv,0);}
 return color+shadow*(1.0-color.a);
}`;

// src/drop-shadow/index.ts
var { createEffect } = remotion__WEBPACK_IMPORTED_MODULE_5__.Internals;
var DEFAULT_RADIUS = 12;
var DEFAULT_OFFSET_X = 8;
var DEFAULT_OFFSET_Y = 8;
var DEFAULT_OPACITY = 0.5;
var DEFAULT_COLOR = "#000000";
var dropShadowSchema = {
  radius: {
    type: "number",
    min: 0,
    max: 100,
    step: 1,
    default: DEFAULT_RADIUS,
    description: "Radius",
    hiddenFromList: false
  },
  offsetX: {
    type: "number",
    step: 1,
    default: DEFAULT_OFFSET_X,
    description: "Offset X",
    hiddenFromList: false
  },
  offsetY: {
    type: "number",
    step: 1,
    default: DEFAULT_OFFSET_Y,
    description: "Offset Y",
    hiddenFromList: false
  },
  opacity: {
    type: "number",
    min: 0,
    max: 1,
    step: 0.01,
    default: DEFAULT_OPACITY,
    description: "Opacity",
    hiddenFromList: false
  },
  color: {
    type: "color",
    default: DEFAULT_COLOR,
    description: "Color"
  }
};
var resolve = (p) => ({
  radius: p.radius ?? DEFAULT_RADIUS,
  offsetX: p.offsetX ?? DEFAULT_OFFSET_X,
  offsetY: p.offsetY ?? DEFAULT_OFFSET_Y,
  opacity: p.opacity ?? DEFAULT_OPACITY,
  color: p.color ?? DEFAULT_COLOR
});
var validateDropShadowParams = (params) => {
  (0,_index_4fvp93ps_mjs__WEBPACK_IMPORTED_MODULE_4__/* .assertEffectParamsObject */ .db)(params, "Drop shadow");
  (0,_index_wxhvgv2s_mjs__WEBPACK_IMPORTED_MODULE_3__/* .assertOptionalFiniteNumber */ .FC)(params.radius, "radius");
  (0,_index_wxhvgv2s_mjs__WEBPACK_IMPORTED_MODULE_3__/* .assertOptionalFiniteNumber */ .FC)(params.offsetX, "offsetX");
  (0,_index_wxhvgv2s_mjs__WEBPACK_IMPORTED_MODULE_3__/* .assertOptionalFiniteNumber */ .FC)(params.offsetY, "offsetY");
  (0,_index_wxhvgv2s_mjs__WEBPACK_IMPORTED_MODULE_3__/* .assertOptionalFiniteNumber */ .FC)(params.opacity, "opacity");
  (0,_index_4fvp93ps_mjs__WEBPACK_IMPORTED_MODULE_4__/* .assertOptionalColor */ .gu)(params.color, "color");
  const r = resolve(params);
  (0,_index_wxhvgv2s_mjs__WEBPACK_IMPORTED_MODULE_3__/* .validateNonNegative */ .XP)(r.radius, "radius");
  (0,_index_wxhvgv2s_mjs__WEBPACK_IMPORTED_MODULE_3__/* .validateUnitInterval */ .yk)(r.opacity, "opacity");
};
var dropShadow = createEffect({
  type: "dev.remotion.effects.dropShadow",
  label: "dropShadow()",
  documentationLink: "https://www.remotion.dev/docs/effects/drop-shadow",
  calculateKey: (params) => {
    const r = resolve(params);
    return `drop-shadow-${r.radius}-${r.offsetX}-${r.offsetY}-${r.opacity}-${r.color}`;
  },
  implementations: {
    webgpu: remotion__WEBPACK_IMPORTED_MODULE_5__.Internals.createEffectImplementation({
      setup: (target) => {
        const canvas = document.createElement("canvas");
        canvas.width = 1;
        canvas.height = 1;
        const colorCtx = canvas.getContext("2d", { willReadFrequently: true });
        if (!colorCtx)
          throw new Error("Could not create color parser");
        return {
          ...(0,_index_kkvzt8b7_mjs__WEBPACK_IMPORTED_MODULE_0__/* .setupWebGpuMultipass */ .SB)(target, "drop-shadow"),
          colorCtx,
          cachedColor: null,
          cachedRgba: [0, 0, 0, 0]
        };
      },
      apply: ({ source, width, height, params, state, gpuDevice }) => {
        if (!gpuDevice)
          throw new Error("A WebGPU device is required for this effect");
        const r = resolve(params);
        if (state.cachedColor !== r.color) {
          state.cachedColor = r.color;
          state.cachedRgba = (0,_index_wxhvgv2s_mjs__WEBPACK_IMPORTED_MODULE_3__/* .parseColorRgba */ .zp)(state.colorCtx, r.color);
        }
        const color = state.cachedRgba.map((channel) => channel / 255);
        (0,_index_kkvzt8b7_mjs__WEBPACK_IMPORTED_MODULE_0__/* .applyWebGpuMultipass */ .JM)({
          auxiliarySource: null,
          state,
          source,
          width,
          height,
          device: gpuDevice,
          passes: [
            {
              shader: DROP_SHADOW_EXTRACT_WEBGPU_SHADER,
              uniforms: new Float32Array([...color, r.opacity, 0, 0, 0]),
              source: -1,
              secondary: -1
            },
            {
              shader: _index_618ky75w_mjs__WEBPACK_IMPORTED_MODULE_1__/* .GAUSSIAN_BLUR_WEBGPU_SHADER */ .j,
              uniforms: new Float32Array([
                width,
                height,
                1,
                0,
                r.radius,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0
              ]),
              source: 0,
              secondary: -1
            },
            {
              shader: _index_618ky75w_mjs__WEBPACK_IMPORTED_MODULE_1__/* .GAUSSIAN_BLUR_WEBGPU_SHADER */ .j,
              uniforms: new Float32Array([
                width,
                height,
                0,
                1,
                r.radius,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0
              ]),
              source: 1,
              secondary: -1
            },
            {
              shader: DROP_SHADOW_COMPOSITE_WEBGPU_SHADER,
              uniforms: new Float32Array([width, height, r.offsetX, r.offsetY]),
              source: -1,
              secondary: 2
            }
          ]
        });
      },
      cleanup: _index_kkvzt8b7_mjs__WEBPACK_IMPORTED_MODULE_0__/* .cleanupWebGpuMultipass */ .$h
    }),
    webgl2: remotion__WEBPACK_IMPORTED_MODULE_5__.Internals.createEffectImplementation({
      setup: (target) => setupDropShadow(target),
      apply: ({ source, width, height, params, state, flipSourceY }) => {
        const r = resolve(params);
        if (state.cachedColorStr !== r.color) {
          state.cachedColorStr = r.color;
          state.cachedColorRgba = (0,_index_wxhvgv2s_mjs__WEBPACK_IMPORTED_MODULE_3__/* .parseColorRgba */ .zp)(state.colorCtx, r.color);
        }
        applyDropShadow({
          state,
          source,
          width,
          height,
          radius: r.radius,
          offsetX: r.offsetX,
          offsetY: r.offsetY,
          opacity: r.opacity,
          color: state.cachedColorRgba,
          flipSourceY
        });
      },
      cleanup: (state) => cleanupDropShadow(state)
    })
  },
  schema: dropShadowSchema,
  validateParams: validateDropShadowParams
});



/***/ },

/***/ 4075
(__unused_webpack___webpack_module__, __webpack_exports__, __webpack_require__) {

/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   b3: () => (/* binding */ assertRequiredColor),
/* harmony export */   c1: () => (/* binding */ assertRequiredFiniteNumber),
/* harmony export */   db: () => (/* binding */ assertEffectParamsObject),
/* harmony export */   fX: () => (/* binding */ assertOptionalBoolean),
/* harmony export */   gu: () => (/* binding */ assertOptionalColor)
/* harmony export */ });
// src/validate-effect-param.ts
var assertEffectParamsObject = (params, effectLabel) => {
  if (params === null || typeof params !== "object") {
    throw new TypeError(`${effectLabel} effect requires a parameters object, but got ${JSON.stringify(params)}`);
  }
};
var assertRequiredFiniteNumber = (value, name) => {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new TypeError(`"${name}" must be a finite number, but got ${JSON.stringify(value)}`);
  }
};
var assertRequiredColor = (value, name) => {
  if (typeof value !== "string" || value.length === 0) {
    throw new TypeError(`"${name}" must be a non-empty string, but got ${JSON.stringify(value)}`);
  }
};
var assertOptionalColor = (value, name) => {
  if (value === undefined) {
    return;
  }
  assertRequiredColor(value, name);
};
var assertOptionalBoolean = (value, name) => {
  if (value === undefined) {
    return;
  }
  if (typeof value !== "boolean") {
    throw new TypeError(`"${name}" must be a boolean, but got ${JSON.stringify(value)}`);
  }
};




/***/ },

/***/ 224
(__unused_webpack___webpack_module__, __webpack_exports__, __webpack_require__) {

/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   j: () => (/* binding */ GAUSSIAN_BLUR_WEBGPU_SHADER)
/* harmony export */ });
/* harmony import */ var _index_kkvzt8b7_mjs__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(7223);


// src/gaussian-blur-webgpu-shader.ts
var GAUSSIAN_BLUR_WEBGPU_SHADER = `
${_index_kkvzt8b7_mjs__WEBPACK_IMPORTED_MODULE_0__/* .WEBGPU_MULTIPASS_BINDINGS */ .NK}
struct Params { resolution: vec2f, direction: vec2f, values: vec4f, startEnd: vec4f, radial: vec4f, }
fn radiusAt(uv: vec2f) -> f32 {
 let mode = params.values.y;
 if (mode == 0.0) {return params.values.x;}
 if (mode == 1.0) {
  let gradient = params.startEnd.zw - params.startEnd.xy;
  let lengthSq = dot(gradient, gradient);
  if (lengthSq <= 0.0000001) {return max(0.0, params.values.z);}
  let progress = clamp(dot(uv - params.startEnd.xy, gradient) / lengthSq, 0.0, 1.0);
  return max(0.0, mix(params.values.z, params.values.w, progress));
 }
 let radii = params.startEnd.zw * params.resolution * 0.5;
 if (radii.x <= 0.0000001 || radii.y <= 0.0000001) {return max(0.0, params.values.z);}
 let delta = (uv - params.startEnd.xy) * params.resolution;
 let angle = radians(params.radial.x);
 let c = cos(angle); let s = sin(angle);
 let local = vec2f(c * delta.x + s * delta.y, -s * delta.x + c * delta.y);
 let ellipseProgress = clamp(length(local / radii), 0.0, 1.0);
 let distance = 1.0 - params.radial.y;
 var progress = step(params.radial.y, ellipseProgress);
 if (abs(distance) > 0.0000001) {progress = clamp((ellipseProgress - params.radial.y) / distance, 0.0, 1.0);}
 return max(0.0, mix(params.values.z, params.values.w, progress));
}
@fragment fn fragment(input: VertexOutput) -> @location(0) vec4f {
 let radius = radiusAt(input.uv);
 if (radius <= 0.0) {return textureSampleLevel(source, sourceSampler, input.uv, 0);}
 let halfKernel = i32(clamp(ceil(radius / 2.0), 4.0, 32.0));
 let stride = radius / f32(halfKernel);
 let sigma = select(max(radius / 3.0, 0.0001), radius / 3.0, params.values.y == 0.0);
 let twoSigmaSq = 2.0 * sigma * sigma;
 var sum = vec4f(0); var weightSum = 0.0;
 for (var i = -32; i <= 32; i++) {
  if (abs(i) > halfKernel) {continue;}
  let offset = f32(i) * stride;
  let weight = exp(-(offset * offset) / twoSigmaSq);
  let uv = input.uv + params.direction / params.resolution * offset;
  sum += textureSampleLevel(source, sourceSampler, uv, 0) * weight;
  weightSum += weight;
 }
 return sum / weightSum;
}
`;




/***/ },

/***/ 9028
(__unused_webpack___webpack_module__, __webpack_exports__, __webpack_require__) {

/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   c: () => (/* binding */ buildGaussianBlurFs)
/* harmony export */ });
// src/gaussian-blur-shader.ts
var buildGaussianBlurFs = (direction) => {
  const dirVec = direction === "horizontal" ? "vec2(1.0, 0.0)" : "vec2(0.0, 1.0)";
  return `#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uSource;
uniform float uRadius;
uniform vec2 uTexelSize;

const int MIN_KERNEL_HALF = 4;
const int MAX_KERNEL_HALF = 32;
const float TARGET_SAMPLE_DISTANCE_PX = 2.0;
const vec2 DIRECTION = ${dirVec};

void main() {
	if (uRadius <= 0.0) {
		fragColor = texture(uSource, vUv);
		return;
	}

	int kernelHalf = int(
		min(
			float(MAX_KERNEL_HALF),
			max(float(MIN_KERNEL_HALF), ceil(uRadius / TARGET_SAMPLE_DISTANCE_PX))
		)
	);
	float pixelStride = uRadius / float(kernelHalf);
	float sigma = uRadius / 3.0;
	float twoSigmaSq = 2.0 * sigma * sigma;

	vec4 sum = vec4(0.0);
	float weightSum = 0.0;

	for (int i = -MAX_KERNEL_HALF; i <= MAX_KERNEL_HALF; ++i) {
		if (abs(i) > kernelHalf) {
			continue;
		}

		float offsetPx = float(i) * pixelStride;
		float w = exp(-(offsetPx * offsetPx) / twoSigmaSq);
		vec2 uv = vUv + DIRECTION * uTexelSize * offsetPx;
		sum += texture(uSource, uv) * w;
		weightSum += w;
	}

	fragColor = sum / weightSum;
}
`;
};




/***/ },

/***/ 7223
(__unused_webpack___webpack_module__, __webpack_exports__, __webpack_require__) {

/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   $h: () => (/* binding */ cleanupWebGpuMultipass),
/* harmony export */   JM: () => (/* binding */ applyWebGpuMultipass),
/* harmony export */   NK: () => (/* binding */ WEBGPU_MULTIPASS_BINDINGS),
/* harmony export */   SB: () => (/* binding */ setupWebGpuMultipass)
/* harmony export */ });
/* harmony import */ var _index_tvfexb7s_mjs__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(4541);


// src/webgpu-multipass-runtime.ts
var WEBGPU_MULTIPASS_BINDINGS = `
${_index_tvfexb7s_mjs__WEBPACK_IMPORTED_MODULE_0__/* .WEBGPU_SINGLE_PASS_VERTEX */ .fH}
@group(0) @binding(0) var source: texture_2d<f32>;
@group(0) @binding(1) var sourceSampler: sampler;
@group(0) @binding(2) var<uniform> params: Params;
@group(0) @binding(3) var secondary: texture_2d<f32>;
`;
var setupWebGpuMultipass = (target, label) => {
  const context = target.getContext("webgpu");
  if (!context)
    throw new Error(`WebGPU is not available for the ${label} effect`);
  return { context, label, resources: null };
};
var cleanupWebGpuMultipass = (state) => {
  state.resources?.source?.texture.destroy();
  state.resources?.auxiliary?.texture.destroy();
  state.resources?.textures.forEach((texture) => texture.destroy());
  state.resources?.passes.forEach((pass) => pass.uniforms.destroy());
  state.resources = null;
  state.context.unconfigure();
};
var applyWebGpuMultipass = ({
  state,
  source,
  width,
  height,
  device,
  passes,
  auxiliarySource
}) => {
  if (state.resources && state.resources.device !== device)
    cleanupWebGpuMultipass(state);
  if (!state.resources) {
    const format = navigator.gpu.getPreferredCanvasFormat();
    state.context.configure({ device, format, alphaMode: "premultiplied" });
    const layout = device.createBindGroupLayout({
      entries: [
        { binding: 0, visibility: GPUShaderStage.FRAGMENT, texture: {} },
        { binding: 1, visibility: GPUShaderStage.FRAGMENT, sampler: {} },
        {
          binding: 2,
          visibility: GPUShaderStage.FRAGMENT,
          buffer: { type: "uniform" }
        },
        { binding: 3, visibility: GPUShaderStage.FRAGMENT, texture: {} }
      ]
    });
    state.resources = {
      device,
      format,
      layout,
      sampler: device.createSampler({ magFilter: "linear", minFilter: "linear" }),
      passes: [],
      textures: [],
      source: null,
      auxiliary: null,
      width,
      height
    };
  }
  const r = state.resources;
  const sourceWidth = "displayWidth" in source ? source.displayWidth : ("videoWidth" in source) ? source.videoWidth : ("naturalWidth" in source) ? source.naturalWidth : typeof source.width === "number" ? source.width : source.width.baseVal.value;
  const sourceHeight = "displayHeight" in source ? source.displayHeight : ("videoHeight" in source) ? source.videoHeight : ("naturalHeight" in source) ? source.naturalHeight : typeof source.height === "number" ? source.height : source.height.baseVal.value;
  if (r.source && (r.source.width !== sourceWidth || r.source.height !== sourceHeight)) {
    r.source.texture.destroy();
    r.source = null;
  }
  if (!r.source) {
    r.source = {
      width: sourceWidth,
      height: sourceHeight,
      texture: device.createTexture({
        size: [sourceWidth, sourceHeight],
        format: "rgba8unorm",
        usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST | GPUTextureUsage.RENDER_ATTACHMENT
      })
    };
  }
  device.queue.copyExternalImageToTexture({ source }, { texture: r.source.texture, premultipliedAlpha: true }, [sourceWidth, sourceHeight]);
  if (r.auxiliary && (!auxiliarySource || r.auxiliary.width !== auxiliarySource.width || r.auxiliary.height !== auxiliarySource.height)) {
    r.auxiliary.texture.destroy();
    r.auxiliary = null;
  }
  if (auxiliarySource) {
    if (!r.auxiliary)
      r.auxiliary = {
        width: auxiliarySource.width,
        height: auxiliarySource.height,
        texture: device.createTexture({
          size: [auxiliarySource.width, auxiliarySource.height],
          format: "rgba8unorm",
          usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST | GPUTextureUsage.RENDER_ATTACHMENT
        })
      };
    device.queue.copyExternalImageToTexture({ source: auxiliarySource }, { texture: r.auxiliary.texture, premultipliedAlpha: true }, [auxiliarySource.width, auxiliarySource.height]);
  }
  if (r.width !== width || r.height !== height) {
    r.textures.forEach((texture) => texture.destroy());
    r.textures.length = 0;
    r.width = width;
    r.height = height;
  }
  const lastReaders = passes.map((_, index) => index);
  for (let index = 0;index < passes.length; index++) {
    for (const input of [passes[index].source, passes[index].secondary]) {
      if (input >= 0)
        lastReaders[input] = index;
    }
  }
  const outputSlots = [];
  const freeAfter = [];
  for (let index = 0;index < passes.length - 1; index++) {
    let slot = freeAfter.findIndex((lastReader) => lastReader < index);
    if (slot === -1)
      slot = freeAfter.length;
    freeAfter[slot] = lastReaders[index];
    outputSlots.push(slot);
  }
  while (r.textures.length < freeAfter.length) {
    r.textures.push(device.createTexture({
      size: [width, height],
      format: "rgba8unorm",
      usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.RENDER_ATTACHMENT
    }));
  }
  while (r.textures.length > freeAfter.length)
    r.textures.pop()?.destroy();
  while (r.passes.length > passes.length)
    r.passes.pop()?.uniforms.destroy();
  const encoder = device.createCommandEncoder();
  for (let index = 0;index < passes.length; index++) {
    const pass = passes[index];
    const format = index === passes.length - 1 ? r.format : "rgba8unorm";
    const size = Math.max(16, Math.ceil(pass.uniforms.byteLength / 16) * 16);
    let resources = r.passes[index];
    if (!resources || resources.shader !== pass.shader || resources.size !== size || resources.format !== format) {
      resources?.uniforms.destroy();
      const module = device.createShaderModule({
        code: pass.shader,
        label: state.label
      });
      resources = {
        shader: pass.shader,
        size,
        format,
        pipeline: device.createRenderPipeline({
          label: state.label,
          layout: device.createPipelineLayout({ bindGroupLayouts: [r.layout] }),
          vertex: { module, entryPoint: "vertex" },
          fragment: { module, entryPoint: "fragment", targets: [{ format }] },
          primitive: { topology: "triangle-list" }
        }),
        uniforms: device.createBuffer({
          size,
          usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST
        })
      };
      r.passes[index] = resources;
    }
    device.queue.writeBuffer(resources.uniforms, 0, pass.uniforms);
    const bindGroup = device.createBindGroup({
      layout: r.layout,
      entries: [
        {
          binding: 0,
          resource: (pass.source === -1 ? r.source.texture : r.textures[outputSlots[pass.source]]).createView()
        },
        { binding: 1, resource: r.sampler },
        { binding: 2, resource: { buffer: resources.uniforms } },
        {
          binding: 3,
          resource: (pass.secondary === -2 && r.auxiliary ? r.auxiliary.texture : pass.secondary === -1 ? r.source.texture : r.textures[outputSlots[pass.secondary]]).createView()
        }
      ]
    });
    const renderPass = encoder.beginRenderPass({
      colorAttachments: [
        {
          view: (index === passes.length - 1 ? state.context.getCurrentTexture() : r.textures[outputSlots[index]]).createView(),
          clearValue: { r: 0, g: 0, b: 0, a: 0 },
          loadOp: "clear",
          storeOp: "store"
        }
      ]
    });
    renderPass.setPipeline(resources.pipeline);
    renderPass.setBindGroup(0, bindGroup);
    renderPass.draw(3);
    renderPass.end();
  }
  device.queue.submit([encoder.finish()]);
};




/***/ },

/***/ 4541
(__unused_webpack___webpack_module__, __webpack_exports__, __webpack_require__) {

/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   DS: () => (/* binding */ setupWebGpuSinglePass),
/* harmony export */   Gl: () => (/* binding */ cleanupWebGpuSinglePass),
/* harmony export */   UI: () => (/* binding */ applyWebGpuSinglePass),
/* harmony export */   fH: () => (/* binding */ WEBGPU_SINGLE_PASS_VERTEX)
/* harmony export */ });
// src/webgpu-single-pass-runtime.ts
var WEBGPU_SINGLE_PASS_VERTEX = `
struct VertexOutput {
	@builtin(position) position: vec4f,
	@location(0) uv: vec2f,
}

@vertex fn vertex(@builtin(vertex_index) index: u32) -> VertexOutput {
	let positions = array<vec2f, 3>(vec2f(-1, -1), vec2f(3, -1), vec2f(-1, 3));
	let position = positions[index];
	var output: VertexOutput;
	output.position = vec4f(position, 0, 1);
	output.uv = vec2f(position.x * 0.5 + 0.5, 0.5 - position.y * 0.5);
	return output;
}
`;
var setupWebGpuSinglePass = (target, label) => {
  const context = target.getContext("webgpu");
  if (!context) {
    throw new Error(`WebGPU is not available for the ${label} effect`);
  }
  return { context, label, resources: null };
};
var cleanupWebGpuSinglePass = (state) => {
  state.resources?.source?.texture.destroy();
  state.resources?.uniforms.destroy();
  state.resources?.auxiliary?.texture.destroy();
  state.resources = null;
  state.context.unconfigure();
};
var applyWebGpuSinglePass = ({
  state,
  source,
  device,
  shader,
  uniformData
}, options = null) => {
  const sourceFilter = options?.sourceFilter ?? "linear";
  const auxiliaryTexture = options?.auxiliaryTexture ?? null;
  const width = "displayWidth" in source ? source.displayWidth : ("videoWidth" in source) ? source.videoWidth : ("naturalWidth" in source) ? source.naturalWidth : typeof source.width === "number" ? source.width : source.width.baseVal.value;
  const height = "displayHeight" in source ? source.displayHeight : ("videoHeight" in source) ? source.videoHeight : ("naturalHeight" in source) ? source.naturalHeight : typeof source.height === "number" ? source.height : source.height.baseVal.value;
  const uniformBufferSize = Math.max(16, Math.ceil(uniformData.byteLength / 16) * 16);
  if (state.resources && (state.resources.device !== device || state.resources.shader !== shader || state.resources.uniformBufferSize !== uniformBufferSize || state.resources.sourceFilter !== sourceFilter || (state.resources.auxiliary?.width ?? null) !== (auxiliaryTexture?.width ?? null) || (state.resources.auxiliary?.height ?? null) !== (auxiliaryTexture?.height ?? null) || (state.resources.auxiliary?.format ?? null) !== (auxiliaryTexture?.format ?? null))) {
    cleanupWebGpuSinglePass(state);
  }
  if (!state.resources) {
    const format = navigator.gpu.getPreferredCanvasFormat();
    state.context.configure({ device, format, alphaMode: "premultiplied" });
    const module = device.createShaderModule({
      code: shader,
      label: state.label
    });
    const bindGroupLayout = device.createBindGroupLayout({
      entries: [
        ...auxiliaryTexture ? [
          {
            binding: 3,
            visibility: GPUShaderStage.FRAGMENT,
            texture: {
              sampleType: auxiliaryTexture.format === "rgba32float" ? "unfilterable-float" : "float"
            }
          }
        ] : [],
        { binding: 0, visibility: GPUShaderStage.FRAGMENT, texture: {} },
        { binding: 1, visibility: GPUShaderStage.FRAGMENT, sampler: {} },
        {
          binding: 2,
          visibility: GPUShaderStage.FRAGMENT,
          buffer: { type: "uniform" }
        }
      ]
    });
    const pipeline = device.createRenderPipeline({
      label: state.label,
      layout: device.createPipelineLayout({
        bindGroupLayouts: [bindGroupLayout]
      }),
      vertex: { module, entryPoint: "vertex" },
      fragment: { module, entryPoint: "fragment", targets: [{ format }] },
      primitive: { topology: "triangle-list" }
    });
    const uniforms = device.createBuffer({
      size: uniformBufferSize,
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST
    });
    const sampler = device.createSampler({
      addressModeU: "clamp-to-edge",
      addressModeV: "clamp-to-edge",
      magFilter: sourceFilter,
      minFilter: sourceFilter
    });
    const auxiliary = auxiliaryTexture ? {
      texture: device.createTexture({
        size: [auxiliaryTexture.width, auxiliaryTexture.height],
        format: auxiliaryTexture.format,
        usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST
      }),
      width: auxiliaryTexture.width,
      height: auxiliaryTexture.height,
      format: auxiliaryTexture.format,
      uploadedData: null
    } : null;
    state.resources = {
      device,
      shader,
      uniformBufferSize,
      sourceFilter,
      auxiliary,
      pipeline,
      uniforms,
      sampler,
      bindGroupLayout,
      source: null
    };
  }
  const { resources } = state;
  if (resources.source && (resources.source.width !== width || resources.source.height !== height)) {
    resources.source.texture.destroy();
    resources.source = null;
  }
  if (!resources.source) {
    const texture = device.createTexture({
      size: [width, height],
      format: "rgba8unorm",
      usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST | GPUTextureUsage.RENDER_ATTACHMENT
    });
    const bindGroup = device.createBindGroup({
      layout: resources.bindGroupLayout,
      entries: [
        ...resources.auxiliary ? [{ binding: 3, resource: resources.auxiliary.texture.createView() }] : [],
        { binding: 0, resource: texture.createView() },
        { binding: 1, resource: resources.sampler },
        { binding: 2, resource: { buffer: resources.uniforms } }
      ]
    });
    resources.source = { texture, bindGroup, width, height };
  }
  if (auxiliaryTexture && resources.auxiliary && resources.auxiliary.uploadedData !== auxiliaryTexture.data) {
    device.queue.writeTexture({ texture: resources.auxiliary.texture }, auxiliaryTexture.data, {
      bytesPerRow: auxiliaryTexture.width * 4 * auxiliaryTexture.data.BYTES_PER_ELEMENT
    }, [auxiliaryTexture.width, auxiliaryTexture.height]);
    resources.auxiliary.uploadedData = auxiliaryTexture.data;
  }
  device.queue.copyExternalImageToTexture({ source }, { texture: resources.source.texture, premultipliedAlpha: true }, [width, height]);
  device.queue.writeBuffer(resources.uniforms, 0, uniformData);
  const encoder = device.createCommandEncoder();
  const pass = encoder.beginRenderPass({
    colorAttachments: [
      {
        view: state.context.getCurrentTexture().createView(),
        clearValue: { r: 0, g: 0, b: 0, a: 0 },
        loadOp: "clear",
        storeOp: "store"
      }
    ]
  });
  pass.setPipeline(resources.pipeline);
  pass.setBindGroup(0, resources.source.bindGroup);
  pass.draw(3);
  pass.end();
  device.queue.submit([encoder.finish()]);
};




/***/ },

/***/ 8197
(__unused_webpack___webpack_module__, __webpack_exports__, __webpack_require__) {

/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   $j: () => (/* binding */ DEFAULT_BRIGHTNESS_AMOUNT),
/* harmony export */   FC: () => (/* binding */ assertOptionalFiniteNumber),
/* harmony export */   HQ: () => (/* binding */ colorAmountSchema),
/* harmony export */   J: () => (/* binding */ brightnessAmountSchema),
/* harmony export */   Oj: () => (/* binding */ clampColorChannel),
/* harmony export */   PQ: () => (/* binding */ DEFAULT_AMOUNT),
/* harmony export */   XP: () => (/* binding */ validateNonNegative),
/* harmony export */   Xb: () => (/* binding */ hueDegreesSchema),
/* harmony export */   cz: () => (/* binding */ validateSignedUnitInterval),
/* harmony export */   n7: () => (/* binding */ DEFAULT_HUE_DEGREES),
/* harmony export */   y0: () => (/* binding */ colorMultiplierSchema),
/* harmony export */   yk: () => (/* binding */ validateUnitInterval),
/* harmony export */   zp: () => (/* binding */ parseColorRgba)
/* harmony export */ });
/* harmony import */ var _index_4fvp93ps_mjs__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(4075);


// src/color-utils.ts
var DEFAULT_AMOUNT = 1;
var DEFAULT_BRIGHTNESS_AMOUNT = 0;
var DEFAULT_HUE_DEGREES = 0;
var colorAmountSchema = {
  type: "number",
  min: 0,
  max: 1,
  step: 0.01,
  default: DEFAULT_AMOUNT,
  description: "Amount",
  hiddenFromList: false
};
var colorMultiplierSchema = {
  type: "number",
  min: 0,
  step: 0.01,
  default: DEFAULT_AMOUNT,
  description: "Amount",
  hiddenFromList: false
};
var brightnessAmountSchema = {
  type: "number",
  min: -1,
  max: 1,
  step: 0.01,
  default: DEFAULT_BRIGHTNESS_AMOUNT,
  description: "Amount",
  hiddenFromList: false
};
var hueDegreesSchema = {
  type: "rotation-degrees",
  step: 1,
  default: DEFAULT_HUE_DEGREES,
  description: "Degrees"
};
var assertOptionalFiniteNumber = (value, name) => {
  if (value === undefined) {
    return;
  }
  ;(0,_index_4fvp93ps_mjs__WEBPACK_IMPORTED_MODULE_0__/* .assertRequiredFiniteNumber */ .c1)(value, name);
};
var validateUnitInterval = (value, name) => {
  if (value < 0) {
    throw new TypeError(`"${name}" must be >= 0, but got ${JSON.stringify(value)}`);
  }
  if (value > 1) {
    throw new TypeError(`"${name}" must be <= 1, but got ${JSON.stringify(value)}`);
  }
};
var validateNonNegative = (value, name) => {
  if (value < 0) {
    throw new TypeError(`"${name}" must be >= 0, but got ${JSON.stringify(value)}`);
  }
};
var validateSignedUnitInterval = (value, name) => {
  if (value < -1) {
    throw new TypeError(`"${name}" must be >= -1, but got ${JSON.stringify(value)}`);
  }
  if (value > 1) {
    throw new TypeError(`"${name}" must be <= 1, but got ${JSON.stringify(value)}`);
  }
};
var clampColorChannel = (value) => {
  return Math.max(0, Math.min(255, value));
};
var parseColorRgba = (ctx, color) => {
  ctx.clearRect(0, 0, 1, 1);
  ctx.fillStyle = color;
  ctx.fillRect(0, 0, 1, 1);
  const { data } = ctx.getImageData(0, 0, 1, 1);
  return [data[0], data[1], data[2], data[3]];
};




/***/ }

}]);
//# sourceMappingURL=4851.bundle.js.map