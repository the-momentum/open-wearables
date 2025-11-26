import { createFileRoute, redirect, Link } from '@tanstack/react-router';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { useAuth } from '@/hooks/use-auth';
import { isAuthenticated } from '@/lib/auth/session';
import {
  forgotPasswordSchema,
  type ForgotPasswordFormData,
} from '@/lib/validation/auth.schemas';
import { Activity, Shield, ArrowLeft, Mail, CheckCircle } from 'lucide-react';

export const Route = createFileRoute('/forgot-password')({
  component: ForgotPasswordPage,
  beforeLoad: () => {
    if (typeof window !== 'undefined' && isAuthenticated()) {
      throw redirect({ to: '/dashboard' });
    }
  },
});

function ForgotPasswordPage() {
  const { forgotPassword, isForgotPasswordPending } = useAuth();
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [focusedField, setFocusedField] = useState<string | null>(null);

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
    <div className="min-h-screen w-full relative overflow-hidden bg-gradient-to-br from-slate-950 via-blue-950 to-slate-900">
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-1/4 -left-48 w-96 h-96 bg-blue-500/30 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 -right-48 w-96 h-96 bg-teal-500/30 rounded-full blur-3xl animate-pulse delay-1000" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/20 rounded-full blur-3xl animate-pulse delay-500" />

        <div className="absolute inset-0 bg-[linear-gradient(rgba(59,130,246,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(59,130,246,0.05)_1px,transparent_1px)] bg-[size:64px_64px] [mask-image:radial-gradient(ellipse_80%_50%_at_50%_50%,black,transparent)]" />
      </div>

      <div className="relative z-10 min-h-screen flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          <div className="mb-8 text-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/10 backdrop-blur-sm border border-white/20 text-white">
              <Activity className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-medium">
                Open Wearables Platform
              </span>
            </div>
          </div>

          <div className="relative group">
            <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-500 to-teal-500 rounded-3xl opacity-20 group-hover:opacity-30 blur transition duration-500" />

            <div className="relative bg-slate-900/90 backdrop-blur-xl rounded-3xl border border-white/10 shadow-2xl overflow-hidden">
              <div className="h-2 bg-gradient-to-r from-blue-500 via-teal-500 to-blue-500 animate-gradient" />

              <div className="p-8 sm:p-10">
                {!isSubmitted ? (
                  <>
                    <div className="space-y-2 mb-8">
                      <h2 className="text-3xl font-bold text-white">
                        Reset Password
                      </h2>
                      <p className="text-slate-400">
                        Enter your email and we'll send you a reset link
                      </p>
                    </div>

                    <Form {...form}>
                      <form
                        onSubmit={form.handleSubmit(onSubmit)}
                        className="space-y-6"
                      >
                        <FormField
                          control={form.control}
                          name="email"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel className="text-white font-medium">
                                Email Address
                              </FormLabel>
                              <div className="relative">
                                <FormControl>
                                  <Input
                                    type="email"
                                    placeholder="you@example.com"
                                    autoComplete="email"
                                    onFocus={() => setFocusedField('email')}
                                    onBlur={() => setFocusedField(null)}
                                    className="h-12 bg-white/5 border-white/10 text-white placeholder:text-slate-500 focus:bg-white/10 focus:border-blue-500/50 transition-all duration-300"
                                    {...field}
                                  />
                                </FormControl>
                                {focusedField === 'email' && (
                                  <div className="absolute inset-0 -z-10 bg-blue-500/20 blur-xl rounded-lg transition-opacity" />
                                )}
                              </div>
                              <FormMessage />
                            </FormItem>
                          )}
                        />

                        <Button
                          type="submit"
                          disabled={isForgotPasswordPending}
                          className="w-full h-12 bg-gradient-to-r from-blue-500 to-teal-500 hover:from-blue-600 hover:to-teal-600 text-white font-semibold rounded-xl shadow-lg shadow-blue-500/25 transition-all duration-300 hover:scale-[1.02] hover:shadow-xl hover:shadow-blue-500/40 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 cursor-pointer"
                        >
                          {isForgotPasswordPending ? (
                            <span className="flex items-center gap-2">
                              <svg
                                className="animate-spin h-5 w-5"
                                viewBox="0 0 24 24"
                              >
                                <circle
                                  className="opacity-25"
                                  cx="12"
                                  cy="12"
                                  r="10"
                                  stroke="currentColor"
                                  strokeWidth="4"
                                  fill="none"
                                />
                                <path
                                  className="opacity-75"
                                  fill="currentColor"
                                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                                />
                              </svg>
                              Sending...
                            </span>
                          ) : (
                            'Send Reset Link'
                          )}
                        </Button>
                      </form>
                    </Form>
                  </>
                ) : (
                  <div className="text-center py-4">
                    <div className="w-16 h-16 mx-auto mb-6 bg-green-500/20 rounded-full flex items-center justify-center">
                      <CheckCircle className="w-8 h-8 text-green-400" />
                    </div>
                    <h2 className="text-2xl font-bold text-white mb-2">
                      Check Your Email
                    </h2>
                    <p className="text-slate-400 mb-6">
                      If an account exists with that email, we've sent password
                      reset instructions.
                    </p>
                    <div className="flex items-center justify-center gap-2 text-slate-500 text-sm">
                      <Mail className="w-4 h-4" />
                      <span>Check your inbox and spam folder</span>
                    </div>
                  </div>
                )}
              </div>

              <div className="px-8 sm:px-10 py-6 bg-white/5 border-t border-white/10">
                <Link
                  to="/login"
                  className="flex items-center justify-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back to sign in
                </Link>
              </div>
            </div>
          </div>

          <div className="mt-8 flex items-center justify-center gap-6 text-xs text-slate-500">
            <div className="flex items-center gap-1">
              <Shield className="w-3 h-3" />
              <span>SOC 2 Certified</span>
            </div>
            <div className="flex items-center gap-1">
              <Shield className="w-3 h-3" />
              <span>HIPAA Compliant</span>
            </div>
            <div className="flex items-center gap-1">
              <Shield className="w-3 h-3" />
              <span>GDPR Ready</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
