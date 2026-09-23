<script lang="ts" generics="T">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import ChevronUp from '@lucide/svelte/icons/chevron-up';
	import GripVertical from '@lucide/svelte/icons/grip-vertical';
	import type { Snippet } from 'svelte';
	import { moved } from '$lib/settings/priorities';

	let {
		items = $bindable(),
		label,
		keyOf,
		row
	}: {
		items: T[];
		/** Names the list for assistive tech — there are two on the page. */
		label: string;
		keyOf: (item: T) => string;
		row: Snippet<[T]>;
	} = $props();

	const step = (index: number, delta: number) => (items = moved(items, index, delta));

	/**
	 * Pointer Events rather than HTML5 drag-and-drop or a package: the native API
	 * does not fire on touch at all, and this is one list on one page.
	 *
	 * The dragged row follows the finger, and crossing half a row swaps it with
	 * its neighbour there and then — so the gap is always where you are pointing.
	 * `startY` moves with each swap, which is what keeps the row under the finger
	 * instead of drifting a row further every time.
	 */
	let dragging = $state<number | null>(null);
	let offset = $state(0);
	let startY = 0;
	let rowHeight = 0;

	function grab(event: PointerEvent, index: number) {
		const handle = event.currentTarget as HTMLElement;
		handle.setPointerCapture(event.pointerId);
		rowHeight = handle.closest('li')!.getBoundingClientRect().height;
		startY = event.clientY;
		offset = 0;
		dragging = index;
	}

	function drag(event: PointerEvent) {
		if (dragging === null) return;

		let delta = event.clientY - startY;

		while (delta > rowHeight / 2 && dragging < items.length - 1) {
			items = moved(items, dragging, 1);
			dragging += 1;
			startY += rowHeight;
			delta -= rowHeight;
		}
		while (delta < -rowHeight / 2 && dragging > 0) {
			items = moved(items, dragging, -1);
			dragging -= 1;
			startY -= rowHeight;
			delta += rowHeight;
		}

		offset = delta;
	}

	function drop() {
		dragging = null;
		offset = 0;
	}

	const ARROW =
		'grid h-5 w-7 place-items-center rounded text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-20';
</script>

<ol aria-label={label} class="divide-y divide-border {dragging !== null ? 'select-none' : ''}">
	{#each items as item, index (keyOf(item))}
		{@const first = index === 0}
		{@const held = dragging === index}
		<li
			class="flex items-center gap-2 py-2.5 sm:gap-3 {held
				? 'relative z-10 rounded-lg bg-surface shadow-lg ring-1 ring-primary/30'
				: ''}"
			style={held ? `transform: translateY(${offset}px)` : undefined}
		>
			<!-- The arrows below are the accessible way to do this; the handle is a
			     pointer affordance on top of them, so it stays out of the tree.
			     touch-action:none is what stops a touch drag scrolling the page. -->
			<span
				aria-hidden="true"
				onpointerdown={(event) => grab(event, index)}
				onpointermove={drag}
				onpointerup={drop}
				onpointercancel={drop}
				class="grid w-5 shrink-0 cursor-grab touch-none place-items-center self-stretch
					text-muted-foreground/50 transition-colors hover:text-foreground active:cursor-grabbing"
			>
				<GripVertical size={14} />
			</span>

			<!-- The rank is what the list is about, so it is what you see first; the
			     winner carries the accent, because "who wins" is the whole question
			     this page answers. -->
			<span
				aria-hidden="true"
				class="grid size-7 shrink-0 place-items-center rounded-lg text-xs font-semibold tabular-nums
					{first ? 'bg-primary/12 text-primary' : 'bg-surface-muted text-muted-foreground'}"
			>
				{index + 1}
			</span>

			<div class="flex min-w-0 flex-1 items-center gap-2.5">{@render row(item)}</div>

			<div class="flex shrink-0 flex-col">
				<button
					type="button"
					onclick={() => step(index, -1)}
					disabled={first}
					aria-label="Move {keyOf(item)} up"
					class={ARROW}
				>
					<ChevronUp size={14} aria-hidden="true" />
				</button>
				<button
					type="button"
					onclick={() => step(index, 1)}
					disabled={index === items.length - 1}
					aria-label="Move {keyOf(item)} down"
					class={ARROW}
				>
					<ChevronDown size={14} aria-hidden="true" />
				</button>
			</div>
		</li>
	{/each}
</ol>
