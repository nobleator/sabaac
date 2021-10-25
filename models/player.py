from models.card import Card


class Player:
    def __init__(self, cookie, turnorder):
        self.cookie: str = cookie
        self.username: str = "Mr. Mysterious"
        self.turnorder: int = turnorder
        self.hand: list[Card] = []
        #TODO: Allow/handle debt?
        self.credits: int = 100
