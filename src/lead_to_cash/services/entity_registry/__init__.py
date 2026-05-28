"""
Entity Registry Service

Unified entity resolution for KYP company matching.
Replaces hardcoded lookup tables with a dynamic database-backed system.

Features:
- Multi-strategy entity matching (exact, fuzzy, semantic)
- External source integration (ACRA, GLEIF, OpenCorporates)
- Inline user confirmation flow
- Persistent storage of confirmed entities

Usage:
    from lead_to_cash.services.entity_registry import (
        EntityResolutionService,
        ResolutionStatus,
        EntityCandidate,
    )

    service = EntityResolutionService()
    await service.initialize()

    result = await service.resolve("ST Engineering")

    if result.status == ResolutionStatus.EXACT_MATCH:
        entity = result.exact_match
    elif result.status == ResolutionStatus.CONFIRMATION_REQUIRED:
        # Present candidates to user
        for c in result.candidates:
            print(f"{c.rank}. {c.canonical_name} ({c.confidence_score}%)")
"""

from lead_to_cash.services.entity_registry.database import (
    EntityRegistryDatabase,
)
from lead_to_cash.services.entity_registry.entity_resolution_service import (
    EntityResolutionService,
)
from lead_to_cash.services.entity_registry.models import (
    Entity,
    EntityAlias,
    EntityCandidate,
    EntityExternalMapping,
    EntitySourceType,
    ResolutionResult,
    ResolutionStatus,
    VerificationStatus,
)

__all__ = [
    # Models
    "Entity",
    "EntityAlias",
    "EntityCandidate",
    "EntityExternalMapping",
    "ResolutionResult",
    "ResolutionStatus",
    "VerificationStatus",
    "EntitySourceType",
    # Services
    "EntityResolutionService",
    "EntityRegistryDatabase",
]
