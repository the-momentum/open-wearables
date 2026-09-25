<script lang="ts">
	let { dates }: { dates: string[] } = $props();

	const month = new Intl.DateTimeFormat('en-GB', { month: 'short', timeZone: 'UTC' });

	// Twelve month starts collide into one smear on a phone, so beyond four only
	// every third survives at narrow widths.
	const ticks = $derived.by(() => {
		const starts = dates
			.map((date, index) => ({ date, index }))
			.filter(
				({ date, index }) => index === 0 || date.slice(0, 7) !== dates[index - 1].slice(0, 7)
			);

		const sparse = starts.length > 4;
		return starts.map((start, rank) => ({
			...start,
			label: month.format(new Date(`${start.date}T00:00:00Z`)),
			always: !sparse || rank % 3 === 0
		}));
	});

	const labelAt = $derived(new Map(ticks.map((tick) => [tick.index, tick])));
</script>

<div class="flex h-5 items-end">
	{#each dates as date, index (date)}
		{@const tick = labelAt.get(index)}
		<span class="relative flex-1">
			{#if tick}
				<span aria-hidden="true" class="absolute bottom-0 left-0 h-1 w-px bg-border"></span>
				<span
					class="absolute bottom-1.5 left-0 text-[10px] leading-none whitespace-nowrap
						text-muted-foreground/70 {tick.always ? '' : 'hidden sm:inline'}"
				>
					{tick.label}
				</span>
			{/if}
		</span>
	{/each}
</div>
