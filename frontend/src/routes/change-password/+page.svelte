<script lang="ts">
	import { enhance } from '$app/forms';
	import { resolve } from '$app/paths';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import PublicPage from '$lib/components/layout/PublicPage.svelte';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import PasswordField from '$lib/components/ui/PasswordField.svelte';
	import { INLINE_LINK } from '$lib/components/ui/typography';
	import { MIN_PASSWORD_LENGTH } from '$lib/settings/password';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';
	import type { ActionData, PageData } from './$types';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	const submit = createSubmitFlag();
</script>

<PublicPage
	title="Change the default password"
	description="{data.email} still uses the default password, which is public. Choose your own to continue."
>
	<form method="POST" action="?/change" class="flex flex-col gap-4" use:enhance={submit.enhance}>
		{#if form?.message}
			<Alert>{form.message}</Alert>
		{/if}

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

		<Button type="submit" disabled={submit.submitting} class="mt-1 w-full">
			{#if submit.submitting}
				<LoaderCircle size={16} aria-hidden="true" class="animate-spin" />
			{/if}
			{submit.submitting ? 'Updating…' : 'Update password'}
		</Button>
	</form>

	<div class="mt-6 flex justify-center gap-4 text-sm">
		{#if !data.required}
			<form method="POST" action="?/skip" use:enhance>
				<button type="submit" class={INLINE_LINK}>Not now</button>
			</form>
		{/if}
		<form method="POST" action={resolve('/logout')} use:enhance>
			<button type="submit" class="text-muted-foreground hover:underline">Sign out</button>
		</form>
	</div>
</PublicPage>
