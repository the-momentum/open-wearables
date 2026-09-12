<script lang="ts">
	import type { Snippet } from 'svelte';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';

	let { children }: { children: Snippet } = $props();
</script>

<p
	role="alert"
	class="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2
		text-sm text-danger"
>
	<TriangleAlert size={16} aria-hidden="true" class="mt-0.5 shrink-0" />
	{@render children()}
</p>
