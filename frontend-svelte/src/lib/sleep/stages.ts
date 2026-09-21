import { humanise } from '$lib/utils/text';
import type { SleepSession, StageInterval, StageName } from './types';

/**
 * Awake at the top down to deep, the way a hypnogram is read, and the shade
 * deepens with it. `sleeping` and `in_bed` are the coarse stages sent *instead*
 * of a breakdown, so they sit below the real ones and never appear beside them.
 */
const ORDER: { stage: StageName; shade: string }[] = [
	{ stage: 'awake', shade: 'bg-primary/20' },
	{ stage: 'rem', shade: 'bg-primary/45' },
	{ stage: 'light', shade: 'bg-primary/65' },
	{ stage: 'deep', shade: 'bg-primary' },
	{ stage: 'sleeping', shade: 'bg-primary/65' },
	{ stage: 'in_bed', shade: 'bg-primary/20' },
	{ stage: 'unknown', shade: 'bg-border' }
];

export const stageLabel = (stage: StageName) => (stage === 'rem' ? 'REM' : humanise(stage));

export type StageLane = {
	key: StageName;
	label: string;
	shade: string;
	spans: { start: number; end: number; title: string }[];
};

/** One lane per stage that occurs: an empty row only invites the reader to wonder. */
export function stageLanes(
	intervals: StageInterval[],
	describe: (span: StageInterval, seconds: number) => string
): StageLane[] {
	return ORDER.map(({ stage, shade }) => ({
		key: stage,
		label: stageLabel(stage),
		shade,
		spans: intervals
			.filter((interval) => interval.stage === stage)
			.map((interval) => {
				const start = new Date(interval.start_time).getTime();
				const end = new Date(interval.end_time).getTime();
				return { start, end, title: describe(interval, Math.round((end - start) / 1000)) };
			})
	})).filter((lane) => lane.spans.length > 0);
}

/**
 * From the summary rather than the intervals: providers that send no intervals
 * still send these, so the strip is there even when the hypnogram cannot be.
 */
export function stageRows(
	session: SleepSession
): { label: string; seconds: number; shade: string }[] {
	const minutes = session.stages;
	if (!minutes) return [];

	const byStage: Partial<Record<StageName, number | null>> = {
		awake: minutes.awake_minutes,
		rem: minutes.rem_minutes,
		light: minutes.light_minutes,
		deep: minutes.deep_minutes
	};

	return ORDER.filter(({ stage }) => byStage[stage]).map(({ stage, shade }) => ({
		label: stageLabel(stage),
		seconds: (byStage[stage] ?? 0) * 60,
		shade
	}));
}
