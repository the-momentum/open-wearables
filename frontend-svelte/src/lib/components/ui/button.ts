import type { ClassValue } from 'svelte/elements';
import { cn } from '$lib/utils/cn';

export type ButtonVariant = 'primary' | 'outline';

/** `sm` is for actions that sit inside a row or a card, beside its content. */
export type ButtonSize = 'md' | 'sm';

const VARIANT: Record<ButtonVariant, string> = {
	primary: 'bg-primary text-primary-foreground hover:bg-primary-hover',
	outline: 'border border-border hover:bg-surface-muted'
};

const SIZE: Record<ButtonSize, string> = {
	md: 'min-h-11 gap-2 px-4 text-sm',
	sm: 'min-h-8 gap-1.5 px-2.5 text-xs'
};

export function buttonClass(
	variant: ButtonVariant,
	size: ButtonSize = 'md',
	className?: ClassValue | null
): string {
	return cn(
		'inline-flex items-center justify-center rounded-lg font-medium whitespace-nowrap transition-colors disabled:opacity-50',
		VARIANT[variant],
		SIZE[size],
		className
	);
}
