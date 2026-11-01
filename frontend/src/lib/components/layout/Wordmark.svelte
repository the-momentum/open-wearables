<script lang="ts">
	import logotype from '$lib/assets/logotype.svg?raw';
	import { cn } from '$lib/utils/cn';

	let { class: className }: { class?: string } = $props();
</script>

<!-- Inlined, not an <img>: an <img> cannot inherit currentColor. -->
<span class={cn('inline-block text-foreground [&>svg]:h-full [&>svg]:w-auto', className)}>
	<!-- eslint-disable-next-line svelte/no-at-html-tags -- build-time asset, never user input -->
	{@html logotype}
</span>
