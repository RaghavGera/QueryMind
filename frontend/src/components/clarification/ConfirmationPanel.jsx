import { motion } from "framer-motion";
import { ShieldCheck } from "lucide-react";

function formatValue(value) {
  if (value === null || value === undefined) return "NULL";
  return typeof value === "string" ? `"${value}"` : String(value);
}

/**
 * Shown for INSERT/UPDATE requests. The backend never runs a write until the
 * user explicitly confirms the exact change previewed here.
 */
export default function ConfirmationPanel({
  confirmation,
  busy = false,
  onConfirm,
  onCancel,
}) {
  const { preview, sql, params = [], expiresIn } = confirmation;
  const changes = preview?.action === "insert" ? preview.values : preview?.set;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="surface-card p-5"
    >
      <p className="mb-1 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-accent-glow">
        <ShieldCheck size={14} />
        Confirm before anything changes
      </p>

      <h3 className="mb-3 text-lg font-medium text-ink">
        {preview?.summary || "This will modify data."}
      </h3>

      {changes && Object.keys(changes).length > 0 && (
        <dl className="mb-3 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
          {Object.entries(changes).map(([column, value]) => (
            <div key={column} className="contents">
              <dt className="text-ink-dim">{column}</dt>
              <dd className="font-mono text-ink">{formatValue(value)}</dd>
            </div>
          ))}
        </dl>
      )}

      {preview?.where?.length > 0 && (
        <p className="mb-3 text-sm text-ink-dim">
          Where{" "}
          {preview.where
            .map((c) => `${c.column} ${c.operator} ${formatValue(c.value)}`)
            .join(" and ")}
        </p>
      )}

      <pre className="mb-4 overflow-x-auto rounded-xl border border-line bg-white/[0.03] p-3 text-xs text-ink-dim">
        {sql}
        {params.length > 0 && `\n-- params: ${JSON.stringify(params)}`}
      </pre>

      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={onConfirm}
          disabled={busy}
          className="btn-primary disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? "Applying..." : "Confirm change"}
        </button>
        <button onClick={onCancel} disabled={busy} className="btn-ghost">
          Cancel
        </button>
        {expiresIn ? (
          <span className="text-xs text-ink-faint">
            Expires in {Math.round(expiresIn / 60)} min
          </span>
        ) : null}
      </div>
    </motion.div>
  );
}
