<script lang="ts">
	import ExpandChevron from '$lib/components/ui/ExpandChevron.svelte';
	import StatusCode from '$lib/components/ui/StatusCode.svelte';
	import { MICRO, MONO } from '$lib/components/ui/typography';
	import { cn } from '$lib/utils/cn';
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
</script>

{#snippet summary(stacked: boolean)}
	<StatusCode code={delivery.responseStatusCode} tone={status.tone} />
	<span class="sr-only">{status.label}</span>

	<code class="min-w-0 flex-1 truncate font-mono text-xs text-foreground">
		{delivery.msg?.eventType ?? 'unknown event'}
	</code>

	<span
		class={cn(
			'flex shrink-0 items-center gap-3 whitespace-nowrap tabular-nums',
			MICRO,
			stacked && 'max-sm:basis-full'
		)}
	>
		{#if delivery.triggerType === 1}<span>retry</span>{/if}
		<span>{delivery.responseDurationMs}ms</span>
		<span>{formatLocalTime(delivery.timestamp, null)}</span>
	</span>
{/snippet}

{#if expandable}
	<button
		type="button"
		onclick={() => (open = !open)}
		aria-expanded={open}
		aria-controls={panelId}
		class="flex w-full items-center gap-2 p-4 text-left transition-colors hover:bg-surface"
	>
		{@render summary(false)}
		<ExpandChevron {open} />
	</button>

	{#if open}
		<div id={panelId} class="flex flex-col gap-3 px-4 pb-4">
			<hr class="border-border" />
			<dl class="flex flex-col gap-1 sm:flex-row sm:flex-wrap sm:gap-x-6 {MICRO}">
				{#each facts as [label, value] (label)}
					<div class="flex min-w-0 gap-1.5">
						<dt>{label}</dt>
						<dd class="min-w-0 break-all text-secondary-foreground">{value}</dd>
					</div>
				{/each}
			</dl>

			<p class="{MICRO} break-all">POST {delivery.url}</p>

			<!-- Side by side where there is room: a delivery is a round trip, and
			     reading what went out against what came back is the whole point. -->
			<div class="grid gap-3 lg:grid-cols-2">
				{#each parts as part (part.label)}
					<div class="flex min-w-0 flex-col gap-1.5">
						<span class={MICRO}>{part.label}</span>
						{#if hasContent(part.value)}
							<pre
								class="max-h-64 overflow-auto rounded-lg border border-border p-2 whitespace-pre-wrap
									text-foreground {MONO}">{show(part.value)}</pre>
						{:else}
							<p class="{MICRO} rounded-lg border border-border p-2">
								Not returned by the webhook service.
							</p>
						{/if}
					</div>
				{/each}
			</div>
		</div>
	{/if}
{:else}
	<!-- In a card's short list a phone moves the timing under the event, as the design does. -->
	<div class="flex flex-wrap items-center gap-x-2 gap-y-1">{@render summary(true)}</div>
{/if}
