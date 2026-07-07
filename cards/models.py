"""Modelos de la aplicación `cards`.

Define cartas, atributos de referencia TCG y especies Pokémon usadas en la
lógica de búsqueda y sincronización."""

from django.db import models


class Rarity(models.Model):
    """Rarities disponibles del Pokémon TCG."""

    name = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)

    def __str__(self):
        """Representación legible de la rareza (display_name)."""
        return self.display_name

    class Meta:
        """Meta para `Rarity` que define representación plural y orden por nombre."""

        verbose_name_plural = "Rarities"
        ordering = ["name"]


class Supertype(models.Model):
    """Supertypes del TCG (Pokémon, Trainer, Energy, etc.)."""

    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100)

    def __str__(self):
        """Representación legible del supertipo (display_name)."""
        return self.display_name

    class Meta:
        """Meta para `Supertype` que define orden por nombre."""

        ordering = ["name"]


class Subtype(models.Model):
    """Subtypes del TCG."""

    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100)

    def __str__(self):
        """Representación legible del subtipo (display_name)."""
        return self.display_name

    class Meta:
        """Meta para `Subtype` que define orden por nombre."""

        ordering = ["name"]


class Artist(models.Model):
    """Artistas de las cartas."""

    name = models.CharField(max_length=255, unique=True, db_index=True)

    def __str__(self):
        """Representación legible del artista (nombre)."""
        return self.name

    class Meta:
        """Meta para `Artist` que define orden por nombre."""

        ordering = ["name"]


class PokemonEspecie(models.Model):
    """Especies Pokémon del Pokédex."""

    numero_pokedex = models.IntegerField(unique=True)
    name_en = models.CharField(max_length=100, db_index=True)
    name_es = models.CharField(max_length=100, db_index=True)
    image = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        """Representación legible de la especie con número de Pokédex y nombre en inglés."""
        return f"#{self.numero_pokedex} - {self.name_en}"

    class Meta:
        """Meta para `PokemonEspecie` con nombres legibles y orden por número de Pokédex."""

        verbose_name = "Especie Pokémon"
        verbose_name_plural = "Especies Pokémon"
        ordering = ["numero_pokedex"]


class Card(models.Model):
    """Cartas del Pokémon TCG."""

    # IDs y metadata básico
    pokemontcg_id = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=255, db_index=True)

    # Imágenes
    image_url = models.URLField()

    # Relaciones a tablas de referencia
    rarity = models.ForeignKey(
        Rarity, on_delete=models.SET_NULL, null=True, blank=True, related_name="cards"
    )
    supertype = models.ForeignKey(
        Supertype,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cards",
    )
    subtype = models.ForeignKey(
        Subtype, on_delete=models.SET_NULL, null=True, blank=True, related_name="cards"
    )
    artist = models.ForeignKey(
        Artist, on_delete=models.SET_NULL, null=True, blank=True, related_name="cards"
    )
    pokemon_especie = models.ForeignKey(
        PokemonEspecie,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cards",
    )

    # Set
    set_name = models.CharField(max_length=255, default="Unknown")
    number = models.CharField(max_length=50, null=True, blank=True)

    # Precio
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Metadata adicional
    hp = models.IntegerField(null=True, blank=True)
    types = models.CharField(max_length=255, null=True, blank=True)  # JSON string o similar

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        """Representación legible de la carta: nombre y set."""
        return f"{self.name} ({self.set_name})"

    class Meta:
        """Meta para `Card`: orden por fecha y varios índices para búsquedas frecuentes."""

        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["pokemontcg_id"]),
            models.Index(fields=["name"]),
            models.Index(fields=["rarity"]),
            models.Index(fields=["supertype"]),
            models.Index(fields=["subtype"]),
            models.Index(fields=["artist"]),
            models.Index(fields=["pokemon_especie"]),
        ]
