// Financial Profile page logic
(function () {
  const TOKEN_KEY = 'access_token';
  const API_PROFILE = '/api/financial-profile';
  const API_KYC = '/api/kyc/status';

  const form = document.getElementById('financialProfileForm');
  const submitBtn = document.getElementById('submitBtn');
  const btnIcon = document.getElementById('btnIcon');
  const btnLabel = document.getElementById('btnLabel');
  const formStatus = document.getElementById('formStatus');

  const monthlyIncome = document.getElementById('monthlyIncome');
  const employmentType = document.getElementById('employmentType');
  const employmentStartDate = document.getElementById('employmentStartDate');
  const existingEmisMonthly = document.getElementById('existingEmisMonthly');
  const existingLoansCount = document.getElementById('existingLoansCount');
  const creditCardLimitTotal = document.getElementById('creditCardLimitTotal');
  const creditCardOutstandingTotal = document.getElementById('creditCardOutstandingTotal');
  const onTimePaymentsPct = document.getElementById('onTimePaymentsPct');
  const missedPaymentsCount12m = document.getElementById('missedPaymentsCount12m');
  const defaultsCount = document.getElementById('defaultsCount');
  const settlementsCount = document.getElementById('settlementsCount');
  const creditHistoryLengthYears = document.getElementById('creditHistoryLengthYears');
  const hardInquiries6m = document.getElementById('hardInquiries6m');

  function setLoading(on) {
    submitBtn.disabled = on;
    if (on) {
      btnIcon.className = '';
      btnIcon.innerHTML = '<span class="ls-spinner"></span>';
      btnLabel.textContent = 'Saving\u2026';
    } else {
      btnIcon.className = 'ti ti-device-floppy';
      btnIcon.innerHTML = '';
      btnLabel.textContent = 'Save financial profile';
    }
  }

  function showAlert(type, msg) {
    formStatus.innerHTML = '<div class="ls-alert ls-alert--' + type + '" style="margin-top:16px;">' + msg + '</div>';
  }

  function clearAlert() {
    formStatus.innerHTML = '';
  }

  // --- KYC Gate Check & Pre-fill on Load ---
  async function init() {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      window.location.href = '/login';
      return;
    }

    try {
      // 1. Verify KYC status
      const kycRes = await fetch(API_KYC, {
        headers: { 'Authorization': 'Bearer ' + token }
      });

      if (kycRes.ok) {
        const kycData = await kycRes.json();
        if (kycData.kyc_status !== 'verified') {
          window.location.href = '/kyc?msg=' + encodeURIComponent('Please complete KYC verification before accessing your financial profile.');
          return;
        }
      } else {
        window.location.href = '/kyc?msg=' + encodeURIComponent('Please complete KYC verification before accessing your financial profile.');
        return;
      }

      // 2. Fetch existing financial profile if any
      const profileRes = await fetch(API_PROFILE, {
        headers: { 'Authorization': 'Bearer ' + token }
      });

      if (profileRes.status === 403) {
        window.location.href = '/kyc?msg=' + encodeURIComponent('Please complete KYC verification before accessing your financial profile.');
        return;
      }

      if (profileRes.ok) {
        const data = await profileRes.json();
        const profile = data.profile || (data.monthly_income !== undefined ? data : null);
        if (profile) {
          if (profile.monthly_income !== undefined && profile.monthly_income !== null) {
            monthlyIncome.value = profile.monthly_income;
          }
          if (profile.employment_type) {
            employmentType.value = profile.employment_type;
          }
          if (profile.employment_start_date) {
            employmentStartDate.value = String(profile.employment_start_date).slice(0, 10);
          }
          if (profile.existing_emis_monthly !== undefined && profile.existing_emis_monthly !== null) {
            existingEmisMonthly.value = profile.existing_emis_monthly;
          }
          if (profile.existing_loans_count !== undefined && profile.existing_loans_count !== null) {
            existingLoansCount.value = profile.existing_loans_count;
          }
          if (profile.credit_card_limit_total !== undefined && profile.credit_card_limit_total !== null) {
            creditCardLimitTotal.value = profile.credit_card_limit_total;
          }
          if (profile.credit_card_outstanding_total !== undefined && profile.credit_card_outstanding_total !== null) {
            creditCardOutstandingTotal.value = profile.credit_card_outstanding_total;
          }
          if (profile.on_time_payments_pct !== undefined && profile.on_time_payments_pct !== null) {
            onTimePaymentsPct.value = profile.on_time_payments_pct;
          }
          if (profile.missed_payments_count_12m !== undefined && profile.missed_payments_count_12m !== null) {
            missedPaymentsCount12m.value = profile.missed_payments_count_12m;
          }
          if (profile.defaults_count !== undefined && profile.defaults_count !== null) {
            defaultsCount.value = profile.defaults_count;
          }
          if (profile.settlements_count !== undefined && profile.settlements_count !== null) {
            settlementsCount.value = profile.settlements_count;
          }
          if (profile.credit_history_length_years !== undefined && profile.credit_history_length_years !== null) {
            creditHistoryLengthYears.value = profile.credit_history_length_years;
          }
          if (profile.hard_inquiries_6m !== undefined && profile.hard_inquiries_6m !== null) {
            hardInquiries6m.value = profile.hard_inquiries_6m;
          }
        }
      }
    } catch (err) {
      console.error('Failed to initialize financial profile:', err);
    }
  }

  // --- Form Submission ---
  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    clearAlert();

    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      window.location.href = '/login';
      return;
    }

    const incomeVal = parseFloat(monthlyIncome.value);
    const empTypeVal = employmentType.value;
    const startDateVal = employmentStartDate.value;

    const errors = [];
    if (isNaN(incomeVal) || incomeVal <= 0) {
      errors.push('Please enter a valid gross monthly income greater than 0.');
    }
    if (!empTypeVal) {
      errors.push('Please select your employment type.');
    }
    if (!startDateVal) {
      errors.push('Please enter your employment start date.');
    }

    const onTimePctVal = parseFloat(onTimePaymentsPct.value);
    if (isNaN(onTimePctVal) || onTimePctVal < 0 || onTimePctVal > 100) {
      errors.push('On-time payments percentage must be between 0 and 100.');
    }

    if (errors.length > 0) {
      showAlert('error', errors.join('<br>'));
      return;
    }

    const payload = {
      monthly_income: incomeVal,
      employment_type: empTypeVal,
      employment_start_date: startDateVal,
      existing_emis_monthly: parseFloat(existingEmisMonthly.value) || 0.0,
      existing_loans_count: parseInt(existingLoansCount.value, 10) || 0,
      credit_card_limit_total: parseFloat(creditCardLimitTotal.value) || 0.0,
      credit_card_outstanding_total: parseFloat(creditCardOutstandingTotal.value) || 0.0,
      on_time_payments_pct: onTimePctVal,
      missed_payments_count_12m: parseInt(missedPaymentsCount12m.value, 10) || 0,
      defaults_count: parseInt(defaultsCount.value, 10) || 0,
      settlements_count: parseInt(settlementsCount.value, 10) || 0,
      credit_history_length_years: parseFloat(creditHistoryLengthYears.value) || 0.0,
      hard_inquiries_6m: parseInt(hardInquiries6m.value, 10) || 0
    };

    setLoading(true);

    try {
      const res = await fetch(API_PROFILE, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + token
        },
        body: JSON.stringify(payload)
      });

      const data = await res.json();

      if (res.status === 403) {
        window.location.href = '/kyc?msg=' + encodeURIComponent('Please complete KYC verification before accessing your financial profile.');
        return;
      }

      if (!res.ok) {
        showAlert('error', data.msg || 'Failed to save financial profile.');
        return;
      }

      showAlert('success', 'Financial profile saved successfully.');
    } catch (err) {
      showAlert('error', 'Network error. Please try again later.');
    } finally {
      setLoading(false);
    }
  });

  window.addEventListener('DOMContentLoaded', init);
})();
