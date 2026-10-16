/** Categorical, from theme tokens, and never a status colour: green and red mean success and failure. */
export const SERIES_TONES = [
	'var(--color-primary)',
	'var(--color-foreground)',
	'color-mix(in oklab, var(--color-primary) 45%, transparent)',
	'var(--color-muted-foreground)',
	'color-mix(in oklab, var(--color-foreground) 30%, transparent)'
];

/**
 * Colour by position rather than by name: a hash of the key would sooner or
 * later hand two lines on the same chart the same colour, and two
 * indistinguishable curves is the one thing a legend cannot fix.
 */
export function tones(keys: string[]): (key: string) => string {
	const byKey = new Map(keys.map((key, index) => [key, SERIES_TONES[index % SERIES_TONES.length]]));
	return (key) => byKey.get(key) ?? SERIES_TONES[SERIES_TONES.length - 1];
}
