import { isRedirect } from '@sveltejs/kit';

/** A request whose failure costs one part of a page, not the page. */
export async function optional<T>(work: Promise<T>, fallback: T): Promise<T> {
	try {
		return await work;
	} catch (error) {
		// A lapsed session costs the whole page: it goes back to sign-in.
		if (isRedirect(error)) throw error;
		return fallback;
	}
}
