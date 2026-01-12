import { createFileRoute, Outlet } from '@tanstack/react-router';

export const Route = createFileRoute('/users/$userId/pair')({
  component: PairLayout,
});

function PairLayout() {
  return <Outlet />;
}
