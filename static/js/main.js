const AUTH_TOKEN_KEY = 'access_token';
const PUBLIC_PATHS = ['/login', '/register'];

// Auth guard
window.addEventListener('DOMContentLoaded', () => {
    const pathname = window.location.pathname;
    if (!PUBLIC_PATHS.includes(pathname) && !localStorage.getItem(AUTH_TOKEN_KEY)) {
        window.location.href = '/login';
    }
});

// Global 401 interceptor
(function () {
    const _fetch = window.fetch.bind(window);
    window.fetch = async function (...args) {
        const response = await _fetch(...args);
        if (response.status === 401) {
            const url = typeof args[0] === 'string' ? args[0] : (args[0]?.url ?? '');
            if (url.startsWith('/api/')) {
                localStorage.removeItem(AUTH_TOKEN_KEY);
                window.location.href = '/login';
                return new Promise(() => {});
            }
        }
        return response;
    };
})();

// Logout
function logout(redirectPath = '/login') {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    window.location.href = redirectPath;
}
window.logout = logout;

// Sidebar: set active nav item from current pathname
function initSidebar() {
    const path = window.location.pathname;
    const map = {
        '/':           'dashboard',
        '/summarizer': 'summarizer',
        '/extractor':  'extractor',
        '/chatbot':    'chatbot',
        '/generator':  'generator',
        '/kyc':        'kyc',
        '/financial-profile': 'financial-profile',
        '/credit-score':      'credit-score',
        '/loan-advisor':      'loan-advisor',
    };
    const activeKey = map[path] || '';

    document.querySelectorAll('[data-nav]').forEach(el => {
        if (el.dataset.nav === activeKey) {
            el.classList.add('active');
        }
    });

    // Auto-open Loan Tools sub-menu when a child page is active
    const loanToolsKeys = ['summarizer', 'extractor', 'chatbot', 'generator'];
    if (loanToolsKeys.includes(activeKey)) {
        const sub    = document.getElementById('loanToolsSub');
        const parent = document.getElementById('navLoanTools');
        if (sub)    sub.classList.add('open');
        if (parent) parent.classList.add('ls-nav-item--open');
    }
}

// Loan Tools accordion toggle
function toggleLoanTools() {
    const sub    = document.getElementById('loanToolsSub');
    const parent = document.getElementById('navLoanTools');
    if (sub)    sub.classList.toggle('open');
    if (parent) parent.classList.toggle('ls-nav-item--open');
}

window.toggleLoanTools = toggleLoanTools;

// KYC Gate check for future modules (Loan Advisor)
async function checkKycGate(e) {
    e.preventDefault();
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    if (!token) {
        window.location.href = '/login';
        return;
    }
    try {
        const res = await fetch('/api/kyc/status', {
            headers: { 'Authorization': 'Bearer ' + token }
        });
        if (res.ok) {
            const data = await res.json();
            if (data.kyc_status === 'verified') {
                window.location.href = '/loan-advisor';
                return;
            }
        }
    } catch (err) {
        console.error('Error verifying KYC gate:', err);
    }
    // If not verified, redirect to KYC with alert message
    window.location.href = '/kyc?msg=' + encodeURIComponent('Please complete KYC verification before proceeding.');
}

function initKycGates() {
    document.querySelectorAll('[data-nav="loan-advisor"]').forEach(el => {
        el.addEventListener('click', checkKycGate);
    });

    // Also attach to dashboard feature card for Loan Advisor
    document.querySelectorAll('.ls-feature-card').forEach(card => {
        const titleEl = card.querySelector('.ls-feature-card__title');
        if (titleEl) {
            const text = titleEl.textContent.toLowerCase();
            if (text.includes('loan advisor')) {
                card.addEventListener('click', checkKycGate);
            }
        }
    });
}

window.addEventListener('DOMContentLoaded', () => {
    initSidebar();
    initKycGates();
});
