import {
  CircleDot,
  HelpCircle,
  Package,
  Scale,
  Smartphone,
  Vibrate,
  Watch,
  type LucideIcon,
} from 'lucide-react';
import type { DeviceType } from '@/lib/api/types';

const DEVICE_TYPE_INFO: Record<
  DeviceType,
  { label: string; Icon: LucideIcon }
> = {
  watch: { label: 'Watch', Icon: Watch },
  band: { label: 'Band', Icon: Vibrate },
  ring: { label: 'Ring', Icon: CircleDot },
  phone: { label: 'Phone', Icon: Smartphone },
  scale: { label: 'Scale', Icon: Scale },
  other: { label: 'Other', Icon: Package },
  unknown: { label: 'Unknown', Icon: HelpCircle },
};

const FALLBACK = { label: 'Unknown', Icon: HelpCircle };

export function deviceTypeInfo(deviceType: DeviceType | string | null) {
  if (!deviceType) return FALLBACK;
  return DEVICE_TYPE_INFO[deviceType as DeviceType] ?? FALLBACK;
}

export function DeviceTypeIcon({
  deviceType,
  className = 'h-3.5 w-3.5',
}: {
  deviceType: DeviceType | string | null;
  className?: string;
}) {
  const { Icon } = deviceTypeInfo(deviceType);
  return <Icon className={className} aria-hidden />;
}
