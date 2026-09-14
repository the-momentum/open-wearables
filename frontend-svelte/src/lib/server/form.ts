import { fail } from '@sveltejs/kit';
import { ApiError } from './api';

export function describe(error: unknown): string {
	if (!(error instanceof ApiError)) return 'Something went wrong. Try again.';
	if (error.status === 409) return 'A user with that email already exists.';
	if (error.status === 404) return 'That user no longer exists.';
	return error.message;
}

/** Echoes the submitted values back so a rejected form keeps what was typed. */
export async function attempt<T extends Record<string, unknown>>(
	action: string,
	context: T,
	work: () => Promise<unknown>
) {
	try {
		await work();
	} catch (error) {
		return fail(400, { action, ...context, message: describe(error) });
	}
	return { action };
}
