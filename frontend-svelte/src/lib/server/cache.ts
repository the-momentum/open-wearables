import { redis } from './redis';

/**
 * Fails open, unlike the session store: with Redis down a cached read costs
 * the call it was saving, not a sign-in. Shared by everything that caches an
 * API answer, so they cannot disagree about what "down" means.
 */
export async function recall<T>(key: string): Promise<T | null> {
	try {
		const hit = await redis().get(key);
		return hit ? (JSON.parse(hit) as T) : null;
	} catch {
		return null;
	}
}

/** Writes in the background and hands the value straight back. */
export function keep<T>(key: string, value: T, ttlSeconds: number): T {
	redis()
		.set(key, JSON.stringify(value), 'EX', ttlSeconds)
		.catch(() => {});
	return value;
}

/** Drops an entry, so the next read goes to the API. */
export const forget = (key: string) =>
	redis()
		.del(key)
		.catch(() => {});

export async function cached<T>(
	key: string,
	ttlSeconds: number,
	load: () => Promise<T>
): Promise<T> {
	return (await recall<T>(key)) ?? keep(key, await load(), ttlSeconds);
}
