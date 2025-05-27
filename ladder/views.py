# ladder/views.py
from django.shortcuts import render
from django.shortcuts import render, redirect
from django import forms
from .models import Player, Game
from django.db.models import Q

class HeadToHeadForm(forms.Form):
    player1 = forms.ModelChoiceField(queryset=Player.objects.all(), label="Игрок 1")
    player2 = forms.ModelChoiceField(queryset=Player.objects.all(), label="Игрок 2")

def all_games(request):
    games = Game.objects.select_related('white', 'black').order_by('-played_at')
    return render(request, 'ladder/all_games.html', {'games': games})


def head_to_head(request):
    form = HeadToHeadForm(request.GET or None)
    stats = None
    games = []
    if form.is_valid():
        p1 = form.cleaned_data["player1"]
        p2 = form.cleaned_data["player2"]
        # Найдём все партии между этими двумя игроками (в любом порядке)
        games = Game.objects.filter(
            (Q(white=p1) & Q(black=p2)) | (Q(white=p2) & Q(black=p1))
        ).order_by("-played_at")
        # Подсчёт результатов
        p1_wins = sum(
            (g.white == p1 and g.result == "1-0") or (g.black == p1 and g.result == "0-1") for g in games
        )
        p2_wins = sum(
            (g.white == p2 and g.result == "1-0") or (g.black == p2 and g.result == "0-1") for g in games
        )
        draws = sum(g.result == "½-½" for g in games)
        stats = {
            "p1": p1,
            "p2": p2,
            "total": games.count(),
            "p1_wins": p1_wins,
            "p2_wins": p2_wins,
            "draws": draws,
        }
    return render(request, "ladder/head_to_head.html", {"form": form, "stats": stats, "games": games})

def ladder(request):
    players = Player.objects.order_by("-elo")
    games   = Game.objects.select_related("white", "black")[:10]
    return render(request, "ladder/dashboard.html", {
        "players": players,
        "games": games,
    })

class GameForm(forms.Form):
    white = forms.ModelChoiceField(queryset=Player.objects.all(), label='Белые')
    black = forms.ModelChoiceField(queryset=Player.objects.all(), label='Чёрные')
    RESULT_CHOICES = [
        ("1-0", "Белые победили"),
        ("0-1", "Чёрные победили"),
        ("½-½", "Ничья"),
    ]
    result = forms.ChoiceField(choices=RESULT_CHOICES, label='Результат')

    # Добавим выпадающий список с предустановленными вариантами времени
    TIME_CHOICES = [
        (1, "Bullet — 1 минута"),
        (2, "Bullet — 2 минуты"),
        (3, "Blitz — 3 минуты"),
        (5, "Blitz — 5 минут"),
        (7, "Rapid — 7 минут"),
        (10, "Rapid — 10 минут"),
        (15, "Rapid — 15 минут"),
        (30, "Classical — 30 минут"),
        (60, "Classical — 60 минут"),
    ]
    time_control = forms.TypedChoiceField(
        choices=TIME_CHOICES,
        coerce=int,
        label="Контроль времени (на игрока)",
        initial=7,  # по умолчанию rapid
        help_text="Можно выбрать из списка или ввести своё время ниже."
    )

    # Можно добавить поле для ввода своего значения
    custom_time = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=180,
        label="Другое время (минут)",
        help_text="Если вашего времени нет в списке — введите своё.",
        widget=forms.NumberInput(attrs={'placeholder': '...'})
    )

    def clean(self):
        cleaned_data = super().clean()
        custom_time = cleaned_data.get("custom_time")
        if custom_time:
            cleaned_data["time_control"] = custom_time
        return cleaned_data
    

def determine_game_type(time_control):
    if time_control <= 2:
        return 'bullet'
    elif 3 <= time_control <= 5:
        return 'blitz'
    elif 6 <= time_control <= 15:
        return 'rapid'
    else:
        return 'classical'

def add_game(request):
    if request.method == 'POST':
        form = GameForm(request.POST)
        if form.is_valid():
            white = form.cleaned_data['white']
            black = form.cleaned_data['black']
            result = form.cleaned_data['result']
            time_control = form.cleaned_data['time_control']
            game_type = determine_game_type(time_control)
            game = Game(
                white=white,
                black=black,
                result=result,
                white_elo_before=white.elo,
                black_elo_before=black.elo,
                time_control=time_control,
                game_type=game_type,
            )
            game.save()
            return redirect('ladder')
    else:
        form = GameForm()
    return render(request, 'ladder/add_game.html', {'form': form})

class PlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = ['name']

def add_player(request):
    if request.method == 'POST':
        form = PlayerForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('ladder')
    else:
        form = PlayerForm()
    return render(request, 'ladder/add_player.html', {'form': form})