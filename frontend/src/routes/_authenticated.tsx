import { createFileRoute, Outlet, redirect } from '@tanstack/react-router';
import { SimpleSidebar } from '@/components/layout/simple-sidebar';
import { isAuthenticated } from '@/lib/auth/session';

export const Route = createFileRoute('/_authenticated')({
  component: AuthenticatedLayout,
  beforeLoad: () => {
    if (typeof window !== 'undefined' && !isAuthenticated()) {
      throw redirect({ to: '/login' });
    }
  },
});

function AuthenticatedLayout() {
  return (
    <div className="flex min-h-screen w-full bg-black">
      <SimpleSidebar />
      <main className="flex-1 overflow-auto bg-zinc-950 border-l border-zinc-800/50">
        <Outlet />
      </main>
    </div>
  );
}
