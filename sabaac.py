from __future__ import annotations
import os
from typing import Dict, List, Optional
import uvicorn
from fastapi import Cookie, FastAPI, WebSocket, WebSocketDisconnect, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse, RedirectResponse, FileResponse
from starlette.requests import Request
from starlette.routing import WebSocketRoute, websocket_session
import random
import json
import enum
# import sqlite3
import datetime
import uuid
import abc


"""
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


class LobbyState:
    def __init__(self):
        pass


class GameLogEntry:
    def __init__(self):
        pass


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        # game code to websocket mappings
        self.game_connections: Dict[str, List[WebSocket]] = {}
        # cookie to websocket mappings
        self.cookie_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, cookie: str, websocket: websocket_session):
        await websocket.accept()
        self.active_connections.append(websocket)
        if cookie in self.cookie_connections:
            if websocket not in self.cookie_connections[cookie]:
                self.cookie_connections[cookie].append(websocket)
            else:
                print(f"Websocket {websocket} already in self.cookie_connections")
        else:
            self.cookie_connections[cookie] = [websocket]

    def disconnect(self, websocket: WebSocketRoute):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        for game_code in self.game_connections:
            if websocket in self.game_connections[game_code]:
                self.game_connections[game_code].remove(websocket)
        for cookie in self.cookie_connections:
            if websocket in self.cookie_connections[cookie]:
                self.cookie_connections[cookie].remove(websocket)

    async def send_player_update(self, cookie: str, game_state: GameState):
        for connection in self.cookie_connections[cookie]:
            await connection.send_json(game_state.to_json())

    async def broadcast_game_state(self, game_state: GameState):
        for connection in self.game_connections[game_state.code]:
            await connection.send_json(game_state.to_json())


# Contains list of Game objects
global_games: list[GameBase] = []
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
manager = ConnectionManager()


@app.get("/")
async def get(games_anon_cookie: Optional[str] = Cookie(None)):
    games_anon_cookie = set_cookie(games_anon_cookie)
    response = RedirectResponse(url = "/login/")
    response.set_cookie(key="games_anon_cookie", value=games_anon_cookie)
    return response


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # Icon courtesy of https://github.com/compycore/sabacc
    file_name = "favicon.ico"
    file_path = os.path.join(app.root_path, f"static/{file_name}")
    return FileResponse(path=file_path, headers={"Content-Disposition": "attachment; filename=" + file_name})


@app.get("/login/", response_class=HTMLResponse)
async def login(request: Request, games_anon_cookie: Optional[str] = Cookie(None)):
    games_anon_cookie = set_cookie(games_anon_cookie)
    response = templates.TemplateResponse("login.html", {"request": request})
    response.set_cookie(key="games_anon_cookie", value=games_anon_cookie)
    return response


@app.get("/createGame/")
async def createGame(games_anon_cookie: Optional[str] = Cookie(None)):
    games_anon_cookie = set_cookie(games_anon_cookie)
    # TODO: Set game type from user input
    new_game = CorellianGambit()
    new_player = Player(cookie=games_anon_cookie, turnorder=1)
    new_game.players.append(new_player)
    global_games.append(new_game)
    return RedirectResponse(url = f"/lobby/{new_game.code}")


@app.post("/joinGame/")
def join_game(gameCode: str = Form(...), games_anon_cookie: Optional[str] = Cookie(None)):
    if gameCode not in [g.code for g in global_games]:
        return RedirectResponse(url = "/login/")
    for game in global_games:
        if gameCode != game.code:
            continue
        if games_anon_cookie not in [p.cookie for p in game.players]:
            max_turnorder = max([p.turnorder for p in game.players])
            new_player = Player(cookie=games_anon_cookie, turnorder=max_turnorder + 1)
            game.players.append(new_player)
        response = RedirectResponse(url = f"/lobby/{gameCode}")
        # set response code explicitly to 302?
        response.status_code = 302
        return response
    if gameCode not in [g.code for g in global_games]:
        return RedirectResponse(url = "/login/")


@app.get("/lobby/{code}", response_class=HTMLResponse)
async def lobby(request: Request, code, games_anon_cookie: Optional[str] = Cookie(None)):
    for game in global_games:
        if code != game.code:
            continue
        if games_anon_cookie not in [p.cookie for p in game.players]:
            return RedirectResponse(url = "/login/")
    return templates.TemplateResponse("lobby.html", {"request": request, "game_code": code})


@app.websocket("/lobbyws")
async def lobby_ws(websocket: WebSocket, games_anon_cookie: Optional[str] = Cookie(None)):
    await manager.connect(games_anon_cookie, websocket)
    try:
        while True:
            message = await websocket.receive_json()
            print(f"Received message: {json.dumps(message)}")
            code = message["code"]
            username = message["username"]
            startgame = message["startgame"]
            game = next(filter(lambda x: x.code == code and x.is_active,
                            global_games))
            if game is not None:
                # TODO: Move to connection manager directly
                if game.code in manager.game_connections:
                    if websocket not in manager.game_connections[game.code]:
                        manager.game_connections[game.code].append(websocket)
                    else:
                        print(f"Websocket {websocket} already in manager.game_connections")
                else:
                    manager.game_connections[game.code] = [websocket]
            if startgame:
                for p in game.players:
                    p.credits -= (game.ante_amount * 2)
                    #TODO: Log message stating ante amounts
                    game.sabaac_pot += game.ante_amount
                    game.hand_pot += game.ante_amount
            else:
                games_anon_cookie = set_cookie(games_anon_cookie)
                for player in game.players:
                    if games_anon_cookie == player.cookie:
                        player.username = username
            game_state = GameState(game)
            game_state.startgame = startgame
            await manager.broadcast_game_state(game_state)
    except WebSocketDisconnect:
        print("WebSocketDisconnect received in lobby")
        manager.disconnect(websocket)
    finally:
        print("Finally block disconnect from lobby")
        manager.disconnect(websocket)


@app.get("/sabaac/{code}")
async def sabaac(request: Request, code, games_anon_cookie: Optional[str] = Cookie(None)):
    game = next(filter(lambda x: x.code == code and x.is_active,
                        global_games))
    if game.round == 0:
        game.round = 1
        for player in game.players:
            for _ in range(2):
                player.hand.append(game.deck.pop(0))
    current_player = next(filter(lambda x: x.cookie == games_anon_cookie, game.players))
    first_player = next(filter(lambda x: x.turnorder == 1, game.players))
    return templates.TemplateResponse("sabaac.html",
        {
            "request": request,
            "game_code": code,
            "username": current_player.username,
            "hand": current_player.hand,
            "first_player": first_player.username
        })


@app.websocket("/sabaacws")
async def sabaacws(websocket: WebSocket, games_anon_cookie: Optional[str] = Cookie(None)):
    await manager.connect(games_anon_cookie, websocket)
    try:
        while True:
            # message is a player's action
            message = await websocket.receive_text()
            print("Received message: " + message)
            message = json.loads(message)
            code = message["code"]
            action = message["action"]
            action_value = message["actionValue"]
            game = next(filter(lambda x: x.code == code and x.is_active,
                            global_games))
            game.process_action(games_anon_cookie, action, action_value)
            game_state = GameState(game)
            # enrich base game state with player-specific details
            for player in game.players:
                game_state.playerhand = player.hand
                game_state.playercredits = player.credits
                await manager.send_player_update(player.cookie, game_state)
    except WebSocketDisconnect:
        print("WebSocketDisconnect received in game")
        manager.disconnect(websocket)
    finally:
        print("Finally block disconnect from game")
        manager.disconnect(websocket)
    

# Models
class GameBase(metaclass=abc.ABCMeta):
    def __init__(self):
        self.guid: str = uuid.uuid1()
        self.is_active: bool = True
        valid_chars = "abcdefghijkmnpqrstuvwxyz23456789"
        code_len = 6
        self.code: str = "".join(random.choices(valid_chars, k=code_len))
        # TODO: Set max rounds/end condition dynamically
        self.round: int = 0
        self.turn: int = 1
        # TODO: Track "hands" as well as rounds? Continue playing for Sabaac pot
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
        self.ante_amount: int = 2
        self.sabaac_pot: int = 0
        self.hand_pot: int = 0

    def dump_to_sql(self):
        return None

    def conv_players_for_lobby(self) -> list:
        return [{"username": p.username,
                 "turnorder": p.turnorder} for p in self.players]

    def process_action(self, cookie: str, action: Actions, action_value: int) -> None:
        timestamp = datetime.datetime.utcnow().isoformat()
        action = Actions(int(action))
        player = next(filter(lambda x: x.cookie == cookie,
                             self.players), None)
        if player.turnorder != self.turn:
            print(f"Action from player {player.username} out of order, ignoring")
        else:
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
                #TODO: Allocate Sabaac pot
                self.winner.credits += self.hand_pot
                message = f"{self.winner.username} wins the game, earning {self.hand_pot} credits"
                self.hand_pot = 0
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
        #TODO: Allow/handle debt?
        self.credits: int = 100


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


# Helper functions
def set_cookie(incoming_cookie) -> str:
    if not incoming_cookie:
        new_cookie = str(uuid.uuid1())
        return new_cookie
    else:
        return incoming_cookie


if __name__ == "__main__":
    port_num = 7777
    address = "0.0.0.0"
    print(f"Listening on {address}:{port_num}")
    uvicorn.run(app, host=address, port=port_num)
