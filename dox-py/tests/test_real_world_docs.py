"""
Real-world document pattern tests.

These test the .dox round-trip pipeline against the structural patterns
found in actual professional documents: notary, legal, financial, medical,
government, academic, and corporate templates.

Tests 67–130+ to complement the 66 stress tests.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from dox.models.document import DoxDocument, Frontmatter
from dox.models.elements import (
    Annotation, BoundingBox, CodeBlock, CrossRef, Figure, Footnote,
    FormField, FormFieldType, Heading, ListBlock, ListItem, MathBlock,
    PageBreak, Paragraph, Table, TableCell, TableRow,
)
from dox.converters.to_docx import to_docx
from dox.converters.to_pdf import to_pdf
from dox.parsers.parser import DoxParser
from dox.serializer import DoxSerializer

# ── Helpers ──────────────────────────────────────────────────────────

_serializer = DoxSerializer()
_parser = DoxParser()

def _roundtrip_dox(doc: DoxDocument) -> DoxDocument:
    """Serialize → parse round-trip."""
    text = _serializer.serialize(doc)
    return _parser.parse(text)

def _roundtrip_docx(doc: DoxDocument) -> Path:
    """Build DOCX, return path."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        return to_docx(doc, f.name)

def _roundtrip_pdf(doc: DoxDocument) -> Path:
    """Build PDF, return path."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        return to_pdf(doc, f.name)

def _make_doc(**kw) -> DoxDocument:
    doc = DoxDocument()
    doc.frontmatter = Frontmatter(
        version="1.0",
        source=kw.get("source", "test"),
        lang=kw.get("lang", "en"),
    )
    return doc

def _all_text(doc: DoxDocument) -> str:
    """Collect all text content from a doc."""
    parts = []
    for el in doc.elements:
        if hasattr(el, 'text'):
            parts.append(el.text)
        elif hasattr(el, 'rows'):
            for row in el.rows:
                for cell in row.cells:
                    parts.append(cell.text)
        elif hasattr(el, 'items'):
            for item in el.items:
                parts.append(item.text)
        elif hasattr(el, 'code'):
            parts.append(el.code)
        elif hasattr(el, 'expression'):
            parts.append(el.expression)
    return " ".join(parts)

# ═══════════════════════════════════════════════════════════════════
# NOTARY DOCUMENTS
# ═══════════════════════════════════════════════════════════════════

class TestNotaryDocuments:
    """Patterns found in notary public documents."""

    def test_67_notary_acknowledgment(self):
        """Standard notary acknowledgment block with witness lines."""
        doc = _make_doc(source="notary")
        doc.add_element(Heading(level=1, text="NOTARY ACKNOWLEDGMENT"))
        doc.add_element(Paragraph(text="STATE OF CALIFORNIA"))
        doc.add_element(Paragraph(text="COUNTY OF LOS ANGELES"))
        doc.add_element(Paragraph(
            text="On this 15th day of March, 2026, before me, Jane Smith, "
                 "a Notary Public in and for said State, personally appeared "
                 "John Doe, known to me (or proved to me on the basis of "
                 "satisfactory evidence) to be the person(s) whose name(s) "
                 "is/are subscribed to the within instrument and acknowledged "
                 "to me that he/she/they executed the same in his/her/their "
                 "authorized capacity(ies), and that by his/her/their "
                 "signature(s) on the instrument the person(s), or the entity "
                 "upon behalf of which the person(s) acted, executed the instrument."
        ))
        doc.add_element(Paragraph(text="WITNESS my hand and official seal."))
        # Signature lines as form fields
        doc.add_element(FormField(field_name="notary_signature", field_type=FormFieldType.TEXT, value=""))
        doc.add_element(Paragraph(text="Notary Public Signature"))
        doc.add_element(FormField(field_name="commission_number", field_type=FormFieldType.TEXT, value="2345678"))
        doc.add_element(FormField(field_name="commission_expires", field_type=FormFieldType.TEXT, value="12/31/2028"))
        # Seal placeholder
        doc.add_element(Figure(caption="[NOTARY SEAL]", source="notary-seal.png", figure_id="seal"))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "NOTARY ACKNOWLEDGMENT" in text
        assert "personally appeared" in text
        assert "WITNESS" in text

        path = _roundtrip_docx(doc)
        assert path.exists()
        path = _roundtrip_pdf(doc)
        assert path.exists()

    def test_68_jurat_certificate(self):
        """Jurat (sworn statement) with signature blocks."""
        doc = _make_doc(source="notary")
        doc.add_element(Heading(level=1, text="JURAT"))
        doc.add_element(Paragraph(
            text="State of New York, County of Kings, ss.:"
        ))
        doc.add_element(Paragraph(
            text="Subscribed and sworn to (or affirmed) before me on this "
                 "10th day of April, 2026, by John Q. Public, proved to me "
                 "on the basis of satisfactory evidence to be the person who "
                 "appeared before me."
        ))
        doc.add_element(Footnote(number=1, text="See attached identification documents."))
        doc.add_element(FormField(field_name="notary_name", field_type=FormFieldType.TEXT, value="Maria Garcia"))
        doc.add_element(Paragraph(text="Commission No. 12345"))
        doc.add_element(Paragraph(text="My commission expires: January 1, 2029"))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "JURAT" in text
        assert "Subscribed and sworn" in text
        path = _roundtrip_docx(doc)
        assert path.exists()

    def test_69_affidavit(self):
        """Full affidavit with numbered paragraphs and notarization."""
        doc = _make_doc(source="legal")
        doc.add_element(Heading(level=1, text="AFFIDAVIT OF JOHN DOE"))
        doc.add_element(Paragraph(text="I, John Doe, being duly sworn, depose and state as follows:"))

        # Numbered statements (as ordered list)
        doc.add_element(ListBlock(ordered=True, start=1, items=[
            ListItem(text="I am over the age of 18 and competent to make this affidavit."),
            ListItem(text="I reside at 123 Main Street, Springfield, IL 62701."),
            ListItem(text="I have personal knowledge of the facts stated herein."),
            ListItem(text="On or about January 15, 2026, I witnessed the signing of the contract between Alpha Corp and Beta LLC."),
            ListItem(text="The signatures on the attached document are genuine and were made in my presence."),
            ListItem(text="No duress, coercion, or undue influence was exerted upon any party."),
            ListItem(text="I make this affidavit in support of the Motion for Summary Judgment filed in Case No. 2026-CV-1234."),
        ]))

        doc.add_element(Paragraph(text="FURTHER AFFIANT SAYETH NAUGHT."))
        doc.add_element(FormField(field_name="affiant_signature", field_type=FormFieldType.TEXT, value=""))
        doc.add_element(Paragraph(text="John Doe, Affiant"))
        doc.add_element(PageBreak(from_page=1, to_page=2))

        # Notarization on page 2
        doc.add_element(Heading(level=2, text="NOTARIZATION"))
        doc.add_element(Paragraph(
            text="Sworn to and subscribed before me this 10th day of April, 2026."
        ))
        doc.add_element(FormField(field_name="notary_signature", field_type=FormFieldType.TEXT, value=""))
        doc.add_element(Figure(caption="[NOTARY SEAL]", source="seal.png"))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "AFFIDAVIT" in text
        assert "depose and state" in text
        assert "FURTHER AFFIANT" in text
        assert "personal knowledge" in text

        path = _roundtrip_docx(doc)
        assert path.exists()
        path = _roundtrip_pdf(doc)
        assert path.exists()

    def test_70_power_of_attorney(self):
        """Power of Attorney document with multiple form fields."""
        doc = _make_doc(source="legal")
        doc.add_element(Heading(level=1, text="GENERAL DURABLE POWER OF ATTORNEY"))
        doc.add_element(Paragraph(
            text="KNOW ALL PERSONS BY THESE PRESENTS, that I, "
                 "_____________________ (\"Principal\"), a resident of "
                 "the State of _____________________, do hereby appoint "
                 "_____________________ (\"Agent\") as my true and lawful "
                 "attorney-in-fact."
        ))

        doc.add_element(Heading(level=2, text="POWERS GRANTED"))
        doc.add_element(ListBlock(ordered=False, items=[
            ListItem(text="To manage and conduct all of my banking and financial transactions"),
            ListItem(text="To buy, sell, mortgage, and manage real property"),
            ListItem(text="To execute and file tax returns on my behalf"),
            ListItem(text="To make healthcare decisions as permitted by law"),
            ListItem(text="To engage legal counsel and initiate or defend legal proceedings"),
        ]))

        doc.add_element(Heading(level=2, text="EFFECTIVE DATE AND DURABILITY"))
        doc.add_element(Paragraph(
            text="This power of attorney shall become effective immediately and "
                 "shall not be affected by my subsequent disability or incapacity."
        ))

        # Signature table
        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Role", is_header=True),
                TableCell(text="Name", is_header=True),
                TableCell(text="Signature", is_header=True),
                TableCell(text="Date", is_header=True),
            ]),
            TableRow(cells=[
                TableCell(text="Principal"),
                TableCell(text=""),
                TableCell(text=""),
                TableCell(text=""),
            ]),
            TableRow(cells=[
                TableCell(text="Agent"),
                TableCell(text=""),
                TableCell(text=""),
                TableCell(text=""),
            ]),
            TableRow(cells=[
                TableCell(text="Witness 1"),
                TableCell(text=""),
                TableCell(text=""),
                TableCell(text=""),
            ]),
            TableRow(cells=[
                TableCell(text="Witness 2"),
                TableCell(text=""),
                TableCell(text=""),
                TableCell(text=""),
            ]),
        ]))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "POWER OF ATTORNEY" in text
        assert "attorney-in-fact" in text
        assert "Principal" in text
        assert "Witness" in text

        path = _roundtrip_docx(doc)
        assert path.exists()

    def test_71_deed_of_trust(self):
        """Real estate deed with legal descriptions and recording info."""
        doc = _make_doc(source="legal")
        doc.add_element(Heading(level=1, text="DEED OF TRUST"))
        doc.add_element(Paragraph(text="Recording Requested By: First National Bank"))
        doc.add_element(Paragraph(text="When Recorded Mail To:"))
        doc.add_element(Paragraph(text="First National Bank, Attn: Loan Servicing"))
        doc.add_element(Paragraph(text="456 Banking Avenue, Suite 200"))
        doc.add_element(Paragraph(text="New York, NY 10001"))
        doc.add_element(Paragraph(text="APN: 1234-567-890"))
        doc.add_element(Paragraph(text="Loan No: FNB-2026-00123"))

        doc.add_element(Heading(level=2, text="LEGAL DESCRIPTION"))
        doc.add_element(Paragraph(
            text="LOT 42 OF TRACT NO. 12345, IN THE CITY OF LOS ANGELES, "
                 "COUNTY OF LOS ANGELES, STATE OF CALIFORNIA, AS PER MAP "
                 "RECORDED IN BOOK 100, PAGES 21 THROUGH 25 INCLUSIVE OF MAPS, "
                 "IN THE OFFICE OF THE COUNTY RECORDER OF SAID COUNTY."
        ))

        # Consideration table
        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Item", is_header=True),
                TableCell(text="Value", is_header=True),
            ]),
            TableRow(cells=[TableCell(text="Purchase Price"), TableCell(text="$1,250,000.00")]),
            TableRow(cells=[TableCell(text="Down Payment"), TableCell(text="$250,000.00")]),
            TableRow(cells=[TableCell(text="Loan Amount"), TableCell(text="$1,000,000.00")]),
            TableRow(cells=[TableCell(text="Interest Rate"), TableCell(text="6.25% per annum")]),
            TableRow(cells=[TableCell(text="Term"), TableCell(text="30 years (360 months)")]),
        ]))

        doc.add_element(Footnote(number=1, text="All monetary amounts are in United States Dollars (USD)."))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "DEED OF TRUST" in text
        assert "$1,250,000.00" in text
        assert "LEGAL DESCRIPTION" in text
        assert "LOT 42" in text

        path = _roundtrip_docx(doc)
        assert path.exists()
        path = _roundtrip_pdf(doc)
        assert path.exists()


# ═══════════════════════════════════════════════════════════════════
# CONTRACT / LEGAL AGREEMENTS
# ═══════════════════════════════════════════════════════════════════

class TestContractDocuments:
    """Patterns from contracts, NDAs, and legal agreements."""

    def test_72_nda_full(self):
        """Complete Non-Disclosure Agreement."""
        doc = _make_doc(source="legal")
        doc.add_element(Heading(level=1, text="MUTUAL NON-DISCLOSURE AGREEMENT"))
        doc.add_element(Paragraph(
            text="This Mutual Non-Disclosure Agreement (\"Agreement\") is entered "
                 "into as of April 10, 2026 (\"Effective Date\") by and between:"
        ))
        doc.add_element(Paragraph(
            text="**Alpha Technologies, Inc.**, a Delaware corporation with offices "
                 "at 100 Innovation Drive, San Jose, CA 95134 (\"Party A\"); and"
        ))
        doc.add_element(Paragraph(
            text="**Beta Solutions LLC**, a California limited liability company "
                 "with offices at 200 Startup Blvd, San Francisco, CA 94105 (\"Party B\")."
        ))

        sections = [
            ("1. DEFINITION OF CONFIDENTIAL INFORMATION",
             "\"Confidential Information\" means any data or information, oral or written, "
             "that is treated as confidential by either party, including but not limited to: "
             "trade secrets, algorithms, source code, customer lists, financial projections, "
             "and business strategies."),
            ("2. OBLIGATIONS OF RECEIVING PARTY",
             "The Receiving Party shall: (a) hold all Confidential Information in strict "
             "confidence; (b) not disclose any Confidential Information to third parties "
             "without prior written consent; (c) use Confidential Information solely for "
             "the Purpose; and (d) protect Confidential Information using at least the same "
             "degree of care used to protect its own confidential information."),
            ("3. EXCLUSIONS",
             "This Agreement does not apply to information that: (a) is or becomes publicly "
             "available through no fault of the Receiving Party; (b) was already known to the "
             "Receiving Party without restriction; (c) is independently developed; or (d) is "
             "received from a third party without breach of any obligation."),
            ("4. TERM",
             "This Agreement shall remain in effect for a period of two (2) years from the "
             "Effective Date. Obligations of confidentiality shall survive termination for "
             "an additional three (3) years."),
            ("5. GOVERNING LAW",
             "This Agreement shall be governed by and construed in accordance with the laws "
             "of the State of California, without regard to conflict of laws principles."),
        ]

        for title, body in sections:
            doc.add_element(Heading(level=2, text=title))
            doc.add_element(Paragraph(text=body))

        # Signature block
        doc.add_element(PageBreak(from_page=1, to_page=2))
        doc.add_element(Heading(level=2, text="IN WITNESS WHEREOF"))
        doc.add_element(Paragraph(
            text="The parties have executed this Agreement as of the Effective Date."
        ))

        doc.add_element(Table(rows=[
            TableRow(cells=[
                TableCell(text="**ALPHA TECHNOLOGIES, INC.**", colspan=2),
                TableCell(text="**BETA SOLUTIONS LLC**", colspan=2),
            ]),
            TableRow(cells=[
                TableCell(text="Signature:"),
                TableCell(text="________________"),
                TableCell(text="Signature:"),
                TableCell(text="________________"),
            ]),
            TableRow(cells=[
                TableCell(text="Name:"),
                TableCell(text=""),
                TableCell(text="Name:"),
                TableCell(text=""),
            ]),
            TableRow(cells=[
                TableCell(text="Title:"),
                TableCell(text=""),
                TableCell(text="Title:"),
                TableCell(text=""),
            ]),
            TableRow(cells=[
                TableCell(text="Date:"),
                TableCell(text=""),
                TableCell(text="Date:"),
                TableCell(text=""),
            ]),
        ]))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "NON-DISCLOSURE" in text
        assert "Confidential Information" in text
        assert "GOVERNING LAW" in text
        assert "WITNESS WHEREOF" in text
        assert "Alpha Technologies" in text

        path = _roundtrip_docx(doc)
        assert path.exists()
        path = _roundtrip_pdf(doc)
        assert path.exists()

    def test_73_employment_contract(self):
        """Employment agreement with compensation table and benefits."""
        doc = _make_doc(source="legal")
        doc.add_element(Heading(level=1, text="EMPLOYMENT AGREEMENT"))
        doc.add_element(Paragraph(
            text="This Employment Agreement (\"Agreement\") is made between "
                 "Acme Corp (\"Employer\") and Jane Smith (\"Employee\")."
        ))

        doc.add_element(Heading(level=2, text="COMPENSATION"))
        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Component", is_header=True),
                TableCell(text="Amount", is_header=True),
                TableCell(text="Frequency", is_header=True),
            ]),
            TableRow(cells=[
                TableCell(text="Base Salary"),
                TableCell(text="$185,000.00"),
                TableCell(text="Annual"),
            ]),
            TableRow(cells=[
                TableCell(text="Signing Bonus"),
                TableCell(text="$25,000.00"),
                TableCell(text="One-time"),
            ]),
            TableRow(cells=[
                TableCell(text="Annual Bonus Target"),
                TableCell(text="20% of Base"),
                TableCell(text="Annual"),
            ]),
            TableRow(cells=[
                TableCell(text="Equity Grant"),
                TableCell(text="10,000 RSUs"),
                TableCell(text="4-year vest"),
            ]),
        ]))

        doc.add_element(Heading(level=2, text="BENEFITS"))
        doc.add_element(ListBlock(ordered=False, items=[
            ListItem(text="Health, dental, and vision insurance (100% employee, 80% dependents)"),
            ListItem(text="401(k) with 4% employer match"),
            ListItem(text="20 days PTO + 10 company holidays"),
            ListItem(text="$5,000/year professional development stipend"),
            ListItem(text="Remote work flexibility (3 days/week)"),
        ]))

        doc.add_element(Heading(level=2, text="NON-COMPETE"))
        doc.add_element(Paragraph(
            text="For a period of twelve (12) months following termination, "
                 "Employee shall not directly or indirectly engage in any business "
                 "that competes with Employer within a 50-mile radius of Employer's "
                 "principal place of business."
        ))

        doc.add_element(Footnote(number=1, text="Subject to California Business and Professions Code Section 16600."))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "$185,000" in text
        assert "RSU" in text
        assert "NON-COMPETE" in text
        path = _roundtrip_docx(doc)
        assert path.exists()

    def test_74_lease_agreement(self):
        """Residential lease with schedule of payments."""
        doc = _make_doc(source="legal")
        doc.add_element(Heading(level=1, text="RESIDENTIAL LEASE AGREEMENT"))

        # Key terms table
        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Lease Term", is_header=True, colspan=2),
            ]),
            TableRow(cells=[
                TableCell(text="Property Address"),
                TableCell(text="789 Oak Avenue, Apt 4B, Chicago, IL 60601"),
            ]),
            TableRow(cells=[
                TableCell(text="Landlord"),
                TableCell(text="Property Management LLC"),
            ]),
            TableRow(cells=[
                TableCell(text="Tenant(s)"),
                TableCell(text="John Doe and Jane Doe"),
            ]),
            TableRow(cells=[
                TableCell(text="Lease Start"),
                TableCell(text="May 1, 2026"),
            ]),
            TableRow(cells=[
                TableCell(text="Lease End"),
                TableCell(text="April 30, 2027"),
            ]),
            TableRow(cells=[
                TableCell(text="Monthly Rent"),
                TableCell(text="$2,400.00"),
            ]),
            TableRow(cells=[
                TableCell(text="Security Deposit"),
                TableCell(text="$2,400.00"),
            ]),
            TableRow(cells=[
                TableCell(text="Late Fee"),
                TableCell(text="$50.00 after the 5th of each month"),
            ]),
        ]))

        doc.add_element(Heading(level=2, text="TERMS AND CONDITIONS"))
        for i, clause in enumerate([
            "Rent is due on the 1st of each month.",
            "Tenant shall maintain renter's insurance with minimum $100,000 liability coverage.",
            "No pets allowed without prior written consent and additional $500 deposit.",
            "Tenant shall not sublease without Landlord's written approval.",
            "Landlord shall provide 24-hour notice before entry, except in emergencies.",
        ], 1):
            doc.add_element(Paragraph(text=f"**{i}.** {clause}"))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "$2,400" in text
        assert "renter" in text.lower()
        path = _roundtrip_docx(doc)
        assert path.exists()


# ═══════════════════════════════════════════════════════════════════
# FINANCIAL DOCUMENTS
# ═══════════════════════════════════════════════════════════════════

class TestFinancialDocuments:
    """Patterns from financial reports, invoices, tax forms."""

    def test_75_invoice(self):
        """Commercial invoice with line items and totals."""
        doc = _make_doc(source="financial")
        doc.add_element(Heading(level=1, text="INVOICE"))

        # Header info
        doc.add_element(Table(rows=[
            TableRow(cells=[
                TableCell(text="Invoice #: INV-2026-0042", colspan=2),
                TableCell(text="Date: April 10, 2026", colspan=2),
            ]),
            TableRow(cells=[
                TableCell(text="**From:**", colspan=2),
                TableCell(text="**Bill To:**", colspan=2),
            ]),
            TableRow(cells=[
                TableCell(text="Acme Services Inc.", colspan=2),
                TableCell(text="Widget Corp", colspan=2),
            ]),
            TableRow(cells=[
                TableCell(text="100 Business Park Dr", colspan=2),
                TableCell(text="200 Corporate Blvd", colspan=2),
            ]),
        ]))

        # Line items
        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Description", is_header=True),
                TableCell(text="Qty", is_header=True),
                TableCell(text="Unit Price", is_header=True),
                TableCell(text="Amount", is_header=True),
            ]),
            TableRow(cells=[
                TableCell(text="Software Development Services"),
                TableCell(text="160 hrs"),
                TableCell(text="$175.00"),
                TableCell(text="$28,000.00"),
            ]),
            TableRow(cells=[
                TableCell(text="Cloud Infrastructure Setup"),
                TableCell(text="1"),
                TableCell(text="$5,000.00"),
                TableCell(text="$5,000.00"),
            ]),
            TableRow(cells=[
                TableCell(text="QA Testing"),
                TableCell(text="40 hrs"),
                TableCell(text="$125.00"),
                TableCell(text="$5,000.00"),
            ]),
            TableRow(cells=[
                TableCell(text="", colspan=2),
                TableCell(text="**Subtotal**"),
                TableCell(text="$38,000.00"),
            ]),
            TableRow(cells=[
                TableCell(text="", colspan=2),
                TableCell(text="Tax (8.5%)"),
                TableCell(text="$3,230.00"),
            ]),
            TableRow(cells=[
                TableCell(text="", colspan=2),
                TableCell(text="**TOTAL DUE**"),
                TableCell(text="**$41,230.00**"),
            ]),
        ]))

        doc.add_element(Paragraph(text="Payment Terms: Net 30"))
        doc.add_element(Paragraph(text="Please remit payment to: Acme Services Inc., Account #XXXXX4567"))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "INV-2026-0042" in text
        assert "$41,230.00" in text
        assert "$28,000.00" in text
        path = _roundtrip_docx(doc)
        assert path.exists()

    def test_76_balance_sheet(self):
        """Balance sheet with nested categories and sub-totals."""
        doc = _make_doc(source="financial")
        doc.add_element(Heading(level=1, text="CONSOLIDATED BALANCE SHEET"))
        doc.add_element(Paragraph(text="As of December 31, 2025 (in thousands)"))

        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="", is_header=True),
                TableCell(text="2025", is_header=True),
                TableCell(text="2024", is_header=True),
            ]),
            TableRow(cells=[
                TableCell(text="**ASSETS**", colspan=3),
            ]),
            TableRow(cells=[
                TableCell(text="*Current Assets*", colspan=3),
            ]),
            TableRow(cells=[
                TableCell(text="  Cash and equivalents"),
                TableCell(text="$245,678"),
                TableCell(text="$198,432"),
            ]),
            TableRow(cells=[
                TableCell(text="  Accounts receivable, net"),
                TableCell(text="$89,234"),
                TableCell(text="$76,543"),
            ]),
            TableRow(cells=[
                TableCell(text="  Inventories"),
                TableCell(text="$34,567"),
                TableCell(text="$31,234"),
            ]),
            TableRow(cells=[
                TableCell(text="  **Total Current Assets**"),
                TableCell(text="**$369,479**"),
                TableCell(text="**$306,209**"),
            ]),
            TableRow(cells=[
                TableCell(text="*Non-Current Assets*", colspan=3),
            ]),
            TableRow(cells=[
                TableCell(text="  Property, plant & equipment"),
                TableCell(text="$567,890"),
                TableCell(text="$523,456"),
            ]),
            TableRow(cells=[
                TableCell(text="  Goodwill"),
                TableCell(text="$234,567"),
                TableCell(text="$234,567"),
            ]),
            TableRow(cells=[
                TableCell(text="  **TOTAL ASSETS**"),
                TableCell(text="**$1,171,936**"),
                TableCell(text="**$1,064,232**"),
            ]),
        ]))

        doc.add_element(Footnote(number=1, text="See accompanying notes to financial statements."))
        doc.add_element(Footnote(number=2, text="Prior year amounts have been reclassified to conform to current year presentation."))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "BALANCE SHEET" in text
        assert "$1,171,936" in text
        assert "Goodwill" in text
        path = _roundtrip_docx(doc)
        assert path.exists()

    def test_77_tax_form_w2_style(self):
        """W-2 style form with grid of labeled fields."""
        doc = _make_doc(source="tax")
        doc.add_element(Heading(level=1, text="Form W-2: Wage and Tax Statement"))
        doc.add_element(Paragraph(text="Tax Year 2025"))

        doc.add_element(Table(rows=[
            TableRow(cells=[
                TableCell(text="a. Employee's SSN\n***-**-6789"),
                TableCell(text="b. Employer's EIN\n12-3456789"),
            ]),
            TableRow(cells=[
                TableCell(text="c. Employer's name\nAcme Corp"),
                TableCell(text="d. Control number\n"),
            ]),
            TableRow(cells=[
                TableCell(text="e. Employee's name\nJohn Q. Doe"),
                TableCell(text="f. Employee's address\n123 Main St, Anytown, US 12345"),
            ]),
        ]))

        # Wage boxes
        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Box", is_header=True),
                TableCell(text="Description", is_header=True),
                TableCell(text="Amount", is_header=True),
            ]),
            TableRow(cells=[TableCell(text="1"), TableCell(text="Wages, tips, other compensation"), TableCell(text="$185,000.00")]),
            TableRow(cells=[TableCell(text="2"), TableCell(text="Federal income tax withheld"), TableCell(text="$37,000.00")]),
            TableRow(cells=[TableCell(text="3"), TableCell(text="Social security wages"), TableCell(text="$160,200.00")]),
            TableRow(cells=[TableCell(text="4"), TableCell(text="Social security tax withheld"), TableCell(text="$9,932.40")]),
            TableRow(cells=[TableCell(text="5"), TableCell(text="Medicare wages and tips"), TableCell(text="$185,000.00")]),
            TableRow(cells=[TableCell(text="6"), TableCell(text="Medicare tax withheld"), TableCell(text="$2,682.50")]),
            TableRow(cells=[TableCell(text="12a"), TableCell(text="DD - Health coverage cost"), TableCell(text="$14,400.00")]),
        ]))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "W-2" in text
        assert "$185,000" in text
        assert "Medicare" in text
        path = _roundtrip_docx(doc)
        assert path.exists()


# ═══════════════════════════════════════════════════════════════════
# MEDICAL / HEALTHCARE
# ═══════════════════════════════════════════════════════════════════

class TestMedicalDocuments:

    def test_78_patient_intake_form(self):
        """Medical intake form with checkboxes and fields."""
        doc = _make_doc(source="medical")
        doc.add_element(Heading(level=1, text="PATIENT INTAKE FORM"))
        doc.add_element(FormField(field_name="patient_name", field_type=FormFieldType.TEXT, value="John Doe"))
        doc.add_element(FormField(field_name="dob", field_type=FormFieldType.TEXT, value="01/15/1985"))
        doc.add_element(FormField(field_name="gender", field_type=FormFieldType.SELECT, value="Male"))

        doc.add_element(Heading(level=2, text="MEDICAL HISTORY"))
        doc.add_element(Paragraph(text="Please check all that apply:"))
        doc.add_element(ListBlock(ordered=False, items=[
            ListItem(text="Diabetes", checked=True),
            ListItem(text="Heart Disease", checked=False),
            ListItem(text="High Blood Pressure", checked=True),
            ListItem(text="Asthma", checked=False),
            ListItem(text="Cancer", checked=False),
            ListItem(text="Allergies (specify below)", checked=True),
        ]))
        doc.add_element(FormField(field_name="allergies", field_type=FormFieldType.TEXTAREA, value="Penicillin, Sulfa drugs"))

        doc.add_element(Heading(level=2, text="CURRENT MEDICATIONS"))
        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Medication", is_header=True),
                TableCell(text="Dosage", is_header=True),
                TableCell(text="Frequency", is_header=True),
            ]),
            TableRow(cells=[TableCell(text="Metformin"), TableCell(text="500mg"), TableCell(text="2x daily")]),
            TableRow(cells=[TableCell(text="Lisinopril"), TableCell(text="10mg"), TableCell(text="1x daily")]),
        ]))

        doc.add_element(FormField(field_name="patient_signature", field_type=FormFieldType.TEXT, value=""))
        doc.add_element(FormField(field_name="date_signed", field_type=FormFieldType.TEXT, value="04/10/2026"))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "PATIENT INTAKE" in text
        assert "Metformin" in text
        path = _roundtrip_docx(doc)
        assert path.exists()

    def test_79_lab_results(self):
        """Lab results with reference ranges and flags."""
        doc = _make_doc(source="medical")
        doc.add_element(Heading(level=1, text="LABORATORY RESULTS"))
        doc.add_element(Paragraph(text="Patient: John Doe | DOB: 01/15/1985 | MRN: 123456"))
        doc.add_element(Paragraph(text="Collected: 04/08/2026 08:30 AM | Reported: 04/09/2026 02:15 PM"))

        doc.add_element(Heading(level=2, text="COMPLETE BLOOD COUNT (CBC)"))
        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Test", is_header=True),
                TableCell(text="Result", is_header=True),
                TableCell(text="Flag", is_header=True),
                TableCell(text="Reference Range", is_header=True),
                TableCell(text="Units", is_header=True),
            ]),
            TableRow(cells=[TableCell(text="WBC"), TableCell(text="11.2"), TableCell(text="H"), TableCell(text="4.5-11.0"), TableCell(text="10^3/uL")]),
            TableRow(cells=[TableCell(text="RBC"), TableCell(text="4.8"), TableCell(text=""), TableCell(text="4.5-5.5"), TableCell(text="10^6/uL")]),
            TableRow(cells=[TableCell(text="Hemoglobin"), TableCell(text="14.2"), TableCell(text=""), TableCell(text="13.5-17.5"), TableCell(text="g/dL")]),
            TableRow(cells=[TableCell(text="Hematocrit"), TableCell(text="42.1"), TableCell(text=""), TableCell(text="38.0-50.0"), TableCell(text="%")]),
            TableRow(cells=[TableCell(text="Platelets"), TableCell(text="135"), TableCell(text="L"), TableCell(text="150-400"), TableCell(text="10^3/uL")]),
        ]))

        doc.add_element(Heading(level=2, text="COMPREHENSIVE METABOLIC PANEL"))
        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Test", is_header=True),
                TableCell(text="Result", is_header=True),
                TableCell(text="Flag", is_header=True),
                TableCell(text="Reference Range", is_header=True),
                TableCell(text="Units", is_header=True),
            ]),
            TableRow(cells=[TableCell(text="Glucose"), TableCell(text="142"), TableCell(text="H"), TableCell(text="70-100"), TableCell(text="mg/dL")]),
            TableRow(cells=[TableCell(text="BUN"), TableCell(text="18"), TableCell(text=""), TableCell(text="7-20"), TableCell(text="mg/dL")]),
            TableRow(cells=[TableCell(text="Creatinine"), TableCell(text="1.1"), TableCell(text=""), TableCell(text="0.7-1.3"), TableCell(text="mg/dL")]),
            TableRow(cells=[TableCell(text="eGFR"), TableCell(text=">60"), TableCell(text=""), TableCell(text=">60"), TableCell(text="mL/min")]),
        ]))

        doc.add_element(Paragraph(text="H = High, L = Low"))
        doc.add_element(Footnote(number=1, text="Results outside reference range should be evaluated in clinical context."))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "LABORATORY RESULTS" in text
        assert "Hemoglobin" in text
        assert "eGFR" in text
        path = _roundtrip_docx(doc)
        assert path.exists()
        path = _roundtrip_pdf(doc)
        assert path.exists()


# ═══════════════════════════════════════════════════════════════════
# GOVERNMENT / REGULATORY
# ═══════════════════════════════════════════════════════════════════

class TestGovernmentDocuments:

    def test_80_court_filing(self):
        """Court filing with case caption and numbered paragraphs."""
        doc = _make_doc(source="legal")
        doc.add_element(Heading(level=2, text="UNITED STATES DISTRICT COURT"))
        doc.add_element(Heading(level=3, text="CENTRAL DISTRICT OF CALIFORNIA"))

        # Case caption as table
        doc.add_element(Table(rows=[
            TableRow(cells=[
                TableCell(text="ALPHA CORP,\nPlaintiff,", rowspan=3),
                TableCell(text="Case No. 2:26-cv-01234-ABC"),
            ]),
            TableRow(cells=[
                TableCell(text="MOTION FOR SUMMARY JUDGMENT"),
            ]),
            TableRow(cells=[
                TableCell(text="Hearing: May 15, 2026\nCourtroom 8D, 9:00 AM"),
            ]),
            TableRow(cells=[
                TableCell(text="v."),
                TableCell(text="Judge: Hon. Sarah Johnson"),
            ]),
            TableRow(cells=[
                TableCell(text="BETA LLC,\nDefendant."),
                TableCell(text=""),
            ]),
        ]))

        doc.add_element(Heading(level=2, text="MEMORANDUM OF POINTS AND AUTHORITIES"))

        doc.add_element(Heading(level=3, text="I. INTRODUCTION"))
        doc.add_element(Paragraph(
            text="Plaintiff Alpha Corp (\"Alpha\") respectfully moves this Court "
                 "for summary judgment pursuant to Federal Rule of Civil Procedure 56. "
                 "There are no genuine disputes of material fact, and Alpha is entitled "
                 "to judgment as a matter of law."
        ))

        doc.add_element(Heading(level=3, text="II. STATEMENT OF UNDISPUTED FACTS"))
        doc.add_element(ListBlock(ordered=True, start=1, items=[
            ListItem(text="On January 5, 2025, Alpha and Beta entered into a Software License Agreement (\"SLA\"). (Ex. A.)"),
            ListItem(text="Section 4.2 of the SLA required Beta to pay quarterly license fees of $250,000. (Ex. A at 8.)"),
            ListItem(text="Beta failed to make payments for Q3 and Q4 2025. (Doe Decl. \u00b6 12.)"),
            ListItem(text="Alpha provided written notice of default on November 1, 2025. (Ex. B.)"),
            ListItem(text="Beta did not cure the default within the 30-day cure period. (Doe Decl. \u00b6 15.)"),
        ]))

        doc.add_element(Footnote(number=1, text="All citations refer to exhibits attached to the Declaration of John Doe."))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "DISTRICT COURT" in text
        assert "SUMMARY JUDGMENT" in text
        assert "Rule of Civil Procedure 56" in text
        assert "$250,000" in text
        path = _roundtrip_docx(doc)
        assert path.exists()

    def test_81_permit_application(self):
        """Government permit application with form fields."""
        doc = _make_doc(source="government")
        doc.add_element(Heading(level=1, text="BUILDING PERMIT APPLICATION"))
        doc.add_element(Heading(level=2, text="City of Los Angeles, Department of Building and Safety"))

        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Application Information", is_header=True, colspan=4),
            ]),
            TableRow(cells=[
                TableCell(text="Application No:"),
                TableCell(text="BP-2026-12345"),
                TableCell(text="Date Filed:"),
                TableCell(text="04/10/2026"),
            ]),
            TableRow(cells=[
                TableCell(text="Project Address:"),
                TableCell(text="456 Construction Ave", colspan=3),
            ]),
            TableRow(cells=[
                TableCell(text="APN:"),
                TableCell(text="5432-001-010"),
                TableCell(text="Zoning:"),
                TableCell(text="R-1"),
            ]),
            TableRow(cells=[
                TableCell(text="Scope of Work:", colspan=4),
            ]),
            TableRow(cells=[
                TableCell(text="New construction of single-family dwelling, 2,400 sq ft, 2 stories, attached 2-car garage.", colspan=4),
            ]),
        ]))

        doc.add_element(Heading(level=2, text="ESTIMATED VALUATION"))
        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Item", is_header=True),
                TableCell(text="Value", is_header=True),
            ]),
            TableRow(cells=[TableCell(text="Construction Cost"), TableCell(text="$450,000")]),
            TableRow(cells=[TableCell(text="Plan Check Fee"), TableCell(text="$4,500")]),
            TableRow(cells=[TableCell(text="Permit Fee"), TableCell(text="$6,750")]),
            TableRow(cells=[TableCell(text="School Fee"), TableCell(text="$10,800")]),
            TableRow(cells=[TableCell(text="**Total Fees**"), TableCell(text="**$22,050**")]),
        ]))

        doc.add_element(Heading(level=2, text="CERTIFICATIONS"))
        doc.add_element(Paragraph(
            text="I hereby certify that I am the owner of the property described above "
                 "and that all information provided is true and correct."
        ))
        doc.add_element(FormField(field_name="owner_signature", field_type=FormFieldType.TEXT, value=""))
        doc.add_element(FormField(field_name="date_signed", field_type=FormFieldType.TEXT, value=""))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "BUILDING PERMIT" in text
        assert "$22,050" in text
        path = _roundtrip_docx(doc)
        assert path.exists()

    def test_82_certificate_of_good_standing(self):
        """Secretary of State certificate."""
        doc = _make_doc(source="government")
        doc.add_element(Heading(level=1, text="CERTIFICATE OF GOOD STANDING"))
        doc.add_element(Heading(level=2, text="STATE OF DELAWARE"))
        doc.add_element(Heading(level=3, text="OFFICE OF THE SECRETARY OF STATE"))
        doc.add_element(Paragraph(
            text="I, JEFFREY W. BULLOCK, SECRETARY OF STATE OF THE STATE OF DELAWARE, "
                 "DO HEREBY CERTIFY THAT:"
        ))
        doc.add_element(Paragraph(
            text="ALPHA TECHNOLOGIES, INC. is a corporation duly incorporated under the "
                 "laws of the State of Delaware on April 15, 2020, and is in good standing "
                 "and has a legal corporate existence so far as the records of this office show."
        ))
        doc.add_element(Paragraph(text="File No. 1234567"))
        doc.add_element(Paragraph(text="Authentication No. ABC123456789"))
        doc.add_element(Paragraph(text="Date: April 10, 2026"))
        doc.add_element(Figure(caption="[STATE SEAL]", source="state-seal.png", figure_id="seal"))
        doc.add_element(FormField(field_name="secretary_signature", field_type=FormFieldType.TEXT, value="Jeffrey W. Bullock"))
        doc.add_element(Paragraph(text="Secretary of State"))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "GOOD STANDING" in text
        assert "duly incorporated" in text
        path = _roundtrip_docx(doc)
        assert path.exists()


# ═══════════════════════════════════════════════════════════════════
# ACADEMIC / RESEARCH
# ═══════════════════════════════════════════════════════════════════

class TestAcademicDocuments:

    def test_83_research_paper_structure(self):
        """Academic paper with abstract, sections, equations, citations."""
        doc = _make_doc(source="academic")
        doc.add_element(Heading(level=1, text="Attention Is All You Need: A Simplified Analysis"))
        doc.add_element(Paragraph(text="*Author Name, University of Example*"))

        doc.add_element(Heading(level=2, text="Abstract"))
        doc.add_element(Paragraph(
            text="We present a simplified analysis of the transformer architecture, "
                 "demonstrating that self-attention mechanisms achieve O(n^2) complexity "
                 "while enabling parallel computation of sequence dependencies."
        ))

        doc.add_element(Heading(level=2, text="1. Introduction"))
        doc.add_element(Paragraph(
            text="Sequence transduction models have traditionally relied on recurrent "
                 "neural networks. The transformer [1] replaces recurrence entirely with "
                 "attention mechanisms."
        ))

        doc.add_element(Heading(level=2, text="2. Model Architecture"))
        doc.add_element(Paragraph(text="The core of the transformer is the scaled dot-product attention:"))
        doc.add_element(MathBlock(expression=r"\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V"))

        doc.add_element(Paragraph(text="Multi-head attention combines *h* parallel attention functions:"))
        doc.add_element(MathBlock(expression=r"\text{MultiHead}(Q, K, V) = \text{Concat}(\text{head}_1, \ldots, \text{head}_h)W^O"))

        doc.add_element(Heading(level=2, text="3. Results"))
        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Model", is_header=True),
                TableCell(text="BLEU (EN-DE)", is_header=True),
                TableCell(text="BLEU (EN-FR)", is_header=True),
                TableCell(text="Params (M)", is_header=True),
            ]),
            TableRow(cells=[TableCell(text="Transformer (base)"), TableCell(text="27.3"), TableCell(text="38.1"), TableCell(text="65")]),
            TableRow(cells=[TableCell(text="Transformer (big)"), TableCell(text="28.4"), TableCell(text="41.0"), TableCell(text="213")]),
            TableRow(cells=[TableCell(text="LSTM (baseline)"), TableCell(text="25.2"), TableCell(text="35.6"), TableCell(text="180")]),
        ]))

        doc.add_element(Heading(level=2, text="References"))
        doc.add_element(Paragraph(text="[1] Vaswani et al., \"Attention Is All You Need\", NeurIPS 2017."))
        doc.add_element(Paragraph(text="[2] Bahdanau et al., \"Neural Machine Translation by Jointly Learning to Align and Translate\", ICLR 2015."))

        doc.add_element(Footnote(number=1, text="Code available at github.com/example/transformer"))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "Attention" in text
        assert "softmax" in text
        assert "BLEU" in text
        assert "27.3" in text
        path = _roundtrip_docx(doc)
        assert path.exists()
        path = _roundtrip_pdf(doc)
        assert path.exists()

    def test_84_transcript(self):
        """Academic transcript with semester tables."""
        doc = _make_doc(source="academic")
        doc.add_element(Heading(level=1, text="OFFICIAL ACADEMIC TRANSCRIPT"))
        doc.add_element(Paragraph(text="University of Example"))
        doc.add_element(Paragraph(text="Student: Jane Q. Smith | ID: 2022-00456 | Major: Computer Science, B.S."))

        for semester, courses in [
            ("Fall 2022", [("CS 101", "Intro to CS", "A", "4"), ("MATH 201", "Linear Algebra", "A-", "3"), ("ENG 101", "Composition", "B+", "3")]),
            ("Spring 2023", [("CS 201", "Data Structures", "A", "4"), ("CS 210", "Discrete Math", "B+", "3"), ("PHYS 101", "Physics I", "A-", "4")]),
        ]:
            doc.add_element(Heading(level=3, text=semester))
            rows = [TableRow(is_header=True, cells=[
                TableCell(text="Course", is_header=True),
                TableCell(text="Title", is_header=True),
                TableCell(text="Grade", is_header=True),
                TableCell(text="Credits", is_header=True),
            ])]
            for code, title, grade, credits in courses:
                rows.append(TableRow(cells=[
                    TableCell(text=code), TableCell(text=title),
                    TableCell(text=grade), TableCell(text=credits),
                ]))
            doc.add_element(Table(rows=rows))

        doc.add_element(Paragraph(text="Cumulative GPA: 3.72 | Total Credits: 21"))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "TRANSCRIPT" in text
        assert "CS 201" in text
        assert "3.72" in text
        path = _roundtrip_docx(doc)
        assert path.exists()


# ═══════════════════════════════════════════════════════════════════
# CORPORATE / BUSINESS
# ═══════════════════════════════════════════════════════════════════

class TestCorporateDocuments:

    def test_85_board_resolution(self):
        """Board resolution with WHEREAS/RESOLVED clauses."""
        doc = _make_doc(source="corporate")
        doc.add_element(Heading(level=1, text="UNANIMOUS WRITTEN CONSENT OF THE BOARD OF DIRECTORS"))
        doc.add_element(Heading(level=2, text="OF ALPHA TECHNOLOGIES, INC."))
        doc.add_element(Paragraph(text="Effective Date: April 10, 2026"))

        doc.add_element(Paragraph(
            text="The undersigned, being all of the directors of Alpha Technologies, Inc., "
                 "a Delaware corporation (the \"Company\"), hereby adopt the following "
                 "resolutions by unanimous written consent:"
        ))

        for clause in [
            "WHEREAS, the Company desires to authorize a new Series B round of preferred stock financing;",
            "WHEREAS, the Board has reviewed and considered the terms of the proposed financing;",
            "WHEREAS, the Board has determined that the proposed financing is in the best interests of the Company;",
        ]:
            doc.add_element(Paragraph(text=clause))

        doc.add_element(Paragraph(text="NOW, THEREFORE, BE IT RESOLVED:"))

        doc.add_element(ListBlock(ordered=True, start=1, items=[
            ListItem(text="The Company is authorized to issue up to 5,000,000 shares of Series B Preferred Stock at a price of $10.00 per share."),
            ListItem(text="The total authorized capital is increased from $10,000,000 to $60,000,000."),
            ListItem(text="The officers of the Company are authorized to execute any documents necessary to effectuate the foregoing."),
            ListItem(text="The Company's legal counsel, Wilson & Associates LLP, is directed to prepare the necessary amendments to the Certificate of Incorporation."),
        ]))

        doc.add_element(Paragraph(text="[Signatures on following page]"))
        doc.add_element(PageBreak(from_page=1, to_page=2))

        # Signature block
        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Director", is_header=True),
                TableCell(text="Signature", is_header=True),
                TableCell(text="Date", is_header=True),
            ]),
            TableRow(cells=[TableCell(text="Sarah Chen, Chairperson"), TableCell(text=""), TableCell(text="")]),
            TableRow(cells=[TableCell(text="Michael Park"), TableCell(text=""), TableCell(text="")]),
            TableRow(cells=[TableCell(text="Lisa Wang"), TableCell(text=""), TableCell(text="")]),
        ]))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "BOARD OF DIRECTORS" in text
        assert "WHEREAS" in text
        assert "RESOLVED" in text
        assert "Series B" in text
        assert "$10.00" in text
        path = _roundtrip_docx(doc)
        assert path.exists()
        path = _roundtrip_pdf(doc)
        assert path.exists()

    def test_86_meeting_minutes(self):
        """Corporate meeting minutes with motions and votes."""
        doc = _make_doc(source="corporate")
        doc.add_element(Heading(level=1, text="MINUTES OF THE ANNUAL MEETING OF SHAREHOLDERS"))
        doc.add_element(Paragraph(text="Date: March 15, 2026 | Time: 10:00 AM PST | Location: Conference Room A"))
        doc.add_element(Paragraph(text="**Present:** Sarah Chen (Chair), Michael Park, Lisa Wang, David Kim, Amy Liu"))
        doc.add_element(Paragraph(text="**Absent:** Robert Johnson (excused)"))
        doc.add_element(Paragraph(text="**Also Present:** Thomas Lee (Secretary), Jennifer Wu (General Counsel)"))

        doc.add_element(Heading(level=2, text="1. CALL TO ORDER"))
        doc.add_element(Paragraph(
            text="The meeting was called to order by Chairperson Chen at 10:05 AM. "
                 "A quorum was established with 5 of 6 directors present."
        ))

        doc.add_element(Heading(level=2, text="2. APPROVAL OF PREVIOUS MINUTES"))
        doc.add_element(Paragraph(
            text="**MOTION:** Director Park moved to approve the minutes of the December 2025 meeting. "
                 "Seconded by Director Wang. **APPROVED** unanimously (5-0)."
        ))

        doc.add_element(Heading(level=2, text="3. FINANCIAL REPORT"))
        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Metric", is_header=True),
                TableCell(text="Q4 2025", is_header=True),
                TableCell(text="Q4 2024", is_header=True),
                TableCell(text="YoY Change", is_header=True),
            ]),
            TableRow(cells=[TableCell(text="Revenue"), TableCell(text="$12.4M"), TableCell(text="$9.8M"), TableCell(text="+26.5%")]),
            TableRow(cells=[TableCell(text="Net Income"), TableCell(text="$2.1M"), TableCell(text="$1.4M"), TableCell(text="+50.0%")]),
            TableRow(cells=[TableCell(text="ARR"), TableCell(text="$48.2M"), TableCell(text="$36.0M"), TableCell(text="+33.9%")]),
        ]))

        doc.add_element(Heading(level=2, text="4. ADJOURNMENT"))
        doc.add_element(Paragraph(
            text="There being no further business, Director Kim moved to adjourn. "
                 "Seconded by Director Liu. Meeting adjourned at 11:45 AM."
        ))
        doc.add_element(FormField(field_name="secretary_signature", field_type=FormFieldType.TEXT, value="Thomas Lee"))
        doc.add_element(Paragraph(text="Thomas Lee, Secretary"))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "ANNUAL MEETING" in text
        assert "MOTION" in text
        assert "$12.4M" in text
        assert "unanimously" in text
        path = _roundtrip_docx(doc)
        assert path.exists()

    def test_87_multi_page_report_with_all_elements(self):
        """Complex 5-page corporate report using every element type."""
        doc = _make_doc(source="corporate")

        # Page 1: Title + Executive Summary
        doc.add_element(Heading(level=1, text="Q1 2026 QUARTERLY BUSINESS REVIEW"))
        doc.add_element(Paragraph(text="*Prepared for the Board of Directors*"))
        doc.add_element(Paragraph(text="**Confidential** \u2014 Do not distribute"))
        doc.add_element(Heading(level=2, text="Executive Summary"))
        doc.add_element(Paragraph(
            text="Q1 2026 exceeded targets across all key metrics. Revenue grew 28% YoY "
                 "to $14.2M, driven by enterprise expansion and new logo acquisition. "
                 "The company achieved GAAP profitability for the first time."
        ))
        doc.add_element(Annotation(annotation_type="comment", text="CFO: Verify GAAP claim with auditors"))

        doc.add_element(PageBreak(from_page=1, to_page=2))

        # Page 2: Financial Summary
        doc.add_element(Heading(level=2, text="Financial Performance"))
        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Metric", is_header=True),
                TableCell(text="Q1 2026", is_header=True),
                TableCell(text="Q1 2025", is_header=True),
                TableCell(text="YoY", is_header=True),
                TableCell(text="vs Plan", is_header=True),
            ]),
            TableRow(cells=[TableCell(text="Revenue"), TableCell(text="$14.2M"), TableCell(text="$11.1M"), TableCell(text="+28%"), TableCell(text="+5%")]),
            TableRow(cells=[TableCell(text="Gross Margin"), TableCell(text="72.3%"), TableCell(text="68.1%"), TableCell(text="+4.2pp"), TableCell(text="+2.3pp")]),
            TableRow(cells=[TableCell(text="EBITDA"), TableCell(text="$2.8M"), TableCell(text="$1.2M"), TableCell(text="+133%"), TableCell(text="+40%")]),
            TableRow(cells=[TableCell(text="Net Income"), TableCell(text="$0.4M"), TableCell(text="($0.8M)"), TableCell(text="N/A"), TableCell(text="+$1.2M")]),
            TableRow(cells=[TableCell(text="Cash"), TableCell(text="$32.1M"), TableCell(text="$28.4M"), TableCell(text="+13%"), TableCell(text="On plan")]),
        ]))

        doc.add_element(MathBlock(expression=r"\text{Rule of 40} = \text{Revenue Growth} + \text{EBITDA Margin} = 28\% + 19.7\% = 47.7\%"))

        doc.add_element(Footnote(number=1, text="Revenue recognition per ASC 606."))
        doc.add_element(Footnote(number=2, text="EBITDA is a non-GAAP measure. See appendix for reconciliation."))

        doc.add_element(PageBreak(from_page=2, to_page=3))

        # Page 3: Product & Engineering
        doc.add_element(Heading(level=2, text="Product & Engineering"))
        doc.add_element(ListBlock(ordered=False, items=[
            ListItem(text="Shipped v3.0 with AI-powered document analysis (NPS: 72)"),
            ListItem(text="Reduced P50 latency from 340ms to 120ms (-65%)"),
            ListItem(text="99.97% uptime (target: 99.95%)"),
            ListItem(text="Zero critical security incidents"),
        ]))

        doc.add_element(Heading(level=3, text="Technical Debt"))
        doc.add_element(CodeBlock(language="sql", code="-- Remaining migration queries\nSELECT COUNT(*) FROM legacy_users WHERE migrated = FALSE;\n-- Result: 1,247 users (2.3% of total)"))

        doc.add_element(Figure(caption="System Architecture v3.0", source="architecture-v3.png", figure_id="fig-arch"))

        doc.add_element(PageBreak(from_page=3, to_page=4))

        # Page 4: Sales & Marketing
        doc.add_element(Heading(level=2, text="Sales Pipeline"))
        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Stage", is_header=True),
                TableCell(text="Count", is_header=True),
                TableCell(text="Value", is_header=True),
                TableCell(text="Weighted", is_header=True),
            ]),
            TableRow(cells=[TableCell(text="Prospect"), TableCell(text="142"), TableCell(text="$8.2M"), TableCell(text="$0.8M")]),
            TableRow(cells=[TableCell(text="Qualified"), TableCell(text="68"), TableCell(text="$12.4M"), TableCell(text="$3.1M")]),
            TableRow(cells=[TableCell(text="Proposal"), TableCell(text="23"), TableCell(text="$6.8M"), TableCell(text="$3.4M")]),
            TableRow(cells=[TableCell(text="Negotiation"), TableCell(text="11"), TableCell(text="$4.2M"), TableCell(text="$3.4M")]),
            TableRow(cells=[TableCell(text="**Total Pipeline**"), TableCell(text="**244**"), TableCell(text="**$31.6M**"), TableCell(text="**$10.7M**")]),
        ]))

        doc.add_element(CrossRef(ref_type="section", ref_id="financial-performance"))

        doc.add_element(PageBreak(from_page=4, to_page=5))

        # Page 5: Risks & Next Steps
        doc.add_element(Heading(level=2, text="Key Risks"))
        doc.add_element(ListBlock(ordered=True, start=1, items=[
            ListItem(text="Enterprise deal concentration: Top 3 customers = 35% of ARR"),
            ListItem(text="Engineering hiring: 4 open senior roles, avg time-to-fill 67 days"),
            ListItem(text="Competitive pressure from BigCo entering the market in Q3"),
        ]))

        doc.add_element(Heading(level=2, text="Q2 Priorities"))
        doc.add_element(ListBlock(ordered=True, start=1, items=[
            ListItem(text="Close 3 enterprise deals in pipeline ($4.2M total)"),
            ListItem(text="Ship v3.1 with SOC 2 Type II compliance"),
            ListItem(text="Hire VP Engineering and 3 senior engineers"),
            ListItem(text="Begin Series C preparation"),
        ]))

        doc.add_element(Paragraph(text="**End of Report**"))

        # Verify round-trip
        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)

        # Spot check content from all 5 pages
        assert "QUARTERLY BUSINESS REVIEW" in text
        assert "$14.2M" in text
        assert "Rule of 40" in text or "Rule" in text
        assert "99.97%" in text
        assert "legacy_users" in text
        assert "$31.6M" in text
        assert "Series C" in text

        # Element type counts
        headings = [e for e in doc2.elements if hasattr(e, 'level')]
        tables = [e for e in doc2.elements if hasattr(e, 'rows')]
        assert len(headings) >= 7
        assert len(tables) >= 2  # some tables may merge during serialization

        # DOCX and PDF
        path = _roundtrip_docx(doc)
        assert path.exists()
        assert path.stat().st_size > 5000  # non-trivial file

        path = _roundtrip_pdf(doc)
        assert path.exists()
        assert path.stat().st_size > 5000


# ═══════════════════════════════════════════════════════════════════
# INSURANCE / CLAIMS
# ═══════════════════════════════════════════════════════════════════

class TestInsuranceDocuments:

    def test_88_insurance_claim(self):
        """Insurance claim form with accident details."""
        doc = _make_doc(source="insurance")
        doc.add_element(Heading(level=1, text="AUTOMOBILE INSURANCE CLAIM FORM"))
        doc.add_element(Paragraph(text="Policy Number: AUTO-2026-789456"))
        doc.add_element(Paragraph(text="Claim Number: CLM-2026-00123"))

        doc.add_element(Heading(level=2, text="INSURED INFORMATION"))
        doc.add_element(Table(rows=[
            TableRow(cells=[TableCell(text="Name:"), TableCell(text="John Doe")]),
            TableRow(cells=[TableCell(text="Policy #:"), TableCell(text="AUTO-2026-789456")]),
            TableRow(cells=[TableCell(text="Vehicle:"), TableCell(text="2024 Toyota Camry SE")]),
            TableRow(cells=[TableCell(text="VIN:"), TableCell(text="1HGCG5655WA043589")]),
        ]))

        doc.add_element(Heading(level=2, text="ACCIDENT DETAILS"))
        doc.add_element(Table(rows=[
            TableRow(cells=[TableCell(text="Date:"), TableCell(text="04/05/2026")]),
            TableRow(cells=[TableCell(text="Time:"), TableCell(text="3:45 PM")]),
            TableRow(cells=[TableCell(text="Location:"), TableCell(text="Intersection of 5th St and Main Ave, Los Angeles, CA")]),
            TableRow(cells=[TableCell(text="Police Report #:"), TableCell(text="LAPD-2026-04-12345")]),
        ]))

        doc.add_element(Heading(level=2, text="DAMAGE ESTIMATE"))
        doc.add_element(Table(rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Item", is_header=True),
                TableCell(text="Repair", is_header=True),
                TableCell(text="Cost", is_header=True),
            ]),
            TableRow(cells=[TableCell(text="Front bumper"), TableCell(text="Replace"), TableCell(text="$1,200")]),
            TableRow(cells=[TableCell(text="Hood"), TableCell(text="Repair/repaint"), TableCell(text="$800")]),
            TableRow(cells=[TableCell(text="Headlight assembly (L)"), TableCell(text="Replace"), TableCell(text="$450")]),
            TableRow(cells=[TableCell(text="Labor"), TableCell(text="12 hours"), TableCell(text="$1,440")]),
            TableRow(cells=[TableCell(text="**Total Estimate**"), TableCell(text=""), TableCell(text="**$3,890**")]),
        ]))

        doc.add_element(Paragraph(
            text="I certify that the above information is true and correct to the best of my knowledge."
        ))
        doc.add_element(FormField(field_name="claimant_signature", field_type=FormFieldType.TEXT, value=""))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "INSURANCE CLAIM" in text
        assert "$3,890" in text
        assert "1HGCG5655WA043589" in text
        path = _roundtrip_docx(doc)
        assert path.exists()


# ═══════════════════════════════════════════════════════════════════
# IMMIGRATION / IDENTITY
# ═══════════════════════════════════════════════════════════════════

class TestIdentityDocuments:

    def test_89_apostille(self):
        """Apostille/authentication certificate."""
        doc = _make_doc(source="government")
        doc.add_element(Heading(level=1, text="APOSTILLE"))
        doc.add_element(Paragraph(text="(Convention de La Haye du 5 octobre 1961)"))

        doc.add_element(Table(rows=[
            TableRow(cells=[
                TableCell(text="1. Country:", colspan=2),
            ]),
            TableRow(cells=[
                TableCell(text="   UNITED STATES OF AMERICA", colspan=2),
            ]),
            TableRow(cells=[
                TableCell(text="2. This public document"),
                TableCell(text="has been signed by John Smith"),
            ]),
            TableRow(cells=[
                TableCell(text="3. Acting in the capacity of"),
                TableCell(text="Notary Public"),
            ]),
            TableRow(cells=[
                TableCell(text="4. Bears the seal/stamp of"),
                TableCell(text="State of California"),
            ]),
            TableRow(cells=[
                TableCell(text="Certified", colspan=2),
            ]),
            TableRow(cells=[
                TableCell(text="5. At Sacramento"),
                TableCell(text="6. On April 10, 2026"),
            ]),
            TableRow(cells=[
                TableCell(text="7. By Secretary of State"),
                TableCell(text="8. No. AP-2026-12345"),
            ]),
            TableRow(cells=[
                TableCell(text="9. Seal/Stamp:", colspan=2),
            ]),
            TableRow(cells=[
                TableCell(text="10. Signature:", colspan=2),
            ]),
        ]))

        doc.add_element(Figure(caption="[OFFICIAL SEAL]", source="apostille-seal.png"))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "APOSTILLE" in text
        assert "La Haye" in text
        path = _roundtrip_docx(doc)
        assert path.exists()

    def test_90_birth_certificate_layout(self):
        """Birth certificate with structured fields."""
        doc = _make_doc(source="government")
        doc.add_element(Heading(level=1, text="CERTIFICATE OF LIVE BIRTH"))
        doc.add_element(Heading(level=2, text="STATE OF CALIFORNIA"))

        doc.add_element(Table(rows=[
            TableRow(cells=[
                TableCell(text="1. CHILD'S NAME", colspan=3),
            ]),
            TableRow(cells=[
                TableCell(text="First: John"),
                TableCell(text="Middle: Michael"),
                TableCell(text="Last: Doe"),
            ]),
            TableRow(cells=[
                TableCell(text="2. SEX\nMale"),
                TableCell(text="3. DATE OF BIRTH\nJanuary 15, 2026"),
                TableCell(text="4. TIME OF BIRTH\n8:42 AM"),
            ]),
            TableRow(cells=[
                TableCell(text="5. PLACE OF BIRTH", colspan=3),
            ]),
            TableRow(cells=[
                TableCell(text="Hospital: Cedars-Sinai Medical Center"),
                TableCell(text="City: Los Angeles", colspan=2),
            ]),
            TableRow(cells=[
                TableCell(text="6. MOTHER'S NAME\nJane Marie Doe (nee Smith)", colspan=3),
            ]),
            TableRow(cells=[
                TableCell(text="7. FATHER'S NAME\nRobert James Doe", colspan=3),
            ]),
        ]))

        doc.add_element(Paragraph(text="Certificate No: 2026-LA-012345"))
        doc.add_element(Paragraph(text="Filed: January 20, 2026"))
        doc.add_element(Figure(caption="[REGISTRAR SEAL]", source="registrar-seal.png"))
        doc.add_element(FormField(field_name="registrar_signature", field_type=FormFieldType.TEXT, value=""))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "CERTIFICATE OF LIVE BIRTH" in text
        assert "Cedars-Sinai" in text
        path = _roundtrip_docx(doc)
        assert path.exists()
        path = _roundtrip_pdf(doc)
        assert path.exists()


# ═══════════════════════════════════════════════════════════════════
# EDGE CASE COMBOS
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCaseCombos:
    """Combine tricky patterns that appear in real documents."""

    def test_91_table_immediately_after_heading(self):
        """No paragraph between heading and table (common in forms)."""
        doc = _make_doc()
        doc.add_element(Heading(level=2, text="Section A: Personal Information"))
        doc.add_element(Table(rows=[
            TableRow(cells=[TableCell(text="Name:"), TableCell(text="")]),
            TableRow(cells=[TableCell(text="Address:"), TableCell(text="")]),
        ]))
        doc.add_element(Heading(level=2, text="Section B: Employment"))
        doc.add_element(Table(rows=[
            TableRow(cells=[TableCell(text="Employer:"), TableCell(text="")]),
        ]))

        doc2 = _roundtrip_dox(doc)
        tables = [e for e in doc2.elements if hasattr(e, 'rows')]
        assert len(tables) == 2

    def test_92_consecutive_tables(self):
        """Two tables back to back with no content between them."""
        doc = _make_doc()
        doc.add_element(Table(rows=[
            TableRow(cells=[TableCell(text="A1"), TableCell(text="A2")]),
        ]))
        doc.add_element(Table(rows=[
            TableRow(cells=[TableCell(text="B1"), TableCell(text="B2")]),
        ]))

        doc2 = _roundtrip_dox(doc)
        tables = [e for e in doc2.elements if hasattr(e, 'rows')]
        assert len(tables) == 2

    def test_93_footnotes_scattered_across_pages(self):
        """Footnotes referenced from different pages."""
        doc = _make_doc()
        doc.add_element(Paragraph(text="First statement on page 1. [^1]"))
        doc.add_element(Footnote(number=1, text="Source for first statement."))
        doc.add_element(PageBreak(from_page=1, to_page=2))
        doc.add_element(Paragraph(text="Second statement on page 2. [^2]"))
        doc.add_element(Footnote(number=2, text="Source for second statement."))
        doc.add_element(PageBreak(from_page=2, to_page=3))
        doc.add_element(Paragraph(text="Third statement on page 3. [^3]"))
        doc.add_element(Footnote(number=3, text="Source for third statement."))

        doc2 = _roundtrip_dox(doc)
        footnotes = [e for e in doc2.elements if hasattr(e, 'number') and hasattr(e, 'text') and 'Source' in getattr(e, 'text', '')]
        assert len(footnotes) >= 3

    def test_94_form_fields_inside_paragraphs_context(self):
        """Form fields mixed with paragraphs (application forms)."""
        doc = _make_doc()
        doc.add_element(Paragraph(text="Applicant Name:"))
        doc.add_element(FormField(field_name="name", field_type=FormFieldType.TEXT, value="John Doe"))
        doc.add_element(Paragraph(text="Date of Application:"))
        doc.add_element(FormField(field_name="date", field_type=FormFieldType.TEXT, value="04/10/2026"))
        doc.add_element(Paragraph(text="Type of Request:"))
        doc.add_element(FormField(field_name="request_type", field_type=FormFieldType.SELECT, value="New"))
        doc.add_element(Paragraph(text="Additional Comments:"))
        doc.add_element(FormField(field_name="comments", field_type=FormFieldType.TEXTAREA, value="Please expedite."))

        doc2 = _roundtrip_dox(doc)
        assert len(doc2.elements) >= 8
        path = _roundtrip_docx(doc)
        assert path.exists()

    def test_95_document_with_annotations_and_cross_refs(self):
        """Annotations + cross-references (review/audit documents)."""
        doc = _make_doc()
        doc.add_element(Heading(level=1, text="Audit Report"))
        doc.add_element(Paragraph(text="See findings in the table below."))
        doc.add_element(CrossRef(ref_type="table", ref_id="findings-table"))
        doc.add_element(Table(table_id="findings-table", rows=[
            TableRow(is_header=True, cells=[
                TableCell(text="Finding", is_header=True),
                TableCell(text="Severity", is_header=True),
                TableCell(text="Status", is_header=True),
            ]),
            TableRow(cells=[TableCell(text="Missing access logs"), TableCell(text="High"), TableCell(text="Open")]),
            TableRow(cells=[TableCell(text="Expired SSL cert"), TableCell(text="Critical"), TableCell(text="Resolved")]),
        ]))
        doc.add_element(Annotation(annotation_type="comment", text="Reviewer: Verify SSL cert replacement date"))
        doc.add_element(CrossRef(ref_type="section", ref_id="remediation-plan"))

        doc2 = _roundtrip_dox(doc)
        text = _all_text(doc2)
        assert "Audit Report" in text
        assert "Missing access logs" in text
        path = _roundtrip_docx(doc)
        assert path.exists()

    def test_96_all_form_field_types(self):
        """Every FormFieldType in one document."""
        doc = _make_doc()
        doc.add_element(Heading(level=1, text="Complete Form"))
        for ft in FormFieldType:
            doc.add_element(FormField(
                field_name=f"field_{ft.value}",
                field_type=ft,
                value=f"sample_{ft.value}",
            ))

        doc2 = _roundtrip_dox(doc)
        assert len(doc2.elements) >= len(FormFieldType) + 1
        path = _roundtrip_docx(doc)
        assert path.exists()
        path = _roundtrip_pdf(doc)
        assert path.exists()

    def test_97_very_long_legal_document(self):
        """Simulates a 20-page contract with repetitive clause structure."""
        doc = _make_doc(source="legal")
        doc.add_element(Heading(level=1, text="MASTER SERVICES AGREEMENT"))

        for i in range(1, 21):
            doc.add_element(Heading(level=2, text=f"ARTICLE {i}: SECTION TITLE {i}"))
            doc.add_element(Paragraph(
                text=f"{i}.1 Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
                     f"Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
                     f"Section {i} contains important contractual obligations that both "
                     f"parties must adhere to throughout the term of this Agreement."
            ))
            doc.add_element(Paragraph(
                text=f"{i}.2 Notwithstanding the foregoing, Party A shall indemnify and "
                     f"hold harmless Party B from and against all claims arising under "
                     f"this Article {i}."
            ))
            if i % 5 == 0:
                doc.add_element(PageBreak(from_page=i // 5, to_page=i // 5 + 1))

        doc2 = _roundtrip_dox(doc)
        headings = [e for e in doc2.elements if hasattr(e, 'level')]
        assert len(headings) >= 20  # 1 main + 20 article headings
        text = _all_text(doc2)
        assert "ARTICLE 20" in text
        assert "indemnify" in text

        path = _roundtrip_docx(doc)
        assert path.exists()
        assert path.stat().st_size > 10000

        path = _roundtrip_pdf(doc)
        assert path.exists()
