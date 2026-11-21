import type { User } from './types';

/** The neutral tone, for the one avatar that needs no telling apart: your own. */
export const AVATAR_TONE = 'bg-surface-muted text-secondary-foreground';

/**
 * Identity tints for initials, the design's five. No green: green, and the
 * status tones beside these, mean something.
 */
export const AVATAR_TONES = [
	AVATAR_TONE,
	'bg-avatar-blue-tint text-avatar-blue',
	'bg-avatar-teal-tint text-avatar-teal',
	'bg-avatar-orange-tint text-avatar-orange',
	'bg-avatar-pink-tint text-avatar-pink'
] as const;

/** FNV-1a: ids that differ only in their last digit still spread across the tones. */
function hash(key: string): number {
	let value = 0x811c9dc5;
	for (let index = 0; index < key.length; index += 1) {
		value ^= key.charCodeAt(index);
		value = Math.imul(value, 0x01000193);
	}
	return value >>> 0;
}

/** The same key wears the same tint on every page and every visit. */
export const avatarTone = (key: string): string => AVATAR_TONES[hash(key) % AVATAR_TONES.length];

export function initials(user: Pick<User, 'first_name' | 'last_name' | 'email'>): string {
	const fromName = [user.first_name, user.last_name]
		.filter((part): part is string => Boolean(part?.trim()))
		.map((part) => part.trim()[0]);

	if (fromName.length > 0) return fromName.join('').slice(0, 2).toUpperCase();

	const local = user.email?.trim();
	return local ? local.slice(0, 2).toUpperCase() : '-';
}

export function fullName(user: Pick<User, 'first_name' | 'last_name'>): string {
	return [user.first_name, user.last_name].filter(Boolean).join(' ').trim();
}
