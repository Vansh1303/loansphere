"""
Bank Form Mappings — maps each (bank_name, loan_type) pair to its
PDF template path, fill type, and field coordinate map.

Adding a new bank is a config-only change: add a new entry below,
drop the official PDF into app/data/bank_forms/, and calibrate coordinates.

source values map to keys in the fill_data dict assembled by
app.models.form_filler.assemble_fill_data().
"""

BANK_FORM_MAPPINGS = {
    ("SBI", "home"): {
        "template_path": "app/data/bank_forms/sbi_home_loan_template.pdf",
        "fill_type": "overlay",  # flat/non-fillable PDF — text overlay at fixed coords
        "field_map": [
            # ── Page 1: Personal details (FORM A) ──────────────────────────
            {"source": "full_name",      "page": 1, "x": 85,  "y": 163, "font_size": 9},
            {"source": "date_of_birth",  "page": 1, "x": 85,  "y": 182, "font_size": 9},
            {"source": "pan_number",     "page": 1, "x": 215, "y": 182, "font_size": 9},
            {"source": "mobile",         "page": 1, "x": 85,  "y": 202, "font_size": 9},
            {"source": "aadhaar_masked", "page": 1, "x": 90,  "y": 428, "font_size": 9},

            # ── Page 3: Employment & income (FORM B) ───────────────────────
            {"source": "employment_type", "page": 3, "x": 100, "y": 197, "font_size": 9},
            {"source": "monthly_income",  "page": 3, "x": 110, "y": 313, "font_size": 9},

            # ── Page 4: Loan details (FORM C) ──────────────────────────────
            {"source": "requested_loan_amount",   "page": 4, "x": 120, "y": 189, "font_size": 9},
            {"source": "requested_tenure_months", "page": 4, "x": 65,  "y": 313, "font_size": 9},
        ]
    },
    # Add more banks here as you source and calibrate their official PDFs:
    #
    # ("HDFC Bank", "personal"): {
    #     "template_path": "app/data/bank_forms/hdfc_personal_loan_template.pdf",
    #     "fill_type": "overlay",
    #     "field_map": [ ... ]
    # },
}
