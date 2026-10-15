<script lang="ts">
	import { slowNavigation } from '$lib/utils/navigation.svelte';

	const slow = slowNavigation();
</script>

{#if slow.target}
	<div
		role="progressbar"
		aria-label="Loading"
		class="fixed inset-x-0 top-0 z-50 h-0.5 overflow-hidden bg-primary/15"
	>
		<div class="h-full w-1/3 animate-progress bg-primary"></div>
	</div>
{/if}
