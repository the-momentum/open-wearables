<script lang="ts">
	import type { Snippet } from 'svelte';
	import UserHeader from '$lib/components/users/detail/UserHeader.svelte';
	import UserTabs from '$lib/components/users/detail/UserTabs.svelte';
	import type { LayoutData } from './$types';

	let { data, children }: { data: LayoutData; children: Snippet } = $props();
</script>

<div class="flex flex-col gap-5">
	<UserHeader user={data.user} />
	<UserTabs user={data.user} />
	{@render children()}
</div>
