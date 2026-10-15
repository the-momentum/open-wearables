import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * "class names", the shadcn/ui convention. `twMerge` is what matters: without
 * it a caller's `class="w-full"` and a component's default `w-auto` both reach
 * the DOM and stylesheet order decides.
 */
export function cn(...inputs: ClassValue[]): string {
	return twMerge(clsx(inputs));
}
