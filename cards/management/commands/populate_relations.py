from django.core.management.base import BaseCommand
from cards.models import Card, Rarity, Supertype, Subtype, Artist

class Command(BaseCommand):
    help = 'Convierte campos de texto en relaciones de base de datos'

    def handle(self, *args, **options):
        # Procesamos las cartas existentes
        cards = Card.objects.all()
        for card in cards:
            # Ejemplo: Si tenías un campo que guardaba el nombre de la rareza como texto
            # Primero crea o busca el objeto Rarity
            if card.rarity_name_temp: # Asegúrate de haber guardado el texto temporalmente
                rarity_obj, _ = Rarity.objects.get_or_create(
                    name=card.rarity_name_temp.lower(),
                    defaults={'display_name': card.rarity_name_temp}
                )
                card.rarity = rarity_obj
                card.save()
        self.stdout.write(self.style.SUCCESS('¡Base de datos migrada exitosamente!'))