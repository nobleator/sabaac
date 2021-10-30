from typing import List, Optional
from models.game_types import GameBase


class GameManager:
    def __init__(self):
        self.all_games: list[GameBase] = []

    def get_games(self) -> List[GameBase]:
        return self.all_games
    
    def get_game_by_code(self, game_code) -> Optional[GameBase]:
        return next(filter(lambda x: x.code == game_code and x.is_active, self.get_games()), None)
