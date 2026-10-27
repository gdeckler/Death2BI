# Death2PowerBI Python DAX support — 0.11.0

Reviewed against [Microsoft's DAX function reference](https://learn.microsoft.com/en-us/dax/dax-function-reference) on October 17, 2026. The implementation registers **190 functions**, including the earlier evaluator's functions, with bounded overloads. This is not full Power BI/Analysis Services equivalence. The accompanying `dax-function-catalog.json` inventories 386 distinct names from linked reference category listings, marks each as implemented-bounded or not-implemented, and retains its Microsoft reference URL. INFO's category page does not enumerate its functions as linked entries, so individual INFO functions are not exhaustively inventoried.

## Grouped iterator safety (0.24.10)

The scalar SQL compiler declines grouped iterator extensions with nested `SUMMARIZE`, aggregates requiring multiple relationship hops, or relationship overrides. These combinations require staged evaluation to retain the group domain and can trigger native correlated-query failures. The existing bounded evaluator handles the declined plan on the same secured connection; ordinary eligible one-hop summaries remain SQL-enabled. Dependency inspection consumes the same request budget, has a bounded depth and uses a bounded request-local cache. Diagnostics include `sqlSafetyFallbacks` and `sqlSafetyReasons`.

This guard addresses native access violations and incorrect employee-level calendar denominators reproduced in LearnPowerBI. It does not rewrite source DAX, raise resource limits, truncate group domains, disable database optimizers globally, or cache data between users.

## Shared aggregates and bounded iterator plans (0.24.7)

Eligible grouped scalar plans reuse exact repeated numeric physical aggregate leaves within one secured request. Group, external and replacement filter predicates stay attached to each leaf. Iterator-local and lexical aliases, row-stack expressions and nonnumeric columns are excluded. Sharing is bounded to 64 unique leaves and 2 MB of leaf SQL per plan.

Eligible `ADDCOLUMNS` context transitions execute at most 64 group identities per SQL plan, preserving source order and expanded-row lineage across batches. Each batch uses the same connection and shared request budget. This reduces native planner pressure without truncating data or changing authored measures. Worker crashes include sanitized native exit codes; a bounded stderr tail is kept private and logged server-side.

Checks: `py -m unittest test_shared_group_aggregates test_add_columns_batches test_dax_pool test_dax_pool_http`.

## Selected table contexts and grouped parameters (0.24.4)

Explicit `ALLSELECTED(Table)` domains can carry a bounded selected-row context through `FILTER`, including nested selected medians used by quadrant measures. The proof requires a complete physical table rowset on the same secured connection and an unchanged relationship graph. Column/no-argument forms under arbitrary nested iterators, other physical row frames, and relationship override combinations remain unsupported. Row-local MIN/MAX shortcuts apply only while a proven full-row transition is unchanged. Caches are bounded and request-local.

The SQL scalar path supports deterministic SIN/COS/RADIANS and typed YEAR extraction, including existing serial-date semantics for numeric YEAR arguments. Constant predicates and lazy IF branches avoid compiling unreachable expressions. Eligible parameter selections can be folded only when independent of grouped columns, and simple same-fact CALCULATE cohorts can be shared across grouped aggregates. Partial physical-row ranking scores can use the grouped scan when ordinary context transition and preserved filter domains are proven. Unsafe combinations fall back rather than change source measures.

Checks: `py -m unittest test_allselected_shadows test_sql_trigonometry test_context_row_scores test_grouped_relationship_scans`.

## Grouped relationship scans (0.24.3)

Eligible numeric aggregate expressions can use one relational scan for the full group domain, including Top N rankings across relationship bridges. The planner supports bounded single-fact aggregates, numeric row iterators, arithmetic, `VAR` bindings, simple `IF` guards and `CALCULATE` without extra modifiers. It deduplicates bridge fan-out using a generated physical row ordinal, preserving duplicate fact rows and duplicate category names. The same secured connection and existing external-filter propagation supply every source relation; no unsecured database connection or cross-user cache is introduced.

The typed row compiler preserves BLANK identity in arithmetic and `ISBLANK`, strict and weak numeric comparisons, MEDIANX blank-as-zero behavior, count guards and empty groups. Unsupported types, context modifiers, virtual row domains and multi-fact measure expressions fall back to the existing compiler/interpreter. Existing time, step and group-domain limits remain unchanged. Temporary group relations are removed after success, interruption or failure.

Regression checks: `py -m unittest test_grouped_relationship_scans test_topn_batch`.

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
| Text | Common transformations, substitution, one-based search, Unicode, concatenation and bounded FORMAT. Full OLE format masks are not implemented; supported FORMAT masks accept explicit locales through Babel. |
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
- FORMAT returns text. Its supported forms are common decimal/percentage/grouping masks, basic currency literals and negative/zero sections, selected ISO/date masks and named formats. An explicit third locale argument (for example es-PY, de-DE or fr-FR) localizes separators and supported date names through Babel, independently per request. Omitted locales retain en-US behavior. Unknown locales and unsupported masks raise an error. FORMAT should not be used when a chart requires a numeric measure; use model format strings instead.
- Text positions are one-based. SEARCH and CONTAINSSTRING support wildcards/tilde escapes. FIND and CONTAINSSTRINGEXACT use literal, case-sensitive matching. RIGHT(...,0) returns an empty string.
- A single visual has a 60-second shared evaluation budget (configurable with D2PBI_DAX_SECONDS), a one-million-operation limit, up to 1,000 groups, 50 projections, 100,000 rows per Python table/context and 5,000 filter tuples. DAX-request DuckDB work is interrupted after the configured time budget plus two seconds; standalone SQL queries retain their ten-second interrupt. D2PBI_DAX_STEPS configures the shared step limit. Time and step failures report distinct messages and measured usage. Python caches retain at most 64 table contexts/200,000 rows. SQL temporary contexts remain within DuckDB's 512 MB memory limit. Resource limits cannot be swallowed by IFERROR.

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
# SQL execution of supported Python-evaluator plans

The bounded evaluator can lower supported scalar ASTs and `SUMMARIZE`/iterator combinations into DuckDB SQL. This includes supported VAR/RETURN bindings, aggregate measures, filtered column iterators, arithmetic, DIVIDE, IF/SWITCH, ISBLANK and ISINSCOPE. Unsupported forms return to the Python evaluator; uploaded Python or JavaScript is never executed as DAX.

External filter contexts are cached in request-local temporary tables and reused across groups. Relationship predicates that share a path constrain the same fact row, including supported bidirectional paths. Grouped categorical contexts run in bounded batches; temporal contexts use scalar plans to limit memory. Temporary tables disappear when the query connection closes and do not alter imported data. DAX requests are serialized to avoid competing for the database memory budget. Time and operation limits remain enforced.

## TREATAS support (October 23, 2026)

TREATAS now remaps an evaluated table expression onto distinct columns of one target model table. Tuple widths must match, multi-column tuples retain their combined identity, and nonmatching values do not create rows in the target. CALCULATE replacement and KEEPFILTERS intersection use the regular filter-context path and remain subject to RLS and evaluation budgets. Cross-table target column lists are rejected. Checks: `py -m unittest test_treatas`.


HTML report measures: `--` comments are tokenized outside strings; unary `NOT` is supported. `EARLIER(column[,depth])` requires an outer iterator row context. `CONCATENATEX` supports bounded multiple order-expression/direction pairs. `ADDCOLUMNS` retains base-column row lineage for qualified references/context transition; arbitrary mixed virtual table filter lineage remains bounded. Numeric date conversions use the DAX epoch (1899-12-30); additional English day/month masks are supported. Measure values are memoized only within the same evaluation budget and filter/scope/row context. Default limits are 60 seconds and 5,000,000 steps, with existing server environment overrides retained.

CROSSFILTER is supported as a CALCULATE/CALCULATETABLE modifier for existing relationships: Both, None, and OneWay (OneWay is rejected for ambiguous many-to-many relationships). Overrides are scoped to the calculation and included in measure-cache identities. Many-to-many filter propagation uses EXISTS predicates rather than duplicated fact rows.

FORMAT supports scaling commas adjacent to numeric placeholders (for example `$0,,,,.00T`), quoted/escaped literals and localized separators. Arithmetic binds before text concatenation, and exponentiation before unary sign. Matrix SparklineData with one grouping column and a measure evaluates up to 2,000 points per cell under the current security/filter context.


DATATABLE supports typed constant rows, aliases, blank cells and constant DATE/TIME expressions, with explicit empty model lineage and shared evaluation budgets. See [Microsoft DATATABLE reference](https://learn.microsoft.com/en-us/dax/datatable-function-dax). Omitted optional scalar arguments retain their defaults, separately from explicit BLANK(). Boolean CALCULATE predicates may use NOT/AND/OR wrappers, including negated IN selections, with the existing one-model-table predicate restriction.

The parser permits up to 2,000,000 source characters for embedded HTML/SVG image assets while retaining a 100,000-character executable-token budget, 32,768 tokens and nesting depth 64. An unmatched terminal quote is reported explicitly rather than repaired silently.



GENERATE and GENERATEALL evaluate the second table in each first-table row context, preserve source-column lineage, reject duplicate column names and cap output at 100,000 rows. GENERATE omits outer rows with empty inner tables; GENERATEALL retains them with blank inner columns. ROW expressions retain their surrounding row context.

SUMMARIZE accepts table expressions that retain model-column lineage, including ALL, FILTER and table variables. Named extension expressions retain the selected source rows; ambiguous computed-column lineage remains an explicit limitation. Boolean CALCULATE filters evaluate distinct referenced-column tuples in DuckDB, avoiding repeated predicate evaluation over duplicate fact rows. Existing RLS and evaluation budgets remain enforced.

CONTAINS supports table expressions and column/value pairs with same-row matching, case-insensitive text, strict blank comparisons and related model-column lookup. Scalar search values are evaluated once outside the table iteration.


GROUPBY supports existing model or virtual grouping columns and named extension expressions, including iterator aggregates over CURRENTGROUP. Group matching is case-insensitive for text and keeps source lineage; CURRENTGROUP outside GROUPBY reports an error. Correlated nested iterators can reference unqualified columns from an outer virtual row. Numeric coercion accepts validated en-US thousands groups such as 1,234.50, including values produced by FORMAT; malformed grouping remains an error.

Large same-table value filters use request-local typed Arrow relations above 1,000 tuples instead of long OR chains. Limits are 100,000 tuples, 2,000,000 cells per filter, 64 relations and 4,000,000 registered cells per request. Existing evaluation time/step budgets and physical RLS still apply. Repeated rowsets reuse their relation. Simple visual measure/aggregate comparisons execute after grouping in SQL before preview truncation, with their filter-only projections removed from chart output.

TOPN and ordered CONCATENATEX batch simple same-table SUM/AVERAGE/MIN/MAX/COUNT measure sort keys when iterating complete model rows. The batch respects secured/filter-context rows, text equivalence, duplicate row context transition, and existing row/step limits. Partial or computed table rows and complex measures use the bounded general evaluator. This avoids one aggregate query per movie in HTML carousel measures.

Model-defined user functions are extracted from PBIX Function metadata and interpreted with the same bounded DAX AST. Untyped named parameters use evaluated value bindings, isolated local variables and the caller filter context; nested calls share budgets and have a 32-call depth cap. Typed/reference/lazy function signatures remain explicit unsupported cases. Functions are also repaired into already imported models when their native source is available.

The conservative SQL path also supports simple CALCULATE column-equals-literal filters and ALL/REMOVEFILTERS modifiers, scalar MIN/MAX pairs, blank-safe concatenation, and scalar VAR bindings. Modified contexts are evaluated against the physically secured model, preserving unrelated external and group filters. Table variables keep the prior table-expression lowering. More complex CALCULATE filters continue through Python.

SELECTCOLUMNS accepts direct column references without explicit aliases and retains the original column name. Mixed fixed-decimal/floating-point arithmetic promotes to floating point when required, including DIVIDE and numeric MOD/QUOTIENT; same-type fixed-decimal operations retain decimal values. Median (semantic aggregation ID 6) is supported in SQL and evaluator projections. The report expression enum is documented in Microsoft’s [Power BI expression reference](https://github.com/microsoft/skills-for-fabric/blob/main/skills/powerbi-report-cli/references/authoring/expressions.md).

Visual Top N filters try grouped SQL scoring in batches, retaining ties and secured rows, before falling back to the bounded interpreter for unsupported sort measures.

Matrix/table sparklines support same-table implicit SUM, AVERAGE, distinct/nonblank count, MIN, MAX and MEDIAN, grouped into a single ordered query with a 2,000-point cap. Bare Boolean columns in CALCULATE become IS TRUE predicates with ordinary replacement/KEEPFILTERS behavior; RLS remains physical. TOPN permits the documented two-argument form without a sort expression and returns at most N source-order rows. Row-independent RANKX vectors and sorted ranks reuse bounded request-local caches (eight vectors, at most two million source cells), avoiding quadratic rescoring. Expressions using outer row context or unsupported functions keep the general path.

VALUES, ALL/ALLSELECTED column domains use bounded SQL projections instead of materializing full fact tables. ALLNOBLANKROW accepts base tables/columns and retains physical blank rows; the current relational engine does not synthesize the Tabular unknown-member row. Iterator shadow contexts for ALLSELECTED remain unsupported.

MINX/MAXX over ALL(base table) and a direct same-table column use secured SQL extrema. This preserves removal of ordinary expanded-table filters while retaining physical RLS.

EXCEPT/INTERSECT retain the first operand’s names, lineage and duplicates. COUNTROWS/ISEMPTY of base tables count in secured SQL. SUMX/AVERAGEX/MINX/MAXX with a base-table source and validated numeric row arithmetic (including DIVIDE) can use SQL; unsupported row expressions retain the interpreter. Row column matching is case-insensitive.


## Dynamic format expressions and BLANK conformance — 2026-10-25

Dynamic FormatStringExpression values run in the same secured grouped context as measure values, under the existing time/step limits. The separate format operation returns a string matrix; numeric measure values stay numeric. SELECTEDMEASURE(), SELECTEDMEASURENAME(), SELECTEDMEASUREFORMATSTRING() are supported only while evaluating format expressions, not as a general calculation-group engine. Child filter contexts retain the selected-measure information. Unsupported expressions report a warning with a static-format fallback. Standard loose/strict BLANK comparisons apply to measure filters; removal of all-blank visual measure rows is a separate nonempty stage and can be disabled by show-items-with-no-data.
