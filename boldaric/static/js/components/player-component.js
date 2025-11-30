class PlayerComponent extends HTMLElement {
  static get observedAttributes() {
    return ['station-id'];
  }

  constructor() {
    super();
    this.stationId = null;
    this.currentTrack = null;
    this.isPlaying = false;
    this.eightyPercentSubmitted = false;
    this.nextTrack = null;
    this.trackSubmitted = false;
    this.isLoadingNextTrack = false;
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (name === 'station-id') {
      this.stationId = newValue;
    }
  }

  connectedCallback() {
    this.render();
    this.setupEventListeners();
    this.setupMediaSession();
    
    // Check if we have a current track from the app navigation
    const app = document.querySelector('boldaric-app');
    if (app && app.currentTrack) {
      this.loadTrack(app.currentTrack);
      // Auto-play the track
      setTimeout(() => {
        this.togglePlayPause();
      }, 100);
    }
  }

  render() {
    this.innerHTML = `
      <div class="player-container">
        <div class="player-header">
          <button id="back-btn" class="back-btn">←</button>
        </div>
        
        <div class="track-info">
          ${this.currentTrack ? `
            <img src="${this.currentTrack.cover_url}" alt="Album Art" class="album-art" onerror="this.style.display='none'">
            <div class="track-details">
              <h3>${this.currentTrack.title}</h3>
              <p class="artist">${this.currentTrack.artist}</p>
              <p class="album">${this.currentTrack.album}</p>
            </div>
          ` : '<div class="loading">Loading track...</div>'}
        </div>
        
        <div class="player-controls">
          <div class="progress-container">
            <span id="current-time">0:00</span>
            <input type="range" id="progress-bar" min="0" max="100" value="0">
            <span id="total-time">0:00</span>
          </div>
          
          <div class="control-buttons">
            <button id="thumbs-down" class="control-btn">👎</button>
            <button id="play-pause" class="control-btn play-pause">▶</button>
            <button id="thumbs-up" class="control-btn">👍</button>
          </div>
        </div>
        
        <audio id="audio-player"></audio>
      </div>
    `;
    
    // Re-attach event listeners after rendering
    this.setupEventListeners();
  }

  setupEventListeners() {
    // Remove any existing event listeners to prevent duplicates
    this.removeEventListener('click', this.handleGlobalClick);
    
    // Add event listeners
    this.addEventListener('click', this.handleGlobalClick.bind(this));

    const audio = this.querySelector('#audio-player');
    if (audio) {
      // Remove existing listeners to prevent duplicates
      audio.removeEventListener('timeupdate', this.updateProgress);
      audio.removeEventListener('ended', this.trackEnded);
      audio.removeEventListener('loadedmetadata', this.onMetadataLoaded);
      audio.removeEventListener('canplay', this.onCanPlay);
      audio.removeEventListener('play', this.onPlay);
      audio.removeEventListener('pause', this.onPause);
      
      // Add event listeners
      audio.addEventListener('timeupdate', this.updateProgress.bind(this));
      audio.addEventListener('ended', this.trackEnded.bind(this));
      audio.addEventListener('loadedmetadata', this.onMetadataLoaded.bind(this));
      audio.addEventListener('canplay', this.onCanPlay.bind(this));
      audio.addEventListener('play', this.onPlay.bind(this));
      audio.addEventListener('pause', this.onPause.bind(this));
    }
    
    const progressBar = this.querySelector('#progress-bar');
    if (progressBar) {
      // Remove existing listeners to prevent duplicates
      progressBar.removeEventListener('input', this.seek);
      progressBar.addEventListener('input', this.seek.bind(this));
    }
  }

  handleGlobalClick = (event) => {
    if (event.target.id === 'back-btn') {
      this.stopPlayback();
      document.querySelector('boldaric-app').navigateTo('stations');
    } else if (event.target.id === 'play-pause') {
      this.togglePlayPause();
    } else if (event.target.id === 'thumbs-up') {
      this.thumbsUp();
    } else if (event.target.id === 'thumbs-down') {
      this.thumbsDown();
    }
  }

  onPlay = () => {
    this.isPlaying = true;
    const playPauseBtn = this.querySelector('#play-pause');
    if (playPauseBtn) {
      playPauseBtn.textContent = '⏸';
    }
  }

  onPause = () => {
    this.isPlaying = false;
    const playPauseBtn = this.querySelector('#play-pause');
    if (playPauseBtn) {
      playPauseBtn.textContent = '▶';
    }
  }

  onMetadataLoaded = () => {
    const audio = this.querySelector('#audio-player');
    const totalTimeSpan = this.querySelector('#total-time');
    
    if (audio && totalTimeSpan) {
      totalTimeSpan.textContent = this.formatTime(audio.duration);
    }
  }

  onCanPlay = () => {
    const audio = this.querySelector('#audio-player');
    const totalTimeSpan = this.querySelector('#total-time');
    
    if (audio && totalTimeSpan) {
      totalTimeSpan.textContent = this.formatTime(audio.duration);
    }
  }

  setupMediaSession() {
    if ('mediaSession' in navigator && this.currentTrack) {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: this.currentTrack.title,
        artist: this.currentTrack.artist,
        album: this.currentTrack.album,
        artwork: this.currentTrack.cover_url ? [
          { src: this.currentTrack.cover_url, sizes: '512x512', type: 'image/jpeg' }
        ] : []
      });

      // Disable next/previous track controls
      navigator.mediaSession.setActionHandler('previoustrack', null);
      navigator.mediaSession.setActionHandler('nexttrack', null);
    }
  }

  loadTrack(track) {
    this.currentTrack = track;
    this.eightyPercentSubmitted = false;
    this.trackSubmitted = false;
    this.render();
    
    const audio = this.querySelector('#audio-player');
    if (audio) {
      audio.src = track.url;
      audio.load();
    }
    
    this.setupMediaSession();
  }

  togglePlayPause() {
    const audio = this.querySelector('#audio-player');
    const playPauseBtn = this.querySelector('#play-pause');
    
    if (!audio || !playPauseBtn) return;
    
    if (this.isPlaying) {
      audio.pause();
      playPauseBtn.textContent = '▶';
    } else {
      audio.play().catch(error => console.error('Play error:', error));
      playPauseBtn.textContent = '⏸';
    }
    
    this.isPlaying = !this.isPlaying;
  }

  updateProgress = () => {
    const audio = this.querySelector('#audio-player');
    const progressBar = this.querySelector('#progress-bar');
    const currentTimeSpan = this.querySelector('#current-time');
    const totalTimeSpan = this.querySelector('#total-time');
    
    if (!audio || !progressBar) return;
    
    const currentTime = audio.currentTime;
    const duration = audio.duration || 0;
    
    if (duration > 0) {
      const progress = (currentTime / duration) * 100;
      progressBar.value = progress;
      
      currentTimeSpan.textContent = this.formatTime(currentTime);
      totalTimeSpan.textContent = this.formatTime(duration);
      
      // Check if 80% completed and we haven't submitted yet
      if ((currentTime / duration) >= 0.8 && !this.eightyPercentSubmitted && !this.trackSubmitted) {
        this.markTrackAsListened();
        this.eightyPercentSubmitted = true;
      }
    }
  }

  formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  seek = () => {
    const audio = this.querySelector('#audio-player');
    const progressBar = this.querySelector('#progress-bar');
    
    if (!audio || !progressBar) return;
    
    const progress = progressBar.value;
    
    if (audio.duration) {
      audio.currentTime = (progress / 100) * audio.duration;
    }
  }

  async markTrackAsListened() {
    if (!this.currentTrack || !this.stationId || this.trackSubmitted) return;
    
    try {
      this.trackSubmitted = true;
      
      await fetch(`/api/station/${this.stationId}/${this.currentTrack.song_id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${sessionStorage.getItem('authToken')}`
        }
      });
      
      // Load next track in background
      this.loadNextTrack();
    } catch (error) {
      console.error('Error marking track as listened:', error);
      this.trackSubmitted = false;
    }
  }

  async thumbsUp() {
    if (!this.currentTrack || !this.stationId) return;
    
    try {
      const response = await fetch(`/api/station/${this.stationId}/${this.currentTrack.song_id}/thumbs_up`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionStorage.getItem('authToken')}`
        }
      });

      if (response.ok) {
        // Mark track as submitted but continue playing current song
        this.trackSubmitted = true;
        console.log('Track thumbs up recorded');
      }
    } catch (error) {
      console.error('Thumbs up error:', error);
    }
  }

  async thumbsDown() {
    console.log('thumbsDown');
    if (!this.currentTrack || !this.stationId) return;
    
    try {
      const response = await fetch(`/api/station/${this.stationId}/${this.currentTrack.song_id}/thumbs_down`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionStorage.getItem('authToken')}`
        }
      });

      if (response.ok) {
        // Mark track as submitted and load next track immediately
        this.trackSubmitted = true;
        this.loadNextTrack(true); // Force immediate play
      }
    } catch (error) {
      console.error('Thumbs down error:', error);
    }
  }

  async loadNextTrack(immediate = false) {
    if (!this.stationId || this.isLoadingNextTrack) return;
    
    this.isLoadingNextTrack = true;
    
    try {
      const response = await fetch(`/api/station/${this.stationId}`, {
        headers: {
          'Authorization': `Bearer ${sessionStorage.getItem('authToken')}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        if (data.tracks && data.tracks.length > 0) {
          if (immediate) {
            // Load and play the next track immediately
            this.loadTrack(data.tracks[0]);
            // Auto-play the next track
            setTimeout(() => {
              const playPauseBtn = this.querySelector('#play-pause');
              const audio = this.querySelector('#audio-player');
              if (playPauseBtn && audio) {
                audio.play().then(() => {
                  playPauseBtn.textContent = '⏸';
                  this.isPlaying = true;
                }).catch(console.error);
              }
            }, 100);
          } else {
            // Store the next track for when the current one ends
            this.nextTrack = data.tracks[0];
          }
        }
      }
    } catch (error) {
      console.error('Error loading next track:', error);
    } finally {
      this.isLoadingNextTrack = false;
    }
  }

  trackEnded = () => {
    // If we haven't submitted the track yet, submit it now
    if (!this.trackSubmitted && this.currentTrack && this.stationId) {
      this.markTrackAsListened();
    }
    
    // Play the next track if we have one
    if (this.nextTrack) {
      this.loadTrack(this.nextTrack);
      // Auto-play the next track
      setTimeout(() => {
        const playPauseBtn = this.querySelector('#play-pause');
        const audio = this.querySelector('#audio-player');
        if (playPauseBtn && audio) {
          audio.play().then(() => {
            playPauseBtn.textContent = '⏸';
            this.isPlaying = true;
          }).catch(console.error);
        }
      }, 100);
    } else {
      // If we don't have a next track, try to load one now
      this.loadNextTrack().then(() => {
        if (this.nextTrack) {
          this.loadTrack(this.nextTrack);
          // Auto-play the next track
          setTimeout(() => {
            const playPauseBtn = this.querySelector('#play-pause');
            const audio = this.querySelector('#audio-player');
            if (playPauseBtn && audio) {
              audio.play().then(() => {
                playPauseBtn.textContent = '⏸';
                this.isPlaying = true;
              }).catch(console.error);
            }
          }, 100);
        }
      });
    }
  }

  stopPlayback() {
    const audio = this.querySelector('#audio-player');
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }
    this.isPlaying = false;
  }
}

customElements.define('player-component', PlayerComponent);
