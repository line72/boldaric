class BoldaricApp extends HTMLElement {
  constructor() {
    super();
    this.token = sessionStorage.getItem('authToken');
    this.currentView = this.token ? 'stations' : 'login';
    this.stationId = null;
  }

  connectedCallback() {
    this.render();
    this.setupEventListeners();
  }

  render() {
    this.innerHTML = `
      <div class="app-container">
        <header>
          <h1>Boldaric Music Player</h1>
          ${this.token ? '<button id="logout-btn">Logout</button>' : ''}
        </header>
        <main id="main-content">
          ${this.getViewTemplate()}
        </main>
      </div>
    `;
  }

  getViewTemplate() {
    switch(this.currentView) {
      case 'login':
        return '<login-component></login-component>';
      case 'stations':
        return '<station-list></station-list>';
      case 'create-station':
        return '<station-create></station-create>';
      default:
        return '<login-component></login-component>';
    }
  }

  navigateTo(view, data = {}) {
    this.currentView = view;
    if (data.stationId) this.stationId = data.stationId;
    this.render();
  }

  logout() {
    sessionStorage.removeItem('authToken');
    this.token = null;
    this.currentView = 'login';
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
