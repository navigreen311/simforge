import { type ReactNode } from "react";

export function EmptyState({
  title,
  description,
  icon,
  action,
}: {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-ink-500 bg-ink-800 p-8 text-center">
      {icon && <div className="text-2xl text-gold-500">{icon}</div>}
      <div className="text-base font-medium text-gold-400">{title}</div>
      {description && <p className="max-w-md text-sm text-ink-300">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
