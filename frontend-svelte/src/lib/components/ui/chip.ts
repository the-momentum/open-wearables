import { cn } from '$lib/utils/cn';

/** On and off for anything the reader picks: filter chips, event chips. */
export const CHIP_ON = 'border-primary/40 bg-primary/10 text-primary';
export const CHIP_OFF =
	'border-border text-muted-foreground hover:bg-surface-muted hover:text-foreground';

/**
 * Shared by FilterChip (a link) and ToggleChip (a button) so the two cannot
 * drift apart visually.
 */
export function chipClass(selected: boolean): string {
	return cn(
		'inline-flex min-h-9 items-center rounded-full border px-3 text-xs font-medium capitalize transition-colors',
		selected ? CHIP_ON : CHIP_OFF
	);
}

/**
 * The small square chip for picking many from a long list — event types,
 * workout types, series. `chipClass` is the round one for a short filter row.
 */
export const tagClass = (selected: boolean): string =>
	cn(
		'rounded-md border px-2 py-1 text-left text-xs transition-colors',
		selected ? CHIP_ON : CHIP_OFF
	);
