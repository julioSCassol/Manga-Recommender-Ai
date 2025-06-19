const mangaContainer = document.getElementById('manga-container');
const personalizedContainer = document.getElementById('personalized-container');
const loadingElement = document.getElementById('loading');
const refreshButton = document.getElementById('refresh-btn');
const modal = document.getElementById('manga-modal');
const modalContent = document.getElementById('modal-content');
const closeModal = document.querySelector('.close');
const preferenceForm = document.getElementById('preference-form');
const questionnaireSection = document.getElementById('questionnaire-section');
const recommendationsSection = document.getElementById('recommendations-section');
const topMangaSection = document.getElementById('top-manga-section');
const questionnaireBtn = document.getElementById('questionnaire-btn');
const closeQuestionnaireBtn = document.getElementById('close-questionnaire');

let likedMangaIds = new Set();
let currentSessionId = null;
let topMangaData = [];
let personalizedData = [];

console.log("Frontend initialized");

async function initApp() {
    console.log("Initializing application...");
    await loadTopManga();
    setupEventListeners();
}

async function loadTopManga() {
    try {
        loadingElement.style.display = 'block';
        const response = await fetch('/api/top-manga');
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }

        topMangaData = data.top_manga;
        console.log("Received top manga data:", topMangaData);
        displayManga(topMangaData, mangaContainer);
        loadingElement.style.display = 'none';
    } catch (error) {
        console.error("Error loading top manga:", error);
        loadingElement.innerHTML = `
            <p class="error">Error: ${error.message}</p>
            <button onclick="location.reload()">Retry</button>
        `;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const ratingSlider = document.getElementById('min-rating');
    const ratingValue = document.getElementById('rating-value');
    
    if (ratingSlider && ratingValue) {
        ratingValue.textContent = ratingSlider.value;
        
        ratingSlider.addEventListener('input', () => {
            ratingValue.textContent = ratingSlider.value;
        });
    }
});

function setupEventListeners() {
    questionnaireBtn.addEventListener('click', () => {
        topMangaSection.style.display = 'none';
        recommendationsSection.style.display = 'none';
        questionnaireSection.style.display = 'block';
    });
    
    closeQuestionnaireBtn.addEventListener('click', () => {
        questionnaireSection.style.display = 'none';
        topMangaSection.style.display = 'block';
    });
    
    preferenceForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await submitQuestionnaire(); 
    });
    
    refreshButton.addEventListener('click', refreshRecommendations);
    
    closeModal.addEventListener('click', () => {
        modal.style.display = 'none';
    });
    
    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });
}

async function submitQuestionnaire() {
    // Collect form data
    const genres = Array.from(document.querySelectorAll('input[name="genres"]:checked')).map(cb => cb.value);
    const themes = Array.from(document.querySelectorAll('input[name="themes"]:checked')).map(cb => cb.value);
    const demographic = document.querySelector('input[name="demographic"]:checked')?.value || 'any';
    const contentRating = document.querySelector('input[name="content-rating"]:checked')?.value || 'any';
    const status = document.querySelector('input[name="status"]:checked')?.value || 'any';
    const timePeriod = document.querySelector('input[name="time-period"]:checked')?.value || 'any';
    const minRating = parseFloat(document.getElementById('min-rating').value) || 7.0;
    
    // Build preferences object
    const preferences = {
        genres,
        themes,
        preferred_demographics: [demographic].filter(d => d !== 'any'),
        preferred_content_rating: [contentRating].filter(c => c !== 'any'),
        preferred_status: [status].filter(s => s !== 'any'),
        time_period: timePeriod,
        min_rating: minRating
    };
    
    console.log("Submitting preferences:", preferences);
    
    // Show loading state
    questionnaireSection.innerHTML = `
        <div class="loading-full">
            <div class="spinner"></div>
            <p>Analyzing your preferences...</p>
        </div>
    `;
    
    // Start session with preferences
    try {
        const response = await fetch('/api/session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preferences })
        });

        const data = await response.json();
        console.log("Session API response:", data);

        if (data.error) {
            throw new Error(data.error);
        }

        currentSessionId = data.session_id;
        likedMangaIds.clear();
        personalizedData = data.recommendations;
        
        // Hide questionnaire, show recommendations
        questionnaireSection.style.display = 'none';
        topMangaSection.style.display = 'none';
        recommendationsSection.style.display = 'block';
        
        displayManga(personalizedData, personalizedContainer);
    } catch (error) {
        console.error("Session error:", error);
        questionnaireSection.innerHTML = `
            <div class="error-full">
                <p class="error">Error: ${error.message}</p>
                <button class="btn-primary" onclick="location.reload()">Try Again</button>
            </div>
        `;
    }
}

// Display manga in a container
function displayManga(mangaList, container) {
    console.log("Displaying manga:", mangaList);
    container.innerHTML = '';

    if (!mangaList || mangaList.length === 0) {
        console.warn("No manga to display");
        container.innerHTML = '<p class="no-results">No manga recommendations found. Try refreshing or check back later.</p>';
        return;
    }

    mangaList.forEach(manga => {
        const mangaCard = document.createElement('div');
        mangaCard.className = 'manga-card';

        const specificStats = manga.stats ? manga.stats[manga.id] : null;
        const averageRating = specificStats && specificStats.rating ? specificStats.rating.average : null;
        const displayRating = averageRating !== null ? averageRating.toFixed(1) : 'N/A';

        mangaCard.innerHTML = `
            <div class="cover-container">
                <img src="${manga.cover_art || 'https://via.placeholder.com/300x450?text=No+Cover'}" 
                     alt="${manga.title}" class="manga-cover">
                <div class="manga-badge">${manga.publication_type ? manga.publication_type.toUpperCase() : 'MANGA'}</div>
            </div>
            <div class="manga-info">
                <div class="manga-title">${manga.title}</div>
                <div class="manga-stats">
                    <div class="year">${manga.year || 'N/A'}</div>
                    <div class="rating">★ ${displayRating}</div>
                </div>
                <div class="manga-genres">
                    ${manga.genres.slice(0, 3).map(genre =>
            `<div class="genre-tag">${genre}</div>`).join('')}
                </div>
                <div class="action-bar">
                    <button class="action-btn like-btn ${likedMangaIds.has(manga.id) ? 'liked' : ''}" data-id="${manga.id}">
                        <i class="fas fa-heart"></i>
                        ${likedMangaIds.has(manga.id) ? 'Liked' : 'Like'}
                    </button>
                    <button class="action-btn details-btn" data-id="${manga.id}">
                        <i class="fas fa-info-circle"></i>
                    </button>
                </div>
            </div>
        `;

        container.appendChild(mangaCard);
    });

    // Add event listeners to like buttons
    container.querySelectorAll('.like-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const mangaId = btn.dataset.id;

            if (likedMangaIds.has(mangaId)) {
                likedMangaIds.delete(mangaId);
                btn.innerHTML = '<i class="fas fa-heart"></i> Like';
                btn.classList.remove('liked');
            } else {
                likedMangaIds.add(mangaId);
                btn.innerHTML = '<i class="fas fa-heart"></i> Liked';
                btn.classList.add('liked');

                // Animation effect
                btn.style.transform = 'scale(1.1)';
                setTimeout(() => {
                    btn.style.transform = 'scale(1)';
                }, 200);
            }
        });
    });

    // Add event listeners to details buttons
    container.querySelectorAll('.details-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const mangaId = btn.dataset.id;
            const dataSource = container === personalizedContainer ? personalizedData : topMangaData;
            const manga = dataSource.find(m => m.id === mangaId);
            if (manga) {
                showMangaDetails(manga);
            }
        });
    });
}

function showMangaDetails(manga) {
    const creators = manga.authors.length > 0 ?
        `<p><strong>Authors:</strong> ${manga.authors.join(', ')}</p>` :
        manga.artists.length > 0 ?
            `<p><strong>Artists:</strong> ${manga.artists.join(', ')}</p>` : '';

    const genres = manga.genres.length > 0 ?
        `<p><strong>Genres:</strong> ${manga.genres.join(', ')}</p>` : '';

    const themes = manga.themes && manga.themes.length > 0 ?
        `<p><strong>Themes:</strong> ${manga.themes.join(', ')}</p>` : '';

    const specificStats = manga.stats ? manga.stats[manga.id] : null;
    const averageRating = specificStats && specificStats.rating ? specificStats.rating.average : null;
    const displayRating = averageRating !== null ? averageRating.toFixed(1) : 'N/A';
    const displayFollows = specificStats && specificStats.follows ? specificStats.follows : null;

    let statsHTML = '';
    if (manga.stats) {
        statsHTML = `
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value">${displayRating ? displayRating : 'N/A'}</div>
                    <div class="stat-label">Rating</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${displayFollows ? displayFollows.toLocaleString() : 'N/A'}</div>
                    <div class="stat-label">Follows</div>
                </div>
            </div>
        `;
    }

    modalContent.innerHTML = `
        <div class="manga-detail-container">
            <img src="${manga.cover_art || 'https://via.placeholder.com/300x450?text=No+Cover'}" 
                alt="${manga.title}" class="manga-detail-cover">
            <div class="manga-detail-info">
                <h2 class="manga-detail-title">${manga.title}</h2>
                
                <div class="manga-detail-meta">
                    <span class="meta-item">${manga.year || 'Year N/A'}</span>
                    <span class="meta-item">${manga.language ? manga.language.toUpperCase() : 'N/A'}</span>
                    <span class="meta-item">${manga.status || 'Status N/A'}</span>
                    <span class="meta-item">${manga.content_rating || 'Rating N/A'}</span>
                </div>
                
                <div class="manga-detail-description">
                    ${manga.description || 'No description available.'}
                </div>
                
                <div class="detail-section">
                    ${creators}
                    ${genres}
                    ${themes}
                </div>
                
                <div class="detail-section">
                    <div class="detail-section-title">Statistics</div>
                    ${statsHTML}
                </div>
            </div>
        </div>
    `;

    modal.style.display = 'block';
}

// Refresh recommendations
async function refreshRecommendations() {
    if (!currentSessionId) return;

    refreshButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refining...';
    refreshButton.disabled = true;

    try {
        const response = await fetch('/api/recommend', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                likes: Array.from(likedMangaIds)
            })
        });

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        personalizedData = data.recommendations;
        displayManga(personalizedData, personalizedContainer);
        showNotification('✨ Recommendations refined based on your preferences!');
    } catch (error) {
        showNotification(`Error: ${error.message}`, 'error');
    } finally {
        refreshButton.innerHTML = '<i class="fas fa-sync-alt"></i> Refine Recommendations';
        refreshButton.disabled = false;
    }
}

function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'fadeOut 0.5s ease forwards';
        setTimeout(() => notification.remove(), 500);
    }, 3000);
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', initApp);