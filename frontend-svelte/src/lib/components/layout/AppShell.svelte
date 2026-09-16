<script lang="ts">
	import type { Snippet } from 'svelte';
	import Sidebar from './Sidebar.svelte';
	import TopBar from './TopBar.svelte';
	import BottomNav from './BottomNav.svelte';

	let { children }: { children: Snippet } = $props();
</script>

<!-- dvh, not vh: vh ignores the collapsing mobile address bar. -->
<div class="min-h-dvh">
	<Sidebar />

	<div class="lg:pl-64">
		<TopBar />

		<!-- Clears the fixed bottom bar plus the home indicator inset. -->
		<main
			class="mx-auto w-full max-w-6xl px-4 py-5 pb-[calc(4.5rem+env(safe-area-inset-bottom))]
				sm:px-6 lg:pb-10"
		>
			{@render children()}
		</main>
	</div>

	<BottomNav />
</div>
