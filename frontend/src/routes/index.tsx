import { createFileRoute, redirect, Navigate } from '@tanstack/react-router';
import { isAuthenticated } from '@/lib/auth/session';
import { LoadingSpinner } from '@/components/common/loading-spinner';

export const Route = createFileRoute('/')({
  beforeLoad: async () => {
    // Skip redirect during SSR - localStorage is not available on the server
    if (typeof window === 'undefined') {
      return;
    }
    // Redirect to users if authenticated, otherwise to login
    if (isAuthenticated()) {
      throw redirect({
        to: '/users',
      });
    } else {
      throw redirect({
        to: '/login',
      });
    }
  },
  component: IndexRedirect,
});

function IndexRedirect() {
  // This component handles the client-side redirect after SSR hydration
  // The beforeLoad will handle the actual redirect, but we need a component
  // for SSR to render something. After hydration, beforeLoad kicks in.
  if (typeof window !== 'undefined') {
    // Client-side: beforeLoad should have already redirected
    // If we get here, fall back to Navigate
    if (isAuthenticated()) {
      return <Navigate to="/users" />;
    }
    return <Navigate to="/login" />;
  }

  // During SSR, render a minimal loading state
  return (
    <div className="min-h-screen flex items-center justify-center bg-black">
      <LoadingSpinner size="lg" />
    </div>
  );
}
