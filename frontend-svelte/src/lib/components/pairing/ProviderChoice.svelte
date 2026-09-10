<script lang="ts">
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import { enhance } from '$app/forms';
	import type { Provider } from '$lib/server/providers';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';
	import ProviderLogo from './ProviderLogo.svelte';

	let { provider, returnUrl }: { provider: Provider; returnUrl: string | null } = $props();

	const submit = createSubmitFlag();
</script>

<form method="POST" action="?/connect" use:enhance={submit.enhance}>
	<input type="hidden" name="provider" value={provider.provider} />
	{#if returnUrl}
		<input type="hidden" name="return_url" value={returnUrl} />
	{/if}
	<button
		type="submit"
		disabled={submit.submitting}
		class="flex w-full items-center gap-4 rounded-xl border border-border bg-surface p-4 text-left
			transition-colors hover:bg-surface-muted disabled:opacity-60"
	>
		<ProviderLogo {provider} />

		<span class="min-w-0 flex-1">
			<span class="block truncate font-medium text-foreground">{provider.name}</span>
			<span class="block text-xs text-muted-foreground">
				{submit.submitting ? 'Opening…' : 'Sign in to connect'}
			</span>
		</span>

		{#if submit.submitting}
			<LoaderCircle size={18} aria-hidden="true" class="shrink-0 animate-spin text-primary" />
		{:else}
			<ChevronRight size={18} aria-hidden="true" class="shrink-0 text-muted-foreground" />
		{/if}
	</button>
</form>
