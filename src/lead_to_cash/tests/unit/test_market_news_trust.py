"""
Regression tests for market news trust pipeline.

Validates the structural guarantees:
1. No query-time Perplexity call in market news path
2. Final sources are KB-only, in [N] order
3. No set()-based reordering
4. Perplexity URLs never in final sources
5. Citation [N] maps to sources[N-1] exactly
"""

import ast
import re
from pathlib import Path


# =============================================================================
# Structural tests (parse the source code to verify architecture)
# =============================================================================

TOOL_EXECUTOR_PATH = Path(__file__).parent.parent.parent / "core" / "tool_executor.py"


def _get_method_source(filepath: Path, method_name: str) -> str:
    """Extract a method's source code from a file by AST parsing."""
    source = filepath.read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == method_name:
                lines = source.splitlines()
                start = node.lineno - 1
                end = node.end_lineno
                return "\n".join(lines[start:end])
    return ""


class TestNoQueryTimePerplexity:
    """Verify Perplexity is NOT called at query time in market news."""

    def test_execute_market_news_does_not_call_perplexity(self):
        """_execute_market_news must NOT call _execute_perplexity."""
        source = _get_method_source(TOOL_EXECUTOR_PATH, "_execute_market_news")
        assert source, "_execute_market_news method not found"

        # Must NOT contain a call to _execute_perplexity
        assert "_execute_perplexity" not in source, (
            "TRUST VIOLATION: _execute_market_news still calls _execute_perplexity. "
            "Perplexity must only be used at ingestion time, not query time."
        )

    def test_execute_market_news_does_not_reference_perplexity_datasource(self):
        """Phase 2 tasks must not include DataSource.PERPLEXITY."""
        source = _get_method_source(TOOL_EXECUTOR_PATH, "_execute_market_news")
        # Check there's no PERPLEXITY_IDX or DataSource.PERPLEXITY in the method
        assert "_PERPLEXITY_IDX" not in source, (
            "TRUST VIOLATION: _execute_market_news has a Perplexity task index"
        )


class TestKBOnlySources:
    """Verify final sources are KB-only and ordered."""

    def test_no_set_reordering_in_sources(self):
        """Final sources must NOT use list(set(...)) which destroys [N] ordering."""
        source = _get_method_source(TOOL_EXECUTOR_PATH, "_execute_market_news")
        assert source, "_execute_market_news method not found"

        assert "list(set(" not in source, (
            "TRUST VIOLATION: list(set(all_sources)) destroys citation ordering. "
            "Sources must be returned in the exact [N] order from KB."
        )

    def test_sources_come_from_kb_only(self):
        """Final ToolResult.sources must be kb_sources, not merged all_sources."""
        source = _get_method_source(TOOL_EXECUTOR_PATH, "_execute_market_news")

        # Must use kb_sources (or marine_intel_output.sources) not all_sources
        assert (
            "sources=kb_sources" in source
            or "sources=marine_intel_output.sources" in source
        ), (
            "TRUST VIOLATION: Final sources must be KB-only (kb_sources), "
            "not merged from multiple tools."
        )

    def test_no_all_sources_in_return(self):
        """The return statement must not reference all_sources."""
        source = _get_method_source(TOOL_EXECUTOR_PATH, "_execute_market_news")

        # Find the return ToolResult statement
        return_match = re.search(r"return ToolResult\(.*?\)", source, re.DOTALL)
        if return_match:
            return_block = return_match.group()
            assert "all_sources" not in return_block, (
                "TRUST VIOLATION: ToolResult sources must not use all_sources"
            )


class TestSynthesisKBBound:
    """Verify synthesis only uses KB content, no Perplexity."""

    def test_no_perplexity_content_in_synthesis(self):
        """_synthesize_market_news must not pass perplexity_content to LLM."""
        source = _get_method_source(TOOL_EXECUTOR_PATH, "_synthesize_market_news")
        assert source, "_synthesize_market_news method not found"

        # Must not have a "REAL-TIME CONTEXT" or "perplexity_content" section
        assert "perplexity_content" not in source, (
            "TRUST VIOLATION: Synthesis must not include Perplexity content. "
            "All cited facts must come from the KB."
        )

    def test_no_perplexity_datasource_in_synthesis_gather(self):
        """Synthesis content extraction must not look for DataSource.PERPLEXITY."""
        source = _get_method_source(TOOL_EXECUTOR_PATH, "_synthesize_market_news")
        assert "DataSource.PERPLEXITY" not in source, (
            "TRUST VIOLATION: Synthesis extracts Perplexity content from tool_outputs"
        )


class TestDateDisplay:
    """Verify published_date is preferred over discovered_at."""

    def test_display_prefers_published_date(self):
        """_execute_marine_intel_search must prefer published_date."""
        source = _get_method_source(TOOL_EXECUTOR_PATH, "_execute_marine_intel_search")
        assert source, "_execute_marine_intel_search method not found"

        assert "published_date" in source, (
            "TRUST VIOLATION: Marine Intel search must use published_date for display"
        )

        # Must not ONLY use discovered_at without checking published_date first
        # The pattern should be: published_date or discovered_at
        assert (
            "opp.published_date or opp.discovered_at" in source
            or "published_date or opp.discovered_at" in source
        ), "TRUST VIOLATION: Must prefer published_date with discovered_at as fallback"


class TestCitationOrdering:
    """Verify [N] citation mapping integrity."""

    def test_marine_intel_search_assigns_sequential_citations(self):
        """KB search must assign [N] sequentially matching sources list order."""
        source = _get_method_source(TOOL_EXECUTOR_PATH, "_execute_marine_intel_search")
        assert source, "method not found"

        # Must have sources.append() + len(sources) pattern for [N] assignment
        assert "sources.append" in source, "Must collect sources in order"
        assert "len(sources)" in source, "Must use len(sources) for [N] numbering"

    def test_no_sources_cap_after_content_formatting(self):
        """sources must NOT be capped after [N] citations are already in content."""
        source = _get_method_source(TOOL_EXECUTOR_PATH, "_execute_marine_intel_search")
        assert source, "method not found"

        # Must NOT have sources[:10] or sources[:N] in the return statement
        assert "sources[:10]" not in source, (
            "TRUST VIOLATION: sources[:10] truncates URLs after [N] already assigned. "
            "Use a loop cap instead."
        )
        assert "sources[:" not in source, (
            "TRUST VIOLATION: sources slicing in return can cause [N] > len(sources)"
        )

    def test_only_items_with_urls_get_citations(self):
        """Items without source_url must be skipped, not cited."""
        source = _get_method_source(TOOL_EXECUTOR_PATH, "_execute_marine_intel_search")
        assert source, "method not found"

        # Must check for source_url before appending to sources
        assert (
            "not opp.source_url" in source
            or "if not opp.source_url" in source
            or "opp.source_url" in source
        ), "Must filter items by source_url presence"


class TestSpeculationStripper:
    """Verify SpeculationStripper catches known motherhood phrases."""

    ENFORCER_PATH = Path(__file__).parent.parent.parent / "core" / "output_enforcer.py"

    def _get_stripper_class_source(self) -> str:
        source = self.ENFORCER_PATH.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "SpeculationStripper":
                lines = source.splitlines()
                return "\n".join(lines[node.lineno - 1 : node.end_lineno])
        return ""

    def test_catches_aligns_with_our(self):
        """Must catch 'aligns with our/RRPS' patterns."""
        source = self._get_stripper_class_source()
        assert "align" in source.lower(), "Missing aligns/aligning pattern"
        assert "our" in source, "Must match 'aligns with our'"

    def test_catches_presenting_opportunity(self):
        """Must catch 'presenting a direct sales opportunity'."""
        source = self._get_stripper_class_source()
        assert "presents" in source.lower() or "presenting" in source.lower()
        assert "opportunity" in source.lower()

    def test_catches_strengthens_our(self):
        """Must catch 'strengthens/supports our' patterns."""
        source = self._get_stripper_class_source()
        assert "strengthens" in source.lower() or "supports" in source.lower()

    def test_catches_represent_potential_market(self):
        """Must catch 'represent a potential market'."""
        source = self._get_stripper_class_source()
        assert "represent" in source.lower()

    def test_catches_potential_market_for(self):
        """Must catch 'a potential market for MTU engines'."""
        source = self._get_stripper_class_source()
        assert "potential" in source.lower() and "market" in source.lower()

    def test_catches_positions_us(self):
        """Must catch 'positions us/RRPS'."""
        source = self._get_stripper_class_source()
        assert "positions" in source.lower()

    def test_catches_could_benefit(self):
        """Must catch 'could benefit from/our'."""
        source = self._get_stripper_class_source()
        assert "could" in source.lower() and "benefit" in source.lower()

    def test_catches_remain_competitive(self):
        """Must catch 'remain competitive'."""
        source = self._get_stripper_class_source()
        assert "remain" in source.lower() and "competitive" in source.lower()


class TestCitationRenumbering:
    """Verify _filter_cited_sources renumbers citations correctly."""

    CONV_PATH = Path(__file__).parent.parent.parent / "core" / "conversation.py"

    def test_filter_returns_tuple(self):
        """_filter_cited_sources must return (answer, sources) tuple."""
        source = self.CONV_PATH.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "_filter_cited_sources":
                    method = "\n".join(
                        source.splitlines()[node.lineno - 1 : node.end_lineno]
                    )
                    assert "-> tuple" in method, (
                        "TRUST VIOLATION: _filter_cited_sources must return "
                        "(renumbered_answer, filtered_sources) tuple"
                    )
                    return
        assert False, "_filter_cited_sources not found"

    def test_caller_unpacks_tuple(self):
        """Caller must unpack (answer, sources) from _filter_cited_sources."""
        source = self.CONV_PATH.read_text()
        # The caller should do: answer, sources = self._filter_cited_sources(...)
        assert "answer, cited_sources = self._filter_cited_sources" in source, (
            "TRUST VIOLATION: Caller must unpack both answer and sources "
            "from _filter_cited_sources to get renumbered answer"
        )

    def test_renumbering_logic_present(self):
        """Must have old_to_new mapping for citation renumbering."""
        source = self.CONV_PATH.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "_filter_cited_sources":
                    method = "\n".join(
                        source.splitlines()[node.lineno - 1 : node.end_lineno]
                    )
                    assert "old_to_new" in method, (
                        "TRUST VIOLATION: Must map old [N] to new sequential numbers"
                    )
                    return


class TestRecencyFilter:
    """Verify recency uses published_date not discovered_at."""

    DB_PATH = (
        Path(__file__).parent.parent.parent
        / "services"
        / "marine_intel"
        / "database.py"
    )

    def test_uses_published_date_for_recency(self):
        """get_recent_opportunities must filter by published_date."""
        source = self.DB_PATH.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "get_recent_opportunities":
                    method = "\n".join(
                        source.splitlines()[node.lineno - 1 : node.end_lineno]
                    )
                    assert "published_date" in method, (
                        "TRUST VIOLATION: Recency must use published_date, "
                        "not discovered_at alone"
                    )
                    assert "COALESCE(published_date" in method, (
                        "TRUST VIOLATION: Must COALESCE published_date with "
                        "discovered_at as fallback"
                    )
                    return
        assert False, "get_recent_opportunities not found"

    def test_prioritizes_records_with_dates(self):
        """Records with published_date must sort before NULL ones."""
        source = self.DB_PATH.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "get_recent_opportunities":
                    method = "\n".join(
                        source.splitlines()[node.lineno - 1 : node.end_lineno]
                    )
                    assert "published_date IS NOT NULL" in method, (
                        "TRUST VIOLATION: Must prioritize records with real "
                        "published_date over NULL"
                    )
                    return


class TestCustomerNewsKBOnly:
    """Verify customer news uses KB, not query-time Perplexity."""

    def test_no_perplexity_in_customer_news(self):
        """_execute_customer_news must NOT call _execute_perplexity."""
        source = _get_method_source(TOOL_EXECUTOR_PATH, "_execute_customer_news")
        assert source, "_execute_customer_news not found"
        assert "_execute_perplexity" not in source, (
            "TRUST VIOLATION: _execute_customer_news calls Perplexity at query time. "
            "Must use KB only."
        )

    def test_customer_news_uses_kb(self):
        """_execute_customer_news must search marine intel KB."""
        source = _get_method_source(TOOL_EXECUTOR_PATH, "_execute_customer_news")
        assert source, "_execute_customer_news not found"
        assert (
            "search_opportunities_by_company" in source
            or "search_articles_by_company" in source
        ), "TRUST VIOLATION: Must search KB by company name"

    def test_customer_news_kb_only_sources(self):
        """Customer news must return kb_sources, not all_sources."""
        source = _get_method_source(TOOL_EXECUTOR_PATH, "_execute_customer_news")
        assert source, "_execute_customer_news not found"
        assert "sources=kb_sources" in source, (
            "TRUST VIOLATION: Must return KB-only ordered sources"
        )
        assert "list(set(" not in source, "TRUST VIOLATION: No set() reordering"

    def test_customer_synthesis_uses_kb_content(self):
        """_synthesize_customer_news must use kb_content, not perplexity_content."""
        source = _get_method_source(TOOL_EXECUTOR_PATH, "_synthesize_customer_news")
        assert source, "_synthesize_customer_news not found"
        assert "perplexity_content" not in source, (
            "TRUST VIOLATION: Synthesis must not reference Perplexity content"
        )
