import { createFileRoute, redirect, useNavigate } from '@tanstack/react-router';
import { isAuthenticated } from '@/lib/auth/session';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { useEffect } from 'react';

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
  const navigate = useNavigate();
  
  // Handle client-side redirect after hydration
  useEffect(() => {
    if (isAuthenticated()) {
      navigate({ to: '/users' });
    } else {
      navigate({ to: '/login' });
    }
  }, [navigate]);

  // Always render the same content on both server and client to avoid hydration mismatch
  return (
    <div className="min-h-screen flex items-center justify-center bg-black">
      <LoadingSpinner size="lg" />
    </div>
  );
}
