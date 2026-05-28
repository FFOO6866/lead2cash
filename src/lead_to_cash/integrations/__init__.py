"""
SAP Integration Module

Provides connectivity to SAP systems:
- CPI (Cloud Platform Integration)
- MS5 (S/4HANA)
- CEC (Customer Engagement Center)
- IPAS (Intelligent Product Advisor System)

Third-Party Risk Management:
- Aravo (TPRM Platform)

For development/testing, use CPISimulator/AravoSimulator for mock responses.

Client Factory:
- get_cpi_client(): Returns real CPIClient if configured, CPISimulator otherwise
- get_aravo_client(): Returns real AravoClient if configured, AravoSimulator otherwise
"""

from lead_to_cash.integrations.aravo_client import AravoClient
from lead_to_cash.integrations.aravo_simulator import AravoSimulator
from lead_to_cash.integrations.cec_client import CECClient
from lead_to_cash.integrations.client_factory import get_aravo_client, get_cpi_client
from lead_to_cash.integrations.cpi_client import CPIClient
from lead_to_cash.integrations.cpi_simulator import CPISimulator
from lead_to_cash.integrations.ipas_client import IPASClient
from lead_to_cash.integrations.ms5_client import MS5Client

__all__ = [
    "AravoClient",
    "AravoSimulator",
    "CPIClient",
    "CPISimulator",
    "MS5Client",
    "CECClient",
    "IPASClient",
    # Factory functions
    "get_cpi_client",
    "get_aravo_client",
]
