/* Loan advisor UI: KYC-gated verdict requests, explainable result rendering,
   and bank form auto-fill generation. */
(function () {
  const token = () => localStorage.getItem('access_token');
  const form = document.getElementById('loanAdvisorForm');
  const amount = document.getElementById('requestedLoanAmount');
  const tenure = document.getElementById('requestedTenureMonths');
  const loanType = document.getElementById('requestedLoanType');
  const submitButton = document.getElementById('submitButton');
  const alertBox = document.getElementById('advisorAlert');

  // Cached after verdict is generated
  let currentVerdictId = null;
  let currentLoanType = null;
  let availableTemplates = [];

  function redirect(path, message) {
    window.location.href = path + '?msg=' + encodeURIComponent(message);
  }

  function showAlert(type, message) {
    alertBox.innerHTML = '';
    const alert = document.createElement('div');
    alert.className = `ls-alert ls-alert--${type}`;
    alert.textContent = message;
    alertBox.appendChild(alert);
  }

  function clearAlert() { alertBox.innerHTML = ''; }
  function formatINR(value) { return '₹' + Number(value || 0).toLocaleString('en-IN'); }

  function setBadge(element, data) {
    const color = data.color || 'info';
    element.className = `ls-badge ls-badge--${color}`;
    element.textContent = data.label || '—';
  }

  function appendList(list, values) {
    list.innerHTML = '';
    values.forEach(value => {
      const item = document.createElement('li');
      item.textContent = value;
      list.appendChild(item);
    });
  }

  // ── Form template availability ────────────────────────────────────

  async function fetchAvailableTemplates() {
    try {
      const res = await fetch('/api/forms/available-templates', {
        headers: { Authorization: 'Bearer ' + token() },
      });
      if (res.ok) {
        const data = await res.json();
        availableTemplates = data.available || [];
      }
    } catch (_) {
      availableTemplates = [];
    }
  }

  function hasTemplate(bankName, lt) {
    return availableTemplates.some(
      t => t.bank_name === bankName && t.loan_type === lt
    );
  }

  // ── Form generation ───────────────────────────────────────────────

  async function generateForm(bankName, lt, actionsContainer) {
    const btn = actionsContainer.querySelector('.ls-btn');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="ls-spinner"></span><span>Generating…</span>';
    }
    try {
      const res = await fetch('/api/forms/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer ' + token(),
        },
        body: JSON.stringify({
          verdict_id: currentVerdictId,
          bank_name: bankName,
          loan_type: lt,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.msg || 'Form generation failed.');

      // Replace button with download link
      actionsContainer.innerHTML = '';
      const link = document.createElement('a');
      link.href = data.download_url;
      link.className = 'la-bank-download';
      link.target = '_blank';
      link.download = '';
      link.innerHTML =
        '<i class="ti ti-download"></i>' +
        'Download pre-filled ' + bankName + ' ' + lt + ' application';
      actionsContainer.appendChild(link);
    } catch (err) {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="ti ti-building-bank"></i><span>Generate pre-filled form</span>';
      }
      showAlert('error', err.message);
    }
  }

  // ── Bank card rendering ───────────────────────────────────────────

  function renderBanks(banks) {
    const list = document.getElementById('banksList');
    list.innerHTML = '';
    const lt = currentLoanType || '';

    banks.forEach(bank => {
      const card = document.createElement('article');
      card.className = 'la-bank-card';

      const name = document.createElement('h3');
      name.className = 'la-bank-name';
      name.textContent = bank.bank_name;

      const limit = document.createElement('p');
      limit.className = 'la-bank-limit';
      limit.textContent = `Maximum eligible amount: ${formatINR(bank.max_eligible_amount)}`;

      const actions = document.createElement('div');
      actions.className = 'la-bank-actions';

      if (hasTemplate(bank.bank_name, lt)) {
        // Template exists — show generate button
        const btn = document.createElement('button');
        btn.className = 'ls-btn ls-btn--primary';
        btn.innerHTML = '<i class="ti ti-building-bank"></i><span>Generate pre-filled form</span>';
        btn.addEventListener('click', () => generateForm(bank.bank_name, lt, actions));
        actions.appendChild(btn);
      } else if (bank.blank_form_url && bank.blank_form_url !== '') {
        // Fallback: download blank official form
        if (bank.blank_form_url === '#') {
          const btn = document.createElement('button');
          btn.className = 'ls-btn ls-btn--secondary';
          btn.disabled = true;
          btn.innerHTML = '<i class="ti ti-download"></i><span>Download blank form (link coming soon)</span>';
          actions.appendChild(btn);
        } else {
          const link = document.createElement('a');
          link.href = bank.blank_form_url;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          link.className = 'ls-btn ls-btn--secondary';
          link.innerHTML = '<i class="ti ti-download"></i><span>Download blank application form</span>';
          actions.appendChild(link);
        }
      }

      if (actions.children.length > 0) {
        card.append(name, limit, actions);
      } else {
        card.append(name, limit);
      }
      list.appendChild(card);
    });
  }

  // ── Verdict rendering ─────────────────────────────────────────────

  function renderVerdict(data) {
    // Store verdict context for form generation
    currentVerdictId = data.verdict_id || null;
    currentLoanType = loanType.value || '';

    const styles = {
      approved: { role: 'success', icon: 'ti-check', title: 'Approved', description: 'Your application meets LoanSphere's automated business-rule criteria.' },
      review: { role: 'warning', icon: 'ti-clock', title: 'Under review', description: 'Your application needs manual review before a lending decision.' },
      rejected: { role: 'danger', icon: 'ti-x', title: 'Not eligible', description: 'Your current application does not meet LoanSphere's automated business-rule criteria.' },
    };
    const state = styles[data.verdict] || styles.review;
    const hero = document.getElementById('verdictHero');
    hero.className = `ls-card la-verdict-hero la-verdict-hero--${state.role}`;
    document.getElementById('verdictIcon').className = `ti ${state.icon} la-verdict-icon`;
    document.getElementById('verdictTitle').textContent = state.title;
    document.getElementById('verdictDescription').textContent = state.description;
    setBadge(document.getElementById('verdictBadge'), { label: state.title, color: state.role });
    document.getElementById('scoreValue').textContent = data.creditworthiness_score;
    document.getElementById('scoreValue').className = `ls-metric-card__value ls-metric-card__value--${data.score_band.color}`;
    setBadge(document.getElementById('scoreBand'), data.score_band);
    document.getElementById('riskValue').textContent = `${(Number(data.estimated_default_risk_probability) * 100).toFixed(1)}%`;
    document.getElementById('riskValue').className = `ls-metric-card__value ls-metric-card__value--${data.risk_tier.color}`;
    setBadge(document.getElementById('riskTier'), data.risk_tier);
    document.getElementById('foirValue').textContent = `${data.foir}%`;
    appendList(document.getElementById('reasoningList'), data.reasoning || []);
    const suggestions = data.suggested_adjustments || [];
    document.getElementById('suggestionsSection').style.display = suggestions.length ? 'block' : 'none';
    appendList(document.getElementById('suggestionsList'), suggestions);
    const banks = data.eligible_banks || [];
    document.getElementById('banksSection').style.display = banks.length ? 'block' : 'none';
    renderBanks(banks);
    document.getElementById('rejectedMessage').style.display = data.verdict === 'rejected' ? 'block' : 'none';
    document.getElementById('requestView').style.display = 'none';
    document.getElementById('resultView').style.display = 'block';
  }

  // ── Form submission ───────────────────────────────────────────────

  async function submit(event) {
    event.preventDefault();
    clearAlert();
    if (!amount.value || Number(amount.value) <= 0 || !tenure.value || Number(tenure.value) <= 0 || !loanType.value) {
      showAlert('error', 'Enter a valid loan amount, tenure, and loan type.');
      return;
    }
    submitButton.disabled = true;
    submitButton.innerHTML = '<span class="ls-spinner"></span><span>Generating verdict…</span>';
    try {
      const response = await fetch('/api/verdict/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token() },
        body: JSON.stringify({ requested_loan_amount: Number(amount.value), requested_tenure_months: Number(tenure.value), requested_loan_type: loanType.value }),
      });
      const data = await response.json();
      if (response.status === 403 && data.verdict === 'kyc_required') {
        redirect('/kyc', data.message);
        return;
      }
      if (response.status === 400 && data.msg && data.msg.includes('Financial profile not found')) {
        redirect('/financial-profile', data.msg);
        return;
      }
      if (!response.ok) throw new Error(data.msg || 'Unable to generate a loan verdict.');
      renderVerdict(data);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (error) {
      showAlert('error', error.message || 'Unable to generate a loan verdict.');
    } finally {
      submitButton.disabled = false;
      submitButton.innerHTML = '<i class="ti ti-scale"></i><span>Get loan verdict</span>';
    }
  }

  // ── Initialization ────────────────────────────────────────────────

  async function init() {
    if (!token()) { window.location.href = '/login'; return; }
    try {
      // Check KYC and fetch available templates in parallel
      const [kycRes] = await Promise.all([
        fetch('/api/kyc/status', { headers: { Authorization: 'Bearer ' + token() } }),
        fetchAvailableTemplates(),
      ]);
      const data = kycRes.ok ? await kycRes.json() : {};
      if (data.kyc_status !== 'verified') {
        redirect('/kyc', 'Please complete KYC verification before accessing the loan advisor.');
        return;
      }
      document.getElementById('loadingState').style.display = 'none';
      document.getElementById('advisorContent').style.display = 'block';
    } catch (_) {
      redirect('/kyc', 'Please complete KYC verification before accessing the loan advisor.');
    }
  }

  form.addEventListener('submit', submit);
  window.addEventListener('DOMContentLoaded', init);
})();
