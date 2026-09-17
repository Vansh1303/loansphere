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

/* =============================================
   UI shell enhancements
   These build the brand mark, theme switcher,
   mobile drawer and user chip at runtime so every
   page picks them up without markup changes.
   ============================================= */

const THEME_KEY = 'ls_theme';

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const btn = document.getElementById('lsThemeToggle');
    if (btn) {
        const dark = theme === 'dark';
        btn.querySelector('i').className = dark ? 'ti ti-sun' : 'ti ti-moon';
        btn.querySelector('span').textContent = dark ? 'Light mode' : 'Dark mode';
        btn.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
    }
}

function resolveTheme() {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === 'dark' || stored === 'light') return stored;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function toggleTheme() {
    const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    localStorage.setItem(THEME_KEY, next);
    applyTheme(next);
}
window.toggleTheme = toggleTheme;

// Read the signed-in user's email out of the JWT payload
function currentUserEmail() {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    if (!token) return '';
    try {
        const part = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
        const payload = JSON.parse(atob(part));
        return payload.sub || payload.identity || payload.email || '';
    } catch (e) {
        return '';
    }
}
window.currentUserEmail = currentUserEmail;

function buildBrandMark() {
    const logo = document.querySelector('.ls-sidebar__logo');
    if (!logo || logo.querySelector('.ls-brand-mark')) return;
    const label = logo.textContent.trim() || 'LoanSphere';
    logo.textContent = '';
    logo.insertAdjacentHTML('afterbegin',
        '<span class="ls-brand-mark" aria-hidden="true"><i class="ti ti-scale"></i></span>' +
        '<span class="ls-brand-text">' + label + '<small>Loan intelligence</small></span>'
    );
}

function buildNavGroups() {
    const nav = document.querySelector('.ls-sidebar__nav');
    if (!nav || nav.querySelector('.ls-nav-group-label')) return;
    const addLabel = (beforeEl, text) => {
        if (!beforeEl) return;
        const el = document.createElement('p');
        el.className = 'ls-nav-group-label';
        el.textContent = text;
        nav.insertBefore(el, beforeEl);
    };
    const items = nav.querySelectorAll(':scope > .ls-nav-item');
    addLabel(items[0], 'Workspace');
    addLabel(items[2], 'Eligibility');
}

function buildSidebarFooter() {
    const bottom = document.querySelector('.ls-sidebar__bottom');
    if (!bottom || document.getElementById('lsThemeToggle')) return;

    const email = currentUserEmail();
    const name  = email ? email.split('@')[0] : 'Account';
    const initial = (name[0] || 'U').toUpperCase();

    bottom.innerHTML =
        '<button class="ls-theme-toggle" id="lsThemeToggle" type="button">' +
            '<i class="ti ti-moon"></i><span>Dark mode</span>' +
        '</button>' +
        '<button class="ls-user-chip" type="button" id="lsUserChip" title="Sign out">' +
            '<span class="ls-user-chip__avatar">' + initial + '</span>' +
            '<span class="ls-user-chip__meta">' +
                '<span class="ls-user-chip__name"></span>' +
                '<span class="ls-user-chip__sub">Sign out</span>' +
            '</span>' +
            '<i class="ti ti-logout ls-user-chip__icon"></i>' +
        '</button>';

    bottom.querySelector('.ls-user-chip__name').textContent = email || 'Profile';
    document.getElementById('lsThemeToggle').addEventListener('click', toggleTheme);
    document.getElementById('lsUserChip').addEventListener('click', () => logout());
}

function buildMobileNav() {
    if (!document.querySelector('.ls-sidebar') || document.querySelector('.ls-nav-toggle')) return;

    const toggle = document.createElement('button');
    toggle.className = 'ls-nav-toggle';
    toggle.type = 'button';
    toggle.setAttribute('aria-label', 'Open navigation');
    toggle.innerHTML = '<i class="ti ti-menu-2"></i>';

    const scrim = document.createElement('div');
    scrim.className = 'ls-scrim';

    document.body.append(toggle, scrim);

    const sidebar = document.querySelector('.ls-sidebar');
    const close = () => { sidebar.classList.remove('open'); scrim.classList.remove('show'); };

    toggle.addEventListener('click', () => {
        const open = sidebar.classList.toggle('open');
        scrim.classList.toggle('show', open);
    });
    scrim.addEventListener('click', close);
    sidebar.querySelectorAll('a').forEach(a => a.addEventListener('click', close));
    document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
}

function initShell() {
    applyTheme(resolveTheme());
    buildBrandMark();
    buildNavGroups();
    buildSidebarFooter();
    buildMobileNav();
}

window.addEventListener('DOMContentLoaded', () => {
    initSidebar();
    initKycGates();
    initShell();
});
