<script lang="ts">
	import type { Snippet } from 'svelte';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
	import { ICON } from './icon';

	let { tone = 'danger', children }: { tone?: 'danger' | 'warning'; children: Snippet } = $props();

	const STYLE = {
		danger: 'border-danger/30 bg-danger/8 text-danger',
		warning: 'border-warning/30 bg-warning/8 text-warning'
	} as const;
</script>

<!-- role="alert" interrupts, which is right for a rejected form and wrong for a
     caution the reader walked into on purpose. -->
<p
	role={tone === 'danger' ? 'alert' : undefined}
	class="flex items-start gap-2 rounded-lg border px-3 py-2 text-sm {STYLE[tone]}"
>
	<TriangleAlert size={ICON.sm} aria-hidden="true" class="mt-0.5 shrink-0" />
	{@render children()}
</p>
