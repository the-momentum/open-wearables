import { SecuritySettings } from '@/components/settings/security/security-settings';

export function SecurityTab() {
  return (
    <div className="space-y-6">
      <div className="max-w-2xl">
        <SecuritySettings />
      </div>
    </div>
  );
}
