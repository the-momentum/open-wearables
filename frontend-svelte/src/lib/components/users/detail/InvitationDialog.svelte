<script lang="ts">
	import { env } from '$env/dynamic/public';
	import Alert from '$lib/components/ui/Alert.svelte';
	import CopyField from '$lib/components/ui/CopyField.svelte';
	import Sheet from '$lib/components/ui/Sheet.svelte';
	import type { InvitationCode } from '$lib/server/invitations';
	import { formatDateTime } from '$lib/utils/datetime';

	let {
		open = $bindable(false),
		invitation
	}: { open?: boolean; invitation: InvitationCode | null } = $props();
</script>

<Sheet bind:open title="Connect mobile app">
	<div class="flex flex-col gap-4 px-4 pb-2">
		<p class="text-sm text-muted-foreground">
			Enter these in the Open Wearables app. The code is single use and issuing it expires any
			earlier one.
		</p>

		{#if env.VITE_API_URL}
			<CopyField label="API URL" value={env.VITE_API_URL} />
		{:else}
			<Alert>No VITE_API_URL is configured, so the address a device should dial is unknown.</Alert>
		{/if}

		{#if invitation}
			<CopyField label="Invitation code" value={invitation.code} mono />
			<p class="text-xs text-muted-foreground">
				Expires {formatDateTime(invitation.expires_at)}
			</p>
		{/if}
	</div>
</Sheet>
