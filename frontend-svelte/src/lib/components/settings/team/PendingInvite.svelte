<script lang="ts">
	import LinkIcon from '@lucide/svelte/icons/link';
	import RotateCw from '@lucide/svelte/icons/rotate-cw';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import { enhance } from '$app/forms';
	import Badge from '$lib/components/ui/Badge.svelte';
	import CopyButton from '$lib/components/ui/CopyButton.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';
	import { formatDate } from '$lib/utils/datetime';
	import { invitationTone, inviteLink } from '$lib/settings/invitations';
	import SettingRow from '../SettingRow.svelte';
	import type { Invitation } from '$lib/settings/types';

	let { invitation, onrevoke }: { invitation: Invitation; onrevoke: () => void } = $props();

	// Empty while this renders on the server; the browser re-runs it before a
	// click can reach the button.
	const origin = typeof location === 'undefined' ? '' : location.origin;
	const resend = createSubmitFlag();
</script>

<SettingRow>
	{#snippet title()}
		<span class="truncate text-sm font-medium text-foreground">{invitation.email}</span>
		<Badge tone={invitationTone(invitation.status)}>{invitation.status}</Badge>
	{/snippet}

	{#snippet meta()}
		<span>
			Sent {formatDate(invitation.created_at)} · expires {formatDate(invitation.expires_at)}
		</span>
	{/snippet}

	{#snippet actions()}
		<!-- The email can fail or be filtered, and then the link is the only way in. -->
		<CopyButton
			value={inviteLink(origin, invitation.token)}
			label="invite link"
			icon={LinkIcon}
			place="action"
		/>

		<form method="POST" action="?/resendInvite" use:enhance={resend.enhance} class="contents">
			<input type="hidden" name="id" value={invitation.id} />
			<IconButton
				type="submit"
				icon={RotateCw}
				label="Resend invitation to {invitation.email}"
				disabled={resend.submitting}
			/>
		</form>

		<IconButton
			icon={Trash2}
			label="Revoke invitation for {invitation.email}"
			danger
			onclick={onrevoke}
		/>
	{/snippet}
</SettingRow>
