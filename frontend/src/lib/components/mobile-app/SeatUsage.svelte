<script lang="ts">
	import Alert from '$lib/components/ui/Alert.svelte';
	import type { AppEntitlement } from '$lib/server/app-registration';

	let { entitlement }: { entitlement: AppEntitlement } = $props();

	const limit = $derived(entitlement.seat_limit);
	const full = $derived(limit !== null && entitlement.seats_used >= limit);
	const percent = $derived(limit ? Math.min(100, (entitlement.seats_used / limit) * 100) : 0);
</script>

<div class="flex flex-col gap-2">
	<p class="text-sm">
		{#if limit === null}
			<strong>{entitlement.seats_used}</strong> app seats used
		{:else}
			<strong>{entitlement.seats_used} of {limit}</strong> app seats used
		{/if}
		<span class="text-muted-foreground">· {entitlement.plan} plan</span>
	</p>
	{#if limit !== null}
		<div class="h-2 overflow-hidden rounded-full bg-surface-muted" aria-hidden="true">
			<div
				class="h-full rounded-full {full ? 'bg-warning' : 'bg-primary'}"
				style="width: {percent}%"
			></div>
		</div>
	{/if}
	{#if full}
		<Alert tone="warning">
			All seats are in use, so new people cannot connect the app{entitlement.rejected_claims_7d > 0
				? ` - ${entitlement.rejected_claims_7d} ${entitlement.rejected_claims_7d === 1 ? 'attempt was' : 'attempts were'} refused in the last 7 days`
				: ''}. Remove someone who no longer uses it, or upgrade your plan.
		</Alert>
	{/if}
</div>
