<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import { buttonClass, type ButtonVariant } from './button';

	let {
		variant = 'primary',
		type = 'button',
		class: className,
		children,
		...rest
	}: HTMLButtonAttributes & {
		variant?: ButtonVariant;
		children: Snippet;
	} = $props();
</script>

<!-- Spreads the rest so callers keep control of aria-* and the like. -->
<button {type} {...rest} class={buttonClass(variant, className)}>
	{@render children()}
</button>
