# Sega Genesis / Mega Drive

Genesis games run on **Genesis Plus GX** (`lr-genesis-plus-gx`). The system appears in EmulationStation as **Sega Mega Drive**, and its ROM folder is `megadrive`.

`scripts/install.sh` installs the core and creates `/home/pi/RetroPie/roms/megadrive/`.

---

## ROMs

Copy ROMs to `/home/pi/RetroPie/roms/megadrive/` on the Pi. Supported formats: `.md`, `.bin`, `.gen`, `.smd`, and `.zip`.

ROMs are **not included** and `make deploy` deliberately skips the `roms/` folder, so copy them to the Pi directly. They must be legally obtained — dumped from hardware you own, or from an official re-release.

The cabinet's working set is on the Pi in `/home/pi/RetroPie/roms/megadrive/`; Mac copies are kept in `roms/megadrive/` (gitignored). EmulationStation displays the ROM filename, so the names below match the installed files.

---

## Controls

Genesis Plus GX's default bindings, mapped through the cabinet's RetroArch profile (shipped in `config/retroarch-autoconfig/`):

| Physical input | RetroPad | Genesis |
|----------------|----------|---------|
| BTN 1 | Y | A |
| BTN 2 | X | Y |
| BTN 3 | L | X |
| BTN 4 | B | B |
| BTN 5 | A | C |
| BTN 6 | R | Z |
| Start | Start | Start / Pause |
| Coin | Select | Mode |

Most Genesis games use only the three original buttons: **BTN 1 = A**, **BTN 4 = B**, and **BTN 5 = C**.

- **Exit a game:** Coin + Start (the global RetroArch hotkey).
- **2-player:** Genesis games have no credits and the cabinet has one set of controls. The BTN 5 + BTN 6 chord is MAME's 2-Player Start and does nothing here.
- **If a game's buttons feel wrong:** remap them in RetroArch's Quick Menu → Controls and save a core remap.

The panel's joystick is 4-way, while these games were designed for an 8-way pad. Platformers (Sonic, Lion King, Aladdin) play fine; games that rely on diagonal movement — Ecco's swimming, beat 'em ups, fighting-game jump angles — are more limited.

---

## Game List

### Sonic

| Game | ROM filename | Notes |
|------|--------------|-------|
| Sonic the Hedgehog | `Sonic the Hedgehog (USA, Europe).zip` | Platformer; any action button jumps |
| Sonic the Hedgehog 2 | `Sonic the Hedgehog 2 (World).zip` | Adds spin dash (Down + jump) and Tails |
| Sonic the Hedgehog 3 | `Sonic the Hedgehog 3 (USA).zip` | Spin dash, elemental shields |
| Sonic & Knuckles | `Sonic & Knuckles (World).zip` | Play as Knuckles; lock-on with Sonic 3 is not configured |
| Sonic Spinball | `Sonic Spinball (USA).zip` | Pinball; flippers on the action buttons |
| Dr. Robotnik's Mean Bean Machine | `Dr. Robotnik's Mean Bean Machine (USA).zip` | Puzzle; D-pad + rotate buttons |
| Sonic 3D Blast | `Sonic 3D Blast ~ Sonic 3D Flickies' Island (USA, Europe, Korea).zip` | Isometric platformer |

### Platformers

| Game | ROM filename | Notes |
|------|--------------|-------|
| The Lion King | `Lion King, The (World).zip` | Platformer |
| Aladdin | `Aladdin (USA).zip` | Platformer; Genesis version has the sword |
| Ecco the Dolphin | `Ecco the Dolphin (USA, Europe, Korea).zip` | Swimming uses diagonals; 4-way stick makes it harder |
| Ecco: The Tides of Time | `Ecco - The Tides of Time (USA).zip` | Optional sequel |

### Run-and-gun

| Game | ROM filename | Notes |
|------|--------------|-------|
| Contra: Hard Corps | `Contra - Hard Corps (USA, Korea).zip` | Run-and-gun; 8-way aiming; hard |
| Gunstar Heroes | `Gunstar Heroes (USA).zip` | Run-and-gun; 8-way aiming |
| Earthworm Jim | `Earthworm Jim (USA).zip` | Platformer / run-and-gun |

### Fighters and brawlers

| Game | ROM filename | Notes |
|------|--------------|-------|
| Streets of Rage 2 | `Streets of Rage 2 (USA).zip` | Beat 'em up; best in the series |
| Golden Axe | `Golden Axe (World).zip` | Beat 'em up; arcade classic |
| Street Fighter II': Special Champion Edition | `Street Fighter II' - Special Champion Edition (USA).zip` | Fighter; uses all 6 action buttons |
| Mortal Kombat II | `Mortal Kombat II (World).zip` | Fighter; uncensored Genesis version |

### Exploration

| Game | ROM filename | Notes |
|------|--------------|-------|
| ToeJam & Earl | `ToeJam & Earl (USA, Europe, Korea).zip` | Co-op exploration; 8-way movement; single-player works by picking one character |

Other reliable picks if you want more: Ristar, Vectorman, Columns, Road Rash II, ToeJam & Earl in Panic on Funkotron.
