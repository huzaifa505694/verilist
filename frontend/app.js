// Automatically redirect from 127.0.0.1 to localhost to support Google OAuth which requires hostname origins
if (window.location.hostname === '127.0.0.1') {
  window.location.replace(window.location.href.replace('127.0.0.1', 'localhost'));
}

// GLOBAL STATE
let state = {
  user: null,
  currentPage: null,
  listings: [],
  savedListings: [],
  currentListingDetail: null,
  viewMode: 'grid', // 'grid' or 'list'
  browsePage: 1,
  browseLimit: 6,
  currentListingId: null,
  detailBackPage: 'browse',
  editingListingId: null,
  adminCategoryFilter: null
};
// BIND DOM EVENTS
const def_events = [
  { id: 'nav-brand-logo', action: () => state.user ? navigateTo('dashboard') : navigateTo('landing') },
  { id: 'nav-login-btn', action: () => navigateTo('login') },
  { id: 'nav-register-btn', action: () => navigateTo('register') },
  { id: 'nav-dash-btn', action: () => navigateTo('dashboard') },
  { id: 'nav-browse-btn', action: () => { state.browsePage = 1; navigateTo('browse'); } },
  { id: 'nav-logout-btn', action: handleLogout },
  { id: 'goto-register-btn', action: () => navigateTo('register') },
  { id: 'goto-login-btn', action: () => navigateTo('login') },
  {
    id: 'dash-action-btn', action: () => {
      if (state.user.role === 'SELLER') navigateTo('create');
      else if (state.user.role === 'ADMIN') navigateTo('admin');
      else navigateTo('browse');
    }
  },
  { id: 'create-cancel-btn', action: () => navigateTo('dashboard') },
  { id: 'modal-close-btn', action: closeListingModal },
  { id: 'apply-filters-btn', action: () => { state.browsePage = 1; renderBrowse(true); } },
  {
    id: 'reset-filters-btn', action: () => {
      document.getElementById('filter-search').value = '';
      document.getElementById('filter-make').value = '';
      document.getElementById('filter-condition').value = '';
      document.getElementById('filter-price-min').value = '';
      document.getElementById('filter-price-max').value = '';
      state.browsePage = 1;
      renderBrowse(true);
    }
  },
  { id: 'landing-get-started', action: () => navigateTo('register') },
  { id: 'landing-sign-in', action: () => navigateTo('login') }
];
function initEventListeners() {
  // Navigation & Page Switching links
  def_events.forEach(item => {
    const el = document.getElementById(item.id);
    if (el) {
      el.addEventListener('click', (e) => {
        e.preventDefault();
        item.action();
      });
    }
  });

  // Forms submit handlers
  const loginForm = document.getElementById('login-form');
  if (loginForm) loginForm.addEventListener('submit', handleLogin);

  const registerForm = document.getElementById('register-form');
  if (registerForm) registerForm.addEventListener('submit', handleRegister);

  const createForm = document.getElementById('create-listing-form');
  if (createForm) createForm.addEventListener('submit', handleCreateListing);

  // Role selectors in register
  const buyerOpt = document.getElementById('role-buyer-opt');
  const sellerOpt = document.getElementById('role-seller-opt');
  if (buyerOpt && sellerOpt) {
    buyerOpt.addEventListener('click', () => {
      buyerOpt.classList.add('active');
      sellerOpt.classList.remove('active');
    });
    sellerOpt.addEventListener('click', () => {
      sellerOpt.classList.add('active');
      buyerOpt.classList.remove('active');
    });
  }

  // Get AI Estimate live preview in creation form


  const deleteBtn = document.getElementById('modal-delete-btn');
  if (deleteBtn) deleteBtn.addEventListener('click', () => {
    if (state.currentListingId) window.handleDeleteListingDirect(state.currentListingId);
  });

  // Click outside modal to close
  const modalBackdrop = document.getElementById('listing-detail-modal');
  if (modalBackdrop) {
    modalBackdrop.addEventListener('click', (e) => {
      if (e.target === modalBackdrop) closeListingModal();
    });
  }

  // Google Sign-In Button (Login Page)
  const googleBtn = document.getElementById('google-login-btn');
  if (googleBtn) {
    googleBtn.addEventListener('click', () => {
      state.googleRequestedRole = 'BUYER';
      initializeAndPromptGoogle();
    });
  }

  // Google Sign-In Button (Register Page)
  const googleRegisterBtn = document.getElementById('google-register-btn');
  if (googleRegisterBtn) {
    googleRegisterBtn.addEventListener('click', () => {
      const activeRoleEl = document.querySelector('.role-option.active');
      const role = activeRoleEl ? activeRoleEl.getAttribute('data-role') : 'BUYER';
      state.googleRequestedRole = role;
      initializeAndPromptGoogle();
    });
  }

  // Google setup modal close
  const googleSetupCloseBtn = document.getElementById('google-setup-close-btn');
  if (googleSetupCloseBtn) {
    googleSetupCloseBtn.addEventListener('click', () => {
      document.getElementById('google-setup-modal').classList.remove('active');
    });
  }

  // Google setup mock bypass action (Offline / local testing fallback)
  const googleBypassBtn = document.getElementById('google-bypass-btn');
  if (googleBypassBtn) {
    googleBypassBtn.addEventListener('click', async () => {
      document.getElementById('google-setup-modal').classList.remove('active');
      showLoader("Signing in with mock Google Account...");
      try {
        const response = await fetch('/api/auth/google', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: "mock_google_user@verilist.com",
            name: "Demo Google User",
            access_token: "mock-google-bypass-token",
            role: state.googleRequestedRole || 'BUYER'
          })
        });
        const data = await response.json();
        if (response.ok) {
          state.user = data.user;
          setupAuthUI();
          showAlert('success', `Welcome, ${data.user.name}! Mock Google sign-in successful.`);
          navigateTo('dashboard');
        } else {
          showAlert('danger', data.error || 'Mock verification failed.');
        }
      } catch (err) {
        showAlert('danger', 'Server connection error during mock login.');
      } finally {
        hideLoader();
      }
    });
  }

  // Google trouble signing in click triggers modal
  document.querySelectorAll('.google-trouble-link').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      const activeRoleEl = document.querySelector('.role-option.active');
      state.googleRequestedRole = activeRoleEl ? activeRoleEl.getAttribute('data-role') : 'BUYER';
      document.getElementById('google-setup-modal').classList.add('active');
    });
  });

  // Dashboard Switch Role Button
  const toggleRoleBtn = document.getElementById('dash-toggle-role-btn');
  if (toggleRoleBtn) {
    toggleRoleBtn.addEventListener('click', () => {
      handleSwitchRole();
    });
  }

  // Back to Dashboard page-level links
  document.querySelectorAll('.back-to-dash-link').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      navigateTo('dashboard');
    });
  });

  // Browse grid/list view toggle actions
  const viewGridBtn = document.getElementById('view-grid-btn');
  const viewListBtn = document.getElementById('view-list-btn');
  if (viewGridBtn && viewListBtn) {
    viewGridBtn.addEventListener('click', () => {
      state.viewMode = 'grid';
      viewGridBtn.classList.add('active');
      viewListBtn.classList.remove('active');
      renderBrowse(true);
    });
    viewListBtn.addEventListener('click', () => {
      state.viewMode = 'list';
      viewListBtn.classList.add('active');
      viewGridBtn.classList.remove('active');
      renderBrowse(true);
    });
  }

  // Detail page back link
  const detailBackLink = document.getElementById('detail-back-link');
  if (detailBackLink) {
    detailBackLink.addEventListener('click', (e) => {
      e.preventDefault();
      navigateTo(state.detailBackPage || 'browse');
    });
  }



  const detailEditBtn = document.getElementById('detail-edit-btn');
  if (detailEditBtn) detailEditBtn.addEventListener('click', () => {
    if (state.currentListingId) window.handleEditListing(state.currentListingId);
  });

  const detailDeleteBtn = document.getElementById('detail-delete-btn');
  if (detailDeleteBtn) detailDeleteBtn.addEventListener('click', () => {
    if (state.currentListingId) window.handleDeleteListingDirect(state.currentListingId);
  });

  // Admin clear category filter button (Feature 2)
  const adminClearFilterBtn = document.getElementById('admin-clear-filter-btn');
  if (adminClearFilterBtn) {
    adminClearFilterBtn.addEventListener('click', (e) => {
      e.preventDefault();
      state.adminCategoryFilter = null;
      window.updateAdminFilterUI();
    });
  }

  // Buyer Action Listeners
  const detailOfferBtn = document.getElementById('detail-offer-btn');
  if (detailOfferBtn) {
    detailOfferBtn.addEventListener('click', handleMakeOffer);
  }

  const detailBuyBtn = document.getElementById('detail-buy-btn');
  if (detailBuyBtn) {
    detailBuyBtn.addEventListener('click', handleInstantBuy);
  }
}

// ROUTING & NAVIGATION
function navigateTo(pageId) {
  clearAlerts();

  const prevPage = state.currentPage;

  // Hide all sections and clear slide classes
  document.querySelectorAll('.page-section').forEach(sec => {
    sec.classList.add('hidden');
    sec.classList.remove('slide-in-right', 'slide-in-left');
  });

  state.currentPage = pageId;

  // Calculate slide direction for landing / auth transitions
  const authFlow = ['landing', 'login', 'register'];
  const isSlide = prevPage && authFlow.includes(pageId) && authFlow.includes(prevPage);
  const slideDir = isSlide
    ? (authFlow.indexOf(pageId) > authFlow.indexOf(prevPage) ? 'slide-in-right' : 'slide-in-left')
    : '';

  if (pageId === 'landing') {
    const el = document.getElementById('landing-page');
    el.classList.remove('hidden');
    if (slideDir) el.classList.add(slideDir);
  } else if (pageId === 'dashboard') {
    if (!state.user) return navigateTo('landing');
    renderDashboard();
  } else if (pageId === 'browse') {
    renderBrowse();
  } else if (pageId === 'saved') {
    if (!state.user) return navigateTo('landing');
    renderSavedListings();
  } else if (pageId === 'create') {
    if (!state.user || state.user.role !== 'SELLER') return navigateTo('dashboard');
    resetCreateForm();
    document.getElementById('create-page').classList.remove('hidden');
  } else if (pageId === 'admin') {
    if (!state.user || state.user.role !== 'ADMIN') return navigateTo('dashboard');
    renderAdminQueue();
  } else if (pageId === 'detail') {
    if (state.currentListingId) {
      renderListingDetail(state.currentListingId);
    } else {
      navigateTo('browse');
    }
  } else {
    // Auth pages (login, register)
    const pageEl = document.getElementById(`${pageId}-page`);
    if (pageEl) {
      pageEl.classList.remove('hidden');
      if (slideDir) pageEl.classList.add(slideDir);
    }
  }

  lucide.createIcons();
}
// ═══════════════════════════════════════════════════════════════════
// DYNAMIC NAVBAR — Auto-hide on scroll down, reveal on scroll up
// ═══════════════════════════════════════════════════════════════════
function initDynamicNavbar() {
  const navbar = document.querySelector('.navbar');
  if (!navbar) return;

  let lastScrollY = window.scrollY;
  let ticking = false;
  const SCROLL_THRESHOLD = 60; // px before hiding kicks in
  const DEAD_ZONE = 10;        // px of movement to ignore (prevents flicker)

  function onScroll() {
    if (ticking) return;
    ticking = true;

    requestAnimationFrame(() => {
      const currentScrollY = window.scrollY;
      const delta = currentScrollY - lastScrollY;

      // Only act if scroll exceeds the dead zone to prevent micro-jitter
      if (Math.abs(delta) > DEAD_ZONE) {
        if (delta > 0 && currentScrollY > SCROLL_THRESHOLD) {
          // Scrolling DOWN past threshold → hide
          navbar.classList.add('navbar--hidden');
        } else if (delta < 0) {
          // Scrolling UP → show
          navbar.classList.remove('navbar--hidden');
        }
        lastScrollY = currentScrollY;
      }

      ticking = false;
    });
  }

  window.addEventListener('scroll', onScroll, { passive: true });
}

// CHECK USER SESSION AND INITIALIZATION
function startApp() {
  initEventListeners();
  initDynamicNavbar();
  checkAuthSession();
  eagerLoadGoogleConfig(); // Eagerly load Google Client ID
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startApp);
} else {
  startApp();
}

async function checkAuthSession() {
  showLoader("Restoring Secure Session...");
  try {
    const response = await fetch('/api/auth/me');
    if (response.ok) {
      const data = await response.json();
      state.user = data.user;
      setupAuthUI();
      navigateTo('dashboard');
    } else {
      state.user = null;
      setupGuestUI();
      navigateTo('landing');
    }
  } catch (err) {
    console.error("Failed to restore session:", err);
    state.user = null;
    setupGuestUI();
    navigateTo('landing');
  } finally {
    hideLoader();
  }
}

// AUTHENTICATION STATE RENDERERS
function setupAuthUI() {
  document.getElementById('guest-nav-links').classList.add('hidden');

  const authLinks = document.getElementById('auth-nav-links');
  authLinks.classList.remove('hidden');
  authLinks.style.display = 'flex';

  // Set user name
  document.getElementById('nav-user-name').innerText = state.user.name.split(' ')[0];

  // Set avatar initials
  const avatarEl = document.getElementById('nav-user-avatar');
  if (avatarEl) {
    const initials = state.user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
    avatarEl.innerText = initials;
  }

  // Role badge
  const roleBadge = document.getElementById('nav-user-role');
  roleBadge.innerText = state.user.role;
  roleBadge.className = 'badge';
  if (state.user.role === 'ADMIN') roleBadge.classList.add('badge-danger');
  else if (state.user.role === 'SELLER') roleBadge.classList.add('badge-gold');
  else roleBadge.classList.add('badge-blue');

  connectNotificationStream();
}

function setupGuestUI() {
  document.getElementById('guest-nav-links').classList.remove('hidden');
  document.getElementById('auth-nav-links').classList.add('hidden');
  
  if (typeof _eventSource !== 'undefined' && _eventSource) {
    _eventSource.close();
    _eventSource = null;
  }
}

// LOGOUT HANDLER
async function handleLogout() {
  showLoader("Logging out...");
  try {
    const response = await fetch('/api/auth/logout', { method: 'POST' });
    if (response.ok) {
      state.user = null;
      setupGuestUI();
      navigateTo('landing');
      showAlert('success', 'Logged out successfully.');
    }
  } catch (err) {
    console.error("Logout failed:", err);
  } finally {
    hideLoader();
  }
}

// LOGIN SUBMIT
async function handleLogin(e) {
  e.preventDefault();
  const email = document.getElementById('login-email').value;
  const password = document.getElementById('login-password').value;

  showLoader("Authenticating...");
  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    const data = await response.json();
    if (response.ok) {
      state.user = data.user;
      setupAuthUI();
      navigateTo('dashboard');
      showAlert('success', 'Welcome back to VeriList!');
    } else {
      showAlert('danger', data.error || 'Login failed. Check credentials.');
    }
  } catch (err) {
    showAlert('danger', 'Server connection failed. Try again.');
  } finally {
    hideLoader();
  }
}

// REGISTER SUBMIT
async function handleRegister(e) {
  e.preventDefault();
  const name = document.getElementById('register-name').value;
  const email = document.getElementById('register-email').value;
  const password = document.getElementById('register-password').value;

  // Find which role option is active
  const activeRoleEl = document.querySelector('.role-option.active');
  const role = activeRoleEl ? activeRoleEl.getAttribute('data-role') : 'BUYER';

  showLoader("Creating Secure Account...");
  try {
    const response = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password, role })
    });

    const data = await response.json();
    if (response.ok) {
      state.user = data.user;
      setupAuthUI();
      navigateTo('dashboard');
      showAlert('success', 'Account registered successfully!');
    } else {
      showAlert('danger', data.error || 'Registration failed.');
    }
  } catch (err) {
    showAlert('danger', 'Server connection failed. Try again.');
  } finally {
    hideLoader();
  }
}

// ═══════════════════════════════════════════════════════════════════
// REAL GOOGLE SIGN-IN (Google Identity Services)
// ═══════════════════════════════════════════════════════════════════

// Fetched once from backend — set by initializeAndPromptGoogle() or eagerLoadGoogleConfig()
let _googleClientId = null;
let _googleTokenClient = null;
let _gsiLibraryReady = false;

// Wire up global GSI onload callback
window.onGsiScriptLoadedCallback = () => {
  _gsiLibraryReady = true;
  console.log('[VeriList] Google GSI library loaded via callback.');
  if (_googleClientId) {
    initGoogleTokenClient();
  }
};

// Check if library already loaded before app.js executed
if (window._gsiLibraryReady) {
  _gsiLibraryReady = true;
}

/**
 * Eagerly loads the Google client configuration from the backend on page load.
 * This pre-loads the client ID, allowing popups to trigger synchronously when the user clicks the button.
 */
async function eagerLoadGoogleConfig() {
  try {
    const res = await fetch('/api/config/google');
    const cfg = await res.json();
    if (cfg.configured && cfg.client_id) {
      _googleClientId = cfg.client_id;
      // Pre-initialize token client if GSI library already loaded
      if (_gsiLibraryReady || (typeof google !== 'undefined' && google.accounts && google.accounts.oauth2)) {
        initGoogleTokenClient();
      }
    }
  } catch (err) {
    console.warn("Failed to eagerly load Google config:", err);
  }
}

/**
 * Initializes the Google Token client if the client ID is present and GSI library is loaded.
 */
function initGoogleTokenClient() {
  if (_googleClientId && !_googleTokenClient && typeof google !== 'undefined' && google.accounts && google.accounts.oauth2) {
    _googleTokenClient = google.accounts.oauth2.initTokenClient({
      client_id: _googleClientId,
      scope: 'https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email',
      callback: async (tokenResponse) => {
        _disarmPopupWatchdog();
        if (tokenResponse.error) {
          showAlert('danger', `Google Sign-in failed: ${tokenResponse.error}`);
          return;
        }
        if (tokenResponse.access_token) {
          await handleGoogleAccessToken(tokenResponse.access_token);
        }
      },
    });
    console.log('[VeriList] Google token client initialized successfully.');
  }
}

/**
 * Waits up to `maxMs` for the GSI library to become available, polling every 200ms.
 * Returns true if the library is ready, false if timed out.
 */
function waitForGsi(maxMs = 8000) {
  return new Promise((resolve) => {
    if (typeof google !== 'undefined' && google.accounts && google.accounts.oauth2) {
      resolve(true);
      return;
    }
    const interval = setInterval(() => {
      if (typeof google !== 'undefined' && google.accounts && google.accounts.oauth2) {
        clearInterval(interval);
        resolve(true);
      }
    }, 200);
    setTimeout(() => {
      clearInterval(interval);
      resolve(false);
    }, maxMs);
  });
}

/**
 * Called when user clicks the Google button.
 * MUST execute requestAccessToken synchronously if ready, to avoid popup blockers.
 */
function initializeAndPromptGoogle() {
  // If the client is already fully initialized (thanks to eager loading),
  // we must call requestAccessToken() IMMEDIATELY without any `await`.
  // `await` yields to the microtask queue, which destroys the user gesture context 
  // and causes strict browsers to block the Google popup.
  if (_googleTokenClient) {
    _armPopupWatchdog();
    _googleTokenClient.requestAccessToken();
    return;
  }

  // Not ready yet. Going through the async fallback below breaks the
  // user-gesture chain, so the popup can get SILENTLY blocked by the
  // browser (no error, no callback — it just looks like the button did
  // nothing). Tell the user plainly instead of failing silently.
  showAlert('warning', 'Google Sign-In is still loading — please wait a second and click the button again.');
  _fallbackAsyncGooglePrompt();
}

// Detects a silently-blocked popup: if the GSI callback never fires within
// a few seconds of requestAccessToken(), the popup was almost certainly
// blocked by the browser.
let _popupWatchdogTimer = null;
function _armPopupWatchdog() {
  clearTimeout(_popupWatchdogTimer);
  _popupWatchdogTimer = setTimeout(() => {
    showAlert('warning', 'Nothing happened? Your browser may have blocked the Google sign-in popup. Allow popups for this site and try again.');
  }, 4000);
}
function _disarmPopupWatchdog() {
  clearTimeout(_popupWatchdogTimer);
}

async function _fallbackAsyncGooglePrompt() {
  // Fetch Client ID from backend if we don't have it yet
  if (!_googleClientId) {
    try {
      const res = await fetch('/api/config/google');
      const cfg = await res.json();
      if (cfg.configured && cfg.client_id) {
        _googleClientId = cfg.client_id;
      } else {
        document.getElementById('google-setup-modal').classList.add('active');
        return;
      }
    } catch (err) {
      showAlert('danger', 'Could not connect to server.');
      return;
    }
  }

  // Wait for GSI library if it hasn't fully loaded yet
  const gsiReady = await waitForGsi(8000);
  if (!gsiReady) {
    showAlert('warning', 'Google Sign-In library did not load (network issue or blocked by browser). Use the demo bypass below.');
    document.getElementById('google-setup-modal').classList.add('active');
    return;
  }

  // Initialize the token client
  initGoogleTokenClient();

  if (!_googleTokenClient) {
    showAlert('danger', 'Failed to initialize Google Sign-In client. Please refresh the page and try again.');
    return;
  }

  // Request token — opens the real Google Account selection popup
  _armPopupWatchdog();
  _googleTokenClient.requestAccessToken();
}

/**
 * Fetches user profile from Google using the access token,
 * then sends the verified data to our backend.
 */
async function handleGoogleAccessToken(accessToken) {
  showLoader('Fetching Google profile...');
  try {
    const profileRes = await fetch(`https://www.googleapis.com/oauth2/v3/userinfo?access_token=${accessToken}`);
    const profile = await profileRes.json();

    if (!profile.email) {
      showAlert('danger', 'Could not retrieve email from Google account.');
      return;
    }

    showLoader('Verifying Google account with server...');
    const response = await fetch('/api/auth/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        email: profile.email,
        name: profile.name || profile.given_name || 'Google User',
        access_token: accessToken,
        role: state.googleRequestedRole || 'BUYER'
      })
    });

    const data = await response.json();

    if (response.ok) {
      state.user = data.user;
      setupAuthUI();
      navigateTo('dashboard');
      showAlert('success', `Welcome, ${data.user.name}! Signed in with Google.`);
    } else {
      showAlert('danger', data.error || 'Google verification failed.');
    }
  } catch (err) {
    showAlert('danger', 'Connection to server failed. Please try again.');
  } finally {
    hideLoader();
  }
}

// SWITCH USER ROLE (BUYER <=> SELLER)
async function handleSwitchRole() {
  if (!state.user) return;
  const newRole = state.user.role === 'BUYER' ? 'SELLER' : 'BUYER';

  showLoader(`Switching to ${newRole}...`);
  try {
    const response = await fetch('/api/auth/role', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: newRole })
    });

    const data = await response.json();
    if (response.ok) {
      state.user = data.user;
      setupAuthUI();
      renderDashboard();
      showAlert('success', `Successfully switched your role to ${newRole}!`);
    } else {
      showAlert('danger', data.error || 'Failed to switch role.');
    }
  } catch (err) {
    showAlert('danger', 'Server connection failed. Try again.');
  } finally {
    hideLoader();
  }
}

// RENDER DASHBOARD
async function renderDashboard() {
  const container = document.getElementById('dashboard-page');
  container.classList.remove('hidden');

  // Set account details card fields
  document.getElementById('dash-welcome-title').innerText = `Welcome Back, ${state.user.name}`;
  document.getElementById('dash-user-role').innerText = state.user.role;
  document.getElementById('dash-account-email').innerText = state.user.email;
  document.getElementById('dash-account-id').innerText = state.user.id;

  // Render Action button depending on role
  const actionBtn = document.getElementById('dash-action-btn');
  if (state.user.role === 'SELLER') {
    actionBtn.innerHTML = `<i data-lucide="plus"></i><span>Create New Listing</span>`;
    actionBtn.className = "btn btn-primary";
  } else if (state.user.role === 'ADMIN') {
    actionBtn.innerHTML = `<i data-lucide="list-filter"></i><span>Audit Review Queue</span>`;
    actionBtn.className = "btn btn-accent";
  } else { // BUYER
    actionBtn.innerHTML = `<i data-lucide="shopping-bag"></i><span>Browse Verified Items</span>`;
    actionBtn.className = "btn btn-primary";
  }

  // Load stats
  const statsGrid = document.getElementById('dash-stats-grid');
  statsGrid.innerHTML = '<div class="loading-container" style="grid-column: 1/-1;"><div class="spinner"></div></div>';

  const sellerListingsContainer = document.getElementById('seller-listings-container');
  if (sellerListingsContainer) {
    if (state.user.role === 'SELLER') {
      sellerListingsContainer.classList.remove('hidden');
    } else {
      sellerListingsContainer.classList.add('hidden');
    }
  }

  try {
    const statsResponse = await fetch('/api/dashboard/stats');
    const statsData = await statsResponse.json();

    if (statsResponse.ok) {
      const stats = statsData.stats;
      statsGrid.innerHTML = ''; // Clear spinner

      if (state.user.role === 'ADMIN') {
        statsGrid.innerHTML = `
          <div class="stat-card glass-card">
            <i data-lucide="alert-circle" style="color: var(--color-gold); width: 24px; height: 24px;"></i>
            <div class="stat-value">${stats.pendingReviews}</div>
            <div class="stat-label">Pending Reviews</div>
          </div>
          <div class="stat-card glass-card">
            <i data-lucide="users" style="color: var(--color-secondary); width: 24px; height: 24px;"></i>
            <div class="stat-value">${stats.activeUsers}</div>
            <div class="stat-label">Active Users</div>
          </div>
          <div class="stat-card glass-card">
            <i data-lucide="car" style="color: var(--color-primary); width: 24px; height: 24px;"></i>
            <div class="stat-value">${stats.totalListings}</div>
            <div class="stat-label">Total Listings</div>
          </div>
        `;
      } else if (state.user.role === 'SELLER') {
        statsGrid.innerHTML = `
          <div class="stat-card glass-card">
            <i data-lucide="bar-chart-2" style="color: var(--color-primary); width: 24px; height: 24px;"></i>
            <div class="stat-value">${stats.totalListings}</div>
            <div class="stat-label">Total Listings</div>
          </div>
          <div class="stat-card glass-card">
            <i data-lucide="shopping-bag" style="color: var(--color-secondary); width: 24px; height: 24px;"></i>
            <div class="stat-value">${stats.activeListings}</div>
            <div class="stat-label">Active Listings</div>
          </div>
          <div class="stat-card glass-card">
            <i data-lucide="check-circle" style="color: var(--color-emerald); width: 24px; height: 24px;"></i>
            <div class="stat-value">${stats.soldListings}</div>
            <div class="stat-label">Sold Listings</div>
          </div>
        `;
        // Load seller's own listings table
        await renderSellerListings();
      } else { // BUYER
        statsGrid.innerHTML = `
          <div class="stat-card glass-card">
            <i data-lucide="shopping-bag" style="color: var(--color-primary); width: 24px; height: 24px;"></i>
            <div class="stat-value">Buyer</div>
            <div class="stat-label">Account Role</div>
          </div>
          <div class="stat-card glass-card">
            <i data-lucide="shield-check" style="color: var(--color-secondary); width: 24px; height: 24px;"></i>
            <div class="stat-value">Active</div>
            <div class="stat-label">Verification Status</div>
          </div>
        `;
      }
    } else {
      statsGrid.innerHTML = '<div style="color: var(--color-rose); text-align: center; grid-column: 1/-1;">Error loading statistics.</div>';
    }
  } catch (err) {
    console.error("Failed to load dashboard statistics:", err);
    statsGrid.innerHTML = '<div style="color: var(--color-rose); text-align: center; grid-column: 1/-1;">Error loading statistics.</div>';
  }

  // Load offers for buyer or seller (Feature 4)
  if (state.user.role === 'BUYER' || state.user.role === 'SELLER') {
    try {
      const offersRes = await fetch('/api/offers');
      const offersData = await offersRes.json();
      if (offersRes.ok) {
        renderOffersSection(offersData.offers);
      }
    } catch (err) {
      console.error("Failed to load offers:", err);
    }
  } else {
    // Hide offers section for admins
    const oldOffers = document.getElementById('dash-offers-container');
    if (oldOffers) oldOffers.remove();
  }

  lucide.createIcons();
}

async function renderSellerListings() {
  const tbody = document.getElementById('seller-listings-table-body');
  const countBadge = document.getElementById('seller-listings-count');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-muted);"><div class="spinner" style="margin: 0 auto; width: 24px; height: 24px;"></div></td></tr>';

  try {
    const res = await fetch(`/api/listings?seller_id=${state.user.id}`);
    const data = await res.json();
    if (res.ok) {
      const listings = data.listings;
      countBadge.innerText = `${listings.length} Listings`;
      tbody.innerHTML = '';

      if (listings.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-muted);">You have not created any listings yet.</td></tr>';
        return;
      }

      listings.forEach(item => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid var(--border-subtle)';

        let statusClass = 'badge-blue';
        if (item.status === 'SOLD') statusClass = 'badge-success';
        else if (item.status === 'PENDING_REVIEW') statusClass = 'badge-warning';
        else if (item.status === 'REMOVED') statusClass = 'badge-danger';

        const viewsCount = item.status === 'ACTIVE' ? Math.round(item.trust_score * 1.5 + 12) : 0;

        tr.innerHTML = `
          <td style="padding: 1rem 0.5rem; font-weight: 600; color: var(--text-primary);">
            <a href="#" onclick="event.preventDefault(); window.navigateToDetail('${item.id}', 'dashboard');" style="color: var(--text-primary); text-decoration: underline;">
              ${item.title}
            </a>
            <div style="font-size: 0.75rem; color: var(--text-muted); font-weight: 400; margin-top: 0.15rem;">
              Year: ${item.year} | Mileage: ${item.mileage.toLocaleString()} mi | Condition: ${item.condition}
            </div>
          </td>
          <td style="padding: 1rem 0.5rem; color: var(--color-gold); font-weight: 700;">$${item.price.toLocaleString()}</td>
          <td style="padding: 1rem 0.5rem;">
            <span class="badge ${item.trust_score >= 80 ? 'badge-success' : 'badge-warning'}">${item.trust_score}%</span>
          </td>
          <td style="padding: 1rem 0.5rem; color: var(--text-secondary);">${viewsCount} views</td>
          <td style="padding: 1rem 0.5rem;">
            <span class="badge ${statusClass}">${item.status}</span>
          </td>
          <td style="padding: 1rem 0.5rem; text-align: right; white-space: nowrap;">
            <button class="btn btn-secondary" onclick="window.handleEditListing('${item.id}')" style="padding: 0.35rem 0.65rem; font-size: 0.75rem; border-radius: 4px; margin-right: 0.25rem;">
              <i data-lucide="pencil" style="width: 12px; height: 12px;"></i>
            </button>
            <button class="btn btn-danger" onclick="window.handleDeleteListingDirect('${item.id}')" style="padding: 0.35rem 0.65rem; font-size: 0.75rem; border-radius: 4px;">
              <i data-lucide="trash-2" style="width: 12px; height: 12px;"></i>
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });
      lucide.createIcons();
    } else {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2rem; color: var(--color-rose);">Failed to load listings.</td></tr>';
    }
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2rem; color: var(--color-rose);">Network error loading listings.</td></tr>';
  }
}

window.navigateToDetail = (id, backPage) => {
  state.currentListingId = id;
  state.detailBackPage = backPage;
  navigateTo('detail');
};

window.handleEditListing = async (id) => {
  showLoader("Retrieving Listing Details...");
  try {
    const res = await fetch(`/api/listings/${id}`);
    const data = await res.json();
    if (res.ok) {
      const listing = data.listing;
      state.editingListingId = listing.id;

      // Populate Create/Edit Form fields
      navigateTo('create');

      // Update Title & Button
      document.querySelector('#create-page h2.auth-title').innerText = "Edit Listing";
      document.querySelector('#create-page p.auth-subtitle').innerText = "Update details about your car. AI models will verify pricing integrity.";
      document.getElementById('create-submit-btn').innerText = "Update Listing";

      document.getElementById('create-title').value = listing.title;
      document.getElementById('create-make').value = listing.make;
      document.getElementById('create-model').value = listing.model;
      document.getElementById('create-year').value = listing.year;
      document.getElementById('create-mileage').value = listing.mileage;
      document.getElementById('create-condition').value = listing.condition;
      document.getElementById('create-price').value = listing.price;
      document.getElementById('create-desc').value = listing.description;

      // Show AI estimate box with pre-saved values
      handleGetAIEstimate();
    } else {
      showAlert('danger', 'Could not retrieve listing details.');
    }
  } catch (err) {
    showAlert('danger', 'Network error retrieving listing details.');
  } finally {
    hideLoader();
  }
};

window.handleDeleteListingDirect = async (id) => {
  if (!confirm("Are you sure you want to permanently delete this listing?")) return;
  showLoader("Deleting listing...");
  try {
    const response = await fetch(`/api/listings/${id}`, { method: 'DELETE' });
    if (response.ok) {
      showAlert('success', 'Listing deleted successfully.');
      if (state.currentPage === 'detail') {
        navigateTo('dashboard');
      } else {
        renderDashboard();
      }
    } else {
      const data = await response.json();
      showAlert('danger', data.error || 'Failed to delete listing.');
    }
  } catch (err) {
    showAlert('danger', 'Server connection error.');
  } finally {
    hideLoader();
  }
};

// RENDER OFFERS LIST IN DASHBOARD
function renderOffersSection(offers) {
  // Remove existing offers container if any
  const oldOffers = document.getElementById('dash-offers-container');
  if (oldOffers) oldOffers.remove();

  if (!offers || offers.length === 0) return;

  const offersContainer = document.createElement('div');
  offersContainer.id = 'dash-offers-container';
  offersContainer.className = 'glass-card';
  offersContainer.style.padding = '2rem';
  offersContainer.style.marginTop = '2rem';
  offersContainer.innerHTML = `
    <h4 class="card-header" style="margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;">
      <i data-lucide="message-square"></i>
      <span>${state.user.role === 'SELLER' ? 'Offers Received' : 'My Offers'}</span>
    </h4>
    <div style="display: flex; flex-direction: column; gap: 1rem;" id="dash-offers-list"></div>
  `;

  // Append after workspace overview grid
  const statsGrid = document.getElementById('dash-stats-grid');
  statsGrid.parentNode.insertBefore(offersContainer, statsGrid.nextSibling);

  const list = document.getElementById('dash-offers-list');
  offers.forEach(o => {
    const item = document.createElement('div');
    item.className = 'glass-card';
    item.style.padding = '1rem 1.5rem';
    item.style.display = 'flex';
    item.style.justifyContent = 'space-between';
    item.style.alignItems = 'center';
    item.style.border = '1px solid var(--border-muted)';

    let badgeClass = 'badge-info';
    if (o.status === 'ACCEPTED') badgeClass = 'badge-success';
    else if (o.status === 'REJECTED') badgeClass = 'badge-danger';
    else if (o.status === 'COUNTER_OFFER') badgeClass = 'badge-warning';

    let actionsHtml = '';
    if (state.user.role === 'SELLER' && o.status === 'PENDING') {
      actionsHtml = `
        <div style="display: flex; gap: 0.4rem; flex-wrap: nowrap;">
          <button class="btn btn-primary" onclick="window.handleOfferAction('${o.id}', 'ACCEPTED')" style="padding: 0.35rem 0.65rem; font-size: 0.75rem;">Accept</button>
          <button class="btn btn-secondary" onclick="window.handleOfferAction('${o.id}', 'REJECTED')" style="padding: 0.35rem 0.65rem; font-size: 0.75rem;">Reject</button>
          <button class="btn btn-gold" onclick="window.handleOfferCounter('${o.id}')" style="padding: 0.35rem 0.65rem; font-size: 0.75rem;">Counter</button>
        </div>
      `;
    } else if (state.user.role === 'BUYER' && o.status === 'COUNTER_OFFER' && o.last_action_by === 'SELLER') {
      actionsHtml = `
        <div style="display: flex; flex-direction: column; gap: 0.3rem; align-items: flex-end;">
          <span class="badge badge-warning" style="font-size:0.75rem;">Counter: $${o.counter_amount.toLocaleString()}</span>
          <button class="btn btn-gold" onclick="window.handleAcceptCounterAndPay('${o.id}', '${o.listing_id}')" style="padding: 0.35rem 0.75rem; font-size: 0.75rem;">Accept & Pay</button>
        </div>
      `;
    } else {
      actionsHtml = `<span class="badge ${badgeClass}">${o.status}</span>`;
    }

    const partyLabel = state.user.role === 'SELLER' ? `Buyer: ${o.buyer_name}` : `Seller: ${o.seller_name}`;

    item.innerHTML = `
      <div>
        <strong style="font-size: 1rem; color: var(--text-primary);">${o.listing_title}</strong>
        <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.25rem;">
          <span>Offer Amount: <strong style="color: var(--color-secondary); font-size: 0.95rem;">$${o.amount.toLocaleString()}</strong></span>
          <span style="margin: 0 0.5rem;">|</span>
          <span>${partyLabel}</span>
        </div>
      </div>
      <div>${actionsHtml}</div>
    `;
    list.appendChild(item);
  });
}

// HANDLE OFFER STATUS ACTIONS (SELLER)
async function handleOfferAction(offerId, status) {
  showLoader("Updating offer...");
  try {
    const response = await fetch(`/api/offers/${offerId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    });

    if (response.ok) {
      showAlert('success', `Offer successfully ${status.toLowerCase()}!`);
      renderDashboard();
    } else {
      const data = await response.json();
      showAlert('danger', data.error || 'Failed to update offer.');
    }
  } catch (err) {
    showAlert('danger', 'Server connection error.');
  } finally {
    hideLoader();
  }
}
window.handleOfferAction = handleOfferAction; // Expose globally for inline onclick

// RENDER BROWSE FEED
async function renderBrowse(keepFilters = false) {
  const container = document.getElementById('browse-page');
  container.classList.remove('hidden');

  if (!keepFilters) {
    state.browsePage = 1;
  }

  // Restore filter panel visibility for Browse page
  document.querySelector('.filter-panel').classList.remove('hidden');

  // Set Browse title
  document.getElementById('browse-page-title').innerText = "Browse Active Listings";

  const search = document.getElementById('filter-search').value;
  const make = document.getElementById('filter-make').value;
  const condition = document.getElementById('filter-condition').value;
  const priceMin = document.getElementById('filter-price-min').value;
  const priceMax = document.getElementById('filter-price-max').value;

  const grid = document.getElementById('listings-feed-grid');
  grid.innerHTML = '<div class="loading-container" style="grid-column: 1/-1;"><div class="spinner"></div></div>';

  try {
    // Build query params with pagination
    let url = `/api/listings?page=${state.browsePage}&limit=${state.browseLimit}&`;
    if (search) url += `search=${encodeURIComponent(search)}&`;
    if (make) url += `make=${encodeURIComponent(make)}&`;
    if (condition) url += `condition=${encodeURIComponent(condition)}&`;
    if (priceMin) url += `price_min=${priceMin}&`;
    if (priceMax) url += `price_max=${priceMax}&`;

    const response = await fetch(url);
    const data = await response.json();

    if (response.ok) {
      grid.innerHTML = ''; // Clear spinner
      const listings = data.listings;
      state.listings = listings;

      // Adjust view layout class based on viewMode
      if (state.viewMode === 'list') {
        grid.className = 'listings-list';
      } else {
        grid.className = 'listings-grid';
      }

      if (listings.length === 0) {
        grid.innerHTML = '<p style="color: var(--text-muted); text-align: center; grid-column: 1/-1; padding: 3rem;">No active listings match your criteria.</p>';
        document.getElementById('listings-pagination').innerHTML = '';
        return;
      }

      listings.forEach(item => {
        const card = document.createElement('div');
        card.className = `glass-card listing-card ${state.viewMode === 'list' ? 'list-layout' : ''}`;
        card.style.cursor = 'pointer';

        card.innerHTML = `
          <div class="listing-image-placeholder" onclick="window.navigateToDetail('${item.id}', 'browse')">
            <i data-lucide="car" style="width: 48px; height: 48px; opacity: 0.25;"></i>
          </div>
          <div class="listing-content" onclick="window.navigateToDetail('${item.id}', 'browse')">
            <div class="listing-card-main-info" style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem;">
              <h2 class="listing-title">${item.title}</h2>
              <div class="listing-price">$${item.price.toLocaleString()}</div>
            </div>
            
            <div class="listings-specs-wrapper" style="margin-top: 0.4rem; margin-bottom: 0.4rem;">
              <div class="listing-specs">
                <div class="listing-spec-item"><i data-lucide="calendar" style="width: 14px;"></i><span>${item.year}</span></div>
                <div class="listing-spec-item"><i data-lucide="gauge" style="width: 14px;"></i><span>${item.mileage.toLocaleString()} mi</span></div>
                <div class="listing-spec-item"><i data-lucide="star" style="width: 14px;"></i><span>${item.condition}</span></div>
              </div>
            </div>
            
            <p class="listing-desc-excerpt">${item.description}</p>
            
            <div class="listing-footer">
              <span class="seller-tag">
                <i data-lucide="user" style="width: 14px; height: 14px;"></i>
                <span>${item.seller_name}</span>
              </span>
            </div>
          </div>
        `;
        grid.appendChild(card);
      });

      // Render Pagination Buttons
      const totalCount = data.total || 0;
      const totalPages = Math.ceil(totalCount / state.browseLimit);
      renderPagination(totalPages);
    } else {
      grid.innerHTML = '<div style="color: var(--status-danger); text-align: center; grid-column: 1/-1;">Error loading listings feed.</div>';
    }
  } catch (err) {
    grid.innerHTML = '<div style="color: var(--status-danger); text-align: center; grid-column: 1/-1;">Error loading listings feed.</div>';
  }
  lucide.createIcons();
}

function renderPagination(totalPages) {
  const pagContainer = document.getElementById('listings-pagination');
  if (!pagContainer) return;
  pagContainer.innerHTML = '';

  if (totalPages <= 1) return;

  const innerDiv = document.createElement('div');
  innerDiv.style.display = 'flex';
  innerDiv.style.gap = '0.5rem';
  innerDiv.style.justifyContent = 'center';
  innerDiv.style.alignItems = 'center';
  innerDiv.style.marginTop = '2rem';

  // Previous Button
  const prevBtn = document.createElement('button');
  prevBtn.className = `btn btn-secondary ${state.browsePage === 1 ? 'btn-disabled' : ''}`;
  prevBtn.style.padding = '0.5rem';
  prevBtn.innerHTML = '<i data-lucide="chevron-left" style="width: 16px; height: 16px;"></i>';
  prevBtn.disabled = state.browsePage === 1;
  prevBtn.addEventListener('click', () => {
    if (state.browsePage > 1) {
      state.browsePage--;
      renderBrowse(true);
    }
  });
  innerDiv.appendChild(prevBtn);

  // Page Numbers
  for (let i = 1; i <= totalPages; i++) {
    const pageBtn = document.createElement('button');
    pageBtn.className = `btn ${state.browsePage === i ? 'btn-primary' : 'btn-secondary'}`;
    pageBtn.style.padding = '0.5rem 1rem';
    pageBtn.style.fontSize = '0.85rem';
    pageBtn.innerText = i;
    pageBtn.addEventListener('click', () => {
      state.browsePage = i;
      renderBrowse(true);
    });
    innerDiv.appendChild(pageBtn);
  }

  // Next Button
  const nextBtn = document.createElement('button');
  nextBtn.className = `btn btn-secondary ${state.browsePage === totalPages ? 'btn-disabled' : ''}`;
  nextBtn.style.padding = '0.5rem';
  nextBtn.innerHTML = '<i data-lucide="chevron-right" style="width: 16px; height: 16px;"></i>';
  nextBtn.disabled = state.browsePage === totalPages;
  nextBtn.addEventListener('click', () => {
    if (state.browsePage < totalPages) {
      state.browsePage++;
      renderBrowse(true);
    }
  });
  innerDiv.appendChild(nextBtn);

  pagContainer.appendChild(innerDiv);
  lucide.createIcons();
}



// RENDER ADMIN AUDIT QUEUE
async function renderAdminQueue() {
  const container = document.getElementById('admin-page');
  container.classList.remove('hidden');

  // Load Platform Stats
  try {
    const statsRes = await fetch('/api/dashboard/stats');
    const statsData = await statsRes.json();
    if (statsRes.ok) {
      const stats = statsData.stats;
      document.getElementById('admin-stat-users').innerText = stats.activeUsers;
      document.getElementById('admin-stat-listings').innerText = stats.totalListings;
      document.getElementById('admin-stat-pending').innerText = stats.pendingReviews;

      // Draw Category Breakdown PieChart using Recharts UMD React
      if (stats.categoryBreakdown) {
        renderCategoryChart(stats.categoryBreakdown);
      }
    }
  } catch (err) {
    console.error("Failed to load admin stats:", err);
  }
  lucide.createIcons();
}

function renderCategoryChart(data) {
  const React = window.React;
  const ReactDOM = window.ReactDOM;
  const Recharts = window.Recharts;
  if (!React || !ReactDOM || !Recharts) {
    console.error("React/ReactDOM/Recharts UMD libraries are not loaded correctly.");
    return;
  }

  const { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } = Recharts;

  // Convert stats breakdown to array format
  const chartData = Object.keys(data).map(key => ({
    name: key,
    value: data[key]
  }));

  const COLORS = ['#3b82f6', '#f59e0b', '#10b981']; // Blue, Amber, Emerald

  const element = React.createElement(
    ResponsiveContainer,
    { width: '100%', height: 300 },
    React.createElement(
      PieChart,
      null,
      React.createElement(
        Pie,
        {
          data: chartData,
          cx: '50%',
          cy: '50%',
          innerRadius: 60,
          outerRadius: 80,
          paddingAngle: 5,
          dataKey: 'value',
          onClick: (entry) => {
            if (entry && entry.name) {
              window.handleCategoryFilter(entry.name);
            }
          },
          style: { cursor: 'pointer' }
        },
        chartData.map((entry, index) =>
          React.createElement(Cell, { key: `cell-${index}`, fill: COLORS[index % COLORS.length] })
        )
      ),
      React.createElement(Tooltip, {
        contentStyle: { background: '#090d16', border: '1px solid var(--border-muted)', borderRadius: '12px', color: '#fff', fontSize: '0.85rem' }
      }),
      React.createElement(Legend, { verticalAlign: 'bottom', height: 36 })
    )
  );

  const container = document.getElementById('admin-chart-container');
  if (container) {
    if (!window.reactRoot) {
      window.reactRoot = ReactDOM.createRoot(container);
    }
    window.reactRoot.render(element);
  }
}

// ADMIN FILTER CALLBACKS (Feature 2)
window.handleCategoryFilter = (category) => {
  if (state.adminCategoryFilter === category) {
    state.adminCategoryFilter = null;
  } else {
    state.adminCategoryFilter = category;
  }
  window.updateAdminFilterUI();
};

window.updateAdminFilterUI = () => {
  const indicator = document.getElementById('admin-category-filter-indicator');
  const badge = document.getElementById('admin-filtered-category-badge');
  if (indicator && badge) {
    if (state.adminCategoryFilter) {
      indicator.classList.remove('hidden');
      badge.innerText = state.adminCategoryFilter;
    } else {
      indicator.classList.add('hidden');
    }
  }
  renderAdminQueue();
};

// ADMIN APPROVE LISTING
async function handleApproveListing(id) {
  showLoader("Approving listing...");
  try {
    const response = await fetch(`/api/listings/${id}/approve`, { method: 'POST' });
    if (response.ok) {
      showAlert('success', 'Listing approved successfully! It is now live in the browse feed.');
      renderAdminQueue();
    } else {
      showAlert('danger', 'Failed to approve listing.');
    }
  } catch (err) {
    showAlert('danger', 'Server connection error.');
  } finally {
    hideLoader();
  }
}
window.handleApproveListing = handleApproveListing;

// ADMIN REJECT/DELETE LISTING
async function handleRejectListing(id) {
  if (!confirm("Are you sure you want to reject and permanently delete this listing?")) return;

  showLoader("Deleting listing...");
  try {
    const response = await fetch(`/api/listings/${id}`, { method: 'DELETE' });
    if (response.ok) {
      showAlert('success', 'Listing rejected and deleted.');
      renderAdminQueue();
    } else {
      showAlert('danger', 'Failed to delete listing.');
    }
  } catch (err) {
    showAlert('danger', 'Server connection error.');
  } finally {
    hideLoader();
  }
}
window.handleRejectListing = handleRejectListing;
// CREATE LISTING FORM HANDLERS
function resetCreateForm() {
  document.getElementById('create-listing-form').reset();
  state.editingListingId = null;
  // Reset Form titles
  document.querySelector('#create-page h2.auth-title').innerText = "Create New Listing";
  document.querySelector('#create-page p.auth-subtitle').innerText = "Add details about your car.";
  document.getElementById('create-submit-btn').innerText = "Publish Listing";
}

// CREATE / EDIT LISTING PUBLICATION
async function handleCreateListing(e) {
  e.preventDefault();
  const title = document.getElementById('create-title').value;
  const make = document.getElementById('create-make').value;
  const model = document.getElementById('create-model').value;
  const year = parseInt(document.getElementById('create-year').value);
  const mileage = parseInt(document.getElementById('create-mileage').value);
  const condition = document.getElementById('create-condition').value;
  const price = parseFloat(document.getElementById('create-price').value);
  const description = document.getElementById('create-desc').value;

  const isEdit = !!state.editingListingId;
  const method = isEdit ? 'PUT' : 'POST';
  const url = isEdit ? `/api/listings/${state.editingListingId}` : '/api/listings';
  const loaderMsg = isEdit ? "Updating listing details..." : "Submitting new listing...";

  showLoader(loaderMsg);
  try {
    const response = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, make, model, year, mileage, condition, price, description })
    });

    const data = await response.json();
    if (response.ok) {
      if (data.listing.status === 'PENDING_REVIEW') {
        showAlert('warning', isEdit ? 'Listing updated but was flagged by AI. It is held in the Admin Review Queue.' : 'Listing created but was flagged by AI. It is held in the Admin Review Queue.');
      } else {
        showAlert('success', isEdit ? 'Listing successfully updated!' : 'Listing successfully published and is now live!');
      }
      resetCreateForm();
      navigateTo('dashboard');
    } else {
      showAlert('danger', data.error || 'Failed to submit listing.');
    }
  } catch (err) {
    showAlert('danger', 'Server connection error.');
  } finally {
    hideLoader();
  }
}
// DEDICATED DETAIL PAGE RENDERER
async function renderListingDetail(listingId) {
  const page = document.getElementById('detail-page');
  page.classList.remove('hidden');

  const backText = document.getElementById('detail-back-text');
  if (backText) {
    if (state.detailBackPage === 'dashboard') {
      backText.innerText = "Back to Dashboard";
    } else {
      backText.innerText = "Back to Browse";
    }
  }

  try {
    const response = await fetch(`/api/listings/${listingId}`);
    const data = await response.json();

    if (response.ok) {
      const listing = data.listing;
      state.currentListingDetail = listing;

      // Populate basic details
      document.getElementById('detail-title').innerText = listing.title;
      document.getElementById('detail-price').innerText = `$${listing.price.toLocaleString()}`;
      document.getElementById('detail-date').innerText = new Date(listing.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
      document.getElementById('detail-description').innerText = listing.description;

      // Specs
      document.getElementById('detail-spec-year').innerText = listing.year;
      document.getElementById('detail-spec-mileage').innerText = `${listing.mileage.toLocaleString()} mi`;
      document.getElementById('detail-spec-condition').innerText = listing.condition;
      document.getElementById('detail-spec-category').innerText = listing.category;

      // Seller Info
      document.getElementById('detail-seller-name').innerText = listing.seller_name;
      document.getElementById('detail-seller-email').innerText = listing.seller_email;

      // Action buttons depending on ownership
      const sellerActions = document.getElementById('detail-seller-actions');
      if (sellerActions) {
        sellerActions.classList.add('hidden');
        if (state.user && (state.user.role === 'ADMIN' || listing.seller_id === state.user.id)) {
          sellerActions.classList.remove('hidden');
          sellerActions.style.display = 'flex';
        }
      }

      const buyerActions = document.getElementById('detail-buyer-actions');
      if (buyerActions) {
        buyerActions.classList.add('hidden');
        if (state.user && state.user.role === 'BUYER' && listing.seller_id !== state.user.id && listing.status === 'ACTIVE') {
          buyerActions.classList.remove('hidden');
          buyerActions.style.display = 'flex';
        }
      }

      renderRecommendationsDetail(data.similar_listings);
    }
  } catch (err) {
    console.error("Failed to load listing detail page:", err);
  }
  lucide.createIcons();
}
// TRUST ACCORDION SCORE VERIFICATION ACCORDION HELPERS (Feature 3)
window.updateDiagnosticReport = (listing) => {
  const diagPrice = document.getElementById('diag-price-check');
  const diagMileage = document.getElementById('diag-mileage-check');
  const diagSpam = document.getElementById('diag-spam-check');
  const diagSeller = document.getElementById('diag-seller-check');

  const setCheck = (el, isPassed, text) => {
    if (!el) return;
    el.innerHTML = isPassed
      ? `<i data-lucide="check-circle" style="color: var(--color-emerald); width: 14px; height: 14px; flex-shrink:0;"></i><span style="color: var(--text-secondary);">${text} (Passed)</span>`
      : `<i data-lucide="alert-triangle" style="color: var(--color-rose); width: 14px; height: 14px; flex-shrink:0;"></i><span style="color: var(--color-rose); font-weight: 600;">${text} (Anomaly Flagged)</span>`;
  };

  // 1. Price check
  const pricePassed = listing.trust_score >= 80;
  setCheck(diagPrice, pricePassed, "Pricing integrity verification");

  // 2. Odometer consistency check
  const age = 2026 - intVal(listing.year);
  const mileageAnomaly = age > 2 && (listing.mileage / age) < 800;
  setCheck(diagMileage, !mileageAnomaly, "Odometer rollback verification");

  // 3. Spam keywords
  let hasScamTerms = false;
  const scamKeywords = ['wire transfer', 'western union', 'moneygram', 'gift card', 'certified check', 'prepay', 'shipper'];
  if (listing.description) {
    const descLower = listing.description.toLowerCase();
    scamKeywords.forEach(k => {
      if (descLower.includes(k)) hasScamTerms = true;
    });
  }
  setCheck(diagSpam, !hasScamTerms, "Threat & fraud scanning");

  // 4. Seller check
  const sellerPassed = listing.trust_score >= 70;
  setCheck(diagSeller, sellerPassed, "Seller credentials check");

  lucide.createIcons();
};

// RENDER SIMILAR LISTINGS FOR DETAIL PAGE
function renderRecommendationsDetail(similar) {
  const grid = document.getElementById('detail-similar-grid');
  const section = document.getElementById('detail-similar-section');
  grid.innerHTML = '';

  if (!similar || similar.length === 0) {
    section.classList.add('hidden');
    return;
  }

  section.classList.remove('hidden');
  similar.forEach(item => {
    const card = document.createElement('div');
    card.className = 'glass-card similar-card';
    card.innerHTML = `
      <strong style="color: var(--text-primary); font-size: 0.95rem; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${item.title}</strong>
      <div style="font-size: 1.1rem; font-weight: 700; color: var(--color-secondary); margin-top: 0.25rem;">$${item.price.toLocaleString()}</div>
      <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.5rem; display: flex; gap: 0.5rem;">
        <span>${item.year}</span>
        <span>•</span>
        <span>${item.mileage.toLocaleString()} mi</span>
      </div>
    `;
    card.addEventListener('click', () => {
      window.navigateToDetail(item.id, state.detailBackPage);
    });
    grid.appendChild(card);
  });
}



// VIEW LISTING DETAILS MODAL (Fallback/Compat)
async function openListingModal(listingId) {
  window.navigateToDetail(listingId, 'browse');
}

function closeListingModal() {
  state.currentListingDetail = null;
}

// ALERTS HELPER
function showAlert(type, message) {
  const container = document.getElementById('global-alert-container');
  const alert = document.createElement('div');
  alert.className = `alert alert-${type}`;

  let icon = 'info';
  if (type === 'danger') icon = 'alert-triangle';
  else if (type === 'success') icon = 'check-circle';
  else if (type === 'warning') icon = 'alert-circle';

  alert.innerHTML = `
    <i data-lucide="${icon}"></i>
    <span>${message}</span>
  `;

  container.appendChild(alert);
  lucide.createIcons();

  // Auto remove alert after 5 seconds
  setTimeout(() => {
    alert.style.opacity = '0';
    alert.style.transition = 'opacity 0.5s ease';
    setTimeout(() => alert.remove(), 500);
  }, 5000);
}

function clearAlerts() {
  const container = document.getElementById('global-alert-container');
  if (container) container.innerHTML = '';
}

// LOADER UTILITIES
function showLoader(text) {
  const loader = document.getElementById('global-loader');
  const textEl = document.getElementById('global-loader-text');
  if (loader && textEl) {
    textEl.innerText = text || "Processing Secure Action...";
    loader.classList.remove('hidden');
  }
}

function hideLoader() {
  const loader = document.getElementById('global-loader');
  if (loader) loader.classList.add('hidden');
}

// UTILITIES
function intVal(val) {
  const num = parseInt(val);
  return isNaN(num) ? 0 : num;
}

async function handleMakeOffer() {
  const amountInput = document.getElementById('detail-offer-amount');
  if (!amountInput) return;
  const amount = parseFloat(amountInput.value);
  if (!amount || isNaN(amount) || amount <= 0) {
    showAlert('danger', 'Please enter a valid offer amount.');
    return;
  }
  
  showLoader("Submitting Offer...");
  try {
    const response = await fetch(`/api/listings/${state.currentListingId}/offer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount })
    });
    const data = await response.json();
    if (response.ok) {
      showAlert('success', 'Offer placed successfully!');
      amountInput.value = '';
      navigateTo('dashboard');
    } else {
      showAlert('danger', data.error || 'Failed to place offer.');
    }
  } catch (err) {
    showAlert('danger', 'Server connection error.');
  } finally {
    hideLoader();
  }
}

async function handleInstantBuy() {
  if (!confirm("Are you sure you want to purchase this car directly?")) return;
  
  showLoader("Initiating Checkout...");
  try {
    const response = await fetch('/api/checkout/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ listing_id: state.currentListingId })
    });
    const data = await response.json();
    if (response.ok) {
      showAlert('success', 'Purchase successful! Listing is now marked as SOLD.');
      navigateTo('dashboard');
    } else {
      showAlert('danger', data.error || 'Failed to process purchase.');
    }
  } catch (err) {
    showAlert('danger', 'Server connection error.');
  } finally {
    hideLoader();
  }
}

window.handleOfferCounter = async (offerId) => {
  const amountStr = prompt("Enter counter-offer amount ($):");
  if (!amountStr) return;
  const amount = parseFloat(amountStr);
  if (!amount || isNaN(amount) || amount <= 0) {
    alert("Please enter a valid positive counter-offer amount.");
    return;
  }

  showLoader("Sending Counter Offer...");
  try {
    const response = await fetch(`/api/offers/${offerId}/counter`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount })
    });
    const data = await response.json();
    if (response.ok) {
      showAlert('success', 'Counter-offer sent successfully!');
      renderDashboard();
    } else {
      showAlert('danger', data.error || 'Failed to send counter-offer.');
    }
  } catch (err) {
    showAlert('danger', 'Server connection error.');
  } finally {
    hideLoader();
  }
};

window.handleAcceptCounterAndPay = async (offerId, listingId) => {
  if (!confirm("Are you sure you want to accept this counter-offer and purchase the listing?")) return;

  showLoader("Processing Payment...");
  try {
    const response = await fetch('/api/checkout/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ listing_id: listingId })
    });
    const data = await response.json();
    if (response.ok) {
      showAlert('success', 'Purchase successful! Counter-offer accepted and payment processed.');
      renderDashboard();
    } else {
      showAlert('danger', data.error || 'Failed to process checkout.');
    }
  } catch (err) {
    showAlert('danger', 'Server connection error.');
  } finally {
    hideLoader();
  }
};

let _eventSource = null;

function connectNotificationStream() {
  if (_eventSource) {
    _eventSource.close();
    _eventSource = null;
  }

  if (!state.user) return;

  _eventSource = new EventSource('/api/notifications/stream');

  _eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'CONNECTED' || data.type === 'KEEPALIVE') {
        return;
      }
      
      // Show notification toast
      showNotificationToast(data);
      
      // If we are currently on the dashboard, reload the dashboard to show new offers/stats!
      if (state.currentPage === 'dashboard') {
        renderDashboard();
      }
    } catch (err) {
      console.error("Error handling notification message:", err);
    }
  };

  _eventSource.onerror = (err) => {
    console.error("EventSource failed, closing connection:", err);
    if (_eventSource) {
      _eventSource.close();
      _eventSource = null;
    }
    // Reconnect after 5 seconds
    setTimeout(connectNotificationStream, 5000);
  };
}

function showNotificationToast(notif) {
  const container = document.getElementById('activity-feed-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'glass-card toast-notification fade-in';
  toast.style.pointerEvents = 'auto';
  toast.style.padding = '1rem 1.25rem';
  toast.style.minWidth = '280px';
  toast.style.maxWidth = '360px';
  toast.style.borderLeft = '4px solid var(--color-gold)';
  toast.style.display = 'flex';
  toast.style.gap = '0.75rem';
  toast.style.alignItems = 'flex-start';
  toast.style.boxShadow = 'var(--shadow-gold)';

  toast.innerHTML = `
    <div style="color: var(--color-gold); margin-top: 0.15rem;">
      <i data-lucide="bell" style="width: 18px; height: 18px;"></i>
    </div>
    <div style="flex: 1;">
      <strong style="font-size: 0.9rem; color: var(--text-primary); display: block;">${notif.title}</strong>
      <span style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.2rem; display: block; line-height: 1.4;">${notif.message}</span>
    </div>
    <button onclick="this.parentElement.remove()" style="background: none; border: none; color: var(--text-muted); cursor: pointer; padding: 0; font-size: 1.1rem; line-height: 1;">&times;</button>
  `;

  container.appendChild(toast);
  
  if (typeof lucide !== 'undefined') {
    lucide.createIcons();
  }

  // Auto remove after 6 seconds
  setTimeout(() => {
    toast.style.animation = 'fadeOut 0.5s forwards';
    setTimeout(() => toast.remove(), 500);
  }, 6000);
}