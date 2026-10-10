# Zombie Outbreak – a Hearts of Iron IV mod

Raise the dead and send them to the front. This mod adds **zombie battalions you
research and train like any other unit**: ten **Necrotech** research projects, a
**Reanimation Serum** equipment line that you produce in military factories,
and three new battalions for the division designer.

It's a normal mod. It doesn't touch your game folder or replace any base-game
file. Drop it in your mod folder and enable it in the launcher.

![thumbnail](zombie_outbreak/thumbnail.png)

## What it adds

### Units (division designer)

| Battalion | Type | Manpower | Training | HP | Org | Needs | Role |
|---|---|---|---|---|---|---|---|
| **Zombie Horde** | Line infantry | 600 | 60 days | 30 | 45 | 100 serum | Cheap, fast to raise, strong soft attack and breakthrough, weak defense |
| **Zombie Brutes** | Line infantry | 400 | 120 days | 25 | 35 | 150 serum | +30% soft attack, +50% breakthrough, −25% defense, −15% speed |
| **Infected Hounds** | Support company | 100 | 60 days | 2 | 20 | 20 serum | Recon company (+1 recon, better movement in forest/jungle/marsh/hills) |

For comparison, vanilla infantry costs 1000 manpower and takes 90 days to train.
All zombie units have high morale (0.5, so they regain organisation quickly)
but low suppression (0.5), so they are poor garrison troops. Hordes fight
better in cities, forests and jungles, brutes in cities, and both fight worse
in mountains.

### Equipment (production)

| Equipment | Soft atk | Hard atk | Piercing | Defense | Breakthrough | Speed | Cost (IC) | Resources |
|---|---|---|---|---|---|---|---|---|
| Reanimation Serum I | 7 | 0.5 | 1 | 15 | 6 | 3.5 | 0.35 | 1 steel |
| Reanimation Serum II | 10 | 0.8 | 1.5 | 19 | 8 | 3.5 | 0.45 | 1 steel |
| Reanimation Serum III | 14 | 1.2 | 2 | 24 | 11 | 4 | 0.55 | 1 steel, 1 chromium |

(Vanilla Infantry Equipment I: 6 / 1 / 4 / 22 / 3, speed 4.) Serum is weak
against tanks: build anti-tank support for zombie divisions.

### Research: Necrotech projects (Decisions screen)

Zombie research runs in your own **Reanimation Laboratory**, found in the
**Decisions** screen under **Necrotech Research**. Each project costs political
power and takes a set number of days; when it finishes you get the technology,
exactly as if you had researched it. The laboratory runs one project at a time,
and while it is busy your normal research is 5% slower.

```
                     Reanimation Experiments  (15 PP, 90 days)  unlocks Zombie Horde + Serum I
          ┌──────────────────┼───────────────────┐
   Virulent Strain    Stabilised Serum     Infected Hounds  (20 PP, 90 days)  unlocks hounds
   (25 PP, 100 d)     (25 PP, 100 d)                │
   +10% atk/brk        Serum II                    │
          │                  │                     │
   Necrotic Brutes    Relentless Hunger     Pack Hunters  (20 PP, 90 days)
   (30 PP, 120 d)     (30 PP, 120 d)        +1 recon, +20% atk, +10% speed
   unlocks brutes     +5 org, faster recovery
          │                  │
   Bone Plating       Perfected Serum
   (35 PP, 140 d)     (35 PP, 140 d)
   +def for zombies    Serum III
                             │
                       Apex Strain  (50 PP, 160 days)
                       +15% atk, +10% brk, +10 org, +10% speed
```

Why not a tab in the tech tree? HoI4 only draws a tech-tree tab if the
base game's tech-screen layout file has a slot for it. A mod can only add one
by shipping a full replacement of that file, which breaks with every game
patch and clashes with other mods. The Decisions screen needs no such file,
so this mod works with any game version.

## Installing

1. Download this repository (green **Code** button → **Download ZIP**) and unzip it.
2. Copy the **`zombie_outbreak`** folder and the **`zombie_outbreak.mod`** file into
   your HoI4 mod folder:
   - Windows: `Documents\Paradox Interactive\Hearts of Iron IV\mod\`
   - Linux: `~/.local/share/Paradox Interactive/Hearts of Iron IV/mod/`
   - macOS: `~/Documents/Paradox Interactive/Hearts of Iron IV/mod/`
3. Open the Paradox launcher, add **Zombie Outbreak** to your playset and play.

That's all. No scripts, and nothing in the game's install folder changes.

## Playing with zombies

1. Open **Decisions** → **Necrotech Research** and start **Research: Reanimation Experiments**.
2. When it finishes, add a production line for **Reanimation Serum I** in **Production**.
3. In the **Division Designer**, build a template from **Zombie Horde** battalions.
   Add **Infected Hounds** as a support company once you have researched them.
4. Train it from the **Deployment** screen like any other division.

To try it out quickly, open the console (`` ` `` or `~`) and type
`research zombie_reanimation` to get the first technology immediately.

## Known limitations

- **The AI doesn't use zombies.** It has no division templates for them, so
  it never starts the research projects. Zombies are a player-only weapon.
- Zombies reuse the infantry 3D models and map counters. Only the 2D icons are new.
- English text only. Other game languages show the English names.
- The mod hasn't been play-tested in a live game yet. If something doesn't
  show up, check `Documents/Paradox Interactive/Hearts of Iron IV/logs/error.log`
  for lines that mention `zombie` and open an issue with them.

## Repository layout

```
zombie_outbreak.mod                  launcher file (copy next to the mod folder)
zombie_outbreak/                     the mod itself
  descriptor.mod, thumbnail.png
  common/technologies/               the 10 Necrotech technologies (granted by decisions)
  common/decisions/                  the Necrotech Research projects + category
  common/units/                      Zombie Horde, Zombie Brutes, Infected Hounds
  common/units/equipment/            Reanimation Serum I–III
  interface/                         sprites (.gfx)
  gfx/                               icons (generated, see below)
  localisation/english/              names and descriptions
tools/
  validate.py                        static checks for the whole mod
  generate_art.py                    redraws every icon (needs Pillow)
  clausewitz.py                      small parser for Paradox script files
```

Every file the mod adds has `zombie` in its name, so it never replaces a
base-game file.

## Development

```
python tools/validate.py        # checks techs, decisions, units, equipment, localisation, sprites
pip install pillow
python tools/generate_art.py    # regenerate all icons after editing the drawings
```
