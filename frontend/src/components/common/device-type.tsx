import {
  Activity,
  BedDouble,
  Bike,
  CircleDot,
  Droplet,
  Dumbbell,
  Gauge,
  Glasses,
  Headphones,
  HeartPulse,
  HelpCircle,
  Monitor,
  Package,
  Scale,
  Smartphone,
  Tablet,
  Thermometer,
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
  tablet: { label: 'Tablet', Icon: Tablet },
  chest_strap: { label: 'Chest strap', Icon: HeartPulse },
  hr_sensor: { label: 'HR sensor', Icon: Activity },
  headphones: { label: 'Headphones', Icon: Headphones },
  head_mounted: { label: 'Headset', Icon: Glasses },
  glasses: { label: 'Glasses', Icon: Glasses },
  smart_display: { label: 'Smart display', Icon: Monitor },
  bp_monitor: { label: 'BP monitor', Icon: Gauge },
  glucose_meter: { label: 'Glucose meter', Icon: Droplet },
  thermometer: { label: 'Thermometer', Icon: Thermometer },
  sleep_monitor: { label: 'Sleep monitor', Icon: BedDouble },
  bike_computer: { label: 'Bike computer', Icon: Bike },
  fitness_machine: { label: 'Fitness machine', Icon: Dumbbell },
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
