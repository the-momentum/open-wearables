import BedDouble from '@lucide/svelte/icons/bed-double';
import Gauge from '@lucide/svelte/icons/gauge';
import type { Component } from 'svelte';
import type { FieldGroup } from '$lib/components/ui/FieldGroups.svelte';
import { formatDuration, formatNumber } from '$lib/utils/format';
import type { SleepSession } from './types';

const maybe = (value: number | null, format: (value: number) => string): string | null =>
	value === null ? null : format(value);

/**
 * What the card does not already show, grouped by subject. The kind is the
 * card's title and the range sits under it, so neither is repeated here. Absent
 * fields are dropped rather than dashed: one dash carries information, a column
 * of them carries none.
 */
export function detailGroups(session: SleepSession): FieldGroup[] {
	const groups: [string, Component, [string, string | null][]][] = [
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

	return groups
		.map(([title, icon, entries]) => ({
			title,
			icon,
			fields: entries
				.filter((entry): entry is [string, string] => entry[1] !== null)
				.map(([label, value]) => ({ label, value }))
		}))
		.filter((group) => group.fields.length > 0);
}
