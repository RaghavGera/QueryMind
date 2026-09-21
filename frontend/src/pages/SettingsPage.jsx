import { Card } from "../components/ui/Surfaces";
import { StatusDot } from "../components/ui/Surfaces";

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-5 px-4 sm:px-6 py-10">
      <h1 className="font-display text-2xl font-semibold text-ink">Settings</h1>

      <Card className="p-5">
        <h2 className="mb-3 text-sm font-medium text-ink">Database connection</h2>
        <div className="flex items-center justify-between rounded-lg border border-line bg-white/[0.02] px-4 py-3 text-sm">
          <div>
            <p className="text-ink">sample_ecommerce_db</p>
            <p className="text-xs text-ink-faint">PostgreSQL · read-only mode</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-ink-dim">
            <StatusDot tone="success" pulse /> Connected
          </div>
        </div>
      </Card>

      <Card className="p-5">
        <h2 className="mb-3 text-sm font-medium text-ink">Query behavior</h2>
        <div className="space-y-3 text-sm">
          <label className="flex items-center justify-between">
            <span className="text-ink-dim">Ask for clarification on ambiguous queries</span>
            <input type="checkbox" defaultChecked className="h-4 w-4 accent-accent-violet" />
          </label>
          <label className="flex items-center justify-between">
            <span className="text-ink-dim">Allow write queries (INSERT/UPDATE/DELETE)</span>
            <input type="checkbox" className="h-4 w-4 accent-accent-violet" />
          </label>
          <label className="flex items-center justify-between">
            <span className="text-ink-dim">Require a WHERE clause for all writes</span>
            <input type="checkbox" defaultChecked disabled className="h-4 w-4 accent-accent-violet opacity-60" />
          </label>
        </div>
      </Card>
    </div>
  );
}
