<script lang="ts">
	import Clock from '@lucide/svelte/icons/clock';
	import UserPlus from '@lucide/svelte/icons/user-plus';
	import Users from '@lucide/svelte/icons/users';
	import { page } from '$app/state';
	import InviteDialog from '$lib/components/settings/team/InviteDialog.svelte';
	import PasswordDialog from '$lib/components/settings/team/PasswordDialog.svelte';
	import PendingInvite from '$lib/components/settings/team/PendingInvite.svelte';
	import TeamMember from '$lib/components/settings/team/TeamMember.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import ConfirmDialog from '$lib/components/ui/ConfirmDialog.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import { outstanding } from '$lib/settings/invitations';
	import type { Developer, Invitation } from '$lib/settings/types';
	import type { ActionData, PageData } from './$types';
	import { messageFrom } from '$lib/utils/forms.svelte';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	const messageFor = (action: string) => messageFrom(form, action);

	// The layout already knows who is signed in, so the row can say so.
	const me = $derived(page.data.developer?.id);
	const pending = $derived(outstanding(data.invitations));

	let inviteOpen = $state(false);
	let passwordOpen = $state(false);
	let removing = $state<Developer | null>(null);
	let removeOpen = $state(false);
	let revoking = $state<Invitation | null>(null);
	let revokeOpen = $state(false);
</script>

<div class="flex flex-col gap-5">
	{#if pending.length > 0}
		<Card
			icon={Clock}
			title="Pending invitations"
			description="Sent but not yet accepted. Each one expires on its own."
		>
			<div class="divide-y divide-border">
				{#each pending as invitation (invitation.id)}
					<PendingInvite
						{invitation}
						onrevoke={() => {
							revoking = invitation;
							revokeOpen = true;
						}}
					/>
				{/each}
			</div>
		</Card>
	{/if}

	<Card icon={Users} title="Developers" description="Everyone who can sign in to this dashboard.">
		{#snippet action()}
			<Button size="sm" onclick={() => (inviteOpen = true)}>
				<UserPlus size={14} aria-hidden="true" />
				Invite
			</Button>
		{/snippet}

		{#if data.developers.length === 0}
			<EmptyState icon={Users} title="No team members yet" />
		{:else}
			<div class="divide-y divide-border">
				{#each data.developers as developer (developer.id)}
					<TeamMember
						{developer}
						you={developer.id === me}
						onpassword={() => (passwordOpen = true)}
						onremove={() => {
							removing = developer;
							removeOpen = true;
						}}
					/>
				{/each}
			</div>
		{/if}
	</Card>
</div>

<InviteDialog bind:open={inviteOpen} message={messageFor('invite')} />

<PasswordDialog
	bind:open={passwordOpen}
	email={page.data.developer?.email ?? ''}
	message={messageFor('changePassword')}
/>

<ConfirmDialog
	bind:open={removeOpen}
	title="Remove team member?"
	action="?/removeMember"
	confirmLabel="Remove"
	busyLabel="Removing…"
	destructive
	fields={{ id: removing?.id ?? '' }}
	message={messageFor('removeMember')}
>
	{removing?.email ?? 'This developer'} loses access to this dashboard. The users and data they created
	stay.
</ConfirmDialog>

<ConfirmDialog
	bind:open={revokeOpen}
	title="Revoke invitation?"
	action="?/revokeInvite"
	confirmLabel="Revoke"
	busyLabel="Revoking…"
	destructive
	fields={{ id: revoking?.id ?? '' }}
	message={messageFor('revokeInvite')}
>
	The link sent to {revoking?.email ?? 'them'} stops working. You can invite them again later.
</ConfirmDialog>
