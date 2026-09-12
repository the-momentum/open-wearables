<script lang="ts">
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';
	import Pencil from '@lucide/svelte/icons/pencil';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import Badge from '$lib/components/ui/Badge.svelte';
	import DeleteUserDialog from '$lib/components/users/DeleteUserDialog.svelte';
	import UserAvatar from '$lib/components/users/UserAvatar.svelte';
	import UserFormDialog from '$lib/components/users/UserFormDialog.svelte';
	import type { InvitationCode } from '$lib/server/invitations';
	import { fullName } from '$lib/users/avatar';
	import type { UserDetail } from '$lib/users/types';
	import InvitationDialog from './InvitationDialog.svelte';
	import UserHeaderActions from './UserHeaderActions.svelte';
	import UserIdentityMeta from './UserIdentityMeta.svelte';

	let { user }: { user: UserDetail } = $props();

	let editing = $state(false);
	let deleting = $state(false);
	let inviting = $state(false);

	const name = $derived(fullName(user) || 'Unnamed user');

	// A layout is not given `form`, so the action results are read off the page.
	const form = $derived(
		page.form as { action?: string; message?: string; invitation?: InvitationCode } | null
	);
	const invitation = $derived(form?.action === 'invite' ? (form.invitation ?? null) : null);
	const messageFor = (action: string) => (form?.action === action ? form.message : undefined);

	$effect(() => {
		if (invitation) inviting = true;
	});
</script>

<div class="flex flex-col gap-3">
	<a
		href={resolve('/users')}
		class="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
	>
		<ArrowLeft size={16} aria-hidden="true" />
		Users
	</a>

	<!-- No flex-wrap: the identity block is min-w-0 and shrinks instead, so the
	     actions stay on the name's row rather than dropping to a line of their
	     own. On a phone only the menu is left there. -->
	<div class="flex items-start justify-between gap-3">
		<div class="flex min-w-0 items-start gap-3 sm:gap-4">
			<UserAvatar {user} size="lg" />
			<div class="min-w-0 flex-1">
				<div class="flex flex-wrap items-center gap-2">
					<h1 class="truncate text-xl font-semibold text-foreground sm:text-2xl">{name}</h1>
					<!-- Before the badge, so a narrow screen wraps the badge onto its own
					     line rather than leaving the pencil stranded there. -->
					<button
						type="button"
						onclick={() => (editing = true)}
						aria-label="Edit user"
						title="Edit user"
						class="grid size-8 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground"
					>
						<Pencil size={15} aria-hidden="true" />
					</button>
					{#if user.has_active_connection}
						<Badge tone="success">Connected</Badge>
					{:else}
						<Badge tone="neutral">No active connection</Badge>
					{/if}
				</div>
				<div class="mt-1">
					<UserIdentityMeta {user} />
				</div>
			</div>
		</div>

		<UserHeaderActions {user} ondelete={() => (deleting = true)} />
	</div>
</div>

<UserFormDialog bind:open={editing} {user} message={messageFor('update')} />

<DeleteUserDialog bind:open={deleting} {user} message={messageFor('delete')} />

<InvitationDialog bind:open={inviting} {invitation} />
