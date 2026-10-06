<script lang="ts">
	import KeyRound from '@lucide/svelte/icons/key-round';
	import Pencil from '@lucide/svelte/icons/pencil';
	import Plus from '@lucide/svelte/icons/plus';
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Button from '$lib/components/ui/Button.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import ConfirmDialog from '$lib/components/ui/ConfirmDialog.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import { MONO } from '$lib/components/ui/typography';
	import NameDialog from '../NameDialog.svelte';
	import CredentialRow from './CredentialRow.svelte';
	import SecretReveal from './SecretReveal.svelte';
	import type { ApiKey } from '$lib/settings/types';

	let {
		keys,
		messageFor,
		secret
	}: {
		keys: ApiKey[];
		messageFor: (action: string) => string | undefined;
		secret?: { title: string; fields: { label: string; value: string }[] };
	} = $props();

	let createOpen = $state(false);
	let renaming = $state<ApiKey | null>(null);
	let renameOpen = $state(false);
	let subject = $state<ApiKey | null>(null);
	let rotateOpen = $state(false);
	let removeOpen = $state(false);

	const rename = (key: ApiKey) => {
		renaming = key;
		renameOpen = true;
	};
</script>

<Card
	icon={KeyRound}
	title="API keys"
	description="Authenticate API requests and embed widgets. The full key is shown only once, when it is created or rotated."
>
	{#snippet action()}
		<Button size="sm" onclick={() => (createOpen = true)}>
			<Plus size={14} aria-hidden="true" />
			New key
		</Button>
	{/snippet}

	{#if keys.length === 0}
		<EmptyState
			icon={KeyRound}
			title="No API keys yet"
			description="Create one to call the API from your own backend."
		/>
	{:else}
		<div class="divide-y divide-border">
			{#each keys as key (key.id)}
				<CredentialRow icon={KeyRound} name={key.name} created={key.created_at}>
					{#snippet identifier()}
						<code class="rounded bg-surface-muted px-1.5 py-0.5 {MONO}">{key.key_prefix}…</code>
					{/snippet}

					{#snippet actions()}
						<IconButton
							icon={RefreshCw}
							label="Rotate {key.name}"
							onclick={() => {
								subject = key;
								rotateOpen = true;
							}}
						/>
						<IconButton icon={Pencil} label="Rename {key.name}" onclick={() => rename(key)} />
						<IconButton
							icon={Trash2}
							label="Delete {key.name}"
							danger
							onclick={() => {
								subject = key;
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
	title="New API key"
	action="?/createKey"
	placeholder="Production backend"
	hint="A name you will recognise when there are several."
	submitLabel="Create key"
	busyLabel="Creating…"
	message={messageFor('createKey')}
/>

<NameDialog
	bind:open={renameOpen}
	title="Rename API key"
	action="?/renameKey"
	value={renaming?.name ?? ''}
	fields={{ id: renaming?.id ?? '' }}
	submitLabel="Save changes"
	busyLabel="Saving…"
	message={messageFor('renameKey')}
/>

<ConfirmDialog
	bind:open={rotateOpen}
	title="Rotate API key?"
	action="?/rotateKey"
	confirmLabel="Rotate key"
	busyLabel="Rotating…"
	fields={{ id: subject?.id ?? '' }}
	message={messageFor('rotateKey')}
>
	{subject?.name ?? 'This key'} stops working immediately and a new one is shown once. Anything still
	using it will start failing.
</ConfirmDialog>

<ConfirmDialog
	bind:open={removeOpen}
	title="Delete API key?"
	action="?/deleteKey"
	confirmLabel="Delete"
	busyLabel="Deleting…"
	destructive
	fields={{ id: subject?.id ?? '' }}
	message={messageFor('deleteKey')}
>
	{subject?.name ?? 'This key'} stops working immediately and cannot be brought back.
</ConfirmDialog>

<SecretReveal {secret} />
