import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "../lib/utils";

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";
const GIS_SRC = "https://accounts.google.com/gsi/client";

let loading = null;

/** Load Google Identity Services once; resolves to google.accounts.oauth2. */
function loadGoogleOAuth() {
  if (window.google?.accounts?.oauth2) return Promise.resolve(window.google.accounts.oauth2);
  if (!loading) {
    loading = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = GIS_SRC;
      script.async = true;
      script.onload = () =>
        window.google?.accounts?.oauth2 ? resolve(window.google.accounts.oauth2) : reject(new Error("Google sign-in did not load."));
      script.onerror = () => {
        loading = null;
        reject(new Error("Could not load Google sign-in. Check your connection or ad blocker."));
      };
      document.head.appendChild(script);
    });
  }
  return loading;
}

/** Google's "G", unaltered, as its brand guidelines require. */
function GoogleG({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  );
}

/**
 * "Continue with Google" in the site's own style. It opens Google's popup;
 * ``onToken`` receives the access token, which the API checks with Google
 * (issued to this app, verified email). Google never gives us a password.
 */
export default function GoogleSignInButton({ onToken, onError, busy = false, className }) {
  const client = useRef(null);
  const handlers = useRef({ onToken, onError });
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(null);

  useEffect(() => {
    handlers.current = { onToken, onError };
  });

  useEffect(() => {
    if (!CLIENT_ID) return undefined;
    let cancelled = false;
    loadGoogleOAuth()
      .then((oauth2) => {
        if (cancelled) return;
        client.current = oauth2.initTokenClient({
          client_id: CLIENT_ID,
          scope: "openid email profile",
          prompt: "select_account",
          callback: (response) => {
            if (response.error) handlers.current.onError?.(new Error("Google sign-in was not completed."));
            else handlers.current.onToken(response.access_token);
          },
          // Closing the popup is a choice, not an error worth shouting about.
          error_callback: (error) => {
            if (error?.type !== "popup_closed") handlers.current.onError?.(new Error("Google sign-in could not open. Allow pop-ups for this site and try again."));
          },
        });
        setReady(true);
      })
      .catch((error) => {
        if (cancelled) return;
        setFailed(error.message);
        handlers.current.onError?.(error);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!CLIENT_ID) {
    return <p className="text-sm text-state-danger">Sign-in isn&apos;t configured: set VITE_GOOGLE_CLIENT_ID for the frontend.</p>;
  }
  return (
    <div className="flex w-full flex-col items-center gap-2">
      <button
        type="button"
        // The popup must open inside the click itself, or browsers block it.
        onClick={() => client.current?.requestAccessToken()}
        disabled={!ready || busy}
        className={cn(
          "btn-secondary w-full max-w-xs gap-3 py-3 hover:border-accent-violet/50 hover:shadow-glow-sm disabled:pointer-events-none disabled:opacity-60",
          className,
        )}
      >
        {busy ? <Loader2 size={18} className="animate-spin" /> : <GoogleG />}
        {busy ? "Signing you in…" : "Continue with Google"}
      </button>
      {failed && <p className="text-sm text-state-danger">{failed}</p>}
    </div>
  );
}
