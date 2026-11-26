<script lang="ts">
	import { AVATAR_TONE, initials } from '$lib/users/avatar';
	import { cn } from '$lib/utils/cn';
	import type { User } from '$lib/users/types';

	let { user, size = 'md' }: { user: User; size?: 'md' | 'lg' } = $props();

	const SIZE = { md: 'size-9 text-xs', lg: 'size-12 text-sm sm:size-14 sm:text-base' } as const;
</script>

<span
	aria-hidden="true"
	class={cn('grid shrink-0 place-items-center rounded-full font-medium', SIZE[size], AVATAR_TONE)}
>
	{initials(user)}
</span>
