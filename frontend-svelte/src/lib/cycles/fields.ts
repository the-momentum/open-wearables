import CalendarDays from '@lucide/svelte/icons/calendar-days';
import Droplet from '@lucide/svelte/icons/droplet';
import Sparkles from '@lucide/svelte/icons/sparkles';
import UserPen from '@lucide/svelte/icons/user-pen';
import { maybe, toFieldGroups, type GroupSpec } from '$lib/events/fields';
import type { FieldGroup } from '$lib/components/ui/FieldGroups.svelte';
import { formatDays, formatLocalDay } from '$lib/utils/format';
import { fertileWindow, phaseLabel } from './phases';
import type { Cycle } from './types';

const days = (value: number | null) => maybe(value, formatDays);
const onDay = (value: number | null) => maybe(value, (day) => `Day ${day}`);

/** Whether a length is the person's own word or the provider's guess. */
const lengthFrom = (value: boolean | null) =>
	maybe(value, (specified) => (specified ? 'The user' : 'Estimated'));

/** What the bar cannot say: where the snapshot caught the cycle, and who said so. */
export function detailGroups(cycle: Cycle): FieldGroup[] {
	const fertile = fertileWindow(cycle);

	const groups: GroupSpec[] = [
		[
			'Cycle',
			CalendarDays,
			[
				['Length', days(cycle.cycle_length)],
				// Only where it says something the measured length does not: a
				// forecast repeating the fact is a row carrying nothing.
				[
					'Predicted length',
					cycle.predicted_cycle_length === cycle.cycle_length
						? null
						: days(cycle.predicted_cycle_length)
				]
			]
		],
		[
			'Period',
			Droplet,
			[
				['Length', days(cycle.period_length)],
				['Fertile window', maybe(fertile, ({ from, to }) => `Day ${from}–${to}`)]
			]
		],
		[
			// The snapshot: a provider sends where the cycle stood when it last
			// looked, which for a closed cycle is where it ended.
			'At last update',
			Sparkles,
			[
				['Phase', phaseLabel(cycle.current_phase_type)],
				['Cycle day', onDay(cycle.day_in_cycle)],
				['Phase length', days(cycle.length_of_current_phase)],
				['Next phase in', days(cycle.days_until_next_phase)],
				['Updated', maybe(cycle.last_updated_at, (at) => formatLocalDay(at, cycle.zone_offset))]
			]
		],
		[
			// Whether the lengths above are the person's own or the provider's
			// guess, which is the difference between a record and an estimate.
			'Where lengths came from',
			UserPen,
			[
				['Cycle length', lengthFrom(cycle.has_specified_cycle_length)],
				['Period length', lengthFrom(cycle.has_specified_period_length)]
			]
		]
	];

	return toFieldGroups(groups);
}
