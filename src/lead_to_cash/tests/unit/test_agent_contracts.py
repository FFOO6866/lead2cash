"""
Unit Tests for Agent Contracts

Tests the AgentResponse typed contract system.
"""

from datetime import datetime

from lead_to_cash.agents.contracts import (
    AgentResponse,
    ClarificationQuestion,
    ConfidenceLevel,
    EntityCandidate,
    ResponseBuilder,
    ResponseType,
)


class TestResponseType:
    """Tests for ResponseType enum."""

    def test_response_type_values(self):
        """Test that response types match frontend expectations."""
        assert ResponseType.ANSWER.value == "answer"
        assert ResponseType.KYP_REPORT.value == "kyp_report"
        assert ResponseType.CLARIFICATION_NEEDED.value == "clarification_needed"
        assert (
            ResponseType.ENTITY_CONFIRMATION_NEEDED.value
            == "entity_confirmation_needed"
        )
        assert ResponseType.ERROR.value == "error"

    def test_response_type_is_string_enum(self):
        """Test that ResponseType values can be used as strings."""
        assert str(ResponseType.ANSWER) == "ResponseType.ANSWER"
        assert ResponseType.ANSWER.value == "answer"


class TestConfidenceLevel:
    """Tests for ConfidenceLevel enum."""

    def test_confidence_level_values(self):
        """Test confidence level values."""
        assert ConfidenceLevel.HIGH.value == "HIGH"
        assert ConfidenceLevel.MEDIUM.value == "MEDIUM"
        assert ConfidenceLevel.LOW.value == "LOW"


class TestClarificationQuestion:
    """Tests for ClarificationQuestion dataclass."""

    def test_basic_question(self):
        """Test creating a basic clarification question."""
        q = ClarificationQuestion(question="Which region?")
        assert q.question == "Which region?"
        assert q.options == []
        assert q.field_name == ""

    def test_question_with_options(self):
        """Test question with options."""
        q = ClarificationQuestion(
            question="Which region?",
            options=["APAC", "Europe", "Americas"],
            field_name="region",
        )
        assert q.options == ["APAC", "Europe", "Americas"]
        assert q.field_name == "region"

    def test_to_dict(self):
        """Test serialization to dict."""
        q = ClarificationQuestion(
            question="Which region?",
            options=["APAC", "Europe"],
            field_name="region",
        )
        d = q.to_dict()
        assert d["question"] == "Which region?"
        assert d["options"] == ["APAC", "Europe"]
        assert d["field_name"] == "region"

    def test_to_dict_minimal(self):
        """Test minimal serialization."""
        q = ClarificationQuestion(question="What?")
        d = q.to_dict()
        assert d == {"question": "What?"}


class TestEntityCandidate:
    """Tests for EntityCandidate dataclass."""

    def test_basic_candidate(self):
        """Test creating a basic entity candidate."""
        c = EntityCandidate(
            entity_id="123",
            name="ST Engineering",
            match_type="exact",
            confidence=1.0,
        )
        assert c.entity_id == "123"
        assert c.name == "ST Engineering"
        assert c.confidence == 1.0

    def test_candidate_with_metadata(self):
        """Test candidate with metadata."""
        c = EntityCandidate(
            entity_id="123",
            name="ST Engineering",
            match_type="fuzzy",
            confidence=0.85,
            metadata={"uen": "199706231H"},
        )
        assert c.metadata["uen"] == "199706231H"

    def test_to_dict(self):
        """Test serialization."""
        c = EntityCandidate(
            entity_id="123",
            name="Test",
            match_type="exact",
            confidence=1.0,
        )
        d = c.to_dict()
        assert d["entity_id"] == "123"
        assert d["name"] == "Test"
        assert d["match_type"] == "exact"
        assert d["confidence"] == 1.0


class TestAgentResponseAnswer:
    """Tests for AgentResponse with type=ANSWER."""

    def test_create_answer_response(self):
        """Test creating an answer response."""
        response = AgentResponse.create_answer(
            session_id="abc123",
            answer="The market shows growth.",
            sources=["Marine DB", "Perplexity"],
            confidence=ConfidenceLevel.HIGH,
        )
        assert response.type == ResponseType.ANSWER
        assert response.session_id == "abc123"
        assert response.answer == "The market shows growth."
        assert response.sources == ["Marine DB", "Perplexity"]
        assert response.confidence == ConfidenceLevel.HIGH

    def test_answer_to_dict(self):
        """Test answer serialization."""
        response = AgentResponse.create_answer(
            session_id="abc123",
            answer="Test answer",
            sources=["Source1"],
            confidence=ConfidenceLevel.MEDIUM,
            tools_used=["perplexity"],
            execution_time_ms=1500,
            follow_up_suggestions=["Ask more?"],
        )
        d = response.to_dict()

        assert d["type"] == "answer"
        assert d["session_id"] == "abc123"
        assert d["answer"] == "Test answer"
        assert d["sources"] == ["Source1"]
        assert d["confidence"] == "MEDIUM"
        assert d["tools_used"] == ["perplexity"]
        assert d["execution_time_ms"] == 1500
        assert d["follow_up_suggestions"] == ["Ask more?"]

    def test_answer_validation_valid(self):
        """Test validation passes for valid answer."""
        response = AgentResponse.create_answer(
            session_id="abc",
            answer="Valid answer",
        )
        assert response.is_valid()
        assert len(response.validate()) == 0

    def test_answer_validation_missing_answer(self):
        """Test validation fails without answer."""
        response = AgentResponse(
            type=ResponseType.ANSWER,
            session_id="abc",
            answer=None,
        )
        errors = response.validate()
        assert "answer is required for ANSWER type" in errors


class TestAgentResponseKYP:
    """Tests for AgentResponse with type=KYP_REPORT."""

    def test_create_kyp_response(self):
        """Test creating a KYP report response."""
        response = AgentResponse.kyp_report(
            session_id="abc123",
            entity_name="ST Engineering",
            sections=[{"id": "credit", "status": "PASSED"}],
            overall_status="PROCEED",
            can_proceed=True,
        )
        assert response.type == ResponseType.KYP_REPORT
        assert response.entity_name == "ST Engineering"
        assert response.overall_status == "PROCEED"
        assert response.can_proceed is True

    def test_kyp_to_dict(self):
        """Test KYP serialization."""
        response = AgentResponse.kyp_report(
            session_id="abc123",
            entity_name="Test Corp",
            sections=[{"id": "credit"}],
        )
        d = response.to_dict()

        assert d["type"] == "kyp_report"
        assert d["entity_name"] == "Test Corp"
        assert d["sections"] == [{"id": "credit"}]
        assert "report_date" in d

    def test_kyp_validation_missing_entity(self):
        """Test validation fails without entity_name."""
        response = AgentResponse(
            type=ResponseType.KYP_REPORT,
            session_id="abc",
            entity_name=None,
            sections=[],
        )
        errors = response.validate()
        assert "entity_name is required for KYP_REPORT type" in errors


class TestAgentResponseError:
    """Tests for AgentResponse with type=ERROR."""

    def test_create_error_response(self):
        """Test creating an error response."""
        response = AgentResponse.create_error(
            session_id="abc123",
            error="Connection failed",
        )
        assert response.type == ResponseType.ERROR
        assert response.error == "Connection failed"

    def test_error_to_dict(self):
        """Test error serialization."""
        response = AgentResponse.create_error(
            session_id="abc123",
            error="Test error",
        )
        d = response.to_dict()

        assert d["type"] == "error"
        assert d["error"] == "Test error"
        assert d["success"] is False

    def test_error_validation_missing_error(self):
        """Test validation fails without error message."""
        response = AgentResponse(
            type=ResponseType.ERROR,
            session_id="abc",
            error=None,
        )
        errors = response.validate()
        assert "error is required for ERROR type" in errors


class TestAgentResponseClarification:
    """Tests for AgentResponse with type=CLARIFICATION_NEEDED."""

    def test_create_clarification_response(self):
        """Test creating a clarification response."""
        questions = [
            ClarificationQuestion(question="Which region?", options=["APAC", "Europe"]),
        ]
        response = AgentResponse.clarification_needed(
            session_id="abc123",
            questions=questions,
            partial_understanding={"intent": "market_intel"},
        )
        assert response.type == ResponseType.CLARIFICATION_NEEDED
        assert len(response.questions) == 1

    def test_clarification_to_dict(self):
        """Test clarification serialization."""
        questions = [
            ClarificationQuestion(question="Region?", options=["A", "B"]),
        ]
        response = AgentResponse.clarification_needed(
            session_id="abc",
            questions=questions,
        )
        d = response.to_dict()

        assert d["type"] == "clarification_needed"
        assert len(d["questions"]) == 1
        assert d["questions"][0]["question"] == "Region?"


class TestAgentResponseEntityConfirmation:
    """Tests for AgentResponse with type=ENTITY_CONFIRMATION_NEEDED."""

    def test_create_entity_confirmation_response(self):
        """Test creating an entity confirmation response."""
        candidates = [
            EntityCandidate(
                entity_id="123",
                name="ST Engineering",
                match_type="exact",
                confidence=1.0,
            ),
            EntityCandidate(
                entity_id="456",
                name="ST Engineering Marine",
                match_type="fuzzy",
                confidence=0.85,
            ),
        ]
        response = AgentResponse.entity_confirmation_needed(
            session_id="abc123",
            message="Multiple matches found. Please select:",
            candidates=candidates,
            original_query="st engineering",
        )
        assert response.type == ResponseType.ENTITY_CONFIRMATION_NEEDED
        assert len(response.candidates) == 2

    def test_entity_confirmation_to_dict(self):
        """Test entity confirmation serialization."""
        candidates = [
            EntityCandidate(
                entity_id="1", name="Test", match_type="exact", confidence=1.0
            ),
        ]
        response = AgentResponse.entity_confirmation_needed(
            session_id="abc",
            message="Select one:",
            candidates=candidates,
        )
        d = response.to_dict()

        assert d["type"] == "entity_confirmation_needed"
        assert d["message"] == "Select one:"
        assert len(d["candidates"]) == 1


class TestResponseBuilder:
    """Tests for ResponseBuilder pattern."""

    def test_build_answer(self):
        """Test building an answer response."""
        response = (
            ResponseBuilder("session123")
            .as_answer()
            .with_answer("Test answer")
            .with_sources(["Source1", "Source2"])
            .with_confidence(ConfidenceLevel.HIGH)
            .with_tools(["perplexity", "sap"])
            .with_execution_time(2000)
            .with_follow_ups(["Follow up 1?"])
            .build()
        )

        assert response.type == ResponseType.ANSWER
        assert response.answer == "Test answer"
        assert response.sources == ["Source1", "Source2"]
        assert response.confidence == ConfidenceLevel.HIGH
        assert response.tools_used == ["perplexity", "sap"]
        assert response.execution_time_ms == 2000

    def test_build_error(self):
        """Test building an error response."""
        response = (
            ResponseBuilder("session123")
            .as_error()
            .with_error("Something went wrong")
            .build()
        )

        assert response.type == ResponseType.ERROR
        assert response.error == "Something went wrong"

    def test_build_kyp_report(self):
        """Test building a KYP report response."""
        response = (
            ResponseBuilder("session123")
            .as_kyp_report()
            .with_entity("Test Corp")
            .with_sections([{"id": "credit", "status": "PASSED"}])
            .with_sources(["SAP", "EODHD"])
            .build()
        )

        assert response.type == ResponseType.KYP_REPORT
        assert response.entity_name == "Test Corp"

    def test_build_clarification(self):
        """Test building a clarification response."""
        questions = [ClarificationQuestion(question="Which one?")]
        response = (
            ResponseBuilder("session123")
            .as_clarification()
            .with_questions(questions)
            .build()
        )

        assert response.type == ResponseType.CLARIFICATION_NEEDED
        assert len(response.questions) == 1


class TestResponseTimestamp:
    """Tests for response timestamp handling."""

    def test_timestamp_auto_generated(self):
        """Test that timestamp is auto-generated."""
        response = AgentResponse.create_answer(
            session_id="abc",
            answer="Test",
        )
        assert response.timestamp is not None
        # Should be ISO format
        datetime.fromisoformat(response.timestamp.replace("Z", "+00:00"))

    def test_timestamp_in_dict(self):
        """Test that timestamp appears in serialized dict."""
        response = AgentResponse.create_answer(
            session_id="abc",
            answer="Test",
        )
        d = response.to_dict()
        assert "timestamp" in d
