from __future__ import annotations
import os
from typing import Optional
import uvicorn
import uuid
from fastapi import Cookie, FastAPI, WebSocket, WebSocketDisconnect, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse, RedirectResponse, FileResponse
from starlette.requests import Request
import json
# import sqlite3
# local modules
from models.player import Player
from models.game_types import CorellianGambit
from models.game_state import GameState
from models.connection_manager import ConnectionManager
from models.game_manager import GameManager


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
connection_manager = ConnectionManager()
game_manager = GameManager()


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
    game_manager.get_games().append(new_game)
    return RedirectResponse(url = f"/lobby/{new_game.code}")


@app.post("/joinGame/")
def join_game(gameCode: str = Form(...), games_anon_cookie: Optional[str] = Cookie(None)):
    if gameCode not in [g.code for g in game_manager.get_games()]:
        return RedirectResponse(url = "/login/")
    for game in game_manager.get_games():
        if gameCode != game.code:
            continue
        if games_anon_cookie not in [p.cookie for p in game.get_players()]:
            max_turnorder = max([p.turnorder for p in game.get_players()])
            new_player = Player(cookie=games_anon_cookie, turnorder=max_turnorder + 1)
            game.players.append(new_player)
        return RedirectResponse(url = f"/lobby/{gameCode}")
    if gameCode not in [g.code for g in game_manager.get_games()]:
        return RedirectResponse(url = "/login/")


@app.get("/lobby/{code}", response_class=HTMLResponse)
async def lobby(request: Request, code, games_anon_cookie: Optional[str] = Cookie(None)):
    game = game_manager.get_game_by_code(code)
    if game is None:
        return RedirectResponse(url = "/login/", status_code=404)
    else:
        if games_anon_cookie not in [p.cookie for p in game.get_players()]:
            return RedirectResponse(url = "/login/", status_code=403)
        else:
            return templates.TemplateResponse("lobby.html", {"request": request, "game_code": code})


@app.websocket("/lobbyws")
async def lobby_ws(websocket: WebSocket, games_anon_cookie: Optional[str] = Cookie(None)):
    await connection_manager.connect(games_anon_cookie, websocket)
    try:
        while True:
            message = await websocket.receive_json()
            print(f"Received message: {json.dumps(message)}")
            code = message["code"]
            username = message["username"]
            startgame = message["startgame"]
            game = game_manager.get_game_by_code(code)
            if game is not None:
                # TODO: Move to connection connection_manager directly
                if game.code in connection_manager.game_connections:
                    if websocket not in connection_manager.game_connections[game.code]:
                        connection_manager.game_connections[game.code].append(websocket)
                    else:
                        print(f"Websocket {websocket} already in connection_manager.game_connections")
                else:
                    connection_manager.game_connections[game.code] = [websocket]
            if startgame:
                for p in game.get_players():
                    p.credits -= (game.ante_amount * 2)
                    #TODO: Log message stating ante amounts
                    game.sabaac_pot += game.ante_amount
                    game.hand_pot += game.ante_amount
            else:
                games_anon_cookie = set_cookie(games_anon_cookie)
                for player in game.get_players():
                    if games_anon_cookie == player.cookie:
                        player.username = username
            game_state = GameState(game)
            game_state.startgame = startgame
            await connection_manager.broadcast_game_state(game_state)
    except WebSocketDisconnect:
        print("WebSocketDisconnect received in lobby")
        connection_manager.disconnect(websocket)
    finally:
        print("Finally block disconnect from lobby")
        connection_manager.disconnect(websocket)


@app.get("/sabaac/{code}")
async def sabaac(request: Request, code, games_anon_cookie: Optional[str] = Cookie(None)):
    game = game_manager.get_game_by_code(code)
    if game.round == 0:
        game.round = 1
        for player in game.get_players():
            for _ in range(2):
                player.hand.append(game.deck.pop(0))
    current_player = game.get_current_player()
    first_player = game.get_first_player()
    return templates.TemplateResponse("sabaac.html",
        {
            "request": request,
            "game_code": code,
            "username": current_player.username,
            "hand": current_player.hand,
            "first_player": first_player.username
        })


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
@app.websocket("/sabaacws")
async def sabaacws(websocket: WebSocket, games_anon_cookie: Optional[str] = Cookie(None)):
    await connection_manager.connect(games_anon_cookie, websocket)
    try:
        while True:
            # message is a player's action
            message = await websocket.receive_text()
            print("Received message: " + message)
            message = json.loads(message)
            code = message["code"]
            action = message["action"]
            action_value = message["actionValue"]
            game = game_manager.get_game_by_code(code)
            game.process_action(games_anon_cookie, action, action_value)
            game_state = GameState(game)
            # enrich base game state with player-specific details
            for player in game.get_players():
                game_state.playerhand = player.hand
                game_state.playercredits = player.credits
                await connection_manager.send_player_update(player.cookie, game_state)
    except WebSocketDisconnect:
        print("WebSocketDisconnect received in game")
        connection_manager.disconnect(websocket)
    finally:
        print("Finally block disconnect from game")
        connection_manager.disconnect(websocket)
    

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
