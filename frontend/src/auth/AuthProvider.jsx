import { createContext, useContext, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { fetchMe, signInWithGoogle, signOut } from "../services/queryApi";
import { getSession, getUsage, subscribeSession, subscribeUsage } from "../services/session.js";

const AuthContext = createContext(null);

/**
 * Who is signed in. ``status`` is "checking" while a stored session is being
 * confirmed with the API, then "signedIn" or "signedOut".
 */
export function AuthProvider({ children }) {
  const session = useSyncExternalStore(subscribeSession, getSession, () => null);
  const [checked, setChecked] = useState(() => !getSession());

  useEffect(() => {
    if (!getSession()) return undefined;
    let active = true;
    fetchMe()
      .catch(() => {}) // a 401 clears the session inside request()
      .finally(() => active && setChecked(true));
    return () => {
      active = false;
    };
  }, []);

  const value = useMemo(
    () => ({
      status: !checked ? "checking" : session ? "signedIn" : "signedOut",
      user: session?.user || null,
      signIn: signInWithGoogle,
      signOut,
    }),
    [checked, session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

/** Today's usage ({ scope, used, limit, resets_at }) or null. */
export function useUsage() {
  return useSyncExternalStore(subscribeUsage, getUsage, () => null);
}
