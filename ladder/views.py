# ladder/views.py
from django.shortcuts import render, redirect
from django import forms
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
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


def create_game_record(white, black, result, time_control):
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
    return game

def add_game(request):
    if request.method == 'POST':
        form = GameForm(request.POST)
        if form.is_valid():
            white = form.cleaned_data['white']
            black = form.cleaned_data['black']
            result = form.cleaned_data['result']
            time_control = form.cleaned_data['time_control']
            create_game_record(white, black, result, time_control)
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


@require_POST
def save_clock_result(request):
    top_player_id = request.POST.get("top_player_id")
    bottom_player_id = request.POST.get("bottom_player_id")
    winner = request.POST.get("winner")
    minutes_raw = request.POST.get("minutes")

    if not top_player_id or not bottom_player_id:
        return JsonResponse({"error": "Выберите обоих игроков."}, status=400)

    if top_player_id == bottom_player_id:
        return JsonResponse({"error": "Игроки должны быть разными."}, status=400)

    if winner not in {"top", "bottom", "draw"}:
        return JsonResponse({"error": "Выберите результат партии."}, status=400)

    try:
        top_player_id = int(top_player_id)
        bottom_player_id = int(bottom_player_id)
        time_control = int(minutes_raw)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Некорректные данные партии."}, status=400)

    if time_control < 1 or time_control > 180:
        return JsonResponse({"error": "Контроль времени вне допустимого диапазона."}, status=400)

    players = Player.objects.in_bulk([top_player_id, bottom_player_id])
    white = players.get(top_player_id)
    black = players.get(bottom_player_id)

    if white is None or black is None:
        return JsonResponse({"error": "Не удалось найти выбранных игроков."}, status=404)

    result_map = {
        "top": "1-0",
        "bottom": "0-1",
        "draw": Game.RESULT_CHOICES[2][0],
    }
    game = create_game_record(white, black, result_map[winner], time_control)

    return JsonResponse({
        "ok": True,
        "gameId": game.id,
        "message": f"Результат сохранен: {white.name} vs {black.name}.",
    })


def clock(request):
    players = Player.objects.order_by("name")

    initial_minutes = 7
    initial_increment = 5
    top_player_id = request.GET.get("top_player_id") or ""
    bottom_player_id = request.GET.get("bottom_player_id") or ""

    top_player_name = None
    bottom_player_name = None

    if top_player_id:
        top_player = players.filter(id=top_player_id).first()
        if top_player is not None:
            top_player_name = top_player.name

    if bottom_player_id:
        bottom_player = players.filter(id=bottom_player_id).first()
        if bottom_player is not None:
            bottom_player_name = bottom_player.name

    clock_config = {
        "initialMinutes": initial_minutes,
        "initialIncrement": initial_increment,
        "topPlayerId": top_player_id,
        "bottomPlayerId": bottom_player_id,
        "topPlayerName": top_player_name,
        "bottomPlayerName": bottom_player_name,
        "saveResultUrl": reverse("save_clock_result"),
    }

    context = {
        "page_title": "Шахматные часы",
        "players": players,
        "initial_minutes": initial_minutes,
        "initial_increment": initial_increment,
        "top_player_name": top_player_name,
        "bottom_player_name": bottom_player_name,
        "clock_config": clock_config,
    }

    return render(request, "clock/clock.html", context)
