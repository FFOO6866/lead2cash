"""Generate Production Readiness Red Team Report as Word document."""

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn


def set_cell_shading(cell, color_hex):
    shading = cell._element.get_or_add_tcPr()
    shd = shading.makeelement(qn("w:shd"), {qn("w:fill"): color_hex, qn("w:val"): "clear"})
    shading.append(shd)


def add_table(doc, headers, rows, col_widths=None, header_color="2F5496"):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            for run in p.runs:
                run.bold = True
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_shading(cell, header_color)
    for r_idx, row_data in enumerate(rows):
        for c_idx, val in enumerate(row_data):
            cell = table.rows[r_idx + 1].cells[c_idx]
            cell.text = str(val)
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(9)
            if r_idx % 2 == 1:
                set_cell_shading(cell, "D6E4F0")
    if col_widths:
        for row in table.rows:
            for i, w in enumerate(col_widths):
                if i < len(row.cells):
                    row.cells[i].width = Cm(w)
    doc.add_paragraph("")
    return table


def add_verdict(doc, text, color_hex):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(
        int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
    )


def main():
    doc = Document()

    title = doc.add_heading("RRPS Lead-to-Cash: Production Readiness Red Team Report", level=0)
    title.runs[0].font.color.rgb = RGBColor(0x2F, 0x54, 0x96)

    doc.add_paragraph("Date: 2026-03-19")
    doc.add_paragraph("Scope: Requirements v5.0 (Epic 1 + Epic 2) vs Actual Implementation")

    # ════════════════════════════════════════════════════════════════════
    doc.add_heading("1. Overall Verdict", level=1)
    # ════════════════════════════════════════════════════════════════════

    add_verdict(doc, "VERDICT: NOT PRODUCTION-READY", "C00000")
    doc.add_paragraph(
        "The system has foundational components built but critical gaps remain. "
        "Production (rr.kailash.ai) runs a different, more mature codebase with 78 endpoints. "
        "The local repo implements core services (CPI, Aravo, IPAS, FinOps) but has not been merged "
        "into the production codebase. Several requirement stories have zero implementation."
    )

    add_table(doc,
        ["Area", "Status", "Readiness"],
        [
            ["Sprint 0: Infrastructure", "PARTIAL", "60%"],
            ["Epic 1: Opportunity Qualification", "PARTIAL", "30%"],
            ["Epic 2: Fast Order Creation", "NOT STARTED", "5%"],
            ["Production Deployment", "GAP", "Local code not merged into production"],
            ["UAT Readiness", "NOT READY", "0%"],
        ],
        col_widths=[6, 3, 8.5],
    )

    # ════════════════════════════════════════════════════════════════════
    doc.add_heading("2. Sprint 0: Infrastructure Setup", level=1)
    # ════════════════════════════════════════════════════════════════════

    add_table(doc,
        ["Checklist Item", "Required", "Actual", "Status"],
        [
            ["Kailash SDK installed", "Yes", "Installed on production server", "DONE"],
            ["PostgreSQL connection", "Yes", "Not verified in local repo", "UNKNOWN"],
            ["DataFlow alpha validation", "Yes", "No DataFlow code in repo", "NOT STARTED"],
            ["Nexus multi-channel test", "Yes", "No Nexus deployment code", "NOT STARTED"],
            ["CEC OData Client (TE-2)", "10 test opportunities", "GetOpportunity iFlow is a STUB\n(returns same 2 hardcoded opps for all customers)", "BLOCKED"],
            ["IPAS Client (TE-3)", "5 BOM retrievals via CPI", "Local XML parser built\n(not CPI-based as spec requires)", "PARTIAL\n(workaround)"],
            ["MS5 BAPI Client (TE-5)", "BAPI_SALESORDER_SIMULATE", "Not implemented", "NOT STARTED"],
            ["MS5 IDoc Client (TE-6)", "Submit ORDERS05", "Not implemented", "NOT STARTED"],
            ["Aravo KYP Client (TE-16)", "Connected + fuzzy match", "Client built and tested.\nIP-restricted: works from prod server only.\nProd env vars NOT set.", "PARTIAL"],
            ["Audit Store", "PostgreSQL tables", "No audit tables or DataFlow models", "NOT STARTED"],
        ],
        col_widths=[4, 3.5, 6.5, 3],
    )

    doc.add_heading("Sprint 0 Verdict", level=2)
    add_verdict(doc, "PROCEED WITH CAUTION", "ED7D31")
    doc.add_paragraph(
        "CPI credit check works. Aravo client is built but not deployed. "
        "IPAS has a local XML workaround. MS5 BAPI/IDoc, DataFlow, and Audit Store are missing entirely. "
        "CEC GetOpportunity iFlow is a stub on the SAP side."
    )

    # ════════════════════════════════════════════════════════════════════
    doc.add_heading("3. Epic 1: Opportunity Qualification", level=1)
    # ════════════════════════════════════════════════════════════════════

    add_table(doc,
        ["Story", "Requirement", "Implementation", "Status"],
        [
            ["1.1: Search Opportunities\nby Customer/Product",
             "Search CEC opportunities by customer name or product.\nPartial matching, <2s response.",
             "GET /api/v1/cpi/opportunities/{customer_id} calls SAP CPI.\n"
             "PROBLEM: iFlow is a STUB - returns same 2 hardcoded opps regardless of input.\n"
             "No product-family search. No partial matching on CEC side.",
             "BLOCKED\n(SAP team dependency)"],

            ["1.2: Filter by AI Readiness\nCriteria",
             "AI confidence scoring (>=70%, 40-69%, <40%).\n"
             "KYP status integrated into score.\nKaizen OpportunityReadinessAgent.",
             "No AI agent implemented.\nNo confidence scoring.\nNo Kaizen integration.\n"
             "KYP assessment exists but not wired to readiness scoring.",
             "NOT STARTED"],

            ["1.3: View AI Confidence\nReasoning",
             "Detailed checklist, next steps, user override with audit.",
             "Not implemented.",
             "NOT STARTED"],
        ],
        col_widths=[3.5, 5, 6, 3],
    )

    doc.add_heading("Epic 1 Verdict", level=2)
    add_verdict(doc, "30% COMPLETE - BLOCKED ON SAP IFLOW", "C00000")
    doc.add_paragraph(
        "The CPI opportunity call works technically but returns stub data. "
        "No AI confidence scoring, no Kaizen agents, no readiness filtering. "
        "Story 1.1 is blocked by SAP team (iFlow needs real CEC data). "
        "Stories 1.2 and 1.3 have zero implementation."
    )

    # ════════════════════════════════════════════════════════════════════
    doc.add_heading("4. Epic 2: Fast Order Creation", level=1)
    # ════════════════════════════════════════════════════════════════════

    add_table(doc,
        ["Story", "Requirement", "Implementation", "Status"],
        [
            ["2.1: Auto-Retrieve Order\nData from Multiple Systems",
             "Parallel retrieval from C4C + IPAS + SAP.\nMerge into unified order object.\n<5s total.",
             "Unified lookup endpoint exists (GET /api/v1/customer/{query}/full).\n"
             "Pulls: credit (CPI), opps (CPI stub), KYP (Aravo), IPAS (XML), FinOps (sim).\n"
             "NOT parallel execution. No SalesOrderProposal assembly.",
             "PARTIAL\n(data retrieval only,\nno order assembly)"],

            ["2.2: AI Agent Validates &\nPopulates IDoc Fields",
             "30-40% auto-fill of IDoc fields.\nKaizen OrderOrchestrationAgent.\nBAPI_SALESORDER_SIMULATE pre-validation.\nColor-coded confidence.",
             "Not implemented. No Kaizen agent.\nNo IDoc field population.\nNo BAPI_SALESORDER_SIMULATE.\nNo confidence scoring.",
             "NOT STARTED"],

            ["2.3: Submit Order to SAP",
             "IDoc ORDERS05 submission.\nVBELN received within 30s.\nIdempotency via correlation_id.",
             "Not implemented. No IDoc client.\nNo submission workflow.\nNo idempotency layer.",
             "NOT STARTED"],

            ["2.4: View Order Status &\nAudit Trail",
             "Order status from SAP.\nImmutable audit trail.\nField provenance.\nPDF export.",
             "Not implemented. No audit store.\nNo provenance tracking.\nNo PDF export.",
             "NOT STARTED"],
        ],
        col_widths=[3.5, 5, 6, 3],
    )

    doc.add_heading("Epic 2 Verdict", level=2)
    add_verdict(doc, "5% COMPLETE - CORE POV FEATURE MISSING", "C00000")
    doc.add_paragraph(
        "This is the critical gap. Story 2.2 (AI auto-fill) is the CORE POV FEATURE "
        "and has zero implementation. Stories 2.3 and 2.4 (SAP submission and audit) "
        "are also completely missing. Only data retrieval (Story 2.1) is partially done "
        "via the unified customer lookup endpoint."
    )

    # ════════════════════════════════════════════════════════════════════
    doc.add_heading("5. Production vs Local Gap Analysis", level=1)
    # ════════════════════════════════════════════════════════════════════

    doc.add_paragraph(
        "The production system at rr.kailash.ai runs a DIFFERENT codebase with significantly "
        "more functionality. The local repo has NOT been merged into production."
    )

    add_table(doc,
        ["Capability", "Production (rr.kailash.ai)", "Local Repo"],
        [
            ["Total Endpoints", "78", "22"],
            ["Authentication", "Login/logout/sessions/RBAC", "API key only (X-API-Key)"],
            ["Chat Agent", "Multi-turn conversational AI with streaming", "Not implemented"],
            ["Marine Intel", "14 endpoints (opportunities, articles, search, retention)", "Not implemented"],
            ["Competitor Intel", "4 endpoints (RAG queries, refresh jobs)", "Not implemented"],
            ["Industry Insights", "4 endpoints (news, structured, search)", "Not implemented"],
            ["Unified Intelligence", "3 endpoints (cross-source semantic search)", "Not implemented"],
            ["Scheduler", "4 endpoints (jobs, history, cleanup)", "Not implemented"],
            ["FinOps", "6 endpoints (summary, billing, collections, aging, payment-terms, refresh)", "4 endpoints (billing, aging, summary, customers)"],
            ["IPAS", "3 endpoints (summary, orders, order detail)", "4 endpoints (summary, orders, order detail, reload)"],
            ["Validation/KYP", "4 endpoints", "4 endpoints (matching)"],
            ["CPI Credit", "Via debug endpoint", "Dedicated endpoint"],
            ["Entity Registry", "Via debug endpoint", "Dedicated endpoints"],
            ["Aravo KYP", "NOT CONFIGURED in prod metrics", "Client built, not deployed"],
            ["IPAS XML Parser", "NOT CONFIGURED in prod", "Built and tested locally"],
            ["CPI Status", "Connected", "Requires env vars"],
        ],
        col_widths=[4, 6.5, 6.5],
    )

    # ════════════════════════════════════════════════════════════════════
    doc.add_heading("6. Integration Status", level=1)
    # ════════════════════════════════════════════════════════════════════

    add_table(doc,
        ["Integration", "Status", "Blocking Issues"],
        [
            ["SAP CPI Credit Check\n(BAPI_CR_ACC_GETDETAIL)", "WORKING",
             "Works with credit control area 0111.\nReturns real credit limit and exposure."],

            ["SAP CPI GetOpportunity", "STUB",
             "iFlow returns same 2 hardcoded anonymous opportunities for ALL customers.\n"
             "SAP team needs to connect it to real CEC data.\nBLOCKS Epic 1 entirely."],

            ["Aravo KYP", "BUILT, NOT DEPLOYED",
             "Client code complete and tested.\n"
             "IP-restricted: 401 from local machine, needs testing from prod server.\n"
             "Production env vars (ARAVO_REPORT_ID, ARAVO_AUTH_TOKEN) NOT SET.\n"
             "GitHub secrets stored but not propagated to production."],

            ["IPAS (XML Parser)", "BUILT, NOT DEPLOYED",
             "Parser works locally with demo XML files.\n"
             "Production shows IPAS=not configured.\n"
             "Need to set IPAS_XML_DIR and deploy XML files to production."],

            ["MS5 BAPI (Simulate)", "NOT IMPLEMENTED",
             "Required for Story 2.2 (IDoc field validation).\n"
             "BAPI_SALESORDER_SIMULATE not built."],

            ["MS5 IDoc (Submit)", "NOT IMPLEMENTED",
             "Required for Story 2.3 (order submission).\n"
             "ORDERS05 IDoc client not built."],

            ["CEC OData (Direct)", "NOT IMPLEMENTED",
             "Required for Story 1.1 (opportunity search).\n"
             "Currently relies on CPI iFlow which is a stub."],

            ["DataFlow / Audit Store", "NOT IMPLEMENTED",
             "Required for Stories 2.3, 2.4.\n"
             "No PostgreSQL audit tables, no DataFlow models."],

            ["Kaizen AI Agents", "NOT IMPLEMENTED",
             "Required for Stories 1.2, 1.3, 2.2.\n"
             "No OpportunityReadinessAgent or OrderOrchestrationAgent."],
        ],
        col_widths=[4, 3, 10.5],
    )

    # ════════════════════════════════════════════════════════════════════
    doc.add_heading("7. What Actually Works Today", level=1)
    # ════════════════════════════════════════════════════════════════════

    doc.add_paragraph("If we deployed the local code to production today, the demo flow would be:")

    add_table(doc,
        ["Step", "What Happens", "Source", "Works?"],
        [
            ["User says: 'Status of ST Engineering'", "Entity registry resolves to 0022005992", "Simulated (in-memory)", "YES"],
            ["Credit Check", "Real SAP CPI call returns credit limit and exposure", "Real SAP CPI", "YES"],
            ["Opportunities", "CPI returns 2 anonymous stub opportunities (not real STE data)", "SAP CPI STUB", "MISLEADING"],
            ["Aravo KYP", "Client built but prod env vars not set -> will fail with config error", "Real Aravo (if configured)", "NO (not deployed)"],
            ["IPAS Order", "Returns 1x 8V2000M72 engine, EUR 62,630, 3 BOM items", "Mock XML file", "YES"],
            ["FinOps Billing", "Returns 2 down payments, fully cleared, ON_TRACK", "Simulated", "YES"],
            ["FinOps Aging", "Returns zero receivables, LOW risk", "Simulated", "YES"],
            ["AI Synthesis", "No chat agent in local repo to synthesize results", "Not implemented", "NO"],
        ],
        col_widths=[4.5, 6, 3, 3],
    )

    # ════════════════════════════════════════════════════════════════════
    doc.add_heading("8. Critical Blockers", level=1)
    # ════════════════════════════════════════════════════════════════════

    add_table(doc,
        ["#", "Blocker", "Impact", "Owner", "Resolution"],
        [
            ["1", "GetOpportunity iFlow is a STUB",
             "Blocks ALL of Epic 1.\nOpportunity data is fake.",
             "SAP CPI Team",
             "SAP team must connect iFlow to real CEC OData.\nNo workaround possible."],

            ["2", "Local code not merged into production",
             "All new services (Aravo, IPAS parser, FinOps sim, entity registry) exist only locally.",
             "Dev Team",
             "Merge local services into production codebase at rr.kailash.ai.\nAlign endpoint patterns."],

            ["3", "Aravo env vars not set in production",
             "KYP compliance check will fail.\nTier 1 validation broken.",
             "Dev Team",
             "Set ARAVO_REPORT_ID, ARAVO_AUTH_TOKEN, ARAVO_VERIFY_SSL in production.\nGitHub secrets exist but not propagated."],

            ["4", "No Kaizen AI agents",
             "No AI confidence scoring (Story 1.2).\nNo IDoc auto-fill (Story 2.2).\nThese are the CORE POV features.",
             "Dev Team",
             "Implement OpportunityReadinessAgent and OrderOrchestrationAgent.\nEstimate: 2-3 weeks."],

            ["5", "No MS5 BAPI/IDoc integration",
             "Cannot submit orders to SAP (Story 2.3).\nCannot validate IDoc fields (Story 2.2).",
             "Dev Team + SAP Team",
             "Build BAPI_SALESORDER_SIMULATE and ORDERS05 IDoc clients.\nRequires SAP sandbox access.\nEstimate: 2 weeks."],

            ["6", "No audit store / DataFlow",
             "No provenance tracking.\nNo idempotency.\nStories 2.3, 2.4 blocked.",
             "Dev Team",
             "Set up PostgreSQL audit tables.\nImplement DataFlow models or fallback to Core SDK.\nEstimate: 1 week."],

            ["7", "SAP_CPI_CLIENT_SECRET missing in GitHub",
             "CPI calls will fail without OAuth secret.",
             "Dev Team",
             "Add SAP_CPI_CLIENT_SECRET to GitHub secrets and production env."],
        ],
        col_widths=[0.8, 4, 4, 2.5, 6],
    )

    # ════════════════════════════════════════════════════════════════════
    doc.add_heading("9. Requirements Compliance Matrix", level=1)
    # ════════════════════════════════════════════════════════════════════

    add_table(doc,
        ["Requirement", "Status", "Evidence"],
        [
            ["Search opportunities by customer/product (1.1)", "BLOCKED", "CPI iFlow is a stub. No product-family search."],
            ["Partial matching on search (1.1)", "PARTIAL", "Entity registry does fuzzy matching on customer name. No CEC-side search."],
            ["Results within 2 seconds (1.1)", "UNTESTED", "CPI call ~2-5s depending on network. Not benchmarked."],
            ["AI readiness filter >=70/40-69/<40 (1.2)", "NOT IMPLEMENTED", "No AI scoring agent."],
            ["KYP in readiness score (1.2)", "NOT IMPLEMENTED", "KYP assessment built but not wired to scoring."],
            ["AI confidence reasoning (1.3)", "NOT IMPLEMENTED", "No reasoning output."],
            ["User override with audit (1.3)", "NOT IMPLEMENTED", "No audit store."],
            ["Parallel data retrieval <5s (2.1)", "PARTIAL", "Unified lookup endpoint exists but calls are sequential, not parallel."],
            ["30-40% IDoc auto-fill (2.2)", "NOT IMPLEMENTED", "No IDoc field population. CORE POV METRIC."],
            ["BAPI pre-validation (2.2)", "NOT IMPLEMENTED", "No BAPI_SALESORDER_SIMULATE."],
            ["Color-coded confidence fields (2.2)", "NOT IMPLEMENTED", "No UI, no confidence scoring."],
            ["IDoc ORDERS05 submission (2.3)", "NOT IMPLEMENTED", "No IDoc client."],
            ["VBELN received within 30s (2.3)", "NOT IMPLEMENTED", "No SAP submission."],
            ["Idempotency via correlation_id (2.3)", "NOT IMPLEMENTED", "No idempotency layer."],
            ["Immutable audit trail (2.4)", "NOT IMPLEMENTED", "No audit store."],
            ["PDF export of audit trail (2.4)", "NOT IMPLEMENTED", "No PDF generation."],
            ["5-10 orders end-to-end (UAT)", "NOT POSSIBLE", "Cannot submit orders without MS5 IDoc."],
            ["30-40% acceptance rate (UAT)", "NOT MEASURABLE", "No IDoc auto-fill to measure acceptance."],
            ["0 critical bugs (UAT)", "N/A", "No UAT conducted."],
        ],
        col_widths=[6.5, 3, 8],
    )

    # ════════════════════════════════════════════════════════════════════
    doc.add_heading("10. Recommendations", level=1)
    # ════════════════════════════════════════════════════════════════════

    doc.add_heading("Immediate Actions (This Week)", level=2)
    rows = [
        ["1", "Merge local services into production codebase", "Aravo, IPAS parser, FinOps sim, entity registry, CPI client updates"],
        ["2", "Set Aravo env vars in production", "ARAVO_REPORT_ID, ARAVO_AUTH_TOKEN, ARAVO_VERIFY_SSL"],
        ["3", "Set SAP_CPI_CLIENT_SECRET in production", "Required for any CPI call"],
        ["4", "Deploy IPAS XML files to production", "Set IPAS_XML_DIR, copy STE_1207814.XML"],
        ["5", "Escalate GetOpportunity iFlow to SAP team", "Epic 1 is completely blocked without real CEC data"],
    ]
    add_table(doc, ["#", "Action", "Detail"], rows, col_widths=[0.8, 6, 10.5])

    doc.add_heading("Short-Term (Next 2 Weeks)", level=2)
    rows = [
        ["6", "Build Kaizen OpportunityReadinessAgent", "AI scoring for Story 1.2 - requires LLM integration"],
        ["7", "Build BAPI_SALESORDER_SIMULATE client", "IDoc pre-validation for Story 2.2"],
        ["8", "Build basic audit store", "PostgreSQL tables for correlation_id, provenance"],
        ["9", "Wire Tier 2 SAP validation", "Connect CPI credit check to validation_service"],
    ]
    add_table(doc, ["#", "Action", "Detail"], rows, col_widths=[0.8, 6, 10.5])

    doc.add_heading("Medium-Term (Weeks 3-4)", level=2)
    rows = [
        ["10", "Build OrderOrchestrationAgent", "IDoc auto-fill for Story 2.2 (CORE POV FEATURE)"],
        ["11", "Build ORDERS05 IDoc client", "SAP submission for Story 2.3"],
        ["12", "Implement idempotency layer", "correlation_id dedup for Story 2.3"],
        ["13", "Build provenance tracking", "AI vs manual field tracking for Story 2.4"],
        ["14", "UAT preparation", "10 test orders, 3-5 pilot users, metrics capture"],
    ]
    add_table(doc, ["#", "Action", "Detail"], rows, col_widths=[0.8, 6, 10.5])

    # ════════════════════════════════════════════════════════════════════
    doc.add_heading("11. Summary", level=1)
    # ════════════════════════════════════════════════════════════════════

    doc.add_paragraph(
        "The system has good foundational infrastructure: SAP CPI credit check works, "
        "Aravo KYP client is built, IPAS XML parser is functional, FinOps simulator has "
        "realistic demo data. However, the CORE POV FEATURES (AI confidence scoring and "
        "IDoc auto-fill) have zero implementation. The production server runs a different "
        "codebase that hasn't been updated with the local work. The SAP GetOpportunity "
        "iFlow is a stub, blocking all of Epic 1."
    )

    p = doc.add_paragraph()
    run = p.add_run("Bottom line: ")
    run.bold = True
    run = p.add_run(
        "We can demo data retrieval and display (credit, IPAS, FinOps, KYP). "
        "We cannot demo AI-driven opportunity qualification or order creation, "
        "which are the two features the POV was designed to prove."
    )

    output = "docs/RRPS Production Readiness Red Team Report.docx"
    doc.save(output)
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()
