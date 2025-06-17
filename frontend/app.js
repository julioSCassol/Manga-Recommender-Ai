let currentSession = null;
let likedMangaIds = new Set();

document.addEventListener('DOMContentLoaded', () => {
    startSession();
    
    document.getElementById('refresh-btn').addEventListener('click', () => {
        getNewRecommendations();
    });
});

async function startSession() {
    try {
        const response = await fetch('/api/session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        currentSession = data.session_id;
        likedMangaIds.clear();
        displayManga(data.recommendations);
        
        document.getElementById('loading').classList.add('hidden');
        document.getElementById('recommendations').classList.remove('hidden');
    } catch (error) {
        document.getElementById('loading').innerHTML = `
            <p class="error">Error: ${error.message}</p>
            <button onclick="location.reload()">Retry</button>
        `;
    }
}

async function getNewRecommendations() {
    if (!currentSession) return;
    
    const loadingBtn = document.getElementById('refresh-btn');
    loadingBtn.textContent = 'Loading...';
    loadingBtn.disabled = true;
    
    try {
        const response = await fetch('/api/recommend', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSession,
                likes: Array.from(likedMangaIds)
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        displayManga(data.recommendations);
    } catch (error) {
        alert(`Error: ${error.message}`);
    } finally {
        loadingBtn.textContent = 'Get Better Recommendations';
        loadingBtn.disabled = false;
    }
}

function displayManga(mangaList) {
    const container = document.getElementById('manga-container');
    container.innerHTML = '';
    
    mangaList.forEach(manga => {
        const mangaCard = document.createElement('div');
        mangaCard.className = 'manga-card';
        
        mangaCard.innerHTML = `
            <img src="${manga.cover_art || 'https://via.placeholder.com/250x350'}" 
                 alt="${manga.title}" class="manga-cover">
            <div class="manga-info">
                <div class="manga-title">${manga.title}</div>
                <div class="manga-genres">
                    ${manga.genres.slice(0, 3).map(genre => 
                        `<span class="genre-tag">${genre}</span>`).join('')}
                </div>
                <button class="like-btn" data-id="${manga.id}">
                    ${likedMangaIds.has(manga.id) ? '❤️ Liked' : '🤍 Like'}
                </button>
            </div>
        `;
        
        container.appendChild(mangaCard);
    });
    
    // Add event listeners to new buttons
    document.querySelectorAll('.like-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const mangaId = btn.dataset.id;
            
            if (likedMangaIds.has(mangaId)) {
                likedMangaIds.delete(mangaId);
                btn.textContent = '🤍 Like';
            } else {
                likedMangaIds.add(mangaId);
                btn.textContent = '❤️ Liked';
            }
        });
    });
}