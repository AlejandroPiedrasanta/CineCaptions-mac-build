"use strict";
(self["webpackChunkcinecaptions_pro_remotion"] = self["webpackChunkcinecaptions_pro_remotion"] || []).push([[3313],{

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

/***/ 6654
(__unused_webpack___webpack_module__, __webpack_exports__, __webpack_require__) {

/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   F7: () => (/* binding */ BLUR_FS_HORIZONTAL),
/* harmony export */   FG: () => (/* binding */ BLUR_FS_VERTICAL),
/* harmony export */   WV: () => (/* binding */ BLUR_VS)
/* harmony export */ });
/* harmony import */ var _index_evy8hyah_mjs__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(9028);


// src/blur/blur-shaders.ts
var BLUR_VS = `#version 300 es
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aUv;
out vec2 vUv;
void main() {
	vUv = aUv;
	gl_Position = vec4(aPos, 0.0, 1.0);
}
`;
var BLUR_FS_HORIZONTAL = (0,_index_evy8hyah_mjs__WEBPACK_IMPORTED_MODULE_0__/* .buildGaussianBlurFs */ .c)("horizontal");
var BLUR_FS_VERTICAL = (0,_index_evy8hyah_mjs__WEBPACK_IMPORTED_MODULE_0__/* .buildGaussianBlurFs */ .c)("vertical");




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

/***/ 8060
(__unused_webpack___webpack_module__, __webpack_exports__, __webpack_require__) {

/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   S: () => (/* binding */ publicUvToShaderUv)
/* harmony export */ });
// src/uv-coordinate.ts
var publicUvToShaderUv = (uv) => {
  return [uv[0], 1 - uv[1]];
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




/***/ },

/***/ 3313
(__unused_webpack___webpack_module__, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   regionBlur: () => (/* binding */ regionBlur)
/* harmony export */ });
/* harmony import */ var _index_kkvzt8b7_mjs__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(7223);
/* harmony import */ var _index_618ky75w_mjs__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(224);
/* harmony import */ var _index_b86qstcs_mjs__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(6654);
/* harmony import */ var _index_gnsce796_mjs__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(8060);
/* harmony import */ var _index_wxhvgv2s_mjs__WEBPACK_IMPORTED_MODULE_4__ = __webpack_require__(8197);
/* harmony import */ var _index_4fvp93ps_mjs__WEBPACK_IMPORTED_MODULE_5__ = __webpack_require__(4075);
/* harmony import */ var remotion__WEBPACK_IMPORTED_MODULE_6__ = __webpack_require__(3947);







// src/region-blur/index.ts


// src/region-blur/region-blur-runtime.ts

var { createWebGL2ContextError } = remotion__WEBPACK_IMPORTED_MODULE_6__.Internals;
var COMPOSITE_FRAGMENT_SHADER = `#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uSource;
uniform sampler2D uBlurred;
uniform vec2 uResolution;
uniform vec2 uTopLeft;
uniform vec2 uBottomRight;
uniform float uFeather;
uniform float uRoundness;

float roundedBoxDistance(vec2 point, vec2 center, vec2 halfSize, float radius) {
	vec2 offset = abs(point - center) - halfSize + vec2(radius);
	return length(max(offset, vec2(0.0))) + min(max(offset.x, offset.y), 0.0) - radius;
}

void main() {
	vec2 minimum = vec2(uTopLeft.x, uBottomRight.y) * uResolution;
	vec2 maximum = vec2(uBottomRight.x, uTopLeft.y) * uResolution;
	vec2 halfSize = (maximum - minimum) * 0.5;
	vec2 center = (minimum + maximum) * 0.5;
	float cornerRadius = min(halfSize.x, halfSize.y) * uRoundness;
	float distanceToRegion = roundedBoxDistance(
		vUv * uResolution,
		center,
		halfSize,
		cornerRadius
	);
	float mask = uFeather <= 0.0
		? (distanceToRegion <= 0.0 ? 1.0 : 0.0)
		: 1.0 - smoothstep(-uFeather * 0.5, uFeather * 0.5, distanceToRegion);

	fragColor = mix(texture(uSource, vUv), texture(uBlurred, vUv), mask);
}
`;
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
    throw new Error(`Shader compile failed: ${log ?? "(no log)"}`);
  }
  return shader;
};
var createProgram = (gl, vertexSource, fragmentSource) => {
  const vertexShader = compileShader(gl, gl.VERTEX_SHADER, vertexSource);
  const fragmentShader = compileShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
  const program = gl.createProgram();
  if (!program) {
    throw new Error("Failed to create WebGL program");
  }
  gl.attachShader(program, vertexShader);
  gl.attachShader(program, fragmentShader);
  gl.linkProgram(program);
  gl.deleteShader(vertexShader);
  gl.deleteShader(fragmentShader);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const log = gl.getProgramInfoLog(program);
    gl.deleteProgram(program);
    throw new Error(`Program link failed: ${log ?? "(no log)"}`);
  }
  return program;
};
var createTexture = (gl) => {
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
  source: gl.getUniformLocation(program, "uSource"),
  radius: gl.getUniformLocation(program, "uRadius"),
  texelSize: gl.getUniformLocation(program, "uTexelSize")
});
var setupRegionBlur = (target) => {
  const gl = target.getContext("webgl2", {
    premultipliedAlpha: true,
    alpha: true,
    preserveDrawingBuffer: true
  });
  if (!gl) {
    throw createWebGL2ContextError("region blur effect");
  }
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
  const horizontalProgram = createProgram(gl, _index_b86qstcs_mjs__WEBPACK_IMPORTED_MODULE_2__/* .BLUR_VS */ .WV, _index_b86qstcs_mjs__WEBPACK_IMPORTED_MODULE_2__/* .BLUR_FS_HORIZONTAL */ .F7);
  const verticalProgram = createProgram(gl, _index_b86qstcs_mjs__WEBPACK_IMPORTED_MODULE_2__/* .BLUR_VS */ .WV, _index_b86qstcs_mjs__WEBPACK_IMPORTED_MODULE_2__/* .BLUR_FS_VERTICAL */ .FG);
  const compositeProgram = createProgram(gl, _index_b86qstcs_mjs__WEBPACK_IMPORTED_MODULE_2__/* .BLUR_VS */ .WV, COMPOSITE_FRAGMENT_SHADER);
  const vao = gl.createVertexArray();
  const vbo = gl.createBuffer();
  const framebuffer = gl.createFramebuffer();
  if (!vao || !vbo || !framebuffer) {
    throw new Error("Failed to create region blur WebGL resources");
  }
  gl.bindVertexArray(vao);
  gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 0, 0, 1, -1, 1, 0, -1, 1, 0, 1, 1, 1, 1, 1]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 16, 0);
  gl.enableVertexAttribArray(1);
  gl.vertexAttribPointer(1, 2, gl.FLOAT, false, 16, 8);
  gl.bindVertexArray(null);
  return {
    gl,
    horizontalProgram,
    verticalProgram,
    compositeProgram,
    vao,
    vbo,
    sourceTexture: createTexture(gl),
    horizontalTexture: createTexture(gl),
    blurredTexture: createTexture(gl),
    framebuffer,
    horizontalUniforms: getBlurUniforms(gl, horizontalProgram),
    verticalUniforms: getBlurUniforms(gl, verticalProgram),
    compositeUniforms: {
      source: gl.getUniformLocation(compositeProgram, "uSource"),
      blurred: gl.getUniformLocation(compositeProgram, "uBlurred"),
      resolution: gl.getUniformLocation(compositeProgram, "uResolution"),
      topLeft: gl.getUniformLocation(compositeProgram, "uTopLeft"),
      bottomRight: gl.getUniformLocation(compositeProgram, "uBottomRight"),
      feather: gl.getUniformLocation(compositeProgram, "uFeather"),
      roundness: gl.getUniformLocation(compositeProgram, "uRoundness")
    }
  };
};
var draw = (state) => {
  state.gl.bindVertexArray(state.vao);
  state.gl.drawArrays(state.gl.TRIANGLE_STRIP, 0, 4);
  state.gl.bindVertexArray(null);
};
var allocateTexture = (gl, texture, width, height) => {
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
};
var renderBlurPass = ({
  state,
  program,
  uniforms,
  input,
  output,
  width,
  height,
  radius
}) => {
  const { gl } = state;
  gl.bindFramebuffer(gl.FRAMEBUFFER, state.framebuffer);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, output, 0);
  if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) {
    throw new Error("Region blur framebuffer is incomplete");
  }
  gl.clear(gl.COLOR_BUFFER_BIT);
  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D, input);
  gl.useProgram(program);
  if (uniforms.source)
    gl.uniform1i(uniforms.source, 0);
  if (uniforms.radius)
    gl.uniform1f(uniforms.radius, radius);
  if (uniforms.texelSize) {
    gl.uniform2f(uniforms.texelSize, 1 / width, 1 / height);
  }
  draw(state);
};
var applyRegionBlur = ({
  state,
  source,
  width,
  height,
  flipSourceY,
  topLeft,
  bottomRight,
  blurRadius,
  feather,
  roundness
}) => {
  const { gl } = state;
  gl.viewport(0, 0, width, height);
  gl.clearColor(0, 0, 0, 0);
  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, flipSourceY);
  gl.bindTexture(gl.TEXTURE_2D, state.sourceTexture);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source);
  allocateTexture(gl, state.horizontalTexture, width, height);
  allocateTexture(gl, state.blurredTexture, width, height);
  renderBlurPass({
    state,
    program: state.horizontalProgram,
    uniforms: state.horizontalUniforms,
    input: state.sourceTexture,
    output: state.horizontalTexture,
    width,
    height,
    radius: blurRadius
  });
  renderBlurPass({
    state,
    program: state.verticalProgram,
    uniforms: state.verticalUniforms,
    input: state.horizontalTexture,
    output: state.blurredTexture,
    width,
    height,
    radius: blurRadius
  });
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  gl.clear(gl.COLOR_BUFFER_BIT);
  gl.useProgram(state.compositeProgram);
  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D, state.sourceTexture);
  gl.activeTexture(gl.TEXTURE1);
  gl.bindTexture(gl.TEXTURE_2D, state.blurredTexture);
  const topLeftShader = (0,_index_gnsce796_mjs__WEBPACK_IMPORTED_MODULE_3__/* .publicUvToShaderUv */ .S)(topLeft);
  const bottomRightShader = (0,_index_gnsce796_mjs__WEBPACK_IMPORTED_MODULE_3__/* .publicUvToShaderUv */ .S)(bottomRight);
  const uniforms = state.compositeUniforms;
  if (uniforms.source)
    gl.uniform1i(uniforms.source, 0);
  if (uniforms.blurred)
    gl.uniform1i(uniforms.blurred, 1);
  if (uniforms.resolution)
    gl.uniform2f(uniforms.resolution, width, height);
  if (uniforms.topLeft) {
    gl.uniform2f(uniforms.topLeft, topLeftShader[0], topLeftShader[1]);
  }
  if (uniforms.bottomRight) {
    gl.uniform2f(uniforms.bottomRight, bottomRightShader[0], bottomRightShader[1]);
  }
  if (uniforms.feather)
    gl.uniform1f(uniforms.feather, feather);
  if (uniforms.roundness)
    gl.uniform1f(uniforms.roundness, roundness);
  draw(state);
  gl.activeTexture(gl.TEXTURE1);
  gl.bindTexture(gl.TEXTURE_2D, null);
  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D, null);
  gl.useProgram(null);
};
var cleanupRegionBlur = (state) => {
  const { gl } = state;
  gl.deleteFramebuffer(state.framebuffer);
  gl.deleteTexture(state.sourceTexture);
  gl.deleteTexture(state.horizontalTexture);
  gl.deleteTexture(state.blurredTexture);
  gl.deleteBuffer(state.vbo);
  gl.deleteVertexArray(state.vao);
  gl.deleteProgram(state.horizontalProgram);
  gl.deleteProgram(state.verticalProgram);
  gl.deleteProgram(state.compositeProgram);
};

// src/region-blur/webgpu-shader.ts
var REGION_BLUR_WEBGPU_SHADER = `
${_index_kkvzt8b7_mjs__WEBPACK_IMPORTED_MODULE_0__/* .WEBGPU_MULTIPASS_BINDINGS */ .NK}
struct Params {resolution: vec2f, feather: f32, roundness: f32, corners: vec4f,}
@fragment fn fragment(input: VertexOutput) -> @location(0) vec4f {
 let minimum = params.corners.xy * params.resolution;
 let maximum = params.corners.zw * params.resolution;
 let halfSize = (maximum - minimum) * 0.5;
 let center = (minimum + maximum) * 0.5;
 let radius = min(halfSize.x, halfSize.y) * params.roundness;
 let offset = abs(input.uv * params.resolution - center) - halfSize + vec2f(radius);
 let distance = length(max(offset, vec2f(0))) + min(max(offset.x, offset.y), 0.0) - radius;
 var mask = select(0.0, 1.0, distance <= 0.0);
 if (params.feather > 0.0) {mask = 1.0 - smoothstep(-params.feather * 0.5, params.feather * 0.5, distance);}
 return mix(textureSampleLevel(source, sourceSampler, input.uv, 0), textureSampleLevel(secondary, sourceSampler, input.uv, 0), mask);
}
`;

// src/region-blur/index.ts
var { createEffect } = remotion__WEBPACK_IMPORTED_MODULE_6__.Internals;
var DEFAULT_BLUR_RADIUS = 40;
var DEFAULT_FEATHER = 0;
var DEFAULT_ROUNDNESS = 0;
var regionBlurSchema = {
  topLeft: {
    type: "uv-coordinate",
    min: -1,
    max: 2,
    step: 0.01,
    default: undefined,
    description: "Top left"
  },
  bottomRight: {
    type: "uv-coordinate",
    min: -1,
    max: 2,
    step: 0.01,
    default: undefined,
    description: "Bottom right"
  },
  blurRadius: {
    type: "number",
    min: 0,
    max: 200,
    step: 1,
    default: DEFAULT_BLUR_RADIUS,
    description: "Blur radius",
    hiddenFromList: false
  },
  feather: {
    type: "number",
    min: 0,
    max: 200,
    step: 1,
    default: DEFAULT_FEATHER,
    description: "Feather",
    hiddenFromList: false
  },
  roundness: {
    type: "number",
    min: 0,
    max: 1,
    step: 0.01,
    default: DEFAULT_ROUNDNESS,
    description: "Roundness",
    hiddenFromList: false
  }
};
var resolve = (params) => ({
  topLeft: [...params.topLeft],
  bottomRight: [...params.bottomRight],
  blurRadius: params.blurRadius ?? DEFAULT_BLUR_RADIUS,
  feather: params.feather ?? DEFAULT_FEATHER,
  roundness: params.roundness ?? DEFAULT_ROUNDNESS
});
var assertRequiredUvCoordinate = (value, name) => {
  if (!Array.isArray(value) || value.length !== 2 || value.some((item) => typeof item !== "number" || !Number.isFinite(item))) {
    throw new TypeError(`"${name}" must be a [number, number] tuple`);
  }
};
var validateRegionBlurParams = (params) => {
  (0,_index_4fvp93ps_mjs__WEBPACK_IMPORTED_MODULE_5__/* .assertEffectParamsObject */ .db)(params, "Region blur");
  assertRequiredUvCoordinate(params.topLeft, "topLeft");
  assertRequiredUvCoordinate(params.bottomRight, "bottomRight");
  (0,_index_wxhvgv2s_mjs__WEBPACK_IMPORTED_MODULE_4__/* .assertOptionalFiniteNumber */ .FC)(params.blurRadius, "blurRadius");
  (0,_index_wxhvgv2s_mjs__WEBPACK_IMPORTED_MODULE_4__/* .assertOptionalFiniteNumber */ .FC)(params.feather, "feather");
  (0,_index_wxhvgv2s_mjs__WEBPACK_IMPORTED_MODULE_4__/* .assertOptionalFiniteNumber */ .FC)(params.roundness, "roundness");
  const resolved = resolve(params);
  (0,_index_wxhvgv2s_mjs__WEBPACK_IMPORTED_MODULE_4__/* .validateNonNegative */ .XP)(resolved.blurRadius, "blurRadius");
  (0,_index_wxhvgv2s_mjs__WEBPACK_IMPORTED_MODULE_4__/* .validateNonNegative */ .XP)(resolved.feather, "feather");
  (0,_index_wxhvgv2s_mjs__WEBPACK_IMPORTED_MODULE_4__/* .validateUnitInterval */ .yk)(resolved.roundness, "roundness");
  if (resolved.topLeft[0] >= resolved.bottomRight[0] || resolved.topLeft[1] >= resolved.bottomRight[1]) {
    throw new TypeError('"topLeft" must be above and to the left of "bottomRight"');
  }
};
var regionBlur = createEffect({
  type: "remotion/region-blur",
  label: "regionBlur()",
  documentationLink: "https://www.remotion.dev/docs/effects/region-blur",
  calculateKey: (params) => {
    const resolved = resolve(params);
    return `region-blur-${resolved.topLeft.join(":")}-${resolved.bottomRight.join(":")}-${resolved.blurRadius}-${resolved.feather}-${resolved.roundness}`;
  },
  implementations: {
    webgpu: remotion__WEBPACK_IMPORTED_MODULE_6__.Internals.createEffectImplementation({
      setup: (target) => (0,_index_kkvzt8b7_mjs__WEBPACK_IMPORTED_MODULE_0__/* .setupWebGpuMultipass */ .SB)(target, "region-blur"),
      apply: ({ source, width, height, params, state, gpuDevice }) => {
        if (!gpuDevice)
          throw new Error("A WebGPU device is required for this effect");
        const r = resolve(params);
        (0,_index_kkvzt8b7_mjs__WEBPACK_IMPORTED_MODULE_0__/* .applyWebGpuMultipass */ .JM)({
          auxiliarySource: null,
          state,
          source,
          width,
          height,
          device: gpuDevice,
          passes: [
            {
              shader: _index_618ky75w_mjs__WEBPACK_IMPORTED_MODULE_1__/* .GAUSSIAN_BLUR_WEBGPU_SHADER */ .j,
              uniforms: new Float32Array([
                width,
                height,
                1,
                0,
                r.blurRadius,
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
              source: -1,
              secondary: -1
            },
            {
              shader: _index_618ky75w_mjs__WEBPACK_IMPORTED_MODULE_1__/* .GAUSSIAN_BLUR_WEBGPU_SHADER */ .j,
              uniforms: new Float32Array([
                width,
                height,
                0,
                1,
                r.blurRadius,
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
              shader: REGION_BLUR_WEBGPU_SHADER,
              uniforms: new Float32Array([
                width,
                height,
                r.feather,
                r.roundness,
                ...r.topLeft,
                ...r.bottomRight
              ]),
              source: -1,
              secondary: 1
            }
          ]
        });
      },
      cleanup: _index_kkvzt8b7_mjs__WEBPACK_IMPORTED_MODULE_0__/* .cleanupWebGpuMultipass */ .$h
    }),
    webgl2: remotion__WEBPACK_IMPORTED_MODULE_6__.Internals.createEffectImplementation({
      setup: (target) => setupRegionBlur(target),
      apply: ({ source, width, height, params, state, flipSourceY }) => {
        const resolved = resolve(params);
        applyRegionBlur({
          state,
          source,
          width,
          height,
          flipSourceY,
          ...resolved
        });
      },
      cleanup: (state) => cleanupRegionBlur(state)
    })
  },
  schema: regionBlurSchema,
  validateParams: validateRegionBlurParams
});



/***/ }

}]);
//# sourceMappingURL=3313.bundle.js.map