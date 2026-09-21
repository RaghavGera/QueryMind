import Navbar from "../components/navigation/Navbar";
import Footer from "../components/landing/Footer";
import ArchitectureDiagram from "../components/landing/ArchitectureDiagram";

export default function Architecture() {
  return (
    <div className="min-h-screen">
      <Navbar />
      <section className="mx-auto max-w-4xl px-4 sm:px-6 pb-20 pt-36 text-center">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-accent-glow">Architecture</p>
        <h1 className="font-display text-4xl font-semibold text-ink">From question to answer</h1>
        <p className="mx-auto mt-3 max-w-xl text-ink-dim">
          Ten stages, each with one job. Hover or tap any stage to see what it does.
        </p>
      </section>
      <section className="px-4 sm:px-6 pb-28">
        <ArchitectureDiagram />
      </section>
      <Footer />
    </div>
  );
}
