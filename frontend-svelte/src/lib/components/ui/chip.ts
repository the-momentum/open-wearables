import { cn } from '$lib/utils/cn';

/**
 * Shared by FilterChip (a link) and ToggleChip (a button) so the two cannot
 * drift apart visually.
 */
export function chipClass(selected: boolean): string {
	return cn(
		'inline-flex min-h-9 items-center rounded-full border px-3 text-xs font-medium capitalize transition-colors',
		selected
			? 'border-primary/40 bg-primary/10 text-primary'
			: 'border-border text-muted-foreground hover:bg-surface-muted hover:text-foreground'
	);
}
