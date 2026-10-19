import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowLeft, CheckCircle2, FileSpreadsheet, KeyRound, Link2, Loader2, LogIn, Upload, X } from "lucide-react";
import { useAuth } from "../auth/AuthProvider";
import { workspaces } from "../hooks/useWorkspaces";
import { importUpload, previewUpload } from "../services/queryApi";
import { forgetSchema } from "../services/schemaApi";
import { expiresIn } from "../services/workspaces.js";
import PageHeader from "../components/ui/PageHeader";
import { cn } from "../lib/utils";

// Same limits as app/uploads.py (checked here first so nothing too big is sent).
const MAX_FILES = 10;
const MAX_TOTAL_BYTES = 10 * 1024 * 1024;
const ACCEPT = [".csv", ".tsv", ".txt", ".xlsx", ".xlsm"];

const TYPE_LABELS = {
  integer: "Whole number",
  decimal: "Decimal number",
  date: "Date",
  timestamp: "Date and time",
  boolean: "Yes / No",
  text: "Text",
};

function size(bytes) {
  return bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function checkFiles(files) {
  if (files.length > MAX_FILES) return `Choose at most ${MAX_FILES} files.`;
  const total = files.reduce((sum, f) => sum + f.size, 0);
  if (total > MAX_TOTAL_BYTES) return `The files add up to ${size(total)}; the limit is 10 MB.`;
  const odd = files.find((f) => !ACCEPT.some((ext) => f.name.toLowerCase().endsWith(ext)));
  if (odd) return `${odd.name}: only CSV and Excel (.xlsx) files can be uploaded.`;
  return null;
}

/** The edits the server applies (app/uploads.py apply_edits), from the editor's tables. */
function planFrom(tables) {
  return {
    tables: tables.map((t) => ({
      key: t.key,
      name: t.name,
      include: t.include,
      columns: t.columns.map((c) => ({ key: c.key, name: c.name, type: c.type, date_order: c.date_order })),
    })),
  };
}

function Notes({ items }) {
  if (!items?.length) return null;
  return (
    <ul className="space-y-1 text-xs text-ink-dim">
      {items.map((note) => (
        <li key={note} className="flex items-start gap-2">
          <AlertTriangle size={13} className="mt-0.5 shrink-0 text-accent-amber" />
          {note}
        </li>
      ))}
    </ul>
  );
}

function TableEditor({ table, types, onChange }) {
  const update = (patch) => onChange({ ...table, ...patch });
  const updateColumn = (key, patch) =>
    update({ columns: table.columns.map((c) => (c.key === key ? { ...c, ...patch } : c)) });
  return (
    <section className={cn("hud space-y-4 p-5 transition-opacity", !table.include && "opacity-50")}>
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-ink-dim">
          <input type="checkbox" checked={table.include} onChange={(e) => update({ include: e.target.checked })} className="accent-[#8b7bff]" />
          Import
        </label>
        <label className="order-first flex w-full min-w-0 items-center gap-2 sm:order-none sm:w-auto sm:flex-1">
          <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-faint">Table</span>
          <input
            value={table.name}
            onChange={(e) => update({ name: e.target.value })}
            disabled={!table.include}
            className="min-w-0 flex-1 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 font-mono text-sm text-ink focus:border-accent-violet/50 focus:outline-none"
            aria-label={`Name of the table from ${table.source}`}
          />
        </label>
        <span className="text-xs text-ink-faint">
          {table.source} · {table.rows.toLocaleString("en")} row{table.rows === 1 ? "" : "s"}
        </span>
        {table.primary_key && (
          <span className="flex items-center gap-1 rounded-full border border-accent-amber/30 px-2 py-0.5 text-xs text-accent-amber" title="Every value is unique: used as the table's key">
            <KeyRound size={12} /> {table.primary_key}
          </span>
        )}
      </div>
      <Notes items={table.notes} />
      {table.include && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-faint">
                <th className="pb-2 pr-3 font-medium">In the file</th>
                <th className="pb-2 pr-3 font-medium">Name</th>
                <th className="pb-2 pr-3 font-medium">Type</th>
                <th className="pb-2 font-medium">Sample values</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.05]">
              {table.columns.map((column) => {
                const dated = column.type === "date" || column.type === "timestamp";
                return (
                  <tr key={column.key} className="align-top">
                    <td className="py-2 pr-3 text-ink-dim">{column.original}</td>
                    <td className="py-2 pr-3">
                      <input
                        value={column.name}
                        onChange={(e) => updateColumn(column.key, { name: e.target.value })}
                        className="w-full rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 font-mono text-xs text-ink focus:border-accent-violet/50 focus:outline-none"
                        aria-label={`Name for ${column.original}`}
                      />
                    </td>
                    <td className="py-2 pr-3">
                      <select
                        value={column.type}
                        onChange={(e) => updateColumn(column.key, { type: e.target.value })}
                        className="w-full rounded-md border border-white/10 bg-base-900 px-2 py-1 text-xs text-ink focus:border-accent-violet/50 focus:outline-none"
                        aria-label={`Type of ${column.original}`}
                      >
                        {types.map((t) => (
                          <option key={t} value={t}>
                            {TYPE_LABELS[t] || t}
                          </option>
                        ))}
                      </select>
                      {dated && (
                        <select
                          value={column.date_order || "dmy"}
                          onChange={(e) => updateColumn(column.key, { date_order: e.target.value })}
                          className={cn(
                            "mt-1 w-full rounded-md border bg-base-900 px-2 py-1 text-xs text-ink focus:outline-none",
                            column.ambiguous_dates ? "border-accent-amber/50" : "border-white/10",
                          )}
                          aria-label={`Date order of ${column.original}`}
                        >
                          <option value="dmy">Day first (DD/MM)</option>
                          <option value="mdy">Month first (MM/DD)</option>
                        </select>
                      )}
                      {column.ambiguous_dates && dated && (
                        <p className="mt-1 text-[11px] text-accent-amber">Check: 03/04 could be either.</p>
                      )}
                    </td>
                    <td className="py-2">
                      <div className="flex flex-wrap gap-1">
                        {column.samples.length ? (
                          column.samples.map((v) => (
                            <span key={v} className="rounded bg-white/[0.04] px-1.5 py-0.5 font-mono text-[11px] text-ink-dim">
                              {v}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-ink-faint">empty</span>
                        )}
                      </div>
                      {column.notes?.length > 0 && <div className="mt-1"><Notes items={column.notes} /></div>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function SignInFirst() {
  return (
    <div className="hud flex flex-col items-start gap-4 p-6">
      <p className="text-ink">Sign in to upload your own data.</p>
      <p className="text-sm text-ink-dim">
        Your files become a private workspace only you can ask. It's read-only and is deleted after 7 days.
      </p>
      <Link to="/signin?next=/app/connect" className="btn-primary">
        <LogIn size={15} /> Sign in with Google
      </Link>
    </div>
  );
}

export default function ConnectPage() {
  const { status } = useAuth();
  const navigate = useNavigate();
  const input = useRef(null);
  const [files, setFiles] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [preview, setPreview] = useState(null);
  const [tables, setTables] = useState([]);
  const [name, setName] = useState("");
  const [replace, setReplace] = useState(false);
  const [busy, setBusy] = useState(null); // "reading" | "checking" | "importing"
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null);

  if (status === "checking") return null;

  const addFiles = (picked) => {
    const next = [...files];
    for (const file of picked) if (!next.some((f) => f.name === file.name && f.size === file.size)) next.push(file);
    setFiles(next);
    setError(checkFiles(next));
  };

  const showPreview = (body) => {
    setPreview(body);
    setTables(body.tables);
    setName((current) => {
      if (current) return current;
      const first = (files[0]?.name || "My data").replace(/\.[^.]+$/, "");
      return files.length > 1 ? `${first} and ${files.length - 1} more` : first;
    });
  };

  const analyse = async () => {
    const problem = checkFiles(files);
    if (problem) return setError(problem);
    setBusy("reading");
    setError(null);
    try {
      showPreview(await previewUpload(files));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  const checkChanges = async () => {
    setBusy("checking");
    setError(null);
    try {
      showPreview(await previewUpload(files, planFrom(tables)));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  const runImport = async () => {
    setBusy("importing");
    setError(null);
    try {
      const result = await importUpload(files, { plan: planFrom(tables), name, replace });
      forgetSchema(result.workspace.id);
      await workspaces.useNew(result.workspace);
      setDone(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  const startOver = () => {
    setFiles([]);
    setPreview(null);
    setTables([]);
    setName("");
    setReplace(false);
    setError(null);
    setDone(null);
  };

  const included = tables.filter((t) => t.include);
  const mustConfirm = Boolean(preview?.replaces) && !replace;

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-10 sm:px-6">
      <PageHeader
        label="Your data"
        title="Ask questions about your own files."
        detail="Upload CSV or Excel files. QueryMind shows what it found, you adjust it, and it becomes a private, read-only workspace for 7 days."
      />

      {status !== "signedIn" ? (
        <SignInFirst />
      ) : done ? (
        <div className="hud space-y-4 p-6">
          <p className="flex items-center gap-2 text-lg text-ink">
            <CheckCircle2 size={20} className="text-state-success" /> {done.workspace.name} is ready.
          </p>
          <p className="text-sm text-ink-dim">
            {done.tables.length} table{done.tables.length === 1 ? "" : "s"},{" "}
            {done.tables.reduce((n, t) => n + t.rows, 0).toLocaleString("en")} rows, {done.links.length} link
            {done.links.length === 1 ? "" : "s"}, {size(done.size_bytes)} in the database · {expiresIn(done.workspace.expires_at)}.
          </p>
          <ul className="flex flex-wrap gap-2">
            {done.tables.map((t) => (
              <li key={t.name} className="rounded-lg border border-white/10 px-3 py-1.5 font-mono text-xs text-ink-dim">
                {t.name} · {t.rows.toLocaleString("en")}
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => navigate("/app")} className="btn-primary">Ask about your data</button>
            <button onClick={startOver} className="btn-secondary">Upload different files</button>
          </div>
        </div>
      ) : !preview ? (
        <div className="space-y-4">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              addFiles([...e.dataTransfer.files]);
            }}
            onClick={() => input.current?.click()}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
            role="button"
            tabIndex={0}
            className={cn(
              "hud flex cursor-pointer flex-col items-center justify-center gap-3 border-dashed px-6 py-14 text-center transition-colors",
              dragging && "border-accent-cyan/60 bg-accent-cyan/[0.04]",
            )}
          >
            <Upload size={26} className="text-accent-cyan" />
            <p className="text-ink">Drop CSV or Excel files here, or click to choose</p>
            <p className="text-xs text-ink-faint">Up to 10 files · 10 MB in total · 200,000 rows per table · each Excel sheet becomes a table</p>
            <input
              ref={input}
              type="file"
              multiple
              accept={ACCEPT.join(",")}
              className="hidden"
              onChange={(e) => {
                addFiles([...e.target.files]);
                e.target.value = "";
              }}
            />
          </div>
          {files.length > 0 && (
            <ul className="space-y-2">
              {files.map((file) => (
                <li key={`${file.name}-${file.size}`} className="flex items-center justify-between gap-3 rounded-lg border border-white/[0.06] px-3 py-2 text-sm">
                  <span className="flex min-w-0 items-center gap-2 text-ink">
                    <FileSpreadsheet size={15} className="shrink-0 text-ink-faint" />
                    <span className="truncate">{file.name}</span>
                    <span className="shrink-0 text-xs text-ink-faint">{size(file.size)}</span>
                  </span>
                  <button
                    onClick={() => {
                      const next = files.filter((f) => f !== file);
                      setFiles(next);
                      setError(checkFiles(next));
                    }}
                    className="btn-ghost !p-1"
                    aria-label={`Remove ${file.name}`}
                  >
                    <X size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}
          {error && <p className="text-sm text-state-danger">{error}</p>}
          <button onClick={analyse} disabled={!files.length || Boolean(error) || Boolean(busy)} className="btn-primary disabled:opacity-50">
            {busy ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />}
            {busy ? "Reading your files…" : "Analyse files"}
          </button>
        </div>
      ) : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-ink">
              Found {preview.tables.length} table{preview.tables.length === 1 ? "" : "s"} and {preview.links.length} link
              {preview.links.length === 1 ? "" : "s"}. Check the names and types, then import.
            </p>
            <button onClick={() => setPreview(null)} className="btn-ghost">
              <ArrowLeft size={14} /> Choose other files
            </button>
          </div>
          <Notes items={preview.notes} />

          {tables.map((table) => (
            <TableEditor
              key={table.key}
              table={table}
              types={preview.types}
              onChange={(next) => setTables(tables.map((t) => (t.key === next.key ? next : t)))}
            />
          ))}

          <section className="hud space-y-2 p-5">
            <p className="hud-label">Links between tables</p>
            {preview.links.length ? (
              <ul className="space-y-1 font-mono text-xs text-ink-dim">
                {preview.links.map((l) => (
                  <li key={`${l.table}.${l.column}`} className="flex items-center gap-2">
                    <Link2 size={13} className="text-accent-cyan" />
                    {l.table}.{l.column} → {l.ref_table}.{l.ref_column}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-dim">
                None found. A column like customer_id links to a customers table when every value matches its key.
              </p>
            )}
            <p className="text-xs text-ink-faint">Renamed columns are linked again when you check your changes or import.</p>
          </section>

          <section className="hud space-y-4 p-5">
            <label className="flex flex-wrap items-center gap-3">
              <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-faint">Workspace name</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={100}
                className="min-w-0 flex-1 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-sm text-ink focus:border-accent-violet/50 focus:outline-none"
              />
            </label>
            {preview.replaces && (
              <label className="flex items-start gap-2 text-sm text-ink">
                <input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} className="mt-1 accent-[#fb7185]" />
                <span>
                  Replace <strong>{preview.replaces.name}</strong>. You can have one workspace; its data will be deleted (your history stays).
                </span>
              </label>
            )}
            {error && (
              <p className="flex items-start gap-2 text-sm text-state-danger">
                <AlertTriangle size={15} className="mt-0.5 shrink-0" />
                {error}
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <button onClick={checkChanges} disabled={Boolean(busy)} className="btn-secondary disabled:opacity-50">
                {busy === "checking" && <Loader2 size={15} className="animate-spin" />} Check changes
              </button>
              <button
                onClick={runImport}
                disabled={Boolean(busy) || !included.length || mustConfirm}
                className="btn-primary disabled:opacity-50"
                title={mustConfirm ? "Tick 'Replace' first" : undefined}
              >
                {busy === "importing" ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />}
                {busy === "importing" ? "Importing…" : `Import ${included.length} table${included.length === 1 ? "" : "s"}`}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
