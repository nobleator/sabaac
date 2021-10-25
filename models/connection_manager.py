from typing import Dict, List, Optional
from fastapi import Cookie, FastAPI, WebSocket, WebSocketDisconnect, Form
from starlette.routing import WebSocketRoute, websocket_session
from models.game_state import GameState


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
