from django.db import models

class Card(models.Model):
    RARITY_CHOICES = [
        ('common', 'Común'),
        ('uncommon', 'Infrecuente'),
        ('rare', 'Rara'),
        ('holorare', 'Holo Rara'),
    ]
    
    pokemontcg_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    image_url = models.URLField()
    rarity = models.CharField(max_length=20, choices=RARITY_CHOICES, default='common')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']


class PokemonEspecie(models.Model):
    numero_pokedex = models.IntegerField(unique=True)
    name = models.CharField(max_length=100, db_index=True)
    image = models.URLField()

    def __str__(self):
        return f"#{self.numero_pokedex} - {self.name.capitalize()}"
    
    class Meta:
        verbose_name = "Especie Pokémon"
        verbose_name_plural = "Especies Pokémon"
        ordering = ['numero_pokedex']