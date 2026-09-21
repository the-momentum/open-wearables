import Activity from '@lucide/svelte/icons/activity';
import Droplet from '@lucide/svelte/icons/droplet';
import HeartPulse from '@lucide/svelte/icons/heart-pulse';
import Percent from '@lucide/svelte/icons/percent';
import Ruler from '@lucide/svelte/icons/ruler';
import Scale from '@lucide/svelte/icons/scale';
import Thermometer from '@lucide/svelte/icons/thermometer';
import Wind from '@lucide/svelte/icons/wind';
import type { Component } from 'svelte';
import { toFieldGroups, type GroupSpec } from '$lib/events/fields';
import type { FieldGroup } from '$lib/components/ui/FieldGroups.svelte';
import { formatDateTime } from '$lib/utils/datetime';
import { DASH, formatDecimal, showDecimal } from '$lib/utils/format';
import type { BodySummary } from './types';

const unit = (value: number | null, suffix: string, digits = 1) => {
	const shown = formatDecimal(value, digits);
	return shown === null ? null : `${shown} ${suffix}`;
};

export type Figure = { icon: Component; label: string; value: string };

/**
 * The body as it stands. Dashes rather than omissions here: this is a fixed
 * shape, and "no weight on record" is one of the things an admin opens the tab
 * to find out.
 */
export function composition(body: BodySummary): Figure[] {
	const slow = body.slow_changing;

	return [
		{ icon: Scale, label: 'Weight', value: unit(slow.weight_kg, 'kg') ?? DASH },
		{ icon: Ruler, label: 'Height', value: unit(slow.height_cm, 'cm', 0) ?? DASH },
		{ icon: Percent, label: 'Body fat', value: unit(slow.body_fat_percent, '%') ?? DASH },
		{ icon: Activity, label: 'BMI', value: showDecimal(slow.bmi) }
	];
}

/** Everything else the summary carries, dropped where nothing arrived. */
export function bodyGroups(body: BodySummary): FieldGroup[] {
	const { slow_changing: slow, averaged, latest } = body;

	const groups: GroupSpec[] = [
		[
			`Averaged over ${averaged.period_days} days`,
			HeartPulse,
			[
				['Resting HR', unit(averaged.resting_heart_rate_bpm, 'bpm', 0)],
				['HRV (RMSSD)', unit(averaged.avg_hrv_rmssd_ms, 'ms')],
				['HRV (SDNN)', unit(averaged.avg_hrv_sdnn_ms, 'ms')]
			]
		],
		[
			'Composition',
			Scale,
			[
				['Muscle mass', unit(slow.muscle_mass_kg, 'kg')],
				['Age', slow.age === null ? null : `${slow.age}`]
			]
		],
		[
			// Withheld unless recent, so each one carries when it was taken: a
			// temperature with no timestamp is a number nobody can act on.
			'Recent readings',
			Thermometer,
			[
				['Body temp', unit(latest.body_temperature_celsius, '°C')],
				[
					'Measured',
					latest.body_temperature_measured_at && formatDateTime(latest.body_temperature_measured_at)
				],
				['Skin temp', unit(latest.skin_temperature_celsius, '°C')]
			]
		],
		[
			'Blood pressure',
			Droplet,
			[
				[
					'Reading',
					latest.blood_pressure?.systolic && latest.blood_pressure?.diastolic
						? `${Math.round(latest.blood_pressure.systolic)}/${Math.round(latest.blood_pressure.diastolic)} mmHg`
						: null
				],
				[
					'Measured',
					latest.blood_pressure_measured_at && formatDateTime(latest.blood_pressure_measured_at)
				]
			]
		]
	];

	return toFieldGroups(groups);
}

/** Label, unit and icon for each vital that gets its own trend. */
export const VITALS: Record<string, { label: string; icon: Component; digits: number }> = {
	resting_heart_rate: { label: 'Resting heart rate', icon: HeartPulse, digits: 0 },
	heart_rate_variability_rmssd: { label: 'HRV (RMSSD)', icon: Activity, digits: 0 },
	oxygen_saturation: { label: 'Blood oxygen', icon: Droplet, digits: 1 },
	respiratory_rate: { label: 'Respiratory rate', icon: Wind, digits: 1 },
	vo2_max: { label: 'VO2 max', icon: Activity, digits: 1 },
	weight: { label: 'Weight', icon: Scale, digits: 1 },
	body_fat_percentage: { label: 'Body fat', icon: Percent, digits: 1 }
};
