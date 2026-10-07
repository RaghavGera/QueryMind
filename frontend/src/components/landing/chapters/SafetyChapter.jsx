import { motion, useTransform } from "framer-motion";
import { Ban, Braces, FilePenLine, KeyRound, MessageCircleQuestion, ShieldCheck } from "lucide-react";
import PinnedChapter, { useChapterProgress } from "../../../motion/PinnedChapter";
import { ChapterHeading } from "./shared";

// Each of these is enforced by the backend today. (Read-only transactions
// and an audit log are planned; they are not claimed here until they ship.)
const POINTS = [
  { icon: ShieldCheck, title: "Schema-checked", detail: "SQL is built only from tables and columns that exist in your database." },
  { icon: Braces, title: "Parameterized", detail: "Values travel as parameters, never pasted into the query text." },
  { icon: MessageCircleQuestion, title: "Asks before guessing", detail: "Vague words like “top” or “expensive” trigger a question, not a guess." },
  { icon: FilePenLine, title: "Writes are opt-in", detail: "Inserts and updates are off by default, previewed, and run only after you confirm." },
  { icon: Ban, title: "No blind writes", detail: "An update without a WHERE clause is blocked. DELETE is refused." },
  { icon: KeyRound, title: "Credentials stay server-side", detail: "Database credentials never reach the browser." },
];

function Tile({ point, index }) {
  const progress = useChapterProgress();
  const at = 0.14 + index * 0.08;
  const lit = useTransform(progress, [at, at + 0.06], [0, 1], { clamp: true });
  const opacity = useTransform(lit, [0, 1], [0.25, 1]);
  const y = useTransform(lit, [0, 1], [16, 0]);
  const glow = useTransform(lit, (v) => `0 0 ${50 * v}px -20px rgba(94,234,212,${0.55 * v})`);
  const Icon = point.icon;

  return (
    <motion.div style={{ opacity, y, boxShadow: glow }} className="hud p-3.5 sm:p-6">
      <Icon size={20} className="mb-2 text-accent-cyan sm:mb-4" />
      <h3 className="font-display text-sm font-medium text-ink sm:text-lg">{point.title}</h3>
      <p className="mt-1 text-[11px] leading-snug text-ink-dim sm:mt-1.5 sm:text-sm sm:leading-relaxed">{point.detail}</p>
    </motion.div>
  );
}

function Safety() {
  const progress = useChapterProgress();
  const scan = useTransform(progress, [0.1, 0.7], ["-10%", "110%"]);

  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col justify-center px-4 pt-16 sm:px-6">
      <ChapterHeading index="06" label="Safety" title="Built to touch a real database." className="mb-6 sm:mb-10" />
      <div className="relative">
        <motion.div
          style={{ top: scan }}
          className="pointer-events-none absolute inset-x-0 z-10 h-px bg-gradient-to-r from-transparent via-accent-cyan to-transparent shadow-[0_0_24px_rgba(94,234,212,0.8)]"
          aria-hidden="true"
        />
        <div className="grid grid-cols-2 gap-2.5 sm:gap-4 lg:grid-cols-3">
          {POINTS.map((point, i) => (
            <Tile key={point.title} point={point} index={i} />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function SafetyChapter() {
  return (
    <PinnedChapter id="safety" length={2}>
      <Safety />
    </PinnedChapter>
  );
}
