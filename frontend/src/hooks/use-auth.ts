import { useMutation } from '@tanstack/react-query';
import { useNavigate } from '@tanstack/react-router';
import { toast } from 'sonner';
import { authService } from '../lib/api';
import { setSession, clearSession, isAuthenticated } from '../lib/auth/session';
import type {
  LoginRequest,
  RegisterRequest,
  ForgotPasswordRequest,
  ResetPasswordRequest,
} from '../lib/api/types';

export function useAuth() {
  const navigate = useNavigate();

  const loginMutation = useMutation({
    mutationFn: (credentials: LoginRequest) => authService.login(credentials),
    onSuccess: (data) => {
      setSession(data.access_token, data.developer_id);
      toast.success('Logged in successfully');
      navigate({ to: '/users' });
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Login failed';
      toast.error(message);
    },
  });

  const registerMutation = useMutation({
    mutationFn: async (data: RegisterRequest) => {
      await authService.register(data);
      const loginResponse = await authService.login({
        email: data.email,
        password: data.password,
      });
      return loginResponse;
    },
    onSuccess: (data) => {
      setSession(data.access_token, data.developer_id);
      toast.success('Account created successfully');
      navigate({ to: '/users' });
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
      clearSession();
      navigate({ to: '/login' });
    },
  });

  const forgotPasswordMutation = useMutation({
    mutationFn: (data: ForgotPasswordRequest) =>
      authService.forgotPassword(data),
    onSuccess: () => {
      toast.success(
        'If an account exists with that email, we have sent password reset instructions'
      );
    },
    onError: () => {
      toast.success(
        'If an account exists with that email, we have sent password reset instructions'
      );
    },
  });

  const resetPasswordMutation = useMutation({
    mutationFn: (data: ResetPasswordRequest) => authService.resetPassword(data),
    onSuccess: () => {
      toast.success('Password reset successfully');
      navigate({ to: '/login' });
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error
          ? error.message
          : 'Unable to reset password. The link may have expired.';
      toast.error(message);
    },
  });

  return {
    login: loginMutation.mutate,
    register: registerMutation.mutate,
    logout: logoutMutation.mutate,
    forgotPassword: forgotPasswordMutation.mutate,
    resetPassword: resetPasswordMutation.mutate,
    isLoggingIn: loginMutation.isPending,
    isRegistering: registerMutation.isPending,
    isLoggingOut: logoutMutation.isPending,
    isForgotPasswordPending: forgotPasswordMutation.isPending,
    isResetPasswordPending: resetPasswordMutation.isPending,
    isAuthenticated: isAuthenticated(),
  };
}
