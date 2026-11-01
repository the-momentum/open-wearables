/** The API's own floor (`minLength: 8` on every password it accepts). */
export const MIN_PASSWORD_LENGTH = 8;

/** Checked before the API: its 422 has no readable `detail`, and it never sees the confirmation. */
export function newPasswordProblem(password: string, confirmation: string): string | null {
	if (password.length < MIN_PASSWORD_LENGTH) {
		return `The password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
	}
	if (password !== confirmation) return 'The confirmation does not match the password.';
	return null;
}
