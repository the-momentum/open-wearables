import Clock from '@lucide/svelte/icons/clock';
import HeartPulse from '@lucide/svelte/icons/heart-pulse';
import Mountain from '@lucide/svelte/icons/mountain';
import Zap from '@lucide/svelte/icons/zap';
import type { FieldGroup } from '$lib/components/ui/FieldGroups.svelte';
import { toFieldGroups, type GroupSpec } from '$lib/events/fields';
import { humanise } from '$lib/utils/text';
import {
	formatDistance,
	formatDuration,
	formatLocalTime,
	formatNumber,
	formatPace
} from '$lib/utils/format';
import type { Workout } from './types';

const maybe = (value: number | null, format: (value: number) => string): string | null =>
	value === null ? null : format(value);

const bpm = (value: number) => formatNumber(value, ' bpm');

/**
 * Everything the API carries that the collapsed row does not already show,
 * grouped so a reader scans a subject rather than an alphabet. Absent fields are
 * dropped rather than dashed: on the summary row a dash says "this provider sent
 * nothing", but a dozen of them here would say nothing at all. `average_speed`
 * is deliberately missing — its unit differs per provider.
 */
export function detailGroups(workout: Workout): FieldGroup[] {
	const groups: GroupSpec[] = [
		[
			'Session',
			Clock,
			[
				['Started', formatLocalTime(workout.start_time, workout.zone_offset)],
				['Ended', formatLocalTime(workout.end_time, workout.zone_offset)],
				['Moving time', maybe(workout.moving_time_seconds, formatDuration)],
				['Recorded', workout.entry_source && humanise(workout.entry_source)],
				['Intensity', workout.intensity && humanise(workout.intensity)]
			]
		],
		[
			'Heart rate',
			HeartPulse,
			[
				['Max', maybe(workout.max_heart_rate_bpm, bpm)],
				['Min', maybe(workout.heart_rate_min, bpm)]
			]
		],
		[
			'Movement',
			Zap,
			[
				['Pace', maybe(workout.avg_pace_sec_per_km, formatPace)],
				['Steps', maybe(workout.steps_count, (value) => formatNumber(value))],
				['Cadence', maybe(workout.average_cadence, (value) => formatNumber(value, ' rpm'))],
				['Avg power', maybe(workout.average_watts, (value) => formatNumber(value, ' W'))],
				['Max power', maybe(workout.max_watts, (value) => formatNumber(value, ' W'))]
			]
		],
		[
			'Elevation',
			Mountain,
			[
				['Gain', maybe(workout.elevation_gain_meters, formatDistance)],
				['Highest', maybe(workout.elev_high, formatDistance)],
				['Lowest', maybe(workout.elev_low, formatDistance)]
			]
		]
	];

	return toFieldGroups(groups);
}
