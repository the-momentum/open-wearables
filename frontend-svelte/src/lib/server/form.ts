import { fail } from '@sveltejs/kit';
import { ApiError } from './api';

export function describe(error: unknown): string {
	if (!(error instanceof ApiError)) return 'Something went wrong. Try again.';
	if (error.status === 409) return 'A user with that email already exists.';
	if (error.status === 404) return 'That user no longer exists.';
	return error.message;
}

/** One trimmed string out of a submission; `String(get(...) ?? '')` everywhere else. */
export const field = (form: FormData, name: string) => String(form.get(name) ?? '').trim();

/**
 * A draft carried through a hidden field. The save bars post the whole list in
 * one go, which keeps them working without JavaScript.
 */
export const jsonField = <T>(form: FormData, name: string, fallback: T): T => {
	try {
		return JSON.parse(String(form.get(name) ?? '')) as T;
	} catch {
		return fallback;
	}
};

/** Echoes the submitted values back so a rejected form keeps what was typed. */
export async function attempt<
	T extends Record<string, unknown>,
	R,
	E extends Record<string, unknown> = Record<string, never>
>(
	action: string,
	context: T,
	work: () => Promise<R>,
	/** What the page needs from the result — a one-time secret, mostly. */
	onSuccess?: (result: R) => E
) {
	try {
		const result = await work();
		return { action, ...(onSuccess?.(result) ?? ({} as E)) };
	} catch (error) {
		return fail(400, { action, ...context, message: describe(error) });
	}
}
