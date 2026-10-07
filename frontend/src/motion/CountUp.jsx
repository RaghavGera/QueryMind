import { motion, useTransform } from "framer-motion";
import { easeOutCubic, formatInt } from "./math";

/** A number that counts up to ``to`` as ``progress`` (motion value) goes 0 → 1. */
export default function CountUp({ progress, to, format = formatInt, className }) {
  const value = useTransform(progress, (p) => format(to * easeOutCubic(Math.min(1, Math.max(0, p)))));
  return <motion.span className={className}>{value}</motion.span>;
}
