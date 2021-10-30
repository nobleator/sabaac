from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from fastapi import WebSocket
from sabaac import app
from models.game_types import GameBase, CorellianGambit
from models.player import Player


def test_read_main() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200


def test_read_login() -> None:
    client = TestClient(app)

    response = client.get("/login/")

    assert response.status_code == 200


def test_read_lobby_valid_code(mocker: MockerFixture) -> None:
    client = TestClient(app)
    game = CorellianGambit()
    code = "valid"
    game.code = code
    mocker.patch('sabaac.game_manager.get_games', return_value=[game])
    cookie = "dummy1"
    mocker.patch.object(GameBase, 'get_players', return_value=[Player(cookie, 1)])
    cookies = { "games_anon_cookie": cookie }
    
    response = client.get(f"/lobby/{code}", cookies=cookies)

    assert response.status_code == 200


def test_read_lobby_invalid_code(mocker: MockerFixture) -> None:
    client = TestClient(app)
    game = CorellianGambit()
    valid_code = "valid"
    invalid_code = "invalid"
    game.code = valid_code
    mocker.patch('sabaac.game_manager.get_games', return_value=[game])
    mocker.patch.object(GameBase, 'get_players', return_value=[Player("dummy1", 1)])
    
    response = client.get(f"/lobby/{invalid_code}")

    assert response.status_code == 404


def test_read_lobby_invalid_cookie(mocker: MockerFixture) -> None:
    client = TestClient(app)
    game = CorellianGambit()
    code = "valid"
    game.code = code
    mocker.patch('sabaac.game_manager.get_games', return_value=[game])
    cookie = "dummy1"
    mocker.patch.object(GameBase, 'get_players', return_value=[Player(cookie, 1)])
    invalid_cookie = "invalid"
    cookies = {"games_anon_cookie": invalid_cookie}
    
    response = client.get(f"/lobby/{code}", cookies=cookies)

    assert response.status_code == 403


def test_read_sabaac(mocker: MockerFixture) -> None:
    retval = CorellianGambit()
    retval.code = "abc"
    mocker.patch('sabaac.game_manager.get_game_by_code', return_value=retval)
    mocker.patch.object(GameBase, 'get_current_player', return_value=Player("dummy1", 1))
    mocker.patch.object(GameBase, 'get_first_player', return_value=Player("dummy1", 1))
    client = TestClient(app)

    response = client.get("/sabaac/{game_code}")

    assert response.status_code == 200


def test_read_sabaac_ws(mocker: MockerFixture) -> None:
    pass
    # client = TestClient(app)
    # with client.websocket_connect("/sabaacws") as websocket:
    #     websocket: WebSocket
    #     data = websocket.receive_json()
    #     assert data == {"msg": "Hello WebSocket"}
    # assert 1 == 1
