# MAHA interface consistency

- Books is the reference for catalog browsing on Books and Knowledge.
- Order: heading/actions, search, category chips, sort/filter row, result count, results.
- Both pages must load `catalog-controls.css` after their page-specific styles. Put shared search, labels, control dimensions, spacing, focus treatment and caret graphics there.
- Sort/filter labels sit above their controls. Preserve native select and details keyboard behavior. Use the same downward caret and control height across both pages.
- Keep page-specific filters and permissions; consistency does not mean identical filter options.
- Check both catalogs at desktop and phone widths when changing shared controls. Do not claim a source update is deployed until the live files have been installed and checked.
- Keep content local. Do not publish books or private configuration to cloud hosting.
