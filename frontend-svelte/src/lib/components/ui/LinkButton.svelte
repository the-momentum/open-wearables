<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLAnchorAttributes } from 'svelte/elements';
	import { buttonClass, type ButtonVariant } from './button';

	let {
		variant = 'primary',
		class: className,
		children,
		...rest
	}: HTMLAnchorAttributes & {
		variant?: ButtonVariant;
		children: Snippet;
	} = $props();
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -- the caller resolves -->
<a {...rest} class={buttonClass(variant, className)}>
	{@render children()}
</a>
