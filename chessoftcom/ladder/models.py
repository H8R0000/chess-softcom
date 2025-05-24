# ladder/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db import transaction
from ladder.utils import update_elo

class Player(models.Model):
    name = models.CharField(max_length=50, unique=True,default="")
    elo = models.IntegerField(default=1000)

    def __str__(self):
        return self.name


class Game(models.Model):
    RESULT_CHOICES = [
        ("1-0", "White wins"),
        ("0-1", "Black wins"),
        ("½-½", "Draw"),
    ]
    TIME_CONTROL_CHOICES = [
        ('bullet', 'Bullet'),
        ('blitz', 'Blitz'),
        ('rapid', 'Rapid'),
        ('classical', 'Classical'),
    ]
    white = models.ForeignKey('Player', related_name="games_as_white", on_delete=models.CASCADE)
    black = models.ForeignKey('Player', related_name="games_as_black", on_delete=models.CASCADE)
    result = models.CharField(max_length=3, choices=RESULT_CHOICES)
    played_at = models.DateTimeField(auto_now_add=True)
    white_elo_before = models.IntegerField()
    black_elo_before = models.IntegerField()
    time_control = models.PositiveSmallIntegerField("Контроль времени (минуты на партию)", default=7)
    game_type = models.CharField(max_length=10, choices=TIME_CONTROL_CHOICES, default='rapid')

    def save(self, *args, **kwargs):
        # Только при первом сохранении (добавление новой партии)
        is_new = self._state.adding
        if is_new:
            self.white_elo_before = self.white.elo
            self.black_elo_before = self.black.elo
            nw, nb = update_elo(self.white.elo, self.black.elo, self.result)
            with transaction.atomic():
                self.white.elo = nw
                self.black.elo = nb
                self.white.save()
                self.black.save()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-played_at"]

    def __str__(self):
        return f"{self.white} vs {self.black} ({self.get_game_type_display()}) — {self.result}"