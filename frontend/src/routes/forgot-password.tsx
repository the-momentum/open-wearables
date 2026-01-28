import { createFileRoute, redirect, Link } from '@tanstack/react-router';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useAuth } from '@/hooks/use-auth';
import { isAuthenticated } from '@/lib/auth/session';
import {
  forgotPasswordSchema,
  type ForgotPasswordFormData,
} from '@/lib/validation/auth.schemas';
import { Activity, ArrowLeft, Mail, CheckCircle, Loader2 } from 'lucide-react';
import { DEFAULT_REDIRECTS, ROUTES } from '@/lib/constants/routes';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export const Route = createFileRoute('/forgot-password')({
  component: ForgotPasswordPage,
  beforeLoad: () => {
    if (typeof window !== 'undefined' && isAuthenticated()) {
      throw redirect({ to: DEFAULT_REDIRECTS.authenticated });
    }
  },
});

function ForgotPasswordPage() {
  const { forgotPassword, isForgotPasswordPending } = useAuth();
  const [isSubmitted, setIsSubmitted] = useState(false);

  const form = useForm<ForgotPasswordFormData>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: {
      email: '',
    },
  });

  const onSubmit = (data: ForgotPasswordFormData) => {
    forgotPassword(
      { email: data.email },
      {
        onSettled: () => {
          setIsSubmitted(true);
        },
      }
    );
  };

  return (
    <div className="bg-black text-zinc-400 antialiased h-screen w-screen overflow-hidden selection:bg-zinc-800 selection:text-white flex items-center justify-center p-4 sm:p-8 relative">
      {/* Background */}
      <div className="absolute inset-0 bg-grid opacity-30" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[400px] bg-indigo-900/20 rounded-full blur-[120px] pointer-events-none" />

      {/* Card */}
      <div className="w-full max-w-md bg-black border border-zinc-900/80 rounded-2xl overflow-hidden shadow-[0_0_50px_-12px_rgba(0,0,0,0.8)] relative z-10 backdrop-blur-sm">
        {/* Header */}
        <div className="p-8 border-b border-zinc-900">
          <div className="flex items-center gap-2 mb-8">
            <div className="w-6 h-6 bg-white rounded flex items-center justify-center">
              <Activity className="text-black w-4 h-4" />
            </div>
            <span className="text-sm font-medium text-white tracking-tight uppercase">
              Open Wearables
            </span>
          </div>

          {!isSubmitted ? (
            <>
              <h1 className="text-2xl font-medium tracking-tight text-white">
                Reset Password
              </h1>
              <p className="text-sm text-zinc-500 mt-2">
                Enter your email and we'll send you a reset link
              </p>
            </>
          ) : (
            <div className="text-center py-4">
              <div className="w-16 h-16 mx-auto mb-6 bg-emerald-500/20 rounded-full flex items-center justify-center">
                <CheckCircle className="w-8 h-8 text-emerald-400" />
              </div>
              <h2 className="text-xl font-medium text-white mb-2">
                Check Your Email
              </h2>
              <p className="text-sm text-zinc-500">
                If an account exists with that email, we've sent password reset
                instructions.
              </p>
              <div className="flex items-center justify-center gap-2 text-zinc-600 text-xs mt-4">
                <Mail className="w-4 h-4" />
                <span>Check your inbox and spam folder</span>
              </div>
            </div>
          )}
        </div>

        {/* Form */}
        {!isSubmitted && (
          <div className="p-8 space-y-6">
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="email" className="text-xs text-zinc-300">
                  Email address
                </Label>
                <div className="relative group">
                  <Input
                    type="email"
                    id="email"
                    {...form.register('email')}
                    className="bg-zinc-900/50 border-zinc-800 pr-10"
                    placeholder="you@example.com"
                  />
                  <div className="absolute inset-y-0 right-3 flex items-center pointer-events-none opacity-0 group-focus-within:opacity-100 transition-opacity">
                    <Mail className="w-4 h-4 text-zinc-500" />
                  </div>
                </div>
                {form.formState.errors.email && (
                  <p className="text-xs text-red-500">
                    {form.formState.errors.email.message}
                  </p>
                )}
              </div>

              <Button
                type="submit"
                disabled={isForgotPasswordPending}
                className="w-full"
              >
                {isForgotPasswordPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Sending...
                  </>
                ) : (
                  'Send Reset Link'
                )}
              </Button>
            </form>
          </div>
        )}

        {/* Footer */}
        <div className="px-8 py-6 border-t border-zinc-900 bg-zinc-950/50">
          <Link
            to={ROUTES.login}
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
