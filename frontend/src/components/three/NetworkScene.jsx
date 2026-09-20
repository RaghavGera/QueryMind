import { useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import * as THREE from "three";

const NODES = [
  { id: "question", label: "User Query", pos: [-3.6, 1.2, 0] },
  { id: "understanding", label: "Semantic Understanding", pos: [-1.6, -0.6, 0.6] },
  { id: "clarification", label: "Clarification", pos: [0, 1.6, -0.4] },
  { id: "sql", label: "SQL Generation", pos: [1.8, -0.4, 0.4] },
  { id: "database", label: "Database", pos: [3.6, 1.1, -0.2] },
  { id: "result", label: "Result", pos: [3.8, -1.6, 0.3] },
];

const EDGES = [
  ["question", "understanding"],
  ["understanding", "clarification"],
  ["clarification", "sql"],
  ["understanding", "sql"],
  ["sql", "database"],
  ["database", "result"],
];

function Node({ node, hovered, onHover }) {
  const ref = useRef();
  useFrame((state) => {
    if (!ref.current) return;
    const t = state.clock.getElapsedTime();
    const scale = hovered ? 1.35 : 1 + Math.sin(t * 1.5 + node.pos[0]) * 0.05;
    ref.current.scale.setScalar(scale);
  });

  return (
    <group position={node.pos}>
      <mesh
        ref={ref}
        onPointerOver={(e) => {
          e.stopPropagation();
          onHover(node.id);
        }}
        onPointerOut={() => onHover(null)}
      >
        <icosahedronGeometry args={[0.16, 1]} />
        <meshStandardMaterial
          color={hovered ? "#a78bfa" : "#8b7bff"}
          emissive={"#6d28d9"}
          emissiveIntensity={hovered ? 1.1 : 0.5}
          roughness={0.3}
          metalness={0.4}
        />
      </mesh>
      {hovered && (
        <Html center distanceFactor={8} style={{ pointerEvents: "none" }}>
          <div className="whitespace-nowrap rounded-lg border border-line-strong bg-base-900/90 px-2.5 py-1 text-[11px] font-medium text-ink shadow-glow-sm">
            {node.label}
          </div>
        </Html>
      )}
    </group>
  );
}

function Edge({ from, to }) {
  const points = useMemo(() => {
    const a = new THREE.Vector3(...from.pos);
    const b = new THREE.Vector3(...to.pos);
    const mid = a.clone().lerp(b, 0.5).add(new THREE.Vector3(0, 0, 0.4));
    const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
    return curve.getPoints(24);
  }, [from, to]);

  const geometry = useMemo(() => new THREE.BufferGeometry().setFromPoints(points), [points]);

  const particleRef = useRef();
  const offset = useMemo(() => Math.random(), []);

  useFrame((state) => {
    if (!particleRef.current) return;
    const t = (state.clock.getElapsedTime() * 0.18 + offset) % 1;
    const idx = Math.min(points.length - 1, Math.floor(t * points.length));
    particleRef.current.position.copy(points[idx]);
  });

  return (
    <group>
      <line geometry={geometry}>
        <lineBasicMaterial color="#3d3d5c" transparent opacity={0.5} />
      </line>
      <mesh ref={particleRef}>
        <sphereGeometry args={[0.035, 8, 8]} />
        <meshBasicMaterial color="#5eead4" />
      </mesh>
    </group>
  );
}

function Rig({ reducedMotion }) {
  const { camera, mouse } = useThree();
  useFrame(() => {
    if (reducedMotion) return;
    camera.position.x += (mouse.x * 0.6 - camera.position.x) * 0.02;
    camera.position.y += (mouse.y * 0.4 - camera.position.y) * 0.02;
    camera.lookAt(0, 0, 0);
  });
  return null;
}

export default function NetworkScene({ reducedMotion = false }) {
  const [hovered, setHovered] = useState(null);
  const nodeMap = useMemo(() => Object.fromEntries(NODES.map((n) => [n.id, n])), []);

  return (
    <Canvas
      camera={{ position: [0, 0, 7], fov: 42 }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, alpha: true }}
      frameloop={reducedMotion ? "demand" : "always"}
    >
      <ambientLight intensity={0.5} />
      <pointLight position={[4, 4, 4]} intensity={40} color="#a78bfa" />
      <pointLight position={[-4, -2, 3]} intensity={25} color="#5eead4" />

      {EDGES.map(([a, b], i) => (
        <Edge key={i} from={nodeMap[a]} to={nodeMap[b]} />
      ))}
      {NODES.map((node) => (
        <Node key={node.id} node={node} hovered={hovered === node.id} onHover={setHovered} />
      ))}

      <Rig reducedMotion={reducedMotion} />
    </Canvas>
  );
}
