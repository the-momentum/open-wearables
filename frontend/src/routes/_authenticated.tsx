import { createFileRoute, Outlet, redirect } from '@tanstack/react-router';
import { SimpleSidebar } from '@/components/layout/simple-sidebar';
import { isAuthenticated } from '@/lib/auth/session';

export const Route = createFileRoute('/_authenticated')({
  component: AuthenticatedLayout,
  beforeLoad: () => {
    // Skip auth check on server-side rendering
    // Only check authentication in the browser
    if (typeof window !== 'undefined' && !isAuthenticated()) {
      throw redirect({ to: '/login' });
    }
  },
});

function AuthenticatedLayout() {
  return (
    <div className="flex min-h-screen w-full">
      <SimpleSidebar />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
