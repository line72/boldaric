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
    
    // Focus the station name input by default
    setTimeout(() => {
      const stationNameInput = this.querySelector('#station-name');
      if (stationNameInput) {
        stationNameInput.focus();
      }
    }, 100);
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
            <div class="input-with-button">
              <input type="text" id="seed-song-search" placeholder="Search for a song...">
              <button type="button" id="search-btn">🔍</button>
            </div>
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
              <strong>${song.artist}</strong>
              <div class="album-info">${song.title} • ${song.album}</div>
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
          this.createStation(event);
        });
      }

      const searchBtn = this.querySelector('#search-btn');
      if (searchBtn) {
        searchBtn.addEventListener('click', (event) => {
          event.preventDefault();
          this.searchSongs();
        });
      }

      const seedSongInput = this.querySelector('#seed-song-search');
      if (seedSongInput) {
        seedSongInput.addEventListener('keypress', (event) => {
          if (event.key === 'Enter') {
            event.preventDefault();
            this.searchSongs();
          }
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

  saveFormValues() {
    // Save current form values before re-rendering
    const stationNameInput = this.querySelector('#station-name');
    const ignoreLiveInput = this.querySelector('#ignore-live');
    const replayCooldownInput = this.querySelector('#replay-cooldown');
    const artistDownrankInput = this.querySelector('#artist-downrank');
    
    if (stationNameInput) {
      this.formValues.stationName = stationNameInput.value;
    }
    
    if (ignoreLiveInput) {
      this.formValues.ignoreLive = ignoreLiveInput.checked;
    }
    
    if (replayCooldownInput) {
      this.formValues.replayCooldown = replayCooldownInput.value;
    }
    
    if (artistDownrankInput) {
      this.formValues.artistDownrank = artistDownrankInput.value;
    }
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
        
        // Update only the search results section instead of re-rendering everything
        const searchResultsContainer = this.querySelector('#search-results');
        if (searchResultsContainer) {
          searchResultsContainer.innerHTML = this.renderSearchResults();
        }
      } else {
        console.error('Search failed with status:', response.status);
      }
    } catch (error) {
      console.error('Search error:', error);
    }
  }

  selectSeedSong(songId) {
    this.selectedSeedSong = songId;
    
    // Save form values before updating the UI
    this.saveFormValues();
    
    // Update only the selected seed section instead of re-rendering everything
    const form = this.querySelector('#create-station-form');
    if (form) {
      const selectedSeedSection = form.querySelector('.selected-seed');
      if (selectedSeedSection) {
        selectedSeedSection.remove();
      }
      
      if (this.selectedSeedSong) {
        const newSelectedSeedSection = document.createElement('div');
        newSelectedSeedSection.className = 'selected-seed';
        newSelectedSeedSection.innerHTML = `
          <h4>Selected Seed Song:</h4>
          <p>${this.getSelectedSongInfo()}</p>
        `;
        
        // Insert after the search results
        const searchResults = form.querySelector('#search-results');
        if (searchResults) {
          searchResults.after(newSelectedSeedSection);
        }
      }
      
      // Update the search results to show the selected state
      const searchResultsContainer = form.querySelector('#search-results');
      if (searchResultsContainer) {
        searchResultsContainer.innerHTML = this.renderSearchResults();
      }
    }
  }

  async createStation(event) {
    event.preventDefault();
    event.stopPropagation();
    
    // Validate that a seed song is selected
    if (!this.selectedSeedSong) {
      alert('Please select a seed song');
      return;
    }

    // Save form values one more time before submitting
    this.saveFormValues();

    // Get current form values
    const stationName = this.formValues.stationName || this.querySelector('#station-name').value.trim();
    const ignoreLive = this.formValues.ignoreLive || this.querySelector('#ignore-live').checked;
    const replayCooldown = parseInt(this.formValues.replayCooldown) || parseInt(this.querySelector('#replay-cooldown').value) || 50;
    const artistDownrank = parseFloat(this.formValues.artistDownrank) || parseFloat(this.querySelector('#artist-downrank').value) || 0.995;

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
