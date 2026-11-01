/** A request whose failure costs one part of a page, not the page. */
export async function optional<T>(work: Promise<T>, fallback: T): Promise<T> {
	try {
		return await work;
	} catch {
		return fallback;
	}
}
