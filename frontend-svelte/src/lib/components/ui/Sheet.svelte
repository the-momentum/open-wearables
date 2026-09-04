<script lang="ts">
	import type { Snippet } from 'svelte';
	import X from '@lucide/svelte/icons/x';

	let {
		open = $bindable(false),
		title,
		children
	}: {
		open?: boolean;
		title: string;
		children: Snippet;
	} = $props();

	let dialog = $state<HTMLDialogElement>();
	const headingId = $props.id();

	// showModal() gives the focus trap, Esc and inert background for free.
	$effect(() => {
		if (!dialog) return;
		if (open && !dialog.open) dialog.showModal();
		if (!open && dialog.open) dialog.close();
	});

	// showModal() leaves the page scrollable behind the sheet.
	$effect(() => {
		if (!open) return;
		const previous = document.body.style.overflow;
		document.body.style.overflow = 'hidden';
		return () => {
			document.body.style.overflow = previous;
		};
	});
</script>

<!-- top-auto: setting both insets would stretch it to full height. -->
<dialog
	bind:this={dialog}
	onclose={() => (open = false)}
	onclick={(event) => {
		// A click on the dialog itself is the backdrop; the panel stops its own.
		if (event.target === dialog) open = false;
	}}
	aria-labelledby={headingId}
	class="fixed inset-x-0 top-auto bottom-0 m-0 h-auto max-h-[85dvh] w-full max-w-none
		rounded-t-2xl bg-surface p-0 text-foreground backdrop:bg-black/50"
>
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div
		onclick={(event) => event.stopPropagation()}
		class="flex flex-col pb-[max(1rem,env(safe-area-inset-bottom))]"
	>
		<div class="mx-auto mt-3 h-1 w-9 shrink-0 rounded-full bg-border"></div>

		<div class="flex items-center justify-between px-4 py-2">
			<h2 id={headingId} class="text-sm font-semibold">{title}</h2>
			<button
				type="button"
				onclick={() => (open = false)}
				aria-label="Close"
				class="grid size-9 place-items-center rounded-lg text-muted-foreground
					transition-colors hover:bg-surface-muted hover:text-foreground"
			>
				<X size={18} aria-hidden="true" />
			</button>
		</div>

		{@render children()}
	</div>
</dialog>

<style>
	dialog[open] {
		animation: slide-up 200ms cubic-bezier(0.32, 0.72, 0, 1);
	}

	dialog[open]::backdrop {
		animation: fade-in 200ms ease-out;
	}

	@keyframes slide-up {
		from {
			transform: translateY(100%);
		}
	}

	@keyframes fade-in {
		from {
			opacity: 0;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		dialog[open],
		dialog[open]::backdrop {
			animation: none;
		}
	}
</style>
