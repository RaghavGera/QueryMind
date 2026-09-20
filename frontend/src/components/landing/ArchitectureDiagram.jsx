import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowDown } from "lucide-react";
import { architectureSteps } from "../../data/mockData";
import { cn } from "../../lib/utils";

export default function ArchitectureDiagram({ compact = false }) {
  const [active, setActive] = useState(null);
  const steps = compact ? architectureSteps.slice(0, 6) : architectureSteps;

  return (
    <div className="mx-auto flex max-w-md flex-col items-center">
      {steps.map((step, i) => (
        <div key={step.key} className="flex w-full flex-col items-center">
          <motion.button
            onMouseEnter={() => setActive(step.key)}
            onMouseLeave={() => setActive(null)}
            onClick={() => setActive((a) => (a === step.key ? null : step.key))}
            whileHover={{ scale: 1.02 }}
            className={cn(
              "w-full rounded-xl border px-4 py-3 text-left transition-colors",
              active === step.key
                ? "border-accent-violet/50 bg-accent-violet/10 shadow-glow-sm"
                : "border-line bg-white/[0.02] hover:bg-white/[0.05]"
            )}
          >
            <div className="text-sm font-medium text-ink">{step.label}</div>
            {active === step.key && (
              <motion.p
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className="mt-1.5 text-xs leading-relaxed text-ink-dim"
              >
                {step.detail}
              </motion.p>
            )}
          </motion.button>
          {i < steps.length - 1 && <ArrowDown size={14} className="my-1.5 text-ink-faint" />}
        </div>
      ))}
    </div>
  );
}
