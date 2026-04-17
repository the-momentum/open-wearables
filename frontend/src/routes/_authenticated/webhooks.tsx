import { createFileRoute, Outlet } from '@tanstack/react-router';

export const Route = createFileRoute('/_authenticated/webhooks')({
  component: WebhooksLayout,
});

function WebhooksLayout() {
  return <Outlet />;
}
