"""
Integration Client Factory

Provides factory functions for creating appropriate integration clients
based on configuration.

- CPI: Real client only — returns (None, False) when unavailable.
- Aravo: Real REST API first, falls back to AravoSimulator for demo.

Usage:
    from lead_to_cash.integrations.client_factory import get_cpi_client, get_aravo_client

    cpi_client, is_real = await get_cpi_client(use_case="CEC")
    if not cpi_client:
        # Handle: SAP CPI not available

    aravo_client, is_real = await get_aravo_client(use_case="KYP")
    if aravo_client and not is_real:
        # Using simulator — TPRM data is demo/mock
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def get_cpi_client(use_case: str = "general") -> tuple[Any, bool]:
    """Get CPI client. Returns (None, False) if unavailable.

    Returns:
        Tuple of (client_or_None, is_real_client)
    """
    from lead_to_cash.config import config

    if config.sap_cpi.client_id and config.sap_cpi.client_secret:
        try:
            from lead_to_cash.integrations.cpi_client import CPIClient

            cpi_client = CPIClient()
            await cpi_client.connect()
            logger.info(f"[{use_case}] Using REAL SAP CPI client (authenticated)")
            return cpi_client, True
        except Exception as e:
            logger.warning(
                f"[{use_case}] Real SAP CPI connection failed: {e}. "
                f"No simulator fallback — returning None"
            )
            return None, False
    else:
        logger.warning(f"[{use_case}] SAP CPI not configured — returning None")
        return None, False


async def get_aravo_client(use_case: str = "general") -> tuple[Any, bool]:
    """Get Aravo client — tries real REST API first, falls back to simulator.

    Connection priority:
    1. Real Aravo REST v5.0 (if configured and reachable)
    2. AravoSimulator (demo fallback for all 7 SAP customers)

    Returns:
        Tuple of (client_or_None, is_real).
        is_real=True for real Aravo, False for simulator.
    """
    from lead_to_cash.config import config

    if config.aravo.is_configured():
        try:
            from lead_to_cash.integrations.aravo_client import AravoClient

            aravo_client = AravoClient()
            await aravo_client.connect()
            logger.info(f"[{use_case}] Using REAL Aravo client (REST API)")
            return aravo_client, True
        except Exception as e:
            logger.warning(
                f"[{use_case}] Real Aravo REST failed: {e}. "
                f"Falling back to AravoSimulator."
            )

    # Fallback to simulator (covers all 7 SAP customers by name/alias/UEN)
    try:
        from lead_to_cash.integrations.aravo_simulator import AravoSimulator

        aravo_client = AravoSimulator()
        await aravo_client.connect()
        logger.info(f"[{use_case}] Using AravoSimulator (demo fallback)")
        return aravo_client, False
    except Exception as e:
        logger.warning(f"[{use_case}] AravoSimulator also failed: {e}")
        return None, False
