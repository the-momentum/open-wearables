import type { ClassValue } from 'svelte/elements';
import { cn } from '$lib/utils/cn';

export type ButtonVariant = 'primary' | 'outline';

const VARIANT: Record<ButtonVariant, string> = {
	primary: 'bg-primary text-primary-foreground hover:bg-primary-hover',
	outline: 'border border-border hover:bg-surface-muted'
};

export function buttonClass(variant: ButtonVariant, className?: ClassValue | null): string {
	return cn(
		'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium whitespace-nowrap transition-colors disabled:opacity-50',
		VARIANT[variant],
		className
	);
}
