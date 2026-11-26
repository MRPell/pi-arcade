# Game Boy Advance

GBA games run on **mGBA** (`lr-mgba`), the default in `/opt/retropie/configs/gba/emulators.cfg`. The system appears in EmulationStation as **Game Boy Advance**, and its ROM folder is `gba`. The RetroPie 4.8 image already includes `lr-mgba`, `lr-gpsp` and `lr-vba-next` and the `gba` folder, so `scripts/install.sh` doesn't need to install anything for GBA.

---

## ROMs

Copy ROMs to `/home/pi/RetroPie/roms/gba/` on the Pi. Supported formats: `.gba`, `.zip`, and `.7z`.

ROMs are **not included**, and `make deploy` deliberately skips the `roms/` folder, so copy them to the Pi directly. They must be legally obtained: dumped from cartridges you own, or from an official re-release. Mac copies go in `roms/gba/` (gitignored). EmulationStation needs a restart to rescan.

Use one clean `.gba` file per game. Don't use GoodGBA-style variant packs: a zip that holds every region, bad dump, hack and translation of a game loads whichever file RetroArch finds first. A clean dump is a power of two in size (4, 8, 16 or 32 MB) and has no `[b]`, `[h]`, `[t]`, `[f]` or `[T]` tags.

---

## Controls

The cabinet's RetroArch profile (shipped in `config/retroarch-autoconfig/`) maps the panel onto the RetroPad:

| Physical input | GBA |
|----------------|-----|
| BTN 4 | B |
| BTN 5 | A |
| BTN 3 | L |
| BTN 6 | R |
| Start | Start |
| Coin | Select |
| BTN 1, 2 | unused |

- **Exit a game:** Coin + Start (the global RetroArch hotkey).
- **Saves:** GBA games save to cartridge memory, which RetroArch writes to disk when the game exits. Quit with Coin + Start before cutting power.

---

## Performance

GBA is the most demanding system on the Pi 3B. mGBA is the most accurate core but can stutter in heavier games. If a game runs slowly, press a button while "Launching..." shows to open the runcommand menu, and pick `lr-gpsp` for that ROM. gpSP is faster but less accurate. It may need a `gba_bios.bin` in `/home/pi/RetroPie/BIOS/`, and none is installed.

---

## Game List

| Game | Genre | Notes |
|------|-------|-------|
| Pokémon Emerald | RPG | The most complete Gen 3 Pokémon game |
| Pokémon FireRed / LeafGreen | RPG | Gen 3 remakes of Red/Blue |
| The Legend of Zelda: The Minish Cap | Action adventure | B and A use the two equipped items, R rolls or picks up, L shrinks or talks to the hat |
| Metroid: Zero Mission | Action exploration | B fire, A jump, R aims diagonally (makes up for the 4-way stick) |
| Mario & Luigi: Superstar Saga | RPG | A controls Mario, B controls Luigi |
| Super Mario Advance 4: Super Mario Bros. 3 | Platformer | B run/fireball, A jump |
| Wario Land 4 | Platformer | A jump, B attack |
| Mario Kart: Super Circuit | Racing | A accelerate, B brake, R hop/drift, L item |
| Astro Boy: Omega Factor | Action | Fast beat 'em up/shooter from Treasure |
