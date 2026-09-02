# Hardware Setup

## Parts

- Raspberry Pi 3 Model B v1.2
- 4-way (or 8-way) arcade joystick with microswitches
- 3 arcade pushbuttons (already wired)
- Breadboard
- Jumper wires (female-to-female for Pi GPIO header)
- USB power supply (2.5A minimum for Pi 3)
- MicroSD card (8GB+)
- HDMI cable and monitor/TV

---

## How the Inputs Work

Arcade joysticks and buttons use **microswitches** — simple on/off contacts. Each switch has:

- **COM** (Common) — connect to **GND**
- **NO** (Normally Open) — connect to a GPIO pin

When you press the button or move the joystick in a direction, the NO contact closes, pulling the GPIO pin from 3.3V down to GND. The Pi reads this as a LOW signal (pressed). The GPIO daemon uses internal pull-up resistors so no external resistors on the breadboard are needed.

---

## GPIO Pin Assignment

All pin numbers are **BCM (Broadcom) numbering**, which is what the software uses.

| Input | BCM GPIO | Physical Pin | Breadboard rail |
|-------|----------|--------------|-----------------|
| Joystick UP | GPIO 17 | Pin 11 | Signal |
| Joystick DOWN | GPIO 18 | Pin 12 | Signal |
| Joystick LEFT | GPIO 27 | Pin 13 | Signal |
| Joystick RIGHT | GPIO 22 | Pin 15 | Signal |
| Button 1 (fire) | GPIO 23 | Pin 16 | Signal |
| Button 2 (action) | GPIO 24 | Pin 18 | Signal |
| Button 3 (coin/start) | GPIO 25 | Pin 22 | Signal |
| Ground (shared) | GND | Pin 14 | GND rail |
| Ground (shared) | GND | Pin 20 | GND rail |

> **Already have buttons wired?** Check which GPIO pins you used and update `config/gpio_map.json` to match before installing.

---

## Pi GPIO Header Diagram

```
        3V3  [ 1] [ 2]  5V
      GPIO2  [ 3] [ 4]  5V
      GPIO3  [ 5] [ 6]  GND
      GPIO4  [ 7] [ 8]  GPIO14
        GND  [ 9] [10]  GPIO15
 UP  GPIO17  [11] [12]  GPIO18  DOWN
LEFT GPIO27  [13] [14]  GND  <-- connect joystick/button GND here
RIGHT GPIO22 [15] [16]  GPIO23  BTN1
        3V3  [17] [18]  GPIO24  BTN2
     GPIO10  [19] [20]  GND  <-- or here
      GPIO9  [21] [22]  GPIO25  BTN3
     GPIO11  [23] [24]  GPIO8
        GND  [25] [26]  GPIO7
      GPIO0  [27] [28]  GPIO1
      GPIO5  [29] [30]  GND
      GPIO6  [31] [32]  GPIO12
     GPIO13  [33] [34]  GND
     GPIO19  [35] [36]  GPIO16
     GPIO26  [37] [38]  GPIO20
        GND  [39] [40]  GPIO21
```

---

## Wiring the Joystick

A standard arcade joystick has **5 wires** coming off it (one per microswitch direction + shared ground). Wire colors vary by brand; check your joystick's label or documentation.

```
Joystick harness:

  GND (common) ──────────────────────── Pi Pin 14 (GND)
  UP signal    ──────────────────────── Pi Pin 11 (GPIO 17)
  DOWN signal  ──────────────────────── Pi Pin 12 (GPIO 18)
  LEFT signal  ──────────────────────── Pi Pin 13 (GPIO 27)
  RIGHT signal ──────────────────────── Pi Pin 15 (GPIO 22)
```

Use the breadboard GND rail as a common ground bus if you need to split GND to multiple inputs.

```
Breadboard layout (top-down view):

  GND rail ─── Pi Pin 14
               Pi Pin 20
               Joystick GND
               Button 1 GND (COM terminal)
               Button 2 GND (COM terminal)
               Button 3 GND (COM terminal)
```

---

## Wiring the Buttons

Each button has two terminals: COM and NO (or marked + and -).

```
Button 1:
  COM  ──── GND rail (breadboard)
  NO   ──── Pi Pin 16 (GPIO 23)

Button 2:
  COM  ──── GND rail
  NO   ──── Pi Pin 18 (GPIO 24)

Button 3:
  COM  ──── GND rail
  NO   ──── Pi Pin 22 (GPIO 25)
```

---

## Button Function Reference

| Button | In-game action | In menus |
|--------|---------------|---------|
| BTN 1 | Primary fire / jump / action | Confirm (A) |
| BTN 2 | Secondary action | Back (B) |
| BTN 3 | Insert coin + Player 1 Start | — |

**Button 3 detail:** The GPIO daemon sends a coin insert event followed automatically by a Player 1 Start event with a small delay. You don't need a separate Start button. Press BTN 3 once to begin any game.

---

## Checklist Before Powering On

- [ ] All button COM terminals connected to GND rail
- [ ] GND rail connected to Pi GND (Pin 14 or 20)
- [ ] Joystick GND (common) connected to GND rail
- [ ] Each joystick direction wire connected to correct GPIO pin
- [ ] Each button NO terminal connected to correct GPIO pin
- [ ] No bare wires touching each other
- [ ] `config/gpio_map.json` updated to match your actual pin wiring
- [ ] Pi powered via official 2.5A USB-C adapter (not a phone charger)
