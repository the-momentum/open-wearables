import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Short for "class names" — the shadcn/ui convention, kept so `shadcn-svelte`
 * can generate components without edits.
 *
 * `clsx` flattens conditionals into a string; `twMerge` then resolves
 * conflicting Tailwind utilities so the last one wins — without it a caller's
 * `class="w-full"` and a component's default `w-auto` both survive into the
 * DOM and stylesheet order decides the winner.
 */
export function cn(...inputs: ClassValue[]): string {
	return twMerge(clsx(inputs));
}
