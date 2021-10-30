from models.game_types import GameBase


class GameManager:
    def __init__(self):
        self.all_games: list[GameBase] = []

    def get_game_by_code(self, game_code) -> GameBase:
        return next(filter(lambda x: x.code == game_code and x.is_active, self.all_games))
