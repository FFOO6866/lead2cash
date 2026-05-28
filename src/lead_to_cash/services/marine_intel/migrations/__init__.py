"""
Database migrations for Marine Intelligence service.

Migrations should be run in order when upgrading existing deployments.
"""

from lead_to_cash.services.marine_intel.migrations.v001_add_embeddings_and_retention import (
    MIGRATION_DESCRIPTION as MIGRATION_001_DESC,
)
from lead_to_cash.services.marine_intel.migrations.v001_add_embeddings_and_retention import (
    MIGRATION_ID as MIGRATION_001_ID,
)
from lead_to_cash.services.marine_intel.migrations.v001_add_embeddings_and_retention import (
    rollback_migration as rollback_001,
)
from lead_to_cash.services.marine_intel.migrations.v001_add_embeddings_and_retention import (
    run_migration as run_001,
)

# List of all migrations in order
MIGRATIONS = [
    {
        "id": MIGRATION_001_ID,
        "description": MIGRATION_001_DESC,
        "run": run_001,
        "rollback": rollback_001,
    },
]

__all__ = [
    "MIGRATIONS",
    "run_001",
    "rollback_001",
]
