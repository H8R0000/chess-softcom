from django.urls import path
from . import views

urlpatterns = [
    path('', views.ladder, name='ladder'),
    path('add/', views.add_game, name='add_game'),
    path('add_player/', views.add_player, name='add_player'), 
    path('headtohead/', views.head_to_head, name='head_to_head'),
    path('all_games/', views.all_games, name='all_games'),

]