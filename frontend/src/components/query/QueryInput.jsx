import { useState } from "react";
import { ArrowRight, Sparkles } from "lucide-react";
import { cn } from "../../lib/utils";

export default function QueryInput({ onSubmit, disabled, initialValue = "" }) {
  const [value, setValue] = useState(initialValue);

  const submit = () => {
    if (!value.trim() || disabled) return;
    onSubmit(value.trim());
  };

  return (
    <div
      className={cn(
        "surface-card flex items-center gap-3 px-4 py-3 transition-shadow focus-within:shadow-glow-sm",
        disabled && "opacity-70"
      )}
    >
      <Sparkles size={18} className="shrink-0 text-accent-violet" />
      <input
        value={value}
        disabled={disabled}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        placeholder="Ask anything about your data..."
        className="flex-1 bg-transparent text-sm text-ink placeholder:text-ink-faint outline-none sm:text-base"
      />
      <button
        onClick={submit}
        disabled={disabled || !value.trim()}
        className="btn-primary !px-3 !py-2 disabled:opacity-40 disabled:hover:translate-y-0 disabled:hover:shadow-glow-sm"
        aria-label="Submit question"
      >
        <ArrowRight size={16} />
      </button>
    </div>
  );
}
