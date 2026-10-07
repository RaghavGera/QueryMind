import { Suspense, useLayoutEffect } from "react";
import { useLocation, useOutlet } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { SmoothScroll, useScrollTo } from "../../motion/SmoothScroll";
import Navbar from "../navigation/Navbar";
import Footer from "../landing/Footer";
import BootScreen from "../ui/BootScreen";

function ScrollToTopOnEnter() {
  const scrollTo = useScrollTo();
  useLayoutEffect(() => {
    scrollTo(0, { immediate: true });
  }, [scrollTo]);
  return null;
}

/**
 * Shell for the public pages: smooth scrolling, the cinematic overlays and
 * a full-screen light-sweep between pages. Only opacity is animated on the
 * page wrapper: transforms/filters there would break the fixed 3D canvas and
 * the sticky scenes inside it.
 */
export default function MarketingLayout() {
  const location = useLocation();
  const outlet = useOutlet();

  return (
    <SmoothScroll>
      <div className="fx-nebula z-0" aria-hidden="true" />
      <Navbar />

      <AnimatePresence mode="wait">
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
          className="relative z-10"
        >
          <ScrollToTopOnEnter />
          {/* Light sweep across the screen as a page arrives. */}
          <motion.div
            className="pointer-events-none fixed inset-y-0 left-0 z-[70] w-[45vw] bg-gradient-to-r from-transparent via-accent-violet/25 to-transparent blur-2xl"
            initial={{ x: "-50vw" }}
            animate={{ x: "160vw" }}
            transition={{ duration: 0.9, ease: [0.65, 0, 0.35, 1] }}
            aria-hidden="true"
          />
          <Suspense fallback={<BootScreen />}>{outlet}</Suspense>
          <Footer />
        </motion.div>
      </AnimatePresence>

      <div className="fx-vignette z-[60]" aria-hidden="true" />
      <div className="fx-scanlines z-[61]" aria-hidden="true" />
      <div className="fx-grain z-[62]" aria-hidden="true" />
    </SmoothScroll>
  );
}
