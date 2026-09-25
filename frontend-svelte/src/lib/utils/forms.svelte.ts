import type { SubmitFunction } from '@sveltejs/kit';

/**
 * Shared submit behaviour: track submission, and by default never reset —
 * fields are bound to local state, and a failed submit must keep what was
 * typed. `reset` is for the one form where keeping it would be wrong.
 */
export function createSubmitFlag(onSuccess?: () => void, { reset = false } = {}) {
	let submitting = $state(false);

	const enhance: SubmitFunction = () => {
		submitting = true;
		return async ({ result, update }) => {
			submitting = false;
			if (result.type === 'success') onSuccess?.();
			await update({ reset });
		};
	};

	return {
		get submitting() {
			return submitting;
		},
		enhance
	};
}

/** A dialog form is the same thing, plus closing itself once it succeeds. */
export const createDialogSubmit = (close: () => void) => createSubmitFlag(close);

/**
 * The message an action left for one form, and nothing for any other. Five
 * pages had written this line out; `id` is for the actions that can fail for
 * one row in particular, as a test send can.
 */
export const messageFrom = (
	form: { action?: string; message?: string; id?: string } | null | undefined,
	action: string,
	id?: string
): string | undefined =>
	form?.action === action && (id === undefined || form.id === id) ? form.message : undefined;
