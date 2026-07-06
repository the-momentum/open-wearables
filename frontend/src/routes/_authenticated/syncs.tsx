import { createFileRoute, Outlet } from '@tanstack/react-router';

export const Route = createFileRoute('/_authenticated/syncs')({
  component: SyncsLayout,
});

function SyncsLayout() {
  return <Outlet />;
}
