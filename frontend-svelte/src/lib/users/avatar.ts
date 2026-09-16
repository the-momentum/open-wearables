import type { User } from './types';

/**
 * Six tones rather than a hash to hex: a fixed set stays inside the token
 * palette, so avatars cannot clash with the theme or fail contrast.
 */
export const AVATAR_TONES = [
	'bg-primary/15 text-primary',
	'bg-success/15 text-success',
	'bg-warning/15 text-warning',
	'bg-danger/15 text-danger',
	'bg-surface-muted text-foreground/70',
	'bg-primary/10 text-primary/80'
] as const;

/** Stable per user, so a row keeps its colour across pages and reloads. */
export function avatarTone(id: string): string {
	let hash = 0;
	for (const character of id) hash = (hash * 31 + character.charCodeAt(0)) % 4096;
	return AVATAR_TONES[hash % AVATAR_TONES.length];
}

export function initials(user: Pick<User, 'first_name' | 'last_name' | 'email'>): string {
	const fromName = [user.first_name, user.last_name]
		.filter((part): part is string => Boolean(part?.trim()))
		.map((part) => part.trim()[0]);

	if (fromName.length > 0) return fromName.join('').slice(0, 2).toUpperCase();

	const local = user.email?.trim();
	return local ? local.slice(0, 2).toUpperCase() : '—';
}

export function fullName(user: Pick<User, 'first_name' | 'last_name'>): string {
	return [user.first_name, user.last_name].filter(Boolean).join(' ').trim();
}
