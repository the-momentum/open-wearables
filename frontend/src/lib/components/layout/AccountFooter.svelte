<script lang="ts">
	import { cn } from '$lib/utils/cn';
	import AccountBadge from './AccountBadge.svelte';
	import AppVersion from './AppVersion.svelte';
	import LogoutButton from './LogoutButton.svelte';
	import ThemeSwitch from './ThemeSwitch.svelte';

	let { class: className }: { class?: string } = $props();
</script>

<!-- Under the sidebar on a desktop, and in the More sheet on a phone. -->
<div class={cn('flex flex-col', className)}>
	<div class="border-t border-border-subtle"></div>
	<AccountBadge />
	<div class="flex items-center gap-2 pr-1">
		<div class="min-w-0 flex-1"><LogoutButton /></div>
		<ThemeSwitch />
	</div>
	<AppVersion />
</div>
