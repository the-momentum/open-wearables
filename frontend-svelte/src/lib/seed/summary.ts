import { formatDate } from '$lib/utils/datetime';
import { profileOf, type Draft, type Window } from './draft';
import type { SeedProfile, SleepProfile } from './types';
import { plural } from '$lib/utils/text';

/** Sleep is thought of in hours even though the API counts minutes. */
const hours = (minutes: number) => `${Math.round((minutes / 60) * 10) / 10}`;

export const windowSummary = (window: Window) =>
	'months' in window
		? `last ${plural(window.months, 'month')}`
		: `${formatDate(window.from)} – ${formatDate(window.to)}`;

export function audienceSummary(draft: Draft, labelFor: (slug: string) => string): string {
	const who = plural(draft.users, 'user');
	return draft.providers.length > 0
		? `${who} on ${draft.providers.map(labelFor).join(', ')}`
		: `${who}, ${plural(draft.connections, 'random connection')} each`;
}

export function workoutSummary(workouts: Draft['workouts']): string {
	if (!workouts.on) return 'Not generated';
	const types = workouts.types === null ? 'any type' : plural(workouts.types.length, 'type');
	return `${plural(workouts.count, 'workout')} · ${workouts.duration[0]}–${workouts.duration[1]} min · ${types}`;
}

export function sleepSummary(sleep: Draft['sleep'], profiles: SleepProfile[]): string {
	if (!sleep.on) return 'Not generated';
	const stages =
		profiles.find((profile) => profile.id === sleep.stageProfile)?.label ?? 'custom stages';
	const naps = sleep.napChance > 0 ? ` · ${sleep.napChance}% naps` : '';
	return `${plural(sleep.count, 'night')} · ${hours(sleep.duration[0])}–${hours(sleep.duration[1])} h · ${stages}${naps}`;
}

export function seriesSummary(series: Draft['series']): string {
	if (!series.on) return 'Not generated';
	const types = plural(series.types.length, 'series type');
	return series.bloodPressure ? `${types} + blood pressure` : types;
}

/** What a profile makes for one user, in the counts that tell presets apart. */
export const countsOf = (profile: SeedProfile): string[] =>
	[
		profile.generate_workouts && plural(profile.workout_config.count, 'workout'),
		profile.generate_sleep && plural(profile.sleep_config.count, 'night'),
		profile.generate_time_series &&
			plural(profile.time_series_config.enabled_types.length, 'series type')
	].filter((part): part is string => Boolean(part));

/** The same counts for the draft, for the line above the button. */
export const perUser = (draft: Draft) => countsOf(profileOf(draft, null)).join(', ') || 'nothing';
