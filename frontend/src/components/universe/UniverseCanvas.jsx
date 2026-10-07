import { Canvas, useFrame } from "@react-three/fiber";
import Starfield from "./Starfield";
import Nebula from "./Nebula";
import SchemaConstellation from "./SchemaConstellation";

function CameraRig({ reducedMotion }) {
  useFrame((state) => {
    if (reducedMotion) return;
    const { camera, pointer } = state;
    camera.position.x += (pointer.x * 0.55 - camera.position.x) * 0.03;
    camera.position.y += (pointer.y * 0.3 - camera.position.y) * 0.03;
    camera.lookAt(0, 0, -20);
  });
  return null;
}

/**
 * The landing page's fixed, full-screen 3D backdrop. Purely decorative
 * (aria-hidden, no pointer events); every word on the page lives in the DOM.
 */
export default function UniverseCanvas({ reducedMotion = false }) {
  const small = typeof window !== "undefined" && window.innerWidth < 768;
  return (
    <div className="pointer-events-none fixed inset-0 z-0" aria-hidden="true">
      <Canvas
        dpr={[1, 1.5]}
        gl={{ antialias: false, alpha: true, powerPreference: "high-performance" }}
        camera={{ position: [0, 0, 0.01], fov: 62, near: 0.05, far: 200 }}
        frameloop={reducedMotion ? "demand" : "always"}
      >
        <Nebula />
        <Starfield count={small ? 3500 : 9000} reducedMotion={reducedMotion} />
        {!reducedMotion && <SchemaConstellation />}
        <CameraRig reducedMotion={reducedMotion} />
      </Canvas>
    </div>
  );
}
