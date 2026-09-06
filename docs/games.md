# Game List

Top 10 single-player high-score arcade games playable with a 4-way joystick and the action buttons.
All run via MAME (lr-mame2003-plus) in RetroPie. Every game here needs at most BTN 1 and BTN 2.

---

## Controls Reference

| Physical Input | In-game mapping |
|---------------|-----------------|
| Joystick | Player movement / direction |
| BTN 1 | Fire / primary action |
| BTN 2 | Secondary action (game-specific) |
| BTN 3–6 | Extra action buttons (unused by these games) |
| Coin | Insert credit |
| Start | Player 1 Start |

---

## The 10 Games

### 1. Pac-Man (1980)
**ROM filename:** `pacman.zip`
**Controls needed:** Joystick only
**High score hook:** Chasing the world record is a dedicated pursuit. Clearing boards efficiently requires memorizing ghost patterns (called "patterns" or "algorithms"). The perfect game score is 3,333,360.

| Input | Action |
|-------|--------|
| Joystick | Move Pac-Man |

---

### 2. Galaga (1981)
**ROM filename:** `galaga.zip`
**Controls needed:** Joystick + BTN 1
**High score hook:** The "challenging stage" bonus, the tractor-beam capture trick (let your ship get captured, then rescue it for double cannon), and no-miss play all stack. A perfect game score exists.

| Input | Action |
|-------|--------|
| Joystick left/right | Move ship |
| BTN 1 | Fire |

---

### 3. Donkey Kong (1981)
**ROM filename:** `dkong.zip`
**Controls needed:** Joystick + BTN 1
**High score hook:** The game loops indefinitely, awarding more points at higher kill screens. Features a famous competitive scene (Twin Galaxies records). The "kill screen" at L22 stops play for most players.

| Input | Action |
|-------|--------|
| Joystick left/right | Move Mario |
| Joystick up/down | Climb ladders |
| BTN 1 | Jump |

---

### 4. Space Invaders (1978)
**ROM filename:** `invaders.zip`
**Controls needed:** Joystick + BTN 1
**High score hook:** Shooting the UFO for maximum bonus (requires precise timing on your shot count) is the core skill. The game rolls over at 9999 points and continues infinitely.

| Input | Action |
|-------|--------|
| Joystick left/right | Move cannon |
| BTN 1 | Fire |

---

### 5. Dig Dug (1982)
**ROM filename:** `digdug.zip`
**Controls needed:** Joystick + BTN 1
**High score hook:** Dropping rocks to crush multiple enemies at once scores exponentially. Killing all enemies on a level with one rock drop is the elite play. The game loops with increasing difficulty.

| Input | Action |
|-------|--------|
| Joystick | Dig and move |
| BTN 1 | Inflate / fire pump |

---

### 6. Frogger (1981)
**ROM filename:** `frogger.zip`
**Controls needed:** Joystick only
**High score hook:** Time bonuses for fast completion, maximizing log rides, and reaching all five home slots without dying accumulate quickly. The game loops with increasing difficulty.

| Input | Action |
|-------|--------|
| Joystick | Move frog |

---

### 7. Q*bert (1982)
**ROM filename:** `qbert.zip`
**Controls needed:** Joystick only (diagonal)
**High score hook:** Catching Slick and Sam (change-back enemies) for big bonuses, and surviving the faster later boards. The joystick is used diagonally — 8-way joysticks work best; a 4-way joystick requires rotating 45 degrees mentally.

| Input | Action |
|-------|--------|
| Joystick (diagonal) | Jump Q*bert |

> **Note:** Q*bert uses diagonal movement. On a 4-way joystick, map up=upper-right, right=lower-right, down=lower-left, left=upper-left. An 8-way joystick is more natural for this game.

---

### 8. 1942 (1984)
**ROM filename:** `1942.zip`
**Controls needed:** Joystick + BTN 1 + BTN 2
**High score hook:** The loop (barrel roll) is essential for dodging enemy fire. Collecting POW items powers up your plane. The game has 32 stages and loops.

| Input | Action |
|-------|--------|
| Joystick | Move plane |
| BTN 1 | Fire |
| BTN 2 | Barrel roll (loop) |

---

### 9. Joust (1982)
**ROM filename:** `joust.zip`
**Controls needed:** Joystick left/right + BTN 1
**High score hook:** Killing multiple buzzard-riders in quick succession for combo bonuses. Surviving the pterodactyl and lava trolls on later waves. The game loops indefinitely.

| Input | Action |
|-------|--------|
| Joystick left/right | Move direction |
| BTN 1 | Flap wings (gain altitude) |

---

### 10. Centipede (1980)
**ROM filename:** `centiped.zip`
**Controls needed:** Joystick + BTN 1
**High score hook:** Originally designed for a trackball — joystick play is harder but still competitive. Shooting mushrooms for points, luring spiders for 900-point kills, and advanced rolling techniques are the meta.

| Input | Action |
|-------|--------|
| Joystick | Move shooter |
| BTN 1 | Fire |

> **Note:** Centipede was designed for a trackball. Joystick play is authentic to the home port. If you later want a trackball, it can be wired in as a USB HID device alongside the joystick.

---

## ROM Filenames Summary

| Game | ROM zip name |
|------|-------------|
| Pac-Man | `pacman.zip` |
| Galaga | `galaga.zip` |
| Donkey Kong | `dkong.zip` |
| Space Invaders | `invaders.zip` |
| Dig Dug | `digdug.zip` |
| Frogger | `frogger.zip` |
| Q*bert | `qbert.zip` |
| 1942 | `1942.zip` |
| Joust | `joust.zip` |
| Centipede | `centiped.zip` |

Copy these `.zip` files to `/home/pi/RetroPie/roms/mame-libretro/` on the Pi. Do not extract them.

---

## MAME Version Note

This setup uses **lr-mame2003-plus** (MAME version ~0.78). ROMs must match this version. If a game doesn't load, the ROM set version is likely mismatched. The MAME 0.78 ROM set is the correct target.

- [mame2003-plus compatibility list](https://docs.libretro.com/library/mame_2003_plus/)
- [MAME free/legal ROMs](https://www.mamedev.org/roms/)

ROMs must be legally obtained — dumped from hardware you own, or from an official re-release.
