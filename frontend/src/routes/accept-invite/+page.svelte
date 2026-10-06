<script lang="ts">
	import { enhance } from '$app/forms';
	import { resolve } from '$app/paths';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import PublicPage from '$lib/components/layout/PublicPage.svelte';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import LinkButton from '$lib/components/ui/LinkButton.svelte';
	import PasswordField from '$lib/components/ui/PasswordField.svelte';
	import TextField from '$lib/components/ui/TextField.svelte';
	import { INLINE_LINK } from '$lib/components/ui/typography';
	import { MIN_PASSWORD_LENGTH } from '$lib/settings/password';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';
	import type { ActionData, PageData } from './$types';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	const submit = createSubmitFlag();

	// The API only judges a token when it is used; a missing one is known up front.
	const dead = $derived(data.token ? form?.dead : 'This invitation link is not valid');
</script>

{#if form?.joined}
	<PublicPage
		title="Your account is ready"
		description="Sign in as {form.joined} with the password you just chose."
	>
		<LinkButton href={resolve('/login')} class="w-full">Sign in</LinkButton>
	</PublicPage>
{:else if dead}
	<PublicPage title={dead} description="Ask whoever invited you to send a new invitation.">
		<p class="text-center text-sm text-muted-foreground">
			Already on the team? <a href={resolve('/login')} class={INLINE_LINK}>Sign in</a>
		</p>
	</PublicPage>
{:else}
	<PublicPage
		title="Join the team"
		description="Set up your developer account to accept the invitation."
	>
		<form method="POST" class="flex flex-col gap-4" use:enhance={submit.enhance}>
			{#if form?.message}
				<Alert>{form.message}</Alert>
			{/if}

			<div class="grid grid-cols-2 gap-3">
				<TextField
					name="first_name"
					label="First name"
					autocomplete="given-name"
					maxlength={100}
					required
					value={form?.first ?? ''}
				/>
				<TextField
					name="last_name"
					label="Last name"
					autocomplete="family-name"
					maxlength={100}
					required
					value={form?.last ?? ''}
				/>
			</div>

			<PasswordField
				name="password"
				label="Password"
				autocomplete="new-password"
				placeholder="At least {MIN_PASSWORD_LENGTH} characters"
			/>
			<PasswordField name="confirm_password" label="Confirm password" autocomplete="new-password" />

			<Button type="submit" disabled={submit.submitting} class="mt-1 w-full">
				{#if submit.submitting}
					<LoaderCircle size={16} aria-hidden="true" class="animate-spin" />
				{/if}
				{submit.submitting ? 'Creating your account…' : 'Join the team'}
			</Button>
		</form>

		<p class="mt-6 text-center text-sm text-muted-foreground">
			Already have an account? <a href={resolve('/login')} class={INLINE_LINK}>Sign in</a>
		</p>
	</PublicPage>
{/if}
