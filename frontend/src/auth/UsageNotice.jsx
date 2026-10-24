import { Link, useLocation } from "react-router-dom";
import { LogIn } from "lucide-react";
import { remaining } from "../services/session.js";

function signInPath(location) {
  return `/signin?next=${encodeURIComponent(location.pathname === "/" ? "/app" : location.pathname + location.search)}`;
}

/** "2 free questions left today · sign in for 20 a day" (or the signed-in count). */
export function TriesLeft({ usage, signedIn }) {
  const location = useLocation();
  const left = remaining(usage);
  if (left === null) return null;
  return (
    // Each half stays on one line, so a narrow screen breaks between them, not mid-phrase.
    <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-faint">
      <span className="whitespace-nowrap">
        {signedIn ? `${left} of ${usage.limit} questions left today` : `${left} free question${left === 1 ? "" : "s"} left today · `}
      </span>{" "}
      {!signedIn && (
        <Link to={signInPath(location)} className="whitespace-nowrap text-accent-cyan hover:underline">
          sign in for {usage.user_limit ?? 20} a day
        </Link>
      )}
    </p>
  );
}

/** Shown once today's questions are used up. */
export function OutOfQuestions({ signedIn, pendingClarification = false }) {
  const location = useLocation();
  let message = "That's all the free questions for today. Sign in with Google to keep going.";
  if (signedIn) message = "You've used today's questions. They reset at 00:00 UTC.";
  else if (pendingClarification)
    message = "Answering this follow-up needs one more question, and the free ones are used up. Sign in with Google to keep going.";
  return (
    <div className="hud hud-amber flex flex-col items-start gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-ink">{message}</p>
      {!signedIn && (
        <Link to={signInPath(location)} className="btn-primary shrink-0">
          <LogIn size={15} /> Sign in with Google
        </Link>
      )}
    </div>
  );
}
