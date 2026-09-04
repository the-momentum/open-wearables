<script lang="ts">
	import { enhance } from '$app/forms';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
	import Wordmark from '$lib/components/layout/Wordmark.svelte';
	import type { ActionData } from './$types';

	let { form }: { form: ActionData } = $props();

	let submitting = $state(false);
</script>

<svelte:head><title>Sign in · Open Wearables</title></svelte:head>

<main class="flex min-h-dvh flex-col justify-center px-5 py-10">
	<div class="mx-auto w-full max-w-sm">
		<div class="flex justify-center">
			<Wordmark class="h-12" />
		</div>

		<h1 class="mt-8 text-center text-lg font-semibold tracking-tight">Sign in</h1>
		<p class="mt-1 text-center text-sm text-muted-foreground">
			Use your Open Wearables developer account.
		</p>

		<!-- Works without JS; enhance only avoids the full page reload. -->
		<form
			method="POST"
			class="mt-7 flex flex-col gap-4"
			use:enhance={() => {
				submitting = true;
				return async ({ update }) => {
					await update();
					submitting = false;
				};
			}}
		>
			{#if form?.message}
				<p
					role="alert"
					class="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/10 px-3
						py-2 text-sm text-danger"
				>
					<TriangleAlert size={16} aria-hidden="true" class="mt-0.5 shrink-0" />
					{form.message}
				</p>
			{/if}

			<label class="flex flex-col gap-1.5">
				<span class="text-sm font-medium">Email</span>
				<input
					name="email"
					type="email"
					required
					autocomplete="username"
					value={form?.email ?? ''}
					class="min-h-11 rounded-lg border border-border bg-surface px-3 text-sm
						placeholder:text-muted-foreground/60"
				/>
			</label>

			<label class="flex flex-col gap-1.5">
				<span class="text-sm font-medium">Password</span>
				<input
					name="password"
					type="password"
					required
					autocomplete="current-password"
					class="min-h-11 rounded-lg border border-border bg-surface px-3 text-sm
						placeholder:text-muted-foreground/60"
				/>
			</label>

			<button
				type="submit"
				disabled={submitting}
				class="mt-1 inline-flex min-h-11 items-center justify-center gap-2 rounded-lg
					bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors
					hover:bg-primary-hover disabled:opacity-60"
			>
				{#if submitting}
					<LoaderCircle size={16} aria-hidden="true" class="animate-spin" />
				{/if}
				{submitting ? 'Signing in…' : 'Sign in'}
			</button>
		</form>
	</div>
</main>
