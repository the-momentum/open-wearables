import BedDouble from '@lucide/svelte/icons/bed-double';
import Gauge from '@lucide/svelte/icons/gauge';
import { maybe, toFieldGroups, type GroupSpec } from '$lib/events/fields';
import type { FieldGroup } from '$lib/components/ui/FieldGroups.svelte';
import { formatDuration, formatNumber } from '$lib/utils/format';
import type { SleepSession } from './types';

/**
 * What the card does not already show, grouped by subject. The kind is the
 * card's title and the range sits under it, so neither is repeated here. Absent
 * fields are dropped rather than dashed: one dash carries information, a column
 * of them carries none.
 */
export function detailGroups(session: SleepSession): FieldGroup[] {
	const groups: GroupSpec[] = [
		[
			'In bed',
			BedDouble,
			[
				['Time in bed', maybe(session.time_in_bed_seconds, formatDuration)],
				['Recorded span', formatDuration(session.duration_seconds)]
			]
		],
		[
			'Quality',
			Gauge,
			[
				['Asleep', maybe(session.sleep_duration_seconds, formatDuration)],
				['Efficiency', maybe(session.efficiency_percent, (value) => formatNumber(value, '%'))]
			]
		]
	];

	return toFieldGroups(groups);
}
