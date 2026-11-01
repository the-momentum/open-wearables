<script lang="ts">
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';
	import type { Snippet } from 'svelte';

	let { href, children }: { href: string; children: Snippet } = $props();
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -- the caller resolves -->
<a
	{href}
	class="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors
		hover:text-foreground"
>
	<ArrowLeft size={16} aria-hidden="true" />
	{@render children()}
</a>
