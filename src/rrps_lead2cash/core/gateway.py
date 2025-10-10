"""
Main gateway orchestrator for the Kailash SDK Template application.

This module contains the main gateway implementation using FastAPI
to serve Kailash SDK workflows with health checks and monitoring.
"""

import os
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global runtime instance
runtime = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global runtime
    
    # Startup
    logger.info("Starting Kailash SDK Template Gateway")
    runtime = LocalRuntime()
    logger.info("LocalRuntime initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Kailash SDK Template Gateway")
    runtime = None

# Create FastAPI app
app = FastAPI(
    title="Kailash SDK Template",
    description="Enterprise-grade deployment template for Kailash SDK applications",
    version="1.0.0",
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
        "message": "Kailash SDK Template Gateway",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "kailash-sdk-template",
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
    # Basic metrics - in production, you'd use proper Prometheus metrics
    return {
        "app_info": {
            "name": "kailash_sdk_template",
            "version": "1.0.0",
            "environment": os.getenv("ENVIRONMENT", "development")
        },
        "runtime_info": {
            "runtime_active": runtime is not None,
            "python_version": platform.python_version() if 'platform' in globals() else "unknown"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )