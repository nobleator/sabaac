from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from sabaac import app
from models.game_types import GameBase, CorellianGambit
from models.player import Player


client = TestClient(app)


def test_read_main() -> None:
    response = client.get("/")
    assert response.status_code == 200

def test_read_login() -> None:
    response = client.get("/login/")
    assert response.status_code == 200

def test_read_lobby(mocker: MockerFixture) -> None:
    mocker.patch('sabaac.game_manager.get_game_by_code', return_value=CorellianGambit())
    game_code = "abc"
    response = client.get(f"/lobby/{game_code}")
    assert response.status_code == 200

def test_read_sabaac(mocker: MockerFixture) -> None:
    retval = CorellianGambit()
    retval.code = "abc"
    mocker.patch('sabaac.game_manager.get_game_by_code', return_value=retval)
    mocker.patch.object(GameBase, 'get_current_player', return_value=Player("dummy1", 1))
    mocker.patch.object(GameBase, 'get_first_player', return_value=Player("dummy1", 1))
    response = client.get("/sabaac/{game_code}")
    assert response.status_code == 200
