<script lang="ts">
	import type { Snippet } from 'svelte';
	import { chipClass } from './chip';

	let {
		href,
		selected = false,
		children
	}: { href: string; selected?: boolean; children: Snippet } = $props();
</script>

<!-- A link, not a button: filters belong in the URL, and Back should undo one. -->
<!-- eslint-disable svelte/no-navigation-without-resolve -->
<a {href} aria-current={selected ? 'true' : undefined} class={chipClass(selected)}>
	{@render children()}
</a>
