import type { ClassValue } from 'svelte/elements';
import { cn } from '$lib/utils/cn';

/** `danger` only for what deletes or removes data. */
export type ButtonVariant = 'primary' | 'outline' | 'danger';

/** `sm` is for actions that sit inside a row or a card, beside its content. */
export type ButtonSize = 'md' | 'sm';

const VARIANT: Record<ButtonVariant, string> = {
	primary: 'bg-inverted text-inverted-foreground hover:bg-inverted-hover',
	outline: 'border border-border text-foreground hover:bg-surface-muted',
	danger: 'bg-danger text-danger-foreground hover:bg-danger-hover'
};

// The glyph is sized here, not by each caller, so a button's icon matches its text step.
const SIZE: Record<ButtonSize, string> = {
	// The design's 40 and 36, except 44 on a phone: the smallest target a thumb hits.
	md: 'min-h-11 gap-2 px-4 text-sm md:min-h-10 [&_svg]:size-4',
	sm: 'min-h-9 gap-1.5 px-2.5 text-xs [&_svg]:size-3'
};

export function buttonClass(
	variant: ButtonVariant,
	size: ButtonSize = 'md',
	className?: ClassValue | null
): string {
	return cn(
		'inline-flex items-center justify-center rounded-lg font-medium whitespace-nowrap transition-colors disabled:opacity-50 [&_svg]:shrink-0',
		VARIANT[variant],
		SIZE[size],
		// The border already sets an outline off, so it needs less air than a filled button.
		variant === 'outline' && size === 'md' && 'px-3',
		className
	);
}

/** A bare glyph that acts on its row - edit, copy, delete - with a 16px icon. */
export const ICON_BUTTON =
	'grid size-9 shrink-0 place-items-center rounded-lg text-muted-foreground transition-colors hover:text-secondary-foreground disabled:opacity-50';
