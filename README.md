# Labyrinth

Labyrinth is a digital adaptation of a childhood multiplayer game designed for family time, conversation, and shared play.

## Project Overview

The purpose of this project is to recreate the original game experience on a computer while preserving its social and emotional character.
The game is intended to feel simple, warm, and engaging rather than highly competitive or visually complex.

At its core, Labyrinth is a hidden-information treasure hunt.
Players move through an unseen maze, relying on the computer to manage the game state, enforce the rules, and reveal only the information each player is allowed to know.

## Design Goals

- Preserve the feeling of the original childhood game
- Support relaxed, family-friendly multiplayer play
- Keep the labyrinth hidden from players during the game
- Let the computer act as a neutral supervisor
- Build a simple first version before expanding the rules or presentation

## Core Game Concept

Labyrinth is a multiplayer game with one supervisor and multiple regular players.
In the digital version, the computer takes the role of the supervisor.

The objective is to find the treasure box hidden inside the labyrinth and carry it out through an exit.
The first player to leave the labyrinth while holding the treasure wins.

## Supervisor Responsibilities

The computer, acting as the supervisor, is responsible for:

1. Generating and drawing the labyrinth
2. Asking each player to choose an initial position
3. Tracking all player positions throughout the game
4. Validating movement and wall collisions
5. Detecting treasure discovery and treasure pickup
6. Detecting when a player exits the labyrinth
7. Declaring the winner and revealing the labyrinth at the end of the game

## Labyrinth Specification

The labyrinth must satisfy the following rules:

- The labyrinth is a 4x4 square grid
- Walls may exist between cells
- Players cannot move through walls
- The number and placement of walls are randomized
- At least one valid exit from the labyrinth must exist
- Exactly one treasure box must exist
- The full labyrinth layout is known only to the computer

## Player Knowledge

Each player knows:

- The size of the labyrinth
- Their own starting coordinate

Each player does not know:

- The wall layout
- The location of the treasure
- The positions of other players, unless the rules are expanded later to expose that information

## Turn Structure

Player order remains fixed during a game.
The initial order of players may be randomized by the supervisor before the game begins.

On a turn, a player may move exactly one step in one of four directions:

- Up
- Down
- Left
- Right

## Movement Rules

When a player attempts to move:

- If a wall blocks the direction, the supervisor responds: `You can't pass`
- If the move is valid, the player's position is updated
- If the player enters the treasure cell, the supervisor responds: `Treasure found`

Finding the treasure does not automatically pick it up.
When a player enters the treasure cell, the supervisor must ask whether the player wants to pick up the treasure.

## Exit and Victory Rules

If a player leaves the labyrinth, the supervisor responds: `Exited the labyrinth`

If a player leaves the labyrinth while carrying the treasure box:

- That player is declared the winner
- The game ends immediately
- The supervisor reveals the full labyrinth layout on the screen

## Core Gameplay Loop

The expected gameplay loop is:

1. The computer generates a hidden labyrinth
2. Players choose starting positions
3. The supervisor establishes player order
4. Players take turns moving one step at a time
5. The supervisor reports blocked paths, treasure discovery, and exits
6. A player finds and picks up the treasure
7. A player escapes the labyrinth with the treasure and wins

## MVP Scope

The first playable version of the project should likely include:

- Local multiplayer on a single computer
- Random labyrinth generation
- Hidden maze state controlled entirely by the computer
- Turn-based movement for multiple players
- Treasure placement and pickup logic
- Exit detection
- End-of-game labyrinth reveal

## Prototype

The current prototype is a terminal-based local multiplayer version of the game.
It focuses on validating the game rules and core loop before building a graphical interface.

Prototype notes:

- Supervisor mode can be enabled when one real person plays the supervisor role
- In supervisor mode, additional internal information is shown on screen, including a graphical labyrinth map with players, treasure, teleports, arsenals, and hospitals marked inside cells
- In normal mode, internal information such as the map and player coordinates is hidden from players
- If a move is blocked, the player keeps trying within the same turn until a valid move is made
- A player may leave the labyrinth, move around in a limited outside buffer zone, and later return through any available exit
- Players cannot move more than three rows or columns away from the labyrinth
- If a player starts a turn on the treasure cell, the treasure can be picked up at the start of that turn without losing the movement action
- Teleports can exist only inside the labyrinth and move the player immediately to another cell inside the labyrinth
- If a player steps onto a teleport cell, the supervisor reports: `You are teleported`
- Teleports are directional: the source and destination are marked separately, for example `P1s` and `P1f`, and only the source cell triggers teleportation
- Arsenals store snowballs, automatically refill the player's snowballs up to capacity when stepped on, and are refilled after a configurable number of turns
- Frozen players cannot throw snowballs, cannot use treasure or arsenals, and can recognize only hospitals
- A player may either throw two snowballs, or use one move and one snowball throw in any order
- Picking up or dropping the treasure is also a valid action and uses one action slot
- A player must do at least one action on each turn and cannot skip the turn immediately
- After making one action, the player may finish the turn early only if another legal action is still available
- If no further legal actions remain, the turn ends automatically
- Typing the configured stop word ends the game in a draw and reveals the labyrinth

## Running the Prototype

Requirements:

- Python 3

Configuration:

- Edit [config.json](/Users/savaspavel/Paylo/Personal/Projects/Labyrinth/labyrinth/config.json:1) to predefine startup parameters
- Supported settings are `grid_size`, `supervisor_mode`, `number_of_players`, `number_of_walls`, `number_of_exits`, `number_of_teleports`, `number_of_arsenals`, `arsenal_snowballs`, `player_snowball_capacity`, `arsenal_refill_turns`, `initial_player_snowballs`, `number_of_hospitals`, and `stop_word`
- A parameter is treated as not set if it is missing or empty
- During initialization, the game asks only for `number_of_players` and for each player's data
- All other settings are taken from `config.json` when valid
- If any non-player setting is missing, empty, invalid, or conflicts with the rules, it is randomized instead of being asked interactively
- If `number_of_teleports` is missing, it defaults to `0`
- If `number_of_arsenals` is missing, it defaults to `0`
- If `arsenal_snowballs` is missing, it defaults to `10`
- If `player_snowball_capacity` is missing, it defaults to `3`
- If `arsenal_refill_turns` is missing, it defaults to `50`
- If `initial_player_snowballs` is missing, it defaults to `0`
- If `number_of_hospitals` is missing, it defaults to `0` when there are no arsenals and no initial snowballs, otherwise `1`
- If `stop_word` is missing or invalid, it falls back to `stop`

Run:

```bash
python3 labyrinth.py
```

The prototype will:

- Load available startup settings from `config.json`
- Randomize any missing or invalid non-player startup settings
- Ask for the number of players
- Ask each player for a name and starting coordinate
- Randomize the initial turn order
- Run the game in the terminal until a player escapes with the treasure

## Current Status

The repository is in an early definition stage.
The game concept and rules are documented, and the first terminal prototype is in place.

## Next Steps

- Write a precise coordinate system definition
- Define how exits are represented on the board edges
- Clarify whether multiple players can occupy the same cell
- Decide how player input will work in the first prototype
- Choose the initial technology stack
- Build a minimal playable prototype
