import { cn } from '$lib/utils/cn';

/** On and off for anything the reader picks: filter chips, event chips. */
export const CHIP_ON = 'border-primary/40 bg-primary/10 text-primary';
export const CHIP_OFF =
	'border-border text-muted-foreground hover:bg-surface-muted hover:text-foreground';

const CHIP = 'items-center border transition-colors disabled:opacity-50';

/**
 * The design's SelectorChip at Md, for a short row of filters. Shared by
 * FilterChip (a link) and ToggleChip (a button) so the two cannot drift apart.
 */
export function chipClass(selected: boolean): string {
	return cn(
		CHIP,
		'inline-flex min-h-9 gap-2 rounded-lg px-2 text-sm capitalize',
		selected ? CHIP_ON : CHIP_OFF
	);
}

/**
 * The SelectorChip at Sm, for picking many from a long list - event types,
 * workout types, series.
 */
export const tagClass = (selected: boolean): string =>
	cn(
		CHIP,
		'inline-flex min-h-7 gap-1.5 rounded-md px-2.5 py-1 text-left text-xs',
		selected ? CHIP_ON : CHIP_OFF
	);

/** The bed a segmented choice sits in; its padding and gap are the caller's. */
export const SEGMENTS = 'inline-flex items-center rounded-lg border border-border bg-surface';

/** One option of a segmented choice: the design's TabItem, the chosen one lifted. */
export const segmentClass = (active: boolean): string =>
	cn(
		'inline-flex h-7.5 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium whitespace-nowrap transition-colors',
		active ? 'bg-surface-hover text-foreground' : 'text-muted-foreground hover:text-foreground'
	);
