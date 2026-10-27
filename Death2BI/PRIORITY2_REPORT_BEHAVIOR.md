# Priority 2 — report behavior and fidelity (9–17)

Implemented in Death2BI 0.22.0. These are shared import, query and rendering paths, rather than changes to individual report files. Existing reports pick up new presentation metadata when next loaded (report parser version 32); semantic data and source DAX are preserved.

| Item | Behavior |
|---|---|
| 9. Cross-highlighting | Explicit HighlightFilter interactions retain base values and query the selected contribution separately. Supported bar, column, line, area, pie and donut renderers dim the full values and overlay the contribution. Stacked contributions retain the full segment offsets; normalized stacks use the full denominator. Unsupported targets retain filtering behavior. NoFilter interactions remain disabled. |
| 10. Synchronized slicers | Changes propagate to matching syncGroup members across pages, including hidden slicer visuals. Filter synchronization respects filterChanges; field synchronization respects fieldChanges. Field identities are translated when members intentionally use different fields. |
| 11. Tooltip resolution | Authored manual assignments and disabled settings take precedence. Automatic field-associated pages resolve from pageBinding parameters, including bound-filter references. Hover context retains compound identities and applicable highlight filters; acceptsFilterContext is respected. Hidden tooltip pages remain hover-only for ordinary accounts under the existing access policy. |
| 12. Drillthrough and hierarchy drill | Select a single data identity and use “Drill through” in the report interaction bar for compatible target pages. All required target fields must be present. Target-page filters use the selected compound identity; additional source filters follow acceptsFilterContext. “Back to report” returns to the source. Category hierarchies provide Drill up, Drill into selection and Expand next level controls. State is isolated by report/page/visual and reset when parameter fields change. |
| 13. Field parameters | Selected rowsets preserve multiple fields, measure/dimension types and model order, including relationship-filtered parameter tables. Parameter slicers retain authored single/multiple selection settings. Expanded category hierarchies use compound labels and data identities. |
| 14. Conditional formatting | Charts, cards, tables and matrices share property expression evaluation for field values, conditional rules and two/three-stop gradients. Matrix cells retain their original grouped formatting context after pivoting. Table/matrix icons and data bars remain supported; totals/subtotals respect applicability settings. |
| 15. Matrices | Preserve authored expansion paths and in-session expansion/sorting state. Support stepped and tabular row headers, level-specific row formatting, hierarchical column headers, sticky headers/totals, and separately queried row/column subtotal and grand-total grains. Totals are not summed from rendered children. |
| 16. Chart layout | Scrolling uses authored category spacing, axis/legend visibility, fonts, label rotation, series count and label needs. Explicit bar thickness/maximum size is applied by the shared style resolver. Existing bounded sampling and scrolling implementations remain in use. |
| 17. Locale and units | Import report locale and defaultDisplayUnitsToNone. Vega views receive locale-specific number/time formatting; native labels, cards, tables, matrices, pie percentages and default DAX FORMAT use report locale. Explicit FORMAT locale overrides and explicit visual unit settings continue to win. |

The shared DAX filter-context operation also now projects compound selections when CALCULATE replaces only part of a multi-table selection, preserving correlations among the remaining fields. This was required by a live cross-highlighting regression.

## Validation

- 55 Python tests passed, including account isolation and RLS regression coverage.
- 38 JavaScript test files passed, including actual Vega-Lite compilation of highlighted chart specifications.
- Existing Midnight Shift report: base bars remain visible and the selected contribution renders without a calculation warning.
- Existing World Champs report: language selection synchronizes across its five pages.
- Isolated browser matrix fixture: saved expansion, collapse/sort controls, tabular layout, hierarchical columns, separately queried subtotal grains, conditional colors and German numeric formatting passed.
- Mixed field-parameter types, ordering, disabled tooltips, compound drillthrough filters, independent sync flags and stale drill-state invalidation have targeted regression checks.

## Boundaries

This does not provide complete Power BI parity. Custom-visual highlight DataViews and cross-report drillthrough are not included. Chart hierarchy drilling is provided for supported category projections; matrix row expansion has its own controls. Complex DAX may still reach evaluator budgets, and optional formatting may be omitted with an explicit warning. Unsupported native formatting properties continue to appear in the compatibility audit rather than being treated as exact reproductions. Expansion state is retained for the current signed-in application session, not as an edited PBIX or a permanent personalized bookmark.

The clean application and Docker build packages exclude installed reports, accounts, federation credentials and personal settings. No installed reports were deleted.

## Documentation references

- [Power BI highlighting](https://learn.microsoft.com/en-us/power-bi/developer/visuals/highlight)
- [Power BI drillthrough](https://learn.microsoft.com/en-us/power-bi/create-reports/desktop-drillthrough)
- [Report tooltip pages](https://learn.microsoft.com/en-us/power-bi/create-reports/desktop-tooltips)
- [Microsoft report schemas](https://github.com/microsoft/json-schemas/tree/main/fabric/item/report/definition)
