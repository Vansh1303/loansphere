/**
 * LoanSphere Creditworthiness Score Frontend Logic
 * Gated behind financial profile existing (GET /api/financial-profile returning non-null), not KYC.
 * Builds and controls an inline SVG semi-circular gauge without third-party chart libraries.
 */

(function () {
  const TOKEN_KEY = 'access_token';
  const API_PROFILE = '/api/financial-profile';
  const API_SCORE_LATEST = '/api/credit-score/latest';
  const API_SCORE_CALCULATE = '/api/credit-score/calculate';

  // DOM Elements
  const loadingState = document.getElementById('loadingState');
  const gateContainer = document.getElementById('gateContainer');
  const mainContent = document.getElementById('mainContent');
  const csAlert = document.getElementById('csAlert');

  const calcFormContainer = document.getElementById('calcFormContainer');
  const creditScoreForm = document.getElementById('creditScoreForm');
  const requestedLoanAmount = document.getElementById('requestedLoanAmount');
  const requestedTenureMonths = document.getElementById('requestedTenureMonths');
  const requestedLoanType = document.getElementById('requestedLoanType');
  const calcSubmitBtn = document.getElementById('calcSubmitBtn');
  const btnIcon = document.getElementById('btnIcon');
  const btnLabel = document.getElementById('btnLabel');
  const cancelRecalcBtn = document.getElementById('cancelRecalcBtn');

  const scoreDisplayContainer = document.getElementById('scoreDisplayContainer');
  const displayScoreNumber = document.getElementById('displayScoreNumber');
  const displayBandBadge = document.getElementById('displayBandBadge');
  const displayLoanContext = document.getElementById('displayLoanContext');
  const contextLoanType = document.getElementById('contextLoanType');
  const contextLoanAmount = document.getElementById('contextLoanAmount');
  const contextLoanTenure = document.getElementById('contextLoanTenure');
  const recalcBtn = document.getElementById('recalcBtn');

  // Gauge Elements
  const gaugeFillArc = document.getElementById('gaugeFillArc');
  const gaugeCenterScore = document.getElementById('gaugeCenterScore');
  const gaugeCenterBand = document.getElementById('gaugeCenterBand');

  // Explanation and Table
  const explanationList = document.getElementById('explanationList');
  const componentTableBody = document.getElementById('componentTableBody');
  const totalWeightedScore = document.getElementById('totalWeightedScore');

  let currentScoreData = null;

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function showAlert(type, message) {
    csAlert.innerHTML = `<div class="ls-alert ls-alert--${type}">${message}</div>`;
  }

  function clearAlert() {
    csAlert.innerHTML = '';
  }

  function setLoading(btn, isLoading, defaultText = 'Calculate score') {
    if (!btn) return;
    btn.disabled = isLoading;
    if (isLoading) {
      btnIcon.innerHTML = '<span class="ls-spinner"></span>';
      btnLabel.textContent = 'Calculating\u2026';
    } else {
      btnIcon.innerHTML = '<i class="ti ti-sparkles"></i>';
      btnLabel.textContent = defaultText;
    }
  }

  const BAND_COLORS = {
    success: '#059669',
    warning: '#d97706',
    danger:  '#dc2626',
  };

  const COMPONENT_LABELS = [
    { key: 'foir', name: 'Fixed Obligation to Income Ratio (FOIR)', formatRaw: v => `${v}%` },
    { key: 'payment_history', name: 'Payment History', formatRaw: v => `${v} / 100` },
    { key: 'credit_utilization', name: 'Credit Utilization', formatRaw: v => `${v}%` },
    { key: 'employment_stability', name: 'Employment Stability', formatRaw: v => `${v} / 100` },
    { key: 'debt_burden', name: 'Debt Burden', formatRaw: v => `${v} / 100` },
    { key: 'inquiry_pressure', name: 'Inquiry Pressure', formatRaw: v => `${v} / 100` },
  ];

  function formatCurrencyINR(num) {
    if (isNaN(num) || num === null || num === undefined) return '0';
    return Number(num).toLocaleString('en-IN');
  }

  function formatLoanTypeName(type) {
    const map = {
      home: 'Home Loan',
      personal: 'Personal Loan',
      education: 'Education Loan',
      car: 'Car Loan',
    };
    return map[type] || type || 'Loan';
  }

  /**
   * Render the score, inline SVG gauge, explanation bullets, and breakdown table
   */
  function renderScore(data) {
    currentScoreData = data;
    const score = Number(data.score);
    const band = data.band || { label: 'Good', color: 'success' };
    const colorKey = band.color || 'success';
    const hexColor = BAND_COLORS[colorKey] || BAND_COLORS.success;

    // 1. Score Number & Badge
    displayScoreNumber.textContent = score;
    displayScoreNumber.className = `cs-score-number cs-score-number--${colorKey}`;

    displayBandBadge.textContent = band.label;
    displayBandBadge.className = `ls-badge ls-badge--${colorKey}`;

    // Loan context details
    if (data.requested_loan_amount && data.requested_loan_type) {
      contextLoanType.textContent = formatLoanTypeName(data.requested_loan_type);
      contextLoanAmount.textContent = '₹' + formatCurrencyINR(data.requested_loan_amount);
      contextLoanTenure.textContent = `${data.requested_tenure_months} months`;
      displayLoanContext.style.display = 'block';
    } else {
      displayLoanContext.style.display = 'none';
    }

    // 2. Inline SVG Semi-Circular Gauge
    // Circumference of semicircle (r=100) = pi * 100 ≈ 314.159
    const totalCircumference = 314.159;
    const clampedScore = Math.max(0, Math.min(900, score));
    const ratio = clampedScore / 900.0;
    const offset = totalCircumference * (1.0 - ratio);

    gaugeFillArc.style.stroke = hexColor;
    gaugeFillArc.style.strokeDasharray = `${totalCircumference}`;
    gaugeFillArc.style.strokeDashoffset = `${offset}`;

    gaugeCenterScore.textContent = score;
    gaugeCenterScore.style.fill = hexColor;
    gaugeCenterBand.textContent = band.label;

    // 3. Why this score explanations
    explanationList.innerHTML = '';
    const explanations = data.explanation || [];
    if (explanations.length === 0) {
      const li = document.createElement('li');
      li.className = 'cs-explanation-item';
      li.innerHTML = '<span class="cs-explanation-bullet"></span><span>Score evaluated based on current financial metrics.</span>';
      explanationList.appendChild(li);
    } else {
      explanations.forEach(text => {
        const li = document.createElement('li');
        li.className = 'cs-explanation-item';
        li.innerHTML = `<span class="cs-explanation-bullet" style="background:${hexColor};"></span><span>${escapeHtml(text)}</span>`;
        explanationList.appendChild(li);
      });
    }

    // 4. Component Breakdown Table
    componentTableBody.innerHTML = '';
    const breakdown = data.component_breakdown || {};
    let sumWeightedScore = 0;

    COMPONENT_LABELS.forEach(item => {
      const comp = breakdown[item.key] || { raw_value: 0, component_score: 0, weight: 0 };
      const rawFormatted = item.formatRaw(comp.raw_value !== undefined ? comp.raw_value : '—');
      const scoreVal = Number(comp.component_score || 0).toFixed(1);
      const weightVal = comp.weight || 0;

      sumWeightedScore += (comp.component_score || 0) * (weightVal / 100.0);

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-weight: 500;">${item.name}</td>
        <td class="cs-col-num" style="color: var(--text-secondary);">${rawFormatted}</td>
        <td class="cs-col-num"><strong>${scoreVal}</strong> <span style="font-size:11px; color:var(--text-muted);">/ 100</span></td>
        <td class="cs-col-num"><span class="cs-table-weight-badge">${weightVal}%</span></td>
      `;
      componentTableBody.appendChild(tr);
    });

    totalWeightedScore.innerHTML = `<strong>${sumWeightedScore.toFixed(1)}</strong> <span style="font-size:11px; color:var(--text-muted);">/ 100</span>`;
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  /**
   * Handle Calculation Form Submit
   */
  async function handleCalculateSubmit(e) {
    e.preventDefault();
    clearAlert();

    const amountVal = requestedLoanAmount.value.trim();
    const tenureVal = requestedTenureMonths.value.trim();
    const typeVal = requestedLoanType.value;

    if (!amountVal || Number(amountVal) <= 0) {
      showAlert('error', 'Please enter a valid requested loan amount.');
      requestedLoanAmount.focus();
      return;
    }
    if (!tenureVal || Number(tenureVal) <= 0) {
      showAlert('error', 'Please enter a valid loan tenure in months.');
      requestedTenureMonths.focus();
      return;
    }
    if (!typeVal) {
      showAlert('error', 'Please select a requested loan type.');
      requestedLoanType.focus();
      return;
    }

    const payload = {
      requested_loan_amount: parseFloat(amountVal),
      requested_tenure_months: parseInt(tenureVal, 10),
      requested_loan_type: typeVal,
    };

    setLoading(calcSubmitBtn, true);

    try {
      const res = await fetch(API_SCORE_CALCULATE, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + getToken(),
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok) {
        if (res.status === 400 && data.msg && data.msg.includes('Financial profile not found')) {
          gateContainer.style.display = 'block';
          mainContent.style.display = 'none';
          return;
        }
        showAlert('error', data.msg || 'Failed to calculate credit score. Please try again.');
        return;
      }

      // Merge requested values for display
      data.requested_loan_amount = payload.requested_loan_amount;
      data.requested_tenure_months = payload.requested_tenure_months;
      data.requested_loan_type = payload.requested_loan_type;

      renderScore(data);
      calcFormContainer.style.display = 'none';
      scoreDisplayContainer.style.display = 'block';
      cancelRecalcBtn.style.display = 'none';
      window.scrollTo({ top: 0, behavior: 'smooth' });

    } catch (err) {
      console.error('Calculation error:', err);
      showAlert('error', 'Network error while calculating score. Please try again.');
    } finally {
      setLoading(calcSubmitBtn, false);
    }
  }

  /**
   * Main Initialization & Gating Logic
   */
  async function init() {
    const token = getToken();
    if (!token) {
      window.location.href = '/login';
      return;
    }

    try {
      // 1. Gate check: financial profile must exist (GET /api/financial-profile returning non-null)
      // Note: Not gated by KYC!
      let profileOk = false;
      try {
        const profileRes = await fetch(API_PROFILE, {
          headers: { 'Authorization': 'Bearer ' + token }
        });
        if (profileRes.ok) {
          const profileData = await profileRes.json();
          if (profileData && profileData.profile !== null) {
            profileOk = true;
          }
        }
      } catch (e) {
        console.error('Error verifying financial profile gate:', e);
      }

      loadingState.style.display = 'none';

      if (!profileOk) {
        gateContainer.style.display = 'block';
        mainContent.style.display = 'none';
        return;
      }

      // Financial profile verified: reveal main section
      gateContainer.style.display = 'none';
      mainContent.style.display = 'block';

      // 2. Check for latest computed score
      const scoreRes = await fetch(API_SCORE_LATEST, {
        headers: { 'Authorization': 'Bearer ' + token }
      });

      if (scoreRes.ok) {
        const scoreData = await scoreRes.json();
        if (scoreData && scoreData.score !== null) {
          // Score exists: prefill form and show score display directly
          if (scoreData.requested_loan_amount) {
            requestedLoanAmount.value = scoreData.requested_loan_amount;
          }
          if (scoreData.requested_tenure_months) {
            requestedTenureMonths.value = scoreData.requested_tenure_months;
          }
          if (scoreData.requested_loan_type) {
            requestedLoanType.value = scoreData.requested_loan_type;
          }

          renderScore(scoreData);
          scoreDisplayContainer.style.display = 'block';
          calcFormContainer.style.display = 'none';
          return;
        }
      }

      // No previous score: show the calculation form
      calcFormContainer.style.display = 'block';
      scoreDisplayContainer.style.display = 'none';

    } catch (err) {
      console.error('Initialization error:', err);
      loadingState.style.display = 'none';
      showAlert('error', 'Failed to load credit score module. Please refresh the page.');
      mainContent.style.display = 'block';
    }
  }

  // Setup Event Listeners
  creditScoreForm.addEventListener('submit', handleCalculateSubmit);

  recalcBtn.addEventListener('click', () => {
    clearAlert();
    calcFormContainer.style.display = 'block';
    cancelRecalcBtn.style.display = 'inline-flex';
    calcFormContainer.scrollIntoView({ behavior: 'smooth' });
  });

  cancelRecalcBtn.addEventListener('click', () => {
    clearAlert();
    calcFormContainer.style.display = 'none';
    if (currentScoreData) {
      scoreDisplayContainer.style.display = 'block';
    }
  });

  window.addEventListener('DOMContentLoaded', init);
})();
