<script lang="ts">
	import { AVATAR_TONE, initials } from '$lib/users/avatar';
	import { cn } from '$lib/utils/cn';
	import type { User } from '$lib/users/types';

	let { developer }: { developer: Pick<User, 'first_name' | 'last_name' | 'email'> } = $props();
</script>

<span
	aria-hidden="true"
	class={cn(
		'grid size-8 shrink-0 place-items-center rounded-full text-xs font-medium',
		AVATAR_TONE
	)}
>
	{initials(developer)}
</span>
