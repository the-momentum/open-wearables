<script lang="ts">
	import { enhance } from '$app/forms';
	import Alert from '$lib/components/ui/Alert.svelte';
	import DialogActions from '$lib/components/ui/DialogActions.svelte';
	import PasswordField from '$lib/components/ui/PasswordField.svelte';
	import Sheet from '$lib/components/ui/Sheet.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { MIN_PASSWORD_LENGTH } from '$lib/settings/password';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';

	let {
		open = $bindable(false),
		email,
		message
	}: { open?: boolean; email: string; message?: string } = $props();

	// Clears on success, unlike every other form here: leaving a password in the
	// box after it has been changed is the one case where keeping input is wrong.
	const submit = createSubmitFlag(() => (open = false), { reset: true });
</script>

<Sheet bind:open title="Change your password">
	<form
		method="POST"
		action="?/changePassword"
		class="flex flex-col gap-4 px-4 pb-2"
		use:enhance={submit.enhance}
	>
		{#if message}
			<Alert>{message}</Alert>
		{/if}

		<p class={MICRO}>
			For {email}. Sessions signed in elsewhere keep working until they expire.
		</p>

		<PasswordField
			name="current_password"
			label="Current password"
			autocomplete="current-password"
		/>
		<PasswordField
			name="new_password"
			label="New password"
			autocomplete="new-password"
			placeholder="At least {MIN_PASSWORD_LENGTH} characters"
		/>
		<PasswordField
			name="confirm_password"
			label="Confirm new password"
			autocomplete="new-password"
		/>

		<DialogActions
			oncancel={() => (open = false)}
			submitting={submit.submitting}
			submitLabel="Update password"
			busyLabel="Updating…"
		/>
	</form>
</Sheet>
