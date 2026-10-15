<script lang="ts">
	import Badge from '$lib/components/ui/Badge.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { deviceIcon, deviceLabel } from '$lib/providers/devices';
	import { sourceDetail, sourceTitle } from '$lib/sources/sources';
	import type { DataSource } from '$lib/sources/types';
	import { cn } from '$lib/utils/cn';

	let { source, preferred = false }: { source: DataSource; preferred?: boolean } = $props();

	const DeviceIcon = $derived(deviceIcon(source.device_type));
	const detail = $derived(sourceDetail(source));
	const facts = $derived(
		[
			source.device_type ? deviceLabel(source.device_type) : null,
			source.software_version ? `v${source.software_version}` : null
		].filter(Boolean)
	);
</script>

<li class="flex items-start gap-3 px-4 py-3 sm:px-5">
	<span
		aria-hidden="true"
		class="grid size-8 shrink-0 place-items-center rounded-lg bg-surface-muted text-muted-foreground"
	>
		<DeviceIcon size={16} />
	</span>
	<div class="flex min-w-0 flex-1 flex-col gap-0.5">
		<div class="flex min-w-0 items-center gap-2">
			<span
				class={cn(
					'truncate text-sm font-medium',
					source.device_name ? 'text-foreground' : 'text-muted-foreground'
				)}
			>
				{sourceTitle(source)}
			</span>
			{#if preferred}
				<Badge tone="primary">Preferred</Badge>
			{/if}
		</div>
		{#if detail}
			<span class="truncate text-xs text-secondary-foreground" title={detail}>{detail}</span>
		{/if}
		{#if facts.length}
			<span class={MICRO}>{facts.join(' · ')}</span>
		{/if}
	</div>
</li>
