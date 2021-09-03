# Getting Started
- Create and activate a virtual environment. For Windows, open a PowerShell window and run:
`python -m venv env`
Then run:
`.\env\Scripts\Activate.ps1`
Note that the last portion, `env` can be updated as desired but the .gitignore file should be updated accordingly.
- Install dependencies:
`pip install -r requirements.txt`
- Run app, either within the IDE of your choice or from a terminal:
`python sabaac.py`
- Navigate to <localhost:7777>

# TODO
- [x] Add .gitignore and exclude venv folders
- [x] Add README.md with setup/run instructions
- [x] Add round/turn tracker to UI
- [x] Add card object and suites
- [ ] Add function annotations
- [ ] Add unit tests
- [ ] Add error handling
- [ ] Migrate from Tornado to FastAPI?
- [ ] Add game modes/variants (Bespin Standard, Empress Teta Preferred, Cloud City Casino, Corellian Gambit, Corellian Spike), including description added as collapsible section to lobby and game screens
- [ ] Add betting (antes, bets/raises/checks, hand and sabaac pots)
- [ ] Split Python code to separate files
- [ ] "Game code not found" error message
- [ ] Explicitly closing clients or a periodic sweep?
- [ ] How to check whether user left entirely or started the game?
- [ ] Verbose autoreload?
- [ ] Add "Play again" button/logic
- [ ] Better alert when it's your turn or cards are shifted
- [ ] Maintain game data in DB
- [ ] Check for uniqueness of active game codes
- [ ] Set timeout for each player's turn
- [ ] Check if user is in multiple games
- [ ] New game object vs resetting game state vs is_active?
- [ ] Update .html files to use templating
- [ ] Consolidate common CSS and JS to separate files
