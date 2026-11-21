import Activity from '@lucide/svelte/icons/activity';
import CalendarClock from '@lucide/svelte/icons/calendar-clock';
import Database from '@lucide/svelte/icons/database';
import Users from '@lucide/svelte/icons/users';
import type { Part } from '$lib/components/charts/ShareBar.svelte';
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

type Figure = { label: string; value: string; exact?: string };

export type Tile = Figure & {
	icon: typeof Users;
	note?: string;
	parts: Figure[];
};

/** Compact, with the whole figure behind it wherever compacting changed what it says. */
function compact(label: string, count: number): Figure {
	const value = formatCompact(count);
	const whole = formatNumber(count);
	return whole === value ? { label, value } : { label, value, exact: whole };
}

/**
 * Exact where the count is cheap and exact, compact where it is neither: the
 * data-point totals come from a cache that falls back to a planner estimate,
 * and seven digits of an approximation claim a precision it has not got - so
 * those keep no exact figure behind them either. Event records are a true count,
 * compacted only to fit, and give the whole one on hover.
 */
export function statTiles(info: SystemInfo): Tile[] {
	const { count, workouts, sleep, menstrual_cycles } = info.event_records;
	const coverage = coverageOf(info);
	// `count` sums every category and only three have a field of their own; the
	// rest (meals, activity, ...) is named so the parts add up to the whole.
	const other = Math.max(count - workouts - sleep - menstrual_cycles, 0);

	return [
		{
			icon: Users,
			label: 'Users',
			value: formatNumber(info.total_users.count),
			parts: [{ label: 'connected', value: formatNumber(coverage.connected) }]
		},
		{
			icon: Activity,
			label: 'Active connections',
			value: formatNumber(info.active_conn.count),
			parts: [{ label: 'users with two or more', value: formatNumber(coverage.multi) }]
		},
		{
			icon: Database,
			label: 'Data points',
			value: formatCompact(info.data_points.count),
			note: 'estimated',
			parts: [{ label: 'day and session rows', value: formatCompact(info.data_points.aggregated) }]
		},
		{
			icon: CalendarClock,
			...compact('Event records', count),
			parts: [
				compact('workouts', workouts),
				compact('sleep', sleep),
				compact('cycles', menstrual_cycles),
				compact('other', other)
			]
		}
	];
}

/** The user base split in two, for one bar. */
export function reachParts(info: SystemInfo): Part[] {
	const coverage = coverageOf(info);

	return [
		{ key: 'connected', label: 'Connected', value: coverage.connected, shade: 'bg-primary-soft' },
		{
			key: 'none',
			label: 'No connection',
			value: coverage.unconnected,
			shade: 'bg-surface-hover'
		}
	];
}

/** The providers actually in use, ranked, as the backend already ordered them. */
export const providerUse = (info: SystemInfo, labelFor: (provider: string) => string): Part[] =>
	info.connections_coverage.top_providers.map((entry) => ({
		key: entry.provider,
		label: labelFor(entry.provider),
		value: entry.count
	}));
