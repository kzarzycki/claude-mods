# UI Prototype

Several radically different variations of one screen on a single route, switched from a floating bottom bar. The user flips between them, picks one or combines parts, and the rest are thrown away.

## Where the variants live

- **Existing page (default).** Render the variants on the page's existing route behind `?variant=`, keeping its data fetching, params and auth; only the rendered subtree swaps. This also covers something new that would naturally live inside an existing page (a dashboard section, a settings card, a step in a flow): mount the variants inside the host. Variants judged in a vacuum all look fine; a real header, sidebar, data and density expose design problems.
- **New page (last resort).** Only when nothing existing could host it: add a throwaway route following the project's routing convention, with `prototype` in its path or filename, and the same `?variant=` switch.

## Build

- Default to 3 variants and cap at 5; beyond that they stop being radically different.
- Write the plan as a one-line comment at the top of the prototype, e.g. "Three variants of the settings page, switchable via `?variant=`, on the existing `/settings` route."
- Make variants structurally different: layout, information hierarchy, primary affordance. Differences in colour or copy alone are a tweak, not a prototype; redo a draft that comes out too close to another. Share small pieces like a header, never the layout.
- Export each under a clear name (`VariantA`, `VariantB`, ...).
- Keep variants read-only and point any mutation at a stub: the question is how it looks, not whether the backend works.
- One switcher on the route renders the variant named by `?variant=` (default `A`); on an existing page, the data fetching stays above it.

## Floating switcher

One shared component, placed wherever the project keeps shared UI: a fixed bar at bottom centre with a previous arrow, the current key plus the variant's name if it exports one (`B (Sidebar layout)`), and a next arrow. Both arrows wrap around.

- Arrows update the search param through the framework's router, so a variant is shareable and survives reload.
- `←` and `→` also cycle, except while an `<input>`, `<textarea>` or `[contenteditable]` has focus.
- Style it to be obviously not part of the design under review (a high-contrast pill with a shadow).
- Hide it in production builds (`process.env.NODE_ENV !== 'production'` or the equivalent), so a stray merge cannot ship it.

## Hand over and capture

Share the URL and the variant keys. Expect answers like "the header from B with the sidebar from C"; that combination is the design they want.

Once a winner is chosen, record which and why, and capture the prototype as [SKILL.md](SKILL.md) describes: the full variant set and switcher go to the throwaway branch. Main gets the winner folded into the existing page, or promoted to a real route replacing the throwaway one, rewritten to production standards because it was written under prototype constraints. Losing variants and the switcher never stay in main, where they rot and confuse the next reader.
