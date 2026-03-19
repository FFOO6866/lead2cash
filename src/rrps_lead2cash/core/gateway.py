"""
Main gateway orchestrator for the RRPS Lead-to-Cash application.

This module contains the main gateway implementation using FastAPI
to serve Kailash SDK workflows with health checks, monitoring,
and customer validation (KYP/Aravo + SAP two-tier).
"""

import os
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request, Depends, Security
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from contextlib import asynccontextmanager

from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

from .models import TwoTierValidationRequest, CustomerValidationRequest
from ..services.aravo_kyp_client import AravoError
from ..services.validation_service import ValidationService
from ..services.ipas_xml_parser import IPASXMLParser
from ..services.finops_simulator import FinOpsSimulator
from ..services.sap_cpi_client import SAPCPIClient, SAPCPIError
from ..services.entity_registry import EntityRegistry

# API Key security
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Verify the X-API-Key header against NEXUS_API_KEY."""
    expected = os.getenv("NEXUS_API_KEY", "")
    if not expected:
        # No key configured — allow access (development mode)
        return "dev"
    if not api_key or api_key != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global runtime instance
runtime = None
validation_service: Optional[ValidationService] = None
ipas_parser: Optional[IPASXMLParser] = None
finops: Optional[FinOpsSimulator] = None
cpi_client: Optional[SAPCPIClient] = None
entity_registry: Optional[EntityRegistry] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global runtime, validation_service, ipas_parser, finops, cpi_client, entity_registry

    # Startup
    logger.info("Starting RRPS Lead-to-Cash Gateway")
    runtime = LocalRuntime()
    validation_service = ValidationService()
    ipas_parser = IPASXMLParser()
    ipas_count = ipas_parser.load_all()
    finops = FinOpsSimulator()
    cpi_client = SAPCPIClient()
    entity_registry = EntityRegistry()
    logger.info(
        "Services initialized: IPAS(%d orders), FinOps, CPI(configured=%s), EntityRegistry(%d customers)",
        ipas_count, cpi_client.is_configured, len(entity_registry.list_customers()),
    )

    yield

    # Shutdown
    logger.info("Shutting down RRPS Lead-to-Cash Gateway")
    runtime = None
    validation_service = None
    ipas_parser = None
    finops = None
    cpi_client = None
    entity_registry = None

# Create FastAPI app
app = FastAPI(
    title="lead_to_cash",
    description="RRPS Lead-to-Cash POV - Multi-Agent SAP Integration Platform",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def create_sample_workflow() -> WorkflowBuilder:
    """Create a sample workflow for testing"""
    workflow = WorkflowBuilder()
    
    # Add a simple status check workflow
    workflow.add_node(
        "PythonCodeNode", 
        "status_check",
        {
            "code": """
import time
import os

result = {
    "status": "healthy",
    "timestamp": time.time(),
    "environment": os.getenv("ENVIRONMENT", "development"),
    "message": "Kailash SDK Template is running successfully"
}
"""
        }
    )
    
    return workflow

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "RRPS Lead-to-Cash Gateway",
        "version": "0.1.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "rrps-lead-to-cash",
        "environment": os.getenv("ENVIRONMENT", "development")
    }

@app.post("/workflows/{workflow_name}/execute")
async def execute_workflow(workflow_name: str, request: Request):
    """Execute a workflow by name"""
    global runtime
    
    if runtime is None:
        raise HTTPException(status_code=500, detail="Runtime not initialized")
    
    try:
        # Get request body
        request_body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        
        # For demo purposes, we'll handle a few sample workflows
        if workflow_name == "get_status":
            workflow = create_sample_workflow()
            results, run_id = runtime.execute(workflow.build(), **request_body)
            
            return {
                "workflow": workflow_name,
                "run_id": run_id,
                "results": results,
                "status": "completed"
            }
        else:
            # For other workflows, return a placeholder response
            return {
                "workflow": workflow_name,
                "message": f"Workflow '{workflow_name}' is not implemented yet",
                "status": "placeholder",
                "available_workflows": ["get_status"]
            }
            
    except Exception as e:
        logger.error(f"Error executing workflow {workflow_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workflows")
async def list_workflows():
    """List available workflows"""
    return {
        "workflows": [
            {
                "name": "get_status",
                "description": "Get application status and health information",
                "endpoint": "/workflows/get_status/execute"
            }
        ]
    }

@app.get("/metrics")
async def metrics():
    """Metrics endpoint for Prometheus"""
    from ..config import config

    ipas_summary = ipas_parser.get_summary() if ipas_parser else None

    return {
        "app_info": {
            "name": "lead_to_cash",
            "version": "0.1.0",
            "environment": os.getenv("ENVIRONMENT", "development")
        },
        "runtime_info": {
            "runtime_active": runtime is not None,
        },
        "integrations": {
            "cpi": cpi_client.is_configured if cpi_client else False,
            "aravo": bool(config.aravo_auth_token and config.aravo_report_id),
            "ipas_xml": {
                "configured": bool(config.ipas_xml_dir),
                "orders_loaded": ipas_summary.total_orders if ipas_summary else 0,
            },
            "finops": True,
        }
    }


# ============================================================================
# Validation Routes (KYP / Two-Tier)
# ============================================================================

@app.get("/api/v1/validation/kyp/{customer_name}")
async def get_kyp_assessment(customer_name: str, _key: str = Depends(verify_api_key)):
    """
    Get KYP compliance assessment for a customer (Tier 1 only).

    Path parameter:
        customer_name: Customer/partner name

    Returns KYP risk assessment including:
    - Risk rating (Low, Medium, High, Very High)
    - Approval status
    - Issues and conditions
    """
    if validation_service is None:
        raise HTTPException(status_code=503, detail="Validation service not initialized")

    try:
        assessment = validation_service.get_kyp_assessment(customer_name)
        return assessment.model_dump()
    except AravoError as exc:
        logger.error("KYP assessment failed for '%s': %s", customer_name, exc)
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/api/v1/validation/validate")
async def validate_customer_two_tier(request: TwoTierValidationRequest, _key: str = Depends(verify_api_key)):
    """
    Perform comprehensive two-tier customer validation.

    Combines:
    - Tier 1: KYP Compliance Assessment (external due diligence)
    - Tier 2: SAP/ECC Validation (transactional due diligence)

    Request body:
    {
        "customer": "BatamFast",
        "order_value": 50000.0
    }

    Response includes:
    - Overall status (APPROVED, CONDITIONAL, BLOCKED, PENDING)
    - Tier 1 KYP results (risk rating, compliance status)
    - Tier 2 SAP results (master data, credit, payment terms)
    - Combined issues and conditions
    """
    if validation_service is None:
        raise HTTPException(status_code=503, detail="Validation service not initialized")

    try:
        result = validation_service.validate_customer(
            customer=request.customer,
            order_value=request.order_value,
        )
        return result.model_dump()
    except AravoError as exc:
        logger.error("Two-tier validation failed for '%s': %s", request.customer, exc)
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/v1/validation/customers")
async def list_validation_customers(_key: str = Depends(verify_api_key)):
    """
    List available customers for validation.
    Returns customers from the Aravo KYP report.
    """
    if validation_service is None:
        raise HTTPException(status_code=503, detail="Validation service not initialized")

    try:
        customers = validation_service.list_customers()
        return {"customers": customers, "count": len(customers)}
    except AravoError as exc:
        logger.error("Failed to list validation customers: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/api/v1/agents/due-diligence/validate")
async def validate_customer_dd(request: CustomerValidationRequest, _key: str = Depends(verify_api_key)):
    """
    Validate customer using Due Diligence agent.

    Example request body:
    {
        "customer_id": "1234567",
        "order_value": 50000.0,
        "sales_org": "US01"
    }
    """
    if validation_service is None:
        raise HTTPException(status_code=503, detail="Validation service not initialized")

    try:
        result = validation_service.validate_customer(
            customer=request.customer_id,
            order_value=request.order_value,
        )
        return result.model_dump()
    except AravoError as exc:
        logger.error("DD validation failed for '%s': %s", request.customer_id, exc)
        raise HTTPException(status_code=502, detail=str(exc))


# ============================================================================
# IPAS Routes (XML-sourced order data for MS5 entry)
# ============================================================================

@app.get("/api/v1/ipas/summary")
async def ipas_summary(_key: str = Depends(verify_api_key)):
    """
    Get summary of all IPAS pending orders.

    Returns count of XML files, total engines, total value.
    """
    if ipas_parser is None:
        raise HTTPException(status_code=503, detail="IPAS parser not initialized")
    return ipas_parser.get_summary().model_dump()


@app.get("/api/v1/ipas/orders")
async def ipas_list_orders(_key: str = Depends(verify_api_key)):
    """
    List all IPAS pending orders parsed from XML files.

    Returns structured order data for MS5 entry.
    """
    if ipas_parser is None:
        raise HTTPException(status_code=503, detail="IPAS parser not initialized")
    orders = ipas_parser.get_all_orders()
    return {
        "orders": [order.model_dump() for order in orders],
        "count": len(orders),
    }


@app.get("/api/v1/ipas/orders/{order_id}")
async def ipas_get_order(order_id: str, _key: str = Depends(verify_api_key)):
    """
    Get a single IPAS order by order number.

    Returns full order detail including header, engines, BOM items,
    and partner information — structured for MS5 SAP order creation.
    """
    if ipas_parser is None:
        raise HTTPException(status_code=503, detail="IPAS parser not initialized")
    order = ipas_parser.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"IPAS order {order_id} not found")
    return order.model_dump()


@app.post("/api/v1/ipas/reload")
async def ipas_reload(_key: str = Depends(verify_api_key)):
    """
    Force reload all IPAS XML files from the configured directory.
    """
    if ipas_parser is None:
        raise HTTPException(status_code=503, detail="IPAS parser not initialized")
    count = ipas_parser.reload()
    return {"reloaded": count, "message": f"Reloaded {count} IPAS orders"}


# ============================================================================
# Entity Registry (Customer Resolution)
# ============================================================================

@app.get("/api/v1/customers/resolve/{query}")
async def resolve_customer(query: str, _key: str = Depends(verify_api_key)):
    """
    Resolve a customer name, alias, or ID to a full customer record.

    Supports: exact name, alias, partial, fuzzy, SAP ID (with/without leading zeros).
    """
    if entity_registry is None:
        raise HTTPException(status_code=503, detail="Entity registry not initialized")
    result = entity_registry.resolve(query)
    if result is None:
        suggestions = entity_registry.search(query, top_n=3)
        return {
            "matched": False,
            "query": query,
            "suggestions": [
                {"score": round(s, 2), "customer_id": c["customer_id"], "name": c["name"]}
                for s, c in suggestions
            ],
        }
    return {"matched": True, "query": query, **result}


@app.get("/api/v1/customers")
async def list_customers(_key: str = Depends(verify_api_key)):
    """List all known customers in the entity registry."""
    if entity_registry is None:
        raise HTTPException(status_code=503, detail="Entity registry not initialized")
    customers = entity_registry.list_customers()
    return {"customers": customers, "count": len(customers)}


# ============================================================================
# Unified Customer Lookup (aggregates ALL sources for a customer)
# ============================================================================

@app.get("/api/v1/customer/{query}/full")
async def customer_full_lookup(query: str, _key: str = Depends(verify_api_key)):
    """
    Full customer intelligence lookup — aggregates ALL data sources.

    This is the endpoint the chat agent should call when asked about a customer.
    Resolves customer name -> SAP ID, then pulls from every available source:
    - Credit check (real SAP CPI)
    - Opportunities (real SAP CPI)
    - KYP compliance (real Aravo)
    - IPAS pending orders (local XML)
    - Financial status (CPI simulator)
    """
    if entity_registry is None:
        raise HTTPException(status_code=503, detail="Services not initialized")

    # Step 1: Resolve customer
    customer = entity_registry.resolve(query)
    if customer is None:
        suggestions = entity_registry.search(query, top_n=3)
        return JSONResponse(status_code=404, content={
            "matched": False,
            "query": query,
            "message": f"Customer '{query}' not found",
            "suggestions": [{"name": c["name"], "id": c["customer_id"]} for _, c in suggestions],
        })

    cid = customer["customer_id"]
    result = {
        "customer": customer,
        "credit": None,
        "opportunities": None,
        "kyp": None,
        "ipas_orders": [],
        "financial": None,
        "data_sources": {},
    }

    # Step 2: Credit check (real SAP CPI)
    if cpi_client and cpi_client.is_configured:
        try:
            result["credit"] = cpi_client.get_credit_check(cid)
            result["data_sources"]["credit"] = "SAP_CPI"
        except SAPCPIError as exc:
            result["credit"] = {"error": str(exc), "source": "SAP_CPI"}
            result["data_sources"]["credit"] = "SAP_CPI_ERROR"
    else:
        result["data_sources"]["credit"] = "NOT_CONFIGURED"

    # Step 3: Opportunities (real SAP CPI)
    if cpi_client and cpi_client.is_configured:
        try:
            result["opportunities"] = cpi_client.get_opportunities(cid)
            result["data_sources"]["opportunities"] = "SAP_CPI"
        except SAPCPIError as exc:
            result["opportunities"] = {"error": str(exc), "source": "SAP_CPI"}
            result["data_sources"]["opportunities"] = "SAP_CPI_ERROR"
    else:
        result["data_sources"]["opportunities"] = "NOT_CONFIGURED"

    # Step 4: KYP compliance (real Aravo)
    if validation_service:
        try:
            kyp = validation_service.get_kyp_assessment(customer["name"])
            result["kyp"] = kyp.model_dump()
            result["data_sources"]["kyp"] = "ARAVO"
        except AravoError as exc:
            result["kyp"] = {"error": str(exc)}
            result["data_sources"]["kyp"] = "ARAVO_ERROR"

    # Step 5: IPAS pending orders (local XML)
    if ipas_parser:
        all_orders = ipas_parser.get_all_orders()
        cid_padded = cid.zfill(10)
        matching = [
            o.model_dump() for o in all_orders
            if o.header.sold_to_party.zfill(10) == cid_padded
        ]
        result["ipas_orders"] = matching
        result["data_sources"]["ipas"] = f"XML ({len(matching)} orders)"

    # Step 6: Financial status (CPI simulator)
    if finops:
        fin_summary = finops.get_financial_summary(cid)
        if fin_summary:
            result["financial"] = fin_summary.model_dump()
            result["data_sources"]["financial"] = "CPI_SIMULATOR"
        else:
            result["data_sources"]["financial"] = "NO_DATA"

    return result


# ============================================================================
# SAP CPI Routes (Credit Check + Opportunity — Real SAP)
# ============================================================================

@app.get("/api/v1/cpi/credit/{customer_id}")
async def cpi_credit_check(customer_id: str, cca: str = "0111", _key: str = Depends(verify_api_key)):
    """
    Get credit limit and exposure from SAP via CPI.

    Source: Real SAP CPI (BAPI_CR_ACC_GETDETAIL).
    """
    if cpi_client is None or not cpi_client.is_configured:
        raise HTTPException(status_code=503, detail="SAP CPI not configured")
    try:
        result = cpi_client.get_credit_check(customer_id, credit_control_area=cca)
        return result
    except SAPCPIError as exc:
        logger.error("CPI credit check failed for %s: %s", customer_id, exc)
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/v1/cpi/opportunities/{customer_id}")
async def cpi_opportunities(customer_id: str, _key: str = Depends(verify_api_key)):
    """
    Get CEC opportunities for a customer from SAP via CPI.

    Source: Real SAP CPI (Integrum/GetOpportunity).
    """
    if cpi_client is None or not cpi_client.is_configured:
        raise HTTPException(status_code=503, detail="SAP CPI not configured")
    try:
        result = cpi_client.get_opportunities(customer_id)
        return result
    except SAPCPIError as exc:
        logger.error("CPI opportunity lookup failed for %s: %s", customer_id, exc)
        raise HTTPException(status_code=502, detail=str(exc))


# ============================================================================
# FinOps Routes (Billing, Collections, Aging — CPI Simulator)
# ============================================================================

@app.get("/api/v1/finops/billing/{sales_order}")
async def finops_billing_status(sales_order: str, _key: str = Depends(verify_api_key)):
    """
    Get billing and down payment status for a sales order.

    Source: CPI_SIMULATOR (SAP BKPF/BSEG reference data).
    """
    if finops is None:
        raise HTTPException(status_code=503, detail="FinOps service not initialized")
    result = finops.get_billing_status(sales_order)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No billing data for sales order {sales_order}")
    return result.model_dump()


@app.get("/api/v1/finops/aging/{customer_id}")
async def finops_aging(customer_id: str, _key: str = Depends(verify_api_key)):
    """
    Get receivables aging analysis for a customer.

    Aging buckets: CURRENT, 1-30, 31-60, 61-90, 90+.
    Source: CPI_SIMULATOR.
    """
    if finops is None:
        raise HTTPException(status_code=503, detail="FinOps service not initialized")
    result = finops.get_aging_analysis(customer_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No aging data for customer {customer_id}")
    return result.model_dump()


@app.get("/api/v1/finops/summary/{customer_id}")
async def finops_financial_summary(customer_id: str, _key: str = Depends(verify_api_key)):
    """
    Get complete financial summary for a customer.

    Includes all orders, billing/collection status, down payments,
    and receivables aging. Source: CPI_SIMULATOR.
    """
    if finops is None:
        raise HTTPException(status_code=503, detail="FinOps service not initialized")
    result = finops.get_financial_summary(customer_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No financial data for customer {customer_id}")
    return result.model_dump()


@app.get("/api/v1/finops/customers")
async def finops_list_customers(_key: str = Depends(verify_api_key)):
    """
    List customers with financial data in the simulator.
    Source: CPI_SIMULATOR.
    """
    if finops is None:
        raise HTTPException(status_code=503, detail="FinOps service not initialized")
    customers = finops.list_customers()
    return {"customers": customers, "count": len(customers), "source": "CPI_SIMULATOR"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )