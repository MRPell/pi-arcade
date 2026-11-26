# NES

NES games run on **FCEUmm** (`lr-fceumm`), RetroPie's default NES core. The system appears in EmulationStation as **Nintendo Entertainment System**, and its ROM folder is `nes`.

`scripts/install.sh` installs the core and creates `/home/pi/RetroPie/roms/nes/`.

---

## ROMs

Copy ROMs to `/home/pi/RetroPie/roms/nes/` on the Pi. Supported formats: `.nes`, `.zip`, and `.7z`.

ROMs are **not included**, and `make deploy` deliberately skips the `roms/` folder, so copy them to the Pi directly. They must be legally obtained: dumped from cartridges you own, or from an official re-release. Mac copies go in `roms/nes/` (gitignored). EmulationStation hides a system until its folder has at least one game, and it needs a restart to rescan.

---

## Controls

FCEUmm's default bindings, mapped through the cabinet's RetroArch profile (shipped in `config/retroarch-autoconfig/`):

| Physical input | RetroPad | NES |
|----------------|----------|-----|
| BTN 4 | B | B |
| BTN 5 | A | A |
| Start | Start | Start |
| Coin | Select | Select |
| BTN 1, 2, 3, 6 | Y, X, L, R | unused |

The NES pad has only **B** and **A**, so use **BTN 4 = B** and **BTN 5 = A**. In most games B fires or runs and A jumps.

- **Exit a game:** Coin + Start (the global RetroArch hotkey).
- **2-player:** the cabinet has one set of controls, so simultaneous 2-player games (Contra, TMNT II) are 1-player only. The BTN 5 + BTN 6 chord is MAME's 2-Player Start and does nothing here.
- **4-way joystick:** the NES pad was 8-way. Platformers play fine; Contra can't aim diagonally (aim straight up or along the ground instead).

---

## Game List

The top 10 for an arcade panel: short sessions, high scores or fast restarts, and B/A-only controls.

| # | Game | Genre | Notes |
|---|------|-------|-------|
| 1 | Contra | Run-and-gun | B fire, A jump. Konami code on the title screen for 30 lives: Up Up Down Down Left Right Left Right B A Start |
| 2 | Excitebike | Racing | A = throttle, B = turbo (watch the temperature gauge). Left/Right tilts the bike in the air. Has a track designer |
| 3 | Super Mario Bros. | Platformer | B run/fireball, A jump |
| 4 | Super Mario Bros. 3 | Platformer | B run/fireball/tail, A jump |
| 5 | Mike Tyson's Punch-Out!! (or Punch-Out!!) | Boxing | B left / A right punch; Up + button for head shots; Start for a star uppercut |
| 6 | Mega Man 2 | Action platformer | B fire, A jump; Start opens the weapon menu |
| 7 | Teenage Mutant Ninja Turtles II: The Arcade Game | Beat 'em up | Port of the arcade game; B attack, A jump |
| 8 | Castlevania | Action platformer | B whip, Up + B sub-weapon, A jump |
| 9 | Ninja Gaiden | Action platformer | B sword, Up + B sub-weapon, A jump. Hard, with checkpoints |
| 10 | Tetris | Puzzle | B/A rotate, Down drops. Score-chasing classic |

Other reliable picks: Super C (the Contra sequel), Double Dragon II, Bubble Bobble, Kirby's Adventure, Galaga.

For a longer game, **The Legend of Zelda** plays well (B uses the item in the B slot, A swings the sword, Start opens the inventory). It saves to battery-backed cartridge RAM, which RetroArch writes to disk when the game exits, so quit with Coin + Start before cutting power.

Skip **Duck Hunt** and other Zapper games, because they need the light gun.
