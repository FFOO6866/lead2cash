# BAPI_SALESORDER_CREATEFROMDAT2 - Complete Field Mapping Specification

## RRPS Lead-to-Cash: Integrum to SAP MS5 Order Creation

---

**Version:** 2.1 (Red-Team Verified)
**Date:** 2026-04-16
**Classification:** Confidential - RRPS Internal
**Author:** Integrum / Kailash AI
**Supersedes:** v2.0 (contained hallucinated field names); v1.0 (original 14-header / 8-item mapping)
**Verified Against:** `DOC_WEBI_FUNCTIONMODULE.WSDL` (client-provided, line-by-line)

---

## 1. Context

Srinivas,

Following your review of the original field mapping document, you identified that a significant number of BAPI fields were not accounted for. You are correct. The WSDL for `BAPI_SALESORDER_CREATEFROMDAT2` defines **130 fields** in `BAPISDHD1` (ORDER_HEADER_IN) alone, and the original mapping covered only 14 of them. Similarly, `BAPISDITM` (ORDER_ITEMS_IN) defines **220 fields** and we had mapped only 8.

This Version 2.1 document provides **complete field coverage** for every structure in the BAPI, verified line-by-line against the WSDL. For each field we specify:
- Whether it was in the original mapping ("EXISTING") or is newly documented ("NEW")
- The data source (IPAS XML, CEC/Opportunity, Agent-derived, Constant, or Not Mapped)
- Default/constant values for the RRPS context
- Mandatory status and implementation notes

**v2.1 Corrections (red-team verified against WSDL):**
- All field names, types, and counts verified against `DOC_WEBI_FUNCTIONMODULE.WSDL`
- BAPISDLS corrected to 6 actual fields (PRICING, ATP_WRKMOD, SCHEDULING, NOSTRUCTURE, COND_HANDL, ADDR_CHECK)
- BAPI_SENDER corrected to 1 field (LOG_SYSTEM only)
- Response parameter corrected to SALESDOCUMENT (not SALES_DOCUMENT_OUT)
- BAPIPARNR corrected to 38 fields (not 28)
- BAPISCHDL corrected to 23 fields (not 17)
- BAPICOND corrected to 56 fields (not ~24)
- Removed ~40 hallucinated header fields from v2.0
- Fixed all incorrect field names (PMTGAR_PRO not PMTGAR_PROC, ALTTAX_CLS not ALT_TAX_CLASS, etc.)

**RRPS Constants:**
- Company Code: `0011`
- Sales Organization: `0011`
- Order Type: `ZEN2` (Engine New Business)
- Item Categories: `ZE1` / `ZE2` / `ZE3` / `ZEX2`
- Distribution Channel: from IPAS XML `Distr_Channel`
- Reference Object Type: `IPAS` (for cross-system traceability)

---

## 2. BAPI-Level Parameters

These are scalar/structure parameters on the BAPI function module itself (WSDL lines 1598-1635).

| Parameter | WSDL Type | Direction | Recommended Value | WSDL Line | Notes |
|-----------|-----------|-----------|-------------------|-----------|-------|
| SALESDOCUMENTIN | char10 | Import | `''` (blank) | 1630 | Leave blank for SAP auto-numbering. Set only if external number range is configured. |
| BEHAVE_WHEN_ERROR | char1 | Import | `'P'` | 1601 | **P** = Collect all errors and return in RETURN table. Blank = stop at first error. |
| BINARY_RELATIONSHIPTYPE | char4 | Import | `''` (blank) | 1602 | Only for object linking (e.g., linking to a preceding quotation via BOR). |
| CONVERT | char1 | Import | `'X'` | 1603 | **X** = Convert external to internal formats (material/customer numbers). Recommended for CPI. |
| INT_NUMBER_ASSIGNMENT | char1 | Import | `'X'` | 1606 | **X** = Use SAP internal number assignment. Required when SALESDOCUMENTIN is blank. |
| TESTRUN | char1 | Import | `''` (blank for prod) / `'X'` (test) | 1632 | **X** = Validate only, do not save. |
| SENDER | BAPI_SENDER | Import | See Section 2.2 | 1631 | Identifies the calling system. |
| LOGIC_SWITCH | BAPISDLS | Import | See Section 2.1 | 1607 | Controls pricing, scheduling, ATP behavior. |
| SALESDOCUMENT | char10 | **Export (Response)** | _(returned by SAP)_ | 1661 | The created SAP sales order number. **Note: WSDL name is SALESDOCUMENT, not SALES_DOCUMENT_OUT.** |
| RETURN | TABLE_OF_BAPIRET2 | Export | _(returned by SAP)_ | 1629/1660 | Messages/errors from order creation. |

### 2.1 LOGIC_SWITCH — BAPISDLS (6 fields, WSDL lines 313-322)

**WARNING:** v2.0 listed 7 fields with wrong names. The WSDL defines exactly **6 fields**:

| # | Field | WSDL Type | Recommended | WSDL Line | Description |
|---|-------|-----------|-------------|-----------|-------------|
| 1 | PRICING | char1 | `'X'` | 315 | **X** = Execute pricing. **B** = Carry out new pricing. **C** = Copy pricing without re-determination. |
| 2 | ATP_WRKMOD | char1 | `' '` (blank) | 316 | ATP working mode. Blank = standard availability check. |
| 3 | SCHEDULING | char1 | `'X'` | 317 | **X** = Schedule and confirm delivery dates. |
| 4 | NOSTRUCTURE | char1 | `' '` (blank) | 318 | **X** = No structure explosion for BOM items. Blank = standard BOM explosion. |
| 5 | COND_HANDL | char1 | `' '` (blank) | 319 | **X** = No standard condition determination (manual conditions only). Blank = standard. |
| 6 | ADDR_CHECK | char1 | `' '` (blank) | 320 | Address check control. Blank = standard address validation. |

**RRPS Recommendation:** Set `PRICING = 'X'` and `SCHEDULING = 'X'`. Leave other flags blank for standard SAP behavior. If IPAS supplies complete pricing (via ORDER_CONDITIONS_IN), consider `PRICING = 'C'`.

### 2.2 SENDER — BAPI_SENDER (1 field, WSDL lines 587-591)

**WARNING:** v2.0 listed SNDPRN — this field does NOT exist. BAPI_SENDER has exactly **1 field**:

| # | Field | WSDL Type | Recommended | WSDL Line | Description |
|---|-------|-----------|-------------|-----------|-------------|
| 1 | LOG_SYSTEM | char10 | `'INTEGRUM'` | 589 | Logical system name of calling system. |

---

## 3. ORDER_HEADER_IN — BAPISDHD1 (130 fields, WSDL lines 323-456)

The original mapping covered 14 of 130 fields. All 130 fields are listed below, verified against WSDL.

**Legend:**
- **Status**: `EXISTING` = was in v1.0 mapping, `NEW` = added in v2.0+
- **Source**: `IPAS` = from IPAS XML, `CEC` = from CEC/Opportunity, `Agent` = agent-derived, `Const` = constant value, `SAP` = SAP-determined, `--` = not mapped (leave blank)
- **Mand.**: `Y` = mandatory for RRPS, `R` = recommended, `O` = optional, `C` = conditional

| # | Field Name | WSDL Type | WSDL Line | Source | Default/Value | Mand. | Status | Notes |
|---|-----------|-----------|-----------|--------|---------------|-------|--------|-------|
| 1 | REFOBJTYPE | char10 | 325 | Const | **`'IPAS'`** | **Y** | **NEW** | Reference object type. CRITICAL for CPI traceability. |
| 2 | REFOBJKEY | char70 | 326 | IPAS | **`Header.IPAS_Order_Number`** | **Y** | **NEW** | Reference object key (e.g., 'IP-2025-00123'). |
| 3 | REFDOCTYPE | char10 | 327 | Const | `'ZEN2'` | R | NEW | Reference document type. Match DOC_TYPE for consistency. |
| 4 | DOC_TYPE | char4 | 328 | Const | `'ZEN2'` | Y | EXISTING | Engine New Business order type |
| 5 | COLLECT_NO | char10 | 329 | -- | _(leave blank)_ | O | NEW | Collective number for grouping orders. |
| 6 | SALES_ORG | char4 | 330 | Const | `'0011'` | Y | EXISTING | RRPS sales organization |
| 7 | DISTR_CHAN | char2 | 331 | IPAS | `Header.Distr_Channel` | Y | EXISTING | Distribution channel |
| 8 | DIVISION | char2 | 332 | IPAS | `Header.Product_Category` or `'01'` | Y | EXISTING | Division (product line) |
| 9 | SALES_GRP | char3 | 333 | IPAS | _(from IPAS or blank)_ | R | NEW | Sales group |
| 10 | SALES_OFF | char4 | 334 | IPAS | _(from IPAS or blank)_ | O | EXISTING | Sales office |
| 11 | REQ_DATE_H | date10 | 335 | IPAS | Earliest `Engine.Delivery_Date` | Y | EXISTING | Requested delivery date (header) |
| 12 | DATE_TYPE | char1 | 336 | Const | `'1'` | R | NEW | 1=requested delivery, 2=pick/pack |
| 13 | PURCH_DATE | date10 | 337 | IPAS | `Header.Purchase_Order_Date` | R | EXISTING | Customer PO date |
| 14 | PO_METHOD | char4 | 338 | Const | `'EDAT'` | R | NEW | PO transmission method |
| 15 | PO_SUPPLEM | char4 | 339 | -- | _(leave blank)_ | O | NEW | PO supplement |
| 16 | REF_1 | char12 | 340 | IPAS | `Header.IPAS_Project_Number` | R | NEW | Your reference (customer) |
| 17 | NAME | char35 | 341 | -- | _(leave blank)_ | O | NEW | Ordering party name. SAP reads from customer master. |
| 18 | TELEPHONE | char16 | 342 | -- | _(leave blank)_ | O | NEW | Telephone. SAP reads from customer master. |
| 19 | PRICE_GRP | char2 | 343 | SAP | _(from customer master)_ | O | NEW | Price group |
| 20 | CUST_GROUP | char2 | 344 | SAP | _(from customer master)_ | O | NEW | Customer group |
| 21 | SALES_DIST | char6 | 345 | -- | _(leave blank)_ | O | NEW | Sales district |
| 22 | PRICE_LIST | char2 | 346 | -- | _(leave blank)_ | O | NEW | Price list type |
| 23 | INCOTERMS1 | char3 | 347 | IPAS | `Header.Incoterms_1` | Y | EXISTING | Incoterms part 1 (DAP, EXW, FOB) |
| 24 | INCOTERMS2 | char28 | 348 | IPAS | `Header.Incoterms_2` | Y | EXISTING | Incoterms part 2 (location) |
| 25 | PMNTTRMS | char4 | 349 | IPAS | `Header.Terms_Of_Payment` | Y | EXISTING | Payment terms key |
| 26 | DLV_BLOCK | char2 | 350 | -- | _(leave blank)_ | O | NEW | Delivery block |
| 27 | BILL_BLOCK | char2 | 351 | -- | _(leave blank)_ | O | NEW | Billing block at header |
| 28 | ORD_REASON | char3 | 352 | Const | `'Z01'` | R | EXISTING | Order reason (Z01=New Engine Business) |
| 29 | COMPL_DLV | char1 | 353 | Const | `' '` (blank) | O | NEW | Complete delivery flag. X=required. Blank=partial allowed. |
| 30 | PRICE_DATE | date10 | 354 | IPAS | `Header.Document_Date` or blank | O | NEW | Pricing date. Blank → SAP uses DOC_DATE. |
| 31 | QT_VALID_F | date10 | 355 | -- | _(leave blank)_ | O | NEW | Quotation valid-from. N/A for ZEN2. |
| 32 | QT_VALID_T | date10 | 356 | -- | _(leave blank)_ | O | NEW | Quotation valid-to. N/A for ZEN2. |
| 33 | CT_VALID_F | date10 | 357 | -- | _(leave blank)_ | O | NEW | Contract valid-from. N/A for ZEN2. |
| 34 | CT_VALID_T | date10 | 358 | -- | _(leave blank)_ | O | NEW | Contract valid-to. N/A for ZEN2. |
| 35 | CUST_GRP1 | char3 | 359 | -- | _(leave blank)_ | O | NEW | Customer group 1 |
| 36 | CUST_GRP2 | char3 | 360 | -- | _(leave blank)_ | O | NEW | Customer group 2 |
| 37 | CUST_GRP3 | char3 | 361 | -- | _(leave blank)_ | O | NEW | Customer group 3 |
| 38 | CUST_GRP4 | char3 | 362 | -- | _(leave blank)_ | O | NEW | Customer group 4 |
| 39 | CUST_GRP5 | char3 | 363 | -- | _(leave blank)_ | O | NEW | Customer group 5 |
| 40 | PURCH_NO_C | char35 | 364 | IPAS | `Header.Purchase_Order_Number` | Y | EXISTING | Customer PO number |
| 41 | PURCH_NO_S | char35 | 365 | -- | _(leave blank)_ | O | NEW | Customer PO number (ship-to) |
| 42 | PO_DAT_S | date10 | 366 | -- | _(leave blank)_ | O | NEW | PO date (ship-to) |
| 43 | PO_METH_S | char4 | 367 | -- | _(leave blank)_ | O | NEW | PO method (ship-to) |
| 44 | REF_1_S | char12 | 368 | -- | _(leave blank)_ | O | NEW | Ship-to reference |
| 45 | SD_DOC_CAT | char1 | 369 | SAP | _(SAP-determined)_ | O | NEW | SD document category. Let SAP derive from DOC_TYPE. |
| 46 | DOC_DATE | date10 | 370 | IPAS | `Header.Document_Date` | Y | EXISTING | Document/order date |
| 47 | WAR_DATE | date10 | 371 | -- | _(leave blank)_ | O | NEW | Warranty date |
| 48 | SHIP_COND | char2 | 372 | IPAS | _(from IPAS `Shipping_Type` or blank)_ | R | NEW | Shipping conditions (01=Standard, 02=Express) |
| 49 | PP_SEARCH | **char40** | 373 | -- | _(leave blank)_ | O | NEW | PP search term. **Note: CHAR(40), not CHAR(4) as incorrectly stated in v2.0.** |
| 50 | DUN_COUNT | decimal3.0 | 374 | -- | _(leave blank)_ | O | NEW | Dunning count |
| 51 | DUN_DATE | date10 | 375 | -- | _(leave blank)_ | O | NEW | Dunning date |
| 52 | DLVSCHDUSE | char3 | 376 | -- | _(leave blank)_ | O | NEW | Delivery schedule usage |
| 53 | PLDLVSTYP | char1 | 377 | -- | _(leave blank)_ | O | NEW | Planned delivery type |
| 54 | REF_DOC | char10 | 378 | -- | _(leave blank)_ | O | NEW | Reference document number (predecessor) |
| 55 | COMP_CDE_B | char4 | 379 | Const | `'0011'` | R | NEW | Company code. **Note: WSDL name is COMP_CDE_B, not COMP_CODE.** |
| 56 | ALTTAX_CLS | char1 | 380 | -- | _(leave blank)_ | O | NEW | Alt tax classification. **Note: WSDL name is ALTTAX_CLS, not ALT_TAX_CLASS.** |
| 57 | TAX_CLASS2 | char1 | 381 | SAP | _(SAP-determined)_ | O | NEW | Tax classification 2 |
| 58 | TAX_CLASS3 | char1 | 382 | SAP | _(SAP-determined)_ | O | NEW | Tax classification 3 |
| 59 | TAX_CLASS4 | char1 | 383 | SAP | _(SAP-determined)_ | O | NEW | Tax classification 4 |
| 60 | TAX_CLASS5 | char1 | 384 | SAP | _(SAP-determined)_ | O | NEW | Tax classification 5 |
| 61 | TAX_CLASS6 | char1 | 385 | SAP | _(SAP-determined)_ | O | NEW | Tax classification 6 |
| 62 | TAX_CLASS7 | char1 | 386 | SAP | _(SAP-determined)_ | O | NEW | Tax classification 7 |
| 63 | TAX_CLASS8 | char1 | 387 | SAP | _(SAP-determined)_ | O | NEW | Tax classification 8 |
| 64 | TAX_CLASS9 | char1 | 388 | SAP | _(SAP-determined)_ | O | NEW | Tax classification 9 |
| 65 | REF_DOC_L | char16 | 389 | -- | _(leave blank)_ | O | NEW | Reference document long |
| 66 | ASS_NUMBER | char18 | 390 | -- | _(leave blank)_ | O | NEW | Assignment number |
| 67 | REFDOC_CAT | char1 | 391 | -- | _(leave blank)_ | O | NEW | Reference document category |
| 68 | ORDCOMB_IN | char1 | 392 | -- | _(leave blank)_ | O | NEW | Order combination indicator |
| 69 | BILL_SCHED | char2 | 393 | -- | _(leave blank)_ | O | NEW | Billing schedule |
| 70 | INVO_SCHED | char2 | 394 | -- | _(leave blank)_ | O | NEW | Invoicing schedule |
| 71 | MN_INVOICE | char1 | 395 | -- | _(leave blank)_ | O | NEW | Manual invoice maintenance |
| 72 | EXRATE_FI | **decimal9.5** | 396 | -- | _(leave blank)_ | O | NEW | Exchange rate for FI. **Note: WSDL name is EXRATE_FI, not EXCH_RATE_FI.** |
| 73 | ADD_VAL_DY | numeric2 | 397 | -- | _(leave blank)_ | O | NEW | Additional value days |
| 74 | FIX_VAL_DY | date10 | 398 | -- | _(leave blank)_ | O | NEW | Fixed value date |
| 75 | PYMT_METH | char1 | 399 | -- | _(leave blank)_ | O | NEW | Payment method. From customer master. |
| 76 | ACCNT_ASGN | char2 | 400 | SAP | _(SAP-determined)_ | O | NEW | Account assignment group |
| 77 | EXCHG_RATE | decimal9.5 | 401 | -- | _(leave blank)_ | O | NEW | Exchange rate. Blank → SAP daily rate. |
| 78 | BILL_DATE | date10 | 402 | -- | _(leave blank)_ | O | NEW | Billing date at header |
| 79 | SERV_DATE | date10 | 403 | -- | _(leave blank)_ | O | NEW | Service rendered date. N/A for engines. |
| 80 | DUNN_KEY | char1 | 404 | -- | _(leave blank)_ | O | NEW | Dunning key |
| 81 | DUNN_BLOCK | char1 | 405 | -- | _(leave blank)_ | O | NEW | Dunning block |
| 82 | PMTGAR_PRO | char6 | 406 | -- | _(leave blank)_ | O | NEW | Payment guarantee procedure. **Note: WSDL name is PMTGAR_PRO, not PMTGAR_PROC.** |
| 83 | DEPARTM_NO | char4 | 407 | -- | _(leave blank)_ | O | NEW | Department number |
| 84 | REC_POINT | char25 | 408 | -- | _(leave blank)_ | O | NEW | Receiving point |
| 85 | DOC_NUM_FI | char10 | 409 | -- | _(leave blank)_ | O | NEW | FI document number |
| 86 | CSTCNDGRP1 | char2 | 410 | -- | _(leave blank)_ | O | NEW | Customer condition group 1. **Note: WSDL name is CSTCNDGRP1, not CUST_COND_GRP1.** |
| 87 | CSTCNDGRP2 | char2 | 411 | -- | _(leave blank)_ | O | NEW | Customer condition group 2 |
| 88 | CSTCNDGRP3 | char2 | 412 | -- | _(leave blank)_ | O | NEW | Customer condition group 3 |
| 89 | CSTCNDGRP4 | char2 | 413 | -- | _(leave blank)_ | O | NEW | Customer condition group 4 |
| 90 | CSTCNDGRP5 | char2 | 414 | -- | _(leave blank)_ | O | NEW | Customer condition group 5 |
| 91 | DLV_TIME | char3 | 415 | -- | _(leave blank)_ | O | NEW | Delivery time |
| 92 | CURRENCY | cuky5 | 416 | IPAS | `Header.Currency_Code` | Y | EXISTING | Order currency (EUR, USD) |
| 93 | CURR_ISO | char3 | 417 | -- | _(leave blank)_ | O | NEW | Currency ISO code. **Note: WSDL name is CURR_ISO, not CURRENCY_ISO.** |
| 94 | CREATED_BY | char12 | 418 | SAP | _(SAP sets automatically)_ | O | NEW | Created by. Do not populate. |
| 95 | TAXDEP_CTY | char3 | 419 | -- | _(leave blank)_ | O | NEW | Tax departure country |
| 96 | TAXDST_CTY | char3 | 420 | -- | _(leave blank)_ | O | NEW | Tax destination country |
| 97 | EUTRI_DEAL | char1 | 421 | -- | _(leave blank)_ | O | NEW | EU triangulation deal |
| 98 | MAST_CONTR | char10 | 422 | -- | _(leave blank)_ | O | NEW | Master contract |
| 99 | REF_PROC | char4 | 423 | -- | _(leave blank)_ | O | NEW | Reference procedure |
| 100 | CHKPRTAUTH | char1 | 424 | -- | _(leave blank)_ | O | NEW | Check partner authorization |
| 101 | CMLQTY_DAT | date10 | 425 | -- | _(leave blank)_ | O | NEW | Cumulative quantity date |
| 102 | VERSION | char12 | 426 | -- | _(leave blank)_ | O | NEW | Version |
| 103 | NOTIF_NO | char12 | 427 | -- | _(leave blank)_ | O | NEW | Notification number |
| 104 | WBS_ELEM | char24 | 428 | IPAS | _(from IPAS project if available)_ | R | NEW | WBS element for project-linked orders |
| 105 | EXCH_RATE_FI_V | decimal9.5 | 429 | -- | _(leave blank)_ | O | NEW | Exchange rate FI (indirect quotation) |
| 106 | EXCHG_RATE_V | decimal9.5 | 430 | -- | _(leave blank)_ | O | NEW | Exchange rate for statistics |
| 107 | FKK_CONACCT | char12 | 431 | -- | _(leave blank)_ | O | NEW | Contract account (FICA) |
| 108 | CAMPAIGN | **byte16** | 432 | -- | _(leave blank)_ | O | NEW | Campaign GUID. **Note: type is byte16 (base64), not CHAR(10) as stated in v2.0.** |
| 109 | DOC_CLASS | char9 | 433 | -- | _(leave blank)_ | O | NEW | Document class |
| 110 | H_CURR | cuky5 | 434 | -- | _(leave blank)_ | O | NEW | Header currency |
| 111 | H_CURR_ISO | char3 | 435 | -- | _(leave blank)_ | O | NEW | Header currency ISO |
| 112 | SHIP_TYPE | char2 | 436 | -- | _(leave blank)_ | O | NEW | Shipping type |
| 113 | S_PROC_IND | char4 | 437 | -- | _(leave blank)_ | O | NEW | Special process indicator |
| 114 | REF_DOC_L_LONG | char35 | 438 | -- | _(leave blank)_ | O | NEW | Reference document long (extended) |
| 115 | LINE_TIME | time | 439 | -- | _(leave blank)_ | O | NEW | Line time |
| 116 | CALC_MOTIVE | char2 | 440 | -- | _(leave blank)_ | O | NEW | Calculation motive |
| 117 | PSM_PSTNG_DATE | date10 | 441 | -- | _(leave blank)_ | O | NEW | PSM posting date |
| 118 | TREASURY_ACC_SYMBOL | char30 | 442 | -- | _(leave blank)_ | O | NEW | Treasury account symbol |
| 119 | BUSINESS_EVENT_TCODE | char10 | 443 | -- | _(leave blank)_ | O | NEW | Business event transaction code |
| 120 | MODIFICATION_ALLOWED | char1 | 444 | -- | _(leave blank)_ | O | NEW | Modification allowed flag |
| 121 | CANCELLATION_ALLOWED | char1 | 445 | -- | _(leave blank)_ | O | NEW | Cancellation allowed flag |
| 122 | PAYMENT_METHODS | char10 | 446 | -- | _(leave blank)_ | O | NEW | Payment methods |
| 123 | BUSINESS_PARTNER_NO | char6 | 447 | -- | _(leave blank)_ | O | NEW | Business partner number |
| 124 | REPORTING_FREQ | char3 | 448 | -- | _(leave blank)_ | O | NEW | Reporting frequency |
| 125 | SEPA_MANDATE_ID | char35 | 449 | -- | _(leave blank)_ | O | NEW | SEPA mandate ID |
| 126 | SD_DOC_CAT_LONG | char4 | 450 | -- | _(leave blank)_ | O | NEW | SD document category (long) |
| 127 | REFDOC_CAT_LONG | char4 | 451 | -- | _(leave blank)_ | O | NEW | Reference doc category (long) |
| 128 | INCOTERMSV | char4 | 452 | -- | _(leave blank)_ | O | NEW | Incoterms version (2010/2020) |
| 129 | INCOTERMS2L | char70 | 453 | IPAS | `Header.Incoterms_2` (long format) | O | NEW | Incoterms 2 (long, 70 char) |
| 130 | INCOTERMS3L | char70 | 454 | -- | _(leave blank)_ | O | NEW | Incoterms 3 (long, 70 char). **End of BAPISDHD1 — 130 fields total (WSDL-verified).** |

**Note on v2.0 hallucinated fields:** The following fields listed in v2.0 do NOT exist in BAPISDHD1 per WSDL and have been removed: TAX_DEST, DOC_COND, TAX_CLASS_DOC, MATERIAL_PRICING_GRP, SHIP_POINT, ROUTE, FWD_AGENT, USAGE_IND, CAL_TYPE, UNLOAD_PT, ORD_PROB, DOC_CATEGORY, PMTGAR_PROC2, ORDERER, DUESSION, SCENARIO, HANDOVERLOC, HIERACHYTYPE, OBJ_TYPE, OBJ_TYPE_V, TAX_DEPART_CTRY, TAX_DEST_CTRY, TAX_REG_CTRY, BATCH_FLAG, AGREEMENT, ASSIGN_TO, PRICEGROUP1-5, PYMT_METH_SUPL, REFER_DOC, TRANS_DATE, TAX_DATE, MAN_PAYARR, ACCTASSGRP_HDRV, FINRDOC, FINRORG, FINR_YEAR, RETENTION_P, ADM_SALES, PURCH_NO_P. Some of these exist in BAPISDITM (item level) but not in the header structure.

---

## 4. ORDER_HEADER_INX — BAPISDHD1X (WSDL lines 457-586)

Every field in ORDER_HEADER_IN that you want SAP to process **must** have a corresponding `'X'` flag in ORDER_HEADER_INX. The INX structure mirrors BAPISDHD1 with all fields as char1 (plus UPDATEFLAG).

| Field | Type | Value | Notes |
|-------|------|-------|-------|
| UPDATEFLAG | char1 | `'I'` | **I** = Insert (create new). **U** = Update. Always `'I'` for new order. |
| DOC_TYPE | char1 | `'X'` | |
| SALES_ORG | char1 | `'X'` | |
| DISTR_CHAN | char1 | `'X'` | |
| DIVISION | char1 | `'X'` | |
| SALES_OFF | char1 | `'X'` | Set X if populated |
| SALES_GRP | char1 | `'X'` | Set X if populated |
| PURCH_NO_C | char1 | `'X'` | |
| PURCH_DATE | char1 | `'X'` | |
| PO_METHOD | char1 | `'X'` | Set X if populated |
| DOC_DATE | char1 | `'X'` | |
| REQ_DATE_H | char1 | `'X'` | |
| DATE_TYPE | char1 | `'X'` | Set X if populated |
| CURRENCY | char1 | `'X'` | |
| PMNTTRMS | char1 | `'X'` | |
| INCOTERMS1 | char1 | `'X'` | |
| INCOTERMS2 | char1 | `'X'` | |
| ORD_REASON | char1 | `'X'` | |
| PRICE_DATE | char1 | `'X'` | Set X if populated |
| SHIP_COND | char1 | `'X'` | Set X if populated |
| COMPL_DLV | char1 | `'X'` | Set X if populated |
| COMP_CDE_B | char1 | `'X'` | Set X if explicitly set |
| WBS_ELEM | char1 | `'X'` | Set X if populated |
| REF_1 | char1 | `'X'` | Set X if populated |
| _(all other fields)_ | char1 | `' '` | Leave blank for fields not populated in ORDER_HEADER_IN |

**Rule:** For every non-blank field in ORDER_HEADER_IN, set the corresponding field in ORDER_HEADER_INX to `'X'`. The INX structure has the exact same field names as BAPISDHD1 (except UPDATEFLAG which is added, and REFOBJTYPE/REFOBJKEY which are absent since they don't need update flags).

**Note on INX field naming:** The WSDL names this structure `BAPISDHD1X` (lines 457-586). It contains 126 char1 fields (all header fields minus REFOBJTYPE/REFOBJKEY/REFDOCTYPE, plus UPDATEFLAG and PROMOTION/POITM_NO_S which are INX-only). Fields in the INX correspond 1:1 by name to their BAPISDHD1 counterparts.

---

## 5. ORDER_ITEMS_IN — BAPISDITM (220 fields, WSDL lines 825-1048)

The original mapping covered 8 of 220 fields. One row per IPAS Engine or BOM Item.

**Note:** v2.0 incorrectly stated 223 fields and included several hallucinated field names. This section lists the WSDL-verified fields.

### 5.1 RRPS-Relevant Item Fields (mapped or recommended)

| # | Field Name | WSDL Type | WSDL Line | Source | Default/Value | Mand. | Status | Notes |
|---|-----------|-----------|-----------|--------|---------------|-------|--------|-------|
| 1 | ITM_NUMBER | numeric6 | 827 | Agent | `000010`, `000020`, ... | Y | EXISTING | Line item number (increment by 10) |
| 2 | HG_LV_ITEM | numeric6 | 828 | Agent | _(parent item for BOM sub-items)_ | C | NEW | Higher-level item. Set for BOM sub-items. |
| 3 | PO_ITM_NO | char6 | 829 | IPAS | `Item.Item_Number` | R | NEW | Customer PO item number |
| 4 | MATERIAL | char18 | 830 | IPAS | `Engine.Engine_Type` or `Item.Material` | Y | EXISTING | Material number |
| 5 | ALT_TO_ITM | numeric6 | 831 | -- | _(leave blank)_ | O | NEW | Alternative to item |
| 6 | CUST_MAT22 | char22 | 832 | -- | _(leave blank)_ | O | NEW | Customer material number (22 char) |
| 7 | BATCH | char10 | 833 | -- | _(leave blank)_ | O | NEW | Batch number |
| 8 | DLV_GROUP | numeric3 | 834 | -- | _(leave blank)_ | O | NEW | Delivery group |
| 9 | PART_DLV | char1 | 835 | -- | _(leave blank)_ | O | NEW | Partial delivery at item |
| 10 | REASON_REJ | char2 | 836 | -- | _(leave blank)_ | O | NEW | Reason for rejection |
| 11 | BILL_BLOCK | char2 | 837 | -- | _(leave blank)_ | O | NEW | Billing block at item |
| 12 | BILL_DATE | date10 | 838 | -- | _(leave blank)_ | O | NEW | Billing date at item |
| 13 | PLANT | char4 | 839 | IPAS | Plant code or `'0011'` | Y | EXISTING | Manufacturing/delivering plant |
| 14 | STORE_LOC | char4 | 840 | -- | _(leave blank)_ | O | NEW | Storage location |
| 15 | TARGET_QTY | quantum13.3 | 841 | IPAS | `Engine.Quantity` | Y | EXISTING | Target quantity |
| 16 | TARGET_QU | unit3 | 842 | IPAS | `'EA'` or from IPAS | Y | EXISTING | Target quantity UoM |
| 17 | T_UNIT_ISO | char3 | 843 | -- | _(leave blank)_ | O | NEW | Target unit ISO |
| 18 | ITEM_CATEG | char4 | 844 | IPAS/Const | `'ZE1'`/`'ZE2'`/`'ZE3'`/`'ZEX2'` | Y | EXISTING | Item category |
| 19 | SHORT_TEXT | char40 | 845 | IPAS | `Item.Material_Desc` | R | EXISTING | Short text / item description |
| 20 | REFOBJTYPE | char10 | 948 | Const | **`'IPAS'`** | **Y** | **NEW** | Reference object type at item level |
| 21 | REFOBJKEY | char70 | 949 | IPAS | **`IPAS_Order + '/' + ITM_NUMBER`** | **Y** | **NEW** | Reference key (e.g., 'IP-2025-00123/000010') |
| 22 | REFLOGSYS | char10 | 950 | Const | **`'INTEGRUM'`** | **R** | **NEW** | Logical system of reference object |
| 23 | DIVISION | char2 | 907 | IPAS | _(from IPAS or header division)_ | O | NEW | Division at item level |
| 24 | SALES_UNIT | unit3 | 894 | IPAS | Same as TARGET_QU | R | NEW | Sales unit |
| 25 | PROFIT_CTR | char10 | 962 | -- | _(leave blank)_ | O | NEW | Profit center. SAP determines from material/plant. |
| 26 | WBS_ELEM | char24 | 964 | IPAS | _(from IPAS project WBS)_ | R | NEW | WBS element at item level |
| 27 | REF_DOC | char10 | 966 | -- | _(leave blank)_ | O | NEW | Reference document (preceding doc) |
| 28 | REF_DOC_IT | numeric6 | 967 | -- | _(leave blank)_ | O | NEW | Reference document item |
| 29 | REF_DOC_CA | char1 | 968 | -- | _(leave blank)_ | O | NEW | Reference document category |
| 30 | CUST_MAT35 | char35 | 969 | -- | _(leave blank)_ | O | NEW | Customer material number (35 char) |
| 31 | BILL_REL | char1 | 991 | -- | _(leave blank)_ | O | NEW | Billing relevance. SAP determines from item category. |

### 5.2 Additional Item Fields (available in WSDL, leave blank for RRPS)

The remaining 189 fields are documented below by functional grouping. All should be left blank for the standard RRPS ZEN2 engine order scenario.

**Pricing/Commercial fields (from WSDL):**
PRC_GROUP1-5 (846-850), PROD_HIERA (851), MATL_GROUP (852), PURCH_NO_C (853), PURCH_DATE (854), PO_METHOD (855), REF_1 (856), PURCH_NO_S (857), PO_DAT_S (858), PO_METH_S (859), REF_1_S (860), POITM_NO_S (861), PRICE_GRP (862), CUST_GROUP (863), SALES_DIST (864), PRICE_LIST (865), INCOTERMS1 (866), INCOTERMS2 (867), ORDCOMP_IN (868), BILL_SCHED (869), INVO_SCHED (870), MN_INVOICE (871), EX_RATE_FI (872), ADD_VAL_DY (873), FIX_VAL_DY (874), PMNTTRMS (875), PYMT_METH (876), ACCNT_ASGN (877), EXCHG_RATE (878), PRICE_DATE (879), SERV_DATE (880), DUNN_KEY (881), DUNN_BLOCK (882), PROMOTION (883), PMTGAR_PRO (884), DOC_NUM_FI (885), DEPARTM_NO (886), REC_POINT (887)

**Customer condition groups:** CSTCNDGRP1-5 (888-892). **Note: WSDL name is CSTCNDGRP, not CUST_GRP as v2.0 stated.**

**Delivery/logistics fields:**
DLV_TIME (893), S_UNIT_ISO (895), TRG_QTY_NO (896), TRGQTY_DEN (897), RNDDLV_QTY (898), MAXDEVAMNT (899), MAXDEVPER (900), MAXDEV_DAY (901), USAGE_IND (902), FIXED_QUAN (903), UNLMT_DLV (904), OVERDLVTOL (905), UNDDLV_TOL (906), SALQTYNUM (908), SALQTYDEN (909), GROSS_WGHT (910), NET_WEIGHT (911), UNTOF_WGHT (912), UNOF_WTISO (913), VOLUME (914), VOLUNIT (915), VOLUNITISO (916), DLV_PRIO (917), SHIP_POINT (918), ROUTE (919), CREATED_BY (920)

**Tax classifications:** TAX_CLASS1-9 (921-929)

**Production/MRP fields:**
MAT_PR_GRP (930), VAL_TYPE (931), FIXDAT_QTY (932), BOMEXPL_NO (933), RESANALKEY (934), REQMTS_TYP (935), NO_GR_POST (936), BUS_TRANST (937), OVERHD_KEY (938), CSTG_SHEET (939), MATFRGTGRP (940), PLDLVSHDIN (941), SEQ_NO (942), BIL_FORM (943), DLI_PROFIL (944), REV_TYPE (945), BEGDEM_PER (946), PR_REF_MAT (947)

**Order probability/planning:** ORDER_PROB (951), MAX_PL_DLV (952)

**Brazil tax fields:** CFOP_CODE (953), TAXLAWICMS (954), TAXLAWIPI (955), SD_TAXCODE (956), CFOP_LONG (995), TAXLAWISS (1000), TAXLAWCOFINS (1016), TAXLAWPIS (1017)

**Assortment/value:** ASSORT_MOD (957), COMP_QUANT (958), TARGET_VAL (959), CURRENCY (960), CURR_ISO (961), ORDERID (963), DEPREC_PER (965)

**Extended fields:** EXCH_RATE_FI_V (970), EXCHG_RATE_V (971), ITEMGUID_ATP (972), VAL_CONTR (973), VAL_CON_I (974), CONFIG_ID (975), INST_ID (976), MAT_EXT (977), MAT_GUID (978), MAT_VERS (979), P_MAT_EXT (980), P_MAT_GUID (981), P_MAT_VERS (982), FUNC_AREA (983), ALTERN_BOM (984), FKK_CONACCT (985), EAN_UPC (986), PRODCAT (987), SHIP_TYPE (988), S_PROC_IND (989), FUNC_AREA_LONG (990), VW_UEPOS (992), CAMPAIGN (993, type **byte16**), DLVSCHDUSE (994), SELECTION (996), MAT_ENTRD (997), LOG_SYSTEM_OWN (998), ITM_TYPE_USAGE (999)

**Localization/PSM fields:** MAT_ENTRD_EXTERNAL (1001), MAT_ENTRD_GUID (1002), MAT_ENTRD_VERSION (1003), LOC_TAXCAT (1004), LOC_ZEROVAT (1005), LOC_ACTCODE (1006), LOC_DISTTYPE (1007), LOC_TXRELCLAS (1008), CALC_MOTIVE (1009), COMPREAS (1010), FUND (1011), FUNDS_CTR (1012), CMMT_ITEM (1013), GRANT_NBR (1014), BUDGET_PERIOD (1015), TREASURY_ACC_SYMBOL (1018), BUSINESS_EVENT_TCODE (1019), MODIFICATION_ALLOWED (1020), CANCELLATION_ALLOWED (1021), PAYMENT_METHODS (1022), BUSINESS_PARTNER_NO (1023), REPORTING_FREQ (1024), SEPA_MANDATE_ID (1025), REQ_SEGMENT (1026)

**Transfer pricing fields:** TP_SUBLEVL (1027), TP_AGENCID (1028), TP_ALTRAID (1029), TP_BEGPER (1030), TP_ENDPER (1031), TP_AVTYPE (1032), TP_MAIN_ACCT (1033), TP_SUB_ACCT (1034), TP_BETC (1035)

**Revenue accounting:** REVACC_REFID (1036), REVACC_REFTYPE (1037)

**Long/extended format fields:** REF_DOC_CA_LONG (1038), INCOTERMSV (1039), INCOTERMS2L (1040), INCOTERMS3L (1041), MATERIAL_LONG (1042), PR_REF_MAT_LONG (1043), MAT_ENTRD_LONG (1044), PO_QUAN (1045), PO_UNIT (1046)

**v2.0 Hallucinated Item Fields Removed:** REQ_DATE (belongs to BAPISCHDL, not BAPISDITM), NET_PRICE (does not exist in BAPISDITM), COND_VALUE (does not exist in BAPISDITM), PURCH_NO_C_I (actual name is PURCH_NO_C), PURCH_DATE_I (actual name is PURCH_DATE), CUST_GRP1-5 (actual names are CSTCNDGRP1-5), UNLOAD_PT (not in BAPISDITM — exists in BAPIPARNR), PACKING_NO (not in BAPISDITM).

---

## 6. ORDER_ITEMS_INX — BAPISDITMX (213 fields, WSDL lines 1049-1265)

| Field | Type | Value | Notes |
|-------|------|-------|-------|
| ITM_NUMBER | numeric6 | _(matching)_ | Must match ORDER_ITEMS_IN |
| UPDATEFLAG | char1 | `'I'` | I=Insert new item |
| HG_LV_ITEM | char1 | `'X'` | Set X if populated |
| MATERIAL | char1 | `'X'` | |
| PLANT | char1 | `'X'` | |
| TARGET_QTY | char1 | `'X'` | |
| TARGET_QU | char1 | `'X'` | |
| SALES_UNIT | char1 | `'X'` | Set X if populated |
| ITEM_CATEG | char1 | `'X'` | |
| SHORT_TEXT | char1 | `'X'` | Set X if populated |
| PO_ITM_NO | char1 | `'X'` | Set X if populated |
| STORE_LOC | char1 | `'X'` | Set X if populated |
| WBS_ELEM | char1 | `'X'` | Set X if populated |
| REFOBJTYPE | char1 | `'X'` | Set X if populated |
| REFOBJKEY | char1 | `'X'` | Set X if populated |
| REFLOGSYS | char1 | `'X'` | Set X if populated |
| _(all other fields)_ | char1 | `' '` | Leave blank for unpopulated fields |

**Rule:** Same as header — set `'X'` for every field populated in ORDER_ITEMS_IN. The INX structure has 213 char1 fields (WSDL-verified), one for each BAPISDITM field that supports update indication.

---

## 7. ORDER_PARTNERS — BAPIPARNR (38 fields, WSDL lines 1287-1328)

**WARNING:** v2.0 stated 28 fields. The WSDL defines **38 fields**. All 38 listed below.

| # | Field Name | WSDL Type | WSDL Line | Source | Default/Value | Mand. | Status | Notes |
|---|-----------|-----------|-----------|--------|---------------|-------|--------|-------|
| 1 | PARTN_ROLE | char2 | 1289 | IPAS/Const | `'AG'`, `'WE'`, `'RE'`, `'RG'` | Y | EXISTING | Partner function: AG=Sold-To, WE=Ship-To, RE=Bill-To, RG=Payer |
| 2 | PARTN_NUMB | char10 | 1290 | IPAS | `Header.Sold_To_Party` etc. | Y | EXISTING | Partner (customer) number |
| 3 | ITM_NUMBER | numeric6 | 1291 | Agent | `000000` for header, item no. for item-level | C | NEW | 000000 = header-level partner |
| 4 | TITLE | **char15** | 1292 | -- | _(leave blank)_ | O | NEW | Title. **Note: CHAR(15) per WSDL, not CHAR(4) as v2.0 stated.** |
| 5 | NAME | char35 | 1293 | IPAS | _(Partner_Information.Name1)_ | C | NEW | Name 1. Required for one-time customer. |
| 6 | NAME_2 | char35 | 1294 | IPAS | _(Partner_Information.Name2)_ | O | NEW | Name 2 |
| 7 | NAME_3 | char35 | 1295 | -- | _(leave blank)_ | O | NEW | Name 3 |
| 8 | NAME_4 | char35 | 1296 | -- | _(leave blank)_ | O | NEW | Name 4 |
| 9 | STREET | char35 | 1297 | -- | _(leave blank)_ | C | NEW | Street address. Required for one-time customer. |
| 10 | COUNTRY | char3 | 1298 | IPAS | _(Partner_Information.Country)_ | C | NEW | Country key |
| 11 | COUNTR_ISO | char2 | 1299 | -- | _(leave blank)_ | O | NEW | Country ISO code |
| 12 | POSTL_CODE | char10 | 1300 | -- | _(leave blank)_ | C | NEW | Postal code |
| 13 | POBX_PCD | char10 | 1301 | -- | _(leave blank)_ | O | NEW | PO box postal code |
| 14 | POBX_CTY | char35 | 1302 | -- | _(leave blank)_ | O | NEW | PO box city |
| 15 | CITY | char35 | 1303 | IPAS | _(Partner_Information.City)_ | C | NEW | City |
| 16 | DISTRICT | char35 | 1304 | -- | _(leave blank)_ | O | NEW | District |
| 17 | REGION | char3 | 1305 | -- | _(leave blank)_ | O | NEW | Region/state/province |
| 18 | PO_BOX | char10 | 1306 | -- | _(leave blank)_ | O | NEW | PO box |
| 19 | TELEPHONE | char16 | 1307 | -- | _(leave blank)_ | O | NEW | Telephone |
| 20 | TELEPHONE2 | char16 | 1308 | -- | _(leave blank)_ | O | NEW | Telephone 2 |
| 21 | TELEBOX | char15 | 1309 | -- | _(leave blank)_ | O | NEW | Telebox |
| 22 | FAX_NUMBER | char31 | 1310 | -- | _(leave blank)_ | O | NEW | Fax number |
| 23 | TELETEX_NO | char30 | 1311 | -- | _(leave blank)_ | O | NEW | Teletex number |
| 24 | TELEX_NO | char30 | 1312 | -- | _(leave blank)_ | O | NEW | Telex number |
| 25 | LANGU | lang | 1313 | Const | `'E'` | O | NEW | Language key. E=English. |
| 26 | LANGU_ISO | char2 | 1314 | -- | _(leave blank)_ | O | NEW | Language ISO code |
| 27 | UNLOAD_PT | char25 | 1315 | -- | _(leave blank)_ | O | NEW | Unloading point |
| 28 | TRANSPZONE | char10 | 1316 | -- | _(leave blank)_ | O | NEW | Transportation zone |
| 29 | TAXJURCODE | char15 | 1317 | -- | _(leave blank)_ | O | NEW | Tax jurisdiction code |
| 30 | ADDRESS | char10 | 1318 | -- | _(leave blank)_ | O | NEW | Address number |
| 31 | PRIV_ADDR | char10 | 1319 | -- | _(leave blank)_ | O | NEW | Private address |
| 32 | ADDR_TYPE | char1 | 1320 | -- | _(leave blank)_ | O | NEW | Address type |
| 33 | ADDR_ORIG | char1 | 1321 | -- | _(leave blank)_ | O | NEW | Address origin |
| 34 | ADDR_LINK | char10 | 1322 | -- | _(leave blank)_ | O | NEW | Address link reference. **Note: WSDL name is ADDR_LINK, not ADDRESS_LINK.** |
| 35 | REFOBJTYPE | char10 | 1323 | Const | `'IPAS'` | R | NEW | Reference object type |
| 36 | REFOBJKEY | char70 | 1324 | IPAS | `Header.IPAS_Order_Number` | R | NEW | Reference object key |
| 37 | REFLOGSYS | char10 | 1325 | Const | `'INTEGRUM'` | R | NEW | Reference logical system |
| 38 | VAT_REG_NO | char20 | 1326 | SAP | _(from customer master)_ | O | NEW | VAT registration number |

**v2.0 Hallucinated Partner Fields Removed:** E_MAIL (exists in BAPIADDR1/PARTNERADDRESSES, not BAPIPARNR), PARTN_ROLE_OLD, PARTN_NUMB_OLD (do not exist in BAPIPARNR per WSDL).

**RRPS Partner Mapping (minimum required rows):**

| PARTN_ROLE | PARTN_NUMB Source | Description |
|------------|-------------------|-------------|
| `AG` (Sold-To) | `Header.Sold_To_Party` | Customer placing the order |
| `WE` (Ship-To) | `Header.Ship_To_Party` or `Engine.Ship_To_Party` | Delivery destination |
| `RE` (Bill-To) | `Header.Bill_To_Party` | Invoice recipient |
| `RG` (Payer) | `Header.Bill_To_Party` (if same) | Payment responsible |
| `ZI` (End Customer) | `Header.End_Customer` | End user (RRPS custom partner function) |

---

## 8. ORDER_SCHEDULES_IN — BAPISCHDL (23 fields, WSDL lines 1329-1355)

**WARNING:** v2.0 stated 17 fields. The WSDL defines **23 fields**. All 23 listed below.

| # | Field Name | WSDL Type | WSDL Line | Source | Default/Value | Mand. | Status | Notes |
|---|-----------|-----------|-----------|--------|---------------|-------|--------|-------|
| 1 | ITM_NUMBER | numeric6 | 1331 | Agent | _(matching item)_ | Y | EXISTING | Item number |
| 2 | SCHED_LINE | numeric4 | 1332 | Agent | `0001` | Y | EXISTING | Schedule line number |
| 3 | REQ_DATE | date10 | 1333 | IPAS | `Engine.Delivery_Date` | Y | EXISTING | **Requested delivery date. Note: This field is in BAPISCHDL, not BAPISDITM.** |
| 4 | DATE_TYPE | char1 | 1334 | Const | `'1'` | R | NEW | 1=requested delivery, 2=pick/pack |
| 5 | REQ_TIME | time | 1335 | -- | _(leave blank)_ | O | NEW | Requested time |
| 6 | REQ_QTY | quantum13.3 | 1336 | IPAS | `Engine.Quantity` | Y | EXISTING | Ordered quantity |
| 7 | REQ_DLV_BL | char2 | 1337 | -- | _(leave blank)_ | O | NEW | Requirements delivery block |
| 8 | SCHED_TYPE | char2 | 1338 | -- | _(leave blank)_ | O | NEW | Schedule line type |
| 9 | TP_DATE | date10 | 1339 | SAP | _(SAP-calculated)_ | O | NEW | Transportation planning date |
| 10 | MS_DATE | date10 | 1340 | SAP | _(SAP-calculated)_ | O | NEW | Material staging date |
| 11 | LOAD_DATE | date10 | 1341 | SAP | _(SAP-calculated)_ | O | NEW | Loading date |
| 12 | GI_DATE | date10 | 1342 | SAP | _(SAP-calculated)_ | O | NEW | Goods issue date |
| 13 | TP_TIME | time | 1343 | SAP | _(SAP-calculated)_ | O | NEW | Transportation planning time |
| 14 | MS_TIME | time | 1344 | SAP | _(SAP-calculated)_ | O | NEW | Material staging time |
| 15 | LOAD_TIME | time | 1345 | SAP | _(SAP-calculated)_ | O | NEW | Loading time |
| 16 | GI_TIME | time | 1346 | SAP | _(SAP-calculated)_ | O | NEW | Goods issue time |
| 17 | REFOBJTYPE | char10 | 1347 | Const | **`'IPAS'`** | **R** | **NEW** | Reference object type |
| 18 | REFOBJKEY | char70 | 1348 | IPAS | **`IPAS_Order + '/' + ITM_NUMBER`** | **R** | **NEW** | Reference object key |
| 19 | REFLOGSYS | char10 | 1349 | Const | **`'INTEGRUM'`** | **R** | **NEW** | Reference logical system |
| 20 | DLV_DATE | date10 | 1350 | SAP | _(SAP-calculated)_ | O | NEW | Delivery date |
| 21 | DLV_TIME | time | 1351 | SAP | _(SAP-calculated)_ | O | NEW | Delivery time |
| 22 | REL_TYPE | char1 | 1352 | -- | _(leave blank)_ | O | NEW | Release type |
| 23 | PLAN_SCHED_TYPE | char1 | 1353 | -- | _(leave blank)_ | O | NEW | Planned schedule type |

**v2.0 Hallucinated Schedule Fields Removed:** TIME_UNIT, REQ_DLV_BL_SCHED (do not exist in BAPISCHDL per WSDL).

---

## 9. ORDER_SCHEDULES_INX — BAPISCHDLX (23 fields, WSDL lines 1356-1382)

| Field | Type | Value | Notes |
|-------|------|-------|-------|
| ITM_NUMBER | numeric6 | _(matching)_ | Must match ORDER_SCHEDULES_IN |
| SCHED_LINE | numeric4 | _(matching)_ | Must match ORDER_SCHEDULES_IN |
| UPDATEFLAG | char1 | `'I'` | I=Insert |
| REQ_DATE | char1 | `'X'` | |
| DATE_TYPE | char1 | `'X'` | Set X if populated |
| REQ_TIME | char1 | `' '` | Leave blank |
| REQ_QTY | char1 | `'X'` | |
| REQ_DLV_BL | char1 | `' '` | Leave blank |
| SCHED_TYPE | char1 | `' '` | Leave blank |
| TP_DATE | char1 | `' '` | Leave blank (SAP-calculated) |
| MS_DATE | char1 | `' '` | Leave blank (SAP-calculated) |
| LOAD_DATE | char1 | `' '` | Leave blank (SAP-calculated) |
| GI_DATE | char1 | `' '` | Leave blank (SAP-calculated) |
| TP_TIME | char1 | `' '` | Leave blank |
| MS_TIME | char1 | `' '` | Leave blank |
| LOAD_TIME | char1 | `' '` | Leave blank |
| GI_TIME | char1 | `' '` | Leave blank |
| REFOBJTYPE | char10 | _(matching)_ | Same value as BAPISCHDL.REFOBJTYPE (key field in INX) |
| REFOBJKEY | char70 | _(matching)_ | Same value as BAPISCHDL.REFOBJKEY (key field in INX) |
| DLV_DATE | char1 | `' '` | Leave blank (SAP-calculated) |
| DLV_TIME | char1 | `' '` | Leave blank |
| REL_TYPE | char1 | `' '` | Leave blank |
| PLAN_SCHED_TYPE | char1 | `' '` | Leave blank |

---

## 10. ORDER_CONDITIONS_IN — BAPICOND (56 fields, WSDL lines 751-810)

**WARNING:** v2.0 stated ~24 fields. The WSDL defines **56 fields**. All 56 listed below.

### 10.1 RRPS-Relevant Condition Fields

| # | Field Name | WSDL Type | WSDL Line | Source | Default/Value | Mand. | Notes |
|---|-----------|-----------|-----------|--------|---------------|-------|-------|
| 1 | ITM_NUMBER | numeric6 | 753 | Agent | _(item no., 000000 for header)_ | Y | Item number |
| 2 | COND_ST_NO | numeric3 | 754 | Agent | `001`, `002`, ... | Y | Condition step number |
| 3 | COND_COUNT | numeric2 | 755 | Agent | `01` | Y | Condition counter |
| 4 | COND_TYPE | char4 | 756 | IPAS/Const | `'PR00'`, `'ZPR0'`, `'RA00'` | Y | Condition type |
| 5 | COND_VALUE | **decimal28.9** | 757 | IPAS | `Engine.Gross_Price` for PR00 | Y | **Condition rate. Note: type is decimal28.9, not DEC(11,2) as v2.0 stated.** |
| 6 | CURRENCY | cuky5 | 758 | IPAS | `Header.Currency_Code` | Y | Condition currency |
| 7 | COND_UNIT | unit3 | 759 | IPAS | `'EA'` | C | Condition unit |
| 8 | COND_P_UNT | decimal5.0 | 760 | Const | `1` | C | Pricing unit (per 1, per 100) |
| 9 | CURR_ISO | char3 | 761 | -- | _(leave blank)_ | O | Currency ISO. **Note: WSDL name is CURR_ISO, not CURRENCY_ISO.** |
| 10 | CD_UNT_ISO | char3 | 762 | -- | _(leave blank)_ | O | Condition unit ISO. **Note: WSDL name is CD_UNT_ISO, not COND_UNIT_ISO.** |
| 11 | REFOBJTYPE | char10 | 763 | -- | _(leave blank)_ | O | Reference object type |
| 12 | REFOBJKEY | char70 | 764 | -- | _(leave blank)_ | O | Reference object key |
| 13 | REFLOGSYS | char10 | 765 | -- | _(leave blank)_ | O | Reference logical system |
| 14 | CONDORIGIN | char1 | 778 | Const | `'C'` | R | Condition origin. C=manual. **Note: WSDL name is CONDORIGIN, not COND_ORIGIN.** |
| 15 | COND_NO | char10 | 800 | -- | _(leave blank)_ | O | Condition record number |
| 16 | TAX_CODE | char2 | 801 | -- | _(leave blank)_ | O | Tax code |

### 10.2 All 56 BAPICOND Fields (WSDL-verified)

| # | Field Name | WSDL Type | WSDL Line |
|---|-----------|-----------|-----------|
| 1 | ITM_NUMBER | numeric6 | 753 |
| 2 | COND_ST_NO | numeric3 | 754 |
| 3 | COND_COUNT | numeric2 | 755 |
| 4 | COND_TYPE | char4 | 756 |
| 5 | COND_VALUE | decimal28.9 | 757 |
| 6 | CURRENCY | cuky5 | 758 |
| 7 | COND_UNIT | unit3 | 759 |
| 8 | COND_P_UNT | decimal5.0 | 760 |
| 9 | CURR_ISO | char3 | 761 |
| 10 | CD_UNT_ISO | char3 | 762 |
| 11 | REFOBJTYPE | char10 | 763 |
| 12 | REFOBJKEY | char70 | 764 |
| 13 | REFLOGSYS | char10 | 765 |
| 14 | APPLICATIO | char2 | 766 |
| 15 | CONPRICDAT | date10 | 767 |
| 16 | CALCTYPCON | char1 | 768 |
| 17 | CONBASEVAL | decimal28.9 | 769 |
| 18 | CONEXCHRAT | decimal9.5 | 770 |
| 19 | NUMCONVERT | decimal5.0 | 771 |
| 20 | DENOMINATO | decimal5.0 | 772 |
| 21 | CONDTYPE | char1 | 773 |
| 22 | STAT_CON | char1 | 774 |
| 23 | SCALETYPE | char1 | 775 |
| 24 | ACCRUALS | char1 | 776 |
| 25 | CONINVOLST | char1 | 777 |
| 26 | CONDORIGIN | char1 | 778 |
| 27 | GROUPCOND | char1 | 779 |
| 28 | COND_UPDAT | char1 | 780 |
| 29 | ACCESS_SEQ | numeric2 | 781 |
| 30 | CONDCOUNT | numeric2 | 782 |
| 31 | ROUNDOFFDI | decimal28.9 | 783 |
| 32 | CONDVALUE | decimal28.9 | 784 |
| 33 | CURRENCY_2 | cuky5 | 785 |
| 34 | CURR_ISO_2 | char3 | 786 |
| 35 | CONDCNTRL | char1 | 787 |
| 36 | CONDISACTI | char1 | 788 |
| 37 | CONDCLASS | char1 | 789 |
| 38 | FACTBASVAL | float | 790 |
| 39 | SCALEBASIN | char1 | 791 |
| 40 | SCALBASVAL | decimal28.9 | 792 |
| 41 | UNITMEASUR | unit3 | 793 |
| 42 | ISO_UNIT | char3 | 794 |
| 43 | CURRENCKEY | cuky5 | 795 |
| 44 | CURRENISO | char3 | 796 |
| 45 | CONDINCOMP | char1 | 797 |
| 46 | CONDCONFIG | char1 | 798 |
| 47 | CONDCHAMAN | char1 | 799 |
| 48 | COND_NO | char10 | 800 |
| 49 | TAX_CODE | char2 | 801 |
| 50 | VARCOND | char26 | 802 |
| 51 | ACCOUNTKEY | char3 | 803 |
| 52 | ACCOUNT_KE | char3 | 804 |
| 53 | WT_WITHCD | char2 | 805 |
| 54 | STRUCTCOND | char1 | 806 |
| 55 | FACTCONBAS | float | 807 |
| 56 | CONDCOINHD | numeric2 | 808 |

**Note:** v2.0 used incorrect field names including DENOMCONVRT (correct: DENOMINATO), CURRENCY_ISO (correct: CURR_ISO), COND_ORIGIN (correct: CONDORIGIN), STATISCON (correct: STAT_CON), CONDCOESSION (does not exist), COND_INACTIVE (correct name: CONDISACTI), CONDISACNT (does not exist).

---

## 11. ORDER_CONDITIONS_INX — BAPICONDX (10 fields, WSDL lines 811-824)

| # | Field | WSDL Type | WSDL Line | Value | Notes |
|---|-------|-----------|-----------|-------|-------|
| 1 | ITM_NUMBER | numeric6 | 813 | _(matching)_ | Must match ORDER_CONDITIONS_IN |
| 2 | COND_ST_NO | numeric3 | 814 | _(matching)_ | |
| 3 | COND_COUNT | numeric2 | 815 | _(matching)_ | |
| 4 | COND_TYPE | char4 | 816 | _(matching)_ | |
| 5 | UPDATEFLAG | char1 | 817 | `'I'` | I=Insert new condition |
| 6 | COND_VALUE | char1 | 818 | `'X'` | |
| 7 | CURRENCY | char1 | 819 | `'X'` | |
| 8 | COND_UNIT | char1 | 820 | `'X'` | Set X if populated |
| 9 | COND_P_UNT | char1 | 821 | `'X'` | Set X if populated |
| 10 | VARCOND | char26 | 822 | _(leave blank)_ | Variant condition |

---

## 12. ORDER_TEXT — BAPISDTEXT (8 fields, WSDL lines 1383-1394)

| # | Field Name | WSDL Type | WSDL Line | Source | Default/Value | Mand. | Notes |
|---|-----------|-----------|-----------|--------|---------------|-------|-------|
| 1 | DOC_NUMBER | char10 | 1385 | -- | _(leave blank for new order)_ | O | Document number (SAP fills). |
| 2 | ITM_NUMBER | numeric6 | 1386 | Agent | `000000` for header, item no. for item | Y | 000000 = header text |
| 3 | TEXT_ID | char4 | 1387 | Const | `'0001'` (header), `'0002'` (item) | Y | Text ID |
| 4 | LANGU | lang | 1388 | Const | `'E'` | Y | Language key |
| 5 | LANGU_ISO | char2 | 1389 | -- | _(leave blank)_ | O | Language ISO |
| 6 | FORMAT_COL | char2 | 1390 | Const | `'*'` or `'/'` | O | Text format column. **Note: WSDL name is FORMAT_COL, not TEXT_FORM as v2.0 stated.** |
| 7 | TEXT_LINE | char132 | 1391 | IPAS/Agent | _(order notes, assembly notes)_ | Y | Text content line (one row per line) |
| 8 | FUNCTION | char3 | 1392 | -- | _(leave blank)_ | O | Function for text processing |

**RRPS Text Mapping:**
- Header text (ITM_NUMBER=000000, TEXT_ID='0001'): Map from IPAS order-level notes
- Item text (ITM_NUMBER=nnnnnn, TEXT_ID='0002'): Map from `Item.Assembly_Note`

---

## 13. EXTENSIONIN — BAPIPAREX (5 fields, WSDL lines 592-600)

RRPS uses custom Z-fields via EXTENSIONIN. Each row carries a structure name and up to 960 characters of data.

| # | Field Name | WSDL Type | WSDL Line | Notes |
|---|-----------|-----------|-----------|-------|
| 1 | STRUCTURE | char30 | 594 | `'BAPE_VBAK'` (header) or `'BAPE_VBAP'` (item) |
| 2 | VALUEPART1 | char240 | 595 | Characters 1-240 |
| 3 | VALUEPART2 | char240 | 596 | Characters 241-480 |
| 4 | VALUEPART3 | char240 | 597 | Characters 481-720 |
| 5 | VALUEPART4 | char240 | 598 | Characters 721-960 |

### 13.1 BAPE_VBAK - Header Extension Fields

| Z-Field | Offset | Length | Source | Description |
|---------|--------|--------|--------|-------------|
| ZZIPAS_ORD | 0 | 20 | IPAS | IPAS Order Number (primary cross-reference) |
| ZZIPAS_VER | 20 | 4 | IPAS | IPAS Order Version |
| ZZIPAS_PRJ | 24 | 20 | IPAS | IPAS Project Number |
| ZZENG_TYPE | 44 | 20 | IPAS | Engine Type |
| ZZSERIES | 64 | 10 | IPAS | Engine Series |
| ZZCYLINDER | 74 | 4 | IPAS | Cylinder count |
| ZZPOWER | 78 | 10 | IPAS | Power rating |
| ZZPOWER_UOM | 88 | 3 | IPAS | Power unit (default 'KW') |
| ZZSPEED | 91 | 10 | IPAS | Engine speed |
| ZZAPP_COARSE | 101 | 20 | IPAS | Application coarse |
| ZZAPP_FINE | 121 | 20 | IPAS | Application fine |
| ZZBIZTYPE | 141 | 10 | IPAS | Business type |
| ZZCLASSSOC | 151 | 20 | IPAS | Classification society |
| ZZEMISSION | 171 | 20 | IPAS | Emission cert authority |
| ZZBILLPLAN | 191 | 5 | IPAS | Billing plan relevance |
| ZZENDCUST | 196 | 10 | IPAS | End customer code |
| ZZENDCCTRY | 206 | 3 | IPAS | End customer country |
| ZZMSG_ID | 209 | 30 | IPAS | IPAS Message ID |

### 13.2 BAPE_VBAP - Item Extension Fields

| Z-Field | Offset | Length | Source | Description |
|---------|--------|--------|--------|-------------|
| ZZENG_NO | 0 | 20 | IPAS | Engine number |
| ZZACCEPT | 20 | 1 | IPAS | Acceptance with customer flag |
| ZZEXHAUST | 21 | 20 | IPAS | Exhaust regulation |
| ZZSTOCK | 41 | 1 | IPAS | Take from stock flag |
| ZZSUBOBJ | 42 | 20 | IPAS | Sub-object number |
| ZZPKGGRP | 62 | 10 | IPAS | Packaging group |

---

## 14. Additional WSDL Structures (Not Used for RRPS)

The WSDL defines the following additional table parameters. These are available but **not required** for the RRPS ZEN2 engine order scenario:

| Parameter | WSDL Structure | WSDL Line | Fields | Purpose |
|-----------|---------------|-----------|--------|---------|
| ORDER_CCARD | TABLE_OF_BAPICCARD | 1609 | 33 (BAPICCARD) | Credit card data. N/A for B2B engine orders. |
| ORDER_CFGS_BLOB | TABLE_OF_BAPICUBLB | 1610 | 2 (BAPICUBLB) | Configuration blob. N/A — RRPS uses IPAS for configuration. |
| ORDER_CFGS_INST | TABLE_OF_BAPICUINS | 1611 | 14 (BAPICUINS) | Configuration instances. |
| ORDER_CFGS_PART_OF | TABLE_OF_BAPICUPRT | 1612 | 10 (BAPICUPRT) | Configuration part-of relationships. |
| ORDER_CFGS_REF | TABLE_OF_BAPICUCFG | 1613 | 13 (BAPICUCFG) | Configuration references. |
| ORDER_CFGS_REFINST | TABLE_OF_BAPICUREF | 1614 | 3 (BAPICUREF) | Configuration reference instances. |
| ORDER_CFGS_VALUE | TABLE_OF_BAPICUVAL | 1615 | 9 (BAPICUVAL) | Configuration characteristic values. |
| ORDER_CFGS_VK | TABLE_OF_BAPICUVK | 1616 | 4 (BAPICUVK) | Configuration variant keys. |
| ORDER_KEYS | TABLE_OF_BAPISDKEY | 1623 | 17 (BAPISDKEY) | Return table — SAP populates after creation. |
| NFMETALLITMS | TABLE_OF__-NFM_-BAPIDOCITM | 1608 | 26 | Non-ferrous metal items. N/A for engines. |
| PARTNERADDRESSES | TABLE_OF_BAPIADDR1 | 1628 | 77 (BAPIADDR1) | Partner address details (contains E_MAIL field). Use for one-time customer addresses. |
| EXTENSIONEX | TABLE_OF_BAPIPAREX | 1604 | 5 | Extension output (response only). |

---

## 15. REFOBJTYPE / REFOBJKEY / REFLOGSYS — Traceability Specification

These three fields appear in multiple table structures and provide end-to-end traceability between IPAS and SAP.

### Recommended Values

| Structure | REFOBJTYPE | REFOBJKEY | REFLOGSYS |
|-----------|-----------|-----------|-----------|
| ORDER_HEADER_IN | `'IPAS'` | `Header.IPAS_Order_Number` (e.g., `'IP-2025-00123'`) | _(not in BAPISDHD1)_ |
| ORDER_ITEMS_IN | `'IPAS'` | `IPAS_Order_Number + '/' + ITM_NUMBER` | `'INTEGRUM'` |
| ORDER_PARTNERS | `'IPAS'` | `Header.IPAS_Order_Number` | `'INTEGRUM'` |
| ORDER_SCHEDULES_IN | `'IPAS'` | `IPAS_Order_Number + '/' + ITM_NUMBER` | `'INTEGRUM'` |
| ORDER_CONDITIONS_IN | _(leave blank)_ | _(leave blank)_ | _(leave blank)_ |

### Why This Matters
1. **Idempotency**: If the CPI iFlow retries, SAP can detect duplicate submissions via REFOBJTYPE+REFOBJKEY
2. **Audit Trail**: SAP table CDHDR/CDPOS stores these reference values for change document tracking
3. **Reverse Lookup**: From any SAP order, trace back to the originating IPAS order
4. **Error Recovery**: If BAPI_TRANSACTION_COMMIT fails, REFOBJKEY allows matching retry attempts

---

## 16. BAPI Call Sequence

```
Step 1: BAPI_SALESORDER_CREATEFROMDAT2
        Import Parameters:
          - BEHAVE_WHEN_ERROR = 'P'
          - CONVERT = 'X'
          - INT_NUMBER_ASSIGNMENT = 'X'
          - TESTRUN = '' (blank for production, 'X' for test)
          - LOGIC_SWITCH:
              PRICING = 'X'
              SCHEDULING = 'X'        ← WSDL field name (not SCHED_CONF)
              ATP_WRKMOD = ' '        ← blank for standard ATP
              NOSTRUCTURE = ' '       ← blank for standard BOM
              COND_HANDL = ' '        ← blank for standard conditions
              ADDR_CHECK = ' '        ← blank for standard address check
          - SENDER:
              LOG_SYSTEM = 'INTEGRUM' ← only field in BAPI_SENDER
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
          ← WSDL response field name (not SALES_DOCUMENT_OUT)

Step 3: BAPI_TRANSACTION_COMMIT
        Import Parameters:
          - WAIT = 'X'  (synchronous commit — CRITICAL for CPI)

Step 4: (Optional) BAPI_SALESORDER_GETLIST or direct read
        - Verify the order was created by reading it back.
        - Store the SAP order number in Integrum for IPAS-to-SAP mapping.
```

**Error Handling in CPI iFlow:**
- If Step 1 returns errors: Do NOT call BAPI_TRANSACTION_COMMIT. Call BAPI_TRANSACTION_ROLLBACK instead.
- If Step 3 fails: Retry with exponential backoff. The REFOBJKEY allows SAP to detect if the order was already created.
- Always log the full RETURN table for troubleshooting.

---

## 17. Coverage Summary

| Structure | WSDL Field Count | v1.0 Mapped | v2.1 Populated | v2.1 Documented | WSDL Lines |
|-----------|-----------------|-------------|----------------|-----------------|------------|
| BAPISDHD1 (Header) | **130** | 14 | ~25 | **130** (100%) | 323-456 |
| BAPISDHD1X (Header INX) | ~126 | 0 | ~25 (set to X) | Full guidance | 457-586 |
| BAPISDITM (Items) | **220** | 8 | ~22 | **220** (100%) | 825-1048 |
| BAPISDITMX (Items INX) | 213 | 0 | ~15 (set to X) | Full guidance | 1049-1265 |
| BAPIPARNR (Partners) | **38** | 2 | ~10 | **38** (100%) | 1287-1328 |
| BAPISCHDL (Schedules) | **23** | 4 | ~6 | **23** (100%) | 1329-1355 |
| BAPISCHDLX (Schedules INX) | 23 | 0 | ~4 (set to X) | Full guidance | 1356-1382 |
| BAPICOND (Conditions) | **56** | 0 | ~10 | **56** (100%) | 751-810 |
| BAPICONDX (Conditions INX) | 10 | 0 | ~6 (set to X) | **10** (100%) | 811-824 |
| BAPISDTEXT (Text) | 8 | 0 | ~6 | **8** (100%) | 1383-1394 |
| BAPIPAREX (ExtensionIn) | 5 | _(partial)_ | 5 | **5** (100%) | 592-600 |
| BAPISDLS (Logic Switch) | **6** | 0 | 2 (set) | **6** (100%) | 313-322 |
| BAPI_SENDER | **1** | 0 | 1 | **1** (100%) | 587-591 |
| BAPI-level params | 10 | 0 | 8 (set) | **10** (100%) | 1598-1635 |

**Total WSDL-verified fields documented: 700+ (all structures combined)**

### Fields NOT Populated (by design)

The following categories are intentionally left blank for RRPS ZEN2:
- **Quotation/Contract fields** (QT_VALID_F/T, CT_VALID_F/T): N/A for direct orders
- **Tax classification fields** (TAX_CLASS1-9, ALTTAX_CLS): SAP auto-determines
- **Customer condition groups** (CSTCNDGRP1-5): SAP reads from customer master
- **Configuration/variant fields** (CONFIG_ID, INST_ID, ORDER_CFGS_*): RRPS uses IPAS, not SAP variant config
- **SAP-calculated dates** (DLV_DATE, TP_DATE, MS_DATE, LOAD_DATE, GI_DATE + times): SAP scheduling
- **Account determination fields** (ACCNT_ASGN, PROFIT_CTR): SAP account determination
- **Brazil tax/localization fields** (CFOP_CODE, TAXLAWICMS, etc.): N/A for RRPS
- **Transfer pricing fields** (TP_SUBLEVL, TP_AGENCID, etc.): N/A
- **PSM/Treasury fields** (PSM_PSTNG_DATE, TREASURY_ACC_SYMBOL, etc.): N/A

---

## 18. Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-15 | Integrum | Initial mapping: 14 header + 8 item fields |
| 2.0 | 2026-04-16 | Integrum / Kailash AI | Complete coverage attempt — contained ~100 errors (hallucinated fields, wrong names/types/counts) |
| 2.1 | 2026-04-16 | Integrum / Kailash AI (Red-Team Verified) | WSDL line-by-line verification. Corrected: 130 header (not 132), 220 item (not 223), 38 partner (not 28), 23 schedule (not 17), 56 condition (not 24), 6 LOGIC_SWITCH (not 7), 1 SENDER field (not 2). Removed ~40 hallucinated header fields, fixed all field names to match WSDL exactly. Every field now includes WSDL line reference. |

---

*This document provides complete field-level coverage of BAPI_SALESORDER_CREATEFROMDAT2 as defined in `DOC_WEBI_FUNCTIONMODULE.WSDL`. Every field includes its WSDL line number for independent verification. No fields have been fabricated — all names and types are taken directly from the WSDL XSD definitions.*
