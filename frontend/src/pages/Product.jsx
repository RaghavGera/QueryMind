import { motion, useTransform } from "framer-motion";
import { ArrowRight, Check, Code2, LineChart, MessageSquare, ShieldQuestion } from "lucide-react";
import PinnedChapter, { useChapterProgress } from "../motion/PinnedChapter";
import ScrambleText from "../motion/ScrambleText";
import { useLaunch } from "../motion/warp";
import Magnetic from "../motion/Magnetic";

// Every claim and example here is something the product does today.
const FEATURES = [
  {
    icon: MessageSquare,
    title: "Ask in plain language",
    detail: "No SQL, no table names. Describe what you want to know the way you'd ask a colleague.",
    demo: (
      <div className="hud px-4 py-3 font-display text-lg text-ink">
        How many new customers signed up last month?
      </div>
    ),
  },
  {
    icon: ShieldQuestion,
    title: "Clarifies instead of guessing",
    detail: "When a question can mean two things, QueryMind asks one targeted question instead of answering the wrong one.",
    demo: (
      <div className="hud hud-amber px-4 py-3">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-accent-amber">I need one detail</p>
        <p className="mt-1.5 text-sm text-ink">What should count as &apos;expensive&apos;? Please give a specific threshold (for example a minimum or maximum value).</p>
      </div>
    ),
  },
  {
    icon: Code2,
    title: "Transparent SQL",
    detail: "Every answer comes with the exact, parameterized SQL that produced it: copy it, re-run it, save it.",
    demo: (
      <pre className="hud overflow-hidden px-4 py-3 font-mono text-[12px] leading-relaxed">
        <span className="text-accent-violet">SELECT</span> <span className="text-[#c9c2ff]">&quot;customers&quot;.&quot;country&quot;</span>,{"\n"}
        {"  "}<span className="text-accent-glow">SUM</span>(<span className="text-[#c9c2ff]">&quot;order_items&quot;.&quot;quantity&quot;</span> * …){"\n"}
        <span className="text-accent-violet">FROM</span> <span className="text-[#c9c2ff]">&quot;orders&quot;</span> …
      </pre>
    ),
  },
  {
    icon: LineChart,
    title: "Results that make sense",
    detail: "A table when you need detail, a chart when the shape fits. History and saved queries keep every answer one click away.",
    demo: (
      <div className="hud space-y-2 px-4 py-4">
        {[100, 94, 90, 89, 88].map((w, i) => (
          <div key={w} className="h-2.5 rounded-full bg-white/[0.05]">
            <div
              className={i === 0 ? "h-full rounded-full bg-gradient-to-r from-accent-violet to-accent-magenta" : "h-full rounded-full bg-accent-violet/50"}
              style={{ width: `${w}%` }}
            />
          </div>
        ))}
      </div>
    ),
  },
];

function Reel() {
  const progress = useChapterProgress();
  // Vertical scroll drives the horizontal track. Each panel rests centred for a
  // stretch of scroll before the next one slides in.
  const x = useTransform(
    progress,
    [0.06, 0.18, 0.3, 0.42, 0.54, 0.66, 0.78, 0.9],
    ["0%", "0%", "-25%", "-25%", "-50%", "-50%", "-75%", "-75%"],
  );
  const bar = useTransform(progress, [0.08, 0.92], [0, 1]);

  return (
    <div className="flex h-full flex-col justify-center pt-16">
      <div className="mx-auto mb-8 flex w-full max-w-7xl items-end justify-between px-6">
        <p className="hud-label">Four things it does</p>
        <div className="h-px w-40 bg-white/10">
          <motion.div style={{ scaleX: bar }} className="h-full origin-left bg-gradient-to-r from-accent-violet to-accent-cyan" />
        </div>
      </div>
      <div className="overflow-hidden">
        <motion.div style={{ x }} className="flex w-[400%]">
          {FEATURES.map((feature, i) => {
            const Icon = feature.icon;
            return (
              <article key={feature.title} className="w-1/4 shrink-0 px-6">
                <div className="mx-auto grid max-w-6xl items-center gap-10 lg:grid-cols-2">
                  <div>
                    <span className="font-mono text-[11px] tracking-[0.2em] text-ink-faint">0{i + 1} / 04</span>
                    <Icon size={26} className="mt-6 text-accent-cyan" />
                    <h2 className="display-lg mt-4 text-gradient">{feature.title}</h2>
                    <p className="mt-5 max-w-md text-lg leading-relaxed text-ink-dim">{feature.detail}</p>
                  </div>
                  <div className="mx-auto w-full max-w-md">{feature.demo}</div>
                </div>
              </article>
            );
          })}
        </motion.div>
      </div>
    </div>
  );
}

export default function Product() {
  const launch = useLaunch();
  return (
    <>
      <section className="relative mx-auto flex min-h-[80svh] max-w-5xl flex-col items-center justify-center px-6 pt-28 text-center">
        <p className="hud-label mb-6">Product</p>
        <ScrambleText as="h1" text="A database interface that thinks before it queries." trigger="mount" className="display-lg block" innerClassName="text-gradient" />
        <p className="mt-6 max-w-xl text-lg text-ink-dim">Scroll to walk through what it does, one capability at a time.</p>
      </section>

      <PinnedChapter id="reel" length={3.2}>
        <Reel />
      </PinnedChapter>

      <section className="mx-auto flex max-w-4xl flex-col items-center px-6 py-32 text-center">
        <ul className="mb-10 flex flex-wrap justify-center gap-3">
          {["PostgreSQL", "Gemini + Groq failover", "Reads your live schema", "Writes off by default"].map((tag) => (
            <li key={tag} className="chip flex items-center gap-1.5 !px-4 !py-1.5 font-mono !text-[11px] uppercase tracking-[0.16em]">
              <Check size={12} className="text-accent-cyan" /> {tag}
            </li>
          ))}
        </ul>
        <Magnetic>
          <button onClick={() => launch("/app")} className="btn-primary !px-8 !py-3.5 text-[15px]">
            Try it on the demo database <ArrowRight size={16} />
          </button>
        </Magnetic>
      </section>
    </>
  );
}
