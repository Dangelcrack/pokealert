"""Comando de gestión para generar históricos de precio ausentes.

Este comando crea entradas de `PriceHistory` para cartas que no tienen registros
previos, usando `Card.price` como referencia cuando está disponible."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from cards.models import Card
from alerts.models import PriceHistory


class Command(BaseCommand):
    """Comando para generar `PriceHistory` faltantes a partir de `Card.price`.

    Útil para rellenar series históricas cuando se migró desde un sistema que
    no generaba históricos diarios. Soporta el argumento `--days` para limitar
    la creación a cartas sin histórico en los últimos N días."""

    help = (
        "Genera entradas de PriceHistory para cartas que no tienen histórico. "
        "Usa el precio actual guardado en `Card.price` cuando esté disponible."
    )

    def add_arguments(self, parser):
        """Define argumentos CLI para el comando (`--days`)."""
        parser.add_argument(
            "--days",
            type=int,
            default=0,
            help="Si se pasa >0, verifica si existe histórico en los últimos N días; solo crea si no existe.",
        )

    def handle(self, *args, **options):
        """Ejecuta la creación de `PriceHistory` según el precio almacenado.

        Si `--days` se especifica, omite cartas con historial en ese rango."""
        days = options.get("days") or 0
        cutoff = None
        if days > 0:
            cutoff = timezone.now() - timezone.timedelta(days=days)

        cards = Card.objects.all()
        created = 0
        skipped = 0

        for card in cards:
            try:
                if cutoff:
                    exists = PriceHistory.objects.filter(
                        card=card, recorded_at__gte=cutoff
                    ).exists()
                else:
                    exists = PriceHistory.objects.filter(card=card).exists()

                if exists:
                    skipped += 1
                    continue

                if card.price is None:
                    skipped += 1
                    continue

                PriceHistory.objects.create(
                    card=card, price=float(card.price), marketplace="tcgplayer"
                )
                created += 1
            except Exception as e:
                self.stderr.write(f"Error con {card.pokemontcg_id}: {e}")

        self.stdout.write(f"Proceso completado. Creadas: {created}. Omitidas: {skipped}.")
