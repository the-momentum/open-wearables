// Per process: a second replica keeps its own copy, which costs it one API call.
const entries = new Map<string, { value: unknown; expiresAt: number }>();

export function recall<T>(key: string, now = Date.now()): T | null {
	const entry = entries.get(key);
	if (!entry) return null;
	if (entry.expiresAt > now) return entry.value as T;
	entries.delete(key);
	return null;
}

export function keep<T>(key: string, value: T, ttlSeconds: number, now = Date.now()): T {
	for (const [stale, entry] of entries) if (entry.expiresAt <= now) entries.delete(stale);
	entries.set(key, { value, expiresAt: now + ttlSeconds * 1000 });
	return value;
}

/** Drops an entry, so the next read goes to the API. */
export const forget = (key: string) => {
	entries.delete(key);
};

/** Empties the cache; only the e2e suite needs this, between tests. */
export const forgetAll = () => entries.clear();

export async function cached<T>(
	key: string,
	ttlSeconds: number,
	load: () => Promise<T>
): Promise<T> {
	return recall<T>(key) ?? keep(key, await load(), ttlSeconds);
}
