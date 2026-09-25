import type { Line } from '$lib/charts/geometry';
import type { FieldGroup } from '$lib/components/ui/FieldGroups.svelte';
import { componentsOf, rawReading, scoreOf } from './categories';
import type { CategoryScores } from './group';

export type DetailSection = { category: string; lines: Line[]; groups: FieldGroup[] };

/**
 * The day's own curve, for a provider that sampled through it. A provider with
 * one score has a number and nothing to plot.
 */
function dayLines(scores: CategoryScores, labelFor: (provider: string) => string): Line[] {
	return scores.providers
		.filter((reading) => reading.readings > 1)
		.map((reading) => ({
			type: reading.provider,
			label: labelFor(reading.provider),
			unit: '',
			points: reading.all
				.map((score) => ({ at: new Date(score.recorded_at).getTime(), value: scoreOf(score) }))
				.filter((point): point is { at: number; value: number } => point.value !== null)
				.sort((a, b) => a.at - b.at)
		}))
		.filter((line) => line.points.length > 1);
}

/**
 * One column per provider, from the newest reading of the day — a stream's
 * rating changes through it, and the row above says which one held for most.
 */
const dayGroups = (scores: CategoryScores, labelFor: (provider: string) => string): FieldGroup[] =>
	scores.providers.map((reading) => {
		const newest = reading.all[0];
		const raw = rawReading(newest);

		return {
			title: labelFor(reading.provider),
			fields: [...(raw ? [raw] : []), ...componentsOf(newest)]
		};
	});

export const detailSections = (
	categories: CategoryScores[],
	labelFor: (provider: string) => string
): DetailSection[] =>
	categories.map((scores) => ({
		category: scores.category,
		lines: dayLines(scores, labelFor),
		groups: dayGroups(scores, labelFor)
	}));

/** Nothing to draw and nothing to list: a section like that is not rendered. */
export const hasDetail = (section: DetailSection) =>
	section.lines.length > 0 || section.groups.some((group) => group.fields.length > 0);
