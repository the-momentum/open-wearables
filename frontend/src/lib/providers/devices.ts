import Activity from '@lucide/svelte/icons/activity';
import BedDouble from '@lucide/svelte/icons/bed-double';
import Bike from '@lucide/svelte/icons/bike';
import CircleDot from '@lucide/svelte/icons/circle-dot';
import Cpu from '@lucide/svelte/icons/cpu';
import Droplet from '@lucide/svelte/icons/droplet';
import Dumbbell from '@lucide/svelte/icons/dumbbell';
import Gauge from '@lucide/svelte/icons/gauge';
import Glasses from '@lucide/svelte/icons/glasses';
import Headphones from '@lucide/svelte/icons/headphones';
import HeartPulse from '@lucide/svelte/icons/heart-pulse';
import Monitor from '@lucide/svelte/icons/monitor';
import Scale from '@lucide/svelte/icons/scale';
import Smartphone from '@lucide/svelte/icons/smartphone';
import Tablet from '@lucide/svelte/icons/tablet';
import Thermometer from '@lucide/svelte/icons/thermometer';
import Vibrate from '@lucide/svelte/icons/vibrate';
import Watch from '@lucide/svelte/icons/watch';
import type { Component } from 'svelte';
import { humanise } from '$lib/utils/text';

const DEVICES: Record<string, { icon: Component; label: string }> = {
	watch: { icon: Watch, label: 'Watch' },
	band: { icon: Vibrate, label: 'Band' },
	ring: { icon: CircleDot, label: 'Ring' },
	phone: { icon: Smartphone, label: 'Phone' },
	scale: { icon: Scale, label: 'Scale' },
	tablet: { icon: Tablet, label: 'Tablet' },
	chest_strap: { icon: HeartPulse, label: 'Chest strap' },
	hr_sensor: { icon: Activity, label: 'HR sensor' },
	headphones: { icon: Headphones, label: 'Headphones' },
	head_mounted: { icon: Glasses, label: 'Headset' },
	glasses: { icon: Glasses, label: 'Glasses' },
	smart_display: { icon: Monitor, label: 'Smart display' },
	bp_monitor: { icon: Gauge, label: 'BP monitor' },
	glucose_meter: { icon: Droplet, label: 'Glucose meter' },
	thermometer: { icon: Thermometer, label: 'Thermometer' },
	sleep_monitor: { icon: BedDouble, label: 'Sleep monitor' },
	bike_computer: { icon: Bike, label: 'Bike computer' },
	fitness_machine: { icon: Dumbbell, label: 'Fitness machine' },
	other: { icon: Cpu, label: 'Other' },
	unknown: { icon: Cpu, label: 'Unknown' }
};

export const DEVICE_TYPES = Object.keys(DEVICES);

export const deviceIcon = (deviceType: string | null): Component =>
	(deviceType && DEVICES[deviceType]?.icon) || Cpu;

export const deviceLabel = (deviceType: string): string =>
	DEVICES[deviceType]?.label ?? humanise(deviceType);
