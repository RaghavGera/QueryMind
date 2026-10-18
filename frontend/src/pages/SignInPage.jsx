import { useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import GoogleSignInButton from "../auth/GoogleSignInButton";
import ScrambleText from "../motion/ScrambleText";
import { LogoMark } from "../components/ui/Logo";

/** Only same-site paths are allowed as the post-sign-in destination. */
function safeNext(raw) {
  return raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/app";
}

export default function SignInPage() {
  const { status, signIn } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const next = safeNext(params.get("next"));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  if (status === "signedIn") return <Navigate to={next} replace />;

  const onToken = async (accessToken) => {
    setBusy(true);
    setError(null);
    try {
      await signIn({ accessToken });
      navigate(next, { replace: true });
    } catch (e) {
      setError(e.message || "Sign-in failed. Please try again.");
      setBusy(false);
    }
  };

  return (
    <section className="flex min-h-svh items-center justify-center px-6 pt-20">
      <div className="hud w-full max-w-md px-8 py-10 text-center">
        <LogoMark size={40} className="mx-auto" />
        <p className="hud-label mt-6">Sign in</p>
        <ScrambleText as="h1" text="Welcome to QueryMind." trigger="mount" duration={800} className="display-md mt-3 block" innerClassName="text-gradient" />
        <p className="mx-auto mt-4 max-w-sm text-sm leading-relaxed text-ink-dim">
          Without an account you get 3 free questions a day. Sign in with Google for 20.
        </p>
        <div className="mt-8 flex min-h-[52px] items-center justify-center">
          <GoogleSignInButton onToken={onToken} onError={(e) => setError(e.message)} busy={busy} />
        </div>
        {error && <p className="mt-4 text-sm text-state-danger">{error}</p>}
        <p className="mt-8 text-xs leading-relaxed text-ink-faint">
          We receive your name, email address and profile picture from Google, nothing else. See the{" "}
          <Link to="/privacy" className="text-ink-dim underline-offset-2 hover:text-ink hover:underline">
            privacy page
          </Link>
          .
        </p>
      </div>
    </section>
  );
}
