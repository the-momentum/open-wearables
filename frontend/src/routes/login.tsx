import { createFileRoute, redirect } from '@tanstack/react-router';
import { useState } from 'react';
import { useAuth } from '@/hooks/use-auth';
import { isAuthenticated } from '@/lib/auth/session';
import { ArrowRight, Mail, Lock, Loader2 } from 'lucide-react';
import logotype from '@/logotype.svg';
import { CodePreviewCard } from '@/components/login/code-preview-card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export const Route = createFileRoute('/login')({
  component: LoginPage,
  beforeLoad: () => {
    if (typeof window !== 'undefined' && isAuthenticated()) {
      throw redirect({ to: '/users' });
    }
  },
});

function LoginPage() {
  const { login, isLoggingIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

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
          <img src={logotype} alt="Open Wearables" className="h-30" />

          {/* Main Form Container */}
          <div className="w-full max-w-sm mx-auto space-y-6 my-auto py-8">
            <div className="space-y-2">
              <h1 className="text-2xl font-medium tracking-tight text-white">
                Welcome back
              </h1>
              <p className="text-sm text-zinc-500">
                Sign in to access dashboard, users, and settings.
              </p>
            </div>

            <form className="space-y-4" onSubmit={handleLogin}>
              {/* Email Input */}
              <div className="space-y-1.5">
                <Label htmlFor="email" className="text-xs text-zinc-300">
                  Email address
                </Label>
                <div className="relative group">
                  <Input
                    type="email"
                    id="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="bg-zinc-900/50 border-zinc-800 pr-10"
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
                <Label htmlFor="password" className="text-xs text-zinc-300">
                  Password
                </Label>
                <div className="relative group">
                  <Input
                    type="password"
                    id="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="bg-zinc-900/50 border-zinc-800 pr-10"
                    placeholder="••••••••"
                    required
                  />
                  <div className="absolute inset-y-0 right-3 flex items-center pointer-events-none opacity-0 group-focus-within:opacity-100 transition-opacity">
                    <Lock className="w-4 h-4 text-zinc-500" />
                  </div>
                </div>
              </div>

              {/* Submit Button */}
              <Button type="submit" disabled={isLoggingIn} className="w-full">
                {isLoggingIn ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Signing in...
                  </>
                ) : (
                  <>
                    Sign in
                    <ArrowRight className="w-4 h-4 opacity-60" />
                  </>
                )}
              </Button>
            </form>
          </div>

          {/* Footer Links */}
          <div className="flex items-center text-xs text-zinc-600">
            <p>© 2025 Open Wearables</p>
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
