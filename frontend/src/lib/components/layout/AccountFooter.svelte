<script lang="ts">
	import { cn } from '$lib/utils/cn';
	import AccountBadge from './AccountBadge.svelte';
	import AppVersion from './AppVersion.svelte';
	import LogoutButton from './LogoutButton.svelte';
	import ThemeSwitch from './ThemeSwitch.svelte';

	let { class: className }: { class?: string } = $props();
</script>

<!-- Under the sidebar on a desktop, and in the More sheet on a phone. -->
<div class="mx-3 border-t border-border/60"></div>
<div class={cn('px-3', className)}>
	<AccountBadge />
	<div class="flex items-center gap-2 pr-1">
		<div class="min-w-0 flex-1"><LogoutButton /></div>
		<ThemeSwitch />
	</div>
	<AppVersion />
</div>
