<script lang="ts">
	import { cn } from '$lib/utils/cn';

	let { value, class: className = '' }: { value: number; class?: string } = $props();
</script>

<!-- Capped in width: full width it outweighed the badge beside it. -->
<span
	class={cn('block h-1 w-full max-w-48 overflow-hidden rounded-full bg-surface-muted', className)}
	role="progressbar"
	aria-valuenow={Math.round(value * 100)}
	aria-valuemin="0"
	aria-valuemax="100"
	aria-label="Sync progress"
>
	<span class="block h-full rounded-full bg-primary/60" style="width: {value * 100}%"></span>
</span>
