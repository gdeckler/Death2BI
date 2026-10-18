# Death2PowerBI Python DAX support — 0.11.0

Reviewed against [Microsoft's DAX function reference](https://learn.microsoft.com/en-us/dax/dax-function-reference) on October 17, 2026. The implementation registers **186 functions**, including the earlier evaluator's functions, with bounded overloads. This is not full Power BI/Analysis Services equivalence. The accompanying `dax-function-catalog.json` inventories 386 distinct names from linked reference category listings, marks each as implemented-bounded or not-implemented, and retains its Microsoft reference URL. INFO's category page does not enumerate its functions as linked entries, so individual INFO functions are not exhaustively inventoried.

## Analysis by function family

| Reference family | Implemented behavior and remaining work |
| --- | --- |
| Aggregation | Column aggregates, row iterators, count variants, product, median, variance and standard deviation. Mixed-type/A variants and variant overloads need further work. |
| Date and time | Dates, times, components, month ends, date differences, weeks, generated calendars, local/UTC clocks. ISO text only; locale parsing, business calendars and other week return types need work. |
| Filter | CALCULATE/CALCULATETABLE, filter removal, intersection, external-selection totals, VALUES, SELECTEDVALUE, FILTERS and lookup. Complex correlated predicates and arbitrary shadow contexts need engine changes. |
| Financial | PMT, PV, FV and NPER annuity calculations. Bond/day-count functions, IRR/XIRR, iterative rate solvers and depreciation are not implemented. |
| INFO | Not implemented: Microsoft DMV/server metadata contracts do not map directly to the converted DuckDB model. Local model metadata remains available in the app. |
| Information | Type/blank/error checks, scope checks, direct/cross-filter checks. Security identities and service/environment information are not implemented. |
| Logical | IF, IF.EAGER, SWITCH, AND/OR/NOT, TRUE/FALSE, COALESCE, BLANK and error handling. Lazy branches and IF.EAGER evaluation differ deliberately. |
| Math and trig | Common arithmetic, rounding, transcendental, combinatorial and integer operations; explicit domain/resource limits. Random/statistical distributions and remaining specialized functions are not implemented. |
| Other | Service-specific identity, RLS, calculation-group and visual evaluation features are not implemented. |
| Parent and child | PATH construction, lookup, containment and length, with cycle/missing-parent/conflict checks. |
| Relationship | RELATED and RELATEDTABLE over supported active relationships. USERELATIONSHIP, CROSSFILTER, limited/many-to-many and ambiguous relationship overrides are not implemented. |
| Statistical | Median, sample/population dispersion, percentiles, TOPN and RANKX. Distributions, regression and advanced window functions are not implemented. |
| Table manipulation | SUMMARIZE, FILTER, ROW, projection/extension, set operations, CROSSJOIN and series. GROUPBY, SUMMARIZECOLUMNS, rollups, arbitrary lineage propagation and window relations need further work. |
| Text | Common transformations, substitution, one-based search, Unicode, concatenation and bounded FORMAT. Full OLE format masks and non-English cultures are not implemented. |
| Time intelligence | Classic single-date-column DATESBETWEEN, FIRSTDATE/LASTDATE, YTD/QTD/MTD date sets and totals. SAMEPERIODLASTYEAR supports classic contiguous date-column selections, including leap-day/month-end extension. DATEADD, fiscal-year arguments and tagged-calendar overloads need further work. |

## Context and semantic limits

The frontend sends the original external filters, current group filters and projected grouping columns separately. Python retains filter column lineage, applies CALCULATE overwrite/intersection rules, propagates supported active relationship filters, performs model-measure row-context transition and keeps variables in their original evaluation context. CALCULATE filters are evaluated before transition; modifiers are applied before explicit filters. Expressions never become executable uploaded Python.

- CALCULATE supports same-table Boolean predicates, lineage-preserving table filters, ALL, REMOVEFILTERS, ALLEXCEPT and KEEPFILTERS. Replacing only part of a compound multi-column predicate or a correlated multi-table selection raises an error. Filter arguments with multiple different model-table lineages and extended-table clustering are not fully supported.
- ALLSELECTED uses the query's original external filters; it supports visual totals but rejects direct row-context use. Nested shadow filter contexts inside iterators are not implemented. ALLEXCEPT as a table expression is unsupported.
- ISINSCOPE uses actual projected query group columns; slicer selection alone does not put a column in scope. Matrix subtotal/rollup hierarchy evaluation is not implemented.
- SUMMARIZE supports a model table, grouping columns from that table or reachable dimensions, and name/expression pairs evaluated per group. Unqualified group columns resolve against its input table. Expression-table clustering, rollups, duplicate output column names and arbitrary extension-column lineage are rejected. Summary row lineage is retained for measure context transition.
- VALUES uses imported rows. Power BI's synthetic unknown-member blank rows for broken relationship keys, auto-exist, full expanded-table semantics and engine collation are not fully reproduced. Comparisons/distinctness use Unicode case folding, not the model's locale-specific collation.
- Date-column time intelligence supports typed dates at midnight and calendar-year/quarter/month boundaries. It does not infer marked date-table metadata or remove other Year/Month column filters automatically. Use direct filters on the date column for these functions. Fiscal/calendar-tagged overloads are rejected.
- SUM/MIN/MAX and iterator variants support the ordinary numeric/date/text forms shown in the tests. Logical values in MIN/MAX and variant-selection overloads are rejected. MEDIANX includes blanks as zero; MEDIAN ignores blanks. Percentile iterators currently reject blank results; explicitly filter blanks first. Population/sample statistics need at least two numeric values.
- RANKX supports ascending/descending and skip/dense ties. Floating-point ranking uses Python numeric precision, without VertiPaq fixed-decimal guarantees. TOPN includes all ties at its cutoff; result ordering is an implementation detail, not a DAX ordering guarantee.
- ADDCOLUMNS/SELECTCOLUMNS, ROW, CROSSJOIN and generated tables can feed iterators. Arbitrary virtual-table column lineage is not available for CALCULATE/context transition. Set operations retain lineage only when their input column lineages match.
- FORMAT returns text. Its supported forms are common decimal/percentage/grouping masks, basic currency literals and negative/zero sections, selected ISO/date masks and named formats with en-US locale. Other masks/locales raise an error. FORMAT should not be used when a chart requires a numeric measure; use model format strings instead.
- Text positions are one-based. SEARCH and CONTAINSSTRING support wildcards/tilde escapes. FIND and CONTAINSSTRINGEXACT use literal, case-sensitive matching. RIGHT(...,0) returns an empty string.
- A single visual has a 30-second shared Python budget (configurable with D2PBI_DAX_SECONDS), a one-million-operation limit, up to 1,000 groups, 50 projections, 100,000 rows per table/context and 5,000 filter tuples. DAX-request DuckDB work is interrupted after the configured Python time budget plus two seconds; standalone SQL queries retain their ten-second interrupt. D2PBI_DAX_STEPS configures the shared step limit. Time and step failures report distinct messages and measured usage. Shared caches retain at most 64 table contexts/200,000 rows. Resource limits cannot be swallowed by IFERROR.

Unsupported syntax/functions/overloads report an explicit error. Some combinations involving unimplemented engine semantics remain outside the compatibility contract even when their component function names are registered. The registry is a capability inventory, not a certification of full DAX compatibility.

## Validation

`py test_dax_reference.py` exercises every registered function, with expected results for scalar examples and grouped/context fixtures. It includes filter replacement versus KEEPFILTERS, multiple filters on the same column, CALCULATE modifier order, relationship propagation, iterator measure transitions, summary groups, direct versus cross filters, scope, external-selection totals, percentile/statistical results, generated tables, paths, date sets/totals, blank handling, lazy errors, rounding, text search and resource limits. `py test_dax.py` retains the supplied Life Satisfaction Change regression across year/country contexts.

The saved Life in Europe model's 40 measures and Power BI Releases model's three measures were also evaluated in an unfiltered context. Evaluation success does not certify agreement with Power BI across every filter context. LearnPowerBI contains measures that can exceed the current Python budget; these remain explicit limitations. There is no Microsoft engine oracle in this test environment; reference examples and independently constructed expected results are used.

## Registered functions by implementation family

### Aggregation (28)

`AVERAGE`, `AVERAGEX`, `COUNT`, `COUNTA`, `COUNTAX`, `COUNTBLANK`, `COUNTROWS`, `COUNTX`, `DISTINCTCOUNT`, `DISTINCTCOUNTNOBLANK`, `MAX`, `MAXX`, `MEDIAN`, `MEDIANX`, `MIN`, `MINX`, `PRODUCT`, `PRODUCTX`, `STDEV.P`, `STDEV.S`, `STDEVX.P`, `STDEVX.S`, `SUM`, `SUMX`, `VAR.P`, `VAR.S`, `VARX.P`, `VARX.S`

### Date and time (21)

`CALENDAR`, `DATE`, `DATEDIFF`, `DATEVALUE`, `DAY`, `EDATE`, `EOMONTH`, `HOUR`, `MINUTE`, `MONTH`, `NOW`, `QUARTER`, `SECOND`, `TIME`, `TIMEVALUE`, `TODAY`, `UTCNOW`, `UTCTODAY`, `WEEKDAY`, `WEEKNUM`, `YEAR`

### Filter (12)

`ALL`, `ALLEXCEPT`, `ALLSELECTED`, `CALCULATE`, `CALCULATETABLE`, `FILTERS`, `ISONORAFTER`, `KEEPFILTERS`, `LOOKUPVALUE`, `REMOVEFILTERS`, `SELECTEDVALUE`, `VALUES`

### Financial (4)

`FV`, `NPER`, `PMT`, `PV`

### Information (15)

`ERROR`, `HASONEFILTER`, `HASONEVALUE`, `ISBLANK`, `ISCROSSFILTERED`, `ISEMPTY`, `ISERROR`, `ISEVEN`, `ISFILTERED`, `ISINSCOPE`, `ISLOGICAL`, `ISNONTEXT`, `ISNUMBER`, `ISODD`, `ISTEXT`

### Logical (11)

`AND`, `BLANK`, `COALESCE`, `FALSE`, `IF`, `IF.EAGER`, `IFERROR`, `NOT`, `OR`, `SWITCH`, `TRUE`

### Math and trig (40)

`ABS`, `ACOS`, `ACOSH`, `ASIN`, `ASINH`, `ATAN`, `ATANH`, `CEILING`, `COMBIN`, `COS`, `COSH`, `DEGREES`, `DIVIDE`, `EVEN`, `EXP`, `FACT`, `FLOOR`, `GCD`, `INT`, `LCM`, `LN`, `LOG`, `LOG10`, `MOD`, `MROUND`, `ODD`, `PI`, `POWER`, `QUOTIENT`, `RADIANS`, `ROUND`, `ROUNDDOWN`, `ROUNDUP`, `SIGN`, `SIN`, `SINH`, `SQRT`, `TAN`, `TANH`, `TRUNC`

### Parent and child (5)

`PATH`, `PATHCONTAINS`, `PATHITEM`, `PATHITEMREVERSE`, `PATHLENGTH`

### Relationship (2)

`RELATED`, `RELATEDTABLE`

### Statistical (5)

`PERCENTILE.EXC`, `PERCENTILE.INC`, `PERCENTILEX.EXC`, `PERCENTILEX.INC`, `RANKX`

### Table manipulation (12)

`ADDCOLUMNS`, `CROSSJOIN`, `DISTINCT`, `EXCEPT`, `FILTER`, `GENERATESERIES`, `INTERSECT`, `ROW`, `SELECTCOLUMNS`, `SUMMARIZE`, `TOPN`, `UNION`

### Text (21)

`CONCATENATE`, `CONCATENATEX`, `CONTAINSSTRING`, `CONTAINSSTRINGEXACT`, `EXACT`, `FIND`, `FORMAT`, `LEFT`, `LEN`, `LOWER`, `MID`, `REPLACE`, `REPT`, `RIGHT`, `SEARCH`, `SUBSTITUTE`, `TRIM`, `UNICHAR`, `UNICODE`, `UPPER`, `VALUE`

### Time intelligence (10)

`DATESBETWEEN`, `DATESMTD`, `DATESQTD`, `DATESYTD`, `FIRSTDATE`, `LASTDATE`, `SAMEPERIODLASTYEAR`, `TOTALMTD`, `TOTALQTD`, `TOTALYTD`



## Employee matrix evaluation update

Unqualified column arguments such as `COUNT([EmplID])` now resolve against the current measure's home table, including nested measures. Basic model-column SUM/AVERAGE/MIN/MAX/COUNT/COUNTA can run directly in DuckDB where their type semantics match; other aggregate forms retain the Python path. SQL results are cached only within the visual and its exact filter context. Base-table FILTER/ISBLANK and FILTER/NOT(ISBLANK) used inside CALCULATE can carry their original rowset as a SQL predicate instead of materializing every employee row. Generic iterator/table materialization limits are unchanged.

SAMEPERIODLASTYEAR supports a typed classic date column and a contiguous selection over a continuous date table. It replaces the calendar table filters when applied in CALCULATE, preserves other dimension filters, and includes classic leap-day and end-of-month extension behavior. Calendar-reference, fiscal/lunar and arbitrary table-expression overloads remain unsupported. See [Microsoft's reference](https://learn.microsoft.com/en-us/dax/sameperiodlastyear-function-dax).

`py test_employee_dax.py` covers home-table resolution, nested measures, aggregates over 120,001 fact rows, captured FILTER contexts under ALL, prior-year calendar replacement and leap-month extension. All three Employee Hiring and History matrix queries completed (210, 60 and 210 rows) within the original 30-second/1,000,000-step budget. Thirty populated measure cells across the three pages matched independently written SQL, including current/prior-year counts, active employees, bad hires and ratios.
