import { createFileRoute, redirect } from '@tanstack/react-router';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/hooks/use-auth';
import { isAuthenticated } from '@/lib/auth/session';
import { Activity, Zap, Shield, TrendingUp } from 'lucide-react';

export const Route = createFileRoute('/login')({
  component: LoginPage,
  beforeLoad: () => {
    // Skip auth check on server-side rendering
    // Only redirect if authenticated in the browser
    if (typeof window !== 'undefined' && isAuthenticated()) {
      throw redirect({ to: '/dashboard' });
    }
  },
});

function LoginPage() {
  const { login, isLoggingIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [focusedField, setFocusedField] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    login({ email, password });
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
        <div className="w-full max-w-6xl grid lg:grid-cols-2 gap-12 items-center">
          <div className="hidden lg:block space-y-8 text-white">
            <div className="space-y-4">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/10 backdrop-blur-sm border border-white/20">
                <Activity className="w-4 h-4 text-blue-400" />
                <span className="text-sm font-medium">
                  Open Wearables Platform
                </span>
              </div>
              <h1 className="text-5xl font-bold leading-tight">
                Unified Health Data
                <br />
                <span className="bg-gradient-to-r from-blue-400 to-teal-400 bg-clip-text text-transparent">
                  One API
                </span>
              </h1>
              <p className="text-lg text-slate-300 max-w-lg">
                Connect with any wearable device and access health data through
                a single, powerful API platform.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="group p-6 rounded-2xl bg-white/5 backdrop-blur-sm border border-white/10 hover:bg-white/10 transition-all duration-300 hover:scale-105">
                <Zap className="w-8 h-8 text-yellow-400 mb-3" />
                <h3 className="font-semibold mb-1">Lightning Fast</h3>
                <p className="text-sm text-slate-400">
                  Real-time data sync across all devices
                </p>
              </div>
              <div className="group p-6 rounded-2xl bg-white/5 backdrop-blur-sm border border-white/10 hover:bg-white/10 transition-all duration-300 hover:scale-105">
                <Shield className="w-8 h-8 text-green-400 mb-3" />
                <h3 className="font-semibold mb-1">Secure & Private</h3>
                <p className="text-sm text-slate-400">
                  Enterprise-grade security standards
                </p>
              </div>
              <div className="group p-6 rounded-2xl bg-white/5 backdrop-blur-sm border border-white/10 hover:bg-white/10 transition-all duration-300 hover:scale-105 col-span-2">
                <TrendingUp className="w-8 h-8 text-blue-400 mb-3" />
                <h3 className="font-semibold mb-1">Advanced Analytics</h3>
                <p className="text-sm text-slate-400">
                  AI-powered insights from health data
                </p>
              </div>
            </div>
          </div>

          <div className="w-full">
            <div className="lg:hidden mb-8 text-center">
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
                  <div className="space-y-2 mb-8">
                    <h2 className="text-3xl font-bold text-white">
                      Welcome Back
                    </h2>
                    <p className="text-slate-400">
                      Sign in to access your dashboard
                    </p>
                  </div>

                  <form onSubmit={handleLogin} className="space-y-6">
                    <div className="space-y-2">
                      <Label htmlFor="email" className="text-white font-medium">
                        Email Address
                      </Label>
                      <div className="relative">
                        <Input
                          id="email"
                          type="email"
                          placeholder="you@example.com"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          onFocus={() => setFocusedField('email')}
                          onBlur={() => setFocusedField(null)}
                          required
                          className="h-12 bg-white/5 border-white/10 text-white placeholder:text-slate-500 focus:bg-white/10 focus:border-blue-500/50 transition-all duration-300"
                        />
                        {focusedField === 'email' && (
                          <div className="absolute inset-0 -z-10 bg-blue-500/20 blur-xl rounded-lg transition-opacity" />
                        )}
                      </div>
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label
                          htmlFor="password"
                          className="text-white font-medium"
                        >
                          Password
                        </Label>
                        <button
                          type="button"
                          className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
                        >
                          Forgot password?
                        </button>
                      </div>
                      <div className="relative">
                        <Input
                          id="password"
                          type="password"
                          placeholder="••••••••"
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          onFocus={() => setFocusedField('password')}
                          onBlur={() => setFocusedField(null)}
                          required
                          className="h-12 bg-white/5 border-white/10 text-white placeholder:text-slate-500 focus:bg-white/10 focus:border-blue-500/50 transition-all duration-300"
                        />
                        {focusedField === 'password' && (
                          <div className="absolute inset-0 -z-10 bg-blue-500/20 blur-xl rounded-lg transition-opacity" />
                        )}
                      </div>
                    </div>

                    <div className="flex items-center">
                      <input
                        id="remember"
                        type="checkbox"
                        className="w-4 h-4 rounded border-white/20 bg-white/5 text-blue-500 focus:ring-blue-500 focus:ring-offset-0 focus:ring-2"
                      />
                      <label
                        htmlFor="remember"
                        className="ml-2 text-sm text-slate-300"
                      >
                        Remember me for 30 days
                      </label>
                    </div>

                    <Button
                      type="submit"
                      disabled={isLoggingIn}
                      className="w-full h-12 bg-gradient-to-r from-blue-500 to-teal-500 hover:from-blue-600 hover:to-teal-600 text-white font-semibold rounded-xl shadow-lg shadow-blue-500/25 transition-all duration-300 hover:scale-[1.02] hover:shadow-xl hover:shadow-blue-500/40 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 cursor-pointer"
                    >
                      {isLoggingIn ? (
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
                          Signing in...
                        </span>
                      ) : (
                        'Sign In'
                      )}
                    </Button>
                  </form>
                </div>

                <div className="px-8 sm:px-10 py-6 bg-white/5 border-t border-white/10">
                  <p className="text-center text-sm text-slate-400">
                    Don't have an account?{' '}
                    <button className="text-blue-400 hover:text-blue-300 font-medium transition-colors">
                      Contact Sales
                    </button>
                  </p>
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

      <style>{`
        @keyframes gradient {
          0%, 100% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
        }
        .animate-gradient {
          background-size: 200% 200%;
          animation: gradient 3s ease infinite;
        }
        .delay-500 {
          animation-delay: 0.5s;
        }
        .delay-1000 {
          animation-delay: 1s;
        }
      `}</style>
    </div>
  );
}
