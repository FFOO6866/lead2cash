"""
Integration Tests for Agent-Signature Integration

Tests verify that:
1. Each agent class has a SIGNATURE attribute pointing to centralized signatures
2. Agents can be instantiated and their signatures match the registry
3. SalesOpsAgent initializes all agents with correct signatures
4. A2A routing works via SignatureRegistry capability matching

NO MOCKING - Tests use real agent and signature classes.
"""

from lead_to_cash.agents.signatures import (
    BillingCollectionsSignature,
    CompetitorIntelSignature,
    DataManagementSignature,
    FinancialOpsSignature,
    IndustryIntelSignature,
    KYPSignature,
    OpportunitySignature,
    ProductIntelSignature,
    SignatureRegistry,
)


class TestAgentSignatureAttribute:
    """Test that each agent has a SIGNATURE class attribute referencing centralized signatures."""

    def test_marine_intel_agent_has_signature(self):
        """MarineIntelAgent should have SIGNATURE = IndustryIntelSignature."""
        from lead_to_cash.agents.marine_intel_agent import MarineIntelAgent

        assert hasattr(
            MarineIntelAgent, "SIGNATURE"
        ), "MarineIntelAgent should have SIGNATURE attribute"
        assert MarineIntelAgent.SIGNATURE is IndustryIntelSignature, (
            f"MarineIntelAgent.SIGNATURE should be IndustryIntelSignature, "
            f"got {MarineIntelAgent.SIGNATURE}"
        )

    def test_competitor_intel_agent_has_signature(self):
        """CompetitorIntelAgent should have SIGNATURE = CompetitorIntelSignature."""
        from lead_to_cash.agents.competitor_intel_agent import CompetitorIntelAgent

        assert hasattr(
            CompetitorIntelAgent, "SIGNATURE"
        ), "CompetitorIntelAgent should have SIGNATURE attribute"
        assert CompetitorIntelAgent.SIGNATURE is CompetitorIntelSignature, (
            f"CompetitorIntelAgent.SIGNATURE should be CompetitorIntelSignature, "
            f"got {CompetitorIntelAgent.SIGNATURE}"
        )

    def test_knowledge_base_agent_has_signature(self):
        """KnowledgeBaseAgent should have SIGNATURE = ProductIntelSignature."""
        from lead_to_cash.agents.knowledge_base_agent import KnowledgeBaseAgent

        assert hasattr(
            KnowledgeBaseAgent, "SIGNATURE"
        ), "KnowledgeBaseAgent should have SIGNATURE attribute"
        assert KnowledgeBaseAgent.SIGNATURE is ProductIntelSignature, (
            f"KnowledgeBaseAgent.SIGNATURE should be ProductIntelSignature, "
            f"got {KnowledgeBaseAgent.SIGNATURE}"
        )

    def test_due_diligence_agent_has_signature(self):
        """DueDiligenceAgent should have SIGNATURE = KYPSignature."""
        from lead_to_cash.agents.due_diligence_agent import DueDiligenceAgent

        assert hasattr(
            DueDiligenceAgent, "SIGNATURE"
        ), "DueDiligenceAgent should have SIGNATURE attribute"
        assert DueDiligenceAgent.SIGNATURE is KYPSignature, (
            f"DueDiligenceAgent.SIGNATURE should be KYPSignature, "
            f"got {DueDiligenceAgent.SIGNATURE}"
        )

    def test_opportunity_agent_has_signature(self):
        """OpportunityAgent should have SIGNATURE = OpportunitySignature."""
        from lead_to_cash.agents.opportunity_agent import OpportunityAgent

        assert hasattr(
            OpportunityAgent, "SIGNATURE"
        ), "OpportunityAgent should have SIGNATURE attribute"
        assert OpportunityAgent.SIGNATURE is OpportunitySignature, (
            f"OpportunityAgent.SIGNATURE should be OpportunitySignature, "
            f"got {OpportunityAgent.SIGNATURE}"
        )

    def test_data_management_agent_has_signature(self):
        """DataManagementAgent should have SIGNATURE = DataManagementSignature."""
        from lead_to_cash.agents.data_management_agent import DataManagementAgent

        assert hasattr(
            DataManagementAgent, "SIGNATURE"
        ), "DataManagementAgent should have SIGNATURE attribute"
        assert DataManagementAgent.SIGNATURE is DataManagementSignature, (
            f"DataManagementAgent.SIGNATURE should be DataManagementSignature, "
            f"got {DataManagementAgent.SIGNATURE}"
        )

    def test_financial_ops_agent_has_signature(self):
        """FinancialOpsAgent should have SIGNATURE = FinancialOpsSignature."""
        from lead_to_cash.agents.financial_ops_agent import FinancialOpsAgent

        assert hasattr(
            FinancialOpsAgent, "SIGNATURE"
        ), "FinancialOpsAgent should have SIGNATURE attribute"
        assert FinancialOpsAgent.SIGNATURE is FinancialOpsSignature, (
            f"FinancialOpsAgent.SIGNATURE should be FinancialOpsSignature, "
            f"got {FinancialOpsAgent.SIGNATURE}"
        )


class TestSalesOpsAgentInitialization:
    """Test that SalesOpsAgent initializes all agents correctly."""

    def test_sales_ops_initializes_all_domain_agents(self):
        """SalesOpsAgent should initialize all 9 domain agents."""
        from lead_to_cash.agents import AgentType, SalesOpsAgent, SalesOpsConfig

        config = SalesOpsConfig()
        agent = SalesOpsAgent(config)

        # Verify all agents are initialized
        expected_agents = [
            AgentType.MARINE_INTEL,
            AgentType.CUSTOMER_MATCHER,
            AgentType.COMPETITOR_INTEL,
            AgentType.DUE_DILIGENCE,
            AgentType.KNOWLEDGE_BASE,
            AgentType.OPPORTUNITY,
            AgentType.DATA_MANAGEMENT,
            AgentType.FINANCIAL_OPS,
            AgentType.ENTITY_RESOLUTION,
        ]

        for agent_type in expected_agents:
            assert (
                agent_type in agent._agents
            ), f"{agent_type} should be initialized in SalesOpsAgent"

        assert (
            len(agent._agents) == 9
        ), f"SalesOpsAgent should have 9 agents, got {len(agent._agents)}"

    def test_intelligence_domain_agents_have_signatures(self):
        """Intelligence domain agents should have SIGNATURE pointing to registry signatures."""
        from lead_to_cash.agents import AgentType, SalesOpsAgent, SalesOpsConfig

        config = SalesOpsConfig()
        orchestrator = SalesOpsAgent(config)

        # Intelligence domain agents
        intel_agents = [
            (AgentType.MARINE_INTEL, IndustryIntelSignature),
            (AgentType.COMPETITOR_INTEL, CompetitorIntelSignature),
            (AgentType.KNOWLEDGE_BASE, ProductIntelSignature),
            (AgentType.DUE_DILIGENCE, KYPSignature),
        ]

        for agent_type, expected_sig in intel_agents:
            agent = orchestrator._agents.get(agent_type)
            assert agent is not None, f"{agent_type} should be initialized"
            assert hasattr(
                agent.__class__, "SIGNATURE"
            ), f"{agent_type} class should have SIGNATURE"
            assert (
                agent.__class__.SIGNATURE is expected_sig
            ), f"{agent_type}.SIGNATURE should be {expected_sig.__name__}"

    def test_order_processing_agents_have_signatures(self):
        """Order processing agents should have SIGNATURE pointing to registry signatures."""
        from lead_to_cash.agents import AgentType, SalesOpsAgent, SalesOpsConfig

        config = SalesOpsConfig()
        orchestrator = SalesOpsAgent(config)

        # Order processing domain agents
        order_agents = [
            (AgentType.OPPORTUNITY, OpportunitySignature),
            (AgentType.DATA_MANAGEMENT, DataManagementSignature),
            (AgentType.FINANCIAL_OPS, FinancialOpsSignature),
        ]

        for agent_type, expected_sig in order_agents:
            agent = orchestrator._agents.get(agent_type)
            assert agent is not None, f"{agent_type} should be initialized"
            assert hasattr(
                agent.__class__, "SIGNATURE"
            ), f"{agent_type} class should have SIGNATURE"
            assert (
                agent.__class__.SIGNATURE is expected_sig
            ), f"{agent_type}.SIGNATURE should be {expected_sig.__name__}"


class TestSignatureRegistryIntegration:
    """Test SignatureRegistry integration with agents."""

    def test_all_agent_signatures_registered(self):
        """All agent signatures should be registered in SignatureRegistry."""
        # Intelligence domain
        assert SignatureRegistry.get("IndustryIntelSignature") is not None
        assert SignatureRegistry.get("CompetitorIntelSignature") is not None
        assert SignatureRegistry.get("ProductIntelSignature") is not None
        assert SignatureRegistry.get("KYPSignature") is not None

        # Order processing domain
        assert SignatureRegistry.get("OpportunitySignature") is not None
        assert SignatureRegistry.get("DataManagementSignature") is not None
        assert SignatureRegistry.get("FinancialOpsSignature") is not None

    def test_backward_compatibility_aliases(self):
        """Backward compatibility aliases should resolve to canonical signatures."""
        # MarineIntelSignature -> IndustryIntelSignature
        marine_sig = SignatureRegistry.get("MarineIntelSignature")
        industry_sig = SignatureRegistry.get("IndustryIntelSignature")
        assert (
            marine_sig is industry_sig
        ), "MarineIntelSignature should alias to IndustryIntelSignature"

        # KnowledgeBaseSignature -> ProductIntelSignature
        kb_sig = SignatureRegistry.get("KnowledgeBaseSignature")
        product_sig = SignatureRegistry.get("ProductIntelSignature")
        assert (
            kb_sig is product_sig
        ), "KnowledgeBaseSignature should alias to ProductIntelSignature"

    def test_find_by_capability_returns_correct_agents(self):
        """SignatureRegistry.find_by_capability should find agents by capability."""
        # Test industry/market capability (single word search)
        industry_agents = SignatureRegistry.find_by_capability("market")
        assert len(industry_agents) > 0, "Should find agents for 'market'"
        assert IndustryIntelSignature in industry_agents

        # Test competitor capability
        competitor_agents = SignatureRegistry.find_by_capability("competitor")
        assert len(competitor_agents) > 0, "Should find agents for 'competitor'"
        assert CompetitorIntelSignature in competitor_agents

        # Test due diligence/KYP capability
        kyp_agents = SignatureRegistry.find_by_capability("sanctions")
        assert len(kyp_agents) > 0, "Should find agents for 'sanctions'"
        assert KYPSignature in kyp_agents

    def test_get_intelligence_agents(self):
        """SignatureRegistry.get_intelligence_agents should return 4 intelligence signatures."""
        intel_agents = SignatureRegistry.get_intelligence_agents()

        assert (
            len(intel_agents) == 4
        ), f"Should have 4 intelligence agents, got {len(intel_agents)}"
        assert IndustryIntelSignature in intel_agents
        assert CompetitorIntelSignature in intel_agents
        assert ProductIntelSignature in intel_agents
        assert KYPSignature in intel_agents

    def test_get_order_processing_agents(self):
        """SignatureRegistry.get_order_processing_agents should return 4 order processing signatures."""
        order_agents = SignatureRegistry.get_order_processing_agents()

        assert (
            len(order_agents) == 4
        ), f"Should have 4 order processing agents, got {len(order_agents)}"
        assert OpportunitySignature in order_agents
        assert DataManagementSignature in order_agents
        assert FinancialOpsSignature in order_agents
        assert BillingCollectionsSignature in order_agents


class TestA2ACapabilityMatching:
    """Test A2A capability matching for intelligent task routing."""

    def test_all_signatures_have_capabilities(self):
        """All registered signatures should have get_capabilities method returning non-empty list."""
        all_sigs = (
            SignatureRegistry.get_intelligence_agents()
            + SignatureRegistry.get_order_processing_agents()
        )

        for sig in all_sigs:
            caps = sig.get_capabilities()
            assert len(caps) > 0, f"{sig.__name__} should have at least one capability"

    def test_all_signatures_have_convergence_detection(self):
        """All signatures should have tool_calls output field for convergence detection."""
        all_sigs = (
            SignatureRegistry.get_intelligence_agents()
            + SignatureRegistry.get_order_processing_agents()
        )

        for sig in all_sigs:
            output_fields = sig.get_output_fields()
            # get_output_fields returns a dict with field names as keys
            field_names = list(output_fields.keys())
            assert (
                "tool_calls" in field_names
            ), f"{sig.__name__} should have 'tool_calls' output field for convergence detection"

    def test_a2a_card_generation(self):
        """All signatures should generate valid A2A cards."""
        all_sigs = (
            SignatureRegistry.get_intelligence_agents()
            + SignatureRegistry.get_order_processing_agents()
        )

        for sig in all_sigs:
            card = sig.to_a2a_card()

            assert "name" in card, f"{sig.__name__} A2A card should have 'name'"
            assert (
                "description" in card
            ), f"{sig.__name__} A2A card should have 'description'"
            assert (
                "capabilities" in card
            ), f"{sig.__name__} A2A card should have 'capabilities'"
            assert (
                "input_schema" in card
            ), f"{sig.__name__} A2A card should have 'input_schema'"
            assert (
                "output_schema" in card
            ), f"{sig.__name__} A2A card should have 'output_schema'"

            # Verify capabilities is not empty
            assert (
                len(card["capabilities"]) > 0
            ), f"{sig.__name__} A2A card should have non-empty capabilities"


class TestEntityResolutionAgentIntegration:
    """Test EntityResolutionAgent integration with SalesOpsAgent."""

    def test_entity_resolution_agent_initialized(self):
        """EntityResolutionAgent should be initialized in SalesOpsAgent."""
        from lead_to_cash.agents import AgentType, SalesOpsAgent, SalesOpsConfig

        config = SalesOpsConfig()
        agent = SalesOpsAgent(config)

        assert AgentType.ENTITY_RESOLUTION in agent._agents
        er_agent = agent._agents[AgentType.ENTITY_RESOLUTION]
        assert er_agent is not None

    def test_entity_resolution_has_signature(self):
        """EntityResolutionAgent should have EntityResolutionSignature."""
        from lead_to_cash.agents.entity_resolution_agent import (
            EntityResolutionAgent,
            EntityResolutionSignature,
        )

        # Check class has signature (defined locally, not in centralized registry)
        # EntityResolutionAgent defines its own signature
        config_imported = True
        try:
            from lead_to_cash.agents import EntityResolutionConfig

            EntityResolutionAgent(config=EntityResolutionConfig())
            # The agent uses EntityResolutionSignature internally
            assert EntityResolutionSignature is not None
        except ImportError:
            config_imported = False

        assert config_imported, "EntityResolutionAgent should be importable"

    def test_entity_resolution_agent_type_in_enum(self):
        """AgentType enum should have ENTITY_RESOLUTION."""
        from lead_to_cash.agents import AgentType

        assert hasattr(AgentType, "ENTITY_RESOLUTION")
        assert AgentType.ENTITY_RESOLUTION.value == "entity_resolution"


class TestAgentExports:
    """Test that all agents are properly exported from the agents module."""

    def test_intelligence_agents_exported(self):
        """Intelligence domain agents should be exported from lead_to_cash.agents."""
        from lead_to_cash.agents import (
            CompetitorIntelAgent,
            DueDiligenceAgent,
            KnowledgeBaseAgent,
            MarineIntelAgent,
        )

        assert MarineIntelAgent is not None
        assert CompetitorIntelAgent is not None
        assert KnowledgeBaseAgent is not None
        assert DueDiligenceAgent is not None

    def test_order_processing_agents_exported(self):
        """Order processing agents should be exported from lead_to_cash.agents."""
        from lead_to_cash.agents import (
            DataManagementAgent,
            FinancialOpsAgent,
            OpportunityAgent,
        )

        assert OpportunityAgent is not None
        assert DataManagementAgent is not None
        assert FinancialOpsAgent is not None

    def test_entity_resolution_agent_exported(self):
        """EntityResolutionAgent should be exported from lead_to_cash.agents."""
        from lead_to_cash.agents import (
            EntityResolutionAgent,
            EntityResolutionConfig,
            EntityResolutionSignature,
            get_entity_resolution_agent,
        )

        assert EntityResolutionAgent is not None
        assert EntityResolutionConfig is not None
        assert EntityResolutionSignature is not None
        assert get_entity_resolution_agent is not None

    def test_architecture_aliases_exported(self):
        """Architecture aliases should be exported from lead_to_cash.agents."""
        # Verify aliases point to the implementation classes
        from lead_to_cash.agents import (
            DueDiligenceAgent,
            IndustryIntelAgent,
            KnowledgeBaseAgent,
            KYPAgent,
            MarineIntelAgent,
            ProductIntelAgent,
        )

        assert IndustryIntelAgent is MarineIntelAgent
        assert ProductIntelAgent is KnowledgeBaseAgent
        assert KYPAgent is DueDiligenceAgent
