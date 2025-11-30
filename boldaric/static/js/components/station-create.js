class StationCreate extends HTMLElement {
  constructor() {
    super();
    this.searchResults = [];
    this.selectedSeedSong = null;
    // Store form field values to prevent them from being cleared
    this.formValues = {
      stationName: '',
      ignoreLive: false,
      replayCooldown: 50,
      artistDownrank: 0.995
    };
  }

  connectedCallback() {
    this.render();
    this.setupEventListeners();
    // Restore form values if they exist
    this.restoreFormValues();
  }

  render() {
    this.innerHTML = `
      <div class="station-create-container">
        <h2>Create New Station</h2>
        <form id="create-station-form">
          <div class="form-group">
            <label for="station-name">Station Name:</label>
            <input type="text" id="station-name" value="${this.formValues.stationName}" required>
          </div>
          
          <div class="form-group">
            <label for="seed-song-search">Seed Song:</label>
            <input type="text" id="seed-song-search" placeholder="Search for a song...">
            <button type="button" id="search-btn">Search</button>
          </div>
          
          <div id="search-results" class="search-results">
            ${this.renderSearchResults()}
          </div>
          
          ${this.selectedSeedSong ? `<div class="selected-seed">
            <h4>Selected Seed Song:</h4>
            <p>${this.getSelectedSongInfo()}</p>
          </div>` : ''}
          
          <div class="form-group">
            <label>
              <input type="checkbox" id="ignore-live" ${this.formValues.ignoreLive ? 'checked' : ''}>
              Ignore live recordings
            </label>
          </div>
          
          <div class="form-group">
            <label for="replay-cooldown">Replay Song Cooldown:</label>
            <input type="number" id="replay-cooldown" value="${this.formValues.replayCooldown}" min="0">
          </div>
          
          <div class="form-group">
            <label for="artist-downrank">Artist Downrank (0.0 - 1.0):</label>
            <input type="number" id="artist-downrank" value="${this.formValues.artistDownrank}" min="0" max="1" step="0.001">
          </div>
          
          <div class="form-actions">
            <button type="button" id="cancel-btn">Cancel</button>
            <button type="submit" id="create-station-submit">Create Station</button>
          </div>
        </form>
      </div>
    `;
  }

  getSelectedSongInfo() {
    if (!this.selectedSeedSong) return '';
    
    const selectedSong = this.searchResults.find(song => song.id === this.selectedSeedSong);
    if (selectedSong) {
      return `${selectedSong.artist} - ${selectedSong.title} (${selectedSong.album})`;
    }
    return 'Selected song';
  }

  renderSearchResults() {
    if (this.searchResults.length === 0) {
      return '<div class="no-results">Search for songs above</div>';
    }

    return `
      <div class="results-list">
        ${this.searchResults.map(song => `
          <div class="search-result-item ${song.id === this.selectedSeedSong ? 'selected' : ''}" data-song-id="${song.id}">
            <div class="song-info">
              <strong>${song.artist}</strong> - ${song.title}
              <div class="album-info">${song.album}</div>
            </div>
            <button class="select-btn" data-song-id="${song.id}">
              ${song.id === this.selectedSeedSong ? 'Selected' : 'Select'}
            </button>
          </div>
        `).join('')}
      </div>
    `;
  }

  setupEventListeners() {
    // Use setTimeout to ensure DOM is fully rendered before attaching listeners
    setTimeout(() => {
      const form = this.querySelector('#create-station-form');
      if (form) {
        form.addEventListener('submit', (event) => {
          console.log('Form submit event triggered');
          this.createStation(event);
        });
      }

      const searchBtn = this.querySelector('#search-btn');
      if (searchBtn) {
        searchBtn.addEventListener('click', () => {
          this.searchSongs();
        });
      }

      const cancelBtn = this.querySelector('#cancel-btn');
      if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
          document.querySelector('boldaric-app').navigateTo('stations');
        });
      }

      // Add event listeners for select buttons
      this.addEventListener('click', (event) => {
        if (event.target.classList.contains('select-btn')) {
          const songId = event.target.dataset.songId;
          this.selectSeedSong(songId);
        }
      });
    }, 0);
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
        // The search API returns a direct array of songs
        this.searchResults = Array.isArray(data) ? data : [];
        this.querySelector('#search-results').innerHTML = this.renderSearchResults();
      } else {
        console.error('Search failed with status:', response.status);
      }
    } catch (error) {
      console.error('Search error:', error);
    }
  }

  selectSeedSong(songId) {
    this.selectedSeedSong = songId;
    this.render();
    // Re-attach event listeners after re-rendering
    this.setupEventListeners();
  }

  async createStation(event) {
    console.log('createStation called');
    event.preventDefault();
    event.stopPropagation();
    
    // Validate that a seed song is selected
    if (!this.selectedSeedSong) {
      alert('Please select a seed song');
      return;
    }

    // Validate that station name is provided
    const stationName = this.querySelector('#station-name').value.trim();
    if (!stationName) {
      alert('Please enter a station name');
      return;
    }

    // Get current form values directly from the form elements to ensure we have the latest values
    // This ensures we get the value even if the user hasn't tabbed out of the field
    const ignoreLive = this.querySelector('#ignore-live')?.checked || false;
    const replayCooldown = parseInt(this.querySelector('#replay-cooldown')?.value) || 50;
    const artistDownrank = parseFloat(this.querySelector('#artist-downrank')?.value) || 0.995;

    console.log('Form values:', { stationName, ignoreLive, replayCooldown, artistDownrank });

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
          stationId: data.station.id,
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
