# University Report Format Spec (extracted from report/MCA_4sem_Project_Report_format.docx)

Source: Dayananda Sagar University (DSU), School of Computer Applications, MCA 4th semester project report template.
Extracted via python-docx on 2026-07-24. This file is the durable checkpoint for Phase 1 — treat the
original DOCX table (below) as the single source of truth if anything here is ambiguous.

## Explicit formatting rules (verbatim from the template's own instruction table)

| Item | Rule |
|---|---|
| Report Cover | Soft Binding |
| Margins | Top: 1", Bottom: 1", Left: 1.5", Right: 1" |
| Orientation | Portrait |
| All fonts | Times New Roman |
| Chapter No. | Font size 18, Sentence case + Bold |
| Chapter TITLE | Font size 18, Capital case + Bold |
| First level heading (e.g. 1.1) | Font size 16, Capital case + Bold |
| Second level heading (e.g. 1.1.1) | Font size 14, Sentence case + Bold |
| Third level heading (e.g. 1.1.1.1) | Font size 12, Sentence case + Italic (no bold) |
| Table caption | Font size 12, Sentence case + Bold, placed at TOP of table |
| Figure caption | Font size 12, Sentence case + Bold, placed at BOTTOM of figure |
| Body text | Times New Roman, 12, Normal |
| Page number | Bottom, right-aligned. Preliminary pages numbered i, ii, iii...; chapter pages + references numbered 1, 2, 3... |
| Line spacing | 1.5 lines |
| Printing | One side of the page only |

Note: the template DOCX's own page-section properties (as currently saved) do not match this table
(section shows ~1"/0.69" margins) — the table above is the university's written instruction and is
authoritative; the blank template's current page setup is not a reliable signal.

## Preliminary pages (in order, with the template's exact placeholder wording)

1. **Cover / Title page**
   - Dayananda Sagar University, Kudlu Gate, Hosur Road, Bengaluru – 560068 (bold, 14pt, centered)
   - "SCHOOL OF COMPUTER APPLICATIONS" (bold, 16pt, centered)
   - "A Project Report on" (16pt, centered)
   - `<<Project Title>>` (14pt, centered) → **replace with "AI-Based Multi-Modal Secure Code Analysis Platform"**
   - "Submitted in Partial fulfilment of the requirements for the award of the Degree of" (14pt)
   - "MASTER OF COMPUTER APPLICATIONS" (bold, 16pt)
   - "Submitted by" (16pt)
   - `<<Name of the Student>>` (bold, 14pt) + USN NO (bold, 14pt) — [REQUIRES VERIFICATION: student name/USN]
   - "Under the guidance of" / `<<Details of the guide>>` (16pt) — guide is **Dr. S. Senthil, Professor and Dean, School of Computer Applications, Dayananda Sagar University, Bengaluru** (from the template's own guide-details table) — [REQUIRES VERIFICATION: confirm this is the correct guide for this specific project]
   - "JULY 2026" (14pt, centered) — [REQUIRES VERIFICATION: actual submission month/year]
   - "DAYANANDA SAGAR UNIVERSITY / Kudlu Gate, Hosur Road, Bengaluru – 560068" (bold, 14pt)

2. **Bonafide Certificate**
   - Heading: "SCHOOL OF COMPUTER APPLICATIONS" / "BONAFIDE CERTIFICATE" (bold, 16pt, centered)
   - Body (justified, 12pt): "This is to certify that the project titled '<<Project Title>>' is a bonafide
     record of the work undertaken by <<Name of the Student (USN NO)>> in partial fulfillment of the
     requirements for the award of the Master of Computer Applications degree at the School of Computer
     Applications, Dayananda Sagar University, Bengaluru, during the academic year 2025-2026."
   - Signature blocks: GUIDE / DEAN, then Internal Examiner / External Examiner

3. **Declaration**
   - Heading: "SCHOOL OF COMPUTER APPLICATIONS" / "DECLARATION"
   - Body (justified, 12pt), three paragraphs — student declares independent work, submission for MCA
     degree AY 2025-2026, and non-submission elsewhere.
   - "Signed by me on: _______" / "Signature of the Candidate"
   - Guide's countersignature paragraph + "Signature of the Guide" / "Date: _______"

4. **Acknowledgement**
   - Fixed thank-you order: Institute → Chancellor (Dr. D. Hemachandra Sagar) & Pro-Chancellor
     (Dr. Premachandra Sagar) → Vice Chancellor (Dr. B.S. Satyanarayana) & Registrar
     (Dr. Puttamadappa C) → Dean, SoCA (Dr. S. Senthil) → Guide → teaching/non-teaching staff →
     parents/friends → closing paragraph. Signed with student name + USN.

5. **Contents (Table of Contents)** — heading "CONTENTS", followed by the chapter/section list (see below).

**No Abstract, List of Figures, List of Tables, or List of Abbreviations pages exist in this template**
(confirmed by keyword search — "abstract", "list of figures/tables", "abbreviation" do not appear anywhere
in the document). Do not add these preliminary sections; they are not part of this university's format.

## Chapter structure (from the CONTENTS list — authoritative section titles)

- **CHAPTER 1: INTRODUCTION**
  1.1 Project Overview
  1.2 Statement of the Problem
  1.3 Brief Description of the Project (Objectives / Scope of the Project also listed here as sub-bullets in the template)
  Objectives of the Project
  Scope of the Project
  Software and Hardware Requirements
    - Software Specifications
    - Hardware Specifications
  1.3 Functional and Non-Functional Requirements (as literally numbered in template — reuse this section numbering; treat prior bullets as 1.1/1.2 with sub-bullets)
  1.4 Company/Domain Profile (if applicable) — likely N/A for this academic project, note briefly or omit per guide's preference

- **CHAPTER 2: LITERATURE SURVEY**
  2.1 Existing Research and Related Work
  2.2 Gaps in Existing Systems
  2.3 Overview of Technologies Used (AI/ML, Deep Learning, etc.)
  2.4 Comparison of Different Approaches

- **CHAPTER 3: METHODOLOGY & SYSTEM ANALYSIS**
  3.1 Existing System — Overview of Current System / 3.1.2 Challenges and Limitations
  3.2 Proposed System — System Architecture / 3.2.2 Features and Functionalities
  Datasets Used (for AI/ML projects) — Dataset Description / Data Collection Process / Data Preprocessing Techniques
  Machine Learning Model/Algorithm Selection — Algorithm Justification / Training and Testing Data Split / Feature Selection and Engineering
  Feasibility Study — Technical / Economic / Operational Feasibility

- **CHAPTER 4: SYSTEM DESIGN AND DEVELOPMENT**
  4.1 System Architecture (High-Level Design) — Conceptual Design / Component Diagram
  4.2 Detailed Design (Low-Level Design) — DFD / Use Case Diagrams / Activity Diagrams / Class Diagrams (if applicable)
  4.3 Database Design — ER Diagram / Schema Design
  4.4 Input/Output Interface Design — UI Screens / API Design (if applicable)
  4.5 Module Description — Description of Each Module / Functionality and Interaction

- **CHAPTER 5: IMPLEMENTATION & CODING**
  5.1 Programming Language and Framework Used
  5.2 Algorithmic Approach (for AI/ML-based projects) — Pseudocode / Flowcharts / Model Training and Fine-Tuning
  Code Snippets and Explanation — 5.3.1 Key Functionalities

- **CHAPTER 6: SOFTWARE TESTING**
  6.1 Testing Strategies — Unit / Integration / System Testing
  6.2 Test Cases — 6.2.1 Sample Test Cases with Expected vs. Actual Results
  6.3 Performance Metrics and Evaluation (for AI/ML projects) — Confusion Matrix / Precision, Recall, F1-Score / Model Accuracy and Loss Curves

- **CHAPTER 7: RESULTS AND DISCUSSION**
  7.1 Experimental Setup — Hardware/Software Setup / Model Hyperparameters
  7.2 Model Performance Analysis — Training vs. Testing Performance / Bias-Variance Analysis / Model Comparisons
  7.3 Comparison with Existing Systems
  7.4 Visualization of Results — Graphs, Charts, and Performance Trends
  7.5 Screenshots of Working System

- **CHAPTER 8: CONCLUSION AND FUTURE ENHANCEMENTS**
  8.1 Conclusion
  8.2 Limitations of the Project
  8.3 Scope for Future Enhancements

- **REFERENCES** — Books, Research Papers, Websites, APIs used, etc.

## Title correction applied throughout

Every occurrence of `<<Project Title>>` in the cover, certificate, and declaration must read:
**"AI-Based Multi-Modal Secure Code Analysis Platform"**
(This supersedes the old working title "Multi-Modal Code Vulnerability Detection Using CodeBERT and
Structural Code Analysis," which may still appear in the repo's own historical docs/commits — that is
expected and not a signal to use it here.)

## Open items requiring user input before final assembly
- [REQUIRES VERIFICATION] Student name and USN number
- [REQUIRES VERIFICATION] Guide identity — template's own guide-details table names Dr. S. Senthil (Dean),
  but confirm this is actually this student's assigned guide rather than a leftover default
- [REQUIRES VERIFICATION] Exact submission month (template placeholder says "JULY 2026")
- [REQUIRES VERIFICATION] Internal/External examiner names (left blank in template — normally filled at viva)
