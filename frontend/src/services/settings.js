const STORAGE_KEY = "querymind.settings";

export const DEFAULT_SETTINGS = {
  // Sent as `strict`: when false, ambiguous questions are answered with the
  // model's best guess (reported as a warning) instead of asking.
  askForClarification: true,
  // Sent as `allow_writes`: the backend still needs QUERYMIND_ENABLE_WRITES.
  allowWrites: false,
};

export function getSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    // fall through to defaults
  }
  return { ...DEFAULT_SETTINGS };
}

export function saveSettings(patch) {
  const next = { ...getSettings(), ...patch };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // best-effort only
  }
  return next;
}
