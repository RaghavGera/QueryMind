import { Link } from "react-router-dom";
import Navbar from "../components/navigation/Navbar";
import Hero from "../components/landing/Hero";
import InteractiveDemo from "../components/landing/InteractiveDemo";
import TrustSection from "../components/landing/TrustSection";
import ArchitectureDiagram from "../components/landing/ArchitectureDiagram";
import Footer from "../components/landing/Footer";
import Button from "../components/ui/Button";

export default function Landing() {
  return (
    <div className="min-h-screen">
      <Navbar />
      <Hero />
      <InteractiveDemo />

      <section className="mx-auto max-w-4xl px-6 py-24">
        <div className="mb-10 text-center">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-accent-glow">How it works</p>
          <h2 className="font-display text-3xl font-semibold text-ink">Every query passes the same pipeline</h2>
        </div>
        <ArchitectureDiagram compact />
        <div className="mt-8 flex justify-center">
          <Button as={Link} to="/architecture" variant="secondary">
            View full architecture
          </Button>
        </div>
      </section>

      <TrustSection />
      <Footer />
    </div>
  );
}
