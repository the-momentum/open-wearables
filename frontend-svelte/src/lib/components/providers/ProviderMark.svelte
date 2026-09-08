<script lang="ts">
	import { avatarTone } from '$lib/users/avatar';
	import { cn } from '$lib/utils/cn';

	let {
		provider,
		label,
		size = 'md'
	}: { provider: string; label: string; size?: 'sm' | 'md' } = $props();

	const SIZE = { sm: 'size-6 text-[10px]', md: 'size-9 text-xs' } as const;
</script>

<!-- The API serves provider icons at a path the browser cannot reach under
     cookie sessions, so this is a letter mark until a proxy route exists. -->
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
