<script lang="ts">
	let { title }: { title: string } = $props();
</script>

<section class="rounded-xl border border-border bg-surface p-5">
	<h2 class="text-base font-semibold tracking-tight">{title}</h2>
	<p class="mt-1 text-sm text-muted-foreground">
		Not built yet. The shell and routing work; this page is a placeholder.
	</p>
</section>
