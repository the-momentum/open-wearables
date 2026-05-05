import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Eye, EyeOff, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/hooks/use-auth';
import {
  changePasswordSchema,
  type ChangePasswordFormData,
} from '@/lib/validation/auth.schemas';

export function SecuritySettings() {
  const { changePassword, isChangePasswordPending } = useAuth();
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const form = useForm<ChangePasswordFormData>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: {
      current_password: '',
      new_password: '',
      confirm_password: '',
    },
  });

  const onSubmit = (data: ChangePasswordFormData) => {
    changePassword(
      {
        current_password: data.current_password,
        new_password: data.new_password,
        confirm_password: data.confirm_password,
      },
      { onSuccess: () => form.reset() }
    );
  };

  return (
    <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-border/60">
        <h3 className="text-sm font-medium text-foreground">Security</h3>
        <p className="text-xs text-muted-foreground mt-1">
          Update your password to keep your developer account secure.
        </p>
      </div>

      <form onSubmit={form.handleSubmit(onSubmit)} className="p-6 space-y-4">
        <div className="space-y-1.5">
          <Label
            htmlFor="current_password"
            className="text-xs text-foreground/90"
          >
            Current Password
          </Label>
          <div className="relative group">
            <Input
              id="current_password"
              type={showCurrentPassword ? 'text' : 'password'}
              {...form.register('current_password')}
              className="bg-card/40 border-border/60 pr-10"
              placeholder="••••••••"
              autoComplete="current-password"
            />
            <button
              type="button"
              onClick={() => setShowCurrentPassword(!showCurrentPassword)}
              className="absolute inset-y-0 right-3 flex items-center text-muted-foreground hover:text-foreground/90 transition-colors"
              aria-label={
                showCurrentPassword
                  ? 'Hide current password'
                  : 'Show current password'
              }
            >
              {showCurrentPassword ? (
                <EyeOff className="w-4 h-4" />
              ) : (
                <Eye className="w-4 h-4" />
              )}
            </button>
          </div>
          {form.formState.errors.current_password && (
            <p className="text-xs text-[hsl(var(--destructive-muted))]">
              {form.formState.errors.current_password.message}
            </p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="new_password" className="text-xs text-foreground/90">
            New Password
          </Label>
          <div className="relative group">
            <Input
              id="new_password"
              type={showNewPassword ? 'text' : 'password'}
              {...form.register('new_password')}
              className="bg-card/40 border-border/60 pr-10"
              placeholder="At least 8 characters"
              autoComplete="new-password"
            />
            <button
              type="button"
              onClick={() => setShowNewPassword(!showNewPassword)}
              className="absolute inset-y-0 right-3 flex items-center text-muted-foreground hover:text-foreground/90 transition-colors"
              aria-label={
                showNewPassword ? 'Hide new password' : 'Show new password'
              }
            >
              {showNewPassword ? (
                <EyeOff className="w-4 h-4" />
              ) : (
                <Eye className="w-4 h-4" />
              )}
            </button>
          </div>
          {form.formState.errors.new_password && (
            <p className="text-xs text-[hsl(var(--destructive-muted))]">
              {form.formState.errors.new_password.message}
            </p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label
            htmlFor="confirm_password"
            className="text-xs text-foreground/90"
          >
            Confirm New Password
          </Label>
          <div className="relative group">
            <Input
              id="confirm_password"
              type={showConfirmPassword ? 'text' : 'password'}
              {...form.register('confirm_password')}
              className="bg-card/40 border-border/60 pr-10"
              placeholder="Confirm your password"
              autoComplete="new-password"
            />
            <button
              type="button"
              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              className="absolute inset-y-0 right-3 flex items-center text-muted-foreground hover:text-foreground/90 transition-colors"
              aria-label={
                showConfirmPassword
                  ? 'Hide confirm password'
                  : 'Show confirm password'
              }
            >
              {showConfirmPassword ? (
                <EyeOff className="w-4 h-4" />
              ) : (
                <Eye className="w-4 h-4" />
              )}
            </button>
          </div>
          {form.formState.errors.confirm_password && (
            <p className="text-xs text-[hsl(var(--destructive-muted))]">
              {form.formState.errors.confirm_password.message}
            </p>
          )}
        </div>

        <div className="pt-2">
          <Button
            type="submit"
            className="w-full sm:w-auto min-w-[140px]"
            disabled={isChangePasswordPending}
          >
            {isChangePasswordPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Updating...
              </>
            ) : (
              'Update Password'
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
