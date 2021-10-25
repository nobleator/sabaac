import datetime
import json
from models.game_types import GameBase


class GameState:
    """
    server-client message format
    (server) write_message(dict) -> JSON.parse() (client)
    {
        "code": string,
        "startgame": None or boolean,
        "round": int,
        "username": None or string,
        "players": None or [string, ...],
        "winner": None or string,
        "currentplayer": None or string (uuid),
        "messages": None or [{"Timestamp": datetime, "Body": string}, ...],
        "topdiscard": None or Card,
        "playerhand": None or [Card, ...]
        "playercredits": None or int
    }
    """
    def __init__(self, game: GameBase):
        self.timestamp = datetime.datetime.utcnow().isoformat()
        self.code = game.code
        self.round = game.round
        self.startgame = False
        self.username = None
        self.players = game.conv_players_for_lobby()
        self.winner = game.winner
        self.currentplayer = game.get_current_player()
        self.messages = game.action_log
        self.topdiscard = game.discard[-1] if len(game.discard) > 0 else None
        self.playerhand = None
        self.playercredits = None
        self.sabaacpot = game.sabaac_pot
        self.handpot = game.hand_pot

    def to_json(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)
