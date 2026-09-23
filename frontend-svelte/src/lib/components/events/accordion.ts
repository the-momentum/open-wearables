/**
 * Whether a click on a card should open or close it. The whole card is the
 * target — its padding and gaps too, since a click there that does nothing
 * reads as broken — except for two things: a control the card carries, which
 * does its own job, and the end of a text selection, which is not a click.
 */
export function togglesCard(event: MouseEvent): boolean {
	const target = event.target as Element | null;
	const control = target?.closest('a, button, input, select, textarea, label');

	if (control && !control.matches('[data-accordion-toggle]')) return false;
	return !document.getSelection()?.toString();
}
