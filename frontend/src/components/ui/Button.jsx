import { cn } from "../../lib/utils";

const variants = {
  primary: "btn-primary",
  secondary: "btn-secondary",
  ghost: "btn-ghost",
};

export default function Button({ variant = "primary", className, as: As = "button", ...props }) {
  return <As className={cn(variants[variant], className)} {...props} />;
}
