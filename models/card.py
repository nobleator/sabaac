class Card:
    def __init__(self, id: int, suite: str, rank: int):
        self.id: int = id
        self.suite: str = suite
        self.rank: int = rank

    def __repr__(self) -> str:
        return f"(ID: {self.id}) {self.rank} of {self.suite}"
