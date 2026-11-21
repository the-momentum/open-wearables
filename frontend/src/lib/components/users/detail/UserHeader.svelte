<script lang="ts">
	import Pencil from '@lucide/svelte/icons/pencil';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import BackLink from '$lib/components/ui/BackLink.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import DeleteUserDialog from '$lib/components/users/DeleteUserDialog.svelte';
	import UserAvatar from '$lib/components/users/UserAvatar.svelte';
	import UserFormDialog from '$lib/components/users/UserFormDialog.svelte';
	import type { InvitationCode } from '$lib/server/invitations';
	import { fullName } from '$lib/users/avatar';
	import type { User } from '$lib/users/types';
	import InvitationDialog from './InvitationDialog.svelte';
	import UserHeaderActions from './UserHeaderActions.svelte';
	import UserIdentityMeta from './UserIdentityMeta.svelte';
	import { messageFrom } from '$lib/utils/forms.svelte';

	let { user }: { user: User } = $props();

	let editing = $state(false);
	let deleting = $state(false);
	let inviting = $state(false);

	const name = $derived(fullName(user) || 'Unnamed user');

	// A layout is not given `form`, so the action results are read off the page.
	const form = $derived(
		page.form as { action?: string; message?: string; invitation?: InvitationCode } | null
	);
	const invitation = $derived(form?.action === 'invite' ? (form.invitation ?? null) : null);
	const messageFor = (action: string) => messageFrom(form, action);

	$effect(() => {
		if (invitation) inviting = true;
	});
</script>

<div class="flex flex-col gap-3">
	<BackLink href={resolve('/users')}>Users</BackLink>

	<!-- No flex-wrap: the identity block is min-w-0 and shrinks instead, so the
	     actions stay on the name's row rather than dropping to a line of their
	     own. On a phone only the menu is left there. -->
	<div class="flex items-start justify-between gap-4 sm:items-center">
		<div class="flex min-w-0 items-start gap-3 sm:items-center sm:gap-4">
			<UserAvatar {user} size="lg" />
			<div class="flex min-w-0 flex-1 flex-col gap-1.5 sm:gap-2">
				<div class="flex flex-wrap items-center gap-2">
					<h1 class="truncate text-xl font-medium text-foreground sm:text-2xl">{name}</h1>
					<!-- Before the badge, so a narrow screen wraps the badge onto its own
					     line rather than leaving the pencil stranded there. -->
					<IconButton
						icon={Pencil}
						label="Edit user"
						title="Edit user"
						onclick={() => (editing = true)}
						class="size-8"
					/>
					{#if user.has_active_connection}
						<Badge tone="success">Connected</Badge>
					{:else}
						<Badge tone="neutral">No active connection</Badge>
					{/if}
				</div>
				<UserIdentityMeta {user} />
			</div>
		</div>

		<UserHeaderActions {user} ondelete={() => (deleting = true)} />
	</div>
</div>

<UserFormDialog bind:open={editing} {user} message={messageFor('update')} />

<DeleteUserDialog bind:open={deleting} {user} message={messageFor('delete')} />

<InvitationDialog bind:open={inviting} {invitation} />
