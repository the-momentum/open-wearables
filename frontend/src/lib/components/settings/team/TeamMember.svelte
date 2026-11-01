<script lang="ts">
	import KeyRound from '@lucide/svelte/icons/key-round';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import CopyableId from '$lib/components/ui/CopyableId.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import { formatDate } from '$lib/utils/datetime';
	import SettingRow from '../SettingRow.svelte';
	import type { Developer } from '$lib/settings/types';

	let {
		developer,
		you,
		onremove,
		onpassword
	}: {
		developer: Developer;
		/** The signed-in account cannot remove itself, so it says which one it is. */
		you: boolean;
		onremove: () => void;
		/** Your own password is a property of your account, so it is offered here. */
		onpassword: () => void;
	} = $props();

	const name = $derived([developer.first_name, developer.last_name].filter(Boolean).join(' '));
</script>

<SettingRow>
	{#snippet title()}
		<span class="truncate text-sm font-medium text-foreground">{developer.email}</span>
		{#if you}<Badge tone="primary">You</Badge>{/if}
	{/snippet}

	{#snippet meta()}
		{#if name}<span class="truncate">{name}</span>{/if}
		<CopyableId value={developer.id} label="Developer ID" />
		<span>Joined {formatDate(developer.created_at)}</span>
	{/snippet}

	{#snippet actions()}
		{#if you}
			<Button variant="outline" size="sm" onclick={onpassword}>
				<KeyRound size={13} aria-hidden="true" />
				Change password
			</Button>
		{:else}
			<IconButton icon={Trash2} label="Remove {developer.email}" danger onclick={onremove} />
		{/if}
	{/snippet}
</SettingRow>
