import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { authService } from '@/lib/api/services/auth.service';
import type { ChangePasswordRequest } from '@/lib/api/types';

const passwordChangeSchema = z
  .object({
    current_password: z.string().min(1, 'Current password is required'),
    new_password: z.string().min(1, 'New password is required'),
    confirm_password: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

type PasswordChangeForm = z.infer<typeof passwordChangeSchema>;

export function SecuritySettings() {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<PasswordChangeForm>({
    resolver: zodResolver(passwordChangeSchema),
  });

  const mutation = useMutation({
    mutationFn: (data: ChangePasswordRequest) =>
      authService.changePassword(data),
    onSuccess: () => {
      toast.success('Password updated successfully');
      reset();
    },
    onError: (error: any) => {
      const detail =
        error.response?.data?.detail || 'Failed to update password';
      toast.error(detail);
    },
  });

  return (
    <div className="rounded-xl border border-border/50 bg-card/30 overflow-hidden shadow-sm">
      <div className="px-6 py-5 border-b border-border/50 bg-card/50">
        <h3 className="text-lg font-semibold text-white">Security</h3>
        <p className="text-sm text-zinc-400 mt-1">
          Update your password to keep your developer account secure.
        </p>
      </div>

      <form
        onSubmit={handleSubmit((data) => mutation.mutate(data))}
        className="p-6 space-y-5"
      >
        <div className="space-y-2">
          <Label htmlFor="current_password">Current Password</Label>
          <Input
            {...register('current_password')}
            id="current_password"
            type="password"
            placeholder="••••••••"
            autoComplete="current-password"
          />
          {errors.current_password && (
            <p className="text-xs font-medium text-red-400 mt-1">
              {errors.current_password.message}
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="new_password">New Password</Label>
          <Input
            {...register('new_password')}
            id="new_password"
            type="password"
            placeholder="••••••••"
            autoComplete="new-password"
          />
          {errors.new_password && (
            <p className="text-xs font-medium text-red-400 mt-1">
              {errors.new_password.message}
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="confirm_password">Confirm New Password</Label>
          <Input
            {...register('confirm_password')}
            id="confirm_password"
            type="password"
            placeholder="••••••••"
            autoComplete="new-password"
          />
          {errors.confirm_password && (
            <p className="text-xs font-medium text-red-400 mt-1">
              {errors.confirm_password.message}
            </p>
          )}
        </div>

        <div className="pt-2">
          <Button
            type="submit"
            variant="neon"
            className="w-full sm:w-auto min-w-[140px]"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? 'Updating...' : 'Update Password'}
          </Button>
        </div>
      </form>
    </div>
  );
}
