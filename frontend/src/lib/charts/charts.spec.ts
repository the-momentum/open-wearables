import { describe, expect, it } from 'vitest';
import { arcs, DONUT_RING, donutSlices, leastArc, REST_KEY, slicePath } from './donut';
import { CATEGORY_TONES } from './palette';

const TAU = Math.PI * 2;

/** The end point of every command in a path, in order. */
const vertices = (path: string) =>
	path
		.split(/(?=[MALZ])/)
		.filter((command) => !command.startsWith('Z'))
		.map((command) => command.slice(1).trim().split(/\s+/).map(Number).slice(-2));

const radius = ([x, y]: number[]) => Math.hypot(x, y);

describe('arcs', () => {
	it('splits the circle in proportion, clockwise from twelve', () => {
		const [first, second] = arcs([3, 1]);
		expect(first.start).toBe(0);
		expect(first.end).toBeCloseTo((TAU * 3) / 4);
		expect(second.end).toBeCloseTo(TAU);
	});

	// One connection among thousands would otherwise be a slice nobody can see or point at.
	it('raises a sliver to the least angle and takes it from the rest', () => {
		const [big, tiny] = arcs([9999, 1], 0.2);
		expect(tiny.end - tiny.start).toBeCloseTo(0.2);
		expect(big.end - big.start).toBeCloseTo(TAU - 0.2);
	});

	it('draws nothing for nothing', () => {
		expect(arcs([0, 0])).toEqual([]);
	});
});

describe('slicePath', () => {
	it('stays between the hole and the rim', () => {
		for (const [x, y] of vertices(slicePath({ start: 0, end: 2 }, DONUT_RING))) {
			expect(radius([x, y])).toBeGreaterThanOrEqual(DONUT_RING.inner - 0.01);
			expect(radius([x, y])).toBeLessThanOrEqual(DONUT_RING.outer + 0.01);
		}
	});

	// The design's gaps are borders of one width, not wedges that widen to the rim.
	it('leaves the same gap between neighbours at the hole and at the rim', () => {
		const [first, second] = arcs([2, 1]).map((arc) => vertices(slicePath(arc, DONUT_RING)));
		// The trailing side runs from vertex 3 (rim) to 4 (hole); the leading one from 7 (hole) to 0 (rim).
		const gapAt = (a: number[], b: number[]) => Math.hypot(a[0] - b[0], a[1] - b[1]);
		expect(gapAt(first[3], second[0])).toBeCloseTo(DONUT_RING.gap, 1);
		expect(gapAt(first[4], second[7])).toBeCloseTo(DONUT_RING.gap, 1);
	});

	it('keeps the narrowest slice it allows, and drops one thinner than its gap', () => {
		expect(slicePath({ start: 0, end: leastArc(DONUT_RING) }, DONUT_RING)).not.toBe('');
		expect(slicePath({ start: 0, end: 0.01 }, DONUT_RING)).toBe('');
	});
});

describe('donutSlices', () => {
	const part = (key: string, value: number) => ({ key, label: key, value });

	it('gives each provider its own hue, in the order given', () => {
		const slices = donutSlices([part('garmin', 5), part('oura', 3)], 8);
		expect(slices.map((slice) => slice.colour)).toEqual(CATEGORY_TONES.slice(0, 2));
	});

	// The backend lists six providers at most, and the total counts every connection.
	it('folds whatever the parts leave of the total into one "Other"', () => {
		const parts = Array.from({ length: 7 }, (_, index) => part(`p${index}`, 10));
		const slices = donutSlices(parts, 75);
		expect(slices).toHaveLength(7);
		expect(slices.at(-1)).toMatchObject({ key: REST_KEY, label: 'Other', value: 15 });
	});

	it('adds no "Other" when the parts make up the whole', () => {
		expect(donutSlices([part('garmin', 5), part('oura', 0)], 5).map((s) => s.key)).toEqual([
			'garmin'
		]);
	});
});
