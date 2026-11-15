export const BATH = [
  [0.00, '#0055FF'], [0.10, '#0066FF'], [0.20, '#007AFF'], [0.32, '#0A84FF'],
  [0.44, '#2563EB'], [0.54, '#3B82F6'], [0.64, '#4B96FF'], [0.74, '#2563EB'],
  [0.82, '#1D4ED8'], [0.90, '#4338CA'], [0.96, '#0A84FF'], [1.00, '#007AFF']
];

const glslColor = (hex) => {
  const v = [1, 3, 5].map((o) => (parseInt(hex.slice(o, o + 2), 16) / 255).toFixed(4));
  return `vec3(${v.join(', ')})`;
};

export const GLOW_THRESHOLD = 0.28;
export const INTRO_BAND = 0.20;
export const INTRO_WARP = 0.30;
export const INTRO_JITTER = 0.16;
export const INTRO_END = 1.0 + INTRO_WARP + INTRO_JITTER + INTRO_BAND;
export const SHAPE_MODES = { mixed: 0, squares: 1, circles: 2, triangles: 3 };

export const VERT = `#version 300 es
layout(location = 0) in vec2 position;
layout(location = 1) in vec2 uv;
out vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

export const NOISE_GLSL = `
vec3 mod289v3(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289v4(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289v4(((x * 34.0) + 10.0) * x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
vec3 fadeCurve(vec3 t) { return t * t * t * (t * (t * 6.0 - 15.0) + 10.0); }

float cnoise(vec3 P) {
  vec3 Pi0 = floor(P); vec3 Pi1 = Pi0 + vec3(1.0);
  Pi0 = mod289v3(Pi0); Pi1 = mod289v3(Pi1);
  vec3 Pf0 = fract(P); vec3 Pf1 = Pf0 - vec3(1.0);
  vec4 ix = vec4(Pi0.x, Pi1.x, Pi0.x, Pi1.x); vec4 iy = vec4(Pi0.yy, Pi1.yy);
  vec4 iz0 = Pi0.zzzz; vec4 iz1 = Pi1.zzzz;
  vec4 ixy = permute(permute(ix) + iy);
  vec4 ixy0 = permute(ixy + iz0); vec4 ixy1 = permute(ixy + iz1);
  vec4 gx0 = ixy0 * (1.0 / 7.0);
  vec4 gy0 = fract(floor(gx0) * (1.0 / 7.0)) - 0.5;
  gx0 = fract(gx0);
  vec4 gz0 = vec4(0.5) - abs(gx0) - abs(gy0); vec4 sz0 = step(gz0, vec4(0.0));
  gx0 -= sz0 * (step(vec4(0.0), gx0) - 0.5); gy0 -= sz0 * (step(vec4(0.0), gy0) - 0.5);
  vec4 gx1 = ixy1 * (1.0 / 7.0);
  vec4 gy1 = fract(floor(gx1) * (1.0 / 7.0)) - 0.5;
  gx1 = fract(gx1);
  vec4 gz1 = vec4(0.5) - abs(gx1) - abs(gy1); vec4 sz1 = step(gz1, vec4(0.0));
  gx1 -= sz1 * (step(vec4(0.0), gx1) - 0.5); gy1 -= sz1 * (step(vec4(0.0), gy1) - 0.5);
  vec3 g000 = vec3(gx0.x, gy0.x, gz0.x); vec3 g100 = vec3(gx0.y, gy0.y, gz0.y);
  vec3 g010 = vec3(gx0.z, gy0.z, gz0.z); vec3 g110 = vec3(gx0.w, gy0.w, gz0.w);
  vec3 g001 = vec3(gx1.x, gy1.x, gz1.x); vec3 g101 = vec3(gx1.y, gy1.y, gz1.y);
  vec3 g011 = vec3(gx1.z, gy1.z, gz1.z); vec3 g111 = vec3(gx1.w, gy1.w, gz1.w);
  vec4 norm0 = taylorInvSqrt(vec4(dot(g000, g000), dot(g010, g010), dot(g100, g100), dot(g110, g110)));
  g000 *= norm0.x; g010 *= norm0.y; g100 *= norm0.z; g110 *= norm0.w;
  vec4 norm1 = taylorInvSqrt(vec4(dot(g001, g001), dot(g011, g011), dot(g101, g101), dot(g111, g111)));
  g001 *= norm1.x; g011 *= norm1.y; g101 *= norm1.z; g111 *= norm1.w;
  float n000 = dot(g000, Pf0); float n100 = dot(g100, vec3(Pf1.x, Pf0.yz));
  float n010 = dot(g010, vec3(Pf0.x, Pf1.y, Pf0.z)); float n110 = dot(g110, vec3(Pf1.xy, Pf0.z));
  float n001 = dot(g001, vec3(Pf0.xy, Pf1.z)); float n101 = dot(g101, vec3(Pf1.x, Pf0.y, Pf1.z));
  float n011 = dot(g011, vec3(Pf0.x, Pf1.yz)); float n111 = dot(g111, Pf1);
  vec3 f = fadeCurve(Pf0);
  vec4 nz = mix(vec4(n000, n100, n010, n110), vec4(n001, n101, n011, n111), f.z);
  vec2 ny = mix(nz.xy, nz.zw, f.y);
  return 2.2 * mix(ny.x, ny.y, f.x);
}

float fbm(vec3 p) {
  float total = 0.0; float amplitude = 1.0; float weight = 0.0; float frequency = 1.0;
  for (int i = 0; i < 2; i++) {
    total += amplitude * cnoise(p * frequency);
    weight += amplitude;
    amplitude *= 0.5; frequency *= 2.0;
  }
  return total / weight;
}
`;

export const BATH_GLSL = `
const int BATH_N = ${BATH.length};
const float BATH_AT[${BATH.length}] = float[](${BATH.map(([t]) => t.toFixed(3)).join(', ')});
const vec3 BATH_RGB[${BATH.length}] = vec3[](${BATH.map(([, c]) => glslColor(c)).join(', ')});

vec3 bathRamp(float s) {
  s = clamp(s, 0.0, 1.0);
  for (int i = 1; i < BATH_N; i++) {
    if (s <= BATH_AT[i]) {
      float k = (s - BATH_AT[i - 1]) / max(1e-4, BATH_AT[i] - BATH_AT[i - 1]);
      return mix(BATH_RGB[i - 1], BATH_RGB[i], smoothstep(0.0, 1.0, k));
    }
  }
  return BATH_RGB[BATH_N - 1];
}

vec3 bath(vec2 uv, float t) {
  float s = uv.x + (uv.y - 0.5) * 0.14;
  s += 0.10 * fbm(vec3(uv * vec2(1.3, 1.9) + vec2(3.1, 7.7), t));
  s += 0.04 * sin(uv.y * 4.2 + uv.x * 2.0 + t * 1.7);
  return bathRamp(s);
}
`;

export const SCENE_FRAG = `#version 300 es
precision highp float;
precision highp int;
uniform vec4 uResolution, uPlacement, uGrid, uField, uMotion, uColor, uHover, uBackground;
uniform highp sampler2D tCharges;
out vec4 fragColor;
const vec2 SEED = vec2(12.9898, 78.233);
const float GLOW_TH = ${GLOW_THRESHOLD.toFixed(2)};
${NOISE_GLSL}
${BATH_GLSL}

float sdIsoTri(vec2 p, vec2 q) {
  vec2 pt = vec2(abs(p.x), p.y);
  vec2 a = pt - q * clamp(dot(pt, q) / dot(q, q), 0.0, 1.0);
  vec2 b = pt - q * vec2(clamp(pt.x / q.x, 0.0, 1.0), 1.0);
  float s = -sign(q.y);
  vec2 d = min(vec2(dot(a, a), s * (pt.x * q.y - pt.y * q.x)), vec2(dot(b, b), s * (pt.y - q.y)));
  return -sqrt(d.x) * sign(d.y);
}

float shapeDist(vec2 p, int shape, float c) {
  if (shape == 0) return max(abs(p.x), abs(p.y)) - c;
  if (shape == 1) return length(p) - c;
  return sdIsoTri(vec2(p.x, p.y + c), vec2(c, 2.0 * c));
}

float h21(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

void main() {
  vec2 res = uResolution.xy; float cellPx = uGrid.x; float dotSize = uGrid.y;
  int mode = int(uGrid.z + 0.5); int cols = int(uGrid.w + 0.5);
  vec3 bg = uBackground.rgb; bool toSurface = uHover.w < 0.5;
  vec4 empty = vec4(bg, toSurface ? 1.0 : 0.0);
  vec2 pixel = vec2(gl_FragCoord.x, res.y - gl_FragCoord.y);
  vec2 uv = pixel / res; vec2 origin = uPlacement.xy;
  int rows = int(uPlacement.z + 0.5);
  vec2 cell = floor((pixel - origin) / cellPx);
  if (cell.y < 0.0 || int(cell.y) >= rows || cell.x < 0.0 || int(cell.x) >= cols) {
    fragColor = empty; return;
  }
  vec2 center = origin + (cell + 0.5) * cellPx;
  vec2 local = (pixel - center) / (cellPx * 0.5);
  vec2 cellUv = center / res;
  float level = 1.0; float fade = uMotion.w;
  if (fade > 0.0) {
    vec2 q = abs(uv * 2.0 - 1.0);
    float radius = pow(pow(q.x, 2.5) + pow(q.y, 2.5), 1.0 / 2.5) / pow(2.0, 1.0 / 2.5);
    level = 1.0 - smoothstep(max(0.0, 1.0 - fade * 2.2), 1.0, radius);
  }
  float noise = fbm(vec3((center + uMotion.xy) / uField.x + SEED, uField.w));
  float tone = clamp((noise * 0.5 + 0.5 - uField.y) * uField.z + 0.5, 0.0, 1.0);
  int band = int(min(tone, 0.999999) * 3.0);
  float charge = texelFetch(tCharges, ivec2(cell), 0).r;
  int stepped = (band + int(clamp(charge, 0.0, 0.999) * 3.0)) % 3;
  int shape = 2 - stepped; float size = dotSize;
  if (mode != 0) { shape = mode - 1; size = dotSize * mix(0.45, 1.0, float(stepped) / 2.0); }
  float introProg = uPlacement.w; float front = 0.0;
  if (introProg < ${INTRO_END.toFixed(2)}) {
    float radial = length((center - res * 0.5) / (res * 0.5)) * 0.70710678;
    float warp = cnoise(vec3(cellUv * vec2(3.2, 2.4) + SEED, 4.7)) * ${INTRO_WARP.toFixed(2)};
    float jitter = h21(cell) * ${INTRO_JITTER.toFixed(2)};
    float spread = radial + warp + jitter + ${INTRO_WARP.toFixed(2)};
    float introBand = ${INTRO_BAND.toFixed(2)} * (0.6 + 0.8 * h21(cell + vec2(17.0, 9.0)));
    float t = clamp((introProg - spread) / introBand, 0.0, 1.0);
    if (t <= 0.0) { fragColor = empty; return; }
    float back = t - 1.0;
    size = max(size * (1.0 + 2.70158 * back * back * back + 1.70158 * back * back), 0.02);
    front = 1.0 - smoothstep(0.0, 1.0, abs(introProg - spread) / introBand);
  }
  float aa = 2.0 / cellPx;
  float coverage = 1.0 - smoothstep(-aa, aa, shapeDist(local, shape, size));
  vec3 hoverTint = bath(cellUv, uField.w * 0.6);
  vec3 activeColor = mix(hoverTint, uHover.rgb, 0.65);
  vec3 tint = mix(uColor.rgb, activeColor, max(smoothstep(0.08, 0.75, charge), front * 0.40));
  vec3 rgb = mix(bg, tint, coverage * level);
  if (toSurface) { fragColor = vec4(rgb, 1.0); return; }
  float lum = dot(tint * level, vec3(0.2126, 0.7152, 0.0722));
  float glow = max(0.0, (lum - GLOW_TH) / (1.0 - GLOW_TH)) * coverage;
  fragColor = vec4(rgb, glow);
}
`;

export const BLUR_FRAG = `#version 300 es
precision highp float;
uniform vec4 uDirection;
uniform sampler2D tSource;
in vec2 vUv;
out vec4 fragColor;
void main() {
  float sigma = uDirection.z;
  int radius = int(ceil(3.0 * sigma));
  vec3 sum = vec3(0.0); float weight = 0.0;
  for (int i = -radius; i <= radius; i++) {
    float offset = float(i);
    float w = exp(-(offset * offset) / (2.0 * sigma * sigma));
    vec4 s = textureLod(tSource, vUv + offset * uDirection.xy, 0.0);
    sum += (uDirection.w > 0.5 ? s.rgb * s.a : s.rgb) * w;
    weight += w;
  }
  fragColor = vec4(sum / weight, 1.0);
}
`;

export const COMPOSITE_FRAG = `#version 300 es
precision highp float;
uniform vec4 uStrength;
uniform sampler2D tScene, tGlow;
in vec2 vUv;
out vec4 fragColor;
void main() {
  vec3 scene = textureLod(tScene, vUv, 0.0).rgb;
  vec3 glow = textureLod(tGlow, vUv, 0.0).rgb;
  fragColor = vec4(scene + glow * uStrength.x, 1.0);
}
`;
