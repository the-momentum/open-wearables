import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Building2, Check, Sparkles, User } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { authService } from '@/lib/api';
import { isAuthenticated } from '@/lib/auth/session';
import { queryKeys } from '@/lib/query/keys';
import { cn } from '@/lib/utils';

// Shown once per developer: the first time they open the dashboard and until
// they close it. Closing (skip or submit) is recorded on the developer via
// PATCH /auth/me, so it stays dismissed across devices and browsers.
// TODO: answers are not sent anywhere yet, only logged.

type UsageType = 'individual' | 'professional';

const OPTIONS: {
  value: UsageType;
  title: string;
  description: string;
  icon: typeof User;
}[] = [
  {
    value: 'individual',
    title: 'Individual',
    description: 'Personal project, tracking my own health data',
    icon: User,
  },
  {
    value: 'professional',
    title: 'Professional',
    description: 'Building a product or using it at a company',
    icon: Building2,
  },
];

const PROFESSIONAL_SERVICES = [
  'Deploying Open Wearables in your infrastructure',
  'Integrating wearable data into your product',
  'Health insights built on top of wearable data',
];

const TELEMETRY_DOCS_URL = 'https://docs.openwearables.io/dev-guides/telemetry';

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function UsageSurveyDialog() {
  const queryClient = useQueryClient();
  const { data: developer } = useQuery({
    queryKey: queryKeys.auth.session(),
    queryFn: () => authService.me(),
    enabled: isAuthenticated(),
  });
  // Local override so the dialog closes instantly, before the PATCH returns.
  const [dismissed, setDismissed] = useState(false);
  const open =
    !dismissed &&
    developer !== undefined &&
    developer.welcome_dialog_seen_at === null;

  const markSeen = useMutation({
    mutationFn: () =>
      authService.updateMe({
        welcome_dialog_seen_at: new Date().toISOString(),
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.auth.session(), updated);
    },
  });

  const close = () => {
    setDismissed(true);
    // Best effort: if this fails the dialog simply shows again next time.
    markSeen.mutate();
  };
  const [usageType, setUsageType] = useState<UsageType | null>(null);
  const [email, setEmail] = useState('');
  const [touched, setTouched] = useState(false);
  const [wantsContact, setWantsContact] = useState(false);

  const emailValid = EMAIL_REGEX.test(email.trim());
  const canSubmit = usageType !== null && emailValid;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!canSubmit) return;
    console.info('[usage-survey]', {
      usageType,
      email: email.trim(),
      wantsContact: usageType === 'professional' && wantsContact,
    });
    toast.success('Thanks! We will keep you posted.');
    close();
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !next && close()}>
      <DialogContent className="max-w-md">
        <form onSubmit={handleSubmit} className="grid gap-5">
          <DialogHeader>
            <DialogTitle>Welcome to Open Wearables</DialogTitle>
            <DialogDescription>
              Tell us a bit about yourself so we can shape Open Wearables around
              what you're building. It takes 10 seconds.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-2">
            <Label>How are you using Open Wearables?</Label>
            <div className="grid gap-2 sm:grid-cols-2">
              {OPTIONS.map((option) => {
                const selected = usageType === option.value;
                const Icon = option.icon;
                return (
                  <button
                    key={option.value}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => setUsageType(option.value)}
                    className={cn(
                      'relative flex flex-col items-start gap-1.5 rounded-lg border p-3 text-left transition-colors',
                      selected
                        ? 'border-primary bg-primary/10'
                        : 'border-border/60 hover:border-border hover:bg-muted/50'
                    )}
                  >
                    <span
                      className={cn(
                        'absolute right-3 top-3 flex h-4 w-4 items-center justify-center rounded border',
                        selected
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-muted-foreground/40'
                      )}
                    >
                      {selected && <Check className="h-3 w-3" />}
                    </span>
                    <Icon className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium text-foreground">
                      {option.title}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {option.description}
                    </span>
                  </button>
                );
              })}
            </div>
            {touched && usageType === null && (
              <p className="text-xs text-destructive">Please pick one.</p>
            )}
            {usageType === 'professional' && (
              <div className="mt-1 grid gap-2.5 rounded-lg border border-border/60 bg-muted/30 p-3">
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <Sparkles className="h-4 w-4 text-primary" />
                  Need a hand? The team behind Open Wearables can help with:
                </div>
                <ul className="grid gap-1 pl-6 text-xs text-muted-foreground">
                  {PROFESSIONAL_SERVICES.map((service) => (
                    <li key={service} className="list-disc">
                      {service}
                    </li>
                  ))}
                </ul>
                <label className="flex cursor-pointer items-center gap-2 text-xs text-foreground">
                  <input
                    type="checkbox"
                    checked={wantsContact}
                    onChange={(e) => setWantsContact(e.target.checked)}
                    className="h-3.5 w-3.5 accent-primary"
                  />
                  I'd like to hear more - reach out to me
                </label>
              </div>
            )}
          </div>

          <div className="grid gap-2">
            <Label htmlFor="usage-survey-email">Email</Label>
            <p className="text-xs text-muted-foreground">
              Be the first to hear about new providers, features and releases.
              Occasional updates only - no spam, unsubscribe anytime.
            </p>
            <Input
              id="usage-survey-email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            {touched && !emailValid && (
              <p className="text-xs text-destructive">
                Please enter a valid email.
              </p>
            )}
          </div>

          <p className="text-xs leading-relaxed text-muted-foreground">
            Privacy is a priority for us. Open Wearables collects anonymous
            telemetry, limited to what helps us improve the product - never your
            users' health data.{' '}
            <a
              href={TELEMETRY_DOCS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2 hover:text-foreground"
            >
              Learn what we collect and how to turn it off
            </a>
            .
          </p>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="ghost" onClick={close}>
              Skip
            </Button>
            <Button type="submit">Continue</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
