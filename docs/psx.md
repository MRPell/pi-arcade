# PlayStation

PlayStation games run on **PCSX ReARMed** (`lr-pcsx-rearmed`), the default in `/opt/retropie/configs/psx/emulators.cfg`. The system appears in EmulationStation as **PlayStation**, and its ROM folder is `psx`. The RetroPie 4.8 image already includes the core and the folder, so `scripts/install.sh` doesn't need to install anything for PlayStation.

---

## BIOS

PCSX ReARMed needs a real PlayStation BIOS for good compatibility. Its built-in replacement BIOS breaks some games and memory-card saves. Copy `scph1001.bin` (US, MD5 `924e392ed05558ffdb115408c263dccf`) to `/home/pi/RetroPie/BIOS/`. The name must be lowercase; the core won't find `SCPH1001.BIN`.

---

## ROMs

Copy each game's `.cue` and `.bin` files straight into `/home/pi/RetroPie/roms/psx/`, not into subfolders. EmulationStation lists only the `.cue` files, so a multi-track game (audio on extra `.bin` tracks) shows up as one entry. Keep the `.bin` names exactly as the `.cue` file refers to them.

ROMs are **not included**, and `make deploy` deliberately skips the `roms/` folder. They must be legally obtained: dumped from discs you own. Mac copies go in `roms/psx/` (gitignored), one folder per game. Discs are 200–750 MB each. EmulationStation needs a restart to rescan.

---

## Controls

The cabinet's RetroArch profile maps the panel onto the RetroPad, and PCSX ReARMed maps that onto a digital PlayStation pad. The button grid ends up shaped like the controller's face buttons:

| Panel | PlayStation |
|-------|-------------|
| BTN 1 (top left) | Square |
| BTN 2 (top middle) | Triangle |
| BTN 3 (top right) | L1 |
| BTN 4 (bottom left) | Cross |
| BTN 5 (bottom middle) | Circle |
| BTN 6 (bottom right) | R1 |
| Start | Start |
| Coin | Select |

- There are no L2/R2 buttons or analog sticks. Every game below plays fine on a digital pad with L1/R1.
- **Exit a game:** Coin + Start (the global RetroArch hotkey).
- **Saves:** games save to virtual memory cards, which RetroArch writes to disk when the game exits. Quit with Coin + Start before cutting power.

---

## Game List

| Game | Genre | Notes |
|------|-------|-------|
| Castlevania: Symphony of the Night | Action exploration | Two tracks (data + audio) |
| Crash Bandicoot | Platformer | Cross jump, Square spin |
| Crash Bandicoot 2: Cortex Strikes Back | Platformer | Cross jump, Square spin, Circle crouch/slide |
| Spyro the Dragon | Platformer | Cross jump/glide, Square charge, Circle flame. L1/R1 turn the camera (L2/R2 aren't needed) |
| Street Fighter EX Plus Alpha | Fighting | 3D Street Fighter. Six attacks need six buttons: if Heavy Kick defaults to R2, remap it to L1 in the game's Config menu |
| Tekken 3 | Fighting | The four limbs are Square/Triangle/Cross/Circle. Three tracks (data + 2 audio) |
| Tony Hawk's Pro Skater 2 | Sports | Cross ollie, Square flip, Circle grab, Triangle grind. L1/R1 spin; L2/R2 aren't needed |
