import { cn } from '$lib/utils/cn';

/** Shared by menu entries that are buttons and by those that submit a form. */
export const menuItemClass = (destructive = false) =>
	cn(
		'flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-sm transition-colors disabled:opacity-40',
		destructive ? 'text-danger hover:bg-danger/10' : 'text-foreground hover:bg-surface-muted'
	);
