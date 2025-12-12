import {
  createFileRoute,
  redirect,
  Link,
  useNavigate,
} from '@tanstack/react-router';
import { useState, useEffect, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { isAuthenticated } from '@/lib/auth/session';
import logotype from '@/logotype.svg';
import {
  acceptInvitationSchema,
  type AcceptInvitationFormData,
} from '@/lib/validation/auth.schemas';
import { useAcceptInvitation } from '@/hooks/api/use-invitations';
import {
  Activity,
  ArrowRight,
  Eye,
  EyeOff,
  AlertCircle,
  ArrowLeft,
  Users,
  CheckCircle2,
} from 'lucide-react';

export const Route = createFileRoute('/accept-invite')({
  component: AcceptInvitePage,
  validateSearch: (search: Record<string, unknown>) => ({
    token: (search.token as string) || '',
  }),
  beforeLoad: () => {
    if (typeof window !== 'undefined' && isAuthenticated()) {
      throw redirect({ to: '/dashboard' });
    }
  },
});

function AcceptInvitePage() {
  const { token } = Route.useSearch();
  const navigate = useNavigate();
  const acceptInvitationMutation = useAcceptInvitation();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout>(null);
  const form = useForm<AcceptInvitationFormData>({
    resolver: zodResolver(acceptInvitationSchema),
    defaultValues: {
      first_name: '',
      last_name: '',
      password: '',
      confirmPassword: '',
    },
  });

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const onSubmit = (data: AcceptInvitationFormData) => {
    if (!token) return;

    acceptInvitationMutation.mutate(
      {
        token,
        first_name: data.first_name,
        last_name: data.last_name,
        password: data.password,
      },
      {
        onSuccess: () => {
          setIsSuccess(true);
          timeoutRef.current = setTimeout(() => {
            navigate({ to: '/login' });
          }, 2000);
        },
        onError: (error) => {
          form.setError('root', {
            type: 'manual',
            message:
              error.message ||
              'Failed to accept invitation. The link may be invalid or expired.',
          });
        },
      }
    );
  };

  if (isSuccess) {
    return (
      <div className="bg-black text-zinc-400 antialiased h-screen w-screen overflow-hidden selection:bg-zinc-800 selection:text-white flex items-center justify-center p-4 sm:p-8 relative">
        <div className="absolute inset-0 bg-grid opacity-30" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[400px] bg-emerald-900/20 rounded-full blur-[120px] pointer-events-none" />

        <div className="w-full max-w-md bg-black border border-zinc-900/80 rounded-2xl overflow-hidden shadow-[0_0_50px_-12px_rgba(0,0,0,0.8)] relative z-10 backdrop-blur-sm">
          <div className="p-8 border-b border-zinc-900">
            <div className="flex items-center gap-2 mb-8">
              <div className="w-6 h-6 bg-white rounded flex items-center justify-center">
                <img src={logotype} alt="Open Wearables" className="h-30" />
              </div>
              <span className="text-sm font-medium text-white tracking-tight uppercase">
                Open Wearables
              </span>
            </div>

            <div className="text-center py-4">
              <div className="w-16 h-16 mx-auto mb-6 bg-emerald-500/20 rounded-full flex items-center justify-center">
                <CheckCircle2 className="w-8 h-8 text-emerald-400" />
              </div>
              <h2 className="text-xl font-medium text-white mb-2">
                Welcome to the Team!
              </h2>
              <p className="text-sm text-zinc-500">
                Your account has been created successfully. Redirecting you to
                sign in...
              </p>
            </div>
          </div>

          <div className="p-8 space-y-4">
            <Link
              to="/login"
              className="w-full bg-white text-black hover:bg-zinc-200 font-medium text-sm h-9 rounded-md transition-colors flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(255,255,255,0.1)]"
            >
              Sign In Now
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="bg-black text-zinc-400 antialiased h-screen w-screen overflow-hidden selection:bg-zinc-800 selection:text-white flex items-center justify-center p-4 sm:p-8 relative">
        <div className="absolute inset-0 bg-grid opacity-30" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[400px] bg-red-900/20 rounded-full blur-[120px] pointer-events-none" />

        <div className="w-full max-w-md bg-black border border-zinc-900/80 rounded-2xl overflow-hidden shadow-[0_0_50px_-12px_rgba(0,0,0,0.8)] relative z-10 backdrop-blur-sm">
          <div className="p-8 border-b border-zinc-900">
            <div className="flex items-center gap-2 mb-8">
              <div className="w-6 h-6 bg-white rounded flex items-center justify-center">
                <img src={logotype} alt="Open Wearables" className="h-30" />
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
                Invalid Invitation Link
              </h2>
              <p className="text-sm text-zinc-500">
                This invitation link is invalid or has expired. Please contact
                your team administrator for a new invitation.
              </p>
            </div>
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

      <div className="w-full max-w-[1100px] h-full max-h-[700px] grid lg:grid-cols-2 bg-black border border-zinc-900/80 rounded-2xl overflow-hidden shadow-[0_0_50px_-12px_rgba(0,0,0,0.8)] relative z-10 backdrop-blur-sm">
        <div className="flex flex-col justify-between p-8 sm:p-12 border-b lg:border-b-0 lg:border-r border-zinc-900 bg-black/90">
          <div className="flex items-center justify-center gap-2">
              <img src={logotype} alt="Open Wearables" className="h-30" />
          </div>

          <div className="w-full max-w-sm mx-auto space-y-6 my-auto py-8">
            <div className="space-y-2">
              <h1 className="text-2xl font-medium tracking-tight text-white">
                Accept Invitation
              </h1>
              <p className="text-sm text-zinc-500">
                Complete your account setup to join the team
              </p>
            </div>

            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label
                    htmlFor="first_name"
                    className="text-xs font-medium text-zinc-300"
                  >
                    First name
                  </label>
                  <input
                    type="text"
                    id="first_name"
                    {...form.register('first_name')}
                    className="w-full bg-zinc-900/50 border border-zinc-800 rounded-md px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-700 focus:border-zinc-700 transition-all shadow-sm"
                    placeholder="John"
                  />
                  {form.formState.errors.first_name && (
                    <p className="text-xs text-red-500">
                      {form.formState.errors.first_name.message}
                    </p>
                  )}
                </div>

                <div className="space-y-1.5">
                  <label
                    htmlFor="last_name"
                    className="text-xs font-medium text-zinc-300"
                  >
                    Last name
                  </label>
                  <input
                    type="text"
                    id="last_name"
                    {...form.register('last_name')}
                    className="w-full bg-zinc-900/50 border border-zinc-800 rounded-md px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-700 focus:border-zinc-700 transition-all shadow-sm"
                    placeholder="Doe"
                  />
                  {form.formState.errors.last_name && (
                    <p className="text-xs text-red-500">
                      {form.formState.errors.last_name.message}
                    </p>
                  )}
                </div>
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="password"
                  className="text-xs font-medium text-zinc-300"
                >
                  Password
                </label>
                <div className="relative group">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    id="password"
                    {...form.register('password')}
                    className="w-full bg-zinc-900/50 border border-zinc-800 rounded-md px-3 py-2 pr-10 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-700 focus:border-zinc-700 transition-all shadow-sm"
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

              <div className="space-y-1.5">
                <label
                  htmlFor="confirmPassword"
                  className="text-xs font-medium text-zinc-300"
                >
                  Confirm password
                </label>
                <div className="relative group">
                  <input
                    type={showConfirmPassword ? 'text' : 'password'}
                    id="confirmPassword"
                    {...form.register('confirmPassword')}
                    className="w-full bg-zinc-900/50 border border-zinc-800 rounded-md px-3 py-2 pr-10 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-700 focus:border-zinc-700 transition-all shadow-sm"
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

              {form.formState.errors.root && (
                <p className="text-xs text-red-500">
                  {form.formState.errors.root.message}
                </p>
              )}

              <button
                type="submit"
                disabled={acceptInvitationMutation.isPending}
                className="w-full bg-white text-black hover:bg-zinc-200 font-medium text-sm h-9 rounded-md transition-colors flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(255,255,255,0.1)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {acceptInvitationMutation.isPending ? (
                  <>
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
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
                    Creating account...
                  </>
                ) : (
                  <>
                    Join Team
                    <ArrowRight className="w-4 h-4 opacity-60" />
                  </>
                )}
              </button>
            </form>

            <p className="text-center text-sm text-zinc-500">
              Already have an account?{' '}
              <Link
                to="/login"
                className="text-white hover:text-zinc-200 transition-colors"
              >
                Sign in
              </Link>
            </p>
          </div>

          <div className="flex items-center justify-between text-xs text-zinc-600">
            <p>© 2025 Open Wearables</p>
          </div>
        </div>

        <div className="hidden lg:flex flex-col relative bg-zinc-950/50 overflow-hidden">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[300px] h-[300px] bg-indigo-500/10 rounded-full blur-[80px]" />

          <div className="relative h-full flex flex-col items-center justify-center p-8">
            <div className="w-full max-w-[350px] space-y-6">
              <div className="w-16 h-16 mx-auto bg-zinc-900 border border-zinc-800 rounded-2xl flex items-center justify-center">
                <Users className="w-8 h-8 text-zinc-400" />
              </div>

              <h2 className="text-xl font-medium text-white text-center">
                You've Been Invited
              </h2>
              <p className="text-sm text-zinc-500 text-center">
                A team member has invited you to join their organization on Open
                Wearables. Complete your registration to get started.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
