<script lang="ts">
	import ExpandChevron from '$lib/components/ui/ExpandChevron.svelte';
	import { TONE } from '$lib/components/ui/tone';
	import { MICRO, MONO } from '$lib/components/ui/typography';
	import { formatLocalTime } from '$lib/utils/format';
	import { hasContent, statusOf, triggerOf } from '$lib/webhooks/status';
	import type { Delivery } from '$lib/webhooks/types';

	let { delivery, expandable = false }: { delivery: Delivery; expandable?: boolean } = $props();

	let open = $state(false);
	const panelId = $props.id();
	const status = $derived(statusOf(delivery.status));

	const show = (value: unknown) =>
		typeof value === 'string' ? value : JSON.stringify(value, null, 2);

	const facts = $derived([
		['Attempt', triggerOf(delivery.triggerType)],
		['Sent', formatLocalTime(delivery.timestamp, null)],
		['Status', delivery.statusText || status.label],
		['Message', delivery.msgId]
	]);

	const parts = $derived([
		{ label: 'Event payload', value: delivery.msg?.payload as unknown },
		{ label: 'Response body', value: delivery.response as unknown }
	]);

	const ROW = 'flex w-full items-center gap-3 py-2 text-left';
</script>

{#snippet summary()}
	<!-- The HTTP code is what a reader checks first, so it wears the colour rather
	     than sitting in grey next to a dot that repeats it. -->
	<span class="w-11 shrink-0 rounded-md py-0.5 text-center tabular-nums {MONO} {TONE[status.tone]}">
		{delivery.responseStatusCode || '—'}
	</span>
	<span class="sr-only">{status.label}</span>

	<code class="min-w-0 flex-1 truncate font-mono text-xs text-foreground">
		{delivery.msg?.eventType ?? 'unknown event'}
	</code>

	{#if delivery.triggerType === 1}
		<span class="shrink-0 {MICRO}">retry</span>
	{/if}

	<span class="hidden shrink-0 tabular-nums sm:inline {MICRO}">{delivery.responseDurationMs}ms</span
	>
	<span class="shrink-0 whitespace-nowrap tabular-nums {MICRO}">
		{formatLocalTime(delivery.timestamp, null)}
	</span>
{/snippet}

<div>
	{#if expandable}
		<button
			type="button"
			onclick={() => (open = !open)}
			aria-expanded={open}
			aria-controls={panelId}
			class={ROW}
		>
			{@render summary()}
			<ExpandChevron {open} />
		</button>
	{:else}
		<div class={ROW}>{@render summary()}</div>
	{/if}

	{#if expandable && open}
		<div id={panelId} class="flex flex-col gap-3 pb-3">
			<dl class="flex flex-wrap gap-x-4 gap-y-1 {MICRO}">
				{#each facts as [label, value] (label)}
					<div class="flex gap-1.5">
						<dt class="text-muted-foreground/70">{label}</dt>
						<dd class="text-foreground/80">{value}</dd>
					</div>
				{/each}
			</dl>

			<p class="{MICRO} truncate">POST {delivery.url}</p>

			<!-- Side by side where there is room: a delivery is a round trip, and
			     reading what went out against what came back is the whole point. -->
			<div class="grid gap-3 lg:grid-cols-2">
				{#each parts as part (part.label)}
					<div class="flex min-w-0 flex-col gap-1">
						<span class={MICRO}>{part.label}</span>
						{#if hasContent(part.value)}
							<pre
								class="max-h-64 overflow-auto rounded-lg bg-surface-muted/60 p-2 whitespace-pre-wrap
									text-foreground/80 {MONO}">{show(part.value)}</pre>
						{:else}
							<p class="{MICRO} rounded-lg bg-surface-muted/40 p-2 italic">
								Not returned by the webhook service.
							</p>
						{/if}
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>
