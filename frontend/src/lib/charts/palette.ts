/** Categorical, opaque (3:1 on the card in both themes), and never a status colour. */
export const SERIES_TONES = [
	'var(--color-primary)',
	'var(--color-foreground)',
	'color-mix(in oklab, var(--color-primary) 70%, var(--color-surface))',
	'var(--color-muted-foreground)',
	'var(--color-secondary-foreground)'
];

/**
 * The design's hues for a chart where colour names the thing, like a provider's
 * slice, in its order. Below 3:1 on a light card, so every slice is also named,
 * with its figure, in the legend. Six at most: fold the rest into one "other".
 */
export const CATEGORY_TONES = [
	'var(--color-chart-blue)',
	'var(--color-chart-orange)',
	'var(--color-chart-teal)',
	'var(--color-chart-amber)',
	'var(--color-chart-pink)',
	'var(--color-chart-green)'
];

/**
 * Colour by position rather than by name: a hash of the key would sooner or
 * later hand two lines on the same chart the same colour, and two
 * indistinguishable curves is the one thing a legend cannot fix.
 */
export function tones(keys: string[], palette: string[] = SERIES_TONES): (key: string) => string {
	const byKey = new Map(keys.map((key, index) => [key, palette[index % palette.length]]));
	return (key) => byKey.get(key) ?? palette[palette.length - 1];
}
