// static/js/search.js
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-input');
    const suggestionsDropdown = document.getElementById('suggestions-dropdown');
    let debounceTimer;

    if (!searchInput) return; // Evita errores si no estamos en la página de búsqueda

    searchInput.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        
        const query = this.value.trim();
        if (query.length < 3) {
            suggestionsDropdown.classList.remove('show');
            return;
        }

        debounceTimer = setTimeout(async () => {
            try {
                const response = await fetch(`/search-suggestions/?q=${encodeURIComponent(query)}`);
                const suggestions = await response.json();
                
                suggestionsDropdown.innerHTML = '';
                if (suggestions.length > 0) {
                    suggestionsDropdown.classList.add('show');
                    suggestions.forEach(suggestion => {
                        const item = document.createElement('div');
                        item.className = 'suggestion-item';
                        item.innerHTML = `<img src="${suggestion.image || suggestion.image_url}" class="suggestion-thumb" loading="lazy" decoding="async" width="40" height="56"><span class="font-medium">${suggestion.name}</span>`;
                        item.onclick = () => {
                            searchInput.value = suggestion.name;
                            searchInput.closest('form').submit();
                        };
                        suggestionsDropdown.appendChild(item);
                    });
                } else {
                    suggestionsDropdown.innerHTML = '<div class="px-4 py-3 text-gray-500 text-center text-sm">Sin resultados</div>';
                    suggestionsDropdown.classList.add('show');
                }
            } catch (e) { 
                console.error("Error en la búsqueda:", e);
                suggestionsDropdown.classList.remove('show'); 
            }
        }, 300);
    });

    document.addEventListener('click', (e) => {
        if (!searchInput.contains(e.target) && !suggestionsDropdown.contains(e.target)) {
            suggestionsDropdown.classList.remove('show');
        }
    });
});