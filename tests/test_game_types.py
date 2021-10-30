import pytest
from pytest_mock import MockerFixture
import random
from models.game_types import GameBase, CorellianGambit
from models.player import Player
from models.card import Card


def test_correlian_gambit_ctor() -> None:
    random.seed(0)
    
    game = CorellianGambit()

    assert game.is_active == True
    assert game.code == "n6b8r7" # From random seed = 0
    assert len(game.deck) == 62
    # Check for uniqueness of card IDs
    card_ids = [c.id for c in game.deck]
    assert len(card_ids) == len(set(card_ids))


pairwise_tests = [
    (Player("p1", 1, username="p1", hand=[Card(1, "test", -1), Card(2, "test", 1)]), Player("p2", 1, username="p2", hand=[Card(1, "test", 3), Card(2, "test", 4)]), "p1"),
    (Player("p1", 1, username="p1", hand=[Card(1, "test", 3), Card(2, "test", 4)]), Player("p2", 1, username="p2", hand=[Card(1, "test", -1), Card(2, "test", 1)]), "p2"),
]
@pytest.mark.parametrize("player1, player2, winner_username", pairwise_tests)
def test_correlian_gambit_calculate_scores_pairwise(player1, player2, winner_username) -> None:
    game = CorellianGambit()
    game.players.append(player1)
    game.players.append(player2)

    winner = game.calculate_scores()
    
    assert len(player1.hand) == 2
    assert len(player2.hand) == 2
    assert winner.username == winner_username


def test_correlian_gambit_process_action(mocker: MockerFixture) -> None:
    pass
