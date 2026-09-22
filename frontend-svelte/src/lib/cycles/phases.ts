import { humanise } from '$lib/utils/text';
import type { Cycle } from './types';

/**
 * The phases a cycle bar is made of, in the order they happen — which is also
 * the order the legend reads. The period is the one colour a reader already
 * expects; the fertile window is marked out because it is what anyone looks for
 * first.
 */
const PHASES: Record<string, { label: string; shade: string }> = {
	menstruation: { label: 'Period', shade: 'bg-danger/70' },
	follicular: { label: 'Follicular', shade: 'bg-primary/30' },
	ovulation: { label: 'Fertile', shade: 'bg-warning/70' },
	luteal: { label: 'Luteal', shade: 'bg-primary/60' }
};

/** A phase a provider can report that is never a span inside a cycle. */
const APART: Record<string, { label: string; shade: string }> = {
	pregnancy: { label: 'Pregnancy', shade: 'bg-primary' }
};

/** Garmin says "menstrual" where the rest of the vocabulary says "menstruation". */
const ALIASES: Record<string, string> = { menstrual: 'menstruation', period: 'menstruation' };

function spec(phase: string) {
	const key = ALIASES[phase] ?? phase;
	return PHASES[key] ?? APART[key];
}

export const phaseLabel = (phase: string | null) =>
	phase ? (spec(phase.toLowerCase())?.label ?? humanise(phase)) : null;

export const phaseShade = (phase: string) => spec(phase)?.shade ?? 'bg-border';

/** Derived, so a phase added above cannot be missed off the legend. */
export const PHASE_ORDER = Object.keys(PHASES);

/** What the cycle ran to, or is expected to: a predicted one has no measured length. */
export const cycleDays = (cycle: Cycle) => cycle.cycle_length ?? cycle.predicted_cycle_length;

/** The days the window covers, inclusive — the bar and the detail column agree. */
export function fertileWindow(cycle: Cycle): { from: number; to: number } | null {
	const from = cycle.fertile_window_start;
	const length = cycle.length_of_fertile_window;
	return from && length ? { from, to: from + length - 1 } : null;
}

export type PhaseSpan = { phase: string; label: string; shade: string; from: number; to: number };

/**
 * The phases laid along the cycle's own days, built from the stored fields
 * rather than from a provider's phase names.
 */
export function phaseSpans(cycle: Cycle): PhaseSpan[] {
	const days = cycleDays(cycle);
	if (!days) return [];

	const period = cycle.period_length ?? 0;
	const fertile = fertileWindow(cycle);
	const bounds: [string, number, number][] = [['menstruation', 1, period]];

	// Follicular and luteal are only what is left either side of the fertile
	// window. Without one there is no honest way to tell them apart, so the track
	// carries the period and stops rather than guessing where they end.
	if (fertile) {
		bounds.push(
			['follicular', period + 1, fertile.from - 1],
			['ovulation', fertile.from, fertile.to],
			['luteal', fertile.to + 1, days]
		);
	}

	return bounds
		.filter(([, from, to]) => from >= 1 && to >= from && to <= days)
		.map(([phase, from, to]) => ({ phase, ...PHASES[phase], from, to }));
}

/**
 * The day the cycle stands on, and only while it is running: a closed cycle's
 * `day_in_cycle` is where it ended, not a place to write "today".
 */
export function currentDay(cycle: Cycle, now = Date.now()): number | null {
	if (cycle.is_predicted_cycle) return null;

	const from = new Date(cycle.start_time).getTime();
	const to = new Date(cycle.end_time).getTime();
	return now >= from && now < to ? cycle.day_in_cycle : null;
}
