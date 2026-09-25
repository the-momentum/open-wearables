<script lang="ts">
	import { MICRO } from '$lib/components/ui/typography';
	import { CHART_BOX, extent, linePath, scaleY, spanOf, type Line } from '$lib/charts/geometry';
	import { seriesColour, unitLabel } from '$lib/timeseries/samples';
	import { toggled } from '$lib/utils/collect';
	import { formatNumber } from '$lib/utils/format';
	import HoverReadout from './HoverReadout.svelte';
	import SeriesLegend from './SeriesLegend.svelte';

	let {
		series,
		zones,
		from,
		to,
		formatTime,
		label,
		colourFor = seriesColour,
		format = (value, unit) => formatNumber(value, unitLabel(unit)),
		shared = false
	}: {
		series: Line[];
		/**
		 * Shaded bands behind one of the lines, keyed by the series they describe.
		 * `zones[i].max` is that band's ceiling; a null one is simply not drawn.
		 */
		zones: { type: string; label: string; zones: { max: number | null }[] } | null;
		from: number;
		to: number;
		/** The caller owns the clock: only it knows whose timezone to read in. */
		formatTime: (at: number) => string;
		label: string;
		/** What a line's `type` means as a colour — a sensor, or a provider. */
		colourFor?: (type: string) => string;
		format?: (value: number, unit: string) => string;
		/**
		 * One scale for every line instead of each on its own. Sensors share no
		 * axis — a pulse and a cadence are not comparable heights — but readings of
		 * the same thing from two providers are exactly what has to be compared.
		 */
		shared?: boolean;
	} = $props();

	// The viewBox is stretched to whatever width the card has, so strokes carry
	// `non-scaling-stroke` and every label lives in HTML outside the SVG.
	const { width: W, height: H } = CHART_BOX;
	/** Below this a band cannot hold its own label without hitting its neighbour. */
	const LABEL_ROOM = 18;

	// A plain array, not a Set: Svelte tracks reassignment, and the list of series
	// a workout has is four at most.
	let off = $state<string[]>([]);

	function toggle(label: string) {
		const next = toggled(off, label);
		// Turning the last one off leaves an empty frame, which reads as no data.
		if (next.length < series.length) off = next;
	}

	// Same metric from a second device keeps the colour and loses the solid line:
	// two identical strokes would be two curves nobody can tell apart.
	const lines = $derived(
		series.map((entry, index) => {
			const rank = series.slice(0, index).filter((other) => other.type === entry.type).length;
			return { ...entry, dash: rank === 0 ? '' : `${rank * 3} ${rank * 3}` };
		})
	);

	const shown = $derived(lines.filter((entry) => !off.includes(entry.label)));

	const span = $derived(Math.max(to - from, 1));
	const x = (at: number) => ((at - from) / span) * W;

	type Scaled = Line & { dash: string; low: number; high: number; path: string };

	const whole = $derived(shared ? spanOf(shown) : null);

	const scaled: Scaled[] = $derived(
		shown.map((entry) => {
			const range = whole ?? extent(entry.points);
			return { ...entry, ...range, path: linePath(entry.points, { from, to }, range, CHART_BOX) };
		})
	);

	// A band is drawn on its own series' scale, so it is only honest while that
	// line is on — and only where it overlaps what the line actually covers.
	const owner = $derived(scaled.find((entry) => entry.type === zones?.type));
	const bands = $derived.by(() => {
		if (!owner || !zones) return [];

		const y = scaleY(owner.low, owner.high, CHART_BOX);
		const out: { zone: number; top: number; y: number; height: number }[] = [];
		let floor = owner.low;

		for (const [index, band] of zones.zones.entries()) {
			const top = band.max;
			if (top === null || top <= floor) continue;

			// Clipped to the frame: a zone whose ceiling sits far above anything
			// recorded maps to a negative y, and an HTML label at that position
			// escapes the chart entirely instead of being cropped like the rect.
			const upper = Math.max(y(top), 0);
			const lower = Math.min(y(floor), H);
			floor = top;
			if (lower - upper > 0) out.push({ zone: index, top, y: upper, height: lower - upper });
		}

		return out;
	});

	let hovered = $state<number | null>(null);

	function track(event: PointerEvent) {
		const box = event.currentTarget as HTMLElement;
		const fraction = (event.clientX - box.getBoundingClientRect().left) / box.clientWidth;
		hovered = from + Math.min(Math.max(fraction, 0), 1) * span;
	}

	/** Nearest reading to the pointer, per visible series. */
	const readings = $derived.by(() => {
		if (hovered === null) return [];
		return scaled.map((entry) => {
			const nearest = entry.points.reduce((best, point) =>
				Math.abs(point.at - hovered!) < Math.abs(best.at - hovered!) ? point : best
			);
			return { type: entry.type, label: entry.label, unit: entry.unit, value: nearest.value };
		});
	});

	const at = $derived(hovered === null ? 0 : ((hovered - from) / span) * 100);
</script>

<div class="flex flex-col gap-2">
	<SeriesLegend
		{lines}
		{off}
		{colourFor}
		ontoggle={toggle}
		bands={bands.length ? zones?.label : undefined}
	/>

	<div
		class="relative"
		onpointermove={track}
		onpointerleave={() => (hovered = null)}
		role="img"
		aria-label={label}
	>
		<!-- Each line fills the frame on its own scale, so without these the shape
		     is readable and the numbers are not. -->
		{#if scaled.length > 0}
			{@const first = scaled[0]}
			<div
				class="pointer-events-none absolute inset-y-0 left-0 flex flex-col justify-between
					py-0.5 text-[10px] tabular-nums"
				style="color: {whole ? 'var(--color-muted-foreground)' : colourFor(first.type)}"
			>
				<!-- On their own background, because a line drawn to the top of the
				     frame crosses the very number that says how high it reached. -->
				<span class="rounded bg-surface/85 px-0.5">{Math.round(first.high)}</span>
				<span class="rounded bg-surface/85 px-0.5">{Math.round(first.low)}</span>
			</div>
		{/if}

		<!-- Each band named and bounded: shading alone said a zone was there but
		     never which, nor where it ends. The label hangs under its own ceiling. -->
		{#each bands.filter((band) => band.height >= LABEL_ROOM) as band (band.zone)}
			<span
				class="pointer-events-none absolute right-1 text-[10px] whitespace-nowrap
					text-muted-foreground/70 tabular-nums"
				style="top: {(band.y / H) * 100}%"
			>
				Z{band.zone + 1} · {band.top}
			</span>
		{/each}
		<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" class="h-44 w-full">
			{#each bands as band (band.zone)}
				<rect
					x="0"
					y={band.y}
					width={W}
					height={band.height}
					fill="var(--color-primary)"
					opacity={0.05 + band.zone * 0.035}
				/>
			{/each}

			{#each scaled as entry (entry.label)}
				<path
					d={entry.path}
					fill="none"
					stroke={colourFor(entry.type)}
					stroke-width="2"
					stroke-linejoin="round"
					stroke-dasharray={entry.dash || undefined}
					vector-effect="non-scaling-stroke"
				/>
			{/each}

			{#if hovered !== null}
				<line
					x1={x(hovered)}
					x2={x(hovered)}
					y1="0"
					y2={H}
					stroke="var(--color-foreground)"
					stroke-width="1"
					opacity="0.35"
					vector-effect="non-scaling-stroke"
				/>
			{/if}
		</svg>

		{#if hovered !== null && readings.length > 0}
			<HoverReadout heading={formatTime(hovered)} {readings} {at} {colourFor} {format} />
		{/if}
	</div>

	<div class="flex justify-between tabular-nums {MICRO}">
		<span>{formatTime(from)}</span>
		<span>{formatTime(to)}</span>
	</div>
</div>
