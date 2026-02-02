import { createFileRoute, redirect, Link } from '@tanstack/react-router';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useAuth } from '@/hooks/use-auth';
import { isAuthenticated } from '@/lib/auth/session';
import {
  registerSchema,
  type RegisterFormData,
} from '@/lib/validation/auth.schemas';
import {
  Activity,
  ArrowRight,
  Mail,
  Eye,
  EyeOff,
  ShieldCheck,
  Zap,
  Bot,
  Loader2,
} from 'lucide-react';
import { DEFAULT_REDIRECTS, ROUTES } from '@/lib/constants/routes';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export const Route = createFileRoute('/register')({
  component: RegisterPage,
  beforeLoad: () => {
    if (typeof window !== 'undefined' && isAuthenticated()) {
      throw redirect({ to: DEFAULT_REDIRECTS.authenticated });
    }
  },
});

function RegisterPage() {
  const { register: registerUser, isRegistering } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const form = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      email: '',
      password: '',
      confirmPassword: '',
    },
  });

  const onSubmit = (data: RegisterFormData) => {
    registerUser({ email: data.email, password: data.password });
  };

  return (
    <div className="bg-black text-zinc-400 antialiased h-screen w-screen overflow-hidden selection:bg-zinc-800 selection:text-white flex items-center justify-center p-4 sm:p-8 relative">
      {/* Background */}
      <div className="absolute inset-0 bg-grid opacity-30" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[400px] bg-indigo-900/20 rounded-full blur-[120px] pointer-events-none" />

      {/* Card Container */}
      <div className="w-full max-w-[1100px] h-full max-h-[700px] grid lg:grid-cols-2 bg-black border border-zinc-900/80 rounded-2xl overflow-hidden shadow-[0_0_50px_-12px_rgba(0,0,0,0.8)] relative z-10 backdrop-blur-sm">
        {/* Left: Form */}
        <div className="flex flex-col justify-between p-8 sm:p-12 border-b lg:border-b-0 lg:border-r border-zinc-900 bg-black/90">
          {/* Logo */}
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-white rounded flex items-center justify-center">
              <Activity className="text-black w-4 h-4" />
            </div>
            <span className="text-sm font-medium text-white tracking-tight uppercase">
              Open Wearables
            </span>
          </div>

          {/* Form */}
          <div className="w-full max-w-sm mx-auto space-y-6 my-auto py-8">
            <div className="space-y-2">
              <h1 className="text-2xl font-medium tracking-tight text-white">
                Create account
              </h1>
              <p className="text-sm text-zinc-500">
                Sign up to start building with Open Wearables
              </p>
            </div>

            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              {/* Email */}
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
                    placeholder="developer@example.com"
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

              {/* Password */}
              <div className="space-y-1.5">
                <Label htmlFor="password" className="text-xs text-zinc-300">
                  Password
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
                  Confirm password
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

              {/* Submit */}
              <Button type="submit" disabled={isRegistering} className="w-full">
                {isRegistering ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Creating account...
                  </>
                ) : (
                  <>
                    Create account
                    <ArrowRight className="w-4 h-4 opacity-60" />
                  </>
                )}
              </Button>
            </form>

            <p className="text-center text-sm text-zinc-500">
              Already have an account?{' '}
              <Link
                to={ROUTES.login}
                className="text-white hover:text-zinc-200 transition-colors"
              >
                Sign in
              </Link>
            </p>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between text-xs text-zinc-600">
            <p>© 2025 Open Wearables</p>
            <div className="flex gap-3">
              <a href="#" className="hover:text-zinc-400 transition-colors">
                Privacy
              </a>
              <a href="#" className="hover:text-zinc-400 transition-colors">
                Terms
              </a>
            </div>
          </div>
        </div>

        {/* Right: Features */}
        <div className="hidden lg:flex flex-col relative bg-zinc-950/50 overflow-hidden">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[300px] h-[300px] bg-indigo-500/10 rounded-full blur-[80px]" />

          <div className="relative h-full flex flex-col items-center justify-center p-8">
            <div className="w-full max-w-[350px] space-y-6">
              <h2 className="text-xl font-medium text-white text-center">
                Start Building Today
              </h2>
              <p className="text-sm text-zinc-500 text-center">
                Create your developer account and integrate health data from any
                wearable device.
              </p>

              <div className="space-y-4 mt-8">
                <div className="flex items-start gap-4 p-4 bg-zinc-900/50 border border-zinc-800 rounded-lg">
                  <div className="w-8 h-8 bg-zinc-800 rounded-lg flex items-center justify-center flex-shrink-0">
                    <Zap className="w-4 h-4 text-zinc-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-medium text-white">
                      Quick Setup
                    </h3>
                    <p className="text-xs text-zinc-500 mt-1">
                      Get started in minutes with our SDK
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-4 p-4 bg-zinc-900/50 border border-zinc-800 rounded-lg">
                  <div className="w-8 h-8 bg-zinc-800 rounded-lg flex items-center justify-center flex-shrink-0">
                    <ShieldCheck className="w-4 h-4 text-zinc-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-medium text-white">
                      Enterprise Ready
                    </h3>
                    <p className="text-xs text-zinc-500 mt-1">
                      SOC 2, HIPAA compliant infrastructure
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-4 p-4 bg-zinc-900/50 border border-zinc-800 rounded-lg">
                  <div className="w-8 h-8 bg-zinc-800 rounded-lg flex items-center justify-center flex-shrink-0">
                    <Bot className="w-4 h-4 text-zinc-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-medium text-white">
                      AI-Powered Insights
                    </h3>
                    <p className="text-xs text-zinc-500 mt-1">
                      Natural language automations and insights
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
