from __future__ import annotations
import tornado.web
import tornado.ioloop
import tornado.websocket
# import tornado.autoreload
import socket
import random
import json
import enum
# import sqlite3
import datetime
import uuid
import abc


"""
server-client message format
(server) write_message(dict) -> JSON.parse() (client)
{
    "timestamp": datetime utc isoformat
    "code": string,
    "round": int,
    "startgame": None or boolean,
    "username": None or string,
    "players": None or [string, ...],
    "winner": None or string (uuid),
    "currentPlayer": None or string (uuid),
    "messages": None or [{"Timestamp": datetime, "Body": string}, ...]
}

client-server message format (player ID in cookie)
(client) JSON.stringify() -> json.parse() (server)
{
    "timestamp": datetime utc isoformat
    "code": string,
    "username": string,
    "startgame": None or boolean,
    "action": None or action enum,
    "actionValue": None or int,
}
"""

# Contains mapping for all WebSocket clients
# ws_clients = {cookie: client}
ws_clients = {}
# Contains list of Game objects
global_games: list[GameBase] = []


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        cookie_manager(self)
        self.redirect(r"/login/")


class LoginHandler(tornado.web.RequestHandler):
    @tornado.web.removeslash
    def get(self):
        cookie_manager(self)
        self.render("login.html")


class CreateGameHandler(tornado.web.RequestHandler):
    @tornado.web.removeslash
    def get(self):
        cookie = cookie_manager(self)
        # TODO: Set game from user input
        new_game = CorellianGambit()
        new_player = Player(cookie=cookie, turnorder=1)
        new_game.players.append(new_player)
        global_games.append(new_game)
        self.redirect(r"/lobby/" + new_game.code)


class JoinGameHandler(tornado.web.RequestHandler):
    def post(self):
        cookie = cookie_manager(self)
        game_code = self.get_argument("gameCode")
        if game_code not in [g.code for g in global_games]:
            self.redirect(r"/login/")
        for game in global_games:
            if game_code != game.code:
                continue
            cookie = cookie_manager(self)
            if cookie not in [p.cookie for p in game.players]:
                max_turnorder = max([p.turnorder for p in game.players])
                new_player = Player(cookie=cookie, turnorder=max_turnorder + 1)
                game.players.append(new_player)
            self.redirect(r"/lobby/" + game_code)
        if game_code not in [g.code for g in global_games]:
            self.redirect(r"/login/")


class LobbyHandler(tornado.web.RequestHandler):
    def get(self, code):
        for game in global_games:
            if code != game.code:
                continue
            cookie = cookie_manager(self)
            if cookie not in [p.cookie for p in game.players]:
                self.redirect(r"/login/")
        self.render("lobby.html", game_code=code)


class LobbyHandler_WS(tornado.websocket.WebSocketHandler):
    def open(self):
        cookie = cookie_manager(self)
        ws_clients[cookie] = self
        print("Lobby WebSocket opened")

    def on_message(self, message):
        print("Received message: " + message)
        message = json.loads(message)
        code = message["code"]
        username = message["username"]
        startgame = message["startgame"]
        game = next(filter(lambda x: x.code == code and x.is_active,
                           global_games))
        if startgame:
            data = message_factory(game.code, game.round, startgame=startgame)
            for p in game.players:
                if ws_clients[p.cookie] is not None:
                    ws_clients[p.cookie].write_message(data)
        else:
            cookie = cookie_manager(self)
            for player in game.players:
                if cookie == player.cookie:
                    player.username = username
            data = message_factory(game.code, game.round, players=game.conv_players_for_lobby())
            for p in game.players:
                if ws_clients[p.cookie] is not None:
                    ws_clients[p.cookie].write_message(data)

    def on_close(self):
        cookie = cookie_manager(self)
        ws_clients[cookie] = None
        print("Lobby WebSocket closed")


class SabaacHandler(tornado.web.RequestHandler):
    def get(self, code):
        cookie = cookie_manager(self)
        game = next(filter(lambda x: x.code == code and x.is_active,
                           global_games))
        username = [p.username for p in game.players
                    if cookie == p.cookie][0]
        if game.round == 0:
            game.round = 1
            for player in game.players:
                for _ in range(2):
                    player.hand.append(game.deck.pop(0))
        self.render("sabaac.html", game_code=code, username=username)


class SabaacHandler_WS(tornado.websocket.WebSocketHandler):
    def open(self):
        cookie = cookie_manager(self)
        ws_clients[cookie] = self
        # Second game reloads end of first game
        game = next(filter(lambda x: cookie in [p.cookie
                                                for p in x.players] and
                           x.is_active,
                           global_games))
        top_discard = None if len(game.discard) <= 0 else game.discard[-1]
        for p in game.players:
            data = message_factory(game.code,
                                   game.round,
                                   topdiscard=top_discard,
                                   current_player=game.get_current_player(),
                                   messages=game.action_log,
                                   playerhand=p.hand)
            if ws_clients[p.cookie] is not None:
                ws_clients[p.cookie].write_message(data)
        print("Game WebSocket opened")

    def on_message(self, message):
        print("Received message: " + message)
        message = json.loads(message)
        code = message["code"]
        action = message["action"]
        action_value = message["actionValue"]
        cookie = cookie_manager(self)
        game = next(filter(lambda x: x.code == code and x.is_active,
                           global_games))
        game.process_action(cookie, action, action_value)
        top_discard = None if len(game.discard) <= 0 else game.discard[-1]
        winner = None if game.winner is None else game.winner.username
        for p in game.players:
            data = message_factory(game.code,
                                   game.round,
                                   topdiscard=top_discard,
                                   current_player=game.get_current_player(),
                                   messages=game.action_log,
                                   playerhand=p.hand,
                                   winner=winner)
            if ws_clients[p.cookie] is not None:
                ws_clients[p.cookie].write_message(data)

    def on_close(self):
        cookie = cookie_manager(self)
        ws_clients[cookie] = None
        print("Game WebSocket closed")


class GameBase(metaclass=abc.ABCMeta):
    def __init__(self):
        self.guid: str = uuid.uuid1()
        self.is_active: bool = True
        valid_chars = "abcdefghijkmnpqrstuvwxyz23456789"
        code_len = 6
        self.code: str = "".join(random.choices(valid_chars, k=code_len))
        self.round: int = 0
        self.turn: int = 1
        # TODO: Change deck composition based on game type
        self.deck: list[Card] = [Card(i, val[0], val[1])
                                 for i, val in enumerate(
                                     [(suite, val) for val in range(-10, 11)
                                     for suite in ["circle", "triangle", "square"]
                                     if val != 0] + [("sylop", 0) for _ in range(2)])]
        random.shuffle(self.deck)
        self.discard: list[Card] = []
        self.players: list[Player] = []
        self.winner: Player = None
        self.action_log: list[str] = []

    def dump_to_sql(self):
        return None

    def conv_players_for_lobby(self) -> list:
        return [{"username": p.username,
                 "turnorder": p.turnorder} for p in self.players]

    def process_action(self, cookie: str, action: Actions, action_value: int) -> None:
        timestamp = datetime.datetime.utcnow().isoformat()
        action = Actions(int(action))
        player = next(filter(lambda x: x.cookie == cookie and
                             x.turnorder == self.turn,
                             self.players))
        if Actions.DRAW_DECK == action:
            player.hand.append(self.deck.pop(0))
            message = f"{player.username} drew from the deck"
            self.action_log.append({"timestamp": timestamp,
                                    "body": message})
        elif Actions.DRAW_DISCARD == action:
            if len(self.discard) > 0:
                player.hand.append(self.discard.pop())
                message = f"{player.username} drew from the discard pile"
                self.action_log.append({"timestamp": timestamp,
                                        "body": message})
            else:
                print("WARNING...No cards in discard")
        elif Actions.DISCARD == action:
            if action_value:
                target_card = next((x for x in player.hand if x.id == int(action_value)), None)
            if target_card in player.hand:
                player.hand.remove(target_card)
                self.discard.append(target_card)
                message = f"{player.username} discarded a {target_card}"
                self.action_log.append({"timestamp": timestamp,
                                        "body": message})
            else:
                print("WARNING...card not present in hand")
        # Increment turn, check for end of round
        self.turn += 1
        if self.turn > max([p.turnorder for p in self.players]):
            d1 = random.randint(1, 6)
            d2 = random.randint(1, 6)
            message = f"Rolled 2 dice: {d1} and {d2}"
            self.action_log.append({"timestamp": timestamp,
                                    "body": message})
            if d1 == d2:
                message = "Doubles!"
                self.action_log.append({"timestamp": timestamp,
                                        "body": message})
                for player in self.players:
                    num_cards = len(player.hand)
                    while len(player.hand) > 0:
                        self.discard.append(player.hand.pop())
                    for _ in range(num_cards):
                        player.hand.append(self.deck.pop(0))
            self.round += 1
            self.turn = 1
        if self.round > 3:
            # Calculate scores, alert winner
            self.winner = self.calculate_scores()
            message = f"{self.winner.username} wins the game"
            self.action_log.append({"timestamp": timestamp,
                                    "body": message})
            self.is_active = False
        print(f"Round {self.round}, turn {self.turn}")

    def get_current_player(self) -> str:
        #TODO: Manage players by IDs rather than usernames
        return next(filter(lambda x: x.turnorder == self.turn,
                           self.players)).username

    @abc.abstractmethod
    def calculate_scores(self):
        pass


class CorellianGambit(GameBase):
    def calculate_scores(self) -> Player:
        """
        1) Hand sums to 0
            Tiebreakers:
                a) Perfect hand [-10, 0, +10]
                b) Number of cards in hand (0 with 3 cards > 0 with 2 cards)
                c) Absolute value of cards ([-4, +4] beats [-1, +1])
        2) Closest to 0
            Tiebreakers:
                a) Positive numbers are better (+1 beats -1)
                b) Number of cards in hand (+1 with 3 cards > +1 with 2 cards)
        Perfect hand: +10,000 points
        Sum to 0: +1000 points
        Distance from 0: -absolute value of sum * 100 points
        Number of cards: +number of cards * 10 points
        Sum of positive values: +sum of positive values * 1 points
        """
        all_scores = {}
        for player in self.players:
            hand_vals = [card.rank for card in player.hand]
            score = 0
            if sorted(hand_vals) == [-10, 0, 10]:
                score += 10000
            if sum(hand_vals) == 0:
                score += 10000
            score += abs(sum(hand_vals)) * -100
            score += len(hand_vals) * 10
            score += sum([c for c in hand_vals if c > 0])
            all_scores[player] = score
        return max(all_scores, key=lambda key: all_scores[key])


class Player:
    def __init__(self, cookie, turnorder):
        self.cookie: str = cookie
        self.username: str = "Mr. Mysterious"
        self.turnorder: int = turnorder
        self.hand: list[Card] = []


class Card:
    def __init__(self, id: int, suite: str, rank: int):
        self.id: int = id
        self.suite: str = suite
        self.rank: int = rank

    def __repr__(self) -> str:
        return f"(ID: {self.id}) {self.rank} of {self.suite}"


class Actions(enum.Enum):
    DRAW_DECK = 1
    DRAW_DISCARD = 2
    PASS = 3
    DISCARD = 4


def cookie_manager(obj) -> str:
    incoming_cookie = obj.get_cookie("games_anon")
    if not incoming_cookie:
        new_cookie = str(uuid.uuid1())
        obj.set_cookie("games_anon", new_cookie)
        return new_cookie
    else:
        return incoming_cookie


def message_factory(code: str, round: int, startgame: bool = None, username: str = None,
                    players: list[str] = None,
                    winner: str = None, current_player: str = None, messages: list[str] = None,
                    topdiscard: Card = None, playerhand: list[Card] = None) -> dict:
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
        "messages": None or [{"Timestamp": datetime, "Body": string}, ...]
    }
    """
    return {"timestamp": datetime.datetime.utcnow().isoformat(),
            "code": code,
            "round": round,
            "startgame": startgame,
            "username": username,
            "players": players,
            "winner": winner,
            "currentplayer": current_player,
            "messages": messages,
            "topdiscard": None if not topdiscard else json.dumps(vars(topdiscard)),
            "playerhand": None if not playerhand else [json.dumps(vars(card)) for card in playerhand]}


# def make_app():
#     settings = {"debug": True,
#                 "cookie_secret": "totally-secret-thing"}
#     return tornado.web.Application([
#         (r"/", MainHandler),
#         (r"/login/*", LoginHandler),
#         (r"/createGame/*", CreateGameHandler),
#         (r"/joinGame/", JoinGameHandler),
#         (r"/lobby/([a-zA-Z0-9]+)", LobbyHandler),
#         (r"/lobbyws", LobbyHandler_WS),
#         (r"/sabaac/([a-zA-Z0-9]+)", SabaacHandler),
#         (r"/sabaacws", SabaacHandler_WS),
#     ], **settings)


if __name__ == "__main__":
    # app = make_app()
    settings = {"debug": True,
                "cookie_secret": "totally-secret-thing"}
    app = tornado.web.Application([
        (r"/", MainHandler),
        (r"/login/*", LoginHandler),
        (r"/createGame/*", CreateGameHandler),
        (r"/joinGame/", JoinGameHandler),
        (r"/lobby/([a-zA-Z0-9]+)", LobbyHandler),
        (r"/lobbyws", LobbyHandler_WS),
        (r"/sabaac/([a-zA-Z0-9]+)", SabaacHandler),
        (r"/sabaacws", SabaacHandler_WS),
    ], **settings)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip_address = s.getsockname()[0]
        s.close()
    except Exception:
        lan_ip_address = "Unavailable"
    port_num = 7777
    address = "0.0.0.0"
    app.listen(port_num, address=address)
    print(f"Listening on {address}:{port_num}")
    print(f"LAN {lan_ip_address}:{port_num}")
    tornado.ioloop.IOLoop.current().start()
