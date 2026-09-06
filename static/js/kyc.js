// KYC verification page logic
(function () {
  const TOKEN_KEY = 'access_token';
  const API_BASE = '/api/kyc';

  // DOM elements
  const form = document.getElementById('kycForm');
  const submitBtn = document.getElementById('submitBtn');
  const btnIcon = document.getElementById('btnIcon');
  const btnLabel = document.getElementById('btnLabel');
  const formStatus = document.getElementById('formStatus');
  const statusBanner = document.getElementById('statusBanner');
  const statusBadge = document.getElementById('statusBadge');
  const rejectionText = document.getElementById('rejectionText');
  const resultsPanel = document.getElementById('resultsPanel');
  const resultsList = document.getElementById('resultsList');

  // Input elements
  const panInput = document.getElementById('panNumber');
  const aadhaarInput = document.getElementById('aadhaarNumber');
  const ifscInput = document.getElementById('bankIfsc');

  // --- Auto-formatting ---

  // PAN: force uppercase
  panInput.addEventListener('input', () => {
    panInput.value = panInput.value.toUpperCase();
  });

  // IFSC: force uppercase
  ifscInput.addEventListener('input', () => {
    ifscInput.value = ifscInput.value.toUpperCase();
  });

  // Aadhaar: auto-space every 4 digits
  aadhaarInput.addEventListener('input', () => {
    let raw = aadhaarInput.value.replace(/\D/g, '').slice(0, 12);
    let formatted = '';
    for (let i = 0; i < raw.length; i++) {
      if (i > 0 && i % 4 === 0) formatted += ' ';
      formatted += raw[i];
    }
    aadhaarInput.value = formatted;
  });

  // --- Validation ---

  const PAN_REGEX = /^[A-Z]{5}[0-9]{4}[A-Z]$/;
  const IFSC_REGEX = /^[A-Z]{4}0[A-Z0-9]{6}$/;

  function validateForm() {
    const errors = [];
    const fullName = document.getElementById('fullName').value.trim();
    const dob = document.getElementById('dob').value;
    const pan = panInput.value.trim().toUpperCase();
    const aadhaar = aadhaarInput.value.replace(/\s/g, '');
    const bankAccount = document.getElementById('bankAccount').value.trim();
    const ifsc = ifscInput.value.trim().toUpperCase();

    if (!fullName) errors.push('Full name is required');
    if (!dob) errors.push('Date of birth is required');
    if (!pan) errors.push('PAN number is required');
    else if (!PAN_REGEX.test(pan)) errors.push('PAN format invalid (e.g. ABCDE1234A)');
    if (!aadhaar) errors.push('Aadhaar number is required');
    else if (!/^\d{12}$/.test(aadhaar)) errors.push('Aadhaar must be exactly 12 digits');
    if (!bankAccount) errors.push('Bank account number is required');
    if (!ifsc) errors.push('IFSC code is required');
    else if (!IFSC_REGEX.test(ifsc)) errors.push('IFSC format invalid (e.g. SBIN0001234)');

    return errors;
  }

  // --- UI helpers ---

  function setLoading(on) {
    submitBtn.disabled = on;
    if (on) {
      btnIcon.className = '';
      btnIcon.innerHTML = '<span class="ls-spinner"></span>';
      btnLabel.textContent = 'Verifying\u2026';
    } else {
      btnIcon.className = 'ti ti-shield-check';
      btnIcon.innerHTML = '';
      btnLabel.textContent = 'Verify KYC';
    }
  }

  function showAlert(type, msg) {
    formStatus.innerHTML = '<div class="ls-alert ls-alert--' + type + '" style="margin-top:14px;">' + msg + '</div>';
  }

  function showStatusBanner(status, rejection) {
    statusBanner.style.display = 'block';
    statusBadge.className = 'ls-badge';
    rejectionText.style.display = 'none';

    if (status === 'verified') {
      statusBadge.classList.add('ls-badge--success');
      statusBadge.textContent = 'Verified';
    } else if (status === 'rejected') {
      statusBadge.classList.add('ls-badge--danger');
      statusBadge.textContent = 'Rejected';
      if (rejection) {
        rejectionText.textContent = rejection;
        rejectionText.style.display = 'block';
      }
    } else if (status === 'pending') {
      statusBadge.classList.add('ls-badge--warning');
      statusBadge.textContent = 'Pending';
    } else {
      statusBanner.style.display = 'none';
    }
  }

  function renderResults(data) {
    resultsPanel.style.display = 'block';
    const rows = [
      { label: 'PAN verified', ok: data.pan_verified },
      { label: 'Aadhaar format valid', ok: data.aadhaar_format_valid },
      { label: 'Bank account verified', ok: data.bank_verified },
    ];
    resultsList.innerHTML = rows.map(function (r) {
      return '<div class="kyc-result-row">' +
        '<i class="ti ' + (r.ok ? 'ti-check' : 'ti-x') + '"></i>' +
        '<span>' + r.label + '</span>' +
        '</div>';
    }).join('');

    // If there was a name mismatch, show it
    if (data.name_match === false && data.pan_verified) {
      resultsList.innerHTML +=
        '<div class="kyc-result-row">' +
        '<i class="ti ti-x"></i>' +
        '<span>Name match (PAN name differs from submitted name)</span>' +
        '</div>';
    }
  }

  // --- API calls ---

  function getAuthHeaders() {
    const token = localStorage.getItem(TOKEN_KEY);
    return {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + token
    };
  }

  async function loadKycStatus() {
    try {
      const res = await fetch(API_BASE + '/status', {
        headers: getAuthHeaders()
      });
      if (!res.ok) return;
      const data = await res.json();

      if (data.kyc_status && data.kyc_status !== 'not_started') {
        showStatusBanner(data.kyc_status, data.rejection_reason);

        // If verified, show results and disable form
        if (data.kyc_status === 'verified') {
          renderResults({
            pan_verified: data.details.pan_verified,
            aadhaar_format_valid: data.details.aadhaar_format_valid,
            bank_verified: data.details.bank_verified,
            name_match: true  // was verified, so name matched
          });
          // Disable form inputs
          form.querySelectorAll('input').forEach(function (i) { i.disabled = true; });
          submitBtn.style.display = 'none';
        }
      }
    } catch (e) {
      console.error('Failed to load KYC status:', e);
    }
  }

  // --- Form submission ---

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    formStatus.innerHTML = '';
    resultsPanel.style.display = 'none';

    const errors = validateForm();
    if (errors.length > 0) {
      showAlert('error', errors.map(function (err) { return '\u26a0\ufe0f ' + err; }).join('<br>'));
      return;
    }

    setLoading(true);

    const payload = {
      pan_number: panInput.value.trim().toUpperCase(),
      aadhaar_number: aadhaarInput.value.replace(/\s/g, ''),
      bank_account_number: document.getElementById('bankAccount').value.trim(),
      bank_ifsc: ifscInput.value.trim().toUpperCase(),
      full_name: document.getElementById('fullName').value.trim(),
      date_of_birth: document.getElementById('dob').value
    };

    try {
      const res = await fetch(API_BASE + '/submit', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (!res.ok) {
        showAlert('error', '\u274c ' + (data.msg || 'KYC submission failed'));
        return;
      }

      // Update status banner
      showStatusBanner(data.kyc_status, data.rejection_reason);

      // Render result rows
      renderResults(data);

      if (data.kyc_status === 'verified') {
        showAlert('success', '\u2705 KYC verification complete \u2014 all checks passed.');
        form.querySelectorAll('input').forEach(function (i) { i.disabled = true; });
        submitBtn.style.display = 'none';
      } else if (data.kyc_status === 'rejected') {
        showAlert('error', '\u274c KYC verification failed. ' + (data.rejection_reason || ''));
      } else {
        showAlert('warning', '\u23f3 KYC verification is pending. Some checks could not be completed.');
      }
    } catch (err) {
      showAlert('error', '\u274c Unable to connect to the server. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  });

  // --- Initialize ---
  window.addEventListener('DOMContentLoaded', () => {
    // Check for incoming redirect message in query string
    const urlParams = new URLSearchParams(window.location.search);
    const msg = urlParams.get('msg');
    if (msg) {
      showAlert('warning', '\u26a0\ufe0f ' + msg);
    }
    loadKycStatus();
  });
})();
