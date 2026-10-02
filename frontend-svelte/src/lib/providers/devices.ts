import CircleDot from '@lucide/svelte/icons/circle-dot';
import Cpu from '@lucide/svelte/icons/cpu';
import Scale from '@lucide/svelte/icons/scale';
import Smartphone from '@lucide/svelte/icons/smartphone';
import Vibrate from '@lucide/svelte/icons/vibrate';
import Watch from '@lucide/svelte/icons/watch';
import type { Component } from 'svelte';

/** Mirrors backend `DeviceType`; `other` and `unknown` share the generic mark. */
const DEVICES: Record<string, Component> = {
	watch: Watch,
	band: Vibrate,
	ring: CircleDot,
	phone: Smartphone,
	scale: Scale
};

export const deviceIcon = (deviceType: string | null): Component =>
	(deviceType && DEVICES[deviceType]) || Cpu;
