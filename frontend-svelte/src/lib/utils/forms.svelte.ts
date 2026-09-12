import type { SubmitFunction } from '@sveltejs/kit';

/**
 * Shared submit behaviour: track submission and never reset — fields are bound
 * to local state, and a failed submit must keep what was typed.
 */
export function createSubmitFlag(onSuccess?: () => void) {
	let submitting = $state(false);

	const enhance: SubmitFunction = () => {
		submitting = true;
		return async ({ result, update }) => {
			submitting = false;
			if (result.type === 'success') onSuccess?.();
			await update({ reset: false });
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
