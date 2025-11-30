class StationCreate extends HTMLElement {
  constructor() {
    super();
    this.searchResults = [];
    this.selectedSeedSong = null;
  }

  connectedCallback() {
    this.render();
    this.setupEventListeners();
  }

  render() {
    this.innerHTML = `
      <div class="station-create-container">
        <h2>Create New Station</h2>
        <form id="create-station-form">
          <div class="form-group">
            <label for="station-name">Station Name:</label>
            <input type="text" id="station-name" required>
          </div>
          
          <div class="form-group">
            <label for="seed-song-search">Seed Song:</label>
            <input type="text" id="seed-song-search" placeholder="Search for a song..." required>
            <button type="button" id="search-btn">Search</button>
          </div>
          
          <div id="search-results" class="search-results">
            ${this.renderSearchResults()}
          </div>
          
          <div class="form-group">
            <label>
              <input type="checkbox" id="ignore-live">
              Ignore live recordings
            </label>
          </div>
          
          <div class="form-group">
            <label for="replay-cooldown">Replay Song Cooldown:</label>
            <input type="number" id="replay-cooldown" value="50" min="0">
          </div>
          
          <div class="form-group">
            <label for="artist-downrank">Artist Downrank (0.0 - 1.0):</label>
            <input type="number" id="artist-downrank" value="0.995" min="0" max="1" step="0.001">
          </div>
          
          <div class="form-actions">
            <button type="button" id="cancel-btn">Cancel</button>
            <button type="submit">Create Station</button>
          </div>
        </form>
      </div>
    `;
  }

  renderSearchResults() {
    if (this.searchResults.length === 0) {
      return '<div class="no-results">Search for songs above</div>';
    }

    return `
      <div class="results-list">
        ${this.searchResults.map(song => `
          <div class="search-result-item" data-song-id="${song.id}">
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
      if (event.target.id === 'search-btn') {
        this.searchSongs();
      } else if (event.target.id === 'cancel-btn') {
        document.querySelector('boldaric-app').navigateTo('stations');
      } else if (event.target.classList.contains('select-btn')) {
        const songId = event.target.dataset.songId;
        this.selectSeedSong(songId);
      }
    });

    this.querySelector('#create-station-form').addEventListener('submit', this.createStation.bind(this));
  }

  async searchSongs() {
    const query = this.querySelector('#seed-song-search').value.trim();
    if (!query) return;

    try {
      // Parse query into artist and title (simple split for now)
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
        this.searchResults = data.results || [];
        this.querySelector('#search-results').innerHTML = this.renderSearchResults();
      }
    } catch (error) {
      console.error('Search error:', error);
    }
  }

  selectSeedSong(songId) {
    this.selectedSeedSong = songId;
    // Highlight selected song
    this.querySelectorAll('.search-result-item').forEach(item => {
      item.classList.toggle('selected', item.dataset.songId === songId);
    });
  }

  async createStation(event) {
    event.preventDefault();
    
    if (!this.selectedSeedSong) {
      alert('Please select a seed song');
      return;
    }

    const stationName = this.querySelector('#station-name').value.trim();
    const ignoreLive = this.querySelector('#ignore-live').checked;
    const replayCooldown = parseInt(this.querySelector('#replay-cooldown').value) || 50;
    const artistDownrank = parseFloat(this.querySelector('#artist-downrank').value) || 0.995;

    try {
      const response = await fetch('/api/stations', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionStorage.getItem('authToken')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          station_name: stationName,
          song_id: this.selectedSeedSong,
          replay_song_cooldown: replayCooldown,
          replay_artist_downrank: artistDownrank,
          ignore_live: ignoreLive
        })
      });

      if (response.ok) {
        const data = await response.json();
        // Navigate to player with the initial track
        document.querySelector('boldaric-app').navigateTo('player', {
          station: data.station,
          track: data.track
        });
      } else {
        const error = await response.json();
        alert(`Error creating station: ${error.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Create station error:', error);
      alert('Network error creating station');
    }
  }
}

customElements.define('station-create', StationCreate);
