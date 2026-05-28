"""
Unit Tests for Agent Signatures

Tests the signature-based capability declaration system for A2A matching.
Tests the 3-domain intelligence architecture:
1. Industry Intelligence
2. Competitor Intelligence
3. Product Intelligence
"""

from lead_to_cash.agents.signatures import (  # Intelligence Domains; Order Processing Domain; Supporting Agents; Registry; Backward compatibility
    AgentSignature,
    BillingCollectionsSignature,
    CompetitorIntelSignature,
    CustomerMatcherSignature,
    DataManagementSignature,
    FieldDescriptor,
    FinancialOpsSignature,
    IndustryIntelSignature,
    InputField,
    KnowledgeBaseSignature,
    KYPSignature,
    MarineIntelSignature,
    OpportunitySignature,
    OutputField,
    ProductIntelSignature,
    SignatureRegistry,
    WebSearchSignature,
)


class TestFieldDescriptor:
    """Tests for FieldDescriptor."""

    def test_create_field_descriptor(self):
        """Test creating a field descriptor."""
        fd = FieldDescriptor(
            description="Test field",
            examples=["example1", "example2"],
            required=True,
            default=None,
            field_type="input",
        )
        assert fd.description == "Test field"
        assert fd.examples == ["example1", "example2"]
        assert fd.required is True
        assert fd.field_type == "input"

    def test_to_dict(self):
        """Test serialization."""
        fd = FieldDescriptor(
            description="Test",
            examples=["ex1"],
            required=False,
            default="default_value",
        )
        d = fd.to_dict()
        assert d["description"] == "Test"
        assert d["examples"] == ["ex1"]
        assert d["required"] is False
        assert d["default"] == "default_value"


class TestInputOutputFields:
    """Tests for InputField and OutputField helpers."""

    def test_input_field(self):
        """Test InputField helper."""
        fd = InputField(
            description="User query",
            examples=["query1", "query2"],
            required=True,
            default=None,
        )
        assert fd.field_type == "input"
        assert fd.required is True

    def test_input_field_optional(self):
        """Test optional InputField."""
        fd = InputField(
            description="Optional param",
            required=False,
            default="default",
        )
        assert fd.required is False
        assert fd.default == "default"

    def test_output_field(self):
        """Test OutputField helper."""
        fd = OutputField(
            description="Result output",
            examples=["result1"],
            default=[],
        )
        assert fd.field_type == "output"
        assert fd.required is False  # Outputs are never required
        assert fd.default == []


class TestAgentSignatureBase:
    """Tests for AgentSignature base class."""

    def test_custom_signature(self):
        """Test creating a custom signature."""

        class TestSignature(AgentSignature):
            query = InputField(description="Test query", examples=["test"])
            result = OutputField(description="Test result")
            tool_calls = OutputField(description="Tools to call", default=[])

        # Check fields were collected
        assert "query" in TestSignature._input_fields
        assert "result" in TestSignature._output_fields
        assert "tool_calls" in TestSignature._output_fields

    def test_get_capabilities(self):
        """Test capability extraction."""

        class TestSignature(AgentSignature):
            query = InputField(
                description="Market analysis query for marine industry",
                examples=["ferry contracts", "offshore vessels"],
            )
            result = OutputField(description="Analysis results with opportunities")

        capabilities = TestSignature.get_capabilities()

        # Should extract meaningful words
        assert "market" in capabilities
        assert "analysis" in capabilities
        assert "marine" in capabilities
        assert "ferry" in capabilities
        assert "offshore" in capabilities

    def test_to_a2a_card(self):
        """Test A2A card generation."""

        class TestSignature(AgentSignature):
            query = InputField(description="Test query")
            result = OutputField(description="Test result")
            tool_calls = OutputField(description="Tools", default=[])

        card = TestSignature.to_a2a_card()

        assert card["name"] == "TestSignature"
        assert "capabilities" in card
        assert "input_schema" in card
        assert "output_schema" in card
        assert card["has_convergence"] is True  # Has tool_calls field

    def test_validate_inputs_valid(self):
        """Test input validation with valid inputs."""

        class TestSignature(AgentSignature):
            query = InputField(description="Query", required=True)
            optional = InputField(description="Optional", required=False, default="x")

        errors = TestSignature.validate_inputs({"query": "test"})
        assert len(errors) == 0

    def test_validate_inputs_missing_required(self):
        """Test input validation with missing required field."""

        class TestSignature(AgentSignature):
            query = InputField(description="Query", required=True)

        errors = TestSignature.validate_inputs({})
        assert len(errors) == 1
        assert "query" in errors[0]


# =============================================================================
# Intelligence Domain 1: Industry Intelligence
# =============================================================================


class TestIndustryIntelSignature:
    """Tests for IndustryIntelSignature."""

    def test_input_fields(self):
        """Test IndustryIntelSignature has expected input fields."""
        fields = IndustryIntelSignature.get_input_fields()

        assert "query" in fields
        assert "regions" in fields
        assert "sectors" in fields
        assert "time_range" in fields

    def test_output_fields(self):
        """Test IndustryIntelSignature has expected output fields."""
        fields = IndustryIntelSignature.get_output_fields()

        assert "opportunities" in fields
        assert "market_trends" in fields
        assert "fleet_data" in fields
        assert "news_articles" in fields
        assert "tool_calls" in fields

    def test_capabilities(self):
        """Test capability extraction includes industry-related terms."""
        capabilities = IndustryIntelSignature.get_capabilities()

        # Should include industry intelligence keywords
        assert any("market" in c for c in capabilities)
        assert any("industry" in c for c in capabilities)

    def test_a2a_card_has_convergence(self):
        """Test A2A card indicates convergence support."""
        card = IndustryIntelSignature.to_a2a_card()
        assert card["has_convergence"] is True

    def test_validate_minimal_inputs(self):
        """Test validation with minimal valid inputs."""
        errors = IndustryIntelSignature.validate_inputs({"query": "ferry contracts"})
        assert len(errors) == 0


class TestMarineIntelBackwardCompatibility:
    """Tests for MarineIntelSignature backward compatibility."""

    def test_marine_intel_is_alias(self):
        """Test that MarineIntelSignature is alias for IndustryIntelSignature."""
        assert MarineIntelSignature is IndustryIntelSignature

    def test_marine_intel_in_registry(self):
        """Test MarineIntelSignature is registered under alias name."""
        assert "MarineIntelSignature" in SignatureRegistry.all()

    def test_marine_intel_resolves_to_canonical(self):
        """Test MarineIntelSignature in registry resolves to canonical class."""
        assert SignatureRegistry.get("MarineIntelSignature") is IndustryIntelSignature


# =============================================================================
# Intelligence Domain 2: Competitor Intelligence
# =============================================================================


class TestCompetitorIntelSignature:
    """Tests for CompetitorIntelSignature."""

    def test_input_fields(self):
        """Test CompetitorIntelSignature has expected fields."""
        fields = CompetitorIntelSignature.get_input_fields()

        assert "competitor" in fields
        assert "analysis_type" in fields
        assert "regions" in fields
        assert "segments" in fields

    def test_output_fields(self):
        """Test output fields include competitive analysis outputs."""
        fields = CompetitorIntelSignature.get_output_fields()

        assert "competitive_position" in fields
        assert "recent_wins_losses" in fields
        assert "pricing_intel" in fields
        assert "product_comparison" in fields
        assert "threat_assessment" in fields
        assert "tool_calls" in fields

    def test_capabilities(self):
        """Test capability extraction includes competitor-related terms."""
        capabilities = CompetitorIntelSignature.get_capabilities()

        assert any("competitor" in c or "competitive" in c for c in capabilities)


# =============================================================================
# Intelligence Domain 3: Product Intelligence
# =============================================================================


class TestProductIntelSignature:
    """Tests for ProductIntelSignature."""

    def test_input_fields(self):
        """Test ProductIntelSignature has expected fields."""
        fields = ProductIntelSignature.get_input_fields()

        assert "query" in fields
        assert "application" in fields
        assert "power_range" in fields
        assert "requirements" in fields

    def test_output_fields(self):
        """Test output fields include product-specific outputs."""
        fields = ProductIntelSignature.get_output_fields()

        assert "product_specs" in fields
        assert "fit_score" in fields
        assert "recommendations" in fields
        assert "comparison" in fields
        assert "similar_installations" in fields
        assert "tool_calls" in fields

    def test_capabilities(self):
        """Test capability extraction includes product-related terms."""
        capabilities = ProductIntelSignature.get_capabilities()

        assert any("product" in c for c in capabilities)


class TestKnowledgeBaseBackwardCompatibility:
    """Tests for KnowledgeBaseSignature backward compatibility."""

    def test_knowledge_base_is_alias(self):
        """Test that KnowledgeBaseSignature is alias for ProductIntelSignature."""
        assert KnowledgeBaseSignature is ProductIntelSignature

    def test_knowledge_base_in_registry(self):
        """Test KnowledgeBaseSignature is registered under alias name."""
        assert "KnowledgeBaseSignature" in SignatureRegistry.all()

    def test_knowledge_base_resolves_to_canonical(self):
        """Test KnowledgeBaseSignature in registry resolves to canonical class."""
        assert SignatureRegistry.get("KnowledgeBaseSignature") is ProductIntelSignature


# =============================================================================
# Order Processing Domain: Opportunity Agent
# =============================================================================


class TestOpportunitySignature:
    """Tests for OpportunitySignature."""

    def test_input_fields(self):
        """Test OpportunitySignature has expected fields."""
        fields = OpportunitySignature.get_input_fields()

        assert "opportunity_id" in fields
        assert "account_id" in fields
        assert "include_ipas" in fields

    def test_output_fields(self):
        """Test output fields include opportunity-specific outputs."""
        fields = OpportunitySignature.get_output_fields()

        assert "opportunities" in fields
        assert "product_configurations" in fields
        assert "ipas_quote_id" in fields
        assert "tool_calls" in fields

    def test_capabilities(self):
        """Test capability extraction includes opportunity-related terms."""
        capabilities = OpportunitySignature.get_capabilities()

        assert any("opportunity" in c or "cec" in c.lower() for c in capabilities)


# =============================================================================
# Order Processing Domain: Data Management Agent
# =============================================================================


class TestDataManagementSignature:
    """Tests for DataManagementSignature."""

    def test_input_fields(self):
        """Test DataManagementSignature has expected fields."""
        fields = DataManagementSignature.get_input_fields()

        assert "ipas_quote_id" in fields
        assert "target_system" in fields

    def test_output_fields(self):
        """Test output fields include data management outputs."""
        fields = DataManagementSignature.get_output_fields()

        assert "ipas_data_display" in fields
        assert "suggested_fields" in fields
        assert "bom_items" in fields
        assert "validation_status" in fields
        assert "tool_calls" in fields

    def test_capabilities(self):
        """Test capability extraction includes data management terms."""
        capabilities = DataManagementSignature.get_capabilities()

        assert any(
            "ipas" in c.lower() or "ms5" in c.lower() or "data" in c
            for c in capabilities
        )


# =============================================================================
# Order Processing Domain: Financial Ops Agent
# =============================================================================


class TestFinancialOpsSignature:
    """Tests for FinancialOpsSignature."""

    def test_input_fields(self):
        """Test FinancialOpsSignature has expected fields."""
        fields = FinancialOpsSignature.get_input_fields()

        assert "opportunity_id" in fields
        assert "customer_id" in fields
        assert "order_type" in fields

    def test_output_fields(self):
        """Test output fields include financial ops outputs."""
        fields = FinancialOpsSignature.get_output_fields()

        assert "order_id" in fields
        assert "order_status" in fields
        assert "simulation_result" in fields
        assert "credit_check" in fields
        assert "tool_calls" in fields

    def test_capabilities(self):
        """Test capability extraction includes financial ops terms."""
        capabilities = FinancialOpsSignature.get_capabilities()

        assert any("order" in c or "draft" in c or "sales" in c for c in capabilities)


# =============================================================================
# Supporting Agent: KYP
# =============================================================================


class TestKYPSignature:
    """Tests for KYPSignature."""

    def test_input_fields(self):
        """Test KYPSignature has expected fields."""
        fields = KYPSignature.get_input_fields()

        assert "entity_name" in fields
        assert "check_types" in fields
        assert "detail_level" in fields
        assert "include_business_context" in fields

    def test_output_fields(self):
        """Test output fields include KYP-specific outputs."""
        fields = KYPSignature.get_output_fields()

        assert "kyp_report" in fields
        assert "risk_score" in fields
        assert "credit_status" in fields
        assert "sanctions_status" in fields
        assert "financial_health" in fields
        assert "business_context" in fields
        assert "recommendation" in fields

    def test_capabilities(self):
        """Test capability extraction includes due diligence terms."""
        capabilities = KYPSignature.get_capabilities()

        # Should include due diligence keywords
        assert any("diligence" in c for c in capabilities)


# =============================================================================
# Supporting Agent: Customer Matcher
# =============================================================================


class TestCustomerMatcherSignature:
    """Tests for CustomerMatcherSignature."""

    def test_input_fields(self):
        """Test CustomerMatcherSignature has expected fields."""
        fields = CustomerMatcherSignature.get_input_fields()

        assert "company_name" in fields
        assert "match_type" in fields
        assert "country_hint" in fields

    def test_output_fields(self):
        """Test output fields include customer matching outputs."""
        fields = CustomerMatcherSignature.get_output_fields()

        assert "customer_id" in fields
        assert "match_confidence" in fields
        assert "candidates" in fields


# =============================================================================
# Web Search Tool
# =============================================================================


class TestWebSearchSignature:
    """Tests for WebSearchSignature."""

    def test_has_search_capabilities(self):
        """Test WebSearchSignature has search-related capabilities."""
        capabilities = WebSearchSignature.get_capabilities()

        assert any("search" in c for c in capabilities)


# =============================================================================
# Signature Registry
# =============================================================================


class TestSignatureRegistry:
    """Tests for SignatureRegistry."""

    def test_intelligence_domains_registered(self):
        """Test that all 3 intelligence domains are registered."""
        all_sigs = SignatureRegistry.all()

        assert "IndustryIntelSignature" in all_sigs
        assert "CompetitorIntelSignature" in all_sigs
        assert "ProductIntelSignature" in all_sigs

    def test_supporting_agents_registered(self):
        """Test that supporting agents are registered."""
        all_sigs = SignatureRegistry.all()

        assert "KYPSignature" in all_sigs
        assert "CustomerMatcherSignature" in all_sigs
        assert "WebSearchSignature" in all_sigs

    def test_get_signature(self):
        """Test getting a signature by name."""
        sig = SignatureRegistry.get("IndustryIntelSignature")
        assert sig is IndustryIntelSignature

    def test_get_nonexistent_signature(self):
        """Test getting a non-existent signature returns None."""
        sig = SignatureRegistry.get("NonExistentSignature")
        assert sig is None

    def test_register_new_signature(self):
        """Test registering a new signature."""

        @SignatureRegistry.register
        class NewTestSignature(AgentSignature):
            query = InputField(description="Test")

        assert "NewTestSignature" in SignatureRegistry.all()
        assert SignatureRegistry.get("NewTestSignature") is NewTestSignature

    def test_find_by_capability(self):
        """Test finding signatures by capability."""
        # Should find IndustryIntelSignature for "market" capability
        matches = SignatureRegistry.find_by_capability("market")

        # At least IndustryIntelSignature should match
        assert len(matches) >= 1
        assert IndustryIntelSignature in matches

    def test_find_by_capability_no_match(self):
        """Test finding with no matching capability."""
        matches = SignatureRegistry.find_by_capability("xyz_nonexistent_capability")
        assert len(matches) == 0

    def test_get_intelligence_agents(self):
        """Test getting the 4 intelligence domain signatures (per ADR-002)."""
        intel_agents = SignatureRegistry.get_intelligence_agents()

        # ADR-002 defines 4 intelligence agents: Industry, Competitor, Product, KYP
        assert len(intel_agents) == 4
        assert IndustryIntelSignature in intel_agents
        assert CompetitorIntelSignature in intel_agents
        assert ProductIntelSignature in intel_agents
        assert KYPSignature in intel_agents

    def test_get_order_processing_agents(self):
        """Test getting the 4 order processing domain signatures."""
        order_agents = SignatureRegistry.get_order_processing_agents()

        # ADR-002 defines 4 order processing agents (updated to include BillingCollections)
        assert len(order_agents) == 4
        assert OpportunitySignature in order_agents
        assert DataManagementSignature in order_agents
        assert FinancialOpsSignature in order_agents
        assert BillingCollectionsSignature in order_agents

    def test_order_processing_agents_registered(self):
        """Test that all order processing agents are registered."""
        all_sigs = SignatureRegistry.all()

        assert "OpportunitySignature" in all_sigs
        assert "DataManagementSignature" in all_sigs
        assert "FinancialOpsSignature" in all_sigs
        assert "BillingCollectionsSignature" in all_sigs

    def test_all_order_processing_agents_have_convergence(self):
        """Test all order processing agents support convergence."""
        for sig in SignatureRegistry.get_order_processing_agents():
            card = sig.to_a2a_card()
            assert card["has_convergence"] is True, f"{sig.__name__} lacks convergence"


# =============================================================================
# Signature Inheritance
# =============================================================================


class TestSignatureInheritance:
    """Tests for signature inheritance patterns."""

    def test_signature_inheritance(self):
        """Test that signatures can inherit from others."""

        class BaseSignature(AgentSignature):
            query = InputField(description="Base query")
            tool_calls = OutputField(description="Tools", default=[])

        class ExtendedSignature(BaseSignature):
            extra_param = InputField(description="Extra", required=False, default=None)
            extra_output = OutputField(description="Extra output")

        # Extended should have both base and extended fields
        inputs = ExtendedSignature.get_input_fields()
        assert "extra_param" in inputs

        outputs = ExtendedSignature.get_output_fields()
        assert "extra_output" in outputs


# =============================================================================
# A2A Card Integration
# =============================================================================


class TestA2ACardIntegration:
    """Tests for A2A card generation and usage."""

    def test_a2a_card_format(self):
        """Test A2A card has required format for semantic matching."""
        card = IndustryIntelSignature.to_a2a_card()

        # Required fields for A2A protocol
        assert "name" in card
        assert "capabilities" in card
        assert "input_schema" in card
        assert "output_schema" in card
        assert "has_convergence" in card

    def test_a2a_card_capabilities_not_empty(self):
        """Test that capabilities are extracted."""
        card = IndustryIntelSignature.to_a2a_card()
        assert len(card["capabilities"]) > 0

    def test_a2a_card_input_schema_structure(self):
        """Test input schema has proper structure."""
        card = IndustryIntelSignature.to_a2a_card()
        input_schema = card["input_schema"]

        # Each field should have description and required
        for field_name, field_info in input_schema.items():
            assert "description" in field_info
            assert "required" in field_info

    def test_all_intelligence_agents_have_convergence(self):
        """Test all intelligence agents support convergence."""
        for sig in SignatureRegistry.get_intelligence_agents():
            card = sig.to_a2a_card()
            assert card["has_convergence"] is True, f"{sig.__name__} lacks convergence"
