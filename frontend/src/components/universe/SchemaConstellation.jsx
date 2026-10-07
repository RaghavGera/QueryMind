import { useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Html, Line } from "@react-three/drei";
import * as THREE from "three";
import { glowTexture } from "./glowTexture";
import { universe } from "./universeState";

// The demo database's real schema: 4 tables, 3 foreign keys. "used" = the
// tables the showcase question ("Which region generated the most revenue?")
// actually joins.
const TABLES = [
  { name: "customers", pos: [-1.7, 1.05, 0.3], used: true },
  { name: "orders", pos: [0.15, 0.2, 0.8], used: true },
  { name: "order_items", pos: [-0.35, -1.4, 0], used: true },
  { name: "products", pos: [2.0, -0.7, -0.6], used: false },
];
const LINKS = [
  ["orders", "customers", true],
  ["order_items", "orders", true],
  ["order_items", "products", false],
];

const VIOLET = new THREE.Color("#8b7bff");
const CYAN = new THREE.Color("#5eead4");
const DIM = new THREE.Color("#4b4b70");

function curveBetween(a, b, lift = 0.5) {
  const va = new THREE.Vector3(...a);
  const vb = new THREE.Vector3(...b);
  const mid = va.clone().lerp(vb, 0.5).add(new THREE.Vector3(0, 0, lift));
  return new THREE.QuadraticBezierCurve3(va, mid, vb);
}

function polylineLength(points) {
  let length = 0;
  for (let i = 1; i < points.length; i += 1) length += points[i].distanceTo(points[i - 1]);
  return length;
}

export default function SchemaConstellation() {
  const size = useThree((s) => s.size);
  const portrait = size.width / size.height < 0.9;
  const layout = portrait ? { pos: [0, -2.3, -9.5], scale: 0.6 } : { pos: [3.1, 0.1, -7.5], scale: 1 };

  const texture = useMemo(() => glowTexture(128), []);
  const byName = useMemo(() => Object.fromEntries(TABLES.map((t) => [t.name, t])), []);
  const edges = useMemo(
    () =>
      LINKS.map(([from, to, used]) => {
        const curve = curveBetween(byName[from].pos, byName[to].pos);
        return { from, to, used, curve, points: curve.getPoints(32) };
      }),
    [byName],
  );
  const beam = useMemo(() => {
    const curve = new THREE.QuadraticBezierCurve3(
      // Rises from below the screen, between the copy and the constellation.
      new THREE.Vector3(-0.6, -7.5, 1.6),
      new THREE.Vector3(1.3, -2.4, 2.2),
      new THREE.Vector3(...byName.orders.pos),
    );
    const points = curve.getPoints(64);
    return { curve, points, length: polylineLength(points) };
  }, [byName]);

  const group = useRef();
  const glows = useRef([]);
  const cores = useRef([]);
  const labels = useRef([]);
  const lines = useRef([]);
  const pulses = useRef([]);
  const beamLine = useRef();
  const beamHead = useRef();
  const level = useRef({ c: 0, h: 0, b: 0 });
  const tmp = useMemo(() => new THREE.Color(), []);

  useFrame((state, delta) => {
    const L = level.current;
    const k = Math.min(1, delta * 4);
    L.c += (universe.constellation - L.c) * k;
    L.h += (universe.highlight - L.h) * k;
    L.b += (universe.beam - L.b) * k;
    const t = state.clock.elapsedTime;
    const g = group.current;
    if (!g) return;

    g.visible = L.c > 0.005;
    if (!g.visible) {
      // drei <Html> labels are DOM and ignore the group's visibility.
      labels.current.forEach((label) => label && (label.style.opacity = "0"));
      return;
    }
    g.position.set(...layout.pos);
    g.scale.setScalar(layout.scale * (0.78 + 0.22 * L.c));
    g.rotation.y = -0.2 + Math.sin(t * 0.12) * 0.22 + state.pointer.x * 0.12;
    g.rotation.x = state.pointer.y * -0.08;

    TABLES.forEach((table, i) => {
      const lit = table.used ? L.h : 0;
      tmp.copy(table.used ? VIOLET : DIM).lerp(CYAN, lit);
      const glow = glows.current[i];
      if (glow) {
        glow.material.color.copy(tmp);
        glow.material.opacity = L.c * (0.35 + 0.65 * (table.used ? 0.4 + 0.6 * lit : 0.2));
        glow.scale.setScalar(1.15 + 0.12 * Math.sin(t * 1.4 + i) + lit * 0.35);
      }
      const core = cores.current[i];
      if (core) {
        core.material.color.copy(tmp);
        core.material.opacity = L.c;
      }
      const label = labels.current[i];
      if (label) {
        label.style.opacity = String(L.c * (table.used ? 0.55 + 0.45 * lit : 0.45));
        label.style.color = lit > 0.5 ? "#5eead4" : "#a3a3b3";
      }
    });

    edges.forEach((edge, i) => {
      const lit = edge.used ? L.h : 0;
      const line = lines.current[i];
      if (line) {
        line.material.opacity = L.c * (0.22 + 0.55 * lit);
        line.material.color.copy(VIOLET).lerp(CYAN, lit);
      }
      const pulse = pulses.current[i];
      if (pulse) {
        pulse.position.copy(edge.curve.getPoint((t * 0.32 + i * 0.37) % 1));
        pulse.material.opacity = L.c * (0.25 + 0.75 * lit);
      }
    });

    if (beamLine.current) {
      beamLine.current.material.dashOffset = beam.length * (1 - L.b);
      beamLine.current.material.opacity = Math.min(1, L.b * 1.4) * L.c;
    }
    if (beamHead.current) {
      beamHead.current.position.copy(beam.curve.getPoint(Math.min(1, L.b)));
      beamHead.current.material.opacity = L.c * Math.min(1, L.b * 8);
    }
  });

  return (
    <group ref={group} visible={false}>
      {edges.map((edge, i) => (
        <group key={`${edge.from}-${edge.to}`}>
          <Line
            ref={(el) => (lines.current[i] = el)}
            points={edge.points}
            color="#8b7bff"
            lineWidth={1.4}
            transparent
            opacity={0}
            depthWrite={false}
          />
          <sprite ref={(el) => (pulses.current[i] = el)} scale={0.22}>
            <spriteMaterial map={texture} color="#5eead4" transparent opacity={0} depthWrite={false} blending={THREE.AdditiveBlending} />
          </sprite>
        </group>
      ))}

      <Line
        ref={beamLine}
        points={beam.points}
        color="#5eead4"
        lineWidth={2.2}
        dashed
        dashSize={beam.length}
        gapSize={beam.length}
        dashOffset={beam.length}
        transparent
        opacity={0}
        depthWrite={false}
      />
      <sprite ref={beamHead} scale={0.7}>
        <spriteMaterial map={texture} color="#c9fff4" transparent opacity={0} depthWrite={false} blending={THREE.AdditiveBlending} />
      </sprite>

      {TABLES.map((table, i) => (
        <group key={table.name} position={table.pos}>
          <sprite ref={(el) => (glows.current[i] = el)} scale={1.2}>
            <spriteMaterial map={texture} color="#8b7bff" transparent opacity={0} depthWrite={false} blending={THREE.AdditiveBlending} />
          </sprite>
          <mesh ref={(el) => (cores.current[i] = el)}>
            <sphereGeometry args={[0.075, 16, 16]} />
            <meshBasicMaterial color="#8b7bff" transparent opacity={0} />
          </mesh>
          <Html position={[0, -0.34, 0]} center style={{ pointerEvents: "none" }}>
            <div
              ref={(el) => (labels.current[i] = el)}
              className="whitespace-nowrap font-mono text-[11px] uppercase tracking-[0.18em]"
              style={{ opacity: 0 }}
            >
              {table.name}
            </div>
          </Html>
        </group>
      ))}
    </group>
  );
}
