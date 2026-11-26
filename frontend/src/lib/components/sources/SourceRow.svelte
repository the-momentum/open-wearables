<script lang="ts">
	import { ICON } from '$lib/components/ui/icon';
	import { MICRO } from '$lib/components/ui/typography';
	import { deviceIcon, deviceLabel } from '$lib/providers/devices';
	import { deviceOf, sourceDetail, sourceTitle } from '$lib/sources/sources';
	import type { DataSource } from '$lib/sources/types';
	import { cn } from '$lib/utils/cn';

	let { source }: { source: DataSource } = $props();

	const DeviceIcon = $derived(deviceIcon(source.device_type));
	const detail = $derived(sourceDetail(source));
	const facts = $derived(
		[
			source.device_type ? deviceLabel(source.device_type) : null,
			source.software_version ? `v${source.software_version}` : null
		].filter(Boolean)
	);
</script>

<!-- Each line always means one thing: the device and its facts, then where the data came from. -->
<li class="flex items-center gap-3 px-4 py-3 sm:px-5">
	<span
		aria-hidden="true"
		class="grid size-8 shrink-0 place-items-center rounded-lg bg-surface-muted text-muted-foreground"
	>
		<DeviceIcon size={ICON.sm} />
	</span>
	<div class="flex min-w-0 flex-1 flex-col gap-0.5">
		<div class="flex min-w-0 items-baseline gap-3">
			<span
				class={cn(
					'truncate text-sm font-medium',
					deviceOf(source) ? 'text-foreground' : 'text-muted-foreground'
				)}
			>
				{sourceTitle(source)}
			</span>
			{#each facts as fact (fact)}
				<span class="{MICRO} shrink-0 whitespace-nowrap">{fact}</span>
			{/each}
		</div>
		{#if detail}
			<span class="truncate text-xs text-secondary-foreground" title={detail}>
				<span class="text-muted-foreground">Source:</span>
				{detail}
			</span>
		{/if}
	</div>
</li>
