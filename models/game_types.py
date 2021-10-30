import abc
import datetime
import random
from typing import Any, List
import uuid
from models.player import Player
from models.card import Card
from models.actions import Actions


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

    def conv_players_for_lobby(self) -> List[Any]: #TODO typing
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

    def get_players(self) -> List[Player]:
        return self.players
    
    def get_current_player(self) -> Player:
        return next(filter(lambda x: x.turnorder == self.turn,  self.players))

    def get_first_player(self) -> Player:
        return next(filter(lambda x: x.turnorder == 1,  self.players))

    @abc.abstractmethod
    def calculate_scores(self) -> Player:
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
