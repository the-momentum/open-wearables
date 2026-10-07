/**
 * Theme tokens, so a chart line cannot drift from the rest of the palette, and
 * ordered least to most alarming: with two lines on a chart nothing is drawn in
 * the colour of an error.
 */
const TONES = [
	'var(--color-primary)',
	'var(--color-warning)',
	'var(--color-success)',
	'var(--color-danger)',
	'var(--color-muted-foreground)'
];

/**
 * Colour by position rather than by name: a hash of the key would sooner or
 * later hand two lines on the same chart the same colour, and two
 * indistinguishable curves is the one thing a legend cannot fix.
 */
export function tones(keys: string[]): (key: string) => string {
	const byKey = new Map(keys.map((key, index) => [key, TONES[index % TONES.length]]));
	return (key) => byKey.get(key) ?? TONES[TONES.length - 1];
}
