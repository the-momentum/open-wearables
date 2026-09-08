<script lang="ts">
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();
</script>

<!-- Button-shaped but a <p>: it states why there is nothing to press, and a
     disabled <button> would be announced as a control that is broken. -->
<p
	class="inline-flex min-h-11 items-center justify-center rounded-lg border border-dashed
		border-border px-3 text-xs text-muted-foreground"
>
	{@render children()}
</p>
