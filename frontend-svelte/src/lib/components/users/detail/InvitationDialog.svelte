<script lang="ts">
	import { publicApiUrl } from '$lib/config/public-api';
	import Alert from '$lib/components/ui/Alert.svelte';
	import CopyField from '$lib/components/ui/CopyField.svelte';
	import Sheet from '$lib/components/ui/Sheet.svelte';
	import type { InvitationCode } from '$lib/server/invitations';
	import { formatDateTime } from '$lib/utils/datetime';

	let {
		open = $bindable(false),
		invitation
	}: { open?: boolean; invitation: InvitationCode | null } = $props();

	const apiUrl = publicApiUrl();
</script>

<Sheet bind:open title="Connect mobile app">
	<div class="flex flex-col gap-4 px-4 pb-2">
		<p class="text-sm text-muted-foreground">
			Enter these in the Open Wearables app. The code is single use and issuing it expires any
			earlier one.
		</p>

		{#if apiUrl}
			<CopyField label="API URL" value={apiUrl} />
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
