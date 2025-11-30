class LoginComponent extends HTMLElement {
  constructor() {
    super();
    this.innerHTML = `
      <div class="login-container">
        <h2>Login to Boldaric</h2>
        <form id="login-form">
          <div class="form-group">
            <label for="username">Username:</label>
            <input type="text" id="username" required>
          </div>
          <button type="submit">Login</button>
        </form>
        <div id="login-error" class="error-message"></div>
      </div>
    `;
  }

  connectedCallback() {
    this.querySelector('#login-form').addEventListener('submit', this.handleLogin.bind(this));
  }

  async handleLogin(event) {
    event.preventDefault();
    const username = this.querySelector('#username').value.trim();
    
    if (!username) return;

    try {
      const response = await fetch('/api/auth', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ login: username })
      });

      if (response.ok) {
        const data = await response.json();
        sessionStorage.setItem('authToken', data.token);
        document.querySelector('boldaric-app').navigateTo('stations');
      } else {
        this.showError('Invalid username or server error');
      }
    } catch (error) {
      this.showError('Network error. Please try again.');
    }
  }

  showError(message) {
    this.querySelector('#login-error').textContent = message;
  }
}

customElements.define('login-component', LoginComponent);
