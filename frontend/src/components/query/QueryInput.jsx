import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { cn } from "../../lib/utils";

export default function QueryInput({ onSubmit, disabled, initialValue = "", autoFocus = false }) {
  const [value, setValue] = useState(initialValue);

  const submit = () => {
    if (!value.trim() || disabled) return;
    onSubmit(value.trim());
  };

  return (
    <div
      className={cn(
        "hud flex items-center gap-3 px-4 py-3 transition-shadow duration-300",
        "focus-within:border-accent-cyan/40 focus-within:shadow-[0_0_0_1px_rgba(94,234,212,0.25),0_0_40px_-8px_rgba(94,234,212,0.45)]",
        disabled && "opacity-70",
      )}
    >
      <span className="select-none font-mono text-lg leading-none text-accent-cyan" aria-hidden="true">
        ›
      </span>
      <input
        value={value}
        disabled={disabled}
        autoFocus={autoFocus}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        placeholder="Ask anything about your data..."
        aria-label="Your question"
        className="flex-1 bg-transparent font-display text-[15px] text-ink caret-accent-cyan outline-none placeholder:text-ink-faint sm:text-base"
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
