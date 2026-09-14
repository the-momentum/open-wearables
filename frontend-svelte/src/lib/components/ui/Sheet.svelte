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

<!-- Bottom sheet on a phone, centred panel from sm up. Setting both insets
     stretches the box, so the phone pins with top-auto and the centred panel
     needs h-fit for margin:auto to have anything to centre. -->
<dialog
	bind:this={dialog}
	onclose={() => (open = false)}
	onclick={(event) => {
		// A click on the dialog itself is the backdrop; the panel stops its own.
		if (event.target === dialog) open = false;
	}}
	aria-labelledby={headingId}
	class="fixed inset-x-0 top-auto bottom-0 m-0 h-auto max-h-[85dvh] w-full max-w-none rounded-t-2xl
		bg-surface p-0 text-foreground backdrop:bg-black/50
		sm:inset-0 sm:m-auto sm:h-fit sm:max-h-[80dvh] sm:w-[min(28rem,calc(100vw-2rem))] sm:rounded-2xl
		sm:border sm:border-border"
>
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div
		onclick={(event) => event.stopPropagation()}
		class="flex flex-col pb-[max(1rem,env(safe-area-inset-bottom))] sm:pb-4"
	>
		<!-- Drag affordance only makes sense on the bottom sheet. -->
		<div class="mx-auto mt-3 h-1 w-9 shrink-0 rounded-full bg-border sm:hidden"></div>

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

	/* The centred panel has nowhere to slide up from. */
	@media (min-width: 40rem) {
		dialog[open] {
			animation: scale-in 150ms ease-out;
		}

		@keyframes scale-in {
			from {
				opacity: 0;
				transform: scale(0.97);
			}
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
