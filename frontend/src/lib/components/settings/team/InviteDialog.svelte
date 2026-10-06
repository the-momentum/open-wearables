<script lang="ts">
	import { enhance } from '$app/forms';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import CopyField from '$lib/components/ui/CopyField.svelte';
	import DialogActions from '$lib/components/ui/DialogActions.svelte';
	import Sheet from '$lib/components/ui/Sheet.svelte';
	import TextField from '$lib/components/ui/TextField.svelte';
	import { inviteLink } from '$lib/settings/invitations';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';

	let {
		open = $bindable(false),
		message,
		emailEnabled
	}: { open?: boolean; message?: string; emailEnabled: boolean } = $props();

	const EMAIL_DOCS = 'https://openwearables.io/docs/developer-portal/settings/team#email-delivery';

	let email = $state('');
	// Without email the link is the invitation, so the dialog stays to hand it over.
	let link = $state<string | null>(null);

	const submit = createSubmitFlag((data) => {
		if (!emailEnabled && typeof data?.token === 'string') {
			link = inviteLink(location.origin, data.token);
		} else open = false;
	});

	$effect(() => {
		if (open) {
			email = '';
			link = null;
		}
	});
</script>

<Sheet bind:open title={link ? 'Invitation created' : 'Invite a developer'}>
	{#if link}
		<div class="flex flex-col gap-4 px-4 pb-2">
			<p class="text-sm text-muted-foreground">
				Share this link with {email}. It works until the invitation expires.
			</p>
			<CopyField label="Invite link" value={link} />
			<div class="mt-1 flex justify-end">
				<Button onclick={() => (open = false)}>Done</Button>
			</div>
		</div>
	{:else}
		<form
			method="POST"
			action="?/invite"
			class="flex flex-col gap-4 px-4 pb-2"
			use:enhance={submit.enhance}
		>
			{#if message}
				<Alert>{message}</Alert>
			{/if}

			{#if !emailEnabled}
				<Alert tone="warning">
					<span>
						Email delivery is not configured on this instance, so no email is sent. Create a link
						and share it yourself, or configure SMTP or Resend as the
						<a href={EMAIL_DOCS} target="_blank" rel="noopener noreferrer" class="underline"
							>team settings guide</a
						> describes.
					</span>
				</Alert>
			{/if}

			<TextField
				name="email"
				type="email"
				label="Email address"
				placeholder="colleague@example.com"
				hint={emailEnabled
					? 'They get a link by email. If it does not arrive, the link can be copied from the list.'
					: undefined}
				required
				bind:value={email}
			/>

			<DialogActions
				oncancel={() => (open = false)}
				submitting={submit.submitting}
				submitLabel={emailEnabled ? 'Send invitation' : 'Create invite link'}
				busyLabel={emailEnabled ? 'Sending…' : 'Creating…'}
			/>
		</form>
	{/if}
</Sheet>
