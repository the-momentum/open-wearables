import { createFileRoute, redirect, Link } from '@tanstack/react-router';
import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useAuth } from '@/hooks/use-auth';
import { isAuthenticated } from '@/lib/auth/session';
import {
  resetPasswordSchema,
  type ResetPasswordFormData,
} from '@/lib/validation/auth.schemas';
import {
  Activity,
  Eye,
  EyeOff,
  AlertCircle,
  ArrowLeft,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export const Route = createFileRoute('/reset-password')({
  component: ResetPasswordPage,
  validateSearch: (search: Record<string, unknown>) => ({
    token: (search.token as string) || '',
  }),
  beforeLoad: () => {
    if (typeof window !== 'undefined' && isAuthenticated()) {
      throw redirect({ to: '/users' });
    }
  },
});

function ResetPasswordPage() {
  const { token } = Route.useSearch();
  const { resetPassword, isResetPasswordPending } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  useEffect(() => {
    if (token && typeof window !== 'undefined') {
      window.history.replaceState({}, '', '/reset-password');
    }
  }, [token]);

  const form = useForm<ResetPasswordFormData>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: {
      password: '',
      confirmPassword: '',
    },
  });

  const onSubmit = (data: ResetPasswordFormData) => {
    if (!token) return;
    resetPassword({ token, password: data.password });
  };

  // Error state - no token
  if (!token) {
    return (
      <div className="bg-black text-zinc-400 antialiased h-screen w-screen overflow-hidden selection:bg-zinc-800 selection:text-white flex items-center justify-center p-4 sm:p-8 relative">
        <div className="absolute inset-0 bg-grid opacity-30" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[400px] bg-red-900/20 rounded-full blur-[120px] pointer-events-none" />

        <div className="w-full max-w-md bg-black border border-zinc-900/80 rounded-2xl overflow-hidden shadow-[0_0_50px_-12px_rgba(0,0,0,0.8)] relative z-10 backdrop-blur-sm">
          <div className="p-8 border-b border-zinc-900">
            <div className="flex items-center gap-2 mb-8">
              <div className="w-6 h-6 bg-white rounded flex items-center justify-center">
                <Activity className="text-black w-4 h-4" />
              </div>
              <span className="text-sm font-medium text-white tracking-tight uppercase">
                Open Wearables
              </span>
            </div>

            <div className="text-center py-4">
              <div className="w-16 h-16 mx-auto mb-6 bg-red-500/20 rounded-full flex items-center justify-center">
                <AlertCircle className="w-8 h-8 text-red-400" />
              </div>
              <h2 className="text-xl font-medium text-white mb-2">
                Invalid Reset Link
              </h2>
              <p className="text-sm text-zinc-500">
                This password reset link is invalid or has expired. Please
                request a new one.
              </p>
            </div>
          </div>

          <div className="p-8 space-y-4">
            <Link
              to="/forgot-password"
              className="w-full bg-white text-black hover:bg-zinc-200 font-medium text-sm h-9 rounded-md transition-colors flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(255,255,255,0.1)]"
            >
              Request New Reset Link
            </Link>
          </div>

          <div className="px-8 py-6 border-t border-zinc-900 bg-zinc-950/50">
            <Link
              to="/login"
              className="flex items-center justify-center gap-2 text-sm text-zinc-500 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to sign in
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-black text-zinc-400 antialiased h-screen w-screen overflow-hidden selection:bg-zinc-800 selection:text-white flex items-center justify-center p-4 sm:p-8 relative">
      <div className="absolute inset-0 bg-grid opacity-30" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[400px] bg-indigo-900/20 rounded-full blur-[120px] pointer-events-none" />

      <div className="w-full max-w-md bg-black border border-zinc-900/80 rounded-2xl overflow-hidden shadow-[0_0_50px_-12px_rgba(0,0,0,0.8)] relative z-10 backdrop-blur-sm">
        <div className="p-8 border-b border-zinc-900">
          <div className="flex items-center gap-2 mb-8">
            <div className="w-6 h-6 bg-white rounded flex items-center justify-center">
              <Activity className="text-black w-4 h-4" />
            </div>
            <span className="text-sm font-medium text-white tracking-tight uppercase">
              Open Wearables
            </span>
          </div>

          <h1 className="text-2xl font-medium tracking-tight text-white">
            Set New Password
          </h1>
          <p className="text-sm text-zinc-500 mt-2">
            Enter your new password below
          </p>
        </div>

        <div className="p-8 space-y-6">
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            {/* New Password */}
            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-xs text-zinc-300">
                New password
              </Label>
              <div className="relative group">
                <Input
                  type={showPassword ? 'text' : 'password'}
                  id="password"
                  {...form.register('password')}
                  className="bg-zinc-900/50 border-zinc-800 pr-10"
                  placeholder="At least 8 characters"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-3 flex items-center text-zinc-500 hover:text-zinc-300 transition-colors"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
              {form.formState.errors.password && (
                <p className="text-xs text-red-500">
                  {form.formState.errors.password.message}
                </p>
              )}
            </div>

            {/* Confirm Password */}
            <div className="space-y-1.5">
              <Label
                htmlFor="confirmPassword"
                className="text-xs text-zinc-300"
              >
                Confirm new password
              </Label>
              <div className="relative group">
                <Input
                  type={showConfirmPassword ? 'text' : 'password'}
                  id="confirmPassword"
                  {...form.register('confirmPassword')}
                  className="bg-zinc-900/50 border-zinc-800 pr-10"
                  placeholder="Confirm your password"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute inset-y-0 right-3 flex items-center text-zinc-500 hover:text-zinc-300 transition-colors"
                >
                  {showConfirmPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
              {form.formState.errors.confirmPassword && (
                <p className="text-xs text-red-500">
                  {form.formState.errors.confirmPassword.message}
                </p>
              )}
            </div>

            <Button
              type="submit"
              disabled={isResetPasswordPending}
              className="w-full"
            >
              {isResetPasswordPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Resetting password...
                </>
              ) : (
                'Reset Password'
              )}
            </Button>
          </form>
        </div>

        <div className="px-8 py-6 border-t border-zinc-900 bg-zinc-950/50">
          <Link
            to="/login"
            className="flex items-center justify-center gap-2 text-sm text-zinc-500 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
