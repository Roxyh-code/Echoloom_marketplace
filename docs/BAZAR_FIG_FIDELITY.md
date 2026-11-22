# Bazar Books — source-derived design specification

This is extracted from the **user-supplied original** `Bazar - Books Mobile App.fig`. The Figma binary is not redistributed. The file contains 4,941 layer-change records, a `🚀 Design` canvas and a `🎲 Styleguide` canvas. The specific screen `🚀 Design > 4. Home > 4. Home` is **375 × 1082 px** with a **solid white #FFFFFF frame background**, not warm paper.

## Measured source tokens

| Role | Hex | Evidence in original file |
| --- | --- | --- |
| Home page / card background | `#FFFFFF` | `4. Home` frame and other Home screens |
| Off-white / secondary surface | `#FAFAFA` | Greyscale 50 / Home bottom navigation |
| Neutral surface | `#F5F5F5` | Greyscale 100 / numerous components |
| Border / divider | `#E8E8E8` | Greyscale 200 |
| Strong border | `#D6D6D6` | Greyscale 300 |
| Primary text | `#121212` | Greyscale 900 / Home text |
| Secondary text | `#7A7A7A` | Greyscale 600 |
| Primary purple | `#54408C` | `Primary 500` **text label** on Styleguide; present in Home instances |
| Primary violet hover | `#352368` | `Primary 600` text label |
| Purple-tinted neutral | `#FAF9FD` | `Primary 50` text label; also in Home |
| Green semantic / alternative symbol | `#307A59` | green component instance, not the chosen primary |
| Red semantic | `#EF5A56` | semantic red swatch |

**Important source inconsistency:** Inside the Styleguide, the swatches named `Primary / 500` are painted green `#307A59` while the adjacent **printed hex label** says `#54408C` (purple). The original `4. Home` subtree contains both colors. For this implementation we select the purple explicitly printed as Primary 500 and used by the Home UI. This choice is recorded, not hidden. Other sourced accents are left as isolated content/cover art, not made into the whole interface theme.

## Typography

The actual `4. Home` screen mostly uses **SF Pro Display** (with a few Roboto elements). The `🎲 Styleguide > Typography` defines **Open Sans** for headings and **Roboto** for body copy. The UI uses the SF Pro system-font stack, falling back to Open Sans / Roboto / Segoe UI / Arial. No third-party font files are redistributed.

## What changed

- Removed the invented yellow/cream `#F8F5EE` background from every app surface.
- Replaced invented brown, rust, dark plum and serif headings with white, greys, source purple and straightforward sans serif labels.
- Cards now use clean white or neutral backgrounds, compact 10px-ish corner radii and reduced ornamental decoration.
- Character covers continue to use a uniform vertical book-cover layout (the requested Wattpad/Character.AI hybrid), while the surrounding controls follow Bazar.
- Story editor, character detail, sheet overlays, reader and the account entry all follow this same system.

## Not a pixel-copy

The source is a **book commerce** design with vendors, authors and carts, while Echoloom is a two-character AI story app. We preserve user-defined functionality and adapt the system rather than reproducing Bazar's unrelated screens. We do **not** commit its `.fig`, third-party book covers or proprietary assets.

## QA

Bazar-specific color regression assertions are in `web/e2e/editorial-ui.spec.ts` and `web/e2e/marketplace.spec.ts`; the existing story and character flows run in Playwright against real app routes with isolated fake AI providers.
