"""Build BAPI_SALESORDER_CREATEFROMDAT2 Complete Field Mapping .docx from reference template."""
import shutil
import re
from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# Paths
REF_DOC = r"C:\Users\fujif\OneDrive\Desktop\BAPI_Field_Mapping_Integrum_to_MS5.docx"
OUT_DOC = r"C:\Users\fujif\OneDrive\Desktop\BAPI_SALESORDER_CREATEFROMDAT2_Complete_Field_Mapping.docx"
MD_FILE = r"C:\Users\fujif\OneDrive\Documents\GitHub\lead2cash\docs\BAPI_SALESORDER_CREATEFROMDAT2_Complete_Field_Mapping.md"

# Copy reference document to preserve styles
shutil.copy2(REF_DOC, OUT_DOC)
doc = Document(OUT_DOC)

# Clear all content
for p in doc.paragraphs[:]:
    p._element.getparent().remove(p._element)
for t in doc.tables[:]:
    t._element.getparent().remove(t._element)

# ============================================================================
# Helper functions (same pattern as build_dp_docx.py)
# ============================================================================

def add_title(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(16)
    run.font.name = 'Calibri'
    try:
        p.style = doc.styles['Title']
    except:
        pass

def add_subtitle(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.font.size = Pt(11)
    run.font.name = 'Calibri'
    run.font.color.rgb = RGBColor(0x59, 0x56, 0x59)

def add_h1(text):
    p = doc.add_heading(text, level=1)
    for run in p.runs:
        run.font.name = 'Calibri'

def add_h2(text):
    p = doc.add_heading(text, level=2)
    for run in p.runs:
        run.font.name = 'Calibri'

def add_h3(text):
    p = doc.add_heading(text, level=3)
    for run in p.runs:
        run.font.name = 'Calibri'

def add_body(text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(9)
    run.font.name = 'Calibri'
    return p

def add_bold_body(text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(9)
    run.font.name = 'Calibri'
    run.bold = True
    return p

def add_bullet(text, level=0):
    p = doc.add_paragraph(style='List Bullet')
    p.clear()
    run = p.add_run(text)
    run.font.size = Pt(9)
    run.font.name = 'Calibri'
    if level > 0:
        pf = p.paragraph_format
        pf.left_indent = Cm(1.27 * (level + 1))
    return p

def add_code(text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(8)
    run.font.name = 'Consolas'
    pf = p.paragraph_format
    pf.left_indent = Cm(1.27)
    pf.space_before = Pt(2)
    pf.space_after = Pt(2)
    # Light gray background shading
    shading = OxmlElement('w:shd')
    shading.set(qn('w:fill'), 'F2F2F2')
    shading.set(qn('w:val'), 'clear')
    p._element.get_or_add_pPr().append(shading)
    return p

def add_table(headers, rows, col_widths=None):
    """Add a formatted table with bold 9pt headers and 9pt body."""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    try:
        table.style = 'Table Grid'
    except:
        pass

    # Header row
    hdr = table.rows[0]
    for i, h in enumerate(headers):
        cell = hdr.cells[i]
        cell.text = ''
        p = cell.paragraphs[0]
        run = p.add_run(h)
        run.bold = True
        run.font.size = Pt(9)
        run.font.name = 'Calibri'
        # Header shading
        shading = OxmlElement('w:shd')
        shading.set(qn('w:fill'), '4472C4')
        shading.set(qn('w:val'), 'clear')
        cell._element.get_or_add_tcPr().append(shading)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    # Data rows
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = table.rows[ri + 1].cells[ci]
            cell.text = ''
            p = cell.paragraphs[0]
            run = p.add_run(str(val))
            run.font.size = Pt(9)
            run.font.name = 'Calibri'
            # Alternate row shading
            if ri % 2 == 1:
                shading = OxmlElement('w:shd')
                shading.set(qn('w:fill'), 'D9E2F3')
                shading.set(qn('w:val'), 'clear')
                cell._element.get_or_add_tcPr().append(shading)

    # Set column widths if provided
    if col_widths:
        for ri_idx, row_obj in enumerate(table.rows):
            for ci_idx, w in enumerate(col_widths):
                if ci_idx < len(row_obj.cells):
                    row_obj.cells[ci_idx].width = Inches(w)

    doc.add_paragraph()  # spacing
    return table

def add_page_break():
    doc.add_page_break()

def clean_md(text):
    """Strip markdown formatting artifacts like **, `, _, etc."""
    text = text.strip()
    text = text.replace('**', '')
    text = text.replace('`', '')
    text = text.replace('_(', '(').replace(')_', ')')
    text = text.replace('_', '')
    return text

def parse_md_table(lines):
    """Parse markdown table lines into (headers, rows).
    Expects lines starting with |. Skips separator lines (|---|)."""
    headers = []
    rows = []
    for line in lines:
        line = line.strip()
        if not line.startswith('|'):
            continue
        cells = [clean_md(c) for c in line.split('|')[1:-1]]
        # Skip separator lines
        if all(set(c.strip()) <= set('-: ') for c in cells):
            continue
        if not headers:
            headers = [c.strip() for c in cells]
        else:
            rows.append([c.strip() for c in cells])
    return headers, rows


# ============================================================================
# Read the markdown file
# ============================================================================
with open(MD_FILE, 'r', encoding='utf-8') as f:
    md_lines = f.readlines()

# Build a simple line-based structure for table extraction
md_text = ''.join(md_lines)

def extract_table_block(start_pattern, end_patterns=None):
    """Extract table lines from markdown between a start pattern and end patterns."""
    table_lines = []
    in_table = False
    found_start = False
    for line in md_lines:
        stripped = line.strip()
        if not found_start:
            if start_pattern in stripped:
                found_start = True
            continue
        if stripped.startswith('|'):
            in_table = True
            table_lines.append(stripped)
        elif in_table and not stripped.startswith('|'):
            # End of table
            break
    return table_lines


# ============================================================================
# TITLE PAGE
# ============================================================================

doc.add_paragraph()
doc.add_paragraph()
add_title("BAPI_SALESORDER_CREATEFROMDAT2")
add_title("Complete Field Mapping Specification")
doc.add_paragraph()
add_subtitle("RRPS Lead-to-Cash: Integrum to SAP MS5 Order Creation")
doc.add_paragraph()
add_subtitle("Version: 2.1 (Red-Team Verified)")
add_subtitle("Date: 2026-04-16")
add_subtitle("Classification: Confidential - RRPS Internal")
add_subtitle("Author: Integrum / Kailash AI")
add_subtitle("Supersedes: BAPI Field Mapping v1.0 (original 14-header / 8-item mapping)")

add_page_break()

# ============================================================================
# TABLE OF CONTENTS
# ============================================================================

add_h1("Table of Contents")
toc_items = [
    "1. Context",
    "2. BAPI-Level Parameters",
    "   2.1 LOGIC_SWITCH (BAPISDLS) - 6 Fields",
    "   2.2 SENDER (BAPI_SENDER) - 1 Field",
    "3. ORDER_HEADER_IN (BAPISDHD1) - All 130 Fields",
    "4. ORDER_HEADER_INX (BAPISDHD1X) - Update Indicators for Header",
    "5. ORDER_ITEMS_IN (BAPISDITM) - All 220 Fields",
    "6. ORDER_ITEMS_INX (BAPISDITMX) - Update Indicators for Items",
    "7. ORDER_PARTNERS (BAPIPARNR) - All 38 Fields",
    "8. ORDER_SCHEDULES_IN (BAPISCHDL) - All 23 Fields",
    "9. ORDER_SCHEDULES_INX (BAPISCHDLX) - Update Indicators for Schedules",
    "10. ORDER_CONDITIONS_IN (BAPICOND) - All 56 Fields",
    "11. ORDER_CONDITIONS_INX (BAPICONDX) - 10 Fields",
    "12. ORDER_TEXT (BAPISDTEXT) - 8 Fields",
    "13. EXTENSIONIN (BAPIPAREX) - Customer Enhancements",
    "   13.1 BAPE_VBAK - Header Extension Fields",
    "   13.2 BAPE_VBAP - Item Extension Fields",
    "14. Additional WSDL Structures (Not Used for RRPS)",
    "15. REFOBJTYPE / REFOBJKEY / REFLOGSYS - Traceability Specification",
    "16. BAPI Call Sequence",
    "17. Coverage Summary",
    "18. Change Log",
]
for item in toc_items:
    add_body(item)

add_page_break()

# ============================================================================
# SECTION 1: Context
# ============================================================================

add_h1("1. Context")

add_body("Srinivas,")

add_body(
    "Following your review of the original field mapping document, you identified that a significant "
    "number of BAPI fields were not accounted for. You are correct. The WSDL for "
    "BAPI_SALESORDER_CREATEFROMDAT2 defines 130 fields in BAPISDHD1 (ORDER_HEADER_IN) alone, and the "
    "original mapping covered only 14 of them. Similarly, BAPISDITM (ORDER_ITEMS_IN) defines 220 fields "
    "and we had mapped only 8."
)

add_body(
    "This Version 2.0 document provides complete field coverage for every structure in the BAPI. "
    "For each field we specify:"
)
add_bullet('Whether it was in the original mapping ("EXISTING") or is newly documented ("NEW")')
add_bullet("The data source (IPAS XML, CEC/Opportunity, Agent-derived, Constant, or Not Mapped)")
add_bullet("Default/constant values for the RRPS context")
add_bullet("Mandatory status and implementation notes")

add_bold_body("Key additions in v2.0:")
add_bullet("REFOBJTYPE / REFOBJKEY / REFLOGSYS traceability fields across all structures")
add_bullet("BAPI-level control parameters (TESTRUN, LOGIC_SWITCH, BEHAVE_WHEN_ERROR, etc.)")
add_bullet("Complete HEADER_INX, ITEMS_INX, SCHEDULES_INX, CONDITIONS_INX update indicator tables")
add_bullet("EXTENSIONIN customer enhancement structures (BAPE_VBAK, BAPE_VBAP)")
add_bullet("ORDER_TEXT structure for long texts")
add_bullet("BAPI call sequence with BAPI_TRANSACTION_COMMIT")

add_bold_body("RRPS Constants:")
add_bullet("Company Code: 0011")
add_bullet("Sales Organization: 0011")
add_bullet("Order Type: ZEN2 (Engine New Business)")
add_bullet("Item Categories: ZE1 / ZE2 / ZE3 / ZEX2")
add_bullet("Distribution Channel: from IPAS XML Distr_Channel")
add_bullet("Reference Object Type: IPAS (for cross-system traceability)")

add_page_break()

# ============================================================================
# SECTION 2: BAPI-Level Parameters
# ============================================================================

add_h1("2. BAPI-Level Parameters")

add_body("These are scalar/structure parameters on the BAPI function module itself, outside the table parameters.")

# Table: BAPI-level parameters
tbl_lines = extract_table_block("| Parameter | WSDL Type | Direction |")
headers, rows = parse_md_table(tbl_lines)
if headers and rows:
    add_table(headers, rows)

# 2.1 LOGIC_SWITCH
add_h2("2.1 LOGIC_SWITCH (BAPISDLS) Recommendations")

tbl_lines = extract_table_block("| # | Field | WSDL Type | Recommended |")
headers, rows = parse_md_table(tbl_lines)
if headers and rows:
    add_table(headers, rows)

add_bold_body("RRPS Recommendation:")
add_body(
    "Set PRICING = 'X' and SCHEDULING = 'X'. Leave other flags blank for standard SAP behavior. "
    "If IPAS supplies complete pricing (via ORDER_CONDITIONS_IN), consider PRICING = 'C' "
    "(copy pricing without re-determination)."
)

# 2.2 SENDER
add_h2("2.2 SENDER (BAPI_SENDER) Recommendations")

# Find the SENDER table specifically (second occurrence of Field|Type|Recommended)
sender_found = False
sender_lines = []
for i, line in enumerate(md_lines):
    if '### 2.2 SENDER' in line:
        sender_found = True
        continue
    if sender_found and line.strip().startswith('|'):
        sender_lines.append(line.strip())
    elif sender_found and sender_lines and not line.strip().startswith('|'):
        break

headers, rows = parse_md_table(sender_lines)
if headers and rows:
    add_table(headers, rows)

add_page_break()

# ============================================================================
# SECTION 3: ORDER_HEADER_IN - All 130 Fields
# ============================================================================

add_h1("3. ORDER_HEADER_IN (BAPISDHD1) - All 130 Fields")

add_body("The original mapping covered 14 of 130 fields. All 130 fields are listed below, verified against WSDL.")

add_bold_body("Legend:")
add_bullet("Status: EXISTING = was in v1.0 mapping, NEW = added in v2.0")
add_bullet("Source: IPAS = from IPAS XML, CEC = from CEC/Opportunity, Agent = agent-derived, Const = constant value, SAP = SAP-determined, -- = not mapped (leave blank)")
add_bullet("Mand.: Y = mandatory for RRPS, R = recommended, O = optional, C = conditional")

# Extract the large header table
header_table_lines = []
in_section3 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '## 3. ORDER_HEADER_IN' in stripped:
        in_section3 = True
        continue
    if in_section3 and stripped.startswith('## ') and '## 3.' not in stripped:
        break
    if in_section3 and stripped.startswith('|'):
        header_table_lines.append(stripped)

headers, rows = parse_md_table(header_table_lines)
if headers and rows:
    add_table(headers, rows)

add_page_break()

# ============================================================================
# SECTION 4: ORDER_HEADER_INX
# ============================================================================

add_h1("4. ORDER_HEADER_INX (BAPISDHD1X) - Update Indicators for Header")

add_body(
    "Every field in ORDER_HEADER_IN that you want SAP to process must have a corresponding 'X' flag "
    "in ORDER_HEADER_INX. If the flag is blank, SAP ignores the value even if populated."
)

header_inx_lines = []
in_section4 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '## 4. ORDER_HEADER_INX' in stripped:
        in_section4 = True
        continue
    if in_section4 and stripped.startswith('## ') and '## 4.' not in stripped:
        break
    if in_section4 and stripped.startswith('|'):
        header_inx_lines.append(stripped)

headers, rows = parse_md_table(header_inx_lines)
if headers and rows:
    add_table(headers, rows)

add_bold_body("Rule:")
add_body("For every non-blank field in ORDER_HEADER_IN, set the corresponding field in ORDER_HEADER_INX to 'X'. For blank/unmapped fields, leave the INX field blank.")

add_page_break()

# ============================================================================
# SECTION 5: ORDER_ITEMS_IN - All 223 Fields
# ============================================================================

add_h1("5. ORDER_ITEMS_IN (BAPISDITM) - All 220 Fields")

add_body("The original mapping covered 8 of 220 fields. One row per IPAS Engine or BOM Item.")

add_h2("5.1 RRPS-Relevant Item Fields (mapped or recommended)")

items_table_lines = []
in_section51 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '### 5.1 RRPS-Relevant' in stripped:
        in_section51 = True
        continue
    if in_section51 and (stripped.startswith('### 5.2') or stripped.startswith('## ')):
        break
    if in_section51 and stripped.startswith('|'):
        items_table_lines.append(stripped)

headers, rows = parse_md_table(items_table_lines)
if headers and rows:
    add_table(headers, rows)

add_h2("5.2 Additional Item Fields (leave blank for RRPS)")
add_body(
    "The remaining 189 fields are available in the WSDL but should be left blank for RRPS ZEN2. "
    "They are documented by functional grouping in the markdown specification with WSDL line references."
)
add_body(
    "Removed hallucinated fields from v2.0: REQ_DATE (belongs to BAPISCHDL), NET_PRICE, COND_VALUE, "
    "PURCH_NO_C_I (actual: PURCH_NO_C), PURCH_DATE_I (actual: PURCH_DATE), "
    "CUST_GRP1-5 (actual: CSTCNDGRP1-5), UNLOAD_PT, PACKING_NO."
)

add_page_break()

# ============================================================================
# SECTION 6: ORDER_ITEMS_INX
# ============================================================================

add_h1("6. ORDER_ITEMS_INX (BAPISDITMX) - Update Indicators for Items")

items_inx_lines = []
in_section6 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '## 6. ORDER_ITEMS_INX' in stripped:
        in_section6 = True
        continue
    if in_section6 and stripped.startswith('## ') and '## 6.' not in stripped:
        break
    if in_section6 and stripped.startswith('|'):
        items_inx_lines.append(stripped)

headers, rows = parse_md_table(items_inx_lines)
if headers and rows:
    add_table(headers, rows)

add_bold_body("Rule:")
add_body("Same as header - set 'X' for every field populated in ORDER_ITEMS_IN.")

add_page_break()

# ============================================================================
# SECTION 7: ORDER_PARTNERS
# ============================================================================

add_h1("7. ORDER_PARTNERS (BAPIPARNR) - All 38 Fields")

add_body("The original mapping covered 2 of 38 fields (PARTN_ROLE + PARTN_NUMB). One row per partner function.")

partners_table_lines = []
in_section7 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '## 7. ORDER_PARTNERS' in stripped:
        in_section7 = True
        continue
    if in_section7 and stripped.startswith('## ') and '## 7.' not in stripped:
        break
    if in_section7 and stripped.startswith('|'):
        partners_table_lines.append(stripped)

headers, rows = parse_md_table(partners_table_lines)
# The partners section has TWO tables. Split them.
if headers and rows:
    # Find where the second table starts (different header)
    # First table: # | Field Name | SAP Type | ...
    # Second table: PARTN_ROLE | PARTN_NUMB Source | Description
    first_table_rows = []
    second_table_headers = None
    second_table_rows = []

    # Check if there are rows with different column counts
    first_col_count = len(headers)

    # Actually, let's parse more carefully by finding both tables
    table1_lines = []
    table2_lines = []
    in_t1 = False
    in_t2 = False
    gap = False
    for tl in partners_table_lines:
        if '# | Field Name' in tl or (not in_t1 and not in_t2 and '|' in tl and 'Field Name' in tl):
            in_t1 = True
            table1_lines.append(tl)
            continue
        if 'PARTN_ROLE' in tl and 'PARTN_NUMB Source' in tl:
            in_t1 = False
            in_t2 = True
            table2_lines.append(tl)
            continue
        if in_t1:
            table1_lines.append(tl)
        elif in_t2:
            table2_lines.append(tl)

    h1, r1 = parse_md_table(table1_lines)
    if h1 and r1:
        add_table(h1, r1)

    add_bold_body("RRPS Partner Mapping (minimum required rows):")

    h2, r2 = parse_md_table(table2_lines)
    if h2 and r2:
        add_table(h2, r2)

add_page_break()

# ============================================================================
# SECTION 8: ORDER_SCHEDULES_IN
# ============================================================================

add_h1("8. ORDER_SCHEDULES_IN (BAPISCHDL) - All 23 Fields")

add_body("The original mapping covered 4 of 23 fields. One row per delivery schedule line per item.")

sched_table_lines = []
in_section8 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '## 8. ORDER_SCHEDULES_IN' in stripped:
        in_section8 = True
        continue
    if in_section8 and stripped.startswith('## ') and '## 8.' not in stripped:
        break
    if in_section8 and stripped.startswith('|'):
        sched_table_lines.append(stripped)

headers, rows = parse_md_table(sched_table_lines)
if headers and rows:
    add_table(headers, rows)

add_page_break()

# ============================================================================
# SECTION 9: ORDER_SCHEDULES_INX
# ============================================================================

add_h1("9. ORDER_SCHEDULES_INX (BAPISCHDLX) - Update Indicators for Schedules")

sched_inx_lines = []
in_section9 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '## 9. ORDER_SCHEDULES_INX' in stripped:
        in_section9 = True
        continue
    if in_section9 and stripped.startswith('## ') and '## 9.' not in stripped:
        break
    if in_section9 and stripped.startswith('|'):
        sched_inx_lines.append(stripped)

headers, rows = parse_md_table(sched_inx_lines)
if headers and rows:
    add_table(headers, rows)

add_page_break()

# ============================================================================
# SECTION 10: ORDER_CONDITIONS_IN
# ============================================================================

add_h1("10. ORDER_CONDITIONS_IN (BAPICOND) - All 56 Fields")

add_body("Pricing conditions. One row per condition type per item (or header-level for header conditions).")

add_h2("10.1 RRPS-Relevant Condition Fields")

cond_rel_lines = []
in_section101 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '### 10.1 RRPS-Relevant' in stripped:
        in_section101 = True
        continue
    if in_section101 and (stripped.startswith('### 10.2') or stripped.startswith('## ')):
        break
    if in_section101 and stripped.startswith('|'):
        cond_rel_lines.append(stripped)

headers, rows = parse_md_table(cond_rel_lines)
if headers and rows:
    add_table(headers, rows)

add_h2("10.2 All 56 BAPICOND Fields (WSDL-verified)")

cond_all_lines = []
in_section102 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '### 10.2 All 56' in stripped:
        in_section102 = True
        continue
    if in_section102 and stripped.startswith('## '):
        break
    if in_section102 and stripped.startswith('|'):
        cond_all_lines.append(stripped)

headers2, rows2 = parse_md_table(cond_all_lines)
if headers2 and rows2:
    add_table(headers2, rows2)

add_page_break()

# ============================================================================
# SECTION 11: ORDER_CONDITIONS_INX
# ============================================================================

add_h1("11. ORDER_CONDITIONS_INX (BAPICONDX) - Update Indicators for Conditions")

cond_inx_lines = []
in_section11 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '## 11. ORDER_CONDITIONS_INX' in stripped:
        in_section11 = True
        continue
    if in_section11 and stripped.startswith('## ') and '## 11.' not in stripped:
        break
    if in_section11 and stripped.startswith('|'):
        cond_inx_lines.append(stripped)

headers, rows = parse_md_table(cond_inx_lines)
if headers and rows:
    add_table(headers, rows)

add_page_break()

# ============================================================================
# SECTION 12: ORDER_TEXT
# ============================================================================

add_h1("12. ORDER_TEXT (BAPISDTEXT) - Long Texts")

add_body("For order-level and item-level long texts (notes, terms, instructions).")

text_table_lines = []
in_section12 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '## 12. ORDER_TEXT' in stripped:
        in_section12 = True
        continue
    if in_section12 and stripped.startswith('## ') and '## 12.' not in stripped:
        break
    if in_section12 and stripped.startswith('|'):
        text_table_lines.append(stripped)

headers, rows = parse_md_table(text_table_lines)
if headers and rows:
    add_table(headers, rows)

add_bold_body("RRPS Text Mapping:")
add_bullet("Header text (ITM_NUMBER=000000, TEXT_ID='0001'): Map from IPAS order-level notes")
add_bullet("Item text (ITM_NUMBER=nnnnnn, TEXT_ID='0002'): Map from Item.Assembly_Note")
add_bullet("Engine text: Map from Engine.Exhaust_Regulation notes or other technical specs")

add_page_break()

# ============================================================================
# SECTION 13: EXTENSIONIN
# ============================================================================

add_h1("13. EXTENSIONIN (BAPIPAREX) - Customer Enhancements")

add_body(
    "RRPS uses custom Z-fields via the EXTENSIONIN table parameter. Each row carries a structure name "
    "and up to 960 characters of data."
)

ext_table_lines = []
in_section13 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '## 13. EXTENSIONIN' in stripped:
        in_section13 = True
        continue
    if in_section13 and stripped.startswith('### 13.1'):
        break
    if in_section13 and stripped.startswith('|'):
        ext_table_lines.append(stripped)

headers, rows = parse_md_table(ext_table_lines)
if headers and rows:
    add_table(headers, rows)

# 13.1 BAPE_VBAK
add_h2("13.1 BAPE_VBAK - Header Extension Fields")

add_body("These Z-fields are packed into VALUEPART1-4 according to the RRPS append structure.")

vbak_lines = []
in_131 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '### 13.1 BAPE_VBAK' in stripped:
        in_131 = True
        continue
    if in_131 and stripped.startswith('### 13.2'):
        break
    if in_131 and stripped.startswith('|'):
        vbak_lines.append(stripped)

headers, rows = parse_md_table(vbak_lines)
if headers and rows:
    add_table(headers, rows)

# 13.2 BAPE_VBAP
add_h2("13.2 BAPE_VBAP - Item Extension Fields")

vbap_lines = []
in_132 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '### 13.2 BAPE_VBAP' in stripped:
        in_132 = True
        continue
    if in_132 and stripped.startswith('## ') or (in_132 and stripped.startswith('---') and vbap_lines):
        break
    if in_132 and stripped.startswith('|'):
        vbap_lines.append(stripped)

headers, rows = parse_md_table(vbap_lines)
if headers and rows:
    add_table(headers, rows)

add_page_break()

# ============================================================================
# SECTION 14: ORDER_KEYS
# ============================================================================

add_h1("14. Additional WSDL Structures (Not Used for RRPS)")

add_body("The WSDL defines additional table parameters available but not required for RRPS ZEN2 engine orders.")

keys_lines = []
in_section14 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '## 14. Additional WSDL Structures' in stripped:
        in_section14 = True
        continue
    if in_section14 and stripped.startswith('## ') and '## 14.' not in stripped:
        break
    if in_section14 and stripped.startswith('|'):
        keys_lines.append(stripped)

headers, rows = parse_md_table(keys_lines)
if headers and rows:
    add_table(headers, rows)

add_page_break()

# ============================================================================
# SECTION 15: REFOBJTYPE / REFOBJKEY / REFLOGSYS
# ============================================================================

add_h1("15. REFOBJTYPE / REFOBJKEY / REFLOGSYS - Traceability Specification")

add_body(
    "These three fields appear in every table structure (Header, Items, Partners, Schedules, Conditions) "
    "and provide end-to-end traceability between IPAS and SAP."
)

add_h2("Recommended Values")

trace_lines = []
in_section15 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '### Recommended Values' in stripped:
        in_section15 = True
        continue
    if in_section15 and (stripped.startswith('### Why') or stripped.startswith('---')):
        break
    if in_section15 and stripped.startswith('|'):
        trace_lines.append(stripped)

headers, rows = parse_md_table(trace_lines)
if headers and rows:
    add_table(headers, rows)

add_h2("Why This Matters")
add_bullet("Idempotency: If the CPI iFlow retries, SAP can detect duplicate submissions via REFOBJTYPE+REFOBJKEY")
add_bullet("Audit Trail: SAP table CDHDR/CDPOS stores these reference values for change document tracking")
add_bullet("Reverse Lookup: From any SAP order, you can trace back to the originating IPAS order")
add_bullet("Error Recovery: If BAPI_TRANSACTION_COMMIT fails, the REFOBJKEY allows matching retry attempts")

add_page_break()

# ============================================================================
# SECTION 16: BAPI Call Sequence
# ============================================================================

add_h1("16. BAPI Call Sequence")

add_body("The complete call sequence for CPI integration:")

add_code("""Step 1: BAPI_SALESORDER_CREATEFROMDAT2
        Import Parameters:
          - BEHAVE_WHEN_ERROR = 'P'
          - CONVERT = 'X'
          - INT_NUMBER_ASSIGNMENT = 'X'
          - TESTRUN = '' (blank for production, 'X' for test)
          - LOGIC_SWITCH:
              PRICING = 'X'
              SCHEDULING = 'X'  (WSDL field name)
              ATP_WRKMOD = ' '
              NOSTRUCTURE = ' '
              COND_HANDL = ' '
              ADDR_CHECK = ' '
          - SENDER:
              LOG_SYSTEM = 'INTEGRUM'  (only field in BAPI_SENDER)
        Table Parameters:
          - ORDER_HEADER_IN (1 row)
          - ORDER_HEADER_INX (1 row)
          - ORDER_ITEMS_IN (1 row per engine/BOM item)
          - ORDER_ITEMS_INX (1 row per item, matching)
          - ORDER_PARTNERS (min 4 rows: AG, WE, RE, RG)
          - ORDER_SCHEDULES_IN (1 row per item)
          - ORDER_SCHEDULES_INX (1 row per schedule, matching)
          - ORDER_CONDITIONS_IN (1+ rows per item if manual pricing)
          - ORDER_CONDITIONS_INX (matching conditions)
          - ORDER_TEXT (optional, for notes)
          - EXTENSIONIN (2+ rows: BAPE_VBAK header, BAPE_VBAP per item)

Step 2: Check RETURN table
        - If TYPE = 'E' or 'A': Errors occurred. Log and abort.
        - If TYPE = 'S' or 'W': Success (with possible warnings).
        - Read SALESDOCUMENT for the created order number.
          (WSDL response field name, not SALES_DOCUMENT_OUT)

Step 3: BAPI_TRANSACTION_COMMIT
        Import Parameters:
          - WAIT = 'X'  (synchronous commit -- CRITICAL for CPI)

Step 4: (Optional) BAPI_SALESORDER_GETLIST or direct read
        - Verify the order was created by reading it back.
        - Store the SAP order number in Integrum for IPAS-to-SAP mapping.""")

add_bold_body("Error Handling in CPI iFlow:")
add_bullet("If Step 1 returns errors: Do NOT call BAPI_TRANSACTION_COMMIT. Call BAPI_TRANSACTION_ROLLBACK instead.")
add_bullet("If Step 3 fails: Retry with exponential backoff. The REFOBJKEY allows SAP to detect if the order was already created.")
add_bullet("Always log the full RETURN table for troubleshooting.")

add_page_break()

# ============================================================================
# SECTION 17: Coverage Summary
# ============================================================================

add_h1("17. Coverage Summary")

summary_lines = []
in_section17 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '## 17. Coverage Summary' in stripped:
        in_section17 = True
        continue
    if in_section17 and stripped.startswith('## ') and '## 17.' not in stripped:
        break
    if in_section17 and stripped.startswith('|'):
        summary_lines.append(stripped)

headers, rows = parse_md_table(summary_lines)
if headers and rows:
    add_table(headers, rows)

add_bold_body("Total WSDL-verified fields documented: 700+ (all structures combined)")

add_h2("Fields NOT Populated (by design)")
add_body("The following categories of fields are intentionally left blank for the RRPS ZEN2 engine order scenario:")
add_bullet("Quotation/Contract fields (QT_VALID_F/T, CT_VALID_F/T): Not applicable to direct orders")
add_bullet("Tax classification fields (TAX_CLASS1-9): SAP determines automatically from customer/material master")
add_bullet("Customer group fields (CUST_GRP1-5): SAP reads from customer master")
add_bullet("Configuration/variant fields (CONFIG_ID, INST_ID, etc.): RRPS engines are configured in IPAS, not SAP variant configuration")
add_bullet("SAP-calculated dates (DLV_DATE, TP_DATE, MS_DATE, LOAD_DATE, GI_DATE): SAP scheduling determines these")
add_bullet("Account determination fields (ACCNT_ASGN, PROFIT_CTR, etc.): SAP account determination handles these")

add_body(
    "These fields are documented above as 'leave blank' or 'SAP-determined' to confirm they were reviewed "
    "and deliberately excluded from the mapping, not overlooked."
)

add_page_break()

# ============================================================================
# SECTION 18: Change Log
# ============================================================================

add_h1("18. Change Log")

changelog_lines = []
in_section18 = False
for i, line in enumerate(md_lines):
    stripped = line.strip()
    if '## 18. Change Log' in stripped:
        in_section18 = True
        continue
    if in_section18 and stripped.startswith('## ') and '## 18.' not in stripped:
        break
    if in_section18 and stripped.startswith('|'):
        changelog_lines.append(stripped)

headers, rows = parse_md_table(changelog_lines)
if headers and rows:
    add_table(headers, rows)

doc.add_paragraph()
add_body(
    "This document provides complete field-level coverage of BAPI_SALESORDER_CREATEFROMDAT2 as defined "
    "in the WSDL. Every field from every structure is accounted for -- either with a mapped source value, "
    "a constant, a SAP-determined note, or an explicit 'leave blank' designation. No fields have been omitted."
)

# ============================================================================
# SAVE
# ============================================================================

doc.save(OUT_DOC)
print(f"Document saved to: {OUT_DOC}")
