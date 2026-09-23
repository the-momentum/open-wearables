<script lang="ts">
	import type { Snippet } from 'svelte';
	import Wordmark from './Wordmark.svelte';

	let { title, description, children }: { title: string; description: string; children: Snippet } =
		$props();
</script>

<svelte:head><title>{title} · Open Wearables</title></svelte:head>

<!-- The pages reached without an account: signing in, and joining a team. -->
<main class="flex min-h-dvh flex-col justify-center px-5 py-10">
	<div class="mx-auto w-full max-w-sm">
		<div class="flex justify-center">
			<Wordmark class="h-12" />
		</div>

		<h1 class="mt-8 text-center text-lg font-semibold tracking-tight">{title}</h1>
		<p class="mt-1 text-center text-sm text-muted-foreground">{description}</p>

		<div class="mt-7">{@render children()}</div>
	</div>
</main>
