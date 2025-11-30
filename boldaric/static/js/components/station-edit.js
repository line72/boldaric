class StationEdit extends HTMLElement {
  static get observedAttributes() {
    return ['station-id'];
  }

  constructor() {
    super();
    this.stationId = null;
    this.station = null;
    this.loading = true;
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (name === 'station-id') {
      this.stationId = newValue;
      this.loadStation();
    }
  }

  async loadStation() {
    try {
      const response = await fetch(`/api/station/${this.stationId}/info`, {
        headers: {
          'Authorization': `Bearer ${sessionStorage.getItem('authToken')}`
        }
      });

      if (response.ok) {
        this.station = await response.json();
        this.loading = false;
        this.render();
      } else if (response.status === 401) {
        // Unauthorized - redirect to login
        document.querySelector('boldaric-app').navigateTo('login');
      }
    } catch (error) {
      console.error('Error loading station:', error);
    }
  }

  render() {
    if (this.loading) {
      this.innerHTML = '<div class="loading">Loading station...</div>';
      return;
    }

    this.innerHTML = `
      <div class="station-edit-container">
        <div class="station-edit-header">
          <button id="back-btn" class="back-btn">←</button>
          <h2>Edit Station: ${this.station.name}</h2>
        </div>
        <form id="edit-station-form">
          <div class="form-group">
            <label>
              <input type="checkbox" id="ignore-live" ${this.station.ignore_live ? 'checked' : ''}>
              Ignore live recordings
            </label>
          </div>
          
          <div class="form-group">
            <label for="replay-cooldown">Replay Song Cooldown:</label>
            <input type="number" id="replay-cooldown" value="${this.station.replay_song_cooldown}" min="0">
          </div>
          
          <div class="form-group">
            <label for="artist-downrank">Artist Downrank (0.0 - 1.0):</label>
            <input type="number" id="artist-downrank" value="${this.station.replay_artist_downrank}" min="0" max="1" step="0.001">
          </div>
          
          <div class="form-actions">
            <button type="submit">Save Changes</button>
          </div>
        </form>
        
        <div class="seed-songs-section">
          <h3>Seed Songs</h3>
          <button id="add-seed-btn">Add Seed Song</button>
          <div id="seed-songs-list">
            <!-- Seed songs will be loaded here -->
          </div>
        </div>
      </div>
    `;

    this.setupEventListeners();
  }

  setupEventListeners() {
    this.addEventListener('click', (event) => {
      if (event.target.id === 'back-btn') {
        document.querySelector('boldaric-app').navigateTo('stations');
      } else if (event.target.id === 'add-seed-btn') {
        this.showSearchModal();
      }
    });

    this.querySelector('#edit-station-form').addEventListener('submit', this.saveChanges.bind(this));
  }

  async saveChanges(event) {
    event.preventDefault();

    // Get current values directly from the form elements without parsing
    const replayCooldown = parseInt(this.querySelector('#replay-cooldown').value);
    const artistDownrank = parseFloat(this.querySelector('#artist-downrank').value);
    const ignoreLive = this.querySelector('#ignore-live').checked;

    try {
      const response = await fetch(`/api/station/${this.stationId}/info`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${sessionStorage.getItem('authToken')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          replay_song_cooldown: replayCooldown,
          replay_artist_downrank: artistDownrank,
          ignore_live: ignoreLive
        })
      });

      if (response.ok) {
        document.querySelector('boldaric-app').navigateTo('stations');
      } else if (response.status === 401) {
        // Unauthorized - redirect to login
        document.querySelector('boldaric-app').navigateTo('login');
      }
    } catch (error) {
      console.error('Save error:', error);
    }
  }

  showSearchModal() {
    // Create and show search modal for adding seed songs
    const modal = document.createElement('search-modal');
    modal.addEventListener('song-selected', (event) => {
      this.addSeedSong(event.detail.songId);
    });
    document.body.appendChild(modal);
  }

  async addSeedSong(songId) {
    try {
      const response = await fetch(`/api/station/${this.stationId}/seed`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionStorage.getItem('authToken')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ song_id: songId })
      });

      if (response.ok) {
        // No alert needed
      } else if (response.status === 401) {
        // Unauthorized - redirect to login
        document.querySelector('boldaric-app').navigateTo('login');
      }
    } catch (error) {
      console.error('Add seed error:', error);
    }
  }
}

customElements.define('station-edit', StationEdit);
