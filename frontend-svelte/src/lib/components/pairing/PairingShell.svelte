<script lang="ts">
	import type { Snippet } from 'svelte';
	import ShieldCheck from '@lucide/svelte/icons/shield-check';
	import Wordmark from '$lib/components/layout/Wordmark.svelte';

	let { title, lead, children }: { title: string; lead: string; children: Snippet } = $props();
</script>

<main class="flex min-h-dvh flex-col items-center px-4 py-10 sm:py-16">
	<div class="flex w-full max-w-lg flex-col items-center gap-8">
		<Wordmark class="h-12" />

		<div class="space-y-2 text-center">
			<h1 class="text-2xl font-semibold text-foreground sm:text-3xl">{title}</h1>
			<p class="text-sm text-muted-foreground">{lead}</p>
		</div>

		<div class="w-full">{@render children()}</div>

		<p class="flex items-center gap-2 text-xs text-muted-foreground">
			<ShieldCheck size={14} aria-hidden="true" />
			You sign in with the provider — we never see your password.
		</p>
	</div>
</main>
