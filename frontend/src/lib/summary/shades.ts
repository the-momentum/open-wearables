/** One hue at descending strength: green and red would imply good and bad. */
const RANK = ['bg-primary', 'bg-primary/75', 'bg-primary/55', 'bg-primary/35', 'bg-primary/20'];

export const rankShade = (index: number) => RANK[Math.min(index, RANK.length - 1)];

/** Step 0 is the border colour: an empty bucket is a bucket, not a hole. */
export const HEAT_STEPS = [
	'bg-border/50',
	'bg-primary/20',
	'bg-primary/35',
	'bg-primary/50',
	'bg-primary/70',
	'bg-primary'
];

/** Legend swatches and heatmap cells have to read as the same thing. */
export const CELL_SHAPE = 'size-2.5 rounded-[2px]';

/** Square root, not linear: one busy day would otherwise flatten every other. */
export function heatShade(count: number, max: number): string {
	if (count <= 0 || max <= 0) return HEAT_STEPS[0];

	const share = Math.sqrt(count) / Math.sqrt(max);
	const step = Math.ceil(share * (HEAT_STEPS.length - 1));
	return HEAT_STEPS[Math.min(Math.max(step, 1), HEAT_STEPS.length - 1)];
}
