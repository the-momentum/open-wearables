<script lang="ts">
	import Sparkles from '@lucide/svelte/icons/sparkles';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { cn } from '$lib/utils/cn';
	import { countsOf } from '$lib/seed/summary';
	import type { SeedPreset } from '$lib/seed/types';

	let {
		presets,
		active,
		onpick
	}: { presets: SeedPreset[]; active: string | null; onpick: (preset: SeedPreset) => void } =
		$props();
</script>

<Card
	icon={Sparkles}
	title="Start from a preset"
	description="Everything below follows it; change anything and it becomes your own."
>
	{#snippet action()}
		{#if active === null}<Badge tone="primary">Custom</Badge>{/if}
	{/snippet}

	<ul class="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
		{#each presets as preset (preset.id)}
			{@const on = preset.id === active}
			<li>
				<button
					type="button"
					aria-pressed={on}
					onclick={() => onpick(preset)}
					class={cn(
						'flex size-full flex-col gap-1 rounded-lg border px-3 py-2.5 text-left transition-colors',
						on ? 'border-primary bg-primary/5' : 'border-border hover:bg-surface'
					)}
				>
					<span class="text-sm font-medium {on ? 'text-primary' : 'text-foreground'}">
						{preset.label}
					</span>
					<span class={MICRO}>{preset.description}</span>
					<span class="mt-auto pt-1 text-xs text-muted-foreground/80 tabular-nums">
						{countsOf(preset.profile).join(', ')}
					</span>
				</button>
			</li>
		{/each}
	</ul>
</Card>
