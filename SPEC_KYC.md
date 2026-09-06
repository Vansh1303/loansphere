# LoanSphere — KYC Verification Module Spec

Follow SPEC_DESIGN_SYSTEM.md for all styling on every page described here.

This spec adds a KYC (Know Your Customer) verification module to LoanSphere.
KYC is a one-time profile-level verification, separate from credit scoring.
It acts as an eligibility gate: features later in the pipeline (Credit Score,
Loan Advisor, Bank Forms) check `kyc_status` before allowing the user to
proceed.

---

## 1. Why this module exists

Before a user can apply for a loan or get a credit assessment, their identity
must be verified. This is standard in every real lending platform. KYC has
NOTHING to do with creditworthiness — a person can have perfect KYC and a
poor credit score, or vice versa. Keep these completely separate in code and
in the database.

---

## 2. What gets verified

| Field | Method | Real or simulated |
|-------|--------|---------------------|
| PAN number | Setu PAN Verification API (sandbox) | **Real API call** |
| Aadhaar number | Format validation only (12-digit + checksum) | Simulated — see note below |
| Bank account + IFSC | Setu Bank Account Verification API (sandbox) | **Real API call** |
| Full name, DOB | Cross-checked against PAN API response | Real, derived from PAN response |

**Important note on Aadhaar**: Setu's direct Aadhaar verification API has been
discontinued industry-wide as of 2026 due to a UIDAI policy change affecting
all verification providers, not just Setu. In production this would route
through DigiLocker's OAuth-based document fetch instead. For this project,
Aadhaar undergoes format validation (12 digits, passes Verhoeff checksum
algorithm) rather than a live government lookup. This limitation should be
stated explicitly in the project report — it is a real, documented industry
constraint, not a shortcut.

---

## 3. Setu Sandbox Setup (do this first, manually, before coding)

1. Go to https://bridge.setu.co/signup and create a free sandbox account
2. Once logged in, go to the Setu Bridge dashboard → create a new scheme for
   "PAN Verification" and one for "Bank Account Verification"
3. Copy the `schemeId`, `clientId`, and `clientSecret` for each
4. Add to `.env`:
   ```
   SETU_CLIENT_ID=your_client_id
   SETU_CLIENT_SECRET=your_client_secret
   SETU_PAN_SCHEME_ID=your_pan_scheme_id
   SETU_BANK_SCHEME_ID=your_bank_scheme_id
   SETU_BASE_URL=https://dg-sandbox.setu.co
   ```

**Sandbox test values to use during development:**
- Valid PAN: `ABCDE1234A` → returns success
- Invalid PAN: `ABCDE1234B` → returns "found but invalid"
- Any other PAN format → returns 404 "PAN not found"
- Bank account sandbox values are provided in the Setu dashboard scheme config

---

## 4. Database Schema Additions

Add to `database/schema.sql`:

```sql
CREATE TABLE kyc_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    pan_number VARCHAR(10),
    pan_verified BOOLEAN DEFAULT FALSE,
    pan_verified_name VARCHAR(255),
    aadhaar_number_masked VARCHAR(20),
    aadhaar_format_valid BOOLEAN DEFAULT FALSE,
    bank_account_number VARCHAR(30),
    bank_ifsc VARCHAR(11),
    bank_verified BOOLEAN DEFAULT FALSE,
    bank_verified_name VARCHAR(255),
    full_name VARCHAR(255),
    date_of_birth DATE,
    kyc_status VARCHAR(20) DEFAULT 'not_started',
        -- values: not_started | pending | verified | rejected
    rejection_reason TEXT,
    submitted_at TIMESTAMP,
    verified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

`kyc_status` is the single field every other module checks. Never store
Aadhaar in full — only the masked version (e.g. `XXXX XXXX 9019`).

---

## 5. Backend — Files to Create

### `app/models/kyc.py`

Responsibilities:
- `verify_pan(pan_number)` — calls Setu PAN API, returns `{ valid, name, aadhaar_seeding_status }`
- `validate_aadhaar_format(aadhaar_number)` — local Verhoeff checksum validation, no external call, returns `{ valid, masked }`
- `verify_bank_account(account_number, ifsc)` — calls Setu Bank Account Verification API, returns `{ valid, account_holder_name }`
- `compute_kyc_status(pan_verified, aadhaar_valid, bank_verified, name_match)` — business logic:
  ```
  if pan_verified AND aadhaar_valid AND bank_verified AND name_match:
      return "verified"
  elif any check explicitly failed (not just missing):
      return "rejected"
  else:
      return "pending"
  ```
- `mask_aadhaar(aadhaar_number)` — returns only last 4 digits visible: `XXXX XXXX 9019`

### `app/routes/kyc.py`

Endpoints:

**POST /api/kyc/submit**
```json
Request:
{
  "pan_number": "ABCDE1234A",
  "aadhaar_number": "999999990019",
  "bank_account_number": "1234567890",
  "bank_ifsc": "SBIN0001234",
  "full_name": "Vansh Jha",
  "date_of_birth": "2003-05-14"
}

Response (200):
{
  "kyc_status": "verified",
  "pan_verified": true,
  "pan_verified_name": "VANSH JHA",
  "aadhaar_format_valid": true,
  "aadhaar_masked": "XXXX XXXX 0019",
  "bank_verified": true,
  "name_match": true,
  "message": "KYC verification complete"
}
```

**GET /api/kyc/status**
```json
Response (200):
{
  "kyc_status": "verified",
  "submitted_at": "2026-05-01T10:00:00Z",
  "verified_at": "2026-05-01T10:00:05Z",
  "details": { "pan_verified": true, "aadhaar_format_valid": true, "bank_verified": true }
}
```

Both routes require JWT authentication. `user_id` comes from the JWT identity,
never from the request body.

---

## 6. Setu API Call Reference

### PAN Verification

**Verified against live Setu docs (docs.setu.co/data/pan/quickstart).**
No token exchange step — credentials go directly as headers on every call.

```python
import requests

def verify_pan(pan_number):
    headers = {
        "x-client-id": SETU_CLIENT_ID,
        "x-client-secret": SETU_CLIENT_SECRET,
        "x-product-instance-id": SETU_PAN_SCHEME_ID,
        "Content-Type": "application/json"
    }
    response = requests.post(
        f"{SETU_BASE_URL}/api/verify/pan",
        headers=headers,
        json={
            "pan": pan_number,
            "consent": "Y",
            "reason": "Verifying identity for loan eligibility on LoanSphere"
            # reason MUST be 20+ characters or Setu returns a 400 error
        }
    )
    data = response.json()

    if response.status_code == 200 and data.get("verification") == "success":
        return {
            "valid": True,
            "name": data["data"].get("full_name", ""),
            "aadhaar_seeding_status": data["data"].get("aadhaar_seeding_status", "unknown")
        }
    elif data.get("message") == "PAN not found.":
        return {"valid": False, "error": "PAN not found"}
    else:
        return {"valid": False, "error": data.get("message", "Verification failed")}
```

Sandbox base URL: `https://dg-sandbox.setu.co` (already confirmed correct
in .env). Production base URL would be `https://dg.setu.co` — not used for
this project.

### Aadhaar Format Validation (Verhoeff Algorithm, no external call)

```python
def validate_aadhaar_format(aadhaar_number):
    aadhaar_number = aadhaar_number.replace(" ", "")
    if not aadhaar_number.isdigit() or len(aadhaar_number) != 12:
        return {"valid": False, "masked": None}

    # Verhoeff checksum validation
    d = [
        [0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],
        [3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],
        [6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],
        [9,8,7,6,5,4,3,2,1,0]
    ]
    p = [
        [0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],
        [8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],
        [2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]
    ]
    c = 0
    digits = [int(x) for x in reversed(aadhaar_number)]
    for i, digit in enumerate(digits):
        c = d[c][p[i % 8][digit]]

    is_valid = (c == 0)
    masked = f"XXXX XXXX {aadhaar_number[-4:]}" if is_valid else None
    return {"valid": is_valid, "masked": masked}
```

**Test Aadhaar numbers that pass Verhoeff validation** (use these for demo):
`999999990019`, `234123412346`

### Bank Account Verification

```python
def verify_bank_account(account_number, ifsc):
    token = get_setu_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "x-client-id": SETU_CLIENT_ID,
        "x-product-instance-id": SETU_BANK_SCHEME_ID
    }
    response = requests.post(
        f"{SETU_BASE_URL}/api/verify/account",
        headers=headers,
        json={"accountNumber": account_number, "ifsc": ifsc}
    )
    if response.status_code == 200:
        data = response.json()
        return {"valid": True, "account_holder_name": data.get("name", "")}
    return {"valid": False, "error": "Account verification failed"}
```

---

## 7. Frontend — Pages to Build

### `frontend/kyc.html`

Follow the sidebar shell from SPEC_DESIGN_SYSTEM.md. Page title: "KYC
verification".

**Layout — single column, max-width 640px, sections in this order:**

1. **Status banner at top** (only shows if kyc_status is not "not_started"):
   - Status badge (Verified / Pending / Rejected) per Section 3.3 of design spec
   - If rejected, show `rejection_reason` in plain text below the badge

2. **Section: Personal details**
   - Full name (text input)
   - Date of birth (date input)

3. **Section: PAN verification**
   - PAN number input, uppercase auto-transform, format hint below: "e.g. ABCDE1234A"
   - Helper text: "We'll verify this against NSDL records"

4. **Section: Aadhaar verification**
   - Aadhaar number input, 12-digit, auto-formats with spaces as user types (XXXX XXXX XXXX)
   - Helper text: "Used for identity confirmation. We never store your full Aadhaar number."

5. **Section: Bank account details**
   - Account number input
   - IFSC code input, uppercase auto-transform

6. Submit button: "Verify KYC" (primary blue button, per Section 3.5)

7. **After submission** — show a results panel:
   - Three checkmark/cross rows: PAN verified ✓/✗, Aadhaar format valid ✓/✗, Bank account verified ✓/✗
   - Use `ti-check` (green) or `ti-x` (red) icons per row
   - Overall status badge at the top updates accordingly

### `static/js/kyc.js`

- On page load, call `GET /api/kyc/status` to check if KYC already exists — if verified, show the status view instead of the form
- On submit, POST to `/api/kyc/submit` with JWT Bearer token
- Show a loading spinner during the ~2-3 second API verification calls
- Auto-format Aadhaar input with spaces every 4 digits as user types
- Auto-uppercase PAN and IFSC inputs
- Client-side validation before submit: PAN regex `^[A-Z]{5}[0-9]{4}[A-Z]$`, Aadhaar 12 digits, IFSC regex `^[A-Z]{4}0[A-Z0-9]{6}$`

---

## 8. Integration Points

### Dashboard update
The existing dashboard's "KYC status" metric card should now show real data from `GET /api/kyc/status` instead of a hardcoded "Pending" value.

### Gate for future modules
Every future module (Credit Score, Loan Advisor, Bank Forms) must check
`kyc_status` before allowing access. Add this check pattern:

```python
def require_kyc_verified(user_id):
    kyc = get_kyc_record(user_id)
    if not kyc or kyc['kyc_status'] != 'verified':
        return False
    return True
```

On the frontend, if a user without verified KYC tries to access Credit
Score or Loan Advisor pages, redirect them to `/kyc` with a message:
"Please complete KYC verification before proceeding."

---

## 9. What to tell Antigravity (paste this as your prompt)

> "Implement the KYC verification module for LoanSphere exactly as described
> in SPEC_KYC.md. This includes:
> 1. The kyc_records table in database/schema.sql
> 2. app/models/kyc.py with verify_pan, validate_aadhaar_format (Verhoeff
>    algorithm), verify_bank_account, and compute_kyc_status functions
> 3. app/routes/kyc.py with POST /api/kyc/submit and GET /api/kyc/status,
>    both JWT protected
> 4. frontend/kyc.html and static/js/kyc.js following SPEC_DESIGN_SYSTEM.md
>    for all styling
> 5. Update the dashboard's KYC status metric card to pull real data from
>    GET /api/kyc/status
> 6. Use environment variables SETU_CLIENT_ID, SETU_CLIENT_SECRET,
>    SETU_PAN_SCHEME_ID, SETU_BANK_SCHEME_ID, SETU_BASE_URL for Setu API
>    calls — these will be provided in .env
> 7. For Aadhaar, do NOT call any external API — only run local format and
>    checksum validation as specified"

---

## 10. Testing Checklist

- [ ] Submit KYC with valid PAN (ABCDE1234A) → pan_verified = true
- [ ] Submit KYC with invalid PAN (ABCDE1234B) → pan_verified = false, status = rejected
- [ ] Submit KYC with valid Aadhaar (999999990019) → aadhaar_format_valid = true
- [ ] Submit KYC with invalid Aadhaar (123456789012) → aadhaar_format_valid = false
- [ ] GET /api/kyc/status before any submission → kyc_status = "not_started"
- [ ] GET /api/kyc/status after successful submission → kyc_status = "verified"
- [ ] Dashboard KYC card reflects real status, not hardcoded value
- [ ] Aadhaar number is never stored or returned in full — only masked version
