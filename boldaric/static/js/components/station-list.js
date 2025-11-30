class StationList extends HTMLElement {
  constructor() {
    super();
    this.stations = [];
    this.loading = true;
  }

  async connectedCallback() {
    await this.loadStations();
    this.render();
    this.setupEventListeners();
  }

  async loadStations() {
    try {
      const response = await fetch('/api/stations', {
        headers: {
          'Authorization': `Bearer ${sessionStorage.getItem('authToken')}`
        }
      });

      if (response.ok) {
        this.stations = await response.json();
      } else if (response.status === 401) {
        // Unauthorized - redirect to login
        document.querySelector('boldaric-app').navigateTo('login');
      }
    } catch (error) {
      console.error('Error loading stations:', error);
    } finally {
      this.loading = false;
    }
  }

  render() {
    this.innerHTML = `
      <div class="station-list-container">
        <div class="station-header">
          <h2>Your Stations</h2>
          <button id="create-station-btn" class="primary-btn">Create New Station</button>
        </div>
        ${this.loading ? '<div class="loading">Loading stations...</div>' : this.renderStations()}
      </div>
    `;
  }

  renderStations() {
    if (this.stations.length === 0) {
      return '<div class="no-stations">No stations found. Create your first station!</div>';
    }

    return `
      <div class="stations-grid">
        ${this.stations.map(station => `
          <div class="station-card" data-station-id="${station.id}">
            <h3>${station.name}</h3>
            <div class="station-options">
              <span>Cooldown: ${station.replay_song_cooldown}</span>
              <span>Downrank: ${station.replay_artist_downrank}</span>
              <span>Ignore Live: ${station.ignore_live ? 'Yes' : 'No'}</span>
            </div>
            <div class="station-actions">
              <button class="play-btn" data-station-id="${station.id}">Play</button>
              <button class="edit-btn" data-station-id="${station.id}">Edit</button>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  setupEventListeners() {
    this.addEventListener('click', (event) => {
      if (event.target.id === 'create-station-btn') {
        document.querySelector('boldaric-app').navigateTo('create-station');
      } else if (event.target.classList.contains('play-btn')) {
        const stationId = event.target.dataset.stationId;
        this.playStation(stationId);
      } else if (event.target.classList.contains('edit-btn')) {
        const stationId = event.target.dataset.stationId;
        document.querySelector('boldaric-app').navigateTo('edit-station', { stationId });
      }
    });
  }

  async playStation(stationId) {
    // Get the first track to play
    try {
      const response = await fetch(`/api/station/${stationId}`, {
        headers: {
          'Authorization': `Bearer ${sessionStorage.getItem('authToken')}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        const firstTrack = data.tracks[0];
        document.querySelector('boldaric-app').navigateTo('player', {
          stationId: stationId,
          track: firstTrack
        });
      } else if (response.status === 401) {
        // Unauthorized - redirect to login
        document.querySelector('boldaric-app').navigateTo('login');
      }
    } catch (error) {
      console.error('Error starting station:', error);
    }
  }
}

customElements.define('station-list', StationList);
