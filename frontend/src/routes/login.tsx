import { createFileRoute, redirect, Link } from '@tanstack/react-router';
import { useState } from 'react';
import { useAuth } from '@/hooks/use-auth';
import { isAuthenticated } from '@/lib/auth/session';
import {
  Activity,
  ArrowRight,
  Mail,
  Lock,
  Check,
  Github,
  Chrome,
} from 'lucide-react';
import { CodePreviewCard } from '@/components/login/code-preview-card';

export const Route = createFileRoute('/login')({
  component: LoginPage,
  beforeLoad: () => {
    if (typeof window !== 'undefined' && isAuthenticated()) {
      throw redirect({ to: '/dashboard' });
    }
  },
});

function LoginPage() {
  const { login, isLoggingIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberDevice, setRememberDevice] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    login({ email, password });
  };

  return (
    <div className="bg-black text-zinc-400 antialiased h-screen w-screen overflow-hidden selection:bg-zinc-800 selection:text-white flex items-center justify-center p-4 sm:p-8 relative">
      {/* Global Background Elements */}
      <div className="absolute inset-0 bg-grid opacity-30" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[400px] bg-indigo-900/20 rounded-full blur-[120px] pointer-events-none" />

      {/* Centered Card Container */}
      <div className="w-full max-w-[1100px] h-full max-h-[700px] grid lg:grid-cols-2 bg-black border border-zinc-900/80 rounded-2xl overflow-hidden shadow-[0_0_50px_-12px_rgba(0,0,0,0.8)] relative z-10 backdrop-blur-sm">
        {/* Left Section: Login Form */}
        <div className="flex flex-col justify-between p-8 sm:p-12 border-b lg:border-b-0 lg:border-r border-zinc-900 bg-black/90">
          {/* Header/Logo */}
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-white rounded flex items-center justify-center">
              <Activity className="text-black w-4 h-4" />
            </div>
            <span className="text-sm font-medium text-white tracking-tight uppercase">
              Open Wearables
            </span>
          </div>

          {/* Main Form Container */}
          <div className="w-full max-w-sm mx-auto space-y-6 my-auto py-8">
            <div className="space-y-2">
              <h1 className="text-2xl font-medium tracking-tight text-white">
                Welcome back
              </h1>
              <p className="text-sm text-zinc-500">
                Enter your credentials to access your unified API keys.
              </p>
            </div>

            <form className="space-y-4" onSubmit={handleLogin}>
              {/* Email Input */}
              <div className="space-y-1.5">
                <label
                  htmlFor="email"
                  className="text-xs font-medium text-zinc-300"
                >
                  Email address
                </label>
                <div className="relative group">
                  <input
                    type="email"
                    id="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full bg-zinc-900/50 border border-zinc-800 rounded-md px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-700 focus:border-zinc-700 transition-all shadow-sm"
                    placeholder="developer@example.com"
                    required
                  />
                  <div className="absolute inset-y-0 right-3 flex items-center pointer-events-none opacity-0 group-focus-within:opacity-100 transition-opacity">
                    <Mail className="w-4 h-4 text-zinc-500" />
                  </div>
                </div>
              </div>

              {/* Password Input */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="password"
                    className="text-xs font-medium text-zinc-300"
                  >
                    Password
                  </label>
                  <Link
                    to="/forgot-password"
                    className="text-xs text-zinc-500 hover:text-white transition-colors"
                  >
                    Forgot password?
                  </Link>
                </div>
                <div className="relative group">
                  <input
                    type="password"
                    id="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full bg-zinc-900/50 border border-zinc-800 rounded-md px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-700 focus:border-zinc-700 transition-all shadow-sm"
                    placeholder="••••••••"
                    required
                  />
                  <div className="absolute inset-y-0 right-3 flex items-center pointer-events-none opacity-0 group-focus-within:opacity-100 transition-opacity">
                    <Lock className="w-4 h-4 text-zinc-500" />
                  </div>
                </div>
              </div>

              {/* Custom Checkbox */}
              <label className="flex items-center gap-2 cursor-pointer group">
                <div className="relative flex items-center">
                  <input
                    type="checkbox"
                    checked={rememberDevice}
                    onChange={(e) => setRememberDevice(e.target.checked)}
                    className="peer sr-only"
                  />
                  <div className="w-4 h-4 border border-zinc-700 rounded bg-zinc-900 peer-checked:bg-white peer-checked:border-white transition-all" />
                  <Check className="absolute w-3 h-3 text-black opacity-0 peer-checked:opacity-100 top-0.5 left-0.5 pointer-events-none transition-opacity" />
                </div>
                <span className="text-xs text-zinc-500 group-hover:text-zinc-400 transition-colors">
                  Remember device for 30 days
                </span>
              </label>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isLoggingIn}
                className="w-full bg-white text-black hover:bg-zinc-200 font-medium text-sm h-9 rounded-md transition-colors flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(255,255,255,0.1)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoggingIn ? (
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
                    Signing in...
                  </>
                ) : (
                  <>
                    Sign in
                    <ArrowRight className="w-4 h-4 opacity-60" />
                  </>
                )}
              </button>
            </form>

            {/* Divider */}
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-zinc-800" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-black px-2 text-zinc-600">
                  Or continue with
                </span>
              </div>
            </div>

            {/* Social Login Buttons */}
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                className="flex items-center justify-center gap-2 bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 hover:border-zinc-700 text-white text-xs font-medium h-9 rounded-md transition-all"
              >
                <Github className="w-3.5 h-3.5" />
                GitHub
              </button>
              <button
                type="button"
                className="flex items-center justify-center gap-2 bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 hover:border-zinc-700 text-white text-xs font-medium h-9 rounded-md transition-all"
              >
                <Chrome className="w-3.5 h-3.5" />
                Google
              </button>
            </div>
          </div>

          {/* Footer Links */}
          <div className="flex items-center justify-between text-xs text-zinc-600">
            <p>© 2025 Open Wearables</p>
            <div className="flex gap-3">
              <a href="#" className="hover:text-zinc-400 transition-colors">
                Privacy
              </a>
              <Link
                to="/register"
                className="text-white hover:text-zinc-200 transition-colors"
              >
                Sign up
              </Link>
            </div>
          </div>
        </div>

        {/* Right Section: Visuals/Context */}
        <div className="hidden lg:flex flex-col relative bg-zinc-950/50 overflow-hidden">
          {/* Inner Glow */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[300px] h-[300px] bg-indigo-500/10 rounded-full blur-[80px]" />
          <CodePreviewCard />
        </div>
      </div>
    </div>
  );
}
