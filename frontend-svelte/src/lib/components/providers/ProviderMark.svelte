<script lang="ts">
	import { avatarTone } from '$lib/users/avatar';
	import { cn } from '$lib/utils/cn';

	let {
		provider,
		label,
		size = 'md'
	}: { provider: string; label: string; size?: 'sm' | 'md' | 'lg' } = $props();

	const SIZE = {
		sm: 'size-6 text-[10px]',
		md: 'size-9 text-xs',
		lg: 'size-16 rounded-xl text-base'
	} as const;
</script>

<!-- Letters where a logo would not fit, and what a logo falls back to when the
     API has none to serve. -->
<span
	aria-hidden="true"
	class={cn(
		'grid shrink-0 place-items-center rounded-lg font-semibold',
		SIZE[size],
		avatarTone(provider)
	)}
>
	{label.slice(0, 2).toUpperCase()}
</span>
