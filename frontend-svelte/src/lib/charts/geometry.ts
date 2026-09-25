export type Point = { at: number; value: number };

/**
 * One drawn line. `type` is the key a palette resolves to a colour — a series
 * type on a sensor chart, a provider on a score chart — and `label` is what the
 * legend calls it.
 */
export type Line = { type: string; label: string; unit: string; points: Point[] };

/** The canvas a chart draws into: viewBox units, not pixels. */
export type Box = { width: number; height: number; pad: number };

/** A chart with an axis and a hover readout, and a tile-sized one without. */
export const CHART_BOX: Box = { width: 1000, height: 200, pad: 12 };
export const SPARK_BOX: Box = { width: 400, height: 90, pad: 8 };

/**
 * Value to canvas, for one series' own range. A band drawn behind a line shares
 * it with that line, which is the only way the two can agree.
 */
export const scaleY = (low: number, high: number, box: Box) => (value: number) =>
	high === low
		? box.height / 2
		: box.height - box.pad - ((value - low) / (high - low)) * (box.height - box.pad * 2);

/** An SVG path through the points, on a time axis the caller owns. */
export function linePath(
	points: Point[],
	window: { from: number; to: number },
	range: { low: number; high: number },
	box: Box
): string {
	const span = Math.max(window.to - window.from, 1);
	const y = scaleY(range.low, range.high, box);

	return points
		.map((point, index) => {
			const x = ((point.at - window.from) / span) * box.width;
			return `${index ? 'L' : 'M'}${x.toFixed(1)} ${y(point.value).toFixed(1)}`;
		})
		.join(' ');
}

/** The lowest and highest reading, which is the range a series is drawn against. */
export function extent(points: Point[]): { low: number; high: number } {
	const values = points.map((point) => point.value);
	return { low: Math.min(...values), high: Math.max(...values) };
}

/** The values every line covers, which is the scale they can share. */
export const spanOf = (lines: Line[]) => extent(lines.flatMap((line) => line.points));

/** The instants every line covers, which is the axis they are drawn on. */
export function windowOf(lines: Line[]): { from: number; to: number } {
	const at = lines.flatMap((line) => line.points.map((point) => point.at));
	return { from: Math.min(...at), to: Math.max(...at) };
}
