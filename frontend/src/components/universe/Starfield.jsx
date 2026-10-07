import { useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { universe } from "./universeState";

const DEPTH = 90;

const vertex = /* glsl */ `
  uniform float uTime;
  uniform float uTravel;
  uniform float uDepth;
  uniform float uPixelRatio;
  uniform float uWarp;
  uniform float uStreak;
  attribute float aScale;
  attribute float aPhase;
  attribute float aTail;
  attribute vec3 aColor;
  varying vec3 vColor;
  varying float vAlpha;

  void main() {
    vec3 p = position;
    // Fly-through: stars move towards the camera and wrap around.
    p.z = mod(p.z + uTravel, uDepth) - uDepth;
    // Warp streaks: the tail vertex trails behind the head.
    p.z -= aTail * uStreak;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;

    float fadeFar = smoothstep(-uDepth, -uDepth + 14.0, p.z);
    float fadeNear = 1.0 - smoothstep(-3.0, -0.6, p.z);
    float twinkle = 0.72 + 0.28 * sin(uTime * 1.6 + aPhase);
    vAlpha = fadeFar * fadeNear * twinkle;
    vColor = aColor;
    gl_PointSize = aScale * uPixelRatio * (34.0 / -mv.z) * (1.0 + uWarp);
  }
`;

const pointsFragment = /* glsl */ `
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    float a = pow(smoothstep(0.5, 0.0, d), 1.7);
    gl_FragColor = vec4(vColor, a * vAlpha);
  }
`;

const streakFragment = /* glsl */ `
  uniform float uWarp;
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
    gl_FragColor = vec4(mix(vColor, vec3(1.0), 0.35), vAlpha * uWarp);
  }
`;

function buildStars(count) {
  const palette = ["#8b7bff", "#a78bfa", "#5eead4", "#c9c2ff", "#ffffff"].map((c) => new THREE.Color(c));
  const weights = [0.28, 0.18, 0.22, 0.17, 0.15];
  const pick = () => {
    let r = Math.random();
    for (let i = 0; i < weights.length; i += 1) {
      r -= weights[i];
      if (r <= 0) return palette[i];
    }
    return palette[0];
  };

  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const scales = new Float32Array(count);
  const phases = new Float32Array(count);
  for (let i = 0; i < count; i += 1) {
    // A tunnel around the view axis: few stars right in the middle, where text sits.
    const radius = 1.4 + Math.pow(Math.random(), 0.7) * 30;
    const angle = Math.random() * Math.PI * 2;
    positions[i * 3] = Math.cos(angle) * radius;
    positions[i * 3 + 1] = Math.sin(angle) * radius * 0.62;
    positions[i * 3 + 2] = -Math.random() * DEPTH;
    pick().toArray(colors, i * 3);
    scales[i] = 0.35 + Math.pow(Math.random(), 3) * 2.4;
    phases[i] = Math.random() * Math.PI * 2;
  }
  return { positions, colors, scales, phases };
}

/** Doubles every star into a head/tail pair for the warp streaks. */
function buildStreaks({ positions, colors, scales, phases }) {
  const count = scales.length;
  const pos = new Float32Array(count * 6);
  const col = new Float32Array(count * 6);
  const scl = new Float32Array(count * 2);
  const phs = new Float32Array(count * 2);
  const tail = new Float32Array(count * 2);
  for (let i = 0; i < count; i += 1) {
    for (let k = 0; k < 2; k += 1) {
      const v = i * 2 + k;
      pos.set(positions.subarray(i * 3, i * 3 + 3), v * 3);
      col.set(colors.subarray(i * 3, i * 3 + 3), v * 3);
      scl[v] = scales[i];
      phs[v] = phases[i];
      tail[v] = k;
    }
  }
  return { pos, col, scl, phs, tail };
}

export default function Starfield({ count = 9000, reducedMotion = false }) {
  const gl = useThree((s) => s.gl);
  const data = useMemo(() => buildStars(count), [count]);
  const streaks = useMemo(() => buildStreaks(data), [data]);
  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uTravel: { value: 0 },
      uDepth: { value: DEPTH },
      uPixelRatio: { value: Math.min(gl.getPixelRatio(), 1.5) },
      uWarp: { value: 0 },
      uStreak: { value: 0 },
    }),
    [gl],
  );
  const motion = useRef({ scroll: 0, drift: 0, warp: 0 });

  useFrame((state, delta) => {
    const m = motion.current;
    const dt = Math.min(delta, 0.05);
    const targetWarp = Math.max(universe.warp, universe.warpBoost);
    m.warp += (targetWarp - m.warp) * Math.min(1, dt * (universe.warpBoost ? 3 : 5));
    m.scroll += (universe.travel - m.scroll) * Math.min(1, dt * 4);
    if (!reducedMotion) m.drift += dt * (1.1 + m.warp * 70);
    uniforms.uTime.value = state.clock.elapsedTime;
    uniforms.uTravel.value = m.scroll * 170 + m.drift;
    uniforms.uWarp.value = m.warp;
    uniforms.uStreak.value = 0.02 + m.warp * 16;
  });

  return (
    <group>
      <points frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[data.positions, 3]} />
          <bufferAttribute attach="attributes-aColor" args={[data.colors, 3]} />
          <bufferAttribute attach="attributes-aScale" args={[data.scales, 1]} />
          <bufferAttribute attach="attributes-aPhase" args={[data.phases, 1]} />
          <bufferAttribute attach="attributes-aTail" args={[new Float32Array(count), 1]} />
        </bufferGeometry>
        <shaderMaterial
          vertexShader={vertex}
          fragmentShader={pointsFragment}
          uniforms={uniforms}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>
      <lineSegments frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[streaks.pos, 3]} />
          <bufferAttribute attach="attributes-aColor" args={[streaks.col, 3]} />
          <bufferAttribute attach="attributes-aScale" args={[streaks.scl, 1]} />
          <bufferAttribute attach="attributes-aPhase" args={[streaks.phs, 1]} />
          <bufferAttribute attach="attributes-aTail" args={[streaks.tail, 1]} />
        </bufferGeometry>
        <shaderMaterial
          vertexShader={vertex}
          fragmentShader={streakFragment}
          uniforms={uniforms}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </lineSegments>
    </group>
  );
}
