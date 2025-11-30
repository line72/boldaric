class BoldaricApp extends HTMLElement {
  constructor() {
    super();
    this.token = sessionStorage.getItem('authToken');
    this.currentView = this.token ? 'stations' : 'login';
    this.stationId = null;
    this.currentStation = null;
    this.currentTrack = null;
  }

  connectedCallback() {
    this.render();
    this.setupEventListeners();
  }

  render() {
    this.innerHTML = `
      <div class="app-container">
        <header>
          <h1>Boldaric</h1>
          ${this.token ? '<div class="menu-container"><button id="menu-btn" class="menu-btn">☰</button><div id="menu-dropdown" class="menu-dropdown"><button id="logout-btn">Log Out</button></div></div>' : ''}
        </header>
        <main id="main-content">
          ${this.getViewTemplate()}
        </main>
      </div>
    `;
    
    // Setup menu toggle if menu exists
    if (this.token) {
      setTimeout(() => {
        const menuBtn = this.querySelector('#menu-btn');
        const menuDropdown = this.querySelector('#menu-dropdown');
        
        if (menuBtn && menuDropdown) {
          menuBtn.addEventListener('click', () => {
            menuDropdown.classList.toggle('show');
          });
          
          // Close menu when clicking outside
          document.addEventListener('click', (event) => {
            if (!menuBtn.contains(event.target) && !menuDropdown.contains(event.target)) {
              menuDropdown.classList.remove('show');
            }
          });
        }
      }, 0);
    }
  }

  getViewTemplate() {
    switch(this.currentView) {
      case 'login':
        return '<login-component></login-component>';
      case 'stations':
        return '<station-list></station-list>';
      case 'create-station':
        return '<station-create></station-create>';
      case 'edit-station':
        return `<station-edit station-id="${this.stationId}"></station-edit>`;
      case 'player':
        return `<player-component station-id="${this.stationId}"></player-component>`;
      default:
        return '<login-component></login-component>';
    }
  }

  navigateTo(view, data = {}) {
    this.currentView = view;
    if (data.station) this.currentStation = data.station;
    if (data.stationId) this.stationId = data.stationId;
    if (data.track) this.currentTrack = data.track;
    
    // Update token if we just logged in
    if (view !== 'login' && !this.token) {
      this.token = sessionStorage.getItem('authToken');
    }
    
    this.render();
    this.setupEventListeners();
  }

  logout() {
    sessionStorage.removeItem('authToken');
    this.token = null;
    this.currentView = 'login';
    this.stationId = null;
    this.currentStation = null;
    this.currentTrack = null;
    this.render();
  }

  setupEventListeners() {
    this.addEventListener('click', (event) => {
      if (event.target.id === 'logout-btn') {
        this.logout();
      }
    });
  }
}

customElements.define('boldaric-app', BoldaricApp);
