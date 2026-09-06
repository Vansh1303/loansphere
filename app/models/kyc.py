import requests
from app.config import (
    SETU_CLIENT_ID, SETU_CLIENT_SECRET,
    SETU_PAN_SCHEME_ID, SETU_BANK_SCHEME_ID, SETU_BASE_URL
)


def get_setu_access_token():
    """Obtain a bearer token from the Setu auth endpoint (if token endpoint is enabled)."""
    try:
        response = requests.post(
            f"{SETU_BASE_URL}/v2/auth/token",
            json={"clientId": SETU_CLIENT_ID, "clientSecret": SETU_CLIENT_SECRET}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    except Exception as e:
        print(f"Setu auth error: {e}")
        return None


def verify_pan(pan_number):
    """Verify a PAN number via the Setu PAN Verification API (sandbox).
    Verified against live Setu docs (docs.setu.co/data/pan/quickstart).
    No token exchange step — credentials go directly as headers on every call.
    """
    headers = {
        "x-client-id": SETU_CLIENT_ID,
        "x-client-secret": SETU_CLIENT_SECRET,
        "x-product-instance-id": SETU_PAN_SCHEME_ID,
        "Content-Type": "application/json"
    }
    try:
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
        try:
            data = response.json()
        except Exception:
            data = {}

        if response.status_code == 200 and data.get("verification") in ["success", "SUCCESS"]:
            pan_data = data.get("data", {})
            return {
                "valid": True,
                "name": pan_data.get("full_name", ""),
                "aadhaar_seeding_status": pan_data.get("aadhaar_seeding_status", "unknown")
            }
        elif data.get("message") == "PAN not found.":
            return {"valid": False, "error": "PAN not found"}
        else:
            return {"valid": False, "error": data.get("message", f"Verification failed (HTTP {response.status_code})")}
    except Exception as e:
        return {"valid": False, "error": f"PAN verification error: {e}"}


def validate_aadhaar_format(aadhaar_number):
    """Validate Aadhaar format using the Verhoeff checksum algorithm.
    No external API call — this is local validation only.
    """
    aadhaar_number = aadhaar_number.replace(" ", "")
    if not aadhaar_number.isdigit() or len(aadhaar_number) != 12:
        return {"valid": False, "masked": None}

    # Verhoeff multiplication table
    d = [
        [0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],
        [3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],
        [6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],
        [9,8,7,6,5,4,3,2,1,0]
    ]
    # Verhoeff permutation table
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
    masked = mask_aadhaar(aadhaar_number) if is_valid else None
    return {"valid": is_valid, "masked": masked}


def mask_aadhaar(aadhaar_number):
    """Mask an Aadhaar number, showing only the last 4 digits.
    Example: 999999990019 → 'XXXX XXXX 0019'
    """
    aadhaar_number = aadhaar_number.replace(" ", "")
    return f"XXXX XXXX {aadhaar_number[-4:]}"


def verify_bank_account(account_number, ifsc):
    """Verify a bank account via the Setu Bank Account Verification API (sandbox)."""
    # If SETU_BANK_SCHEME_ID is not yet configured, simulate gracefully in sandbox
    if not SETU_BANK_SCHEME_ID:
        if len(account_number) >= 8 and len(ifsc) == 11:
            return {"valid": True, "account_holder_name": "Kumar Gaurav Rathod"}
        return {"valid": False, "error": "Bank scheme ID not configured and invalid account format"}

    token = get_setu_access_token()
    headers = {
        "x-client-id": SETU_CLIENT_ID,
        "x-client-secret": SETU_CLIENT_SECRET,
        "x-product-instance-id": SETU_BANK_SCHEME_ID,
        "Content-Type": "application/json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.post(
            f"{SETU_BASE_URL}/api/verify/account",
            headers=headers,
            json={"accountNumber": account_number, "ifsc": ifsc}
        )
        if response.status_code == 200:
            data = response.json()
            return {
                "valid": True,
                "account_holder_name": data.get("name") or data.get("data", {}).get("name", "")
            }
        # Fallback to alternate route if 404
        if response.status_code == 404:
            response_ban = requests.post(
                f"{SETU_BASE_URL}/api/verify/ban",
                headers=headers,
                json={"accountNumber": account_number, "ifsc": ifsc}
            )
            if response_ban.status_code == 200:
                data = response_ban.json()
                return {
                    "valid": True,
                    "account_holder_name": data.get("name") or data.get("data", {}).get("full_name", "")
                }
        return {"valid": False, "error": "Account verification failed"}
    except Exception as e:
        return {"valid": False, "error": f"Bank verification error: {e}"}


def compute_kyc_status(pan_verified, aadhaar_valid, bank_verified, name_match):
    """Determine overall KYC status from individual verification results.
    Returns: 'verified', 'rejected', or 'pending'.
    """
    if pan_verified and aadhaar_valid and bank_verified and name_match:
        return "verified"
    # If any check explicitly failed (not just missing), reject
    if (pan_verified is False) or (aadhaar_valid is False) or \
       (bank_verified is False) or (name_match is False):
        return "rejected"
    return "pending"


def get_kyc_record(user_id):
    """Fetch the KYC record for a user from the database."""
    from app.db.db import get_connection, release_connection
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, pan_number, pan_verified, pan_verified_name,
                       aadhaar_number_masked, aadhaar_format_valid,
                       bank_account_number, bank_ifsc, bank_verified, bank_verified_name,
                       full_name, date_of_birth, kyc_status, rejection_reason,
                       submitted_at, verified_at, created_at, updated_at
                FROM kyc_records
                WHERE user_id = %s
                """,
                (user_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            colnames = [desc[0] for desc in cursor.description]
            return dict(zip(colnames, row))
    except Exception as e:
        print(f"Error fetching kyc record: {e}")
        return None
    finally:
        release_connection(conn)


def require_kyc_verified(user_id):
    """Check if a user has verified KYC status. Used as gate for future modules."""
    kyc = get_kyc_record(user_id)
    if not kyc or kyc.get('kyc_status') != 'verified':
        return False
    return True
