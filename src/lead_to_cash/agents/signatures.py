"""
Agent Signature System - Capability Declaration for A2A Matching

This module implements Kaizen-style signatures for agent capability declaration.
Signatures enable semantic matching for agent-to-agent (A2A) routing.

Lead-to-Cash Agent Architecture:
┌─────────────────────────────────────────────────────────────────┐
│                     SALES OPS AGENT                              │
│                   (Central Orchestrator)                         │
│  Intent classification, multi-agent coordination, synthesis      │
└────────────────────────┬────────────────────────────────────────┘
                         │
      ┌──────────────────┼──────────────────┐
      │                  │                  │
      ▼                  ▼                  ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ INTELLIGENCE  │ │ORDER PROCESSING│ │INFRASTRUCTURE │
│ (4 agents)    │ │ (3 agents)    │ │ (tools)       │
├───────────────┤ ├───────────────┤ ├───────────────┤
│ IndustryIntel │ │ Opportunity   │ │ WebSearch     │
│ CompetitorInt │ │ DataMgmt      │ │ Database      │
│ ProductIntel  │ │ FinancialOps  │ │ CustomerMatch │
│ KYP           │ │               │ │               │
└───────────────┘ └───────────────┘ └───────────────┘
      │                  │                  │
      └──────────────────┴──────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────────┐
│              KNOWLEDGE BASE (Shared Tool - 4 Data Domains)      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ MARKET   │ │ CUSTOMER │ │COMPETITOR│ │ PRODUCT  │           │
│  │ news,opps│ │ SAP,prof │ │ win/loss │ │ specs,fit│           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────────┐
│              SCRAPER / INGESTION LAYER (Populates KB)           │
│  NewsCollector | PressRoomScraper | CompetitorScrapers | RSS    │
└─────────────────────────────────────────────────────────────────┘

Key Concepts:
- InputField: Declares what the agent needs to perform its task
- OutputField: Declares what the agent produces
- tool_calls: Special output field for convergence detection (empty = done)
- Knowledge Base: Shared tool all agents can call (not a separate agent)

How A2A Matching Works:
1. Agent registers its signature (capabilities)
2. When a task arrives, A2A router extracts keywords/embeddings
3. Router matches task against agent signatures
4. Best matching agent is selected for execution

Usage:
    from lead_to_cash.agents.signatures import (
        AgentSignature,
        InputField,
        OutputField,
        IndustryIntelSignature,
        CompetitorIntelSignature,
        ProductIntelSignature,
    )

    # Get agent capabilities
    capabilities = IndustryIntelSignature.get_capabilities()
    # ['market', 'intelligence', 'opportunities', 'fleet', 'industry']

    # Generate A2A card for registration
    card = IndustryIntelSignature.to_a2a_card()
"""

from dataclasses import dataclass, field
from typing import Any, ClassVar, Optional


@dataclass
class FieldDescriptor:
    """
    Describes an input or output field for an agent signature.

    Attributes:
        description: Human-readable description of the field
        examples: Example values for the field
        required: Whether the field is required (for inputs)
        default: Default value if not provided
        field_type: The type of field (input/output)
    """

    description: str
    examples: list[str] = field(default_factory=list)
    required: bool = True
    default: Any = None
    field_type: str = "input"  # "input" or "output"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "description": self.description,
            "required": self.required,
        }
        if self.examples:
            result["examples"] = self.examples
        if self.default is not None:
            result["default"] = self.default
        return result


def InputField(
    description: str,
    examples: list[str] = None,
    required: bool = True,
    default: Any = None,
) -> FieldDescriptor:
    """
    Define an input field for an agent signature.

    Args:
        description: What this input represents
        examples: Example values to help with semantic matching
        required: Whether this input is required
        default: Default value if not provided

    Returns:
        FieldDescriptor configured as input
    """
    return FieldDescriptor(
        description=description,
        examples=examples or [],
        required=required,
        default=default,
        field_type="input",
    )


def OutputField(
    description: str,
    examples: list[str] = None,
    default: Any = None,
) -> FieldDescriptor:
    """
    Define an output field for an agent signature.

    Args:
        description: What this output represents
        examples: Example values
        default: Default value

    Returns:
        FieldDescriptor configured as output
    """
    return FieldDescriptor(
        description=description,
        examples=examples or [],
        required=False,
        default=default,
        field_type="output",
    )


class AgentSignatureMeta(type):
    """Metaclass for AgentSignature to collect field descriptors."""

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)

        # Collect fields from class attributes
        input_fields = {}
        output_fields = {}

        for attr_name, attr_value in namespace.items():
            if isinstance(attr_value, FieldDescriptor):
                if attr_value.field_type == "input":
                    input_fields[attr_name] = attr_value
                else:
                    output_fields[attr_name] = attr_value

        cls._input_fields = input_fields
        cls._output_fields = output_fields

        return cls


class AgentSignature(metaclass=AgentSignatureMeta):
    """
    Base class for agent capability signatures.

    Subclass this to define your agent's inputs and outputs.
    The signature is used for:
    1. A2A semantic matching (routing tasks to agents)
    2. Convergence detection (via tool_calls field)
    3. Documentation and validation

    Example:
        class MyAgentSignature(AgentSignature):
            # Inputs (what the agent needs)
            query = InputField(
                description="User query to process",
                examples=["market trends", "competitor analysis"]
            )

            # Outputs (what the agent produces)
            result = OutputField(description="Analysis result")
            tool_calls = OutputField(
                description="Next tools to call (empty when done)",
                default=[]
            )
    """

    # Class-level storage (populated by metaclass)
    _input_fields: ClassVar[dict[str, FieldDescriptor]] = {}
    _output_fields: ClassVar[dict[str, FieldDescriptor]] = {}

    @classmethod
    def get_input_fields(cls) -> dict[str, FieldDescriptor]:
        """Get all input field descriptors."""
        return cls._input_fields

    @classmethod
    def get_output_fields(cls) -> dict[str, FieldDescriptor]:
        """Get all output field descriptors."""
        return cls._output_fields

    @classmethod
    def get_capabilities(cls) -> list[str]:
        """
        Extract capability keywords from field descriptions.

        These keywords are used for semantic matching when routing tasks.

        Returns:
            List of unique capability keywords
        """
        capabilities = set()

        # Extract from all field descriptions
        all_fields = {**cls._input_fields, **cls._output_fields}
        for field_desc in all_fields.values():
            # Extract meaningful words from description
            words = field_desc.description.lower().split()
            capabilities.update(w for w in words if len(w) > 3 and w.isalpha())

            # Also include examples as capabilities
            for example in field_desc.examples:
                example_words = example.lower().replace("_", " ").split()
                capabilities.update(
                    w for w in example_words if len(w) > 3 and w.isalpha()
                )

        return sorted(capabilities)

    @classmethod
    def to_a2a_card(cls) -> dict[str, Any]:
        """
        Generate A2A capability card for agent registration.

        This card is used by the A2A router for semantic matching.

        Returns:
            Dictionary with signature metadata for A2A protocol
        """
        input_schema = {
            name: desc.to_dict() for name, desc in cls._input_fields.items()
        }
        output_schema = {
            name: desc.to_dict() for name, desc in cls._output_fields.items()
        }

        return {
            "name": cls.__name__,
            "description": cls.__doc__ or "",
            "capabilities": cls.get_capabilities(),
            "input_schema": input_schema,
            "output_schema": output_schema,
            "has_convergence": "tool_calls" in cls._output_fields,
        }

    @classmethod
    def validate_inputs(cls, inputs: dict[str, Any]) -> list[str]:
        """
        Validate that inputs match the signature.

        Returns list of validation errors (empty if valid).
        """
        errors = []

        for name, field_desc in cls._input_fields.items():
            if field_desc.required and name not in inputs:
                if field_desc.default is None:
                    errors.append(f"Required input '{name}' is missing")

        return errors

    @classmethod
    def validate_outputs(cls, outputs: dict[str, Any]) -> list[str]:
        """
        Validate that outputs match the signature.

        Returns list of validation errors (empty if valid).
        """
        errors = []

        # Check that all declared outputs are present (with defaults allowed)
        for name, field_desc in cls._output_fields.items():
            if name not in outputs and field_desc.default is None:
                errors.append(f"Expected output '{name}' is missing")

        return errors


# =============================================================================
# Intelligence Domain 1: INDUSTRY INTELLIGENCE
# =============================================================================


class IndustryIntelSignature(AgentSignature):
    """
    Signature for Industry Intelligence Agent.

    Domain: Market trends, fleet data, opportunities, industry news

    Capabilities:
    - Market opportunity identification
    - Fleet and vessel tracking
    - Industry news aggregation
    - Regional market analysis

    Tools Used:
    - Knowledge Base (shared): Entity resolution, historical data
    - Local VectorDB: Marine intel database, opportunities
    - SAP MCP: Customer cross-reference
    - Perplexity: Real-time news and updates
    """

    # Inputs
    query: FieldDescriptor = InputField(
        description="Natural language query about industry and market intelligence",
        examples=[
            "ferry contracts in APAC",
            "offshore vessel orders",
            "newbuild opportunities Singapore",
            "marine industry trends Europe",
        ],
    )
    regions: FieldDescriptor = InputField(
        description="Geographic regions of interest",
        examples=["APAC", "Europe", "Singapore", "Indonesia", "Americas"],
        required=False,
        default=[],
    )
    sectors: FieldDescriptor = InputField(
        description="Industry sectors to focus on",
        examples=["ferry", "offshore", "tanker", "container", "cruise"],
        required=False,
        default=[],
    )
    time_range: FieldDescriptor = InputField(
        description="Time range for data (days)",
        examples=["7", "30", "90"],
        required=False,
        default=30,
    )

    # Outputs
    opportunities: FieldDescriptor = OutputField(
        description="List of identified market opportunities with priority scores"
    )
    market_trends: FieldDescriptor = OutputField(
        description="Current market trends and analysis"
    )
    fleet_data: FieldDescriptor = OutputField(
        description="Fleet and vessel information relevant to query"
    )
    news_articles: FieldDescriptor = OutputField(
        description="Relevant industry news articles and sources"
    )
    customer_matches: FieldDescriptor = OutputField(
        description="Matched existing customers from SAP (if applicable)"
    )
    tool_calls: FieldDescriptor = OutputField(
        description="Next tools to call (empty when task is complete)",
        default=[],
    )


# Backward compatibility alias
MarineIntelSignature = IndustryIntelSignature


# =============================================================================
# Intelligence Domain 2: COMPETITOR INTELLIGENCE
# =============================================================================


class CompetitorIntelSignature(AgentSignature):
    """
    Signature for Competitor Intelligence Agent.

    Domain: Competitive analysis, win/loss tracking, market positioning

    Capabilities:
    - Competitor activity tracking
    - Win/loss analysis
    - Pricing intelligence
    - Product comparison
    - Strategic move detection

    Tools Used:
    - Knowledge Base (shared): Competitor profiles, product specs
    - Local VectorDB: Competitor signals database
    - SAP MCP: Check competitor presence at our customers
    - Perplexity: Real-time competitor news
    - EODHD: Financial data for public competitors
    """

    # Inputs
    competitor: FieldDescriptor = InputField(
        description="Competitor name to analyze",
        examples=[
            "Caterpillar",
            "Cummins",
            "Wartsila",
            "MAN Energy Solutions",
            "Volvo Penta",
        ],
    )
    analysis_type: FieldDescriptor = InputField(
        description="Type of competitive analysis to perform",
        examples=[
            "market_share",
            "win_loss",
            "pricing",
            "product_comparison",
            "strategic_moves",
        ],
        required=False,
        default="general",
    )
    regions: FieldDescriptor = InputField(
        description="Geographic regions for analysis",
        examples=["APAC", "Europe", "Americas", "Global"],
        required=False,
        default=[],
    )
    segments: FieldDescriptor = InputField(
        description="Market segments to analyze",
        examples=["marine", "power_generation", "industrial", "rail"],
        required=False,
        default=[],
    )
    time_range: FieldDescriptor = InputField(
        description="Time range for historical data",
        examples=["quarter", "year", "3_years"],
        required=False,
        default="year",
    )

    # Outputs
    competitive_position: FieldDescriptor = OutputField(
        description="Assessment of competitive positioning and market share"
    )
    recent_wins_losses: FieldDescriptor = OutputField(
        description="Recent competitive wins and losses with analysis"
    )
    pricing_intel: FieldDescriptor = OutputField(
        description="Pricing intelligence and discount patterns"
    )
    product_comparison: FieldDescriptor = OutputField(
        description="Product feature and capability comparison"
    )
    strategic_moves: FieldDescriptor = OutputField(
        description="Recent strategic moves, announcements, and acquisitions"
    )
    threat_assessment: FieldDescriptor = OutputField(
        description="Overall threat level and recommended counter-strategies"
    )
    tool_calls: FieldDescriptor = OutputField(
        description="Next tools to call (empty when task is complete)",
        default=[],
    )


# =============================================================================
# Intelligence Domain 3: PRODUCT INTELLIGENCE
# =============================================================================


class ProductIntelSignature(AgentSignature):
    """
    Signature for Product Intelligence Agent.

    Domain: Product specifications, fit analysis, recommendations

    Capabilities:
    - Product specification lookup
    - Application fit scoring
    - Product recommendations
    - Technical comparison
    - Configuration guidance

    Tools Used:
    - Knowledge Base (shared): Product specs, technical documentation
    - Local VectorDB: Similar applications, case studies
    - SAP MCP: Installed base data
    """

    # Inputs
    query: FieldDescriptor = InputField(
        description="Query for product information or fit analysis",
        examples=[
            "MTU 16V 4000 specifications",
            "engine for 50m ferry",
            "compare MTU vs Caterpillar for OSV",
            "power requirements for cruise ship",
        ],
    )
    application: FieldDescriptor = InputField(
        description="Target application or use case",
        examples=["ferry", "tug", "OSV", "yacht", "power_plant", "data_center"],
        required=False,
        default=None,
    )
    power_range: FieldDescriptor = InputField(
        description="Power range in kW (min-max)",
        examples=["500-1000", "2000-5000", "10000+"],
        required=False,
        default=None,
    )
    requirements: FieldDescriptor = InputField(
        description="Specific technical requirements",
        examples=["IMO Tier III", "dual fuel", "low emissions", "high efficiency"],
        required=False,
        default=[],
    )

    # Outputs
    product_specs: FieldDescriptor = OutputField(
        description="Detailed product specifications"
    )
    fit_score: FieldDescriptor = OutputField(
        description="Application fit score (0-100) with justification"
    )
    recommendations: FieldDescriptor = OutputField(
        description="Recommended products for the application"
    )
    comparison: FieldDescriptor = OutputField(
        description="Comparison table if multiple products considered"
    )
    configuration: FieldDescriptor = OutputField(
        description="Recommended configuration and options"
    )
    similar_installations: FieldDescriptor = OutputField(
        description="Similar successful installations as references"
    )
    tool_calls: FieldDescriptor = OutputField(
        description="Next tools to call (empty when task is complete)",
        default=[],
    )


# Backward compatibility alias
KnowledgeBaseSignature = ProductIntelSignature


# =============================================================================
# Supporting Agent: KYP (Know Your Partner) Due Diligence
# =============================================================================


class KYPSignature(AgentSignature):
    """
    Signature for KYP (Know Your Partner) Due Diligence Agent.

    Domain: Comprehensive due diligence orchestrating all intelligence domains

    Capabilities:
    - Credit status verification
    - Sanctions and blacklist checking
    - Financial health assessment
    - Litigation and legal review
    - Reputation analysis

    Orchestrates:
    - Industry Intel: Business context, market position
    - Competitor Intel: Competitive landscape
    - Product Intel: Installed base, technical relationship

    Tools Used:
    - Knowledge Base (shared): Entity profiles, historical KYP
    - SAP MCP: Customer data, credit status
    - EODHD: Financial fundamentals
    - Perplexity: Sanctions, litigation, news
    - Aravo: Third-party risk management
    """

    # Inputs
    entity_name: FieldDescriptor = InputField(
        description="Company name for due diligence",
        examples=["ST Engineering", "Maersk", "Pacific International Lines"],
    )
    check_types: FieldDescriptor = InputField(
        description="Types of checks to perform",
        examples=[
            "credit",
            "sanctions",
            "litigation",
            "financial",
            "reputation",
            "all",
        ],
        required=False,
        default=["all"],
    )
    detail_level: FieldDescriptor = InputField(
        description="Level of detail for the report",
        examples=["summary", "full"],
        required=False,
        default="full",
    )
    include_business_context: FieldDescriptor = InputField(
        description="Include business relationship context (contracts, pipeline, revenue)",
        required=False,
        default=True,
    )

    # Outputs
    kyp_report: FieldDescriptor = OutputField(
        description="Comprehensive KYP due diligence report with all sections"
    )
    risk_score: FieldDescriptor = OutputField(
        description="Overall risk score (0-100, higher = more risk)"
    )
    credit_status: FieldDescriptor = OutputField(
        description="SAP credit check results with limit/exposure"
    )
    sanctions_status: FieldDescriptor = OutputField(
        description="Sanctions and blacklist check results (NO_ADVERSE_FINDINGS or ADVERSE_FINDINGS)"
    )
    financial_health: FieldDescriptor = OutputField(
        description="Financial health assessment from EODHD"
    )
    business_context: FieldDescriptor = OutputField(
        description="Business relationship summary (contracts, pipeline, revenue)"
    )
    recommendation: FieldDescriptor = OutputField(
        description="PROCEED / PROCEED_WITH_CAUTION / DO_NOT_PROCEED"
    )
    tool_calls: FieldDescriptor = OutputField(
        description="Next tools to call (empty when task is complete)",
        default=[],
    )


# =============================================================================
# Supporting Agent: Customer/Entity Matcher
# =============================================================================


class CustomerMatcherSignature(AgentSignature):
    """
    Signature for Customer/Entity Matcher Agent.

    Domain: Entity resolution and customer identification

    Capabilities:
    - Customer lookup in SAP
    - Fuzzy name matching
    - Entity resolution across sources
    - Credit information retrieval

    Tools Used:
    - Knowledge Base (shared): Entity registry, aliases
    - SAP MCP: Customer master data
    - ACRA/GLEIF: External registries for verification
    """

    # Inputs
    company_name: FieldDescriptor = InputField(
        description="Company name to match",
        examples=["Batam Fast", "ST Engineering", "stengg", "maersk"],
    )
    match_type: FieldDescriptor = InputField(
        description="Type of matching to perform",
        examples=["exact", "fuzzy", "semantic"],
        required=False,
        default="semantic",
    )
    country_hint: FieldDescriptor = InputField(
        description="Country hint to narrow search",
        examples=["SG", "DK", "US"],
        required=False,
        default=None,
    )
    include_credit: FieldDescriptor = InputField(
        description="Whether to include credit information",
        required=False,
        default=True,
    )

    # Outputs
    customer_id: FieldDescriptor = OutputField(description="SAP customer ID if matched")
    customer_name: FieldDescriptor = OutputField(
        description="Canonical customer name from SAP"
    )
    match_confidence: FieldDescriptor = OutputField(
        description="Confidence score for the match (0-100)"
    )
    match_type_used: FieldDescriptor = OutputField(
        description="Type of match that succeeded (exact, alias, fuzzy)"
    )
    credit_info: FieldDescriptor = OutputField(
        description="Credit limit and exposure if requested"
    )
    uen: FieldDescriptor = OutputField(description="UEN/Tax number if available")
    candidates: FieldDescriptor = OutputField(
        description="List of candidate matches if ambiguous"
    )
    tool_calls: FieldDescriptor = OutputField(
        description="Next tools to call (empty when task is complete)",
        default=[],
    )


# =============================================================================
# Tool: Web Search (Perplexity)
# =============================================================================


class WebSearchSignature(AgentSignature):
    """
    Signature for Web Search Tool (via Perplexity).

    This is a TOOL, not an agent - called by intelligence agents.

    Capabilities:
    - Real-time web search
    - News aggregation
    - Source verification
    """

    # Inputs
    query: FieldDescriptor = InputField(
        description="Search query for web research",
        examples=["Caterpillar marine contract 2024", "ferry industry APAC news"],
    )
    search_depth: FieldDescriptor = InputField(
        description="Depth of search",
        examples=["quick", "standard", "deep"],
        required=False,
        default="standard",
    )
    sources: FieldDescriptor = InputField(
        description="Preferred sources",
        examples=["news", "industry", "financial", "regulatory"],
        required=False,
        default=["news", "industry"],
    )

    # Outputs
    search_results: FieldDescriptor = OutputField(
        description="Search results with summaries"
    )
    sources_consulted: FieldDescriptor = OutputField(
        description="List of sources consulted with URLs"
    )
    key_findings: FieldDescriptor = OutputField(
        description="Key findings synthesized from search"
    )
    tool_calls: FieldDescriptor = OutputField(
        description="Next tools to call (empty when task is complete)",
        default=[],
    )


# =============================================================================
# ORDER PROCESSING DOMAIN: Opportunity Agent
# =============================================================================


class OpportunitySignature(AgentSignature):
    """
    Signature for Opportunity Agent.

    Domain: Extract opportunity data from CEC and IPAS

    Capabilities:
    - Read opportunities from SAP CEC (Sales Cloud)
    - Extract product configurations from IPAS (XML)
    - Link opportunities to product configurations

    Tools Used:
    - CEC Client: Opportunity retrieval
    - IPAS Client: Product configuration XML extraction
    - Knowledge Base (shared): Entity resolution
    """

    # Inputs
    opportunity_id: FieldDescriptor = InputField(
        description="CEC opportunity ID to retrieve",
        examples=["OPP-2026-001", "1000012345"],
        required=False,
        default=None,
    )
    account_id: FieldDescriptor = InputField(
        description="SAP customer ID to get all opportunities",
        examples=["0022005992", "0000100001"],
        required=False,
        default=None,
    )
    include_ipas: FieldDescriptor = InputField(
        description="Include IPAS product configuration data",
        required=False,
        default=True,
    )

    # Outputs
    opportunities: FieldDescriptor = OutputField(
        description="List of CEC opportunities with status, value, dates"
    )
    product_configurations: FieldDescriptor = OutputField(
        description="IPAS product configurations linked to opportunities"
    )
    ipas_quote_id: FieldDescriptor = OutputField(
        description="IPAS quote reference number"
    )
    sap_order_id: FieldDescriptor = OutputField(
        description="SAP sales order reference (if exists)"
    )
    tool_calls: FieldDescriptor = OutputField(
        description="Next tools to call (empty when task is complete)",
        default=[],
    )


# =============================================================================
# ORDER PROCESSING DOMAIN: Data Management Agent
# =============================================================================


class DataManagementSignature(AgentSignature):
    """
    Signature for Data Management Agent.

    Domain: Assist with SAP data entry by displaying IPAS data and suggesting field values

    Capabilities:
    - Display IPAS product configuration for user review
    - Suggest MS5 field values based on IPAS data
    - Validate data completeness before order creation
    - Map IPAS fields to SAP sales order fields

    Tools Used:
    - IPAS Client: Read product configurations
    - SAP MCP: Field validation, reference data
    - Knowledge Base (shared): Entity resolution
    """

    # Inputs
    ipas_quote_id: FieldDescriptor = InputField(
        description="IPAS quote ID to extract data from",
        examples=["IPAS-2025-0892", "IPAS-2026-0001"],
    )
    target_system: FieldDescriptor = InputField(
        description="Target SAP system for field mapping",
        examples=["MS5", "S4HANA"],
        required=False,
        default="MS5",
    )
    display_mode: FieldDescriptor = InputField(
        description="How to display data to user",
        examples=["summary", "detailed", "field_mapping"],
        required=False,
        default="field_mapping",
    )

    # Outputs
    ipas_data_display: FieldDescriptor = OutputField(
        description="Formatted IPAS data for user display"
    )
    suggested_fields: FieldDescriptor = OutputField(
        description="Suggested SAP field values mapped from IPAS"
    )
    bom_items: FieldDescriptor = OutputField(
        description="Bill of materials from IPAS configuration"
    )
    validation_status: FieldDescriptor = OutputField(
        description="Data validation result (complete/incomplete with missing fields)"
    )
    user_actions: FieldDescriptor = OutputField(
        description="Actions user needs to take before order creation"
    )
    tool_calls: FieldDescriptor = OutputField(
        description="Next tools to call (empty when task is complete)",
        default=[],
    )


# =============================================================================
# ORDER PROCESSING DOMAIN: Financial Operations Agent
# =============================================================================


class FinancialOpsSignature(AgentSignature):
    """
    Signature for Financial Operations Agent.

    Domain: Create draft sales orders in MS5 (S/4HANA)

    Capabilities:
    - Create draft sales orders in SAP MS5
    - Validate order data before submission
    - Handle order simulation
    - Track order status

    Tools Used:
    - MS5 Client: Sales order creation
    - SAP MCP: Customer data, credit check
    - IPAS Client: Product configuration for BOM
    """

    # Inputs
    opportunity_id: FieldDescriptor = InputField(
        description="CEC opportunity ID for reference",
        examples=["OPP-2026-001"],
    )
    customer_id: FieldDescriptor = InputField(
        description="SAP customer ID (10-digit)",
        examples=["0022005992", "0000100001"],
    )
    ipas_quote_id: FieldDescriptor = InputField(
        description="IPAS quote ID for product configuration",
        examples=["IPAS-2025-0892"],
        required=False,
        default=None,
    )
    order_type: FieldDescriptor = InputField(
        description="Sales order type",
        examples=["draft", "simulation", "final"],
        required=False,
        default="draft",
    )
    items: FieldDescriptor = InputField(
        description="Order line items (materials, quantities)",
        required=False,
        default=[],
    )

    # Outputs
    order_id: FieldDescriptor = OutputField(
        description="SAP sales order ID (if created)"
    )
    order_status: FieldDescriptor = OutputField(
        description="Order status (draft/simulated/created/error)"
    )
    simulation_result: FieldDescriptor = OutputField(
        description="Order simulation results (pricing, availability)"
    )
    credit_check: FieldDescriptor = OutputField(
        description="Credit check result for customer"
    )
    validation_errors: FieldDescriptor = OutputField(
        description="Any validation errors preventing order creation"
    )
    next_steps: FieldDescriptor = OutputField(
        description="Recommended next steps for sales process"
    )
    tool_calls: FieldDescriptor = OutputField(
        description="Next tools to call (empty when task is complete)",
        default=[],
    )


# =============================================================================
# ORDER PROCESSING DOMAIN: Billing & Collections Agent
# =============================================================================


class BillingCollectionsSignature(AgentSignature):
    """
    Signature for Billing & Collections Agent.

    Domain: Accounts receivable, billing status, collections tracking

    Capabilities:
    - Get billing items pending invoicing
    - Track collections status and overdue payments
    - Retrieve payment terms for customers
    - Provide aging bucket analysis
    - Explain payment schedules and milestones

    Tools Used:
    - FinOpsDataService: Billing and collections data aggregation
    - CPI/MS5: SAP billing documents
    - PaymentTermsHarmonizer: Parse complex payment terms text
    """

    # Inputs
    customer_id: FieldDescriptor = InputField(
        description="SAP customer ID for billing lookup",
        examples=["0022005992", "0000100001", "0021000090"],
        required=False,
        default=None,
    )
    document_number: FieldDescriptor = InputField(
        description="Specific billing document number to look up",
        examples=["3228005112", "3228005113"],
        required=False,
        default=None,
    )
    query_type: FieldDescriptor = InputField(
        description="Type of billing/collections query",
        examples=["billing", "collections", "aging", "payment_terms", "summary"],
        required=False,
        default="summary",
    )
    status_filter: FieldDescriptor = InputField(
        description="Filter by billing status",
        examples=["PENDING_BILLING", "PENDING_COLLECTION", "OVERDUE", "PARTIALLY_PAID"],
        required=False,
        default=None,
    )

    # Outputs
    billing_items: FieldDescriptor = OutputField(
        description="List of billing items with status and amounts"
    )
    collections_items: FieldDescriptor = OutputField(
        description="List of items requiring collection action"
    )
    summary: FieldDescriptor = OutputField(
        description="Summary counts for billing, collections, and overdue items"
    )
    aging_buckets: FieldDescriptor = OutputField(
        description="Aging bucket breakdown (Current, 1-30, 31-60, 61-90, 90+ days)"
    )
    payment_terms: FieldDescriptor = OutputField(
        description="Harmonized payment terms for customer"
    )
    total_outstanding: FieldDescriptor = OutputField(
        description="Total outstanding amount across all items"
    )
    tool_calls: FieldDescriptor = OutputField(
        description="Next tools to call (empty when task is complete)",
        default=[],
    )


# =============================================================================
# Signature Registry
# =============================================================================


class SignatureRegistry:
    """
    Registry of all available agent signatures.

    Used for A2A routing to find agents by capability.

    Intelligence Domain (4 agents):
    - IndustryIntelSignature: Market opportunities, fleet, news
    - CompetitorIntelSignature: Competitive analysis, win/loss
    - ProductIntelSignature: Product specs, fit analysis
    - KYPSignature: Due diligence, risk assessment

    Order Processing Domain (4 agents):
    - OpportunitySignature: CEC + IPAS data extraction
    - DataManagementSignature: Assist with MS5 data entry
    - FinancialOpsSignature: Draft order creation in MS5
    - BillingCollectionsSignature: AR/billing/collections tracking

    Infrastructure:
    - CustomerMatcherSignature: Entity resolution
    - WebSearchSignature: Real-time search tool
    """

    _signatures: dict[str, type[AgentSignature]] = {}

    @classmethod
    def register(
        cls, signature_class: type[AgentSignature], name: Optional[str] = None
    ) -> type[AgentSignature]:
        """
        Register a signature class.

        Can be used as a decorator:
            @SignatureRegistry.register
            class MySignature(AgentSignature):
                ...

        Or with explicit name for aliases:
            SignatureRegistry.register(IndustryIntelSignature, "MarineIntelSignature")

        Args:
            signature_class: The signature class to register
            name: Optional explicit name (defaults to class __name__)
        """
        registration_name = name if name else signature_class.__name__
        cls._signatures[registration_name] = signature_class
        return signature_class

    @classmethod
    def register_alias(cls, alias_name: str, target_name: str) -> None:
        """
        Register an alias for an existing signature.

        Args:
            alias_name: The alias name to register
            target_name: The canonical signature name to alias

        Raises:
            KeyError: If target signature is not registered
        """
        target = cls._signatures.get(target_name)
        if target is None:
            raise KeyError(f"Cannot create alias: {target_name} not registered")
        cls._signatures[alias_name] = target

    @classmethod
    def get(cls, name: str) -> Optional[type[AgentSignature]]:
        """Get a signature by name."""
        return cls._signatures.get(name)

    @classmethod
    def all(cls) -> dict[str, type[AgentSignature]]:
        """Get all registered signatures."""
        return cls._signatures.copy()

    @classmethod
    def find_by_capability(cls, capability: str) -> list[type[AgentSignature]]:
        """
        Find signatures that have a given capability.

        Args:
            capability: Capability keyword to search for

        Returns:
            List of signature classes with matching capability
        """
        matches = []
        capability_lower = capability.lower()

        for sig_class in cls._signatures.values():
            capabilities = sig_class.get_capabilities()
            if any(capability_lower in cap.lower() for cap in capabilities):
                matches.append(sig_class)

        return matches

    @classmethod
    def get_intelligence_agents(cls) -> list[type[AgentSignature]]:
        """Get the four intelligence domain signatures."""
        return [
            cls._signatures.get("IndustryIntelSignature"),
            cls._signatures.get("CompetitorIntelSignature"),
            cls._signatures.get("ProductIntelSignature"),
            cls._signatures.get("KYPSignature"),
        ]

    @classmethod
    def get_order_processing_agents(cls) -> list[type[AgentSignature]]:
        """Get the four order processing domain signatures."""
        return [
            cls._signatures.get("OpportunitySignature"),
            cls._signatures.get("DataManagementSignature"),
            cls._signatures.get("FinancialOpsSignature"),
            cls._signatures.get("BillingCollectionsSignature"),
        ]


# =============================================================================
# Register all signatures
# =============================================================================

# Intelligence Domain (4 agents)
SignatureRegistry.register(IndustryIntelSignature)
SignatureRegistry.register(CompetitorIntelSignature)
SignatureRegistry.register(ProductIntelSignature)
SignatureRegistry.register(KYPSignature)

# Order Processing Domain (4 agents)
SignatureRegistry.register(OpportunitySignature)
SignatureRegistry.register(DataManagementSignature)
SignatureRegistry.register(FinancialOpsSignature)
SignatureRegistry.register(BillingCollectionsSignature)

# Infrastructure
SignatureRegistry.register(CustomerMatcherSignature)
SignatureRegistry.register(WebSearchSignature)

# Backward compatibility aliases (use explicit names since these are Python aliases)
SignatureRegistry.register_alias("MarineIntelSignature", "IndustryIntelSignature")
SignatureRegistry.register_alias("KnowledgeBaseSignature", "ProductIntelSignature")
