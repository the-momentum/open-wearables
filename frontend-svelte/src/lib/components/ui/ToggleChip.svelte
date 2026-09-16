<script lang="ts">
	import type { Snippet } from 'svelte';
	import { chipClass } from './chip';

	let {
		pressed = false,
		onclick,
		children
	}: { pressed?: boolean; onclick: () => void; children: Snippet } = $props();
</script>

<button type="button" {onclick} aria-pressed={pressed} class={chipClass(pressed)}>
	{@render children()}
</button>
