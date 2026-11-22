# Editorial application-wide UI — Stage 2

## Design direction

**Character Marketplace × Book Discovery × Literary Editorial**. The same warm paper, plum ink, refined serif display headings, terracotta book/edition details, two-column cover grids, and simple printed-page surfaces are used everywhere in the existing app.

## Screens included

- **Marketplace:** discovery cover cards, search, collection filters, two-character cast tray.
- **Story studio / library:** start scene, list/search/filter saved stories, story-card previews and sample scenes.
- **Casting and editor:** selected actors A/B, portrait grid, character detail actions, scene brief input and saved setup state.
- **Character library / create / detail:** card grid, search/archive, description form, image-generation progress, cover portrait and character profile, edit/refine forms, portrait and profile versions.
- **Reading and direction:** stage context, live story reader, speaker/narration/action blocks, continue/intervene/takeover, rewrite, direction cards and choice sheets.
- **Review & history:** scene review, saved story, export preview, scene and character version sheets.
- **All dialogs and settings:** common paper sheet, typography, form controls, error/loading state and destructive buttons.
- **Account gate:** same typography/controls on first-time local sign-in.

The current UI is implemented in React / CSS, not as a Figma runtime. It is inspired by the user's Bazar Books UI Kit and earlier Wattpad / Literary Archive preferences. No Bazar binary design files or copyrighted book imagery are committed. Existing private character images retain their prior access permissions.

## Files

- `web/app/marketplace/marketplace.css`: bookshop-themed Discover.
- `web/app/rehearsal/rehearsal.css`: retained layout and behaviors, legacy dark palette migrated to warm paper.
- `web/app/rehearsal/editorial.css`: unified detailed design rules for **every** existing Rehearsal and Mobile Character Studio view.
- `web/app/editorial-global.css`: account gate and body-level theme.
- `web/components/rehearsal-app.tsx`: keeps all existing state handlers and scene flows, updates navigation and headers.
- `web/components/mobile-character-studio.tsx`: retains creation/edit/history semantics with consistent labels.

## Validation plan

Run `npm run typecheck`, `npm run build`, backend regression tests, and mobile Playwright flows. New `web/e2e/editorial-ui.spec.ts` checks calculated styles and actual open/edit/scene/reading/dialog flows at phone width.

## Boundaries

No public character listings, wallet authentication, Solana payment, creator payout or paid entitlements. Existing scenes remain local account objects and do **not** become publicly accessible. The old working scene engine is not replaced by a fake static UI.
