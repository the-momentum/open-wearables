<script lang="ts">
	import type { Snippet } from 'svelte';
	import UserHeader from '$lib/components/users/detail/UserHeader.svelte';
	import UserTabs from '$lib/components/users/detail/UserTabs.svelte';
	import PendingOutlet from '$lib/components/layout/PendingOutlet.svelte';
	import { userTabHref } from '$lib/users/tabs';
	import type { LayoutData } from './$types';

	let { data, children }: { data: LayoutData; children: Snippet } = $props();
</script>

<UserHeader user={data.user} />
<UserTabs user={data.user} />
<PendingOutlet within={userTabHref(data.user.id, '')}>{@render children()}</PendingOutlet>
