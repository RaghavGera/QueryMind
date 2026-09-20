import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import Button from "../ui/Button";
import { StatusDot } from "../ui/Surfaces";
import HeroCanvas from "../three/HeroCanvas";

export default function Hero() {
  return (
    <section className="relative overflow-hidden pt-40 pb-28">
      <div className="absolute inset-0 bg-radial-glow" />
      <HeroCanvas className="pointer-events-none absolute inset-0 opacity-90 md:opacity-100" />

      <div className="relative mx-auto max-w-4xl px-6 text-center">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 inline-flex items-center gap-2 chip"
        >
          <StatusDot tone="success" pulse />
          Query engine operational
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="font-display text-4xl font-semibold leading-[1.1] tracking-tight text-gradient sm:text-6xl"
        >
          Ask your database.
          <br />
          QueryMind understands.
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mx-auto mt-5 max-w-xl text-balance text-base text-ink-dim sm:text-lg"
        >
          Turn natural language into reliable database answers. QueryMind detects
          ambiguity, resolves intent, generates SQL, validates the query, and
          returns the result.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row"
        >
          <Button as={Link} to="/app" variant="primary" className="!px-6 !py-3 text-sm">
            Try QueryMind
          </Button>
          <Button as={Link} to="/architecture" variant="secondary" className="!px-6 !py-3 text-sm">
            View architecture
          </Button>
        </motion.div>
      </div>
    </section>
  );
}
