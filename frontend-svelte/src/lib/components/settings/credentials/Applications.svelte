<script lang="ts">
	import Plus from '@lucide/svelte/icons/plus';
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';
	import Smartphone from '@lucide/svelte/icons/smartphone';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Button from '$lib/components/ui/Button.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import ConfirmDialog from '$lib/components/ui/ConfirmDialog.svelte';
	import CopyableId from '$lib/components/ui/CopyableId.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import NameDialog from '../NameDialog.svelte';
	import CredentialRow from './CredentialRow.svelte';
	import SecretReveal from './SecretReveal.svelte';
	import type { Application } from '$lib/settings/types';

	let {
		applications,
		messageFor,
		secret
	}: {
		applications: Application[];
		messageFor: (action: string) => string | undefined;
		secret?: { title: string; fields: { label: string; value: string }[] };
	} = $props();

	let createOpen = $state(false);
	let subject = $state<Application | null>(null);
	let rotateOpen = $state(false);
	let removeOpen = $state(false);
</script>

<Card
	icon={Smartphone}
	title="SDK applications"
	description="Credentials for mobile apps that push health data through the SDK. Keep the app secret on your own backend."
>
	{#snippet action()}
		<Button size="sm" onclick={() => (createOpen = true)}>
			<Plus size={14} aria-hidden="true" />
			New application
		</Button>
	{/snippet}

	{#if applications.length === 0}
		<EmptyState
			icon={Smartphone}
			title="No applications yet"
			description="Register one to authenticate your mobile app."
		/>
	{:else}
		<div class="divide-y divide-border">
			{#each applications as app (app.id)}
				<CredentialRow icon={Smartphone} name={app.name} created={app.created_at}>
					{#snippet identifier()}
						<CopyableId value={app.app_id} label="App ID" visible={24} />
					{/snippet}

					{#snippet actions()}
						<IconButton
							icon={RefreshCw}
							label="Rotate secret for {app.name}"
							onclick={() => {
								subject = app;
								rotateOpen = true;
							}}
						/>
						<IconButton
							icon={Trash2}
							label="Delete {app.name}"
							danger
							onclick={() => {
								subject = app;
								removeOpen = true;
							}}
						/>
					{/snippet}
				</CredentialRow>
			{/each}
		</div>
	{/if}
</Card>

<NameDialog
	bind:open={createOpen}
	title="New application"
	action="?/createApp"
	label="Application name"
	placeholder="My iOS app"
	hint="One per app you ship, so a leak can be rotated on its own."
	submitLabel="Create application"
	busyLabel="Creating…"
	message={messageFor('createApp')}
/>

<ConfirmDialog
	bind:open={rotateOpen}
	title="Rotate app secret?"
	action="?/rotateApp"
	confirmLabel="Rotate secret"
	busyLabel="Rotating…"
	fields={{ appId: subject?.app_id ?? '' }}
	message={messageFor('rotateApp')}
>
	Builds of {subject?.name ?? 'this app'} that carry the current secret stop authenticating immediately.
</ConfirmDialog>

<ConfirmDialog
	bind:open={removeOpen}
	title="Delete application?"
	action="?/deleteApp"
	confirmLabel="Delete"
	busyLabel="Deleting…"
	destructive
	fields={{ appId: subject?.app_id ?? '' }}
	message={messageFor('deleteApp')}
>
	{subject?.name ?? 'This application'} stops authenticating immediately and cannot be brought back.
</ConfirmDialog>

<SecretReveal {secret} />
