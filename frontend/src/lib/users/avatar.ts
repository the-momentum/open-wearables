import type { User } from './types';

/** One neutral tone: green, amber and red are reserved for status. */
export const AVATAR_TONE = 'bg-surface-muted text-secondary-foreground';

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
