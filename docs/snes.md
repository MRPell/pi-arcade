# SNES

SNES games run on **Snes9x 2010** (`lr-snes9x2010`), RetroPie's default SNES core on the Pi 3. The system appears in EmulationStation as **Super Nintendo**, and its ROM folder is `snes`.

`scripts/install.sh` installs the core and creates `/home/pi/RetroPie/roms/snes/`.

---

## ROMs

Copy ROMs to `/home/pi/RetroPie/roms/snes/` on the Pi. Supported formats: `.sfc`, `.smc`, `.zip`, and `.7z`.

ROMs are **not included**, and `make deploy` deliberately skips the `roms/` folder, so copy them to the Pi directly. They must be legally obtained: dumped from cartridges you own, or from an official re-release. Mac copies go in `roms/snes/` (gitignored). EmulationStation hides a system until its folder has at least one game, and it needs a restart to rescan.

---

## Controls

The cabinet's RetroArch profile (shipped in `config/retroarch-autoconfig/`) maps the panel onto the RetroPad, which matches the SNES pad one-to-one:

| Physical input | SNES |
|----------------|------|
| BTN 1 | Y |
| BTN 2 | X |
| BTN 3 | L |
| BTN 4 | B |
| BTN 5 | A |
| BTN 6 | R |
| Start | Start |
| Coin | Select |

- **Exit a game:** Coin + Start (the global RetroArch hotkey).
- **2-player:** the cabinet has one set of controls, so simultaneous 2-player games (Contra III, Turtles in Time, Street Fighter II) are 1-player only. The BTN 5 + BTN 6 chord is MAME's 2-Player Start and does nothing here.
- **4-way joystick:** the SNES pad was 8-way. Contra III and Super Metroid lose diagonal aiming, but both have L/R aim-lock workarounds (below). Fighting-game jump angles and the quarter-circle specials are harder.
- **If a game's buttons feel wrong:** remap them in RetroArch's Quick Menu → Controls and save a core remap.

---

## Game List

| # | Game | Genre | Notes |
|---|------|-------|-------|
| 1 | Contra III: The Alien Wars | Run-and-gun | Y fire, B jump, X bomb, L/R switch weapons, L + R together = stand still and spin-fire diagonally (makes up for the 4-way stick) |
| 2 | Super Mario World | Platformer | Y run, B jump, A spin jump |
| 3 | Teenage Mutant Ninja Turtles IV: Turtles in Time | Beat 'em up | Y attack, B jump. Arcade-style |
| 4 | Street Fighter II Turbo | Fighter | Uses all 6 buttons: punches on Y/X/L, kicks on B/A/R |
| 5 | Mega Man X | Action platformer | Y fire (hold to charge), B jump, A dash |
| 6 | Donkey Kong Country | Platformer | Y roll/run, B jump, A swap Kongs |
| 7 | Super Punch-Out!! | Boxing | Y/B left and right body blows; Up + Y/B for head shots |
| 8 | Super Metroid | Action exploration | Y fire, B jump, L/R aim diagonally (fixes the 4-way stick) |
| 9 | Super Mario Kart | Racing | B accelerate, Y brake, L/R hop/drift, A item |
| 10 | The Legend of Zelda: A Link to the Past | Action adventure | B sword, Y item, A action. Battery saves work, so progress persists |

Other reliable picks: Super Castlevania IV, F-Zero, Tetris Attack, Final Fight.

### Also installed

| Game | Notes |
|------|-------|
| Donkey Kong Country 2: Diddy's Kong Quest | Same controls as Donkey Kong Country |
| Mega Man X2 | Same controls as Mega Man X |
| Kirby Super Star | Several short games in one; good for quick sessions |
| Super Bomberman | B drops a bomb. The multiplayer mode needs extra pads |
| NBA Jam | 2-on-2 arcade basketball, played against the CPU here |
| Mortal Kombat II | Fighter. Uses the 6 buttons plus block |
| Killer Instinct | Fighter. Uses all 6 buttons |
| Super Mario RPG: Legend of the Seven Stars | RPG with timed button presses |
| Chrono Trigger | RPG |
| Final Fantasy III (FF VI in Japan) | RPG |
| EarthBound | RPG |
| Secret of Mana | Action RPG |
| Super Mario World 2: Yoshi's Island | Uses the Super FX 2 chip and may slow down on a Pi 3 |
| Star Fox | Uses the Super FX chip and may slow down on a Pi 3 |

The RPGs and Kirby Super Star use battery saves, which RetroArch writes to disk when the game exits. Quit with Coin + Start before cutting power.
