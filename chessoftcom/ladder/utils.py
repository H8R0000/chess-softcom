import math
from django.db import models, transaction

def expected_score(r_a, r_b):
    return 1 / (1 + math.pow(10, (r_b - r_a) / 400))

def update_elo(r_white, r_black, result):
    K = 32
    w_exp = expected_score(r_white, r_black)
    if result == "1-0":
        s_white, s_black = 1, 0
    elif result == "0-1":
        s_white, s_black = 0, 1
    else:
        s_white = s_black = 0.5
    new_white = r_white + K * (s_white - w_exp)
    new_black = r_black + K * (s_black - (1 - w_exp))
    return round(new_white), round(new_black)
