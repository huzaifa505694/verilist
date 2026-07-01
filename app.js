// GLOBAL STATE
let state = {
  user: null,
  currentPage: null,
  listings: [],
  savedListings: [],
  currentListingDetail: null
};

// INITIALIZATION
document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  checkAuthSession();
});

// CHECK USER SESSION
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

// BIND DOM EVENTS
const def_events = [
  { id: 'nav-brand-logo', action: () => state.user ? navigateTo('dashboard') : navigateTo('landing') },
  { id: 'nav-login-btn', action: () => navigateTo('login') },
  { id: 'nav-register-btn', action: () => navigateTo('register') },
  { id: 'nav-browse-btn', action: () => navigateTo('browse') },
  { id: 'nav-saved-btn', action: () => navigateTo('saved') },
  { id: 'nav-logout-btn', action: handleLogout },
  { id: 'goto-register-btn', action: () => navigateTo('register') },
  { id: 'goto-login-btn', action: () => navigateTo('login') },
  { id: 'dash-action-btn', action: () => {
      if (state.user.role === 'SELLER') navigateTo('create');
      else if (state.user.role === 'ADMIN') navigateTo('admin');
      else navigateTo('browse');
    }
  },
  { id: 'create-cancel-btn', action: () => navigateTo('dashboard') },
  { id: 'modal-close-btn', action: closeListingModal },
  { id: 'apply-filters-btn', action: () => renderBrowse(true) },
  { id: 'reset-filters-btn', action: () => {
      document.getElementById('filter-search').value = '';
      document.getElementById('filter-make').value = '';
      document.getElementById('filter-condition').value = '';
      document.getElementById('filter-price-min').value = '';
      document.getElementById('filter-price-max').value = '';
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
  const aiEstBtn = document.getElementById('get-ai-estimate-btn');
  if (aiEstBtn) aiEstBtn.addEventListener('click', handleGetAIEstimate);

  // Modal actions
  const buyBtn = document.getElementById('modal-buy-now-btn');
  if (buyBtn) buyBtn.addEventListener('click', handleBuyListing);

  const offerBtn = document.getElementById('modal-make-offer-btn');
  if (offerBtn) offerBtn.addEventListener('click', handleMakeOffer);

  const deleteBtn = document.getElementById('modal-delete-btn');
  if (deleteBtn) deleteBtn.addEventListener('click', handleDeleteListing);

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

  // Dashboard Switch Role Button
  const toggleRoleBtn = document.getElementById('dash-toggle-role-btn');
  if (toggleRoleBtn) {
    toggleRoleBtn.addEventListener('click', () => {
      handleSwitchRole();
    });
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

  // Show/Hide Saved tab for buyers
  const savedBtn = document.getElementById('nav-saved-btn');
  if (state.user.role === 'BUYER') {
    savedBtn.classList.remove('hidden');
    savedBtn.style.display = '';
  } else {
    savedBtn.classList.add('hidden');
  }
}

function setupGuestUI() {
  document.getElementById('guest-nav-links').classList.remove('hidden');
  document.getElementById('auth-nav-links').classList.add('hidden');
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

// Fetched once from backend — set by initializeAndPromptGoogle()
let _googleClientId = null;
let _googleTokenClient = null;

/**
 * Called when user clicks the Google button.
 * 1. Fetches GOOGLE_CLIENT_ID from backend /api/config
 * 2. If configured → init GSI Token Client and request access token (real popup)
 * 3. If not configured → show setup instructions modal
 */
async function initializeAndPromptGoogle() {
  // Fetch Client ID from backend if we don't have it yet
  if (!_googleClientId) {
    try {
      const res = await fetch('/api/config/google');
      const cfg = await res.json();
      if (cfg.configured && cfg.client_id) {
        _googleClientId = cfg.client_id;
      } else {
        // Not configured — show setup modal
        document.getElementById('google-setup-modal').classList.add('active');
        return;
      }
    } catch (err) {
      showAlert('danger', 'Could not connect to server.');
      return;
    }
  }

  // Check that Google GSI library has loaded
  if (typeof google === 'undefined' || !google.accounts || !google.accounts.oauth2) {
    showAlert('warning', 'Google Sign-In is still loading. Please wait a moment and try again.');
    return;
  }

  if (!_googleTokenClient) {
    _googleTokenClient = google.accounts.oauth2.initTokenClient({
      client_id: _googleClientId,
      scope: 'https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email',
      callback: async (tokenResponse) => {
        if (tokenResponse.error) {
          showAlert('danger', `Google Sign-in failed: ${tokenResponse.error}`);
          return;
        }
        if (tokenResponse.access_token) {
          await handleGoogleAccessToken(tokenResponse.access_token);
        }
      },
    });
  }

  // Request token (opens real Google Account selection popup)
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

  // Configure Switch Role row
  const roleSwitchRow = document.getElementById('dash-role-switch-row');
  const toggleRoleBtnText = document.getElementById('dash-toggle-role-btn-text');
  if (state.user.role === 'ADMIN') {
    if (roleSwitchRow) roleSwitchRow.classList.add('hidden');
  } else {
    if (roleSwitchRow) {
      roleSwitchRow.classList.remove('hidden');
      roleSwitchRow.style.display = 'flex';
    }
    if (toggleRoleBtnText) {
      toggleRoleBtnText.innerText = state.user.role === 'BUYER' ? 'Switch to Seller' : 'Switch to Buyer';
    }
  }

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

  // Load stats and active offers
  const statsGrid = document.getElementById('dash-stats-grid');
  statsGrid.innerHTML = '<div class="loading-container" style="grid-column: 1/-1;"><div class="spinner"></div></div>';

  try {
    // 1. Fetch Stats
    const statsResponse = await fetch('/api/dashboard/stats');
    const statsData = await statsResponse.json();
    
    // 2. Fetch Offers
    const offersResponse = await fetch('/api/offers');
    const offersData = await offersResponse.json();

    if (statsResponse.ok) {
      const stats = statsData.stats;
      statsGrid.innerHTML = ''; // Clear spinner

      if (state.user.role === 'ADMIN') {
        statsGrid.innerHTML = `
          <div class="stat-card glass-card">
            <i data-lucide="alert-circle" style="color: var(--status-warning); width: 24px; height: 24px;"></i>
            <div class="stat-value">${stats.pendingReviews}</div>
            <div class="stat-label">Pending Reviews</div>
          </div>
          <div class="stat-card glass-card">
            <i data-lucide="users" style="color: var(--color-secondary); width: 24px; height: 24px;"></i>
            <div class="stat-value">${stats.activeUsers}</div>
            <div class="stat-label">Active Users</div>
          </div>
          <div class="stat-card glass-card">
            <i data-lucide="trending-up" style="color: var(--color-primary); width: 24px; height: 24px;"></i>
            <div class="stat-value">${stats.totalVolume}</div>
            <div class="stat-label">Total Volume</div>
          </div>
        `;
      } else if (state.user.role === 'SELLER') {
        statsGrid.innerHTML = `
          <div class="stat-card glass-card">
            <i data-lucide="shopping-bag" style="color: var(--color-secondary); width: 24px; height: 24px;"></i>
            <div class="stat-value">${stats.activeListings}</div>
            <div class="stat-label">Active Listings</div>
          </div>
          <div class="stat-card glass-card">
            <i data-lucide="eye" style="color: var(--color-primary); width: 24px; height: 24px;"></i>
            <div class="stat-value">${stats.listingViews}</div>
            <div class="stat-label">Listing Views</div>
          </div>
          <div class="stat-card glass-card">
            <i data-lucide="shield-check" style="color: var(--status-success); width: 24px; height: 24px;"></i>
            <div class="stat-value">${stats.trustRating}</div>
            <div class="stat-label">Seller Trust Rating</div>
          </div>
        `;
        
        // Render Offers received by Seller
        renderOffersSection(offersData.offers);
      } else { // BUYER
        statsGrid.innerHTML = `
          <div class="stat-card glass-card">
            <i data-lucide="shopping-bag" style="color: var(--color-primary); width: 24px; height: 24px;"></i>
            <div class="stat-value">${stats.savedListings}</div>
            <div class="stat-label">Saved Listings</div>
          </div>
          <div class="stat-card glass-card">
            <i data-lucide="shield-check" style="color: var(--color-secondary); width: 24px; height: 24px;"></i>
            <div class="stat-value">${stats.aiVerifiedChecks}</div>
            <div class="stat-label">AI Verified Checks</div>
          </div>
          <div class="stat-card glass-card">
            <i data-lucide="trending-up" style="color: var(--status-success); width: 24px; height: 24px;"></i>
            <div class="stat-value">${stats.activeOffers}</div>
            <div class="stat-label">Active Offers</div>
          </div>
        `;
        
        // Render Offers made by Buyer
        renderOffersSection(offersData.offers);
      }
    }
  } catch (err) {
    console.error("Failed to load dashboard statistics:", err);
    statsGrid.innerHTML = '<div style="color: var(--status-danger); text-align: center; grid-column: 1/-1;">Error loading statistics.</div>';
  }
  lucide.createIcons();
}

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

    let actionsHtml = '';
    if (state.user.role === 'SELLER' && o.status === 'PENDING') {
      actionsHtml = `
        <div style="display: flex; gap: 0.5rem;">
          <button class="btn btn-primary" onclick="handleOfferAction('${o.id}', 'ACCEPTED')" style="padding: 0.4rem 0.8rem; font-size: 0.8rem;">Accept</button>
          <button class="btn btn-secondary" onclick="handleOfferAction('${o.id}', 'REJECTED')" style="padding: 0.4rem 0.8rem; font-size: 0.8rem;">Reject</button>
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
          <span>Offer Amount: <strong style="color: var(--color-secondary); font-size: 0.9rem;">$${o.amount.toLocaleString()}</strong></span>
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

  const search = document.getElementById('filter-search').value;
  const make = document.getElementById('filter-make').value;
  const condition = document.getElementById('filter-condition').value;
  const priceMin = document.getElementById('filter-price-min').value;
  const priceMax = document.getElementById('filter-price-max').value;

  const grid = document.getElementById('listings-feed-grid');
  grid.innerHTML = '<div class="loading-container" style="grid-column: 1/-1;"><div class="spinner"></div></div>';

  try {
    // Build query params
    let url = '/api/listings?';
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

      if (listings.length === 0) {
        grid.innerHTML = '<p style="color: var(--text-muted); text-align: center; grid-column: 1/-1; padding: 3rem;">No active listings match your criteria.</p>';
        return;
      }

      // Fetch saved listings to show toggle state (only for logged-in buyers)
      let savedIds = [];
      if (state.user && state.user.role === 'BUYER') {
        const savedRes = await fetch('/api/listings/saved');
        if (savedRes.ok) {
          const savedData = await savedRes.json();
          savedIds = savedData.listings.map(l => l.id);
        }
      }

      listings.forEach(item => {
        const card = document.createElement('div');
        card.className = 'glass-card listing-card';
        card.style.cursor = 'pointer';
        
        // Trust badge classes
        let trustBadgeClass = 'badge-success';
        if (item.trust_score < 70) trustBadgeClass = 'badge-danger';
        else if (item.trust_score < 85) trustBadgeClass = 'badge-warning';

        // Heart save icon
        let heartIcon = 'heart';
        let heartStyle = 'color: var(--text-muted);';
        if (savedIds.includes(item.id)) {
          heartIcon = 'heart';
          heartStyle = 'fill: var(--status-danger); color: var(--status-danger);';
        }

        const buyerSaveHtml = (state.user && state.user.role === 'BUYER') 
          ? `<button class="btn btn-secondary" onclick="event.stopPropagation(); handleToggleSave('${item.id}');" style="padding: 0.5rem; border-radius: 50%;">
              <i data-lucide="${heartIcon}" style="${heartStyle} width: 16px; height: 16px;"></i>
             </button>`
          : '';

        card.innerHTML = `
          <div class="listing-image-placeholder" onclick="openListingModal('${item.id}')">
            <i data-lucide="car" style="width: 48px; height: 48px; opacity: 0.25;"></i>
            <div class="trust-badge-overlay">
              <span class="badge ${trustBadgeClass}">
                <i data-lucide="shield-check" style="width: 12px; height: 12px;"></i>
                <span>${item.trust_score}% Trust</span>
              </span>
            </div>
          </div>
          <div class="listing-content" onclick="openListingModal('${item.id}')">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem;">
              <h2 class="listing-title">${item.title}</h2>
              <div class="listing-price">$${item.price.toLocaleString()}</div>
            </div>
            
            <div class="listing-specs">
              <div class="listing-spec-item"><i data-lucide="calendar" style="width: 14px;"></i><span>${item.year}</span></div>
              <div class="listing-spec-item"><i data-lucide="gauge" style="width: 14px;"></i><span>${item.mileage.toLocaleString()} mi</span></div>
              <div class="listing-spec-item"><i data-lucide="star" style="width: 14px;"></i><span>${item.condition}</span></div>
            </div>
            
            <p class="listing-desc-excerpt">${item.description}</p>
            
            <div class="listing-footer">
              <span class="seller-tag">
                <i data-lucide="user" style="width: 14px; height: 14px;"></i>
                <span>${item.seller_name}</span>
              </span>
              ${buyerSaveHtml}
            </div>
          </div>
        `;
        grid.appendChild(card);
      });
    }
  } catch (err) {
    grid.innerHTML = '<div style="color: var(--status-danger); text-align: center; grid-column: 1/-1;">Error loading listings feed.</div>';
  }
  lucide.createIcons();
}

// TOGGLE SAVE LISTING
async function handleToggleSave(listingId) {
  try {
    const response = await fetch(`/api/listings/${listingId}/save`, { method: 'POST' });
    if (response.ok) {
      if (state.currentPage === 'saved') {
        renderSavedListings();
      } else {
        renderBrowse(true);
      }
    }
  } catch (err) {
    console.error("Save toggle failed:", err);
  }
}
window.handleToggleSave = handleToggleSave;

// RENDER SAVED LISTINGS (BUYER ONLY)
async function renderSavedListings() {
  const container = document.getElementById('browse-page');
  container.classList.remove('hidden');
  
  // Set title
  document.getElementById('browse-page-title').innerText = "My Saved Listings";
  
  // Hide filters panel on Saved page
  document.querySelector('.filter-panel').classList.add('hidden');

  const grid = document.getElementById('listings-feed-grid');
  grid.innerHTML = '<div class="loading-container" style="grid-column: 1/-1;"><div class="spinner"></div></div>';

  try {
    const response = await fetch('/api/listings/saved');
    const data = await response.json();

    if (response.ok) {
      grid.innerHTML = '';
      const listings = data.listings;
      
      if (listings.length === 0) {
        grid.innerHTML = '<p style="color: var(--text-muted); text-align: center; grid-column: 1/-1; padding: 3rem;">You haven\'t saved any listings yet.</p>';
        return;
      }

      listings.forEach(item => {
        const card = document.createElement('div');
        card.className = 'glass-card listing-card';
        card.style.cursor = 'pointer';
        
        let trustBadgeClass = 'badge-success';
        if (item.trust_score < 70) trustBadgeClass = 'badge-danger';
        else if (item.trust_score < 85) trustBadgeClass = 'badge-warning';

        card.innerHTML = `
          <div class="listing-image-placeholder" onclick="openListingModal('${item.id}')">
            <i data-lucide="car" style="width: 48px; height: 48px; opacity: 0.25;"></i>
            <div class="trust-badge-overlay">
              <span class="badge ${trustBadgeClass}">
                <i data-lucide="shield-check" style="width: 12px; height: 12px;"></i>
                <span>${item.trust_score}% Trust</span>
              </span>
            </div>
          </div>
          <div class="listing-content" onclick="openListingModal('${item.id}')">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem;">
              <h2 class="listing-title">${item.title}</h2>
              <div class="listing-price">$${item.price.toLocaleString()}</div>
            </div>
            
            <div class="listing-specs">
              <div class="listing-spec-item"><i data-lucide="calendar" style="width: 14px;"></i><span>${item.year}</span></div>
              <div class="listing-spec-item"><i data-lucide="gauge" style="width: 14px;"></i><span>${item.mileage.toLocaleString()} mi</span></div>
              <div class="listing-spec-item"><i data-lucide="star" style="width: 14px;"></i><span>${item.condition}</span></div>
            </div>
            
            <p class="listing-desc-excerpt">${item.description}</p>
            
            <div class="listing-footer">
              <span class="seller-tag">
                <i data-lucide="user" style="width: 14px; height: 14px;"></i>
                <span>${item.seller_name}</span>
              </span>
              <button class="btn btn-secondary" onclick="event.stopPropagation(); handleToggleSave('${item.id}');" style="padding: 0.5rem; border-radius: 50%;">
                <i data-lucide="heart" style="fill: var(--status-danger); color: var(--status-danger); width: 16px; height: 16px;"></i>
              </button>
            </div>
          </div>
        `;
        grid.appendChild(card);
      });
    }
  } catch (err) {
    grid.innerHTML = '<div style="color: var(--status-danger); text-align: center; grid-column: 1/-1;">Error loading saved listings.</div>';
  }
  lucide.createIcons();
}

// RENDER ADMIN AUDIT QUEUE
async function renderAdminQueue() {
  const container = document.getElementById('admin-page');
  container.classList.remove('hidden');

  const list = document.getElementById('admin-audit-list');
  list.innerHTML = '<div class="loading-container"><div class="spinner"></div></div>';

  try {
    const response = await fetch('/api/listings?status=PENDING_REVIEW');
    const data = await response.json();

    if (response.ok) {
      list.innerHTML = '';
      const listings = data.listings;

      if (listings.length === 0) {
        list.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 2rem;">No pending listings in the audit queue.</p>';
        return;
      }

      listings.forEach(o => {
        const item = document.createElement('div');
        item.className = 'glass-card audit-item';
        item.style.border = '1px solid var(--border-glow)';
        
        let flagsHtml = '';
        o.risk_flags.forEach(f => {
          flagsHtml += `<span class="badge badge-danger" style="margin-right: 0.25rem;">${f}</span>`;
        });

        item.innerHTML = `
          <div class="audit-details">
            <h3 style="font-size: 1.2rem;">${o.title}</h3>
            <p style="font-size: 0.9rem; color: var(--text-secondary); margin-top: 0.25rem;">${o.description}</p>
            <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.5rem;">
              <span>Asking Price: <strong>$${o.price.toLocaleString()}</strong></span>
              <span style="margin: 0 0.5rem;">|</span>
              <span>AI Estimate: <strong>$${o.predicted_price_min.toLocaleString()} - $${o.predicted_price_max.toLocaleString()}</strong></span>
              <span style="margin: 0 0.5rem;">|</span>
              <span>Seller: <strong>${o.seller_name} (${o.seller_email})</strong></span>
            </div>
            <div class="audit-flags" style="margin-top: 0.5rem;">
              <span class="badge badge-warning" style="margin-right: 0.5rem; font-weight: 700;">${o.trust_score}% Trust Score</span>
              ${flagsHtml}
            </div>
          </div>
          <div class="audit-actions">
            <button class="btn btn-primary" onclick="handleApproveListing('${o.id}')" style="padding: 0.6rem 1rem; font-size: 0.85rem;">Approve</button>
            <button class="btn btn-danger" onclick="handleRejectListing('${o.id}')" style="padding: 0.6rem 1rem; font-size: 0.85rem;">Reject & Delete</button>
          </div>
        `;
        list.appendChild(item);
      });
    }
  } catch (err) {
    list.innerHTML = '<p style="color: var(--status-danger); text-align: center;">Error loading review queue.</p>';
  }
  lucide.createIcons();
}

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
  const box = document.getElementById('ai-estimate-box');
  box.classList.add('hidden');
}

async function handleGetAIEstimate() {
  const year = document.getElementById('create-year').value;
  const make = document.getElementById('create-make').value;
  const model = document.getElementById('create-model').value;
  const mileage = document.getElementById('create-mileage').value;
  const condition = document.getElementById('create-condition').value;
  const price = parseFloat(document.getElementById('create-price').value);
  const description = document.getElementById('create-desc').value;

  if (!year || !make || !model || !mileage || !condition) {
    showAlert('warning', 'Please fill out Year, Make, Model, Mileage, and Condition before requesting AI estimation.');
    return;
  }

  showLoader("Consulting Pricing Regression Models...");
  try {
    const response = await fetch('/api/ai/estimate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ year, make, model, mileage, condition })
    });
    const data = await response.json();

    if (response.ok) {
      const box = document.getElementById('ai-estimate-box');
      box.classList.remove('hidden');

      const estPrice = Math.round((data.predicted_price_min + data.predicted_price_max) / 2);
      document.getElementById('ai-est-price').innerText = `$${estPrice.toLocaleString()}`;
      document.getElementById('ai-est-range').innerText = `$${data.predicted_price_min.toLocaleString()} - $${data.predicted_price_max.toLocaleString()}`;

      // Simulate a local Anomaly check to show verdict badge
      const badge = document.getElementById('ai-est-badge');
      const verdict = document.getElementById('ai-est-verdict');
      
      let isUnderpriced = false;
      if (price && price < (0.7 * data.predicted_price_min)) isUnderpriced = true;

      // Keywords check
      let hasScamTerms = false;
      const scamKeywords = ['wire transfer', 'western union', 'moneygram', 'gift card', 'certified check', 'prepay', 'shipper'];
      if (description) {
        const descLower = description.toLowerCase();
        scamKeywords.forEach(k => {
          if (descLower.includes(k)) hasScamTerms = true;
        });
      }

      // Check odometer rollback check
      let mileageAnomaly = false;
      const age = 2026 - intVal(year);
      if (age > 2 && (mileage / age) < 800) mileageAnomaly = true;

      if (isUnderpriced || hasScamTerms || mileageAnomaly) {
        badge.innerText = "FLAGGED / PENDING REVIEW";
        badge.className = "badge badge-danger";
        let text = "Listing contains anomalies: ";
        if (isUnderpriced) text += "asking price is suspiciously low. ";
        if (hasScamTerms) text += "suspicious terms in description. ";
        if (mileageAnomaly) text += "odometer rollback anomaly. ";
        text += "If published, this listing will go to the Admin Audit queue.";
        verdict.innerText = text;
      } else {
        badge.innerText = "PASSED / VERIFIED";
        badge.className = "badge badge-success";
        verdict.innerText = "Listing price and details conform to integrity guidelines. Listing will go live immediately on publication.";
      }
    }
  } catch (err) {
    showAlert('danger', 'AI estimate service is temporarily unavailable.');
  } finally {
    hideLoader();
  }
}

// CREATE LISTING PUBLICATION
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

  showLoader("Submitting listing...");
  try {
    const response = await fetch('/api/listings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, make, model, year, mileage, condition, price, description })
    });
    
    const data = await response.json();
    if (response.ok) {
      if (data.listing.status === 'PENDING_REVIEW') {
        showAlert('warning', 'Listing created but was flagged by AI. It is held in the Admin Review Queue.');
      } else {
        showAlert('success', 'Listing successfully published and is now live!');
      }
      navigateTo('dashboard');
    } else {
      showAlert('danger', data.error || 'Failed to publish listing.');
    }
  } catch (err) {
    showAlert('danger', 'Server connection error.');
  } finally {
    hideLoader();
  }
}

// VIEW LISTING DETAILS MODAL
async function openListingModal(listingId) {
  // Clear any inputs in modal
  document.getElementById('modal-offer-amount').value = '';

  const modal = document.getElementById('listing-detail-modal');
  modal.classList.add('active');

  try {
    const response = await fetch(`/api/listings/${listingId}`);
    const data = await response.json();

    if (response.ok) {
      const listing = data.listing;
      state.currentListingDetail = listing;

      // Populate basic details
      document.getElementById('modal-title').innerText = listing.title;
      document.getElementById('modal-price').innerText = `$${listing.price.toLocaleString()}`;
      document.getElementById('modal-date').innerText = new Date(listing.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
      document.getElementById('modal-description').innerText = listing.description;
      
      // Specs
      document.getElementById('modal-spec-year').innerText = listing.year;
      document.getElementById('modal-spec-mileage').innerText = `${listing.mileage.toLocaleString()} mi`;
      document.getElementById('modal-spec-condition').innerText = listing.condition;
      document.getElementById('modal-spec-category').innerText = listing.category;

      // Seller Info
      document.getElementById('modal-seller-name').innerText = listing.seller_name;
      document.getElementById('modal-seller-email').innerText = listing.seller_email;

      // AI Pricing verification
      document.getElementById('modal-ai-range').innerText = `$${listing.predicted_price_min.toLocaleString()} - $${listing.predicted_price_max.toLocaleString()}`;
      
      const aiBadge = document.getElementById('modal-ai-badge');
      aiBadge.innerText = `${listing.trust_score}% Trust`;
      aiBadge.className = 'badge';
      if (listing.trust_score < 70) aiBadge.classList.add('badge-danger');
      else if (listing.trust_score < 85) aiBadge.classList.add('badge-warning');
      else aiBadge.classList.add('badge-success');

      // Risk flags warnings
      const flagsBox = document.getElementById('modal-risk-flags-box');
      const flagsList = document.getElementById('modal-risk-flags-list');
      flagsList.innerHTML = '';
      if (listing.risk_flags && listing.risk_flags.length > 0) {
        flagsBox.classList.remove('hidden');
        listing.risk_flags.forEach(f => {
          const badge = document.createElement('span');
          badge.className = 'badge badge-danger';
          badge.style.alignSelf = 'flex-start';
          badge.innerText = f;
          flagsList.appendChild(badge);
        });
      } else {
        flagsBox.classList.add('hidden');
      }

      // Action buttons depending on user role & ownership
      const buyerActions = document.getElementById('modal-buyer-actions');
      const sellerActions = document.getElementById('modal-seller-actions');
      const buyBtn = document.getElementById('modal-buy-now-btn');

      buyerActions.classList.add('hidden');
      sellerActions.classList.add('hidden');

      if (state.user) {
        if (state.user.role === 'ADMIN' || listing.seller_id === state.user.id) {
          sellerActions.classList.remove('hidden');
        } else if (state.user.role === 'BUYER' && listing.status === 'ACTIVE') {
          buyerActions.classList.remove('hidden');
        }
      }

      // Check if Sold to disable buy button
      if (listing.status === 'SOLD') {
        buyBtn.innerText = "SOLD / TRANSACTION COMPLETE";
        buyBtn.className = "btn btn-disabled";
        buyBtn.disabled = true;
      } else {
        buyBtn.innerHTML = `<i data-lucide="shopping-bag"></i><span>Buy Now (Simulated Stripe)</span>`;
        buyBtn.className = "btn btn-primary";
        buyBtn.disabled = false;
      }

      // Render Recommendations (similar listings)
      renderRecommendations(data.similar_listings);
    }
  } catch (err) {
    console.error("Failed to load listing detail:", err);
  }
  lucide.createIcons();
}

function closeListingModal() {
  document.getElementById('listing-detail-modal').classList.remove('active');
  state.currentListingDetail = null;
}

// RENDER SIMILAR LISTINGS
function renderRecommendations(similar) {
  const grid = document.getElementById('modal-similar-grid');
  const section = document.getElementById('modal-similar-section');
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
      openListingModal(item.id);
    });
    grid.appendChild(card);
  });
}

// BUY LISTING (MOCK STRIPE PAYMENTS)
async function handleBuyListing() {
  if (!state.currentListingDetail) return;
  const listingId = state.currentListingDetail.id;

  showLoader("Connecting to Stripe Secure Gateway...");
  try {
    const response = await fetch('/api/checkout/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ listing_id: listingId })
    });
    const data = await response.json();

    if (response.ok) {
      showAlert('success', 'Stripe payment success! Transaction completed securely.');
      closeListingModal();
      navigateTo('dashboard');
    } else {
      showAlert('danger', data.error || 'Checkout failed.');
    }
  } catch (err) {
    showAlert('danger', 'Payment connection error.');
  } finally {
    hideLoader();
  }
}

// MAKE OFFER (BUYER)
async function handleMakeOffer() {
  if (!state.currentListingDetail) return;
  const listingId = state.currentListingDetail.id;
  const amount = document.getElementById('modal-offer-amount').value;

  if (!amount) {
    showAlert('warning', 'Please enter a bid amount.');
    return;
  }

  showLoader("Submitting bid...");
  try {
    const response = await fetch(`/api/listings/${listingId}/offer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount })
    });
    const data = await response.json();

    if (response.ok) {
      showAlert('success', 'Offer placed successfully! The seller has been notified.');
      closeListingModal();
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

// DELETE LISTING (SELLER/ADMIN)
async function handleDeleteListing() {
  if (!state.currentListingDetail) return;
  if (!confirm("Are you sure you want to permanently delete this listing?")) return;

  const listingId = state.currentListingDetail.id;
  showLoader("Deleting listing...");
  try {
    const response = await fetch(`/api/listings/${listingId}`, { method: 'DELETE' });
    if (response.ok) {
      showAlert('success', 'Listing deleted.');
      closeListingModal();
      if (state.currentPage === 'admin') {
        renderAdminQueue();
      } else {
        navigateTo('dashboard');
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
