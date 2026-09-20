"""
Phase 4: SQL Generation Engine

Converts a validated/clarified StructuredIntent (Phase 2) into a parameterized
PostgreSQL query, using the Phase 3 AmbiguityDetector as a gatekeeper so that
unsafe or unclear intents never silently produce the wrong (or a destructive)
query.

Design goals
------------
1. Never emit a DELETE/UPDATE without a WHERE clause, no matter what the
   ambiguity settings say (defense in depth on top of Phase 3).
2. Auto-resolve ambiguities the detector is already confident about
   (``suggested_resolution`` is present) instead of bothering the user.
3. Refuse to guess on anything the detector flags as CRITICAL, or as
   HIGH/MEDIUM with no confident suggestion -- return clarification
   questions instead of a query.
4. Always build parameterized SQL (``%s`` placeholders + a params list),
   never string-interpolated values, to keep the door closed on SQL
   injection.

Typical usage
-------------
    >>> generator = SQLGenerator(schema)
    >>> result = generator.generate(intent)
    >>> if result.status == GenerationStatus.SUCCESS:
    ...     cursor.execute(result.sql, result.params)
    >>> elif result.status in (GenerationStatus.NEEDS_CLARIFICATION, GenerationStatus.BLOCKED):
    ...     for q in result.clarification_questions:
    ...         print(q)
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from app.ambiguity_detector import (
    AmbiguityDetectionResult,
    AmbiguityDetector,
    AmbiguityType,
    SeverityLevel,
    resolve_ambiguity,
)
from app.models import (
    AggregationType,
    Condition,
    ConditionOperator,
    Join,
    OrderBy,
    QueryType,
    StructuredIntent,
)
from app.schema import DatabaseSchema


class SQLGenerationError(Exception):
    """Raised for hard generation failures (unknown table/column, bad shape)."""


class GenerationStatus(str, Enum):
    """Outcome of a SQL generation attempt."""
    SUCCESS = "success"                        # Clean generation, nothing to flag
    SUCCESS_WITH_WARNINGS = "success_with_warnings"  # Generated, but ambiguities were auto-resolved
    NEEDS_CLARIFICATION = "needs_clarification"  # Non-critical ambiguity with no confident resolution
    BLOCKED = "blocked"                         # Critical ambiguity (e.g. unfiltered DELETE) - refused
    ERROR = "error"                             # Intent could not be turned into SQL at all


class SQLGenerationResult(BaseModel):
    """Result of a SQL generation attempt."""
    status: GenerationStatus = Field(description="Outcome of generation")
    sql: Optional[str] = Field(default=None, description="Parameterized SQL, if generated")
    params: List[Any] = Field(default_factory=list, description="Positional params for the %s placeholders")
    warnings: List[str] = Field(default_factory=list, description="Auto-resolutions applied during generation")
    clarification_questions: List[str] = Field(
        default_factory=list,
        description="Questions the user must answer before SQL can be produced"
    )
    error_message: Optional[str] = Field(default=None, description="Populated when status == ERROR")
    ambiguity_result: Optional[AmbiguityDetectionResult] = Field(
        default=None, description="Full ambiguity detection result, for callers that want detail"
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "sql": self.sql,
            "params": self.params,
            "warnings": self.warnings,
            "clarification_questions": self.clarification_questions,
            "error_message": self.error_message,
            "has_ambiguities": bool(self.ambiguity_result and self.ambiguity_result.has_ambiguities),
        }


class SQLGenerator:
    """
    Generates SQL from a StructuredIntent, using ambiguity detection as a
    gatekeeper before ever touching the query builder.
    """

    def __init__(
        self,
        schema: DatabaseSchema,
        detector: Optional[AmbiguityDetector] = None,
        strict: bool = True,
        auto_resolve: bool = True,
    ):
        """
        Args:
            schema: Database schema, used both for validation and passed to
                the AmbiguityDetector.
            detector: Optional pre-built AmbiguityDetector. One is created
                from `schema` if omitted.
            strict: If True (default), any non-critical ambiguity that the
                detector could not confidently auto-resolve blocks
                generation (NEEDS_CLARIFICATION). If False, generation
                proceeds using the intent as given, and unresolved
                ambiguities are only reported as warnings.
            auto_resolve: If True (default), ambiguities that come with a
                `suggested_resolution` are applied automatically via
                `resolve_ambiguity` rather than surfaced to the user.
        """
        self.schema = schema
        self.detector = detector or AmbiguityDetector(schema)
        self.strict = strict
        self.auto_resolve = auto_resolve

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def generate(
        self,
        intent: StructuredIntent,
        allow_full_table_write: bool = False,
    ) -> SQLGenerationResult:
        """
        Run the full pipeline: validate -> detect ambiguities -> resolve
        what can be resolved -> generate SQL (or refuse to).

        Args:
            intent: The structured intent to convert.
            allow_full_table_write: Escape hatch that permits a WHERE-less
                UPDATE/DELETE to actually be generated. Even when True, the
                CRITICAL ambiguity for that case must still not be present
                (i.e. it doesn't bypass the ambiguity gate, only the final
                hardcoded safety check).

        Returns:
            SQLGenerationResult describing what happened.
        """
        # 1. Ambiguity detection (also the source of truth for "is this
        #    table name close to something real?").
        ambiguity_result = self.detector.detect_ambiguities(intent)

        # 2. Hard structural validation: a table that doesn't exist AND that
        #    the detector didn't even flag as a fuzzy match to something
        #    real isn't an "ambiguity" to clarify -- it's just wrong.
        try:
            self._validate_intent_shape(intent, ambiguity_result)
        except SQLGenerationError as exc:
            return SQLGenerationResult(
                status=GenerationStatus.ERROR, error_message=str(exc), ambiguity_result=ambiguity_result
            )

        if not ambiguity_result.can_proceed:
            critical = [a for a in ambiguity_result.ambiguities if a.severity == SeverityLevel.CRITICAL]
            return SQLGenerationResult(
                status=GenerationStatus.BLOCKED,
                clarification_questions=[a.clarification_question for a in critical],
                ambiguity_result=ambiguity_result,
            )

        # 3. Auto-resolve what we're confident about; collect the rest.
        working_intent = intent
        warnings: List[str] = []
        unresolved = []

        for amb in ambiguity_result.ambiguities:
            if self.auto_resolve and amb.suggested_resolution:
                try:
                    working_intent = resolve_ambiguity(amb, amb.suggested_resolution, working_intent)
                    warnings.append(
                        f"Auto-resolved ({amb.severity.value}): {amb.description} "
                        f"-> {amb.suggested_resolution}"
                    )
                except Exception:
                    # If applying the suggestion fails for any reason, fall
                    # back to treating it as unresolved rather than crashing.
                    unresolved.append(amb)
            else:
                unresolved.append(amb)

        if unresolved and self.strict:
            return SQLGenerationResult(
                status=GenerationStatus.NEEDS_CLARIFICATION,
                warnings=warnings,
                clarification_questions=[a.clarification_question for a in unresolved],
                ambiguity_result=ambiguity_result,
            )

        # Anything left unresolved in non-strict mode just becomes a warning.
        for amb in unresolved:
            warnings.append(f"Unresolved ({amb.severity.value}, proceeding anyway): {amb.description}")

        # 4. Build the actual SQL.
        try:
            sql, params = self._build_sql(working_intent, allow_full_table_write=allow_full_table_write)
        except SQLGenerationError as exc:
            return SQLGenerationResult(
                status=GenerationStatus.ERROR,
                error_message=str(exc),
                ambiguity_result=ambiguity_result,
            )

        status = GenerationStatus.SUCCESS_WITH_WARNINGS if warnings else GenerationStatus.SUCCESS
        return SQLGenerationResult(
            status=status,
            sql=sql,
            params=params,
            warnings=warnings,
            ambiguity_result=ambiguity_result,
        )

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

    def _validate_intent_shape(self, intent: StructuredIntent, ambiguity_result: AmbiguityDetectionResult) -> None:
        """
        Catch structural problems the ambiguity detector won't flag: a table
        name with *no* plausible match at all. (A table with a fuzzy match
        is already covered by a MULTIPLE_TABLE_MATCHES ambiguity and is
        handled downstream, not here.)
        """
        flagged_tables = {
            amb.context.get("original_table")
            for amb in ambiguity_result.ambiguities
            if amb.ambiguity_type == AmbiguityType.MULTIPLE_TABLE_MATCHES
        }

        for table in intent.tables:
            if table not in self.schema.tables and table not in flagged_tables:
                raise SQLGenerationError(
                    f"Table '{table}' does not exist in the schema and no similar table was found."
                )

    # ------------------------------------------------------------------ #
    # SQL construction
    # ------------------------------------------------------------------ #

    def _build_sql(self, intent: StructuredIntent, allow_full_table_write: bool) -> Tuple[str, List[Any]]:
        if intent.query_type == QueryType.SELECT:
            return self._build_select(intent)
        if intent.query_type in (QueryType.COUNT, QueryType.AGGREGATE):
            return self._build_select(intent)  # COUNT/AGGREGATE are SELECTs with aggregations
        if intent.query_type == QueryType.INSERT:
            return self._build_insert(intent)
        if intent.query_type == QueryType.UPDATE:
            return self._build_update(intent, allow_full_table_write)
        if intent.query_type == QueryType.DELETE:
            return self._build_delete(intent, allow_full_table_write)

        raise SQLGenerationError(f"Unsupported query type: {intent.query_type}")

    def _build_select(self, intent: StructuredIntent) -> Tuple[str, List[Any]]:
        params: List[Any] = []

        base_table = self._base_table(intent)

        select_parts: List[str] = []
        for col in intent.columns:
            select_parts.append(self._qualify(col))
        for agg in intent.aggregations:
            select_parts.append(self._render_aggregation(agg))

        if not select_parts:
            select_parts = ["*"]

        distinct = "DISTINCT " if intent.distinct else ""
        sql = f"SELECT {distinct}{', '.join(select_parts)}\nFROM {self._quote_ident(base_table)}"

        for join in intent.joins:
            join_sql, join_params = self._render_join(join)
            sql += f"\n{join_sql}"
            params.extend(join_params)

        if intent.conditions:
            where_sql, where_params = self._build_condition_clause(intent.conditions)
            sql += f"\nWHERE {where_sql}"
            params.extend(where_params)

        if intent.group_by:
            sql += f"\nGROUP BY {', '.join(self._qualify(c) for c in intent.group_by)}"

        if intent.having_conditions:
            having_sql, having_params = self._build_condition_clause(intent.having_conditions)
            sql += f"\nHAVING {having_sql}"
            params.extend(having_params)

        if intent.order_by:
            order_parts = [f"{self._qualify(o.column)} {o.direction.value}" for o in intent.order_by]
            sql += f"\nORDER BY {', '.join(order_parts)}"

        if intent.limit is not None:
            sql += f"\nLIMIT {int(intent.limit)}"

        if intent.offset is not None:
            sql += f"\nOFFSET {int(intent.offset)}"

        return sql, params

    def _build_insert(self, intent: StructuredIntent) -> Tuple[str, List[Any]]:
        if not intent.insert_values:
            raise SQLGenerationError("INSERT query has no insert_values.")

        table = intent.tables[0]
        columns = list(intent.insert_values.keys())
        values = list(intent.insert_values.values())

        col_sql = ", ".join(self._quote_ident(c) for c in columns)
        placeholder_sql = ", ".join(["%s"] * len(values))

        sql = f"INSERT INTO {self._quote_ident(table)} ({col_sql})\nVALUES ({placeholder_sql})"
        return sql, values

    def _build_update(self, intent: StructuredIntent, allow_full_table_write: bool) -> Tuple[str, List[Any]]:
        if not intent.update_values:
            raise SQLGenerationError("UPDATE query has no update_values.")

        if not intent.conditions and not allow_full_table_write:
            raise SQLGenerationError(
                "Refusing to generate an UPDATE with no WHERE clause "
                "(pass allow_full_table_write=True if this is really intended)."
            )

        table = intent.tables[0]
        params: List[Any] = []

        set_parts = []
        for col, val in intent.update_values.items():
            set_parts.append(f"{self._quote_ident(col)} = %s")
            params.append(val)

        sql = f"UPDATE {self._quote_ident(table)}\nSET {', '.join(set_parts)}"

        if intent.conditions:
            where_sql, where_params = self._build_condition_clause(intent.conditions)
            sql += f"\nWHERE {where_sql}"
            params.extend(where_params)

        return sql, params

    def _build_delete(self, intent: StructuredIntent, allow_full_table_write: bool) -> Tuple[str, List[Any]]:
        if not intent.conditions and not allow_full_table_write:
            raise SQLGenerationError(
                "Refusing to generate a DELETE with no WHERE clause "
                "(pass allow_full_table_write=True if this is really intended)."
            )

        table = intent.tables[0]
        sql = f"DELETE FROM {self._quote_ident(table)}"
        params: List[Any] = []

        if intent.conditions:
            where_sql, where_params = self._build_condition_clause(intent.conditions)
            sql += f"\nWHERE {where_sql}"
            params.extend(where_params)

        return sql, params

    # ------------------------------------------------------------------ #
    # Clause / fragment helpers
    # ------------------------------------------------------------------ #

    def _base_table(self, intent: StructuredIntent) -> str:
        if intent.joins:
            return intent.joins[0].left_table
        if intent.tables:
            return intent.tables[0]
        raise SQLGenerationError("No table specified for query.")

    def _render_join(self, join: Join) -> Tuple[str, List[Any]]:
        alias_sql = f" AS {self._quote_ident(join.alias)}" if join.alias else ""
        right_ref = self._quote_ident(join.alias) if join.alias else self._quote_ident(join.right_table)
        sql = (
            f"{join.join_type.value} {self._quote_ident(join.right_table)}{alias_sql} "
            f"ON {self._qualify(f'{join.left_table}.{join.left_column}')} = "
            f"{right_ref}.{self._quote_ident(join.right_column)}"
        )
        return sql, []

    def _render_aggregation(self, agg) -> str:
        if agg.aggregation_type == AggregationType.COUNT and agg.column is None:
            expr = "COUNT(*)"
        else:
            distinct = "DISTINCT " if agg.distinct else ""
            col = self._qualify(agg.column) if agg.column else "*"
            expr = f"{agg.aggregation_type.value}({distinct}{col})"
        return f"{expr} AS {self._quote_ident(agg.alias)}" if agg.alias else expr

    def _build_condition_clause(self, conditions: List[Condition]) -> Tuple[str, List[Any]]:
        fragments: List[str] = []
        params: List[Any] = []

        for i, cond in enumerate(conditions):
            frag, cond_params = self._render_condition(cond)
            fragments.append(frag)
            params.extend(cond_params)
            if i < len(conditions) - 1:
                fragments.append(cond.logic or "AND")

        return " ".join(fragments), params

    def _render_condition(self, cond: Condition) -> Tuple[str, List[Any]]:
        col = self._qualify(f"{cond.table}.{cond.column}" if cond.table else cond.column)
        op = cond.operator

        if op in (ConditionOperator.IS_NULL, ConditionOperator.IS_NOT_NULL):
            return f"{col} {op.value}", []

        if op in (ConditionOperator.IN, ConditionOperator.NOT_IN):
            values = cond.value if isinstance(cond.value, list) else [cond.value]
            placeholders = ", ".join(["%s"] * len(values))
            return f"{col} {op.value} ({placeholders})", list(values)

        if op == ConditionOperator.BETWEEN:
            values = cond.value
            return f"{col} BETWEEN %s AND %s", [values[0], values[1]]

        return f"{col} {op.value} %s", [cond.value]

    # ------------------------------------------------------------------ #
    # Identifier quoting
    # ------------------------------------------------------------------ #

    def _quote_ident(self, name: str) -> str:
        """Quote a single SQL identifier (no dots)."""
        return f'"{name}"'

    def _qualify(self, name: str) -> str:
        """Quote a possibly-qualified identifier like 'table.column'."""
        if "." in name:
            table, col = name.split(".", 1)
            return f'{self._quote_ident(table)}.{self._quote_ident(col)}'
        return self._quote_ident(name)
