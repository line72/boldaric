class SearchModal extends HTMLElement {
  constructor() {
    super();
    this.searchResults = [];
  }

  connectedCallback() {
    this.render();
    this.setupEventListeners();
  }

  render() {
    this.innerHTML = `
      <div class="modal-overlay">
        <div class="search-modal">
          <div class="modal-header">
            <h3>Search for Songs</h3>
            <button id="close-modal" class="close-btn">×</button>
          </div>
          <div class="modal-content">
            <div class="search-form">
              <input type="text" id="search-input" placeholder="Enter artist and/or song title">
              <button id="search-submit">Search</button>
            </div>
            <div id="search-results" class="search-results">
              ${this.renderResults()}
            </div>
          </div>
        </div>
      </div>
    `;
  }

  renderResults() {
    if (this.searchResults.length === 0) {
      return '<div class="no-results">Enter search terms above</div>';
    }

    return `
      <div class="results-list">
        ${this.searchResults.map(song => `
          <div class="result-item" data-song-id="${song.id}">
            <div class="song-info">
              <strong>${song.artist}</strong> - ${song.title}
              <div class="album-info">${song.album}</div>
            </div>
            <button class="select-btn" data-song-id="${song.id}">Select</button>
          </div>
        `).join('')}
      </div>
    `;
  }

  setupEventListeners() {
    this.addEventListener('click', (event) => {
      if (event.target.id === 'close-modal') {
        this.remove();
      } else if (event.target.id === 'search-submit') {
        this.performSearch();
      } else if (event.target.classList.contains('select-btn')) {
        const songId = event.target.dataset.songId;
        this.dispatchEvent(new CustomEvent('song-selected', {
          detail: { songId }
        }));
        this.remove();
      }
    });

    this.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        this.remove();
      }
    });

    this.querySelector('#search-input').addEventListener('keypress', (event) => {
      if (event.key === 'Enter') {
        this.performSearch();
      }
    });
  }

  async performSearch() {
    const query = this.querySelector('#search-input').value.trim();
    if (!query) return;

    try {
      const parts = query.split(' ');
      const artist = parts[0] || '';
      const title = parts.slice(1).join(' ') || '';

      const response = await fetch(`/api/search?artist=${encodeURIComponent(artist)}&title=${encodeURIComponent(title)}`, {
        headers: {
          'Authorization': `Bearer ${sessionStorage.getItem('authToken')}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        // The search API returns a direct array of songs
        this.searchResults = Array.isArray(data) ? data : [];
        this.querySelector('#search-results').innerHTML = this.renderResults();
      } else if (response.status === 401) {
        // Unauthorized - redirect to login
        this.remove();
        document.querySelector('boldaric-app').navigateTo('login');
      }
    } catch (error) {
      console.error('Search error:', error);
    }
  }
}

customElements.define('search-modal', SearchModal);
