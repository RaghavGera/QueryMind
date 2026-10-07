import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { glowTexture } from "./glowTexture";
import { universe } from "./universeState";

// Big, far-away glows. Violet and cyan are always there; amber and magenta
// swell during the ambiguity and answer chapters.
const CLOUDS = [
  { color: "#6d5bff", pos: [-26, 14, -70], scale: 70, base: 0.42 },
  { color: "#2dd4bf", pos: [30, -16, -75], scale: 64, base: 0.26 },
  { color: "#8b7bff", pos: [6, 22, -85], scale: 52, base: 0.2 },
  { color: "#fbbf24", pos: [0, -4, -60], scale: 58, base: 0, signal: "amber" },
  { color: "#f472b6", pos: [14, 4, -65], scale: 60, base: 0, signal: "magenta" },
];

export default function Nebula() {
  const texture = useMemo(() => glowTexture(256), []);
  const refs = useRef([]);
  const levels = useRef(CLOUDS.map((c) => c.base));

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    CLOUDS.forEach((cloud, i) => {
      const sprite = refs.current[i];
      if (!sprite) return;
      const target = cloud.signal ? universe[cloud.signal] * 0.38 : cloud.base;
      levels.current[i] += (target - levels.current[i]) * Math.min(1, delta * 2.5);
      sprite.material.opacity = levels.current[i] * (0.9 + 0.1 * Math.sin(t * 0.4 + i));
      sprite.position.x = cloud.pos[0] + Math.sin(t * 0.05 + i) * 3;
      sprite.position.y = cloud.pos[1] + Math.cos(t * 0.04 + i) * 2;
    });
  });

  return CLOUDS.map((cloud, i) => (
    <sprite key={cloud.color + i} ref={(el) => (refs.current[i] = el)} position={cloud.pos} scale={cloud.scale}>
      <spriteMaterial
        map={texture}
        color={new THREE.Color(cloud.color)}
        transparent
        opacity={cloud.base}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </sprite>
  ));
}
