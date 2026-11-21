<script lang="ts">
	import type { Snippet } from 'svelte';
	import Sidebar from './Sidebar.svelte';
	import TopBar from './TopBar.svelte';
	import BottomNav from './BottomNav.svelte';

	let { children }: { children: Snippet } = $props();
</script>

<!-- dvh, not vh: vh ignores the collapsing mobile address bar. With the sidebar,
     a page is one card-coloured panel on the grey page; a phone has no room for
     that frame, so there the page itself is the card. -->
<div class="min-h-dvh bg-card lg:bg-page">
	<Sidebar />

	<div class="lg:pl-64">
		<TopBar />

		<!-- Clears the fixed bottom bar plus the home indicator inset. -->
		<main class="px-4 pt-4 pb-[calc(4.5rem+env(safe-area-inset-bottom))] sm:px-6 lg:p-8">
			<div
				class="mx-auto flex w-full max-w-7xl flex-col gap-4 lg:rounded-xl lg:bg-card lg:p-6
					lg:shadow-elevation-s"
			>
				{@render children()}
			</div>
		</main>
	</div>

	<BottomNav />
</div>
