// Authentication hook

import { useMutation } from '@tanstack/react-query';
import { useNavigate } from '@tanstack/react-router';
import { toast } from 'sonner';
import { authService } from '../lib/api';
import { setSession, clearSession, isAuthenticated } from '../lib/auth/session';
import type { LoginRequest, RegisterRequest } from '../lib/api/types';

export function useAuth() {
  const navigate = useNavigate();

  const loginMutation = useMutation({
    mutationFn: (credentials: LoginRequest) => authService.login(credentials),
    onSuccess: (data) => {
      setSession(data.access_token, data.developer_id);
      toast.success('Logged in successfully');
      navigate({ to: '/dashboard' });
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Login failed';
      toast.error(message);
    },
  });

  const registerMutation = useMutation({
    mutationFn: (data: RegisterRequest) => authService.register(data),
    onSuccess: (data) => {
      setSession(data.access_token, data.developer_id);
      toast.success('Account created successfully');
      navigate({ to: '/dashboard' });
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error ? error.message : 'Registration failed';
      toast.error(message);
    },
  });

  const logoutMutation = useMutation({
    mutationFn: () => authService.logout(),
    onSuccess: () => {
      clearSession();
      toast.success('Logged out successfully');
      navigate({ to: '/login' });
    },
    onError: () => {
      // Clear session even if API call fails
      clearSession();
      navigate({ to: '/login' });
    },
  });

  return {
    login: loginMutation.mutate,
    register: registerMutation.mutate,
    logout: logoutMutation.mutate,
    isLoggingIn: loginMutation.isPending,
    isRegistering: registerMutation.isPending,
    isLoggingOut: logoutMutation.isPending,
    isAuthenticated: isAuthenticated(),
  };
}
