import { CATEGORY_TONES, tones } from './palette';

/** Radii, the gap between slices and the slices' corner radius, in px around the centre. */
export type Ring = { outer: number; inner: number; gap: number; corner: number };

export const DONUT_RING: Ring = { outer: 84, inner: 52, gap: 2, corner: 4 };

/** Radians, clockwise from twelve o'clock. */
export type Arc = { start: number; end: number };

export type Slice = { key: string; label: string; value: number; colour: string };

const TAU = Math.PI * 2;

/** Not a provider code, so a provider can never take the remainder's place. */
export const REST_KEY = '(other)';

/**
 * The slices to draw: the first six as given, each in its own hue, and
 * everything else - the parts past six and whatever of `total` no part
 * accounts for - as one grey "Other", so the ring still adds up to the total.
 */
export function donutSlices(
	parts: { key: string; label: string; value: number }[],
	total: number
): Slice[] {
	const named = parts.filter((part) => part.value > 0).slice(0, CATEGORY_TONES.length);
	const colourFor = tones(
		named.map((part) => part.key),
		CATEGORY_TONES
	);
	const rest = total - named.reduce((sum, part) => sum + part.value, 0);

	const slices = named.map((part) => ({ ...part, colour: colourFor(part.key) }));
	return rest > 0
		? [
				...slices,
				{ key: REST_KEY, label: 'Other', value: rest, colour: 'var(--color-surface-strong)' }
			]
		: slices;
}

/**
 * Each value's share of the circle, every one at least `least` radians: a
 * provider with one connection among thousands still gets a slice the
 * pointer can find, and the legend keeps its exact figure.
 */
export function arcs(values: number[], least = 0): Arc[] {
	const total = values.reduce((sum, value) => sum + value, 0);
	if (total <= 0) return [];

	const raised = new Set<number>();
	let scale = TAU / total;
	for (;;) {
		const below = values.flatMap((value, index) =>
			!raised.has(index) && value * scale < least ? [index] : []
		);
		if (below.length === 0) break;
		for (const index of below) raised.add(index);
		const rest = values.reduce((sum, value, index) => (raised.has(index) ? sum : sum + value), 0);
		scale = rest > 0 ? (TAU - raised.size * least) / rest : 0;
	}

	let start = 0;
	return values.map((value, index) => {
		const end = start + (raised.has(index) ? least : value * scale);
		const arc = { start, end };
		start = end;
		return arc;
	});
}

/** The narrowest slice that still shows its gap and both inner corners. */
export const leastArc = ({ inner, gap, corner }: Ring) => (gap + corner * 2) / inner;

type XY = [number, number];

const f = (value: number) => value.toFixed(2);
const xy = ([x, y]: XY) => `${f(x)} ${f(y)}`;
const scaled = ([x, y]: XY, by: number): XY => [x * by, y * by];

/**
 * One slice: an annular sector with rounded corners, drawn around (0, 0), its
 * straight sides held `gap / 2` off the radius so every gap is the same width
 * from the hole to the rim, as the design's white borders are.
 */
export function slicePath({ start, end }: Arc, { outer, inner, gap, corner }: Ring): string {
	const half = gap / 2;
	const sine = Math.sin(Math.min((end - start) / 2, Math.PI / 2));
	if (sine * inner <= half) return '';

	// The largest corner whose inner fillet still fits the slice's width at the hole.
	const c = Math.max(Math.min(corner, (outer - inner) / 2, (sine * inner - half) / (1 - sine)), 0);
	const h = half + c;
	const rim = Math.sqrt((outer - c) ** 2 - h ** 2);
	const hole = Math.sqrt((inner + c) ** 2 - h ** 2);

	// `side` 1 is the slice's leading edge, -1 its trailing one: both step inwards.
	const edge = (angle: number, side: 1 | -1) => {
		const along = (radial: number, offset: number): XY => [
			radial * Math.sin(angle) + side * offset * Math.cos(angle),
			-radial * Math.cos(angle) + side * offset * Math.sin(angle)
		];
		return {
			rimSide: xy(along(rim, half)),
			rim: xy(scaled(along(rim, h), outer / (outer - c))),
			holeSide: xy(along(hole, half)),
			hole: xy(scaled(along(hole, h), inner / (inner + c)))
		};
	};

	const lead = edge(start, 1);
	const trail = edge(end, -1);
	const rimSpan = end - start - 2 * Math.asin(h / (outer - c));
	const holeSpan = end - start - 2 * Math.asin(h / (inner + c));
	const fillet = `A${f(c)} ${f(c)} 0 0 1`;

	return [
		`M${lead.rimSide}`,
		`${fillet} ${lead.rim}`,
		`A${outer} ${outer} 0 ${rimSpan > Math.PI ? 1 : 0} 1 ${trail.rim}`,
		`${fillet} ${trail.rimSide}`,
		`L${trail.holeSide}`,
		`${fillet} ${trail.hole}`,
		`A${inner} ${inner} 0 ${holeSpan > Math.PI ? 1 : 0} 0 ${lead.hole}`,
		`${fillet} ${lead.holeSide}`,
		'Z'
	].join(' ');
}

/** A whole ring, for a single slice: it has no neighbour to leave a gap for. */
export const ringPath = ({ outer, inner }: Ring): string =>
	[outer, inner]
		.map(
			(radius, index) =>
				`M0 ${-radius} A${radius} ${radius} 0 1 ${1 - index} 0 ${radius} ` +
				`A${radius} ${radius} 0 1 ${1 - index} 0 ${-radius} Z`
		)
		.join(' ');
