#!/usr/bin/env python3

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path


DEFAULT_OUTSIDE_LIMIT = 3
DEFAULT_ARSENAL_SNOWBALLS = 10
DEFAULT_PLAYER_CAPACITY = 3
DEFAULT_ARSENAL_REFILL_TURNS = 50
DEFAULT_INITIAL_SNOWBALLS = 0
CONFIG_PATH = Path(__file__).with_name("config.json")
DIRECTIONS = {
    "u": (-1, 0, "up"),
    "d": (1, 0, "down"),
    "l": (0, -1, "left"),
    "r": (0, 1, "right"),
}
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}


@dataclass
class GameConfig:
    grid_size: int
    supervisor_mode: bool
    number_of_players: int
    number_of_walls: int
    number_of_exits: int
    number_of_teleports: int
    number_of_arsenals: int
    arsenal_snowballs: int
    player_snowball_capacity: int
    arsenal_refill_turns: int
    initial_player_snowballs: int
    number_of_hospitals: int
    stop_word: str
    outside_limit: int = DEFAULT_OUTSIDE_LIMIT


@dataclass
class Player:
    name: str
    row: int
    col: int
    carrying_treasure: bool = False
    knows_treasure_location: bool = False
    snowballs: int = 0
    frozen: bool = False
    pending_warmup: bool = False

    @property
    def coordinate(self) -> str:
        return f"({self.row + 1}, {self.col + 1})"


class LabyrinthGame:
    def __init__(self, config: GameConfig) -> None:
        self.config = config
        self.size = config.grid_size
        self.supervisor_mode = config.supervisor_mode
        self.outside_limit = config.outside_limit
        self.passages = self._generate_passages(config.number_of_walls)
        self.exits = self._generate_exits(config.number_of_exits)
        self.players: list[Player] = []
        self.turn_index = 0
        self.turns_played = 0
        self.treasure_taken = False

        self.treasure, self.teleports, self.arsenals, self.hospitals = self._generate_special_cells()

    def _generate_passages(self, wall_count: int) -> dict[tuple[int, int], set[str]]:
        passages = {(row, col): set() for row in range(self.size) for col in range(self.size)}
        all_edges = self._all_internal_edges()
        cells_count = self.size * self.size
        open_edges_needed = len(all_edges) - wall_count
        extra_openings_needed = open_edges_needed - (cells_count - 1)

        visited = {(0, 0)}
        stack = [(0, 0)]
        tree_edges = set()

        while stack:
            row, col = stack[-1]
            neighbors = []
            for _, (d_row, d_col, direction) in DIRECTIONS.items():
                next_row = row + d_row
                next_col = col + d_col
                if 0 <= next_row < self.size and 0 <= next_col < self.size:
                    if (next_row, next_col) not in visited:
                        neighbors.append((next_row, next_col, direction))

            if not neighbors:
                stack.pop()
                continue

            next_row, next_col, direction = random.choice(neighbors)
            edge = self._canonical_edge((row, col), (next_row, next_col), direction)
            tree_edges.add(edge)
            passages[(row, col)].add(direction)
            passages[(next_row, next_col)].add(OPPOSITE[direction])
            visited.add((next_row, next_col))
            stack.append((next_row, next_col))

        remaining_edges = [edge for edge in all_edges if edge not in tree_edges]
        random.shuffle(remaining_edges)
        for first, second, direction in remaining_edges[:extra_openings_needed]:
            passages[first].add(direction)
            passages[second].add(OPPOSITE[direction])

        return passages

    def _generate_exits(self, exit_count: int) -> set[tuple[int, int, str]]:
        candidates = []
        for index in range(self.size):
            candidates.extend(
                [
                    (0, index, "up"),
                    (self.size - 1, index, "down"),
                    (index, 0, "left"),
                    (index, self.size - 1, "right"),
                ]
            )
        random.shuffle(candidates)
        return set(candidates[:exit_count])

    def _generate_special_cells(self):
        all_cells = [(row, col) for row in range(self.size) for col in range(self.size)]
        random.shuffle(all_cells)

        treasure = all_cells.pop()

        teleport_sources = []
        teleport_targets = []
        for _ in range(self.config.number_of_teleports):
            if len(all_cells) < 2:
                break
            source = all_cells.pop()
            target = all_cells.pop()
            teleport_sources.append(source)
            teleport_targets.append(target)
        teleports = dict(zip(teleport_sources, teleport_targets))

        arsenals = {}
        for _ in range(self.config.number_of_arsenals):
            if not all_cells:
                break
            cell = all_cells.pop()
            arsenals[cell] = self.config.arsenal_snowballs

        hospitals = set()
        for _ in range(self.config.number_of_hospitals):
            if not all_cells:
                break
            hospitals.add(all_cells.pop())

        return treasure, teleports, arsenals, hospitals

    def setup_players(self) -> None:
        used_names = set()

        for index in range(self.config.number_of_players):
            while True:
                name = input(f"Player {index + 1} name: ").strip()
                if not name:
                    print("Please enter a name.")
                    continue
                if name in used_names:
                    print("That name is already used.")
                    continue
                used_names.add(name)
                break

            row = self._prompt_int(
                f"{name}, choose starting row (1-{self.size}): ",
                minimum=1,
                maximum=self.size,
            )
            col = self._prompt_int(
                f"{name}, choose starting column (1-{self.size}): ",
                minimum=1,
                maximum=self.size,
            )
            player = Player(
                name=name,
                row=row - 1,
                col=col - 1,
                snowballs=min(self.config.initial_player_snowballs, self.config.player_snowball_capacity),
            )
            self._initialize_player_cell_state(player)
            self.players.append(player)

        random.shuffle(self.players)
        print("\nTurn order:")
        for index, player in enumerate(self.players, start=1):
            print(f"{index}. {player.name}")

    def _initialize_player_cell_state(self, player: Player) -> None:
        if (player.row, player.col) == self.treasure:
            player.knows_treasure_location = True
        if (player.row, player.col) in self.arsenals and not player.frozen:
            self._apply_arsenal_refill(player)
        if (player.row, player.col) in self.hospitals and player.frozen:
            player.pending_warmup = True

    def play(self) -> None:
        print("\nThe labyrinth is ready.")
        print(f"Grid size: {self.size}x{self.size}")
        print("The labyrinth layout is hidden. Try to find the treasure and escape.\n")

        while True:
            player = self._next_player()
            self._take_turn(player)
            self.turns_played += 1
            self._maybe_refill_arsenals()

    def _next_player(self) -> Player:
        player = self.players[self.turn_index % len(self.players)]
        self.turn_index += 1
        return player

    def _take_turn(self, player: Player) -> None:
        print(f"\n{player.name}'s turn")
        if self.supervisor_mode:
            print(f"Supervisor: current position is {self._describe_position(player)}")
            print(self._render_supervisor_legend())
            print(self._render_maze(reveal_treasure=True, reveal_teleports=True, reveal_support=True))

        self._handle_start_of_turn_effects(player)

        actions_remaining = 2
        moved_this_turn = False
        throws_this_turn = 0
        action_taken = False

        while actions_remaining > 0:
            if not self._has_available_action(player, moved_this_turn, throws_this_turn):
                if action_taken:
                    print("Turn ended automatically")
                return

            action = self._prompt_action(player, moved_this_turn, throws_this_turn, action_taken)
            if action == self.config.stop_word:
                print("Game ended in a draw")
                self.reveal_labyrinth()
                raise SystemExit(0)

            if action == "end":
                break

            if action == "p":
                self._handle_pick_up_treasure(player)
                action_taken = True
                actions_remaining -= 1
                continue

            if action == "d":
                self._handle_drop_treasure(player)
                action_taken = True
                actions_remaining -= 1
                continue

            if action == "m":
                self._handle_move_action(player)
                moved_this_turn = True
                action_taken = True
                actions_remaining -= 1
                continue

            if action == "t":
                if self._handle_throw_action(player):
                    throws_this_turn += 1
                    action_taken = True
                    actions_remaining -= 1
                continue

    def _handle_start_of_turn_effects(self, player: Player) -> None:
        if player.pending_warmup and player.frozen and (player.row, player.col) in self.hospitals:
            player.frozen = False
            player.pending_warmup = False
            print("You are warmed up")

        if player.carrying_treasure:
            print("Status: carrying the treasure")

        if not player.frozen and self._can_pick_up_treasure(player):
            print("Treasure found")

        if player.frozen and (player.row, player.col) in self.hospitals and not player.pending_warmup:
            player.pending_warmup = True

        print(f"Snowballs: {player.snowballs}")
        if player.frozen:
            print("Status: frozen")

    def _prompt_action(
        self,
        player: Player,
        moved_this_turn: bool,
        throws_this_turn: int,
        action_taken: bool,
    ) -> str:
        allowed = []
        if not moved_this_turn and throws_this_turn < 2:
            allowed.append("m")
        if self._can_pick_up_treasure(player):
            allowed.append("p")
        if self._can_drop_treasure(player):
            allowed.append("d")
        if not player.frozen and player.snowballs > 0 and throws_this_turn < 2:
            allowed.append("t")
        if action_taken:
            allowed.append("end")

        while True:
            prompt_actions = []
            if "m" in allowed:
                prompt_actions.append("m=move")
            if "p" in allowed:
                prompt_actions.append("p=pick up treasure")
            if "d" in allowed:
                prompt_actions.append("d=drop treasure")
            if "t" in allowed:
                prompt_actions.append("t=throw snowball")
            if "end" in allowed:
                prompt_actions.append("end=finish turn")
            prompt = f"Action ({', '.join(prompt_actions)}): "

            answer = input(prompt).strip().lower()
            if answer == self.config.stop_word:
                return answer
            if answer in allowed:
                return answer
            print("Please choose one of the allowed actions.")

    def _has_available_action(self, player: Player, moved_this_turn: bool, throws_this_turn: int) -> bool:
        if not moved_this_turn and throws_this_turn < 2:
            return True
        if self._can_pick_up_treasure(player):
            return True
        if self._can_drop_treasure(player):
            return True
        if not player.frozen and player.snowballs > 0 and throws_this_turn < 2:
            return True
        return False

    def _handle_move_action(self, player: Player) -> None:
        while True:
            move = self._prompt_direction()
            result = self._move_player(player, move)

            if result == "blocked":
                print("You can't pass")
                continue

            print("Passed")
            if result == "returned":
                teleported = self._apply_teleport(player)
                if teleported:
                    print("You are teleported")
                print("Returned to the labyrinth")
            elif result == "exit":
                print("Exited the labyrinth")
                if player.carrying_treasure:
                    print(f"{player.name} wins!")
                    self.reveal_labyrinth()
                    raise SystemExit(0)
            else:
                teleported = self._apply_teleport(player)
                if teleported:
                    print("You are teleported")

            if self.supervisor_mode:
                print(f"Supervisor: current position is {self._describe_position(player)}")
                print(self._render_supervisor_legend())
                print(self._render_maze(reveal_treasure=True, reveal_teleports=True, reveal_support=True))

            self._handle_cell_arrival(player)
            return

    def _handle_throw_action(self, player: Player) -> bool:
        if player.frozen:
            print("Frozen players cannot throw snowballs")
            return False
        if player.snowballs <= 0:
            print("You have no snowballs")
            return False

        direction_key = self._prompt_direction()
        player.snowballs -= 1

        target = self._find_snowball_target(player, direction_key)
        if target is None:
            print("The snowball hit nothing")
            return True

        if target.frozen:
            print("The snowball hit nothing")
            return True

        target.frozen = True
        target.pending_warmup = False
        target.knows_treasure_location = False

        if target.carrying_treasure:
            target.carrying_treasure = False
            self.treasure = (target.row, target.col)
            self.treasure_taken = False
            print("Treasure dropped")

        print(f"{player.name} froze {target.name}")
        print(f"{target.name} is frozen")
        return True

    def _handle_pick_up_treasure(self, player: Player) -> None:
        if not self._can_pick_up_treasure(player):
            print("You can't pick up the treasure now")
            return
        player.carrying_treasure = True
        self.treasure_taken = True
        print("Treasure picked up")

    def _handle_drop_treasure(self, player: Player) -> None:
        if not self._can_drop_treasure(player):
            print("You can't drop the treasure here")
            return
        player.carrying_treasure = False
        self.treasure = (player.row, player.col)
        self.treasure_taken = False
        player.knows_treasure_location = True
        print("Treasure dropped")

    def _find_snowball_target(self, shooter: Player, direction_key: str) -> Player | None:
        d_row, d_col, _ = DIRECTIONS[direction_key]
        row = shooter.row
        col = shooter.col

        while True:
            next_row = row + d_row
            next_col = col + d_col

            if not self._within_outside_limit(next_row, next_col):
                return None
            if not self._snowball_can_pass(row, col, next_row, next_col):
                return None

            row, col = next_row, next_col
            for player in self.players:
                if player is shooter:
                    continue
                if player.row == row and player.col == col and not player.frozen:
                    return player

    def _snowball_can_pass(self, row: int, col: int, next_row: int, next_col: int) -> bool:
        current_inside = self._is_inside(row, col)
        next_inside = self._is_inside(next_row, next_col)

        if current_inside and next_inside:
            direction = self._direction_between(row, col, next_row, next_col)
            return direction in self.passages[(row, col)]

        if current_inside and not next_inside:
            direction = self._direction_between(row, col, next_row, next_col)
            return (row, col, direction) in self.exits

        if not current_inside and next_inside:
            direction = self._direction_between(row, col, next_row, next_col)
            outside_direction = OPPOSITE[direction]
            return (next_row, next_col, outside_direction) in self.exits

        return True

    def _handle_cell_arrival(self, player: Player) -> None:
        if player.frozen:
            if self._is_inside(player.row, player.col) and (player.row, player.col) in self.hospitals:
                print("You found a hospital")
                player.pending_warmup = True
            return

        if self._is_inside(player.row, player.col) and (player.row, player.col) == self.treasure and not self.treasure_taken:
            self._discover_treasure(player)

        if self._is_inside(player.row, player.col) and (player.row, player.col) in self.arsenals:
            self._apply_arsenal_refill(player)

    def _apply_arsenal_refill(self, player: Player) -> None:
        if player.frozen or not self._is_inside(player.row, player.col):
            return
        cell = (player.row, player.col)
        if cell not in self.arsenals:
            return

        print("You found an arsenal")
        capacity_left = self.config.player_snowball_capacity - player.snowballs
        available = self.arsenals[cell]
        take_count = min(capacity_left, available)

        if take_count <= 0:
            print("You received 0 more snowballs")
            return

        player.snowballs += take_count
        self.arsenals[cell] -= take_count
        print(f"You received {take_count} more snowballs")

    def _move_player(self, player: Player, move_key: str) -> str:
        d_row, d_col, direction = DIRECTIONS[move_key]
        next_row = player.row + d_row
        next_col = player.col + d_col
        current_inside = self._is_inside(player.row, player.col)
        next_inside = self._is_inside(next_row, next_col)

        if not self._within_outside_limit(next_row, next_col):
            return "blocked"

        if current_inside and next_inside:
            if direction not in self.passages[(player.row, player.col)]:
                return "blocked"
            player.row = next_row
            player.col = next_col
            return "moved"

        if current_inside and not next_inside:
            if (player.row, player.col, direction) not in self.exits:
                return "blocked"
            player.row = next_row
            player.col = next_col
            return "exit"

        if not current_inside and next_inside:
            if not self._can_enter_from_outside(next_row, next_col, direction):
                return "blocked"
            player.row = next_row
            player.col = next_col
            return "returned"

        player.row = next_row
        player.col = next_col
        return "moved"

    def _discover_treasure(self, player: Player) -> None:
        if not self._is_inside(player.row, player.col):
            return
        if (player.row, player.col) != self.treasure or self.treasure_taken or player.carrying_treasure:
            return
        if player.knows_treasure_location or player.frozen:
            return

        player.knows_treasure_location = True
        print("Treasure found")

    def _apply_teleport(self, player: Player) -> bool:
        if not self._is_inside(player.row, player.col):
            return False

        current = (player.row, player.col)
        target = self.teleports.get(current)
        if target is None:
            return False

        player.row, player.col = target
        return True

    def _can_pick_up_treasure(self, player: Player) -> bool:
        if self.treasure_taken or player.carrying_treasure or player.frozen:
            return False
        if not player.knows_treasure_location:
            return False
        return self._is_inside(player.row, player.col) and (player.row, player.col) == self.treasure

    def _can_drop_treasure(self, player: Player) -> bool:
        return player.carrying_treasure and self._is_inside(player.row, player.col)

    def _maybe_refill_arsenals(self) -> None:
        if not self.arsenals:
            return
        if self.config.arsenal_refill_turns <= 0:
            return
        if self.turns_played == 0 or self.turns_played % self.config.arsenal_refill_turns != 0:
            return
        for cell in self.arsenals:
            self.arsenals[cell] = self.config.arsenal_snowballs
        print("All arsenals have been refilled")

    def _is_inside(self, row: int, col: int) -> bool:
        return 0 <= row < self.size and 0 <= col < self.size

    def _within_outside_limit(self, row: int, col: int) -> bool:
        min_index = -self.outside_limit
        max_index = self.size - 1 + self.outside_limit
        return min_index <= row <= max_index and min_index <= col <= max_index

    def _can_enter_from_outside(self, row: int, col: int, direction: str) -> bool:
        outside_direction = OPPOSITE[direction]
        return (row, col, outside_direction) in self.exits

    def _direction_between(self, row: int, col: int, next_row: int, next_col: int) -> str:
        if next_row == row - 1:
            return "up"
        if next_row == row + 1:
            return "down"
        if next_col == col - 1:
            return "left"
        return "right"

    def _describe_position(self, player: Player) -> str:
        if self._is_inside(player.row, player.col):
            return f"inside at {player.coordinate}"
        return f"outside at ({player.row + 1}, {player.col + 1})"

    def reveal_labyrinth(self) -> None:
        print("\nLabyrinth layout:")
        print(self._render_supervisor_legend())
        print(self._render_maze(reveal_treasure=True, reveal_teleports=True, reveal_support=True))

    def _render_maze(
        self,
        reveal_treasure: bool,
        reveal_teleports: bool = False,
        reveal_support: bool = False,
    ) -> str:
        lines = []
        teleport_display_labels = self._teleport_display_labels()
        arsenal_labels = self._arsenal_labels()
        hospital_labels = self._hospital_labels()

        top = "+"
        for col in range(self.size):
            top += ("         " if (0, col, "up") in self.exits else "---------") + "+"
        lines.append(top)

        player_positions: dict[tuple[int, int], list[Player]] = {}
        for player in self.players:
            if self._is_inside(player.row, player.col):
                player_positions.setdefault((player.row, player.col), []).append(player)

        for row in range(self.size):
            middle = ""
            for col in range(self.size):
                if col == 0:
                    middle += " " if (row, col, "left") in self.exits else "|"

                cell_marker = self._cell_marker(
                    row,
                    col,
                    player_positions.get((row, col), []),
                    teleport_display_labels,
                    arsenal_labels,
                    hospital_labels,
                    reveal_treasure,
                    reveal_teleports,
                    reveal_support,
                )
                middle += f"{cell_marker:^9}"
                if col == self.size - 1:
                    middle += " " if (row, col, "right") in self.exits else "|"
                else:
                    middle += " " if "right" in self.passages[(row, col)] else "|"
            lines.append(middle)

            bottom = "+"
            for col in range(self.size):
                if row == self.size - 1:
                    bottom += ("         " if (row, col, "down") in self.exits else "---------") + "+"
                else:
                    bottom += ("         " if "down" in self.passages[(row, col)] else "---------") + "+"
            lines.append(bottom)

        return "\n".join(lines)

    def _cell_marker(
        self,
        row: int,
        col: int,
        players: list[Player],
        teleport_display_labels: dict[tuple[int, int], str],
        arsenal_labels: dict[tuple[int, int], str],
        hospital_labels: dict[tuple[int, int], str],
        reveal_treasure: bool,
        reveal_teleports: bool,
        reveal_support: bool,
    ) -> str:
        markers = [self._player_marker(player) for player in players]
        if reveal_treasure and (row, col) == self.treasure and not self.treasure_taken:
            markers.append("T")
        if reveal_teleports and (row, col) in teleport_display_labels:
            markers.append(teleport_display_labels[(row, col)])
        if reveal_support and (row, col) in arsenal_labels:
            markers.append(arsenal_labels[(row, col)])
        if reveal_support and (row, col) in hospital_labels:
            markers.append(hospital_labels[(row, col)])
        if not markers:
            return " "
        return "/".join(markers)[:9]

    def _player_marker(self, player: Player) -> str:
        return self._player_shortcuts()[player.name]

    def _render_supervisor_legend(self) -> str:
        shortcuts = self._player_shortcuts()
        player_legend = ", ".join(
            f"{shortcuts[player.name]}={player.name}{' (frozen)' if player.frozen else ''}, snowballs={player.snowballs}"
            for player in self.players
        )

        teleport_parts = []
        teleport_labels = self._teleport_labels()
        for source, target in sorted(self.teleports.items()):
            label = teleport_labels[source]
            teleport_parts.append(f"{label}: ({source[0] + 1},{source[1] + 1}) -> ({target[0] + 1},{target[1] + 1})")

        arsenal_parts = []
        arsenal_labels = self._arsenal_labels()
        for cell, amount in sorted(self.arsenals.items()):
            arsenal_parts.append(f"{arsenal_labels[cell]}: ({cell[0] + 1},{cell[1] + 1}) [{amount}]")

        hospital_parts = []
        hospital_labels = self._hospital_labels()
        for cell in sorted(self.hospitals):
            hospital_parts.append(f"{hospital_labels[cell]}: ({cell[0] + 1},{cell[1] + 1})")

        parts = [f"Players: {player_legend}"]
        parts.append(f"T=treasure at ({self.treasure[0] + 1},{self.treasure[1] + 1})" if not self.treasure_taken else "T=carried")
        if teleport_parts:
            parts.append("Teleports: " + ", ".join(teleport_parts))
        if arsenal_parts:
            parts.append("Arsenals: " + ", ".join(arsenal_parts))
        if hospital_parts:
            parts.append("Hospitals: " + ", ".join(hospital_parts))
        return "; ".join(parts)

    def _player_shortcuts(self) -> dict[str, str]:
        shortcuts: dict[str, str] = {}
        used: set[str] = set()

        for player in self.players:
            base = "".join(ch for ch in player.name.upper() if ch.isalnum()) or "P"
            shortcut = base[:2] or "P"
            if shortcut in used:
                index = 2
                while True:
                    candidate = f"{shortcut[:1]}{index}"
                    if candidate not in used:
                        shortcut = candidate
                        break
                    index += 1
            used.add(shortcut)
            shortcuts[player.name] = shortcut

        return shortcuts

    def _teleport_labels(self) -> dict[tuple[int, int], str]:
        return {source: f"P{index}" for index, source in enumerate(sorted(self.teleports.keys()), start=1)}

    def _teleport_display_labels(self) -> dict[tuple[int, int], str]:
        source_labels = self._teleport_labels()
        display_labels: dict[tuple[int, int], str] = {}
        for source, target in self.teleports.items():
            label = source_labels[source]
            display_labels[source] = f"{label}s"
            display_labels[target] = f"{label}f"
        return display_labels

    def _arsenal_labels(self) -> dict[tuple[int, int], str]:
        return {cell: f"A{index}" for index, cell in enumerate(sorted(self.arsenals.keys()), start=1)}

    def _hospital_labels(self) -> dict[tuple[int, int], str]:
        return {cell: f"H{index}" for index, cell in enumerate(sorted(self.hospitals), start=1)}

    def _all_internal_edges(self) -> list[tuple[tuple[int, int], tuple[int, int], str]]:
        edges = []
        for row in range(self.size):
            for col in range(self.size):
                if row + 1 < self.size:
                    edges.append(((row, col), (row + 1, col), "down"))
                if col + 1 < self.size:
                    edges.append(((row, col), (row, col + 1), "right"))
        return edges

    @staticmethod
    def _canonical_edge(first: tuple[int, int], second: tuple[int, int], direction: str):
        if direction in {"down", "right"}:
            return first, second, direction
        if direction == "up":
            return second, first, "down"
        return second, first, "right"

    @staticmethod
    def _prompt_int(prompt: str, minimum: int, maximum: int) -> int:
        while True:
            raw_value = input(prompt).strip()
            try:
                value = int(raw_value)
            except ValueError:
                print("Please enter a valid number.")
                continue
            if minimum <= value <= maximum:
                return value
            print(f"Please enter a number between {minimum} and {maximum}.")

    @staticmethod
    def _prompt_yes_no(prompt: str) -> bool:
        while True:
            answer = input(prompt).strip().lower()
            if answer in {"y", "yes"}:
                return True
            if answer in {"n", "no"}:
                return False
            print("Please answer with y or n.")

    @staticmethod
    def _prompt_direction() -> str:
        while True:
            answer = input("Direction (u/d/l/r): ").strip().lower()
            if answer in DIRECTIONS:
                return answer
            print("Please enter one of: u, d, l, r.")


def load_config_file() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            data = json.load(config_file)
    except (json.JSONDecodeError, OSError):
        print("Config file could not be read. Falling back to defaults where needed.")
        return {}
    if not isinstance(data, dict):
        print("Config file must contain a JSON object. Falling back to defaults where needed.")
        return {}
    return data


def get_optional_config_value(config_data: dict, key: str):
    value = config_data.get(key)
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def parse_config_int(config_data: dict, key: str) -> int | None:
    value = get_optional_config_value(config_data, key)
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_config_bool(config_data: dict, key: str) -> bool | None:
    value = get_optional_config_value(config_data, key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1"}:
            return True
        if normalized in {"false", "no", "n", "0"}:
            return False
    return None


def max_wall_count_for_size(size: int) -> int:
    total_internal_edges = 2 * size * (size - 1)
    minimum_open_edges = size * size - 1
    return total_internal_edges - minimum_open_edges


def resolve_game_config() -> GameConfig:
    config_data = load_config_file()

    grid_size = resolve_grid_size(config_data)
    supervisor_mode = resolve_supervisor_mode(config_data)
    number_of_players = resolve_number_of_players(config_data)
    number_of_walls = resolve_number_of_walls(config_data, grid_size)
    number_of_exits = resolve_number_of_exits(config_data, grid_size)
    number_of_teleports = resolve_number_of_teleports(config_data, grid_size)
    number_of_arsenals = resolve_number_of_arsenals(config_data, grid_size)
    arsenal_snowballs = resolve_positive_int(config_data, "arsenal_snowballs", DEFAULT_ARSENAL_SNOWBALLS)
    player_snowball_capacity = resolve_positive_int(config_data, "player_snowball_capacity", DEFAULT_PLAYER_CAPACITY)
    arsenal_refill_turns = resolve_positive_int(config_data, "arsenal_refill_turns", DEFAULT_ARSENAL_REFILL_TURNS)
    initial_player_snowballs = resolve_nonnegative_int(config_data, "initial_player_snowballs", DEFAULT_INITIAL_SNOWBALLS)
    if initial_player_snowballs > player_snowball_capacity:
        initial_player_snowballs = player_snowball_capacity
    number_of_hospitals = resolve_number_of_hospitals(
        config_data,
        grid_size,
        number_of_arsenals,
        initial_player_snowballs,
    )
    stop_word = resolve_stop_word(config_data)

    return GameConfig(
        grid_size=grid_size,
        supervisor_mode=supervisor_mode,
        number_of_players=number_of_players,
        number_of_walls=number_of_walls,
        number_of_exits=number_of_exits,
        number_of_teleports=number_of_teleports,
        number_of_arsenals=number_of_arsenals,
        arsenal_snowballs=arsenal_snowballs,
        player_snowball_capacity=player_snowball_capacity,
        arsenal_refill_turns=arsenal_refill_turns,
        initial_player_snowballs=initial_player_snowballs,
        number_of_hospitals=number_of_hospitals,
        stop_word=stop_word,
    )


def resolve_grid_size(config_data: dict) -> int:
    configured_size = parse_config_int(config_data, "grid_size")
    if configured_size is not None and configured_size >= 2:
        return configured_size
    if get_optional_config_value(config_data, "grid_size") is not None:
        print("Ignoring invalid config value for grid_size.")
    return random.randint(2, 12)


def resolve_supervisor_mode(config_data: dict) -> bool:
    configured_mode = parse_config_bool(config_data, "supervisor_mode")
    if configured_mode is not None:
        return configured_mode
    if get_optional_config_value(config_data, "supervisor_mode") is not None:
        print("Ignoring invalid config value for supervisor_mode.")
    return random.choice([False, True])


def resolve_number_of_players(config_data: dict) -> int:
    configured_players = parse_config_int(config_data, "number_of_players")
    if configured_players is not None and 2 <= configured_players <= 8:
        return configured_players
    return LabyrinthGame._prompt_int("Number of players: ", minimum=2, maximum=8)


def resolve_number_of_walls(config_data: dict, grid_size: int) -> int:
    configured_walls = parse_config_int(config_data, "number_of_walls")
    max_walls = max_wall_count_for_size(grid_size)
    if configured_walls is not None and 0 <= configured_walls <= max_walls:
        return configured_walls
    if get_optional_config_value(config_data, "number_of_walls") is not None:
        print("Ignoring invalid config value for number_of_walls.")
    return random.randint(0, max_walls)


def resolve_number_of_exits(config_data: dict, grid_size: int) -> int:
    configured_exits = parse_config_int(config_data, "number_of_exits")
    max_exits = 4 * grid_size
    if configured_exits is not None and 1 <= configured_exits <= max_exits:
        return configured_exits
    if get_optional_config_value(config_data, "number_of_exits") is not None:
        print("Ignoring invalid config value for number_of_exits.")
    return random.randint(1, max_exits)


def resolve_number_of_teleports(config_data: dict, grid_size: int) -> int:
    configured_teleports = parse_config_int(config_data, "number_of_teleports")
    max_teleports = max(0, (grid_size * grid_size) // 2)
    if configured_teleports is not None and 0 <= configured_teleports <= max_teleports:
        return configured_teleports
    if get_optional_config_value(config_data, "number_of_teleports") is not None:
        print("Ignoring invalid config value for number_of_teleports.")
        return random.randint(0, max_teleports)
    return 0


def resolve_number_of_arsenals(config_data: dict, grid_size: int) -> int:
    configured_arsenals = parse_config_int(config_data, "number_of_arsenals")
    max_arsenals = grid_size * grid_size
    if configured_arsenals is not None and 0 <= configured_arsenals <= max_arsenals:
        return configured_arsenals
    if get_optional_config_value(config_data, "number_of_arsenals") is not None:
        print("Ignoring invalid config value for number_of_arsenals.")
        return random.randint(0, max_arsenals // 3)
    return 0


def resolve_number_of_hospitals(
    config_data: dict,
    grid_size: int,
    number_of_arsenals: int,
    initial_player_snowballs: int,
) -> int:
    configured_hospitals = parse_config_int(config_data, "number_of_hospitals")
    max_hospitals = grid_size * grid_size
    if configured_hospitals is not None and 0 <= configured_hospitals <= max_hospitals:
        return configured_hospitals
    if get_optional_config_value(config_data, "number_of_hospitals") is not None:
        print("Ignoring invalid config value for number_of_hospitals.")
        return random.randint(0, max_hospitals // 3)
    return 1 if number_of_arsenals > 0 or initial_player_snowballs > 0 else 0


def resolve_positive_int(config_data: dict, key: str, default: int) -> int:
    configured_value = parse_config_int(config_data, key)
    if configured_value is not None and configured_value > 0:
        return configured_value
    if get_optional_config_value(config_data, key) is not None:
        print(f"Ignoring invalid config value for {key}.")
        return random.randint(1, max(default * 2, 2))
    return default


def resolve_nonnegative_int(config_data: dict, key: str, default: int) -> int:
    configured_value = parse_config_int(config_data, key)
    if configured_value is not None and configured_value >= 0:
        return configured_value
    if get_optional_config_value(config_data, key) is not None:
        print(f"Ignoring invalid config value for {key}.")
        return random.randint(0, max(default + 3, 3))
    return default


def resolve_stop_word(config_data: dict) -> str:
    configured_stop_word = get_optional_config_value(config_data, "stop_word")
    if isinstance(configured_stop_word, str):
        normalized = configured_stop_word.strip().lower()
        if normalized and normalized not in DIRECTIONS:
            return normalized
    if configured_stop_word is not None:
        print("Ignoring invalid config value for stop_word.")
    return "stop"


def main() -> None:
    print("Labyrinth Prototype")
    print("-------------------")
    config = resolve_game_config()
    game = LabyrinthGame(config)
    game.setup_players()
    game.play()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGame interrupted.")
