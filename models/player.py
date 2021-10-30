from typing import List
from models.card import Card


class Player:
    def __init__(self, cookie, turnorder, username: str = "Mr. Mysterious", hand: List[Card] = None):
        # TODO: Player ID?
        self.cookie: str = cookie
        self.username: str = username
        self.turnorder: int = turnorder
        self.hand: list[Card] = hand if hand is not None else []
        #TODO: Allow/handle debt?
        self.credits: int = 100
