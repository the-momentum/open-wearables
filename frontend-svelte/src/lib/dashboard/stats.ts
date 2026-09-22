import Activity from '@lucide/svelte/icons/activity';
import CalendarClock from '@lucide/svelte/icons/calendar-clock';
import Database from '@lucide/svelte/icons/database';
import Users from '@lucide/svelte/icons/users';
import type { Part } from '$lib/components/charts/ShareBar.svelte';
import type { Tone } from '$lib/components/ui/tone';
import { formatCompact, formatNumber } from '$lib/utils/format';
import type { SystemInfo } from './types';

export type Coverage = {
	/** Users with at least one live connection, and the rest. */
	connected: number;
	unconnected: number;
	percent: number;
	/** Of those, the ones wearing more than one thing. */
	multi: number;
	multiPercent: number;
};

const share = (part: number, whole: number) => (whole > 0 ? Math.round((part / whole) * 100) : 0);

/** How much of the user base is actually sending anything. */
export function coverageOf(info: SystemInfo): Coverage {
	const users = info.total_users.count;
	const { users_with_active, users_with_multi_active } = info.connections_coverage;

	return {
		connected: users_with_active,
		unconnected: Math.max(users - users_with_active, 0),
		percent: share(users_with_active, users),
		multi: users_with_multi_active,
		multiPercent: share(users_with_multi_active, users)
	};
}

export type Tile = {
	icon: typeof Users;
	label: string;
	value: string;
	note?: string;
	tone: Tone;
	parts: { label: string; value: string }[];
};

/**
 * Exact where the count is cheap and exact, compact where it is neither: the
 * data-point totals come from a cache that falls back to a planner estimate,
 * and seven digits of an approximation claim a precision it has not got.
 */
export function statTiles(info: SystemInfo): Tile[] {
	const records = info.event_records;
	const coverage = coverageOf(info);

	return [
		{
			icon: Users,
			label: 'Users',
			value: formatNumber(info.total_users.count),
			tone: 'primary',
			parts: [{ label: 'connected', value: formatNumber(coverage.connected) }]
		},
		{
			icon: Activity,
			label: 'Active connections',
			value: formatNumber(info.active_conn.count),
			tone: 'success',
			parts: [{ label: 'users with two or more', value: formatNumber(coverage.multi) }]
		},
		{
			icon: Database,
			label: 'Data points',
			value: formatCompact(info.data_points.count),
			note: 'estimated',
			tone: 'warning',
			parts: [{ label: 'archived', value: formatCompact(info.data_points.archived) }]
		},
		{
			icon: CalendarClock,
			label: 'Event records',
			value: formatCompact(records.count),
			tone: 'muted',
			parts: [
				{ label: 'workouts', value: formatCompact(records.workouts) },
				{ label: 'sleep', value: formatCompact(records.sleep) },
				{ label: 'cycles', value: formatCompact(records.menstrual_cycles) }
			]
		}
	];
}

/** The user base split in two, for one bar. */
export function reachParts(info: SystemInfo): Part[] {
	const coverage = coverageOf(info);

	return [
		{ key: 'connected', label: 'Connected', value: coverage.connected },
		{ key: 'none', label: 'No connection', value: coverage.unconnected, shade: 'bg-border' }
	];
}

/**
 * The event mix. `count` is every category, and only three of them have a field
 * of their own — so whatever is left over is named rather than silently making
 * the parts fail to add up.
 */
export function eventMix(info: SystemInfo): Record<string, number> {
	const { count, workouts, sleep, menstrual_cycles } = info.event_records;
	const other = count - workouts - sleep - menstrual_cycles;

	// Named for the reader, not after the backend's category codes: "Menstrual
	// cycle" truncates in a ranking row on a phone, and these are labels.
	const mix: Record<string, number> = { workouts, sleep, cycles: menstrual_cycles, other };

	return Object.fromEntries(Object.entries(mix).filter(([, value]) => value > 0));
}

/** The providers actually in use, ranked, as the backend already ordered them. */
export const providerUse = (info: SystemInfo): Record<string, number> =>
	Object.fromEntries(
		info.connections_coverage.top_providers.map((entry) => [entry.provider, entry.count])
	);
