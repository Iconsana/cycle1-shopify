// Initialize the UI
function initializeUI() {
    const appContainer = document.getElementById('app');
    appContainer.innerHTML = `
        <!-- Header -->
        <div class="mb-8 text-center">
            <h1 class="text-4xl font-bold text-gray-800 mb-2">ACDC Product Scraper</h1>
            <p class="text-gray-600">Automate product synchronization with Shopify</p>
        </div>

        <!-- Control Panel -->
        <div class="bg-white rounded-lg shadow-md p-6 mb-8">
            <h2 class="text-2xl font-semibold mb-4">Scraping Options</h2>
            
            <!-- Scraping Form -->
            <form id="scrapeForm" class="space-y-4">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <!-- Category Selection -->
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Category</label>
                        <select id="category" name="category" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            <option value="">All Categories</option>
                        </select>
                    </div>

                    <!-- Page Range -->
                    <div class="flex space-x-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Start Page</label>
                            <input type="number" id="startPage" name="start_page" min="1" value="1" 
                                   class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">End Page</label>
                            <input type="number" id="endPage" name="end_page" min="1"
                                   class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                    </div>
                </div>

                <!-- Submit Button -->
                <button type="submit" 
                        class="w-full bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 transition-colors">
                    Start Scraping
                </button>
            </form>
        </div>

        <!-- Status Panel -->
        <div id="statusPanel" class="bg-white rounded-lg shadow-md p-6 mb-8 hidden">
            <h2 class="text-2xl font-semibold mb-4">Scraping Status</h2>
            
            <!-- Progress Bar -->
            <div class="mb-4">
                <div class="w-full bg-gray-200 rounded-full h-4">
                    <div id="progressBar" class="progress-bar bg-blue-600 h-4 rounded-full" style="width: 0%"></div>
                </div>
                <p id="progressText" class="text-sm text-gray-600 mt-2">Starting...</p>
            </div>

            <!-- Download Section -->
            <div id="downloadSection" class="hidden">
                <a id="downloadLink" href="#" 
                   class="inline-block bg-green-600 text-white px-6 py-2 rounded-md hover:bg-green-700 transition-colors">
                    Download CSV
                </a>
            </div>
        </div>

        <!-- Results Panel -->
        <div id="resultsPanel" class="bg-white rounded-lg shadow-md p-6 hidden">
            <h2 class="text-2xl font-semibold mb-4">Results</h2>
            <div id="resultsContent" class="space-y-2">
            </div>
        </div>
    `;
}

// Load categories from the server
async function loadCategories() {
    try {
        const response = await fetch('/categories');
        const categories = await response.json();
        const select = document.getElementById('category');
        categories.forEach(category => {
            const option = document.createElement('option');
            option.value = category;
            option.textContent = category;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading categories:', error);
    }
}

// Handle form submission
function setupFormHandler() {
    document.getElementById('scrapeForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        document.getElementById('statusPanel').classList.remove('hidden');
        document.getElementById('downloadSection').classList.add('hidden');
        
        const formData = new FormData(this);
        
        try {
            const response = await fetch('/sync', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (data.success) {
                pollStatus(data.task_id);
            } else {
                showError(data.message);
            }
        } catch (error) {
            showError(error.message);
        }
    });
}

// Poll task status
function pollStatus(taskId) {
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`/status/${taskId}`);
            const data = await response.json();
            
            updateProgress(data);
            
            if (['SUCCESS', 'FAILURE'].includes(data.state)) {
                clearInterval(interval);
                if (data.state === 'SUCCESS') {
                    showResult(data.result);
                }
            }
        } catch (error) {
            console.error('Error polling status:', error);
        }
    }, 1000);
}

// Update progress bar and status
function updateProgress(data) {
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    
    if (data.state === 'PROGRESS') {
        const percent = data.percent || 0;
        progressBar.style.width = `${percent}%`;
        progressText.textContent = data.status || 'Processing...';
    } else if (data.state === 'SUCCESS') {
        progressBar.style.width = '100%';
        progressText.textContent = 'Completed!';
    }
}

// Show results
function showResult(result) {
    const downloadSection = document.getElementById('downloadSection');
    const downloadLink = document.getElementById('downloadLink');
    
    if (result.file) {
        downloadLink.href = `/download/${result.file}`;
        downloadSection.classList.remove('hidden');
        
        const resultsPanel = document.getElementById('resultsPanel');
        const resultsContent = document.getElementById('resultsContent');
        resultsPanel.classList.remove('hidden');
        resultsContent.innerHTML = `
            <p>Products scraped: ${result.count}</p>
            <p>File name: ${result.file}</p>
            <p>Completed at: ${new Date().toLocaleString()}</p>
        `;
    }
}

// Show error message
function showError(message) {
    const resultsPanel = document.getElementById('resultsPanel');
    const resultsContent = document.getElementById('resultsContent');
    resultsPanel.classList.remove('hidden');
    resultsContent.innerHTML = `
        <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            Error: ${message}
        </div>
    `;
}

// Initialize everything when the page loads
document.addEventListener('DOMContentLoaded', function() {
    initializeUI();
    loadCategories();
    setupFormHandler();
});
