"""
CustomSat Insurance Risk Analysis Platform

OVERVIEW:
This Flask application provides satellite-based risk analysis for insurance purposes.
It uses Sentinel-2 satellite data to calculate various risk factors and generate
comprehensive risk assessments for geographical areas.

MAIN FUNCTIONALITIES:
1. Authentication System - Session-based login/logout
2. Current Risk Analysis - Point-in-time risk assessment 
3. Trend Analysis - Risk evolution over time periods
4. Satellite Data Processing - Converts raw satellite bands into risk indicators
5. PDF Report Generation - Comprehensive risk reports with visualizations

ARCHITECTURE FLOW:
User Login → Area Selection → Data Fetching → Risk Processing → Visualization → Reports

AUTHENTICATION:
- Session-based authentication using Flask sessions
- Demo credentials: admin@customsat.it / password
- All main routes are protected with @login_required decorator
- Automatic redirects for unauthenticated users

RISK ANALYSIS PROCESS:
1. User selects area on map (lat/lon bounds)
2. System fetches satellite data for multiple spectral indices
3. Raw satellite bands are processed into normalized indices (NDVI, NDMI, etc.)
4. Individual risk scores are calculated from satellite indices  
5. Composite risk score is computed from weighted individual factors
6. Visualizations are generated for each risk layer
7. Results are returned as images and numerical data

SATELLITE INDICES USED:
- NDVI (Normalized Difference Vegetation Index) - Vegetation health
- NDMI (Normalized Difference Moisture Index) - Water/moisture content  
- NDBI (Normalized Difference Built-up Index) - Urban development
- NBR (Normalized Burn Ratio) - Fire damage/burn scars
- Custom roof detection - Building roof material analysis
- Custom drainage detection - Water drainage patterns

TREND ANALYSIS:
- Analyzes risk evolution over user-defined time periods
- Splits date range into intervals (3, 6, or 12 months)
- Performs individual risk analysis for each time period
- Compares risk levels across time to identify trends
- Generates trend charts and statistical summaries
"""

import os
import json
import tempfile
import base64
import math
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from io import BytesIO

from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, flash
from dotenv import load_dotenv
import numpy as np
from PIL import Image
from scipy.ndimage import zoom, gaussian_filter
from functools import wraps

# PDF generation imports for comprehensive reporting
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Set matplotlib backend before importing pyplot to avoid threading issues in deployment
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for server environments
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Import custom utilities for satellite data processing
from sentinel_utils import (
    get_sh_config, create_bbox_from_coords,
    process_risk_data, 
    fetch_veg_health, fetch_water_stress, fetch_urban_detection,
    fetch_burn_detection, fetch_roof_detection, fetch_drainage_detection,
    risk_score_to_image, array_to_image
)

# Load environment variables from .env file (Sentinel Hub credentials, etc.)
load_dotenv()

app = Flask(__name__)

# =============================================================================
# AUTHENTICATION CONFIGURATION
# =============================================================================

# Configuration for session-based authentication
app.secret_key = os.environ.get('SECRET_KEY', 'demo-secret-key-for-customsat-2024')

# Configure session settings for better reliability
app.config.update(
    SESSION_COOKIE_SECURE=False,  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY=True,  # Prevent XSS attacks
    SESSION_COOKIE_SAMESITE='Lax',  # CSRF protection
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24)  # Session expires after 24 hours
)

# Demo credentials for deployment and demonstration
# In production, these should be stored securely with proper hashing
DEMO_CREDENTIALS = {
    'admin@customsat.it': 'password'
}

def login_required(f):
    """
    Decorator to require login for protected routes.
    
    FUNCTIONALITY:
    - Checks if user has active session with 'logged_in' flag
    - Redirects unauthenticated users to login page
    - Preserves original function for authenticated users
    
    USAGE:
    @login_required
    def protected_route():
        # This function only runs for logged-in users
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# =============================================================================
# UTILITY FUNCTIONS FOR GEOSPATIAL CALCULATIONS
# =============================================================================

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points on Earth using the Haversine formula.
    
    PURPOSE:
    - Used to calculate the actual area size in km² from latitude/longitude bounds
    - Essential for determining appropriate satellite data resolution
    - Helps validate if selected area is within processing limits
    
    ALGORITHM:
    1. Convert decimal degrees to radians for trigonometric calculations
    2. Apply Haversine formula to account for Earth's spherical nature
    3. Use Earth's radius (6371 km) to convert to kilometers
    
    PARAMETERS:
    lat1, lon1: Coordinates of first point (decimal degrees)
    lat2, lon2: Coordinates of second point (decimal degrees)
    
    RETURNS:
    Distance in kilometers between the two points
    """
    # Convert decimal degrees to radians for trigonometric calculations
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    
    # Haversine formula - accounts for Earth's spherical shape
    dlon = lon2 - lon1  # Difference in longitude
    dlat = lat2 - lat1  # Difference in latitude
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of Earth in kilometers
    return c * r

def sanitize_for_json(obj):
    """
    Recursively sanitize numpy values and NaN/inf for JSON serialization.
    
    PURPOSE:
    - Converts numpy data types to native Python types for JSON compatibility
    - Handles NaN and infinity values that would break JSON serialization
    - Ensures all satellite data can be safely sent to frontend
    
    PROCESSING RULES:
    - Numpy integers/floats → Python float
    - NaN/Infinity values → 0.0 (safe fallback)
    - Numpy arrays → Python lists
    - Nested dictionaries/lists → Recursively processed
    
    WHY NEEDED:
    Satellite data processing returns numpy arrays and values that contain:
    - np.float64, np.int32 (not JSON serializable)
    - NaN values from invalid pixels (clouds, shadows)
    - Infinity values from division operations
    """
    if isinstance(obj, dict):
        # Recursively process dictionary values
        return {key: sanitize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        # Recursively process list items
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, (np.integer, np.floating)):
        # Convert numpy numbers to Python float, handle invalid values
        if np.isnan(obj) or np.isinf(obj):
            return 0.0  # Safe fallback for invalid values
        return float(obj)
    elif isinstance(obj, np.ndarray):
        # Convert numpy arrays to Python lists
        return obj.tolist()
    elif isinstance(obj, float):
        # Handle native Python floats that might be NaN/inf
        if math.isnan(obj) or math.isinf(obj):
            return 0.0  # Safe fallback for invalid values
        return obj
    else:
        # Return other types unchanged
        return obj

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handle user authentication for the CustomSat platform.
    
    FUNCTIONALITY:
    - GET: Display login form with CustomSat branding
    - POST: Process login credentials and create user session
    
    AUTHENTICATION FLOW:
    1. User submits email and password via login form
    2. Credentials are checked against DEMO_CREDENTIALS dictionary
    3. If valid: Create session with logged_in=True and user_email
    4. If invalid: Show error message and return to login form
    5. Successful login redirects to main application
    
    SESSION MANAGEMENT:
    - Uses Flask sessions to maintain login state
    - Sets session['logged_in'] = True for authenticated users
    - Stores session['user_email'] for display in UI
    - Session persists until logout or browser closure
    
    SECURITY FEATURES:
    - Flash messages provide user feedback
    - No password storage in session (only validation flag)
    - Automatic redirect to main app after successful login
    """
    if request.method == 'POST':
        # Extract credentials from login form
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Validate credentials against demo user database
        if email in DEMO_CREDENTIALS and DEMO_CREDENTIALS[email] == password:
            # Create authenticated session
            session['logged_in'] = True
            session['user_email'] = email
            session.permanent = True  # Make session persistent
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            # Authentication failed - show error
            flash('Invalid email or password. Please try again.', 'error')
    
    # Display login form (GET request or failed POST)
    return render_template('login.html')

@app.route('/logout')
def logout():
    """
    Handle user logout and session cleanup.
    
    FUNCTIONALITY:
    - Clears all session data (logged_in flag, user_email, etc.)
    - Provides user feedback via flash message
    - Redirects to login page
    
    SECURITY:
    - Complete session cleanup prevents session hijacking
    - Immediate redirect ensures user cannot access protected content
    - Flash message confirms successful logout
    """
    # Clear all session data for security
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

# =============================================================================
# MAIN APPLICATION ROUTES
# =============================================================================

@app.route('/')
#@login_required
def index():
    """
    Render the main CustomSat application interface.
    
    FUNCTIONALITY:
    - Serves the main map-based risk analysis interface
    - Protected route - requires authentication
    - Loads interactive map, drawing tools, and analysis controls
    
    INTERFACE COMPONENTS:
    - Interactive Leaflet map for area selection
    - Drawing tools for defining analysis regions
    - Analysis mode selection (Current vs Trend)
    - Date range controls for trend analysis
    - Results display panels and layer visualization
    """
    return render_template('index.html')

def generate_simple_fallback(size=(256, 256), bbox=None):
    """
    Generate placeholder satellite data when API calls fail.
    
    PURPOSE:
    - Provides fallback data when Sentinel Hub API is unavailable
    - Ensures application continues to function during API outages
    - Generates realistic-looking data for demonstration purposes
    
    FALLBACK STRATEGY:
    1. Creates random data with realistic value ranges (-0.1 to 0.1)
    2. Adds location-based variation using latitude coordinates
    3. Includes mask channel to simulate valid/invalid pixels
    4. Returns data in same format as real satellite processing
    
    DATA STRUCTURE:
    - Returns list containing numpy array with shape (height, width, 2)
    - Channel 0: Spectral index values (e.g., NDVI, NDMI)
    - Channel 1: Mask values (1 = valid pixel, 0 = invalid)
    
    PARAMETERS:
    size: Tuple of (height, width) for generated array
    bbox: Bounding box for location-based variation (optional)
    """
    print("⚠️ Generating placeholder data - API call failed")
    
    height, width = size
    
    # Add location-based variation if bbox is provided
    if bbox:
        # Use latitude to add some variation (higher latitudes = different patterns)
        lat_center = (bbox.min_y + bbox.max_y) / 2
        lat_factor = abs(lat_center) / 90.0  # 0-1 based on distance from equator
        
        # Create more varied data based on location
        base_value = (lat_factor - 0.5) * 0.3  # Range from -0.15 to 0.15
        data = np.random.uniform(base_value - 0.1, base_value + 0.1, (height, width))
    else:
        # Simple neutral data (around 0) with slight random variation
        data = np.random.uniform(-0.1, 0.1, (height, width))
    
    # Add mask channel (all valid pixels)
    mask = np.ones((height, width, 1))
    # Combine data and mask into expected format
    combined_data = np.dstack((data, mask))
    
    return [combined_data]

@app.route('/analyze', methods=['POST'])
@login_required
def analyze():
    """
    Process selected geographical area and return comprehensive risk analysis.
    
    COMPLETE ANALYSIS PIPELINE:
    
    1. INPUT VALIDATION
       - Validates geographical bounds (lat/lon coordinates)
       - Checks area size against processing limits (max 10,000 km²)
       - Calculates optimal satellite data resolution based on area size
    
    2. SATELLITE DATA ACQUISITION
       - Fetches Sentinel-2 satellite data from multiple spectral bands
       - Processes 6 different risk factors using specialized algorithms:
         * Vegetation Health (NDVI) - B08/B04 bands
         * Water Stress (NDMI) - B08/B11 bands  
         * Urban Detection (NDBI) - B11/B08 bands
         * Fire Risk (NBR) - B08/B12 bands
         * Roof Vulnerability - Multi-band analysis (B02,B04,B08,B11)
         * Drainage Issues - Multi-band analysis (B08,B04,B11)
    
    3. RISK FACTOR CALCULATION
       - Each satellite index is converted to risk score (1-10 scale)
       - Individual factors are weighted and combined
       - Composite risk score represents overall area risk
    
    4. VISUALIZATION GENERATION
       - Creates color-coded images for each risk factor
       - Generates overall risk heatmap
       - Applies appropriate color schemes for different data types
    
    5. RESPONSE FORMATTING
       - Converts all data to JSON-safe formats
       - Returns images as base64-encoded strings
       - Includes metadata (coordinates, area size, analysis date)
    
    ERROR HANDLING:
    - Graceful fallback to placeholder data for API failures
    - Detailed error reporting for debugging
    - Ensures response even with partial data availability
    """
    try:
        # =================================================================
        # STEP 1: INPUT VALIDATION AND PREPROCESSING
        # =================================================================
        
        # Get data from request
        data = request.json
        bounds = data.get('bounds')
        
        # Validate that bounds are provided and properly formatted
        if not bounds or len(bounds) != 2:
            return jsonify({
                'status': 'error',
                'message': 'Invalid bounds provided. Please select an area on the map.'
            }), 400
        
        # Extract and validate coordinates
        min_lon, min_lat = bounds[0]  # Southwest corner
        max_lon, max_lat = bounds[1]  # Northeast corner
        
        # Comprehensive coordinate validation
        if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180 and
                -90 <= min_lat <= 90 and -90 <= max_lat <= 90):
            return jsonify({
                'status': 'error',
                'message': 'Invalid coordinates. Please select a valid area on Earth.'
            }), 400
        
        # Ensure bounds form a valid rectangle
        if min_lon >= max_lon or min_lat >= max_lat:
            return jsonify({
                'status': 'error',
                'message': 'Invalid area selection. Please ensure proper bounds.'
            }), 400
        
        # =================================================================
        # STEP 2: AREA CALCULATION AND RESOLUTION OPTIMIZATION
        # =================================================================
        
        # Calculate the actual area size in square kilometers using Haversine formula
        width_km = haversine_distance(min_lat, min_lon, min_lat, max_lon)
        height_km = haversine_distance(min_lat, min_lon, max_lat, min_lon)
        area_km2 = width_km * height_km
        print(f"📐 Selected area: {area_km2:.1f} km²")
        
        # Enforce processing limits to prevent timeouts and excessive API costs
        if area_km2 > 10000:  # 10,000 km² limit
            return jsonify({
                'status': 'error',
                'message': f"Selected area is too large ({area_km2:.0f} km²). Please select a smaller area (max 10,000 km²)."
            }), 400
        
        # Dynamically adjust satellite data resolution based on area size
        # Smaller areas get higher resolution for better detail
        # Larger areas get lower resolution for faster processing
        if area_km2 < 100:  # Small area (< 100 km²)
            resolution = 20   # High resolution: 20m per pixel
        elif area_km2 < 1000:  # Medium area (100-1000 km²)
            resolution = 30   # Medium resolution: 30m per pixel
        elif area_km2 < 5000:  # Large area (1000-5000 km²)
            resolution = 60   # Lower resolution: 60m per pixel
        else:  # Very large area (5000-10000 km²)
            resolution = 100  # Lowest resolution: 100m per pixel
        
        print(f"🎯 Using resolution: {resolution}m per pixel for {area_km2:.1f} km² area")
        
        # =================================================================
        # STEP 3: SATELLITE DATA CONFIGURATION
        # =================================================================
        
        # Create bounding box for Sentinel Hub API
        bbox = create_bbox_from_coords(min_lon, min_lat, max_lon, max_lat)
            
        # Get Sentinel Hub configuration from environment variables
        sh_config = get_sh_config()
        
        # Validate Sentinel Hub credentials before proceeding
        if not sh_config.sh_client_id or not sh_config.sh_client_secret:
            return jsonify({
                'status': 'error',
                'message': 'Sentinel Hub credentials not configured. Please check your .env file.'
            }), 500
        
        print(f"✓ Sentinel Hub credentials loaded:")
        print(f"  Client ID: {sh_config.sh_client_id[:8]}***")
        print(f"  Client Secret: {sh_config.sh_client_secret[:8]}***")
        print(f"  Base URL: {sh_config.sh_base_url}")
        
        # =================================================================
        # STEP 4: DATE RANGE CALCULATION FOR SATELLITE DATA
        # =================================================================
        
        # Calculate optimal date ranges for satellite data acquisition
        # Uses historical dates with guaranteed satellite coverage to ensure data availability
        current_date = datetime.now()
        
        # Ensure we're not requesting future dates (satellite data not available)
        if current_date.year >= 2025:
            # Use known good dates from 2024 with excellent satellite coverage
            end_date = "2024-08-31"    # Late summer - clear skies, good data
            start_date = "2024-06-01"  # Early summer - start of growing season
            recent_date = "2024-08-15" # Mid-analysis period
        else:
            # Use recent dates but ensure they're not in the future
            end_date = current_date.strftime("%Y-%m-%d")
            start_date = (current_date - timedelta(days=90)).strftime("%Y-%m-%d")  # 3 months ago
            recent_date = (current_date - timedelta(days=30)).strftime("%Y-%m-%d") # 1 month ago
        
        print(f"📅 Date range for satellite data: {start_date} to {end_date} (focusing on {recent_date})")
        
        # =================================================================
        # STEP 5: MULTI-FACTOR SATELLITE DATA ACQUISITION
        # =================================================================
        
        # Track API performance and data availability
        failed_apis = []      # List of failed satellite data requests
        successful_data = {}  # Dictionary of successfully fetched data
        
        # Define comprehensive risk factor configuration
        # Each factor uses specific Sentinel-2 bands optimized for that risk type
        risk_factors_config = {
            'vegetation_health': {
                'fetch_fn': fetch_veg_health,
                'description': 'NDVI (Vegetation Health)',
                'bands': 'B08/B04',  # NIR/Red ratio - vegetation chlorophyll absorption
                'purpose': 'Detects healthy vs stressed/dead vegetation, fire risk indicator'
            },
            'water_stress': {
                'fetch_fn': fetch_water_stress,
                'description': 'NDMI (Water/Moisture Content)',
                'bands': 'B08/B11',  # NIR/SWIR ratio - water absorption in SWIR
                'purpose': 'Measures soil/vegetation moisture, drought conditions'
            },
            'urban_detection': {
                'fetch_fn': fetch_urban_detection,
                'description': 'NDBI (Built-up Areas)',
                'bands': 'B11/B08',  # SWIR/NIR ratio - built materials vs vegetation
                'purpose': 'Identifies buildings, roads, urban infrastructure density'
            },
            'burn_detection': {
                'fetch_fn': fetch_burn_detection,
                'description': 'NBR (Burn Areas)',
                'bands': 'B08/B12',  # NIR/SWIR2 ratio - burn scar detection
                'purpose': 'Detects recent fires, burn scars, fire damage assessment'
            },
            'roof_detection': {
                'fetch_fn': fetch_roof_detection,
                'description': 'Roof Material Analysis',
                'bands': 'B02,B04,B08,B11',  # Blue,Red,NIR,SWIR - multi-spectral analysis
                'purpose': 'Analyzes roof materials, structural vulnerability'
            },
            'drainage_detection': {
                'fetch_fn': fetch_drainage_detection,
                'description': 'Drainage Pattern Analysis',
                'bands': 'B08,B04,B11',  # NIR,Red,SWIR - water flow and pooling
                'purpose': 'Identifies poor drainage, flood risk areas'
            }
        }
        
        # Fetch satellite data for each risk factor
        print(f"🛰️ Fetching satellite data for {len(risk_factors_config)} risk factors...")
        for factor_name, config in risk_factors_config.items():
            try:
                print(f"  📡 Fetching {config['description']} using bands {config['bands']}...")
                print(f"      Purpose: {config['purpose']}")
                
                # Call the specialized fetch function with proper parameters
                # Parameter order: bbox, start_date, end_date, sh_config, resolution
                data_result = config['fetch_fn'](bbox, start_date, end_date, sh_config, resolution)
                
                if data_result and len(data_result) > 0:
                    successful_data[factor_name] = data_result
                    print(f"  ✅ Successfully fetched {factor_name}")
                else:
                    print(f"  ❌ No data returned for {factor_name}")
                    failed_apis.append(config['description'])
                    successful_data[factor_name] = generate_simple_fallback(bbox=bbox)
                    
            except Exception as e:
                print(f"  ❌ Failed to fetch {factor_name}: {str(e)}")
                print(f"      Error type: {type(e).__name__}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"      HTTP status: {e.response.status_code}")
                    try:
                        error_detail = e.response.json()
                        print(f"      API response: {error_detail}")
                    except:
                        print(f"      Response text: {e.response.text[:200]}...")
                
                # Add to failed list and use fallback data
                failed_apis.append(config['description'])
                successful_data[factor_name] = generate_simple_fallback(bbox=bbox)
        
        # Check if we have any real satellite data
        if len(failed_apis) == len(risk_factors_config):
            return jsonify({
                'status': 'error',
                'message': 'Unable to fetch any satellite data. Please check your Sentinel Hub credentials and try again.'
            }), 500
        
        # =================================================================
        # STEP 6: RISK CALCULATION AND PROCESSING
        # =================================================================
        
        # Process satellite indices into risk scores using advanced algorithms
        print("🔄 Processing satellite indices into risk scores...")
        composite_risk, index_values, risk_values = process_risk_data(
            successful_data.get('vegetation_health'),  # NDVI data
            successful_data.get('water_stress'),       # NDMI data
            successful_data.get('urban_detection'),    # NDBI data
            successful_data.get('burn_detection'),     # NBR data
            successful_data.get('roof_detection'),     # Multi-band roof analysis
            successful_data.get('drainage_detection')  # Multi-band drainage analysis
        )
        
        # =================================================================
        # STEP 7: VISUALIZATION GENERATION
        # =================================================================
        
        # Generate color-coded visualizations for all risk factors
        print("🎨 Generating risk visualizations...")
        images = {}
        
        # Overall composite risk visualization (1-10 scale with red-green gradient)
        images['risk_map'] = risk_score_to_image(composite_risk, scale_max=10)
        
        # Individual factor visualizations with specialized color schemes
        # Each visualization uses colors optimized for the specific data type
        visualization_config = {
            'vegetation_health': {
                'color': 'green',           # Green scale - healthy vegetation is green
                'range': (-1, 1),           # NDVI ranges from -1 to +1
                'description': 'Green = healthy vegetation, Red = stressed/dead vegetation'
            },
            'water_stress': {
                'color': 'blue',            # Blue scale - water content visualization
                'range': (-1, 1),           # NDMI ranges from -1 to +1
                'description': 'Blue = high moisture, Red = dry conditions'
            },
            'urban_detection': {
                'color': 'purple',          # Purple scale - urban areas
                'range': (-1, 1),           # NDBI ranges from -1 to +1
                'description': 'Purple = built-up areas, Dark = vegetation/water'
            },
            'burn_detection': {
                'color': 'red',             # Red scale - fire/burn damage
                'range': (-1, 1),           # NBR ranges from -1 to +1
                'description': 'Red = recent burns/fire damage, Green = unburned areas'
            },
            'roof_detection': {
                'color': 'heat',            # Heat map - roof vulnerability
                'range': None,              # Dynamic range based on calculated values
                'description': 'Heat map of roof material vulnerability'
            },
            'drainage_detection': {
                'color': 'blue_to_brown',   # Blue (wet) to brown (dry) gradient
                'range': (-1, 1),           # Custom drainage index range
                'description': 'Blue = good drainage, Brown = poor drainage/flood risk'
            }
        }
        
        # Generate individual factor visualizations
        for factor_name, viz_config in visualization_config.items():
            if factor_name in successful_data:
                # Extract the primary data channel (channel 0) from satellite data
                factor_img = successful_data[factor_name][0][:, :, 0]
                
                if viz_config['range']:
                    # Use specified value range for normalization
                    min_val, max_val = viz_config['range']
                    images[factor_name] = array_to_image(
                        factor_img, viz_config['color'], 
                        normalize=True, min_val=min_val, max_val=max_val
                    )
                else:
                    # Use dynamic range based on actual data values
                    images[factor_name] = array_to_image(
                        factor_img, viz_config['color'], normalize=True
                    )
                
                print(f"  ✅ Generated visualization for {factor_name}")
        
        # =================================================================
        # STEP 8: RESPONSE FORMATTING AND METADATA
        # =================================================================
        
        # Create comprehensive status message
        if failed_apis:
            failed_str = ", ".join(failed_apis)
            message = f'Analysis complete. Note: {failed_str} used placeholder data due to API issues.'
            status_warning = True
            using_fallback = True
        else:
            message = 'Analysis complete using real satellite data.'
            status_warning = False
            using_fallback = False
        
        print(f"📊 Analysis complete! Composite risk score: {np.nanmean(composite_risk):.1f}/10")
        
        # Return comprehensive analysis results
        return jsonify({
            'status': 'success',
            'message': message,
            'has_warnings': status_warning,
            'failed_apis': failed_apis,
            'using_fallback': using_fallback,
            
            # VISUALIZATION DATA
            'risk_image': images['risk_map'],           # Overall risk heatmap
            'factor_images': images,                    # Individual factor visualizations
            
            # NUMERICAL DATA
            'index_values': sanitize_for_json(index_values),  # Raw satellite indices
            'risk_values': sanitize_for_json(risk_values),    # Processed risk scores
            
            # METADATA
            'area_info': {
                'coordinates': {
                    'min_lon': float(min_lon),
                    'min_lat': float(min_lat),
                    'max_lon': float(max_lon),
                    'max_lat': float(max_lat)
                },
                'area_km2': round(area_km2, 1),
                'resolution_m': int(resolution),
                'analysis_date': end_date,
                'data_period': f"{start_date} to {end_date}"
            }
        })
    
    except Exception as e:
        print(f"Error in analyze route: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'Analysis failed: {str(e)}'
        }), 500

# =============================================================================
# TIME SERIES AND TREND ANALYSIS
# =============================================================================

@app.route('/analyze_trends', methods=['POST'])
@login_required
def analyze_trends():
    """
    Process comprehensive trend analysis over user-defined time periods.
    
    TIME SERIES ANALYSIS OVERVIEW:
    This function performs temporal risk analysis by breaking down a date range into
    discrete time periods and analyzing each period independently. The results show
    how risk factors evolve over time, revealing seasonal patterns, environmental
    changes, and long-term trends.
    
    TREND ANALYSIS PIPELINE:
    
    1. TIME PERIOD SEGMENTATION
       - User provides start date, end date, and analysis interval
       - System splits date range into overlapping analysis periods
       - Each period represents a discrete temporal snapshot
    
    2. TEMPORAL DATA ACQUISITION
       - For each time period: fetch satellite data from all risk factors
       - Handle seasonal variations in data availability
       - Apply fallback strategies for periods with missing data
    
    3. MULTI-TEMPORAL PROCESSING
       - Process each time period using same algorithms as current analysis
       - Generate risk scores for each temporal snapshot
       - Maintain consistent methodology across all time periods
    
    4. TREND CALCULATION
       - Compare risk levels across time periods
       - Calculate statistical trends (increasing, decreasing, stable)
       - Identify seasonal patterns and anomalies
    
    5. VISUALIZATION GENERATION
       - Create trend charts showing risk evolution
       - Generate heatmaps for each time period
       - Provide comparative visualizations
    
    TEMPORAL CONSIDERATIONS:
    - Satellite data availability varies by season and location
    - Cloud cover affects data quality in certain periods
    - Some indices (e.g., vegetation) show strong seasonal cycles
    - Analysis intervals should align with environmental cycles
    
    USE CASES:
    - Insurance premium adjustment based on historical trends
    - Seasonal risk assessment for agricultural areas
    - Climate change impact analysis
    - Post-disaster recovery monitoring
    - Long-term environmental monitoring
    """
    try:
        # Get data from request
        data = request.json
        bounds = data.get('bounds')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        interval_months = data.get('interval_months', 6)
        
        if not bounds or len(bounds) != 2:
            return jsonify({
                'status': 'error',
                'message': 'Invalid bounds provided. Please select an area on the map.'
            }), 400
        
        if not start_date or not end_date:
            return jsonify({
                'status': 'error',
                'message': 'Start date and end date are required for trend analysis.'
            }), 400
        
        # Extract and validate coordinates
        min_lon, min_lat = bounds[0]
        max_lon, max_lat = bounds[1]
        
        # Basic coordinate validation
        if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180 and
                -90 <= min_lat <= 90 and -90 <= max_lat <= 90):
            return jsonify({
                'status': 'error',
                'message': 'Invalid coordinates. Please select a valid area on Earth.'
            }), 400
        
        if min_lon >= max_lon or min_lat >= max_lat:
            return jsonify({
                'status': 'error',
                'message': 'Invalid area selection. Please ensure proper bounds.'
            }), 400
        
        # Parse dates
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                'status': 'error',
                'message': 'Invalid date format. Please use YYYY-MM-DD format.'
            }), 400
        
        if start_dt >= end_dt:
            return jsonify({
                'status': 'error',
                'message': 'Start date must be before end date.'
            }), 400
        
        # Ensure dates are not in the future - adjust if necessary
        current_date = datetime.now()
        if end_dt > current_date:
            print(f"⚠️ End date {end_date} is in the future, adjusting to current date")
            end_dt = current_date
            end_date = end_dt.strftime('%Y-%m-%d')
        
        if start_dt > current_date:
            print(f"⚠️ Start date {start_date} is in the future, adjusting to 2 years ago")
            start_dt = current_date - timedelta(days=730)  # 2 years ago
            start_date = start_dt.strftime('%Y-%m-%d')
        
        # Additional check: if the range is too recent, use known good dates
        if end_dt.year >= 2025 or (end_dt.year == 2024 and end_dt.month >= 12):
            print("⚠️ Using safe historical dates for satellite data availability")
            end_dt = datetime(2024, 8, 31)
            start_dt = datetime(2023, 6, 1)
            end_date = end_dt.strftime('%Y-%m-%d')
            start_date = start_dt.strftime('%Y-%m-%d')
        
        print(f"📅 Final date range: {start_date} to {end_date}")
        
        # Calculate the area size in square kilometers
        width_km = haversine_distance(min_lat, min_lon, min_lat, max_lon)
        height_km = haversine_distance(min_lat, min_lon, max_lat, min_lon)
        area_km2 = width_km * height_km
        print(f"Selected area for trend analysis: {area_km2:.1f} km²")
        
        # Check if area is too large
        if area_km2 > 5000:  # Smaller limit for trend analysis due to multiple requests
            return jsonify({
                'status': 'error',
                'message': f"Selected area is too large for trend analysis ({area_km2:.0f} km²). Please select a smaller area (max 5,000 km²)."
            }), 400
        
        # Adjust resolution based on area size
        if area_km2 < 100:  # Small area
            resolution = 30
        elif area_km2 < 1000:  # Medium area
            resolution = 60
        else:  # Large area
            resolution = 100
        
        print(f"Using resolution: {resolution}m for trend analysis of {area_km2:.1f} km² area")
        
        # Create bounding box
        bbox = create_bbox_from_coords(min_lon, min_lat, max_lon, max_lat)
        
        # Get Sentinel Hub configuration
        sh_config = get_sh_config()
        
        # Validate SH credentials
        if not sh_config.sh_client_id or not sh_config.sh_client_secret:
            return jsonify({
                'status': 'error',
                'message': 'Sentinel Hub credentials not configured. Please check your .env file.'
            }), 500
        
        print(f"✓ Sentinel Hub credentials loaded for trend analysis")
        
        # =================================================================
        # TIME PERIOD SEGMENTATION AND TEMPORAL ANALYSIS SETUP
        # =================================================================
        
        # Generate discrete time periods for trend analysis
        # ALGORITHM:
        # 1. Start from user-provided start date
        # 2. Create analysis periods of 3 months duration each
        # 3. Advance by user-specified interval (3, 6, or 12 months)
        # 4. Continue until end date is reached
        
        time_periods = []
        current_dt = start_dt
        
        print(f"📅 Generating time periods with {interval_months}-month intervals...")
        
        while current_dt <= end_dt:
            # Calculate end of current analysis period (3 months of data)
            period_end = current_dt + relativedelta(months=3)
            if period_end > end_dt:
                period_end = end_dt  # Don't exceed user-specified end date
            
            # Create time period definition for this analysis window
            time_periods.append({
                'start': current_dt.strftime('%Y-%m-%d'),           # Period start date
                'end': period_end.strftime('%Y-%m-%d'),             # Period end date  
                'analysis_date': period_end.strftime('%Y-%m-%d')    # Representative date for this period
            })
            
            # Advance to next analysis period based on user interval
            current_dt += relativedelta(months=interval_months)
        
        print(f"📊 Generated {len(time_periods)} time periods for analysis:")
        for i, period in enumerate(time_periods):
            print(f"  Period {i+1}: {period['start']} to {period['end']} (focus: {period['analysis_date']})")
        
        # =================================================================
        # MULTI-TEMPORAL RISK ANALYSIS PROCESSING
        # =================================================================
        
        # Initialize trend analysis results storage
        trend_data = []  # Results for each time period
        
        # Process each time period independently using same methodology as current analysis
        for i, period in enumerate(time_periods):
            print(f"\n🔍 ANALYZING PERIOD {i+1}/{len(time_periods)}")
            print(f"   📅 Date Range: {period['start']} to {period['end']}")
            print(f"   🎯 Focus Date: {period['analysis_date']}")
            
            try:
                # =============================================================
                # TEMPORAL SATELLITE DATA ACQUISITION
                # =============================================================
                
                # Track data availability for this specific time period
                failed_apis = []      # APIs that failed for this period
                successful_data = {}  # Successfully fetched data for this period
                
                # Define same risk factors as current analysis for consistency
                risk_factors_config = {
                    'vegetation_health': {
                        'fetch_fn': fetch_veg_health,
                        'description': 'NDVI (Vegetation Health)',
                        'bands': 'B08/B04',
                        'purpose': 'Temporal vegetation health trends'
                    },
                    'water_stress': {
                        'fetch_fn': fetch_water_stress,
                        'description': 'NDMI (Water/Moisture Content)',
                        'bands': 'B08/B11',
                        'purpose': 'Seasonal moisture patterns'
                    },
                    'urban_detection': {
                        'fetch_fn': fetch_urban_detection,
                        'description': 'NDBI (Built-up Areas)',
                        'bands': 'B11/B08',
                        'purpose': 'Urban development tracking'
                    },
                    'burn_detection': {
                        'fetch_fn': fetch_burn_detection,
                        'description': 'NBR (Burn Areas)',
                        'bands': 'B08/B12',
                        'purpose': 'Fire incident temporal tracking'
                    },
                    'roof_detection': {
                        'fetch_fn': fetch_roof_detection,
                        'description': 'Roof Material Analysis',
                        'bands': 'B02,B04,B08,B11',
                        'purpose': 'Infrastructure degradation over time'
                    },
                    'drainage_detection': {
                        'fetch_fn': fetch_drainage_detection,
                        'description': 'Drainage Pattern Analysis',
                        'bands': 'B08,B04,B11',
                        'purpose': 'Seasonal drainage pattern changes'
                    }
                }
                
                # Fetch satellite data for each risk factor in this time period
                print(f"   🛰️ Fetching satellite data for {len(risk_factors_config)} factors...")
                for factor_name, config in risk_factors_config.items():
                    try:
                        print(f"     📡 {config['description']} ({config['bands']}) - {config['purpose']}")
                        
                        # Fetch data for this specific time period
                        # Same parameter order as current analysis: bbox, start, end, config, resolution
                        result = config['fetch_fn'](
                            bbox,
                            period['start'],     # Time period specific start date
                            period['end'],       # Time period specific end date
                            sh_config,
                            resolution
                        )
                        
                        if result and len(result) > 0:
                            successful_data[factor_name] = result
                            print(f"     ✅ Success: {factor_name} for period {period['analysis_date']}")
                        else:
                            failed_apis.append(factor_name)
                            print(f"     ❌ No data: {factor_name} for period {period['analysis_date']}")
                            # Use fallback data to maintain analysis consistency
                            successful_data[factor_name] = generate_simple_fallback(bbox=bbox)
                    
                    except Exception as e:
                        failed_apis.append(factor_name)
                        print(f"     ❌ Error: {factor_name} for period {period['analysis_date']}: {str(e)}")
                        # Use fallback data to ensure temporal series continuity
                        successful_data[factor_name] = generate_simple_fallback(bbox=bbox)
                
                # Process the data for this period
                if successful_data:
                    print(f"  🔄 Processing risk data for {period['analysis_date']}...")
                    
                    # Process data using risk calculation
                    composite_risk, index_values, risk_values = process_risk_data(
                        successful_data.get('vegetation_health'),
                        successful_data.get('water_stress'), 
                        successful_data.get('urban_detection'),
                        successful_data.get('burn_detection'), 
                        successful_data.get('roof_detection'), 
                        successful_data.get('drainage_detection')
                    )
                    
                    # Generate visualization images
                    images = {}
                    
                    # Overall composite risk visualization (1-10 scale)
                    images['risk_map'] = risk_score_to_image(composite_risk, scale_max=10)
                    
                    # Individual factor visualizations
                    visualization_config = {
                        'vegetation_health': {'color': 'green', 'range': (-1, 1)},
                        'water_stress': {'color': 'blue', 'range': (-1, 1)},
                        'urban_detection': {'color': 'purple', 'range': (-1, 1)},
                        'burn_detection': {'color': 'red', 'range': (-1, 1)},
                        'roof_detection': {'color': 'heat', 'range': None},
                        'drainage_detection': {'color': 'blue_to_brown', 'range': (-1, 1)}
                    }
                    
                    for factor_name, viz_config in visualization_config.items():
                        if factor_name in successful_data:
                            factor_img = successful_data[factor_name][0][:, :, 0]
                            if viz_config['range']:
                                min_val, max_val = viz_config['range']
                                images[factor_name] = array_to_image(
                                    factor_img, viz_config['color'], 
                                    normalize=True, min_val=min_val, max_val=max_val
                                )
                            else:
                                images[factor_name] = array_to_image(
                                    factor_img, viz_config['color'], normalize=True
                                )
                    
                    # Store results for this period
                    period_result = {
                        'analysis_date': period['analysis_date'],
                        'data_period': f"{period['start']} to {period['end']}",
                        'composite_risk': float(np.nanmean(composite_risk)) if not np.isnan(np.nanmean(composite_risk)) else 5.0,
                        'index_values': sanitize_for_json(index_values),
                        'risk_values': sanitize_for_json(risk_values),
                        'risk_image': images['risk_map'],
                        'factor_images': images,
                        'area_info': {
                            'coordinates': {
                                'min_lon': float(min_lon),
                                'min_lat': float(min_lat),
                                'max_lon': float(max_lon),
                                'max_lat': float(max_lat)
                            },
                            'area_km2': round(area_km2, 1),
                            'resolution_m': int(resolution)
                        },
                        'failed_apis': failed_apis,
                        'using_fallback': len(failed_apis) > 0
                    }
                    
                    trend_data.append(period_result)
                    print(f"  ✅ Completed analysis for {period['analysis_date']} - Risk: {period_result['composite_risk']:.1f}")
                
                else:
                    print(f"  ⚠️ No data available for period {period['analysis_date']}")
            
            except Exception as e:
                print(f"  ❌ Error analyzing period {period['analysis_date']}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        if not trend_data:
            return jsonify({
                'status': 'error',
                'message': 'No data could be retrieved for any time period. Please try a different date range or check your Sentinel Hub credentials.'
            }), 500
        
        print(f"📈 Trend analysis completed: {len(trend_data)} periods analyzed")
        
        # Return trend analysis results
        return jsonify({
            'status': 'success',
            'analysis_type': 'trend',
            'trend_data': trend_data,
            'summary': {
                'total_periods': len(trend_data),
                'date_range': f"{start_date} to {end_date}",
                'interval_months': interval_months,
                'area_km2': round(area_km2, 1)
            }
        })
    
    except Exception as e:
        print(f"Error in analyze_trends route: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'Trend analysis failed: {str(e)}'
        }), 500

@app.route('/download_report', methods=['POST'])
@login_required
def download_report():
    """Generate and download a PDF report of the analysis results."""
    try:
        print("🔄 PDF download request received")
        
        # Get data from request
        data = request.json
        print(f"🔄 Request data keys: {list(data.keys()) if data else 'None'}")
        
        if not data:
            print("❌ No analysis data provided")
            return jsonify({
                'status': 'error',
                'message': 'No analysis data provided for report generation.'
            }), 400
        
        analysis_type = data.get('analysis_type', 'current')
        print(f"🔄 Analysis type: {analysis_type}")
        
        # Generate PDF
        print("🔄 Starting PDF generation...")
        pdf_buffer = generate_pdf_report(data)
        print("✅ PDF generation completed")
        
        # Generate filename with timestamp and analysis type
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"customsat_{analysis_type}_analysis_{timestamp}.pdf"
        print(f"🔄 Generated filename: {filename}")
        
        print("🔄 Sending file response...")
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    
    except Exception as e:
        print(f"❌ Error generating PDF report: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'Failed to generate PDF report: {str(e)}'
        }), 500

def generate_pdf_report(data):
    """Generate a comprehensive PDF report from analysis data."""
    from io import BytesIO
    buffer = BytesIO()
    
    # Create the PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Create custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=20,
        spaceAfter=30,
        textColor=colors.HexColor('#0066cc'),
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        spaceBefore=20,
        textColor=colors.HexColor('#1a1a1a')
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=14,
        spaceAfter=8,
        spaceBefore=15,
        textColor=colors.HexColor('#4b5563')
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6,
        leading=14
    )
    
    # Build the document content
    story = []
    
    # Determine report type and data FIRST
    is_trend = data.get('analysis_type') == 'trend'
    
    # DEBUG: Print the data structure for debugging
    print(f"🔍 PDF Generation Debug - is_trend: {is_trend}")
    print(f"🔍 Data keys: {list(data.keys())}")
    if is_trend and 'trend_data' in data:
        print(f"🔍 Trend data length: {len(data['trend_data'])}")
        if data['trend_data']:
            latest = data['trend_data'][-1]
            print(f"🔍 Latest trend data keys: {list(latest.keys())}")
            print(f"🔍 Latest composite_risk: {latest.get('composite_risk', 'NOT_FOUND')}")
            print(f"🔍 Latest area_info keys: {list(latest.get('area_info', {}).keys())}")
    else:
        print(f"🔍 Current analysis composite_risk: {data.get('index_values', {}).get('composite_risk', 'NOT_FOUND')}")
    
    # Determine report type for title
    if is_trend:
        title_text = "CustomSat Insurance Risk Trend Analysis Report"
        report_type_text = "Multi-Period Risk Evolution Analysis"
    else:
        title_text = "CustomSat Insurance Risk Assessment Report"
        report_type_text = "Point-in-Time Risk Analysis"
    
    # Title
    story.append(Paragraph(title_text, title_style))
    story.append(Paragraph(report_type_text, ParagraphStyle('Subtitle', parent=styles['Normal'], 
                                                           fontSize=14, alignment=TA_CENTER, 
                                                           textColor=colors.HexColor('#666666'), 
                                                           spaceAfter=20)))
    
    # Report metadata
    report_date = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    story.append(Paragraph(f"<b>Report Generated:</b> {report_date}", body_style))
    
    if is_trend:
        periods_analyzed = len(data.get('trend_data', []))
        story.append(Paragraph(f"<b>Analysis Periods:</b> {periods_analyzed} time periods analyzed", body_style))
        story.append(Paragraph(f"<b>Date Range:</b> {data.get('summary', {}).get('date_range', 'N/A')}", body_style))
    
    story.append(Spacer(1, 20))
    
    # Extract data based on report type
    if is_trend and 'trend_data' in data:
        # Use latest data point for coordinates
        latest_data = data['trend_data'][-1] if data['trend_data'] else {}
        coords = latest_data.get('area_info', {}).get('coordinates', {})
        area_info = latest_data.get('area_info', {})
        risk_values = latest_data.get('risk_values', {})
        index_values = latest_data.get('index_values', {})
        total_risk = latest_data.get('composite_risk', 0)
    else:
        coords = data.get('area_info', {}).get('coordinates', {})
        area_info = data.get('area_info', {})
        risk_values = data.get('risk_values', {})
        index_values = data.get('index_values', {})
        total_risk = index_values.get('composite_risk', data.get('composite_risk', 0))
    
    # Area Information Section
    story.append(Paragraph("Area Information", heading_style))
    
    area_data = [
        ['Property', 'Value'],
        ['Coordinates', f"{coords.get('min_lat', 0):.4f}°N, {coords.get('min_lon', 0):.4f}°E to {coords.get('max_lat', 0):.4f}°N, {coords.get('max_lon', 0):.4f}°E"],
        ['Area Size', f"{area_info.get('area_km2', 0)} km²"],
        ['Analysis Resolution', f"{area_info.get('resolution_m', 0)} meters"],
        ['Analysis Date', area_info.get('analysis_date', 'N/A')],
        ['Data Period', area_info.get('data_period', 'N/A')]
    ]
    
    if is_trend:
        area_data.append(['Analysis Type', f"Trend Analysis ({len(data.get('trend_data', []))} time periods)"])
        area_data.append(['Date Range', data.get('summary', {}).get('date_range', 'N/A')])
    else:
        area_data.append(['Analysis Type', 'Current Point-in-Time Analysis'])
    
    area_table = Table(area_data, colWidths=[4*cm, 12*cm])
    area_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e6f2ff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0066cc')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    story.append(area_table)
    story.append(Spacer(1, 20))
    
    # Risk Summary Section
    story.append(Paragraph("Risk Assessment Summary", heading_style))
    
    # Overall risk assessment
    risk_level = get_risk_level_text(total_risk)
    story.append(Paragraph(f"<b>Overall Risk Level:</b> {total_risk:.1f}/10 ({risk_level})", body_style))
    story.append(Spacer(1, 10))
    
    # Risk factors table
    risk_data = [['Risk Factor', 'Score', 'Level', 'Description']]
    
    if risk_values:
        factors = [
            ('Vegetation Health', risk_values.get('vegetation_health', 0), 'Plant health and vegetation density'),
            ('Water Stress', risk_values.get('water_stress', 0), 'Moisture content and water availability'),
            ('Urban Development', risk_values.get('urban_areas', 0), 'Built-up areas and infrastructure density'),
            ('Fire Risk', risk_values.get('burn_areas', 0), 'Fire damage and burn scar detection'),
            ('Roof Vulnerability', risk_values.get('roof_risk', 0), 'Roof material and structural assessment'),
            ('Drainage Issues', risk_values.get('drainage_risk', 0), 'Water drainage and flood risk')
        ]
        
        for factor_name, score, description in factors:
            level = get_risk_level_text(score)
            risk_data.append([factor_name, f"{score:.1f}/10", level, description])
    
    risk_table = Table(risk_data, colWidths=[4*cm, 2*cm, 2.5*cm, 7.5*cm])
    risk_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e6f2ff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0066cc')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    story.append(risk_table)
    story.append(Spacer(1, 20))
    
    # Track temporary files for cleanup
    temp_files_to_cleanup = []
    
    # Trend Analysis Section (if applicable) - SIMPLIFIED VERSION
    if is_trend and 'trend_data' in data:
        story.append(PageBreak())  # Start trend analysis on new page
        story.append(Paragraph("Trend Analysis Results", heading_style))
        
        # Simple trend summary
        trend_summary = get_trend_summary(data['trend_data'])
        story.append(Paragraph(trend_summary, body_style))
        story.append(Spacer(1, 15))
        
        # Simple trend data table instead of charts
        story.append(Paragraph("Risk Evolution Over Time", subheading_style))
        
        trend_table_data = [['Date', 'Overall Risk', 'Vegetation', 'Water Stress', 'Fire Risk']]
        for period in data['trend_data']:
            date = period.get('analysis_date', 'N/A')
            overall = f"{period.get('composite_risk', 0):.1f}"
            veg = f"{period.get('risk_values', {}).get('vegetation_health', 0):.1f}"
            water = f"{period.get('risk_values', {}).get('water_stress', 0):.1f}"
            fire = f"{period.get('risk_values', {}).get('burn_areas', 0):.1f}"
            trend_table_data.append([date, overall, veg, water, fire])
        
        trend_table = Table(trend_table_data, colWidths=[3*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm])
        trend_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e6f2ff')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0066cc')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        story.append(trend_table)
        story.append(Spacer(1, 15))
        
        # Simple text analysis instead of complex charts
        story.append(Paragraph("Key Findings", subheading_style))
        
        if len(data['trend_data']) >= 2:
            first_risk = data['trend_data'][0]['composite_risk']
            last_risk = data['trend_data'][-1]['composite_risk']
            change = last_risk - first_risk
            
            if change > 0.5:
                trend_text = f"Risk has increased by {change:.1f} points over the analysis period."
            elif change < -0.5:
                trend_text = f"Risk has decreased by {abs(change):.1f} points over the analysis period."
            else:
                trend_text = "Risk levels have remained relatively stable over the analysis period."
            
            story.append(Paragraph(trend_text, body_style))
            story.append(Spacer(1, 10))
            
            # Add simple recommendations
            story.append(Paragraph("• Monitor areas with increasing risk trends", body_style))
            story.append(Paragraph("• Consider seasonal patterns in risk assessment", body_style))
            story.append(Paragraph("• Review coverage for high-risk periods", body_style))
        
        story.append(Spacer(1, 15))
    
    # Technical Details Section
    story.append(Paragraph("Technical Details", heading_style))
    
    if index_values:
        tech_details = []
        if 'vegetation_health' in index_values:
            vh = index_values['vegetation_health']
            tech_details.append(f"<b>NDVI (Vegetation Health):</b> {vh.get('raw_ndvi', 0):.3f} - {vh.get('interpretation', 'N/A')}")
        
        if 'water_stress' in index_values:
            ws = index_values['water_stress']
            tech_details.append(f"<b>NDMI (Water Stress):</b> {ws.get('raw_ndmi', 0):.3f} - {ws.get('interpretation', 'N/A')}")
        
        if 'urban_areas' in index_values:
            ua = index_values['urban_areas']
            tech_details.append(f"<b>NDBI (Urban Areas):</b> {ua.get('raw_ndbi', 0):.3f} - {ua.get('interpretation', 'N/A')}")
        
        if 'burn_areas' in index_values:
            ba = index_values['burn_areas']
            tech_details.append(f"<b>NBR (Burn Areas):</b> {ba.get('raw_nbr', 0):.3f} - {ba.get('interpretation', 'N/A')}")
        
        for detail in tech_details:
            story.append(Paragraph(detail, body_style))
            story.append(Spacer(1, 5))
    
    story.append(Spacer(1, 15))
    
    # Recommendations Section
    story.append(Paragraph("Risk Management Recommendations", heading_style))
    recommendations = generate_recommendations(total_risk, risk_values, index_values)
    for rec in recommendations:
        story.append(Paragraph(f"• {rec}", body_style))
        story.append(Spacer(1, 3))
    
    story.append(Spacer(1, 20))
    
    # Footer
    story.append(Paragraph("This report was generated by CustomSat Insurance Risk Analysis platform using Sentinel-2 satellite data.", 
                          ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=TA_CENTER)))
    
    # Build PDF
    print("🔄 Starting PDF document build...")
    print(f"🔄 Story has {len(story)} elements")
    try:
        doc.build(story)
        print("✅ PDF document built successfully")
    except Exception as e:
        print(f"❌ Error building PDF document: {e}")
        import traceback
        traceback.print_exc()
        raise e
    
    print("🔄 Seeking buffer to beginning...")
    buffer.seek(0)
    print(f"✅ Buffer position reset, buffer size: {len(buffer.getvalue())} bytes")
    
    # Clean up temporary chart files after PDF is built
    print(f"🔄 Cleaning up {len(temp_files_to_cleanup)} temporary files...")
    for temp_file in temp_files_to_cleanup:
        try:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
                print(f"✅ Cleaned up temporary file: {temp_file}")
        except Exception as e:
            print(f"⚠️ Could not clean up temporary file {temp_file}: {e}")
    
    print("✅ PDF generation completed successfully")
    return buffer

def get_risk_level_text(score):
    """Convert numeric risk score to descriptive text."""
    if score < 3:
        return "Low Risk"
    elif score < 6:
        return "Moderate Risk"
    elif score < 8:
        return "High Risk"
    else:
        return "Critical Risk"

def get_trend_summary(trend_data):
    """Generate a summary of trend analysis."""
    if len(trend_data) < 2:
        return "Insufficient data for trend analysis."
    
    first_risk = trend_data[0]['composite_risk']
    last_risk = trend_data[-1]['composite_risk']
    change = last_risk - first_risk
    
    if abs(change) < 0.5:
        trend_text = "Risk levels have remained relatively stable over the analysis period."
    elif change > 0:
        trend_text = f"Risk levels have increased by {change:.1f} points ({((change/first_risk)*100):.1f}%) over the analysis period."
    else:
        trend_text = f"Risk levels have decreased by {abs(change):.1f} points ({((abs(change)/first_risk)*100):.1f}%) over the analysis period."
    
    # Add seasonality insights
    risks = [item['composite_risk'] for item in trend_data]
    max_risk = max(risks)
    min_risk = min(risks)
    avg_risk = sum(risks) / len(risks)
    
    summary = f"{trend_text} The analysis period shows an average risk of {avg_risk:.1f}, with values ranging from {min_risk:.1f} to {max_risk:.1f}."
    
    return summary

def generate_recommendations(total_risk, risk_values, index_values):
    """Generate risk management recommendations based on analysis."""
    recommendations = []
    
    # Overall risk recommendations
    if total_risk > 7:
        recommendations.append("Immediate attention required due to high overall risk levels.")
        recommendations.append("Consider comprehensive risk mitigation strategies.")
    elif total_risk > 5:
        recommendations.append("Moderate risk levels detected - implement preventive measures.")
    else:
        recommendations.append("Low risk levels detected - maintain current monitoring practices.")
    
    # Specific factor recommendations
    if risk_values:
        if risk_values.get('vegetation_health', 0) > 6:
            recommendations.append("Poor vegetation health detected - consider fire prevention measures.")
        
        if risk_values.get('water_stress', 0) > 6:
            recommendations.append("High water stress identified - monitor drought conditions and water supply.")
        
        if risk_values.get('burn_areas', 0) > 6:
            recommendations.append("Fire risk detected - review fire safety protocols and insurance coverage.")
        
        if risk_values.get('roof_risk', 0) > 6:
            recommendations.append("Roof vulnerability identified - consider structural assessments and improvements.")
        
        if risk_values.get('drainage_risk', 0) > 6:
            recommendations.append("Drainage issues detected - assess flood risk and drainage infrastructure.")
    
    # General recommendations
    recommendations.append("Regular monitoring recommended using satellite-based risk assessment.")
    recommendations.append("Consider updating insurance coverage based on identified risk factors.")
    
    return recommendations

# Initialize Gemini client
api_token = os.getenv("GOOGLE_API_KEY")
#print(os.getenv("GOOGLE_API_KEY"))
if not api_token:
    print("Warning: GOOGLE_API_KEY not found in environment variables")
    model = None
else:
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_token)
        
        
        # List available models for debugging
        '''
        print("Available models:")
        for m in genai.list_models():
            print(f"- {m.name}")
        '''
        # Use the latest stable version of Gemini Pro
        model = genai.GenerativeModel('models/gemini-2.0-flash')
        print("Successfully initialized Gemini client")
    except Exception as e:
        print(f"Error initializing Gemini client: {str(e)}")
        model = None

@app.route('/get_ai_interpretation', methods=['POST'])
@login_required
def get_ai_interpretation():
    """Generate AI interpretation of risk assessment using Gemini."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Extract risk values from the request
        risk_values = data.get('risk_values', {})
        if not risk_values:
            return jsonify({'error': 'No risk values provided'}), 400

        # Calculate total risk as average of all risk factors
        total_risk = sum(risk_values.values()) / len(risk_values) if risk_values else 0

        # Construct the prompt for Gemini
        prompt = f"""You are an expert insurance risk analyst. Please provide a precise and concise interpretation of the following risk assessment data, specifically focused on informing insurance underwriting and premium pricing decisions. Address these points clearly:

A brief overview of the overall risk level and its potential impact on insurance liability.

Key concerns based on individual risk factors that would influence coverage terms or premiums.

Specific, actionable risk mitigation recommendations that could reduce insurance risk or costs.

Notable patterns or interactions between risk factors that might amplify overall risk exposure.

Keep your analysis focused, relevant to an insurer's perspective, and no longer than 250 words. :

Area Information:
- Location: {data.get('location', 'Unknown')}
- Date: {data.get('date', 'Unknown')}

Risk Assessment Results:
- Total Risk Score: {total_risk:.2f}
- Individual Risk Factors:
{chr(10).join(f'- {factor}: {value:.2f}' for factor, value in risk_values.items())}

Please provide a detailed analysis of these risk levels and specific recommendations for risk mitigation."""

        # Check if Gemini model is available
        if not model:
            print("Gemini model not available, using fallback interpretation")
            interpretation = generate_basic_interpretation(total_risk, risk_values)
            return jsonify({
                'interpretation': interpretation,
                'success': True,
                'note': 'Using fallback interpretation (Gemini model not available)'
            })

        try:
            print("Attempting to call Gemini API...")
            # Call Gemini API with safety settings
            response = model.generate_content(
                prompt,
                safety_settings=[
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_NONE"
                    }
                ]
            )
            if not response or not response.text:
                raise ValueError("Empty response from API")
                
            print("Successfully received response from Gemini API")
            interpretation = response.text.strip()
            
        except Exception as api_error:
            print(f"Error calling Gemini API: {str(api_error)}")
            print(f"Error type: {type(api_error)}")
            print(f"Error details: {api_error.__dict__}")
            interpretation = generate_basic_interpretation(total_risk, risk_values)
            return jsonify({
                'interpretation': interpretation,
                'success': True,
                'note': 'Using fallback interpretation due to API error'
            })

        return jsonify({
            'interpretation': interpretation,
            'success': True
        })

    except Exception as e:
        print(f"Error generating AI interpretation: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error details: {e.__dict__}")
        return jsonify({
            'error': 'Failed to generate AI interpretation',
            'success': False
        }), 500

def generate_basic_interpretation(total_risk, risk_values):
    """Generate a basic interpretation if the API call fails."""
    interpretation = f"""
1. Overall Risk Assessment
The area shows an overall risk score of {total_risk:.1f}/10. This indicates a {get_risk_level_text(total_risk).lower()} level of risk.

2. Key Risk Factors
"""
    
    # Add interpretation for each risk factor
    for factor, value in risk_values.items():
        level = get_risk_level_text(value)
        if factor == 'vegetation_health':
            interpretation += f"- Vegetation Health ({value:.1f}/10): {level} level of vegetation health\n"
        elif factor == 'water_stress':
            interpretation += f"- Water Stress ({value:.1f}/10): {level} level of water stress\n"
        elif factor == 'urban_areas':
            interpretation += f"- Urban Development ({value:.1f}/10): {level} level of urban development\n"
        elif factor == 'burn_areas':
            interpretation += f"- Fire Risk ({value:.1f}/10): {level} level of fire risk\n"
        elif factor == 'roof_risk':
            interpretation += f"- Roof Vulnerability ({value:.1f}/10): {level} level of roof vulnerability\n"
        elif factor == 'drainage_risk':
            interpretation += f"- Drainage Issues ({value:.1f}/10): {level} level of drainage issues\n"

    interpretation += """
3. Recommendations
Based on the risk assessment, we recommend:
- Regular monitoring of the identified risk factors
- Implementation of appropriate risk mitigation strategies
- Regular updates to insurance coverage based on risk levels
- Consultation with risk management experts for detailed planning

4. Risk Patterns
The analysis shows a combination of different risk factors that should be monitored together for comprehensive risk management."""

    return interpretation

if __name__ == '__main__':
    app.run(debug=True, port=5001) 