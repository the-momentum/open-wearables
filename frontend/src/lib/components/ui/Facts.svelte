<script lang="ts">
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();
</script>

<!-- A wrapping row of <Fact>s. -->
<dl class="flex flex-wrap gap-x-6 gap-y-2 text-sm">{@render children()}</dl>
