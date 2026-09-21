import Flame from '@lucide/svelte/icons/flame';
import Footprints from '@lucide/svelte/icons/footprints';
import HeartPulse from '@lucide/svelte/icons/heart-pulse';
import Mountain from '@lucide/svelte/icons/mountain';
import { toFieldGroups, type GroupSpec } from '$lib/events/fields';
import type { FieldGroup } from '$lib/components/ui/FieldGroups.svelte';
import { formatDistance, formatDuration, formatNumber } from '$lib/utils/format';
import type { ActivityDay } from './types';

const maybe = (value: number | null | undefined, format: (value: number) => string) =>
	value === null || value === undefined ? null : format(value);

const minutes = (value: number | null | undefined) =>
	maybe(value, (mins) => formatDuration(mins * 60));
const bpm = (value: number | null | undefined) =>
	maybe(value, (rate) => formatNumber(rate, ' bpm'));

/**
 * What the card does not already show, grouped by subject. Absent fields are
 * dropped rather than dashed: one dash carries information, a column of them
 * carries none.
 */
export function detailGroups(day: ActivityDay): FieldGroup[] {
	const groups: GroupSpec[] = [
		[
			'Movement',
			Footprints,
			[
				['Active', minutes(day.active_minutes)],
				['Sedentary', minutes(day.sedentary_minutes)]
			]
		],
		[
			'Intensity',
			Flame,
			[
				['Light', minutes(day.intensity_minutes?.light)],
				['Moderate', minutes(day.intensity_minutes?.moderate)],
				['Vigorous', minutes(day.intensity_minutes?.vigorous)]
			]
		],
		[
			'Heart rate',
			HeartPulse,
			[
				['Max', bpm(day.heart_rate?.max_bpm)],
				['Min', bpm(day.heart_rate?.min_bpm)]
			]
		],
		[
			'Elevation',
			Mountain,
			[
				['Floors', maybe(day.floors_climbed, (floors) => formatNumber(floors))],
				['Gain', maybe(day.elevation_meters, formatDistance)]
			]
		],
		[
			// Active energy is on the card; the total is here because the gap between
			// them is basal, and a missing basal series is a real thing to notice.
			'Energy',
			Flame,
			[['Total', maybe(day.total_calories_kcal, (kcal) => formatNumber(kcal, ' kcal'))]]
		]
	];

	return toFieldGroups(groups);
}
