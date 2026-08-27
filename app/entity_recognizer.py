"""
Entity Recognizer Module

This module provides functionality to recognize and extract entities from natural language
questions, including tables, columns, and values. It uses fuzzy matching to handle typos
and variations in naming conventions.

Example:
    >>> schema = {
    ...     "employees": ["id", "name", "department", "salary"],
    ...     "departments": ["id", "dept_name", "manager_id"]
    ... }
    >>> recognizer = EntityRecognizer(schema)
    >>> entities = recognizer.recognize_entities("Show me all employes in the sales department")
    >>> for entity in entities:
    ...     print(f"{entity.entity_type}: {entity.entity_name} (confidence: {entity.confidence})")
"""

from typing import Dict, List, Optional, Set, Tuple
import re
from difflib import SequenceMatcher
from pydantic import BaseModel, Field


class RecognizedEntity(BaseModel):
    """
    Represents a recognized entity extracted from a question.

    Attributes:
        entity_type: The type of entity - "table", "column", or "value"
        entity_name: The recognized name of the entity
        table_name: For column entities, the table they belong to (optional)
        confidence: Confidence score from 0.0 to 1.0
        original_text: The text from the question that led to this recognition
    """
    entity_type: str = Field(..., description="Type: 'table', 'column', or 'value'")
    entity_name: str = Field(..., description="The recognized entity name")
    table_name: Optional[str] = Field(None, description="Table name for column entities")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    original_text: str = Field(..., description="Original text from the question")


class EntityRecognizer:
    """
    Recognizes and extracts entities from natural language questions.

    This class uses fuzzy matching and contextual analysis to identify tables, columns,
    and values in user questions. It handles case-insensitivity, plural forms, typos,
    and common variations in naming conventions.

    Attributes:
        schema_context: Dictionary mapping table names to lists of column names
        _stop_words: Common words to exclude from value extraction
    """

    def __init__(self, schema_context: Dict[str, List[str]]):
        """
        Initialize the EntityRecognizer with schema information.

        Args:
            schema_context: Dictionary where keys are table names and values are lists
                          of column names. Example:
                          {
                              "employees": ["id", "name", "department"],
                              "departments": ["id", "name"]
                          }
        """
        self.schema_context = schema_context
        # Normalize schema to lowercase for matching
        self._normalized_schema = {
            table.lower(): [col.lower() for col in cols]
            for table, cols in schema_context.items()
        }
        self._stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "from", "by", "with", "is", "are", "was", "were", "be", "been",
            "all", "each", "every", "both", "some", "any", "who", "which", "where",
            "what", "when", "why", "how", "show", "get", "find", "list", "display",
            "retrieve", "select", "query", "fetch", "me", "us", "you", "him", "her"
        }

    def recognize_entities(self, question: str) -> List[RecognizedEntity]:
        """
        Main method to recognize all entities in a question.

        This method orchestrates the recognition of tables, columns, and values
        from the input question. Entities are returned in order of confidence.

        Args:
            question: The natural language question to analyze

        Returns:
            List of RecognizedEntity objects sorted by confidence (highest first)

        Example:
            >>> recognizer = EntityRecognizer({"users": ["id", "name"]})
            >>> entities = recognizer.recognize_entities("What is the name of user 123?")
            >>> len(entities) > 0
            True
        """
        entities = []

        # Find table mentions
        entities.extend(self._find_table_mentions(question))

        # Find column mentions
        entities.extend(self._find_column_mentions(question))

        # Find potential values
        entities.extend(self._find_values(question))

        # Sort by confidence (highest first)
        entities.sort(key=lambda e: e.confidence, reverse=True)

        return entities

    def _find_table_mentions(self, question: str) -> List[RecognizedEntity]:
        """
        Find and recognize table names in the question.

        This method searches for exact matches, plural forms, and fuzzy matches
        of table names in the schema.

        Args:
            question: The question to search for table mentions

        Returns:
            List of RecognizedEntity objects with entity_type='table'
        """
        entities = []
        question_lower = question.lower()
        processed_matches = set()

        # Get list of candidate table names
        table_candidates = list(self.schema_context.keys())

        # Look for exact matches first
        for table in table_candidates:
            if table.lower() in question_lower:
                match_pos = question_lower.find(table.lower())
                original_text = question[match_pos:match_pos + len(table)]

                if original_text not in processed_matches:
                    entities.append(RecognizedEntity(
                        entity_type="table",
                        entity_name=table,
                        confidence=1.0,
                        original_text=original_text
                    ))
                    processed_matches.add(original_text)

        # Look for plural forms (e.g., "employees" -> "employee")
        for table in table_candidates:
            plural_form = table + "s"
            if plural_form in question_lower:
                match_pos = question_lower.find(plural_form)
                original_text = question[match_pos:match_pos + len(plural_form)]

                if original_text not in processed_matches:
                    entities.append(RecognizedEntity(
                        entity_type="table",
                        entity_name=table,
                        confidence=0.95,
                        original_text=original_text
                    ))
                    processed_matches.add(original_text)

        # Look for fuzzy matches (e.g., "employe" -> "employee")
        words = re.findall(r'\b\w+\b', question_lower)
        for word in words:
            if word not in self._stop_words and word not in processed_matches:
                match, confidence = self._fuzzy_match(word, table_candidates, threshold=0.8)
                if match:
                    match_pos = question_lower.find(word)
                    original_text = question[match_pos:match_pos + len(word)]

                    if original_text not in processed_matches:
                        entities.append(RecognizedEntity(
                            entity_type="table",
                            entity_name=match,
                            confidence=confidence,
                            original_text=original_text
                        ))
                        processed_matches.add(original_text)

        return entities

    def _find_column_mentions(self, question: str) -> List[RecognizedEntity]:
        """
        Find and recognize column names in the question.

        This method identifies column references by matching against columns
        in the schema. It returns columns with their associated table names
        when context allows for it.

        Args:
            question: The question to search for column mentions

        Returns:
            List of RecognizedEntity objects with entity_type='column'
        """
        entities = []
        question_lower = question.lower()
        processed_matches = set()

        # First, identify which tables are mentioned (for context)
        mentioned_tables = set()
        table_entities = self._find_table_mentions(question)
        for entity in table_entities:
            mentioned_tables.add(entity.entity_name.lower())

        # Look for column matches across all tables
        all_columns = {}
        for table, cols in self._normalized_schema.items():
            for col in cols:
                if col not in all_columns:
                    all_columns[col] = []
                all_columns[col].append(table)

        # Look for exact column matches
        for col_lower, tables in all_columns.items():
            if col_lower in question_lower:
                match_pos = question_lower.find(col_lower)
                # Find original text with proper case
                original_text = question[match_pos:match_pos + len(col_lower)]

                if original_text not in processed_matches:
                    # Determine table context
                    table_context = None
                    if mentioned_tables:
                        # Use first mentioned table that has this column
                        for table in mentioned_tables:
                            if col_lower in self._normalized_schema.get(table, []):
                                table_context = table
                                break

                    if table_context is None and tables:
                        table_context = tables[0]

                    # Find original column name with proper casing
                    original_col_name = self._get_original_name(col_lower, self.schema_context)

                    entities.append(RecognizedEntity(
                        entity_type="column",
                        entity_name=original_col_name,
                        table_name=table_context,
                        confidence=1.0,
                        original_text=original_text
                    ))
                    processed_matches.add(original_text)

        # Look for fuzzy matches on columns
        words = re.findall(r'\b\w+\b', question_lower)
        for word in words:
            if word not in self._stop_words and word not in processed_matches:
                # Try to match against all columns
                all_col_names = list(all_columns.keys())
                match, confidence = self._fuzzy_match(word, all_col_names, threshold=0.8)
                if match and match not in [e.entity_name.lower() for e in entities]:
                    match_pos = question_lower.find(word)
                    original_text = question[match_pos:match_pos + len(word)]

                    if original_text not in processed_matches:
                        table_context = None
                        if mentioned_tables:
                            for table in mentioned_tables:
                                if match in self._normalized_schema.get(table, []):
                                    table_context = table
                                    break

                        if table_context is None and all_columns[match]:
                            table_context = all_columns[match][0]

                        original_col_name = self._get_original_name(match, self.schema_context)

                        entities.append(RecognizedEntity(
                            entity_type="column",
                            entity_name=original_col_name,
                            table_name=table_context,
                            confidence=confidence * 0.9,  # Slightly lower confidence for fuzzy matches
                            original_text=original_text
                        ))
                        processed_matches.add(original_text)

        return entities

    def _find_values(self, question: str) -> List[RecognizedEntity]:
        """
        Extract potential values from the question.

        This method identifies strings that could be data values being queried,
        including quoted strings, numbers, dates, and named entities. Stop words
        and schema references are excluded.

        Args:
            question: The question to extract values from

        Returns:
            List of RecognizedEntity objects with entity_type='value'
        """
        entities = []
        processed_values = set()

        # Extract quoted strings
        quoted_pattern = r"['\"]([^'\"]+)['\"]"
        for match in re.finditer(quoted_pattern, question):
            value = match.group(1)
            if value not in processed_values:
                entities.append(RecognizedEntity(
                    entity_type="value",
                    entity_name=value,
                    confidence=0.95,
                    original_text=match.group(0)
                ))
                processed_values.add(value)

        # Extract numbers (integers and decimals)
        number_pattern = r'\b\d+(?:\.\d+)?\b'
        for match in re.finditer(number_pattern, question):
            value = match.group(0)
            if value not in processed_values:
                entities.append(RecognizedEntity(
                    entity_type="value",
                    entity_name=value,
                    confidence=0.9,
                    original_text=value
                ))
                processed_values.add(value)

        # Extract dates (simple patterns: YYYY-MM-DD, MM/DD/YYYY)
        date_pattern = r'\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\b'
        for match in re.finditer(date_pattern, question):
            value = match.group(0)
            if value not in processed_values:
                entities.append(RecognizedEntity(
                    entity_type="value",
                    entity_name=value,
                    confidence=0.92,
                    original_text=value
                ))
                processed_values.add(value)

        # Extract capitalized words that are not schema entities (likely proper nouns)
        # These are candidates for being values
        words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', question)

        # Get all schema entity names (lowercase) to exclude
        schema_entities = set()
        for table in self.schema_context.keys():
            schema_entities.add(table.lower())
        for cols in self.schema_context.values():
            for col in cols:
                schema_entities.add(col.lower())

        for word in words:
            if word.lower() not in schema_entities and word not in processed_values:
                # Look for the word in the original question to get exact casing
                if word in question:
                    entities.append(RecognizedEntity(
                        entity_type="value",
                        entity_name=word,
                        confidence=0.7,
                        original_text=word
                    ))
                    processed_values.add(word)

        return entities

    def _fuzzy_match(
        self,
        text: str,
        candidates: List[str],
        threshold: float = 0.8
    ) -> Tuple[Optional[str], float]:
        """
        Perform fuzzy matching to handle typos and variations.

        Uses sequence matching to find the best candidate match above the
        specified confidence threshold.

        Args:
            text: The text to match
            candidates: List of candidate strings to match against
            threshold: Minimum confidence score (0.0-1.0) for a match

        Returns:
            Tuple of (matched_candidate, confidence_score) or (None, 0.0)
            if no match exceeds the threshold

        Example:
            >>> recognizer = EntityRecognizer({})
            >>> match, conf = recognizer._fuzzy_match("employe", ["employee"], threshold=0.8)
            >>> match
            'employee'
            >>> conf > 0.8
            True
        """
        best_match = None
        best_ratio = 0.0

        text_lower = text.lower()

        for candidate in candidates:
            candidate_lower = candidate.lower()
            ratio = SequenceMatcher(None, text_lower, candidate_lower).ratio()

            if ratio > best_ratio and ratio >= threshold:
                best_ratio = ratio
                best_match = candidate

        return best_match, best_ratio

    def _get_original_name(self, normalized_name: str, schema: Dict[str, List[str]]) -> str:
        """
        Get the original casing of a schema entity from its normalized form.

        Args:
            normalized_name: The lowercase version of the entity name
            schema: The original schema with proper casing

        Returns:
            The original entity name with proper casing, or the normalized name
            if not found
        """
        # Check tables
        for table in schema.keys():
            if table.lower() == normalized_name:
                return table

        # Check columns
        for cols in schema.values():
            for col in cols:
                if col.lower() == normalized_name:
                    return col

        return normalized_name
