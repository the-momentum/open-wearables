/**
 * Month steps a calendar axis may take, each lining up with the calendar:
 * months, quarters, halves, then years in 1-2-5 steps without end. "All time"
 * has no upper bound, so neither may this.
 */
function* steps() {
	yield* [1, 2, 3, 6];
	for (let decade = 1; ; decade *= 10) yield* [12 * decade, 24 * decade, 60 * decade];
}

/** Space a label needs: Switzer at 12px runs about 6.5px a character. */
const CHAR_PX = 6.5;
const GAP_PX = 10;

const month = new Intl.DateTimeFormat('en-GB', { month: 'short', timeZone: 'UTC' });

/** `at` runs from 0 at the axis start to 1 at its end. */
export type Tick = { at: number; label: string };

/** Whether each label ends before the next one starts, on an axis `width` px wide. */
export function ticksClear(ticks: Tick[], width: number): boolean {
	return ticks.every(
		(tick, rank) =>
			rank === ticks.length - 1 ||
			(ticks[rank + 1].at - tick.at) * width >= tick.label.length * CHAR_PX + GAP_PX
	);
}

/** The first of every month from `from` (inclusive) to `to` (exclusive), UTC. */
function monthStarts(from: number, to: number): Date[] {
	const at = new Date(from);
	at.setUTCHours(0, 0, 0, 0);
	if (at.getUTCDate() !== 1 || at.getTime() < from) at.setUTCMonth(at.getUTCMonth() + 1, 1);

	const starts: Date[] = [];
	for (; at.getTime() < to; at.setUTCMonth(at.getUTCMonth() + 1)) starts.push(new Date(at));
	return starts;
}

const labelOf = (start: Date, step: number, first: boolean) => {
	const year = String(start.getUTCFullYear());
	if (step >= 12) return year;
	return first || start.getUTCMonth() === 0
		? `${month.format(start)} ${year}`
		: month.format(start);
};

/**
 * Month starts to label on a time axis from `from` to `to` (epoch ms) drawn
 * `width` px wide. Each sits where its date falls rather than on the bucket it
 * lands in: snapped to weeks, a five-Monday month stood a fifth wider than the
 * rest. Takes the finest step whose labels all clear each other, so density
 * follows the room there is, not the length of the period.
 */
export function calendarTicks(from: number, to: number, width: number): Tick[] {
	const span = to - from;
	if (span <= 0) return [];
	const starts = monthStarts(from, to);

	for (const step of steps()) {
		const picked = starts.filter(
			(start) => (start.getUTCFullYear() * 12 + start.getUTCMonth()) % step === 0
		);
		const ticks = picked.map((start, rank) => ({
			at: (start.getTime() - from) / span,
			label: labelOf(start, step, rank === 0)
		}));
		// Ends: a step wider than the whole span leaves at most one tick, which fits.
		if (ticksClear(ticks, width)) return ticks;
	}
	return [];
}
