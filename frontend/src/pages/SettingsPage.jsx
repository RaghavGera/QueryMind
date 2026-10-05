import { useEffect, useState } from "react";
import { Card } from "../components/ui/Surfaces";
import { StatusDot } from "../components/ui/Surfaces";
import { getHealth } from "../services/queryApi";
import { getSettings, saveSettings } from "../services/settings";

function Setting({ label, hint, children }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-ink-dim">{label}</p>
        {hint && <p className="mt-0.5 text-xs text-ink-faint">{hint}</p>}
      </div>
      <div className="shrink-0 pt-0.5">{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState(getSettings);
  // null while loading; { error } if the backend could not be reached.
  const [health, setHealth] = useState(null);

  useEffect(() => {
    let active = true;
    getHealth()
      .then((body) => active && setHealth(body))
      .catch((error) => active && setHealth({ error: error.message }));
    return () => {
      active = false;
    };
  }, []);

  const update = (patch) => setSettings(saveSettings(patch));

  const connected = health?.database?.connected === true;
  const serverWrites = health?.writes_enabled;
  const writesLocked = serverWrites === false;

  let connectionTone = "idle";
  let connectionLabel = "Checking…";
  if (health?.error) {
    connectionTone = "danger";
    connectionLabel = "Unreachable";
  } else if (health) {
    connectionTone = connected ? "success" : "danger";
    connectionLabel = connected ? "Connected" : "Disconnected";
  }

  let writesHint = "Every change is previewed and runs only after you confirm it. DELETE is never run.";
  if (writesLocked) {
    writesHint = "Disabled on this server (the backend needs QUERYMIND_ENABLE_WRITES=true).";
  } else if (serverWrites === undefined && !health?.error) {
    writesHint = "Checking whether this server accepts writes…";
  }

  return (
    <div className="mx-auto max-w-2xl space-y-5 px-4 sm:px-6 py-10">
      <h1 className="font-display text-2xl font-semibold text-ink">Settings</h1>

      <Card className="p-5">
        <h2 className="mb-3 text-sm font-medium text-ink">Database connection</h2>
        <div className="flex items-center justify-between rounded-lg border border-line bg-white/[0.02] px-4 py-3 text-sm">
          <div>
            <p className="text-ink">{health?.database?.database || "sample_ecommerce_db"}</p>
            <p className="text-xs text-ink-faint">
              PostgreSQL · {serverWrites ? "writes allowed (with confirmation)" : "read-only mode"}
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-ink-dim">
            <StatusDot tone={connectionTone} pulse={connected} /> {connectionLabel}
          </div>
        </div>
        {health?.error && <p className="mt-2 text-xs text-state-danger">{health.error}</p>}
      </Card>

      <Card className="p-5">
        <h2 className="mb-3 text-sm font-medium text-ink">Query behavior</h2>
        <div className="space-y-4 text-sm">
          <Setting
            label="Ask for clarification on ambiguous queries"
            hint={
              settings.askForClarification
                ? "Unclear questions get a follow-up question instead of a guess."
                : "Unclear questions are answered with the model's best guess (check the generated SQL); a warning says what was unclear. Unsafe requests are still blocked."
            }
          >
            <input
              type="checkbox"
              checked={settings.askForClarification}
              onChange={(e) => update({ askForClarification: e.target.checked })}
              className="h-4 w-4 accent-accent-violet"
            />
          </Setting>

          <Setting label="Allow write queries (INSERT/UPDATE)" hint={writesHint}>
            <input
              type="checkbox"
              checked={settings.allowWrites && !writesLocked}
              disabled={writesLocked}
              onChange={(e) => update({ allowWrites: e.target.checked })}
              className="h-4 w-4 accent-accent-violet disabled:opacity-60"
            />
          </Setting>

          <Setting
            label="Require a WHERE clause for all writes"
            hint="Always on: an UPDATE must say which rows to change, and deleting data is not supported."
          >
            <span className="rounded-full border border-line px-2 py-0.5 text-xs text-ink-faint">Always on</span>
          </Setting>
        </div>
      </Card>
    </div>
  );
}
