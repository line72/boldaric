class BoldaricApp extends HTMLElement {
  constructor() {
    super();
    this.token = sessionStorage.getItem('authToken');
    this.currentView = this.token ? 'stations' : 'login';
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
        return '<div>Station dashboard will go here</div>';
      default:
        return '<login-component></login-component>';
    }
  }

  navigateTo(view) {
    this.currentView = view;
    this.render();
  }

  logout() {
    sessionStorage.removeItem('authToken');
    this.token = null;
    this.navigateTo('login');
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
