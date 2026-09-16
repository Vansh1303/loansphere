# LoanSphere — Bank Form Auto-Filler Spec

Follow SPEC_DESIGN_SYSTEM.md for all styling.
Depends on: SPEC_KYC.md (identity data), SPEC_FEATURES.md (financial data),
SPEC_VERDICT.md (eligible banks list). This is the final step in the
pipeline — it turns an approved/review verdict into a downloadable,
pre-filled official bank application form.

---

## 1. Why this module exists

This directly answers the panel's original question: "how will you align
with the banks' own forms?" Instead of generating a custom LoanSphere
document (which no bank would accept), this module takes the **actual
official application PDF** published by a real bank and pre-fills it with
the user's KYC and financial profile data — producing a document the user
can genuinely take to a bank branch or upload to the bank's portal.

**Scope for this project**: implement 2 banks fully (SBI and one other,
e.g. HDFC) across the loan types you already have real PDFs for or can
source easily. The architecture must make adding a 3rd/4th/5th bank later
a config change, not a code rewrite — but you do not need to source and
map all 5 banks' forms to finish this module for your deadline.

---

## 2. Two Technical Approaches — pick based on the PDF type

Official bank PDFs come in two forms. Check each one you download:

**Type A — Fillable PDF (has AcroForm fields)**
Open the PDF in Adobe Acrobat or check with PyMuPDF (`doc.is_form_pdf`). If
the fields are clickable/fillable natively, use this approach — it's far
more reliable.

```python
import fitz  # PyMuPDF

def fill_form_pdf(template_path, output_path, field_values: dict):
    doc = fitz.open(template_path)
    for page in doc:
        for widget in page.widgets():
            field_name = widget.field_name
            if field_name in field_values:
                widget.field_value = str(field_values[field_name])
                widget.update()
    doc.save(output_path)
    doc.close()
```

**Type B — Flat/non-fillable PDF (just an image of a form)**
Most official bank PDFs, including the SBI Home Loan form you already have,
are this type. You overlay text at fixed x/y coordinates on top of the
blank form. This requires manually mapping each field's position once per
form template.

```python
import fitz

def overlay_fill_pdf(template_path, output_path, field_positions: list):
    """
    field_positions: list of dicts like
    {"page": 0, "x": 120, "y": 340, "text": "Vansh Jha", "font_size": 9}
    """
    doc = fitz.open(template_path)
    for field in field_positions:
        page = doc[field["page"]]
        page.insert_text(
            (field["x"], field["y"]),
            field["text"],
            fontsize=field.get("font_size", 9),
            fontname="helv"
        )
    doc.save(output_path)
    doc.close()
```

**How to find x/y coordinates for Type B**: open the PDF in a coordinate
inspector (PyMuPDF has a debug mode, or use `page.get_text("dict")` to see
where existing text sits on the page as a reference), or simplest: open the
PDF in a PDF editor, hover over where each blank line is, note the
approximate position, and calibrate by trial and error — fill a test value,
open the output, adjust coordinates until text lands on the blank lines.
This is manual, one-time setup work per bank form.

---

## 3. Bank Form Configuration

### `app/data/bank_forms/` (new directory)

Store each bank's actual official PDF template here:
```
app/data/bank_forms/
    sbi_home_loan_template.pdf
    hdfc_personal_loan_template.pdf
    ... (add more as you source them)
```

### `app/data/bank_form_mappings.py`

One config entry per bank + loan type combination. This is the layer that
makes adding new banks a config change, not new code.

```python
BANK_FORM_MAPPINGS = {
    ("SBI", "home"): {
        "template_path": "app/data/bank_forms/sbi_home_loan_template.pdf",
        "fill_type": "overlay",  # or "acroform"
        "field_map": [
            # Maps LoanSphere data keys to PDF positions/field names
            {"source": "full_name", "page": 0, "x": 130, "y": 210, "font_size": 9},
            {"source": "pan_number", "page": 0, "x": 130, "y": 240, "font_size": 9},
            {"source": "date_of_birth", "page": 0, "x": 130, "y": 270, "font_size": 9},
            {"source": "mobile", "page": 0, "x": 350, "y": 210, "font_size": 9},
            {"source": "requested_loan_amount", "page": 2, "x": 200, "y": 400, "font_size": 9},
            {"source": "requested_tenure_months", "page": 2, "x": 200, "y": 430, "font_size": 9},
            {"source": "monthly_income", "page": 1, "x": 250, "y": 500, "font_size": 9},
            {"source": "employment_type", "page": 1, "x": 250, "y": 530, "font_size": 9},
            # add more fields as needed, matched to the actual template's blank lines
        ]
    },
    ("HDFC", "personal"): {
        "template_path": "app/data/bank_forms/hdfc_personal_loan_template.pdf",
        "fill_type": "overlay",
        "field_map": [
            # populate once you source and inspect the HDFC template
        ]
    }
}
```

`source` values map to keys the fill function will look up from a combined
data dict assembled from KYC + financial profile + the specific loan
request — see Section 4.

---

## 4. Backend Logic

### `app/models/form_filler.py`

```python
import fitz
from app.data.bank_form_mappings import BANK_FORM_MAPPINGS
from app.models.kyc import get_kyc_record
from app.models.feature_engineering import get_financial_profile

def assemble_fill_data(user_id, requested_loan_amount, requested_tenure_months, requested_loan_type):
    kyc = get_kyc_record(user_id)
    profile = get_financial_profile(user_id)

    return {
        "full_name": kyc["full_name"],
        "pan_number": kyc["pan_number"],
        "date_of_birth": str(kyc["date_of_birth"]),
        "aadhaar_masked": kyc["aadhaar_number_masked"],
        "bank_account_number": kyc["bank_account_number"],
        "bank_ifsc": kyc["bank_ifsc"],
        "monthly_income": str(profile["monthly_income"]),
        "employment_type": profile["employment_type"].replace("_", " ").title(),
        "requested_loan_amount": str(requested_loan_amount),
        "requested_tenure_months": str(requested_tenure_months),
        "requested_loan_type": requested_loan_type.title(),
    }

def generate_filled_form(bank_name, loan_type, fill_data, output_dir="static/generated"):
    key = (bank_name, loan_type)
    if key not in BANK_FORM_MAPPINGS:
        raise ValueError(f"No form template configured for {bank_name} - {loan_type}")

    config = BANK_FORM_MAPPINGS[key]
    template_path = config["template_path"]

    import uuid
    output_filename = f"{bank_name}_{loan_type}_{uuid.uuid4().hex[:8]}.pdf"
    output_path = f"{output_dir}/{output_filename}"

    if config["fill_type"] == "overlay":
        field_positions = []
        for field in config["field_map"]:
            value = fill_data.get(field["source"], "")
            field_positions.append({
                "page": field["page"], "x": field["x"], "y": field["y"],
                "text": str(value), "font_size": field.get("font_size", 9)
            })
        overlay_fill_pdf(template_path, output_path, field_positions)
    else:  # acroform
        field_values = {f["field_name"]: fill_data.get(f["source"], "") for f in config["field_map"]}
        fill_form_pdf(template_path, output_path, field_values)

    return output_path
```

Reuse `overlay_fill_pdf` and `fill_form_pdf` from Section 2.

---

## 5. Database Schema Addition

```sql
CREATE TABLE filled_forms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    verdict_id UUID REFERENCES verdicts(id),
    bank_name VARCHAR(50),
    loan_type VARCHAR(20),
    file_path TEXT,
    generated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 6. Backend Route

### `app/routes/form_filler.py`

**POST /api/forms/generate**
```json
Request:
{
  "verdict_id": "uuid-of-existing-verdict",
  "bank_name": "SBI",
  "loan_type": "home"
}

Response (200):
{
  "form_id": "uuid",
  "download_url": "/static/generated/SBI_home_a1b2c3d4.pdf",
  "bank_name": "SBI",
  "loan_type": "home"
}
```

Logic:
1. Fetch the verdict by ID, confirm it belongs to the authenticated user
2. Confirm `bank_name` is in the verdict's `eligible_banks` list — reject
   with 400 if the user tries to generate a form for a bank they weren't
   eligible for
3. Call `assemble_fill_data()` then `generate_filled_form()`
4. Save to `filled_forms` table, return download URL

**GET /api/forms/available-templates**
```json
Response (200):
{
  "available": [
    { "bank_name": "SBI", "loan_type": "home" },
    { "bank_name": "HDFC", "loan_type": "personal" }
  ]
}
```

Used by the frontend to know which bank+loan-type combos actually have a
working template, since not all 5 banks × 4 loan types will be mapped —
only show "Generate form" buttons for combinations that exist in
`BANK_FORM_MAPPINGS`.

---

## 7. Frontend Integration

This does **not** need its own full page — it extends the Loan Advisor
page (`frontend/loan-advisor.html`) built in SPEC_VERDICT.md.

### Changes to `frontend/loan-advisor.html` / `static/js/loan-advisor.js`

On the "Eligible banks" section (shown for approved/review verdicts):
- For each bank card, check against `GET /api/forms/available-templates`
- If a template exists for that bank + the requested loan type, show a
  "Generate pre-filled form" button instead of/alongside the existing
  "Proceed with this bank" placeholder button
- On click, POST to `/api/forms/generate` with the verdict_id, bank_name, loan_type
- On success, show a download link with a `ti-download` icon: "Download pre-filled [Bank name] [loan type] application"
- If no template exists for that bank yet, show a small muted note instead: "Pre-filled form not yet available for this bank — download the blank form from [bank]'s website"

---

## 8. What to tell Antigravity / Codex

> "Implement the Bank Form Auto-Filler module as described in
> SPEC_FORM_FILLER.md. This includes:
> 1. app/data/bank_forms/ directory — I will manually place the actual PDF
>    template files here (starting with the SBI Home Loan form already
>    uploaded earlier in this project)
> 2. app/data/bank_form_mappings.py with the BANK_FORM_MAPPINGS config,
>    starting with an SBI home loan entry — leave placeholder x/y
>    coordinates that I will calibrate manually by testing
> 3. app/models/form_filler.py with overlay_fill_pdf, fill_form_pdf,
>    assemble_fill_data, and generate_filled_form functions
> 4. The filled_forms table in database/schema.sql
> 5. app/routes/form_filler.py with POST /api/forms/generate and
>    GET /api/forms/available-templates, JWT protected
> 6. Extend frontend/loan-advisor.html and static/js/loan-advisor.js to
>    add 'Generate pre-filled form' buttons on eligible bank cards,
>    only shown when a template exists for that bank + loan type
> 7. Do not attempt to source or hardcode coordinates for banks whose PDFs
>    I haven't provided yet — leave those out of BANK_FORM_MAPPINGS until
>    I add the template file and calibrate coordinates myself"

---

## 9. Calibrating Coordinates — a practical workflow

Since this is manual, tedious work, do it efficiently:

1. Add one field to `field_map` with a rough guess coordinate
2. Call the generate endpoint (via Postman or a quick test script), open
   the output PDF
3. Check if the text landed on the right line — adjust x/y, repeat
4. Once one field is correctly calibrated, use it as a reference for
   nearby fields on the same page (e.g. if "Name" is correct at y=210,
   "Father's name" one line below is probably around y=230-240)
5. Only calibrate the fields that matter for your demo — you don't need
   every single field on a 9-page SBI form perfectly filled; prioritize
   name, PAN, DOB, income, loan amount, tenure — the fields your panel
   will actually notice

---

## 10. Testing Checklist

- [ ] POST /api/forms/generate with a valid verdict + eligible bank → returns a downloadable PDF
- [ ] POST /api/forms/generate with a bank NOT in the verdict's eligible list → returns 400
- [ ] Generated PDF opens correctly and at least the priority fields (name, PAN, loan amount) are visible and correctly positioned
- [ ] GET /api/forms/available-templates correctly reflects which bank+loan-type combos are configured
- [ ] Loan Advisor page only shows "Generate form" button for banks with an available template
- [ ] Banks without a template show the fallback "not yet available" message instead of a broken button
- [ ] filled_forms table records each generation with correct user_id and verdict_id
