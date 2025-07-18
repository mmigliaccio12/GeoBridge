// Initialize the map
const map = L.map('map').setView([45.4642, 9.1900], 10); // Milan, Italy as starting point

// Add OpenStreetMap tile layer
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 18
}).addTo(map);

// Initialize variables to store the selected area
let selectedArea = null;
let drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

// Keep track of risk overlay and current layer overlay
let riskOverlay = null;
let currentLayerOverlay = null;

// Store analysis results
let analysisResults = null;

// Analysis mode and charts
let currentAnalysisMode = 'current';
let trendCharts = {}; // Store multiple charts

// Initialize modals
let loadingModal;
let detailedReportModal;

// Sidebar states
let sidebarState = 'analysis'; // 'analysis' or 'layer-view'

document.addEventListener('DOMContentLoaded', function() {
    // Initialize modals
    loadingModal = new bootstrap.Modal(document.getElementById('loadingModal'), {
        backdrop: 'static',
        keyboard: false
    });
    
    detailedReportModal = new bootstrap.Modal(document.getElementById('detailedReportModal'));
    
    // Set default end date to current date or August 2024 (whichever is earlier)
    const today = new Date();
    const safeEndDate = new Date(2024, 7, 31); // August 31, 2024
    const endDate = today > safeEndDate ? safeEndDate : today;
    document.getElementById('end-date').value = endDate.toISOString().split('T')[0];
    
    // Set default start date to 18 months before end date
    const startDate = new Date(endDate);
    startDate.setMonth(startDate.getMonth() - 18);
    document.getElementById('start-date').value = startDate.toISOString().split('T')[0];
    
    console.log(`📅 Initialized date range: ${startDate.toISOString().split('T')[0]} to ${endDate.toISOString().split('T')[0]}`);
    
    // Chart.js debugging
    console.log('🔍 Chart.js availability check:', typeof Chart !== 'undefined' ? 'Available' : 'Not available');
    if (typeof Chart !== 'undefined') {
        console.log('📊 Chart.js version:', Chart.version);
    }
    
    // Initialize button state on page load
    updateAnalyzeButtonState();
});

// Function to update analyze button state based on area selection
function updateAnalyzeButtonState() {
    const analyzeBtn = document.getElementById('analyze-btn');
    const analyzeBtnText = document.getElementById('analyze-btn-text');
    const analysisControls = document.getElementById('analysis-controls');
    
    if (selectedArea) {
        // Area is selected - enable button
        analyzeBtn.removeAttribute('disabled');
        analyzeBtn.classList.add('active');
        
        // Add visual indicator to the controls container
        if (analysisControls) {
            analysisControls.classList.add('area-selected');
        }
        
        // Set button text based on analysis mode
        if (currentAnalysisMode === 'trend') {
            analyzeBtnText.textContent = 'Analyze Trends for Selected Area';
        } else {
            analyzeBtnText.textContent = 'Analyze Selected Area';
        }
        
        // Update tooltip for enabled state
        analyzeBtn.setAttribute('title', 'Click to start satellite data analysis');
        
        console.log('✅ Analyze button enabled - area selected');
    } else {
        // No area selected - disable button
        analyzeBtn.setAttribute('disabled', 'true');
        analyzeBtn.classList.remove('active');
        
        // Remove visual indicator from controls container
        if (analysisControls) {
            analysisControls.classList.remove('area-selected');
        }
        
        // Set helpful button text
        analyzeBtnText.textContent = 'Select an Area to Analyze';
        
        // Add helpful tooltip for disabled state
        analyzeBtn.setAttribute('title', 'Please draw an area on the map using the drawing tools');
        
        console.log('❌ Analyze button disabled - no area selected');
    }
}

// Location search variables
let searchMarker = null;
const searchInput = document.getElementById('location-search');
const searchSuggestions = document.getElementById('search-suggestions');
let searchTimeout = null;
let selectedSuggestionIndex = -1;

// Function to search for locations with autocomplete
function searchLocations(query) {
    if (query.length < 3) {
        searchSuggestions.innerHTML = '';
        searchSuggestions.style.display = 'none';
        return;
    }
    
    // Cancel previous timeout
    if (searchTimeout) {
        clearTimeout(searchTimeout);
    }
    
    // Set a timeout to prevent too many requests
    searchTimeout = setTimeout(() => {
        // Use Nominatim for geocoding
        fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=5`)
            .then(response => response.json())
            .then(data => {
                // Clear current suggestions
                searchSuggestions.innerHTML = '';
                
                if (data.length === 0) {
                    searchSuggestions.style.display = 'none';
                    return;
                }
                
                // Create suggestion items
                data.forEach((place, index) => {
                    const suggestion = document.createElement('div');
                    suggestion.className = 'search-suggestion';
                    suggestion.innerHTML = `
                        <i class="bi bi-geo-alt-fill"></i>
                        <div class="suggestion-details">
                            <div class="suggestion-name">${place.display_name.split(',')[0]}</div>
                            <div class="suggestion-address">${place.display_name}</div>
                        </div>
                    `;
                    
                    // Add click event
                    suggestion.addEventListener('click', () => {
                        selectLocation(place);
                    });
                    
                    // Add hover event
                    suggestion.addEventListener('mouseenter', () => {
                        selectedSuggestionIndex = index;
                        highlightSuggestion();
                    });
                    
                    searchSuggestions.appendChild(suggestion);
                });
                
                // Show suggestions
                searchSuggestions.style.display = 'block';
            })
            .catch(error => {
                console.error('Error fetching search results:', error);
                searchSuggestions.innerHTML = '<div class="search-error">Error fetching results</div>';
                searchSuggestions.style.display = 'block';
            });
    }, 300);
}

// Function to select a location from search
function selectLocation(place) {
    // Clear search suggestions
    searchSuggestions.innerHTML = '';
    searchSuggestions.style.display = 'none';
    
    // Set input value to selected place
    searchInput.value = place.display_name;
    
    // Clear previous marker
    if (searchMarker) {
        map.removeLayer(searchMarker);
    }
    
    // Get coordinates
    const lat = parseFloat(place.lat);
    const lng = parseFloat(place.lon);
    
    // Add marker
    searchMarker = L.marker([lat, lng], {
        icon: L.divIcon({
            className: 'search-marker',
            html: '<div class="marker-icon"><i class="bi bi-geo-alt-fill"></i></div>',
            iconSize: [30, 30]
        })
    }).addTo(map);
    
    // Show popup with place name
    searchMarker.bindPopup(`<b>${place.display_name.split(',')[0]}</b><br>${place.display_name}`).openPopup();
    
    // Fly to location
    map.flyTo([lat, lng], 14);
}

// Function to highlight the selected suggestion
function highlightSuggestion() {
    const suggestions = searchSuggestions.querySelectorAll('.search-suggestion');
    
    // Remove highlight from all suggestions
    suggestions.forEach(suggestion => {
        suggestion.classList.remove('selected');
    });
    
    // Add highlight to selected suggestion
    if (selectedSuggestionIndex >= 0 && selectedSuggestionIndex < suggestions.length) {
        suggestions[selectedSuggestionIndex].classList.add('selected');
    }
}

// Event listener for search input
searchInput.addEventListener('input', (e) => {
    searchLocations(e.target.value);
});

// Event listener for search button
document.getElementById('search-btn').addEventListener('click', () => {
    const query = searchInput.value.trim();
    if (query) {
        // Use Nominatim for geocoding
        fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`)
            .then(response => response.json())
            .then(data => {
                if (data.length > 0) {
                    selectLocation(data[0]);
                } else {
                    alert('Location not found. Please try a different search term.');
                }
            })
            .catch(error => {
                console.error('Error fetching search results:', error);
                alert('Error searching for location. Please try again.');
            });
    }
});

// Handle keyboard navigation in suggestions
searchInput.addEventListener('keydown', (e) => {
    const suggestions = searchSuggestions.querySelectorAll('.search-suggestion');
    
    if (suggestions.length === 0) {
        return;
    }
    
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedSuggestionIndex = Math.min(selectedSuggestionIndex + 1, suggestions.length - 1);
        highlightSuggestion();
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedSuggestionIndex = Math.max(selectedSuggestionIndex - 1, 0);
        highlightSuggestion();
    } else if (e.key === 'Enter') {
        e.preventDefault();
        if (selectedSuggestionIndex >= 0 && selectedSuggestionIndex < suggestions.length) {
            suggestions[selectedSuggestionIndex].click();
        } else if (suggestions.length > 0) {
            suggestions[0].click();
        }
    } else if (e.key === 'Escape') {
        e.preventDefault();
        searchSuggestions.innerHTML = '';
        searchSuggestions.style.display = 'none';
    }
});

// Hide suggestions when clicking outside
document.addEventListener('click', (e) => {
    if (!searchInput.contains(e.target) && !searchSuggestions.contains(e.target)) {
        searchSuggestions.innerHTML = '';
        searchSuggestions.style.display = 'none';
    }
});

// Initialize Leaflet Draw controls
const drawControl = new L.Control.Draw({
    draw: {
        polyline: false,
        polygon: false,
        rectangle: {
            shapeOptions: {
                color: '#0074d9',
                fillOpacity: 0.2
            }
        },
        circle: false,
        circlemarker: false,
        marker: false
    },
    edit: {
        featureGroup: drawnItems,
        remove: true
    }
});
map.addControl(drawControl);

// Event handler for when a shape is drawn on the map
map.on('draw:created', function(e) {
    // Clear any existing layers
    drawnItems.clearLayers();
    
    // Add the newly drawn layer
    drawnItems.addLayer(e.layer);
    
    // Store the bounds for analysis
    if (e.layerType === 'rectangle') {
        console.log("Rectangle created");
        const bounds = e.layer.getBounds();
        selectedArea = {
            bounds: [
                [bounds.getSouthWest().lng, bounds.getSouthWest().lat],
                [bounds.getNorthEast().lng, bounds.getNorthEast().lat]
            ],
            getBounds: function() {
                return bounds; // Store the actual Leaflet bounds object for later use
            },
            getSouth: function() {
                return bounds.getSouth();
            },
            getNorth: function() {
                return bounds.getNorth();
            },
            getWest: function() {
                return bounds.getWest();
            },
            getEast: function() {
                return bounds.getEast();
            }
        };
        
        console.log("Selected area:", selectedArea);
        
        // Calculate and display area information
        updateAreaInfo(selectedArea);
    }
    
    // Update analyze button state
    updateAnalyzeButtonState();
});

// Event handler for when a shape is deleted
map.on('draw:deleted', function(e) {
    selectedArea = null;
    
    // Hide area info
    document.getElementById('area-info').style.display = 'none';
    
    // Update analyze button state
    updateAnalyzeButtonState();
});

// Event handlers for analysis mode switching
document.querySelectorAll('input[name="analysis-mode"]').forEach(radio => {
    radio.addEventListener('change', function() {
        currentAnalysisMode = this.value;
        updateAnalysisMode();
    });
});

// Function to update UI based on analysis mode
function updateAnalysisMode() {
    const timeRangeControls = document.getElementById('time-range-controls');
    
    if (currentAnalysisMode === 'trend') {
        timeRangeControls.style.display = 'block';
    } else {
        timeRangeControls.style.display = 'none';
    }
    
    // Update button text based on new mode and current selection state
    updateAnalyzeButtonState();
}

// Function to calculate and display area information
function updateAreaInfo(area) {
    const areaInfoPanel = document.getElementById('area-info');
    const areaSizeElement = document.getElementById('area-size');
    const areaCoordsElement = document.getElementById('area-coords');
    
    // Calculate area in km²
    const bounds = area.getBounds();
    const areaKm2 = calculateAreaFromBounds(bounds);
    
    // Update display
    areaSizeElement.textContent = `${areaKm2.toFixed(1)} km²`;
    areaCoordsElement.textContent = `${bounds.getSouth().toFixed(3)}°, ${bounds.getWest().toFixed(3)}° to ${bounds.getNorth().toFixed(3)}°, ${bounds.getEast().toFixed(3)}°`;
    
    // Show the panel
    areaInfoPanel.style.display = 'block';
}

// Function to calculate area from bounds (approximate)
function calculateAreaFromBounds(bounds) {
    const R = 6371; // Earth's radius in km
    const lat1 = bounds.getSouth() * Math.PI / 180;
    const lat2 = bounds.getNorth() * Math.PI / 180;
    const deltaLat = (bounds.getNorth() - bounds.getSouth()) * Math.PI / 180;
    const deltaLng = (bounds.getEast() - bounds.getWest()) * Math.PI / 180;
    
    const a = Math.sin(deltaLat/2) * Math.sin(deltaLat/2) +
              Math.cos(lat1) * Math.cos(lat2) *
              Math.sin(deltaLng/2) * Math.sin(deltaLng/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    
    // Approximate area calculation
    const latDistance = R * deltaLat;
    const lngDistance = R * deltaLng * Math.cos((lat1 + lat2) / 2);
    
    return Math.abs(latDistance * lngDistance);
}

// Event handler for analyze button
document.getElementById('analyze-btn').addEventListener('click', function() {
    // Double-check area selection (should not happen with disabled button, but good failsafe)
    if (!selectedArea) {
        showNotification('warning', 'Please select an area on the map first by using the drawing tools');
        return;
    }
    
    // Proceed directly with analysis - backend will handle authentication
    startAnalysis();
});

function startAnalysis() {
    console.log('🚀 Starting analysis for selected area:', selectedArea.bounds);
    
    // Show loading modal
    loadingModal.show();
    
    // Initialize progress
    updateLoadingProgress(0, 'Initializing analysis...', 'Preparing satellite data requests...');
    
    // Prepare request data based on analysis mode
    let requestData = {
        bounds: selectedArea.bounds,
        analysis_mode: currentAnalysisMode
    };
    
    if (currentAnalysisMode === 'trend') {
        requestData.start_date = document.getElementById('start-date').value;
        requestData.end_date = document.getElementById('end-date').value;
        requestData.interval_months = parseInt(document.getElementById('time-interval').value);
    }
    
    console.log("Sending analysis request with data:", requestData);
    
    // Simulate progress updates
    updateLoadingProgress(20, 'Connecting to Sentinel Hub...', 'Authenticating with satellite data provider...');
    
    setTimeout(() => {
        updateLoadingProgress(40, 'Fetching satellite data...', 'Downloading satellite imagery and indices...');
    }, 1000);
    
    setTimeout(() => {
        updateLoadingProgress(60, 'Processing satellite indices...', 'Calculating NDVI, NDMI, NDBI, NBR values...');
    }, 2000);
    
    setTimeout(() => {
        updateLoadingProgress(80, 'Calculating risk scores...', 'Analyzing vegetation, water stress, urban areas...');
    }, 3000);
    
    // Choose endpoint based on analysis mode
    const endpoint = currentAnalysisMode === 'trend' ? '/analyze_trends' : '/analyze';
    
    // Send request to backend
    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
    })
    .then(response => {
        updateLoadingProgress(95, 'Finalizing results...', 'Generating visualizations and summary...');
        
        // Check if we got redirected to login page
        if (response.redirected && response.url.includes('/login')) {
            throw new Error('Authentication required. Please log in and try again.');
        }
        
        if (!response.ok) {
            // Try to parse error response as JSON, but handle cases where it might be HTML
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return response.json().then(data => {
                    throw new Error(data.message || 'Error during analysis');
                });
            } else {
                throw new Error('Server error occurred. Please check your login status and try again.');
            }
        }
        
        // Make sure we're getting JSON response before parsing
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('Unexpected response format. Please ensure you are logged in.');
        }
        
        return response.json();
    })
    .then(data => {
        updateLoadingProgress(100, 'Analysis complete!', 'Preparing results display...');
        
        // Hide loading modal after a brief delay
        setTimeout(() => {
            loadingModal.hide();
            
            // Process and display results
            console.log("Analysis results:", data);
            analysisResults = data;
            
            // Go directly to detailed report modal
            populateDetailedReportModal(data);
            detailedReportModal.show();
            
        }, 500);
    })
    .catch(error => {
        console.error('Analysis error:', error);
        
        // Hide loading modal
        loadingModal.hide();
        
        // Show error modal
        const errorModal = new bootstrap.Modal(document.getElementById('error-modal'));
        document.getElementById('error-message').textContent = error.message || 'An unexpected error occurred during analysis';
        errorModal.show();
    });
}

// Function to update loading progress
function updateLoadingProgress(percentage, mainText, detailText) {
    document.getElementById('loading-progress-bar').style.width = `${percentage}%`;
    document.getElementById('loading-progress-text').textContent = mainText;
    document.getElementById('loading-details').textContent = detailText;
}

// Function to populate detailed report modal
function populateDetailedReportModal(data) {
    console.log('🔍 Populating detailed report modal with data:', data);
    
    // Determine if this is trend analysis
    const isTrendAnalysis = data.analysis_type === 'trend';
    let reportData, coords;
    
    if (isTrendAnalysis && data.trend_data && data.trend_data.length > 0) {
        // For trend analysis, use the latest data point
        reportData = data.trend_data[data.trend_data.length - 1];
        coords = reportData.area_info.coordinates;
        document.getElementById('report-modal-title').textContent = 'Trend Analysis Report';
    } else {
        // For current analysis
        reportData = data;
        coords = data.area_info.coordinates;
        document.getElementById('report-modal-title').textContent = 'Risk Analysis Report';
    }
    
    // Populate overall risk summary
    const riskScore = isTrendAnalysis ? reportData.composite_risk : data.index_values.composite_risk;
    document.getElementById('detailed-risk-score').textContent = riskScore.toFixed(1);
    
    const riskLevel = getRiskLevel(riskScore);
    const riskBadge = document.getElementById('detailed-risk-level');
    riskBadge.textContent = riskLevel.text;
    riskBadge.className = `badge ${riskLevel.class}`;
    
    // Populate area information
    document.getElementById('detailed-area-size').textContent = `${reportData.area_info.area_km2} km²`;
    document.getElementById('detailed-analysis-date').textContent = 
        isTrendAnalysis ? `${data.summary.date_range} (${data.trend_data.length} periods)` : reportData.area_info.analysis_date;
    document.getElementById('detailed-coordinates').textContent = 
        `${coords.min_lat.toFixed(4)}°N, ${coords.min_lon.toFixed(4)}°E to ${coords.max_lat.toFixed(4)}°N, ${coords.max_lon.toFixed(4)}°E`;
    
    // Populate risk factors
    populateDetailedRiskFactors(isTrendAnalysis ? reportData.risk_values : data.risk_values);
    
    // Fetch AI interpretation
    fetchAIInterpretation(isTrendAnalysis ? reportData : data);
    
    // Handle trend charts or single analysis
    if (isTrendAnalysis) {
        document.getElementById('trend-charts-container').style.display = 'block';
        createTrendCharts(data.trend_data);
    } else {
        document.getElementById('trend-charts-container').style.display = 'none';
        // Destroy any existing trend charts
        destroyAllTrendCharts();
    }
    
    // Populate layers grid
    const factorImages = isTrendAnalysis ? reportData.factor_images : data.factor_images;
    const riskImage = isTrendAnalysis ? reportData.risk_image : data.risk_image;
    populateDetailedLayersGrid(factorImages, riskImage);
    
    // Add risk overlay to map
    addRiskOverlayToMap(reportData);
}

// Function to format AI interpretation with markdown styling
function formatAIInterpretation(text) {
    // Replace markdown headers with styled HTML
    text = text.replace(/^## (.*$)/gm, '<h2 class="mb-3">$1</h2>');
    text = text.replace(/^### (.*$)/gm, '<h3 class="mb-2">$1</h3>');
    
    // Replace bold text
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Replace bullet points
    text = text.replace(/^\* (.*$)/gm, '<li>$1</li>');
    text = text.replace(/(<li>.*<\/li>)/gs, '<ul class="mb-3">$1</ul>');
    
    // Replace paragraphs
    text = text.replace(/^(?!<[hul])(.*$)/gm, '<p class="mb-2">$1</p>');
    
    return text;
}

// Function to get risk level info
function getRiskLevel(score) {
    if (score < 3) {
        return { text: 'Low Risk', class: 'bg-success' };
    } else if (score < 6) {
        return { text: 'Moderate Risk', class: 'bg-warning' };
    } else if (score < 8) {
        return { text: 'High Risk', class: 'bg-danger' };
    } else {
        return { text: 'Critical Risk', class: 'bg-dark' };
    }
}

// Function to populate detailed risk factors
function populateDetailedRiskFactors(riskValues) {
    const container = document.getElementById('detailed-risk-factors');
    container.innerHTML = '';
    
    const factors = [
        { 
            key: 'vegetation_health', 
            label: 'Vegetation Health', 
            icon: 'bi-tree', 
            color: '#28a745',
            description: 'Measures the density and health of vegetation. High values indicate sparse, dry vegetation (often associated with higher fire risk); low values indicate dense, healthy vegetation (potential storm damage, but fire-resistant when moist).'
        },
        { 
            key: 'water_stress', 
            label: 'Water Stress', 
            icon: 'bi-droplet', 
            color: '#007bff',
            description: 'Indicates the moisture content in vegetation. High values mean water stress and higher drought/fire risk; low values mean healthy, well-watered plants and lower fire risk.'
        },
        { 
            key: 'urban_areas', 
            label: 'Urban Areas', 
            icon: 'bi-buildings', 
            color: '#6f42c1',
            description: 'Detects the density of built-up areas and infrastructure. Higher values mean more buildings and higher property risk; lower values indicate more natural, undeveloped land.'
        },
        { 
            key: 'burn_areas', 
            label: 'Fire Risk', 
            icon: 'bi-fire', 
            color: '#dc3545',
            description: 'Assesses recent fire damage and burn severity. High values indicate recent burns or stressed vegetation (high fire risk); low values mean healthy, unburned vegetation.'
        },
        { 
            key: 'roof_risk', 
            label: 'Roof Risk', 
            icon: 'bi-house-door', 
            color: '#fd7e14',
            description: 'Estimates the vulnerability of roof materials to weather damage. Higher values indicate more exposed or fragile roofs, increasing risk from hail, wind, or storms.'
        },
        { 
            key: 'drainage_risk', 
            label: 'Drainage', 
            icon: 'bi-water', 
            color: '#20c997',
            description: 'Identifies areas with poor water drainage or waterlogging risk. High values mean potential for flooding or water accumulation; low values indicate good drainage.'
        }
    ];
    
    factors.forEach(factor => {
        if (riskValues[factor.key] !== undefined) {
            const value = riskValues[factor.key].toFixed(1);
            const riskLevel = getRiskLevel(riskValues[factor.key]);
            
            const factorEl = document.createElement('div');
            factorEl.className = 'col-md-4 col-sm-6 mb-3';
            factorEl.innerHTML = `
                <div class="card h-100" data-bs-toggle="tooltip" data-bs-placement="top" title="${factor.description}">
                    <div class="card-body text-center">
                        <i class="${factor.icon}" style="font-size: 2rem; color: ${factor.color}; margin-bottom: 0.5rem;"></i>
                        <h5 class="card-title">${factor.label}</h5>
                        <div class="risk-score-large">${value}/10</div>
                        <span class="badge ${riskLevel.class}">${riskLevel.text}</span>
                    </div>
                </div>
            `;
            container.appendChild(factorEl);
        }
    });
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl, {
            html: true,
            trigger: 'hover'
        });
    });
}

// Function to create trend charts
function createTrendCharts(trendData) {
    console.log('📊 Creating trend charts...');
    
    // Check if Chart.js is available
    if (typeof Chart === 'undefined') {
        console.error('❌ Chart.js not available');
        document.getElementById('trend-charts-container').innerHTML = `
            <div class="alert alert-warning">
                <h6>Chart Library Error</h6>
                <p>Chart.js failed to load. Please refresh the page.</p>
                <details>
                    <summary>Raw Data</summary>
                    <pre>${JSON.stringify(trendData, null, 2)}</pre>
                </details>
            </div>
        `;
        return;
    }
    
    console.log('✅ Chart.js is available, version:', Chart.version);
    
    // Destroy existing charts
    destroyAllTrendCharts();
    
    // Create overall trend chart
    createOverallTrendChart(trendData);
    
    // Create individual factor charts
    createFactorTrendCharts(trendData);
}

// Function to create overall trend chart
function createOverallTrendChart(trendData) {
    const ctx = document.getElementById('overall-trend-chart');
    if (!ctx) {
        console.error('Overall trend chart canvas not found');
        return;
    }
    
    const dates = trendData.map(item => {
        const date = new Date(item.analysis_date);
        return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    });
    
    const riskData = trendData.map(item => item.composite_risk);
    
    try {
        trendCharts.overall = new Chart(ctx, {
            type: 'line',
            data: {
                labels: dates,
                datasets: [{
                    label: 'Overall Risk Score',
                    data: riskData,
                    borderColor: '#e74c3c',
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.3,
                    pointBackgroundColor: '#e74c3c',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 6,
                    pointHoverRadius: 8,
                    pointHoverBackgroundColor: '#c0392b',
                    pointHoverBorderColor: '#fff',
                    pointHoverBorderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: '#e74c3c',
                        borderWidth: 2,
                        cornerRadius: 8,
                        displayColors: false,
                        callbacks: {
                            title: function(context) {
                                return `Analysis Date: ${context[0].label}`;
                            },
                            label: function(context) {
                                const value = context.parsed.y;
                                let level = 'Low';
                                if (value >= 8) level = 'Critical';
                                else if (value >= 6) level = 'High';
                                else if (value >= 3) level = 'Moderate';
                                
                                return [
                                    `Risk Score: ${value.toFixed(1)}/10`,
                                    `Risk Level: ${level}`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 10,
                        title: {
                            display: true,
                            text: 'Risk Level (1-10)',
                            font: {
                                size: 12,
                                weight: 'bold'
                            }
                        },
                        grid: {
                            color: 'rgba(0,0,0,0.1)'
                        },
                        ticks: {
                            stepSize: 1
                        }
                    },
                    x: {
                        grid: {
                            color: 'rgba(0,0,0,0.1)'
                        },
                        ticks: {
                            maxTicksLimit: 6,
                            font: {
                                size: 10
                            }
                        }
                    }
                },
                elements: {
                    point: {
                        hoverRadius: 8
                    }
                }
            }
        });
        console.log('✅ Overall trend chart created successfully');
    } catch (error) {
        console.error('❌ Error creating overall trend chart:', error);
        ctx.parentElement.innerHTML = `<div class="alert alert-danger">Error creating chart: ${error.message}</div>`;
    }
}

// Function to create individual factor trend charts
function createFactorTrendCharts(trendData) {
    const container = document.getElementById('factor-trend-charts');
    container.innerHTML = '';
    
    const factors = [
        { key: 'vegetation_health', label: 'Vegetation Health', color: '#28a745' },
        { key: 'water_stress', label: 'Water Stress', color: '#007bff' },
        { key: 'urban_areas', label: 'Urban Areas', color: '#6f42c1' },
        { key: 'burn_areas', label: 'Fire Risk', color: '#dc3545' },
        { key: 'roof_risk', label: 'Roof Risk', color: '#fd7e14' },
        { key: 'drainage_risk', label: 'Drainage Risk', color: '#20c997' }
    ];
    
    const dates = trendData.map(item => {
        const date = new Date(item.analysis_date);
        return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    });
    
    factors.forEach(factor => {
        // Check if this factor has data in the trend data
        const hasData = trendData.some(item => item.risk_values && item.risk_values[factor.key] !== undefined);
        if (!hasData) return;
        
        // Create chart container
        const chartContainer = document.createElement('div');
        chartContainer.className = 'col-md-6 mb-3';
        chartContainer.innerHTML = `
            <div class="card">
                <div class="card-body">
                    <h6 class="factor-chart-title">${factor.label} Trend</h6>
                    <div class="factor-chart-container">
                        <canvas id="${factor.key}-trend-chart" width="400" height="150"></canvas>
                    </div>
                </div>
            </div>
        `;
        container.appendChild(chartContainer);
        
        // Get canvas and create chart
        const ctx = document.getElementById(`${factor.key}-trend-chart`);
        if (!ctx) {
            console.error(`Canvas not found for ${factor.key}`);
            return;
        }
        
        const factorData = trendData.map(item => 
            item.risk_values && item.risk_values[factor.key] !== undefined ? item.risk_values[factor.key] : null
        );
        
        try {
            trendCharts[factor.key] = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: dates,
                    datasets: [{
                        label: factor.label,
                        data: factorData,
                        borderColor: factor.color,
                        backgroundColor: factor.color + '20',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointBackgroundColor: factor.color,
                        pointBorderColor: '#fff',
                        pointBorderWidth: 1,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        pointHoverBackgroundColor: factor.color,
                        pointHoverBorderColor: '#fff',
                        pointHoverBorderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            titleColor: '#fff',
                            bodyColor: '#fff',
                            borderColor: factor.color,
                            borderWidth: 2,
                            cornerRadius: 6,
                            displayColors: false,
                            callbacks: {
                                title: function(context) {
                                    return context[0].label;
                                },
                                label: function(context) {
                                    const value = context.parsed.y;
                                    let level = 'Low';
                                    if (value >= 8) level = 'Critical';
                                    else if (value >= 6) level = 'High';
                                    else if (value >= 3) level = 'Moderate';
                                    
                                    return [
                                        `${factor.label}: ${value.toFixed(1)}/10`,
                                        `Level: ${level}`
                                    ];
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 10,
                            title: {
                                display: true,
                                text: 'Risk Level',
                                font: {
                                    size: 10
                                }
                            },
                            grid: {
                                color: 'rgba(0,0,0,0.05)'
                            },
                            ticks: {
                                stepSize: 2,
                                font: {
                                    size: 9
                                }
                            }
                        },
                        x: {
                            grid: {
                                color: 'rgba(0,0,0,0.05)'
                            },
                            ticks: {
                                maxTicksLimit: 4,
                                font: {
                                    size: 8
                                }
                            }
                        }
                    },
                    elements: {
                        point: {
                            hoverRadius: 6
                        }
                    }
                }
            });
            console.log(`✅ ${factor.label} trend chart created successfully`);
        } catch (error) {
            console.error(`❌ Error creating ${factor.label} trend chart:`, error);
            ctx.parentElement.innerHTML = `<div class="alert alert-danger small">Chart error: ${error.message}</div>`;
        }
    });
}

// Function to destroy all trend charts
function destroyAllTrendCharts() {
    Object.keys(trendCharts).forEach(key => {
        if (trendCharts[key]) {
            trendCharts[key].destroy();
            delete trendCharts[key];
        }
    });
}

// Function to populate detailed layers grid
function populateDetailedLayersGrid(factorImages, riskImage) {
    const container = document.getElementById('detailed-layers-grid');
    container.innerHTML = '';
    
    // Add overall risk map first
    if (riskImage) {
        addDetailedLayerThumbnail(container, riskImage, 'Combined Risk', 'combined-risk');
    }
    
    // Add factor layers
    const layers = [
        { key: 'vegetation_health', label: 'Vegetation Health' },
        { key: 'water_stress', label: 'Water Stress' },
        { key: 'urban_detection', label: 'Urban Areas' },
        { key: 'burn_detection', label: 'Fire Risk' },
        { key: 'roof_detection', label: 'Roof Analysis' },
        { key: 'drainage_detection', label: 'Drainage Risk' }
    ];
    
    layers.forEach(layer => {
        if (factorImages && factorImages[layer.key]) {
            addDetailedLayerThumbnail(container, factorImages[layer.key], layer.label, layer.key);
        }
    });
}

// Function to add detailed layer thumbnail
function addDetailedLayerThumbnail(container, imageUrl, title, layerId) {
    const layerEl = document.createElement('div');
    layerEl.className = 'col-md-3 col-sm-4 col-6';
    layerEl.innerHTML = `
        <div class="layer-thumbnail" data-layer-id="${layerId}" data-image-url="${imageUrl}" data-title="${title}">
            <img src="${imageUrl}" alt="${title}">
            <div class="layer-title">${title}</div>
        </div>
    `;
    
    // Add click event
    layerEl.querySelector('.layer-thumbnail').addEventListener('click', function() {
        showLayerOnMap(this);
        // Hide the results modal and switch to layer view
        detailedReportModal.hide();
        switchToLayerViewSidebar(title, analysisResults);
    });
    
    container.appendChild(layerEl);
}

// Function to show layer on map
function showLayerOnMap(thumbnailEl) {
    const layerId = thumbnailEl.dataset.layerId;
    const imageUrl = thumbnailEl.dataset.imageUrl;
    const title = thumbnailEl.dataset.title;
    
    // Remove previous layer overlay if exists
    if (currentLayerOverlay) {
        map.removeLayer(currentLayerOverlay);
        currentLayerOverlay = null;
    }
    
    // Add layer overlay to map
    if (selectedArea) {
        const imageBounds = [
            [selectedArea.getSouth(), selectedArea.getWest()],
            [selectedArea.getNorth(), selectedArea.getEast()]
        ];
        
        currentLayerOverlay = L.imageOverlay(imageUrl, imageBounds, {
            opacity: 0.8
        }).addTo(map);
        
        console.log(`🗺️ Showing ${title} layer on map`);
    }
}

// Function to switch to layer view sidebar
function switchToLayerViewSidebar(layerName, results) {
    sidebarState = 'layer-view';
    
    // Hide analysis controls
    document.getElementById('analysis-controls').style.display = 'none';
    
    // Show layer view controls
    document.getElementById('layer-view-controls').style.display = 'block';
    
    // Populate layer info
    document.getElementById('current-layer-name').textContent = layerName;
    
    if (selectedArea) {
        const bounds = selectedArea.getBounds();
        document.getElementById('layer-area-coords').textContent = 
            `${bounds.getSouth().toFixed(3)}°, ${bounds.getWest().toFixed(3)}° to ${bounds.getNorth().toFixed(3)}°, ${bounds.getEast().toFixed(3)}°`;
    }
    
    // Show overall risk score
    if (results) {
        let riskScore;
        if (results.analysis_type === 'trend' && results.trend_data && results.trend_data.length > 0) {
            riskScore = results.trend_data[results.trend_data.length - 1].composite_risk;
        } else if (results.index_values) {
            riskScore = results.index_values.composite_risk;
        } else {
            riskScore = 0;
        }
        
        const riskLevel = getRiskLevel(riskScore);
        document.getElementById('layer-risk-score').textContent = `${riskScore.toFixed(1)}/10 (${riskLevel.text})`;
    }
}

// Function to switch back to analysis sidebar
function switchToAnalysisSidebar() {
    sidebarState = 'analysis';
    
    // Show analysis controls
    document.getElementById('analysis-controls').style.display = 'block';
    
    // Hide layer view controls
    document.getElementById('layer-view-controls').style.display = 'none';
}

// Function to add risk overlay to map
function addRiskOverlayToMap(data) {
    // Remove previous overlay if exists
    if (riskOverlay) {
        map.removeLayer(riskOverlay);
    }
    
    if (selectedArea && data.risk_image) {
        const imageBounds = [
            [selectedArea.getSouth(), selectedArea.getWest()],
            [selectedArea.getNorth(), selectedArea.getEast()]
        ];
        
        riskOverlay = L.imageOverlay(data.risk_image, imageBounds, {
            opacity: 0.7
        }).addTo(map);
    }
}

// Event handler for back to report button
document.getElementById('back-to-report-btn').addEventListener('click', () => {
    switchToAnalysisSidebar();
    if (analysisResults) {
        detailedReportModal.show();
    }
});

// Event handler for hide layer button
document.getElementById('hide-layer-btn').addEventListener('click', () => {
    if (currentLayerOverlay) {
        map.removeLayer(currentLayerOverlay);
        currentLayerOverlay = null;
    }
    switchToAnalysisSidebar();
});

// Event handler for download PDF button
document.getElementById('detailed-download-pdf-btn').addEventListener('click', () => {
    downloadPDFReport();
});

// Function to download PDF report
function downloadPDFReport() {
    if (!analysisResults) {
        alert('No analysis results available.');
        return;
    }
    
    const downloadBtn = event.target;
    const originalText = downloadBtn.innerHTML;
    downloadBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Generating PDF...';
    downloadBtn.disabled = true;
    
    fetch('/download_report', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(analysisResults)
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.message || 'Error generating PDF report');
            });
        }
        return response.blob();
    })
    .then(blob => {
        // Create download link
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        
        // Generate filename with timestamp
        const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
        a.download = `sentinel_risk_report_${timestamp}.pdf`;
        
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showNotification('success', 'PDF report downloaded successfully!');
    })
    .catch(error => {
        console.error('Error downloading report:', error);
        alert('Error generating PDF report: ' + error.message);
    })
    .finally(() => {
        downloadBtn.innerHTML = originalText;
        downloadBtn.disabled = false;
    });
}

// Function to show notifications
function showNotification(type, message) {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show layer-notification`;
    notification.innerHTML = `
        ${message} 
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    document.body.appendChild(notification);
    
    // Auto-dismiss after 3 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 3000);
}

// Event handler for reset button
document.getElementById('reset-btn').addEventListener('click', () => {
    console.log('🔄 Resetting application state...');
    
    // Clear drawn items from map
    drawnItems.clearLayers();
    
    // Reset selected area FIRST (before updating button state)
    selectedArea = null;
    
    // Remove risk overlay if exists
    if (riskOverlay) {
        map.removeLayer(riskOverlay);
        riskOverlay = null;
    }
    
    // Remove current layer overlay if exists
    if (currentLayerOverlay) {
        map.removeLayer(currentLayerOverlay);
        currentLayerOverlay = null;
    }
    
    // Destroy trend charts if they exist
    destroyAllTrendCharts();
    
    // Reset analysis results
    analysisResults = null;
    
    // Hide area info panel
    document.getElementById('area-info').style.display = 'none';
    
    // Update analyze button state (now that selectedArea is null)
    updateAnalyzeButtonState();
    
    // Switch back to analysis sidebar if in layer view
    if (sidebarState === 'layer-view') {
        switchToAnalysisSidebar();
    }
    
    console.log('✅ Application reset complete - analyze button should be disabled');
}); 

// Function to fetch AI interpretation
function fetchAIInterpretation(data) {
    const aiInterpretationDiv = document.getElementById('ai-interpretation');
    
    // Show loading state
    aiInterpretationDiv.innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2 text-muted">Generating AI interpretation...</p>
        </div>
    `;

    // Fetch interpretation from server
    fetch('/get_ai_interpretation', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to fetch AI interpretation');
        }
        return response.json();
    })
    .then(result => {
        if (result.success) {
            // Format the interpretation with proper styling
            aiInterpretationDiv.innerHTML = formatAIInterpretation(result.interpretation);
        } else {
            throw new Error(result.error || 'Failed to generate interpretation');
        }
    })
    .catch(error => {
        console.error('Error fetching AI interpretation:', error);
        aiInterpretationDiv.innerHTML = `
            <div class="alert alert-warning" role="alert">
                <i class="bi bi-exclamation-triangle"></i>
                Unable to generate AI interpretation at this time. Please try again later.
            </div>
        `;
    });
} 