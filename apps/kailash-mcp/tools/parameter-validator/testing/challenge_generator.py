"""
Challenge dataset generator for A/B testing MCP Parameter Validation Tool.
Creates realistic workflow challenges without lookahead bias.
"""

import json
import random
from pathlib import Path
from typing import Any, Dict, List


class WorkflowChallengeGenerator:
    """Generate realistic workflow challenges for unbiased testing."""

    def __init__(self):
        """Initialize with challenge templates and patterns."""
        self.node_types = [
            "LLMAgentNode",
            "HTTPRequestNode",
            "CSVReaderNode",
            "JSONReaderNode",
            "DataProcessorNode",
            "DatabaseQueryNode",
            "EmailSenderNode",
            "FileWriterNode",
            "WebScraperNode",
            "ImageProcessorNode",
            "SentimentAnalysisNode",
            "TranslationNode",
            "SummarizerNode",
        ]

        self.common_errors = [
            "missing_imports",
            "wrong_connection_syntax",
            "missing_parameters",
            "incorrect_parameter_types",
            "deprecated_patterns",
            "no_error_handling",
            "import_order_issues",
            "unused_imports",
            "relative_imports",
        ]

        self.complexity_patterns = {
            "linear": {"nodes": (2, 4), "connections": "sequential"},
            "parallel": {"nodes": (4, 8), "connections": "branching"},
            "cyclic": {"nodes": (3, 6), "connections": "feedback_loops"},
            "hybrid": {"nodes": (8, 15), "connections": "mixed_patterns"},
        }

    def generate_challenge_dataset(
        self, num_challenges: int = 80
    ) -> List[Dict[str, Any]]:
        """Generate a complete challenge dataset."""
        challenges = []

        # Distribute challenges across difficulty levels
        per_level = num_challenges // 4

        for level in range(1, 5):
            for i in range(per_level):
                challenge = self._generate_single_challenge(
                    level=level, challenge_id=f"WF{level:01d}{i+1:02d}"
                )
                challenges.append(challenge)

        # Add remaining challenges if not evenly divisible
        remaining = num_challenges - len(challenges)
        for i in range(remaining):
            level = random.randint(1, 4)
            challenge = self._generate_single_challenge(
                level=level, challenge_id=f"WF{level:01d}{len(challenges)+1:02d}"
            )
            challenges.append(challenge)

        return challenges

    def _generate_single_challenge(
        self, level: int, challenge_id: str
    ) -> Dict[str, Any]:
        """Generate a single workflow challenge."""
        # Select complexity pattern based on level
        if level == 1:
            pattern = "linear"
            num_errors = random.randint(1, 2)
        elif level == 2:
            pattern = random.choice(["linear", "parallel"])
            num_errors = random.randint(2, 3)
        elif level == 3:
            pattern = random.choice(["parallel", "cyclic"])
            num_errors = random.randint(3, 4)
        else:  # level 4
            pattern = random.choice(["cyclic", "hybrid"])
            num_errors = random.randint(4, 6)

        # Generate challenge components
        domain = self._select_domain()
        title = self._generate_title(domain, pattern)
        description = self._generate_description(domain, pattern, level)
        requirements = self._generate_requirements(domain, pattern, level)
        constraints = self._generate_constraints(level)
        success_criteria = self._generate_success_criteria(level)
        planted_errors = self._select_planted_errors(num_errors)

        return {
            "challenge_id": challenge_id,
            "level": level,
            "pattern": pattern,
            "domain": domain,
            "title": title,
            "description": description,
            "requirements": requirements,
            "constraints": constraints,
            "success_criteria": success_criteria,
            "planted_errors": planted_errors,
            "estimated_nodes": self.complexity_patterns[pattern]["nodes"],
            "metadata": {
                "created_for_testing": True,
                "bias_free": True,
                "difficulty_level": level,
                "expected_duration_minutes": 10 + (level * 5),
            },
        }

    def _select_domain(self) -> str:
        """Select application domain for the challenge."""
        domains = [
            "data_processing",
            "content_analysis",
            "api_integration",
            "document_workflow",
            "monitoring_system",
            "data_pipeline",
            "customer_service",
            "financial_analysis",
            "inventory_management",
            "social_media",
            "research_automation",
            "compliance_checking",
        ]
        return random.choice(domains)

    def _generate_title(self, domain: str, pattern: str) -> str:
        """Generate descriptive title for the challenge."""
        domain_titles = {
            "data_processing": [
                "Data Validation Pipeline",
                "ETL Workflow",
                "Data Quality Monitor",
            ],
            "content_analysis": [
                "Content Moderation System",
                "Text Analysis Pipeline",
                "Document Classifier",
            ],
            "api_integration": [
                "Multi-API Orchestrator",
                "Service Integration Hub",
                "API Response Aggregator",
            ],
            "document_workflow": [
                "Document Processing Chain",
                "PDF Analysis Pipeline",
                "Report Generator",
            ],
            "monitoring_system": [
                "System Health Monitor",
                "Alert Processing System",
                "Performance Tracker",
            ],
            "data_pipeline": [
                "Real-time Data Stream",
                "Batch Processing Pipeline",
                "Data Transformation",
            ],
            "customer_service": [
                "Support Ticket Router",
                "Customer Feedback Analyzer",
                "Response Automation",
            ],
            "financial_analysis": [
                "Portfolio Analyzer",
                "Risk Assessment System",
                "Transaction Processor",
            ],
            "inventory_management": [
                "Stock Level Monitor",
                "Reorder Point Calculator",
                "Supplier Communication",
            ],
            "social_media": [
                "Social Media Monitor",
                "Engagement Analyzer",
                "Content Scheduler",
            ],
            "research_automation": [
                "Literature Review System",
                "Data Collection Pipeline",
                "Analysis Automation",
            ],
            "compliance_checking": [
                "Compliance Validator",
                "Audit Trail Generator",
                "Regulatory Monitor",
            ],
        }

        titles = domain_titles.get(
            domain, ["Generic Workflow", "Process Automation", "System Integration"]
        )
        base_title = random.choice(titles)

        if pattern == "cyclic":
            base_title += " with Feedback Loop"
        elif pattern == "parallel":
            base_title += " with Parallel Processing"
        elif pattern == "hybrid":
            base_title += " - Advanced Integration"

        return base_title

    def _generate_description(self, domain: str, pattern: str, level: int) -> str:
        """Generate detailed description for the challenge."""
        descriptions = {
            "data_processing": f"Build a workflow that processes incoming data through validation, transformation, and output stages. The system should handle {self._get_complexity_adjective(level)} data volumes and ensure quality standards.",
            "content_analysis": f"Create a content analysis pipeline that processes text documents, performs sentiment analysis, and generates insights. Implement {self._get_complexity_adjective(level)} analysis techniques.",
            "api_integration": f"Develop an integration workflow that coordinates multiple external APIs, handles authentication, and manages response data. Design for {self._get_complexity_adjective(level)} integration scenarios.",
            "document_workflow": f"Build a document processing system that handles file ingestion, content extraction, and structured output generation. Support {self._get_complexity_adjective(level)} document types.",
            "monitoring_system": f"Create a monitoring workflow that collects system metrics, analyzes performance data, and triggers alerts when needed. Implement {self._get_complexity_adjective(level)} monitoring capabilities.",
            "data_pipeline": f"Design a data pipeline that ingests, processes, and stores information from multiple sources. Handle {self._get_complexity_adjective(level)} data transformation requirements.",
        }

        base_desc = descriptions.get(
            domain,
            f"Create a {self._get_complexity_adjective(level)} workflow system for automated processing and analysis.",
        )

        if pattern == "cyclic":
            base_desc += " Include iterative refinement based on quality feedback."
        elif pattern == "parallel":
            base_desc += " Optimize for concurrent processing of multiple data streams."
        elif pattern == "hybrid":
            base_desc += " Combine multiple processing patterns for maximum efficiency."

        return base_desc

    def _get_complexity_adjective(self, level: int) -> str:
        """Get complexity adjective based on difficulty level."""
        adjectives = {1: "simple", 2: "moderate", 3: "complex", 4: "enterprise-grade"}
        return adjectives[level]

    def _generate_requirements(
        self, domain: str, pattern: str, level: int
    ) -> List[str]:
        """Generate specific requirements for the challenge."""
        base_requirements = [
            "Use appropriate Kailash SDK nodes for the task",
            "Implement proper error handling for external dependencies",
            "Include logging and monitoring capabilities",
            "Ensure data validation at input and output stages",
        ]

        if level >= 2:
            base_requirements.extend(
                [
                    "Support configurable parameters for different environments",
                    "Implement retry logic for unreliable operations",
                ]
            )

        if level >= 3:
            base_requirements.extend(
                [
                    "Include performance optimization for large data volumes",
                    "Implement circuit breaker pattern for external services",
                    "Support parallel processing where applicable",
                ]
            )

        if level >= 4:
            base_requirements.extend(
                [
                    "Implement comprehensive audit logging",
                    "Support dynamic workflow reconfiguration",
                    "Include metrics collection and reporting",
                    "Ensure enterprise-grade reliability patterns",
                ]
            )

        if pattern == "cyclic":
            base_requirements.append(
                "Implement convergence criteria to avoid infinite loops"
            )

        return base_requirements

    def _generate_constraints(self, level: int) -> List[str]:
        """Generate constraints for the challenge."""
        constraints = ["Use LocalRuntime for execution"]

        if level <= 2:
            constraints.extend(
                [
                    "Maximum 8 nodes in the workflow",
                    "Use only standard Kailash SDK nodes",
                ]
            )
        elif level == 3:
            constraints.extend(
                [
                    "Maximum 12 nodes in the workflow",
                    "Include at least one cycle or parallel branch",
                ]
            )
        else:  # level 4
            constraints.extend(
                [
                    "Maximum 20 nodes in the workflow",
                    "Demonstrate enterprise architecture patterns",
                    "Include both cycles and parallel processing",
                ]
            )

        return constraints

    def _generate_success_criteria(self, level: int) -> Dict[str, List[str]]:
        """Generate success criteria for evaluation."""
        base_criteria = {
            "functional": [
                "Workflow executes without errors",
                "All nodes properly connected",
                "Expected output format produced",
            ],
            "code_quality": [
                "Proper import statements",
                "Correct parameter declarations",
                "No deprecated patterns used",
            ],
            "performance": ["Reasonable execution time", "Efficient resource usage"],
        }

        if level >= 2:
            base_criteria["code_quality"].extend(
                ["Error handling implemented", "Appropriate node types selected"]
            )

        if level >= 3:
            base_criteria["functional"].append(
                "Parallel processing utilized where beneficial"
            )
            base_criteria["performance"].append("Optimized for concurrent execution")

        if level >= 4:
            base_criteria["functional"].extend(
                ["Enterprise patterns demonstrated", "Comprehensive error recovery"]
            )
            base_criteria["code_quality"].extend(
                ["Production-ready code quality", "Proper documentation and comments"]
            )

        return base_criteria

    def _select_planted_errors(self, num_errors: int) -> List[Dict[str, str]]:
        """Select errors to plant in the challenge for testing detection."""
        available_errors = [
            {
                "type": "missing_imports",
                "description": "Required import statements missing",
                "detection_difficulty": "easy",
            },
            {
                "type": "wrong_connection_syntax",
                "description": "Using 2-parameter instead of 4-parameter connection syntax",
                "detection_difficulty": "easy",
            },
            {
                "type": "missing_parameters",
                "description": "Required node parameters not provided",
                "detection_difficulty": "medium",
            },
            {
                "type": "incorrect_parameter_types",
                "description": "Parameter values don't match expected types",
                "detection_difficulty": "medium",
            },
            {
                "type": "deprecated_patterns",
                "description": "Using cycle=True instead of CycleBuilder API",
                "detection_difficulty": "medium",
            },
            {
                "type": "no_error_handling",
                "description": "Missing error handling for external services",
                "detection_difficulty": "hard",
            },
            {
                "type": "import_order_issues",
                "description": "Imports not ordered according to PEP 8",
                "detection_difficulty": "easy",
            },
            {
                "type": "unused_imports",
                "description": "Imported modules not actually used",
                "detection_difficulty": "easy",
            },
            {
                "type": "relative_imports",
                "description": "Using relative instead of absolute imports",
                "detection_difficulty": "medium",
            },
        ]

        # Select errors with balanced difficulty distribution
        selected = random.sample(
            available_errors, min(num_errors, len(available_errors))
        )
        return selected

    def save_challenge_dataset(
        self, challenges: List[Dict[str, Any]], output_path: str
    ):
        """Save challenge dataset to JSON file."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        dataset = {
            "metadata": {
                "version": "1.0",
                "created_for": "MCP Parameter Validation Tool A/B Testing",
                "bias_free": True,
                "total_challenges": len(challenges),
                "levels_distribution": self._calculate_level_distribution(challenges),
            },
            "challenges": challenges,
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)

        print(f"Challenge dataset saved: {output_file}")
        print(f"Total challenges: {len(challenges)}")
        print(f"Distribution: {dataset['metadata']['levels_distribution']}")

    def _calculate_level_distribution(
        self, challenges: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Calculate distribution of challenges across difficulty levels."""
        distribution = {}
        for challenge in challenges:
            level = f"Level {challenge['level']}"
            distribution[level] = distribution.get(level, 0) + 1
        return distribution


def main():
    """Generate and save challenge dataset."""
    generator = WorkflowChallengeGenerator()

    # Generate challenge dataset
    challenges = generator.generate_challenge_dataset(num_challenges=80)

    # Save to file
    output_path = "testing/datasets/workflow_challenges.json"
    generator.save_challenge_dataset(challenges, output_path)

    # Generate a few sample challenges for preview
    print("\n=== Sample Challenges ===")
    for i, challenge in enumerate(challenges[:3]):
        print(f"\n--- Challenge {i+1} ---")
        print(f"ID: {challenge['challenge_id']}")
        print(f"Level: {challenge['level']} ({challenge['pattern']})")
        print(f"Title: {challenge['title']}")
        print(f"Domain: {challenge['domain']}")
        print(f"Description: {challenge['description']}")
        print(f"Requirements: {len(challenge['requirements'])} items")
        print(f"Planted Errors: {[e['type'] for e in challenge['planted_errors']]}")


if __name__ == "__main__":
    main()
