<script lang="ts">
	import { cn } from '$lib/utils/cn';

	let { rank }: { rank: number } = $props();
</script>

<!-- The top of the list is the one that wins, so it stands out a step. Hidden
     from assistive tech: the <ol> it sits in already says the position. -->
<span
	aria-hidden="true"
	class={cn(
		'grid size-6 shrink-0 place-items-center rounded-md border text-xs font-medium tabular-nums',
		rank === 1
			? 'border-border bg-surface-muted text-foreground'
			: 'border-border-subtle bg-surface text-muted-foreground'
	)}
>
	{rank}
</span>
