# Report presentation support

Version 0.20.0 retains presentation metadata from PBIX/PBIP reports, including legacy UTF-16 layouts. Existing saved native reports are upgraded from their retained source files without reimporting model data.

Supported mappings include nested visual group positions and layer order; transparent visual, page and wallpaper backgrounds; borders, rounded corners, shadows and padding; common geometric shapes and arrows; formatted textbox runs; embedded raster images and HTTP(S) image URLs; report theme palettes, stable category colors and visual color overrides; common axis, legend, line, area, bar, donut and table styling. Field-based colors and supported conditional comparisons are applied when their inputs are present in the visual query result. The report canvas scales proportionally with its containing panel.

Page-navigation, back, web-URL and basic bookmark actions are supported on converted elements. Bookmark support covers page navigation, filters, slicers and visibility states where these are represented by supported source properties. Report-page tooltip mappings render converted tooltip visuals with hovered category/series and page/slicer context. This is not full Power BI bookmark, drill-through or tooltip parity.

Hidden pages are delivered only to administrators. Nonadministrators cannot download raw report bundles containing hidden pages; HTML/snapshot files containing hidden pages are likewise administrator-only. Hidden tooltip pages follow the same rule. Page visibility is not row-level security: a shared semantic model remains queryable through existing authorized query tools.

Unsupported shapes, unknown visual types, unavailable custom visuals and visuals whose queries cannot be translated are omitted from the canvas. Reasons are recorded in Compatibility instead of leaving empty boxes. An image which fails to load is removed. Original metadata remains in the saved model for future mappings.

Limitations: this is a best-effort renderer, not pixel-identical Power BI execution. Proprietary effects, unsupported conditional-format expressions, complex bookmark states and custom visual host requirements may differ. Embedded raster assets are limited to 8 MB per image and 32 MB per report; SVG resources are not embedded. External image URLs need network access and browser permission/CORS behavior may affect them. Color domains use up to 1,000 distinct values per supported field, with deterministic fallback colors beyond that bound.

Validation: presentation fixtures cover legacy layouts, themes, embedded assets, nested group positions, hidden-page and source-export authorization. JavaScript tests compile styled chart specifications to SVG and check shape paths, colors, selectors, safe image URLs, conditional rules, axes and legends. Browser inspection verified shapes, the embedded logo, backgrounds and proportional text on LearnPowerBI.

## Interactive Explorer corrections (0.20.1)

Line and scatter axes preserve explicit minimum/maximum independently, including zero bounds, without Vega rounding those limits. Automatic line/scatter scales do not force zero. Life in Europe Original uses automatic line ranges rather than explicit saved bounds; its population trend now fits the actual values.

Azure Maps with an enabled filled-map layer convert on import to the local country choropleth; other Azure Maps convert to the point-map path. Country geometry and optional zoom controls use the existing local Vega renderer, without an Azure service/key. Azure basemap tiles and proprietary additional layers are not reproduced. Filled-map gradients use the source two-color fill rule where present. Scatter country/category labels preserve their visibility, size, font and color while retaining zoom.

Custom button images, including embedded Home icons, render without invented navigation text. Small scalar cards use source label formatting and omit hidden category labels and default-off titles. Bookmark display snapshots apply group and per-visual visibility independently and recompute inherited visibility. A unique obsolete group reference can be reconciled with a unique unmatched current group when all descendants occur in the saved snapshot; ambiguous references are not guessed.

Existing saved native reports receive these metadata changes automatically; no data reimport is required. Tests cover import mappings, owned versus inherited visibility, obsolete group reconciliation, exact and one-sided axis bounds, layered scatter SVG rendering, custom icons, and repeated bookmark switching. Browser verification uses Interactive Explorer in Life in Europe Original.

## Map navigation and line-axis ordering

Numeric line/area x-axes use a continuous scale unless the source explicitly selects a categorical axis. This preserves chronological year positions even when the source query returns rows sorted by a measure. Categorical axes retain the source query order. Bookmark order-by snapshots are restored with the bookmark. Continuous year axes do not round their range beyond the available years.

Converted Azure Maps omit color/size legends by default unless explicitly enabled. Other supported visuals honor an explicit legend-off setting for quantitative as well as categorical legends.

Hover over the map and turn the mouse wheel to zoom around the pointer. Holding the middle button and dragging vertically also zooms. Left-button dragging pans; a click on a data country or point selects it and filters the other visuals. Dragging suppresses that click selection. Ctrl/Cmd-click continues to support multiple country selections. The Fit map to data button (or Home while the map is focused) restores the fitted view; plus/minus and directional controls remain available.

The initial map fits nonblank data countries or coordinate points, refits when the location set changes, and adjusts to responsive layout until manually navigated. Fitting uses the actual completed projection viewport after legends and padding. Manual views persist during other visual interactions with the same location set. Country fitting uses the largest polygon to keep distant overseas territories from dominating the extent. All fitting and navigation paths share finite 1–65,536 zoom bounds. Nonzero local extents retain their precision; a single or coincident point uses a bounded regional default. The base geography is available for panning outside the fitted region.

Validation includes live projection tests for all four map mappings; mouse-event checks for wheel, middle-button zoom, drag/click separation, resize, fit reset and cleanup; and browser checks on Life in Europe Original showing chronological years, a legend-free Europe extent, wheel zoom, panning and Germany selection filtering the trend chart.

## Deep Dive compatibility (0.21.0)

Top N source subqueries with one category and one SQL-translatable ranking expression now translate into contextual ranking filters. Bottom N uses the opposite ranking direction. Ranking excludes blank results, preserves ties at the boundary, and applies current report/page/visual/slicer/cross-filter predicates before ranking. More complex Top N subquery shapes are rejected rather than displayed unfiltered.

The custom host accepts a package registered under its exact GUID or the same GUID plus `_DEBUG`. Categorical mappings can omit an optional series/legend role, allowing the installed MAQ Box and Whisker package to render. The known violin-plot visual in this report has an external-dependency bundle; its query and source color are mapped to a local Vega kernel-density silhouette. These small overlays are data visuals rather than embedded images.

Deep Dive was verified with four MAQ box plots, eight Top/Bottom 5 bar charts and four local violin overlays. CSV downloads were checked for both summarized Top 5 values and the 25 underlying country/year rows for the same five countries. See the README for CSV limits and measure-lineage caveats.

## Filter inspection

The report viewer includes a filter inspector with report/page/visual scopes, current slicer state, and cross-visual selection applicability. It shares the viewer's live state and filter parser rather than creating an independent filter execution path. Source filters are read-only; interactive clearing uses the existing slicer/selection state. Visuals hidden by bookmarks are excluded from the visual selector, while active hidden slicers remain visible as part of the actual query context.

Validation covers source aliases, inverted selections, blanks, inactive filter wells, Top/Bottom N descriptions, unknown predicates, scope counts, hidden visuals and selection applicability. Browser checks on Deep Dive verified live Southern Europe slicer changes, Spain chart selection, source-visual exclusion, effects on another visual, and clearing both interactive restrictions.
# Compact page navigation icons

The converter separates overlapping compact navigation icons in the upper-left of a page with a two-unit gap and fits their images inside the corrected bounds. Original bounds are retained as `navigationSourceBounds`. Other report elements and intentional stacked icon states keep their positions; existing navigation actions are preserved. Saved native reports are upgraded automatically from their retained source.

## Field parameters, bookmark buttons and range slicers

Imported query roles with `fieldParameters` now resolve the selected parameter-table identity into a model measure or column before planning the visual query. Parameter tables are imported as bounded metadata (up to 256 choices), with no imported code execution. Single field selections work with saved identities, dropdown changes and bookmark-restored selections; multiple-field parameter expansion is not yet implemented.

Bookmark projection changes are applied alongside display snapshots. Overlapping bookmark button variants in a common button row preserve their active/inactive state using opaque selected fill and lighter unselected fill. Existing source colors and action targets are retained.

Numeric slicers explicitly configured as `Between` render inclusive lower/upper number inputs and range handles. Basic and dropdown slicers retain their configured mode, including when bookmarks switch between separate slicer visuals. Ranges affect page visual queries through the common filter engine and appear in the Filters pane. Existing native reports upgrade automatically without reimporting.

## Canvas, controls and report formatting

Theme color references reserve positions 0/1 for background/foreground and start the data palette at position 2. This mapping is shared by canvas fills, shapes, text and charts. Raw theme style entries and explicit visual properties both participate in the cascade. Page styles include canvas and wallpaper images, sizing and transparency; image opacity is independent of the surrounding interface. Rounded rectangles preserve circular physical corner radii rather than stretching square SVG corners.

Slicers preserve source header/item/date/number font settings and colors. Date `Between` slicers use date inputs with inclusive end dates, while numeric ranges retain numeric handles. Slicers/filter controls do not offer data exports. Classic cards center their callout by default and respect supported alignment overrides. Bar/column data labels retain their source font as a maximum size and shrink to avoid overlapping neighboring categories. Percent-of-grand-total projections receive percentage formatting.

Advanced Button slicers retain image-valued tiles when image formatting or an Image URL field is declared. URLs use the shared image protocol checks; source image fit, tile rows/columns, selected/unselected fills, value fonts, outlines and strict single selection remain active. Image-only buttons do not print the URL over the poster. The legacy slicer field header is omitted for Button slicers unless explicitly enabled; an authored visual title remains independent. Image tiles expose the same hover callbacks and typed categorical selections as other slicer values.

Matrix visuals use a shared hierarchy renderer with expandable row levels and pivoted column groups. Each expanded level and grand total is queried at its own grain, so non-additive measures are not summed from child rows. Expansion requests use the session query cache. Each request retains the 1,000-group preview limit; narrow filters for complete results. Matrix column headers sort loaded sibling groups independently, keeping children with their parents and grand totals last. Sorting toggles ascending/descending with click, Enter or Space and makes no database request. The selected order also applies when additional groups are expanded. Exact saved expansion states, column drill controls, and all Power BI subtotal/layout variants are not yet reproduced. Historical line data renders separately from Power BI forecast transforms, which are explicitly marked as untranslated. Font families are retained as CSS references; unavailable fonts use browser fallbacks.

## Rich text and inline icons

Text boxes use their own compact paragraph line height and default inset rather than inheriting the application's body-paragraph spacing. Source font sizes, alignment, blank lines, repeated spaces and tabs are retained. Missing run sizes inherit the paragraph's initial run size or theme label default. Bullet and numbered paragraphs render as semantic lists with hanging indents, with supported list levels and paragraph spacing. Supported web/email links remain escaped, protocol-checked links.

Small image/icon visuals over a text box can occupy nearby whitespace placeholders in the source text. The renderer fits those icons to the text line, keeps the reserved horizontal spacing, and delegates supported navigation actions to the original visual. This handles navigation instructions and icon attribution rows without report-specific IDs or text matching. Icons without a nearby matching placeholder keep their original report positions. The same layout is included in snapshot capture.

## Table formatting and cached sorting

Native tables and matrices resolve formatting selectors against model/query references as well as display names. Primary/secondary row foregrounds and backgrounds, header colors/fonts/alignment, column formatting and supported field/conditional colors are applied to the available query values. Common Circle, Sign, Arrow, Flag and Star high/medium/low icons render as accessible SVGs; `IconOnly` hides the raw value in the cell while preserving it in the query cache and data export. Conditional rules requiring a field absent from the visual result are not evaluated through additional queries.

Click a column header, or press Enter/Space while it is focused, to sort the current loaded result. Repeat to reverse direction. Sorting compares raw values rather than formatted percentages, moves existing row elements, and reapplies row formatting without querying the server. Equal values keep their source order and blanks remain last. A preview limited to 1,000 rows sorts those cached rows only; filtering or reloading obtains a new result. This sorting control applies to converted native tables, not arbitrary imported HTML.

Bar/column label settings use the shared theme resolver, including theme-based font colors and default-selector formatting entries.

Line and area charts with secondary Y fields keep separate left/right value scales. Each axis retains its model number format and source display units, bounds, visibility, title, fonts and colors, including modern `y2Axis.sec*` and legacy secondary-axis settings. Series colors remain stable across both axes. Data labels, trend lines and cross-highlights use their corresponding axis so a percentage series does not inherit a revenue scale. The same axis formatting resolver also applies to combination charts.

Tables and matrices restore default alternating row backgrounds when omitted from the PBIX. Explicit primary/secondary colors, equal colors, banding-disabled settings and the None style preset take precedence. Banding is reapplied after local table sorting and matrix expansion.

## Table and Matrix data bars

The shared table presentation renderer reads `columnFormatting`, scoped `values`, and `cellElements` data-bar definitions by model/query metadata aliases, including renamed measures and repeated Matrix value columns. Bars preserve literal/theme colors (including maxColor/minColor/foreground tokens), positive and negative ranges, a zero axis, fixed numeric minValue/maxValue, reverseDirection and hideText. Blank/non-numeric cells have no bars. Text remains accessible when hidden visually; exported and cached values remain numeric. Bars are independent of background/foreground colors and banding, and are redrawn without duplication after local sorting or Matrix expansion.

Automatic bounds use eligible numeric cells in the loaded visual result, excluding Matrix grand totals for instances-only rules. Preview limits still apply; exact model-wide auto bounds beyond the loaded result are not queried separately. Matrix grand-total metadata supports instances-and-totals (0), instances-only (1), and totals-only (2), following [Microsoft matching-option definitions](https://github.com/microsoft/powerbi-visuals-utils-dataviewutils/blob/main/src/dataViewWildcard.ts). Arbitrary measure-based bounds requiring additional fields/queries and every legacy gradient/border option are not implemented.

Matrix headings contain only authored source title text; generated projection-label headings are omitted. Matrix scroll containers participate in pointer hit testing so headers and scrolling remain interactive on transparent report canvases.

Matrix and table cells support assigned report-page tooltips through the shared tooltip engine. Matrix value-cell context includes row ancestors and pivot-column ancestors, while subtotal and grand-total contexts omit absent dimensions. Sorting and expansion retain the correct displayed identities. Tooltip settings with show disabled remain disabled. Legacy hidden tooltip pages with enabled Canvas assignments are retained for hovering without entering ordinary page navigation; unrelated hidden pages remain restricted. Existing saved manifests are recognized on load without reimport. Tooltip charts retain their assigned visual boxes and display the full plotted result without horizontal expansion or category windowing; tooltip tables can still grow to reveal their content. The complete tooltip page scales to the available viewport without scrollbars.

Matrix sparklines resolve each value field's `sparklines` formatting selector. The source chart type chooses Line or Column, consistent with [Power BI sparkline settings](https://learn.microsoft.com/en-us/power-bi/create-reports/power-bi-sparklines-tables). Authored/theme data colors and line width are retained. Column sparklines include zero in their vertical scale, draw negative values below zero, and preserve empty period slots without inventing values. Line sparklines leave gaps for blank/non-numeric values. These settings apply when existing reports render and during future conversions; each sparkline field retains its own formatting.

Tables, like matrices, display only source-authored titles. Generated field-name headings (for example Date / Count of Index) are omitted for existing reports and future conversions.

Pie/donut labels now render source label styles (category, value, percentage), numeric precision/units and source font/color settings. Omitted label visibility uses the pie/donut default of visible values; explicit hidden labels remain hidden. Outside labels use separated callouts for small slices. Horizontal categorical legends wrap into width-aware columns rather than overflowing as a single row; pie/donut radii reserve space for legends and labels. These shared renderer changes apply to existing and future imports.


## Compatibility foundations — 2026-10-25

See README: pinned offline PBIR validation, schema diagnostics, layered formatting/provenance, contextual dynamic format strings, independent visual nonempty handling, immutable scoped/multi-page bookmark plans, and compound hover/selection identities. These extend existing mappings rather than promising pixel-identical Power BI execution. Rendering fallbacks are observable on Compatibility; unsupported schema versions remain preserved. Hidden-page authorization remains unchanged.


Static PBIR DateSpan filters support day, month, year, decade, second, minute and hour spans, including aggregate post-filters. Week spans and dynamic Now expressions require additional calendar semantics. Scatter X projections bound to text model columns use categorical axes and retain model sort order. Numeric X validation and sampling are unchanged. Optional formatting reuses the visual's already resolved Top N domain.
