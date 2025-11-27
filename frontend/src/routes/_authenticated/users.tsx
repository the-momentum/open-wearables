import { createFileRoute, Outlet } from '@tanstack/react-router';

export const Route = createFileRoute('/_authenticated/users')({
  component: UsersLayout,
});

function UsersLayout() {
  return <Outlet />;
}
