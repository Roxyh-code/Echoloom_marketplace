# Mobile editorial design — first pass

This is an original implementation inspired by the user's licensed Bazar Figma design reference, Wattpad-style vertical book-cover grids and a Literary Archive direction. **No Bazar `.fig` source, purchased UI components, stock book covers or third-party portraits are redistributed in this repository.**

- New mobile-first route: `/marketplace` (now the default entry point).
- Existing `/rehearsal` remains fully operational and unchanged.
- The curated Mira/Leo samples are drawn from original pre-existing demo SVG assets and are clearly labeled **Sample**; they are not public creator listings or purchasable characters.
- Your local characters are loaded through the existing authenticated `/api/rehearsal/characters` route. Selecting two creates a local, unpaid rehearsal draft via the existing backend and opens `/rehearsal?view=setup&scene=<id>`.
- Search and collection filters work locally. The new page is a **design prototype**, not a live public Marketplace.
- Wallet, listing permissions, copyright-clearance checks, Solana payouts, orders and entitlements must be implemented before opening public publishing or payments.
- UI palette: warm paper, plum ink, terracotta highlights; serif editorial headings, understated sans-serif labels; consistent two-column portrait covers. Do not infer commercial redistribution rights from a design preview.

**Input design file (not committed):** `Bazar-Books-Mobile-App.zip` → `Bazar - Books Mobile App.fig`. Its bundled instructions describe 51 mobile screens at 375px; it uses Open Sans / Roboto. The instruction PDF calls the product a stationery app even though the bundle contains book and author imagery. The binary Figma node graph should be inspected in Figma itself before pixel-perfect design fidelity work.
