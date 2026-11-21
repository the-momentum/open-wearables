<script lang="ts">
	import type { Component } from 'svelte';
	import Info from '@lucide/svelte/icons/info';
	import Hint from '$lib/components/ui/Hint.svelte';
	import { ICON } from '$lib/components/ui/icon';
	import { MICRO, STAT } from '$lib/components/ui/typography';
	import { cn } from '$lib/utils/cn';

	type Figure = {
		label: string;
		value: string;
		/** The unabbreviated figure behind a compact one, shown on hover: "584612 event records". */
		exact?: string;
	};

	let {
		icon: Icon,
		label,
		value,
		exact,
		note,
		parts
	}: Figure & {
		icon: Component;
		/** A word about the figure itself - that it is an estimate, say. */
		note?: string;
		/**
		 * Always rendered, zero included: "0 day and session rows" says nothing has been rolled up,
		 * and leaving the row out says nothing at all.
		 */
		parts: Figure[];
	} = $props();

	// One part reads as a sentence ("90 connected"); several split the total into columns.
	const single = $derived(parts.length === 1);
</script>

{#snippet exactly(figure: Figure)}
	<span class="font-mono uppercase">{figure.exact} {figure.label}</span>
{/snippet}

<!-- The design's frame: a surface band round a card, from the two-column grid up.
     A phone stacks the tiles inside one shared band instead, which is the page's. -->
<div class="h-full sm:rounded-lg sm:border sm:border-border sm:bg-surface sm:p-1">
	<div
		class="flex h-full flex-col gap-3 rounded-lg border border-border-subtle bg-card p-4 sm:gap-4 sm:p-3.5"
	>
		<div class="flex items-center gap-2 sm:flex-col sm:items-stretch sm:gap-4">
			<div class="flex min-w-0 flex-1 items-center gap-2">
				<span
					aria-hidden="true"
					class="grid size-8 shrink-0 place-items-center rounded-lg bg-surface-muted text-foreground"
				>
					<Icon size={ICON.sm} />
				</span>
				<span class="truncate text-sm text-foreground">{label}</span>
			</div>

			<div class="flex shrink-0 flex-col items-end sm:h-14 sm:items-center sm:justify-center">
				<div class="flex items-center gap-1.5">
					<span class={STAT}>{value}</span>
					<!-- The exact figures are the desktop design's alone: the phone tile has
					     neither the info icon nor the bubbles. -->
					{#if exact}
						<span class="hidden sm:contents">
							<Hint label="Exact {label.toLowerCase()}">
								{#snippet trigger()}
									<Info size={ICON.sm} aria-hidden="true" class="text-muted-foreground" />
								{/snippet}
								{@render exactly({ label, value, exact })}
							</Hint>
						</span>
					{/if}
				</div>
				{#if note}<span class="text-xs text-foreground">{note}</span>{/if}
			</div>
		</div>

		<dl
			class={cn(
				'flex flex-1 border-t border-border-subtle pt-3 sm:pt-4',
				single ? 'items-center' : 'justify-between gap-4'
			)}
		>
			<!-- The term comes first, as a description list needs; the figure is drawn first. -->
			{#each parts as part, index (part.label)}
				<div
					class={cn(
						'flex min-w-0',
						single ? 'flex-row-reverse items-center justify-end gap-1.5' : 'flex-col-reverse'
					)}
				>
					<dt class="{MICRO} truncate">{part.label}</dt>
					<dd class="text-sm font-medium text-foreground tabular-nums">
						{#if part.exact}
							<span class="sm:hidden">{part.value}</span>
							<span class="hidden sm:contents">
								<Hint
									label="Exact {part.label}"
									align={index < parts.length / 2 ? 'left' : 'right'}
								>
									{#snippet trigger()}{part.value}{/snippet}
									{@render exactly(part)}
								</Hint>
							</span>
						{:else}
							{part.value}
						{/if}
					</dd>
				</div>
			{/each}
		</dl>
	</div>
</div>
