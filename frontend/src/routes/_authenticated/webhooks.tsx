import { createFileRoute, Outlet } from '@tanstack/react-router';
import { FlaskConical } from 'lucide-react';

export const Route = createFileRoute('/_authenticated/webhooks')({
  component: WebhooksLayout,
});

function WebhooksLayout() {
  return (
    <>
      <div className="px-8 pt-8">
        <div className="flex items-start gap-3 rounded-lg border border-[hsl(var(--warning-muted)/0.2)] bg-[hsl(var(--warning-muted)/0.1)] px-4 py-2.5 text-[hsl(var(--warning-muted))]">
          <FlaskConical className="h-4 w-4 shrink-0 mt-0.5 text-[hsl(var(--warning-muted))]" />
          <p className="text-xs font-medium leading-relaxed">
            <span className="font-semibold text-[hsl(var(--warning-muted))]">
              Beta
            </span>
            {' - '}
            Webhooks are in beta. The API and delivery behavior may change, and
            we don't recommend relying on them for production workloads yet.
          </p>
        </div>
      </div>
      <Outlet />
    </>
  );
}
