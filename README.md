# CustomSat Platform - Comprehensive Technical Documentation

A satellite imagery analysis platform for environmental monitoring.

## Getting Started (Beginner-Friendly Guide)

Follow these steps to download, set up, and run the project on your local machine.

### 0. Make Sure Python is Installed

This project requires Python 3.9 or newer.

#### Check if Python is already installed:

Open a terminal and run:

    python3 --version

If you see something like:

    Python 3.10.8

...then you're good to go.

If you see an error like "command not found", you'll need to install Python.

#### Installing Python (macOS, Windows, Linux):

Go to:  
https://www.python.org/downloads/

Download the appropriate installer for your operating system.

**macOS users**: Make sure you install Python from the official source or use a package manager like Homebrew (`brew install python`).

**Windows users**: During installation, make sure to check the box that says:  
✅ “Add Python to PATH”

After installation, close and reopen your terminal, then verify by running:

    python3 --version

---

### 1. Install a Code Editor

To work with this project, you need a code editor. We recommend Visual Studio Code (VS Code), but you can use any editor of your choice.

Download and install VS Code from:  
👉 https://code.visualstudio.com/

---

### 2. Clone the Project from GitHub

Once your editor is installed:

1. Open VS Code (or your editor).
2. Go to the Source Control tab or press Ctrl+Shift+P and select "Clone Repository".
3. Paste the following URL:

    https://github.com/kapeto9119/MP_CustomSat.git

4. Choose a folder where you want the project saved.

Now the project is downloaded.

---

### 3. Create a Virtual Environment

This keeps your Python packages separate from the rest of your system.

Open a terminal and navigate into the project folder. Then run:

**On macOS/Linux:**
    python3 -m venv venv
    source venv/bin/activate

**On Windows:**
    python -m venv venv
    venv\Scripts\activate

You should now see `(venv)` at the beginning of the terminal prompt.

---

### 4. Make Sure pip is Installed (Python’s package manager)

Check if `pip` is installed:

    pip --version

If it works, you're good.

If not, run the following to install it:

**macOS/Linux:**

    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    python3 get-pip.py

**Windows:**

1. Download this file: https://bootstrap.pypa.io/get-pip.py
2. Open Command Prompt or PowerShell in the same folder.
3. Run:

    python get-pip.py

---

### 5. Install Required Python Packages

Now install all project dependencies using:

    pip install -r requirements.txt

This will download and install all the Python packages the project needs.
If this doesn't work for you copy paste this into your terminal: 
```bash
pip install flask python-dotenv sentinelhub numpy pillow scipy requests reportlab matplotlib gunicorn google-generativeai
```
---

### 6. Run the Flask App

Start the development server with:

    flask run

You should see output like:

    * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)

---

### 7. View the App in Your Browser

Open your browser (e.g., Chrome) and go to:

    http://127.0.0.1:5000/

You should now see the CustomSat Platform running locally.

---

## Troubleshooting

- If `python` or `python3` is not recognized, make sure Python is installed and added to PATH (especially on Windows).
- If you get an error when activating the virtual environment, double-check the command for your OS.
- If `pip` doesn’t work, see step 4 above.
- If `flask` isn’t found, try running:
```bash
    pip install flask
```

- Ensure you're in the project folder when running commands.

---

Happy coding! 🚀


<!-- Auto-deploy test: Railway should deploy this automatically -->

## Features

## 🛰️ Overview

CustomSat is a sophisticated insurance risk analysis platform that transforms raw Sentinel-2 satellite data into actionable risk assessments. The platform provides comprehensive environmental and infrastructure risk analysis for geographical areas worldwide, specifically designed for insurance applications.

## 🏗️ System Architecture

### Technical Stack
```
Frontend: HTML5 + Leaflet.js + JavaScript
Backend: Flask (Python 3.8+)
Satellite API: Sentinel Hub Commercial API
Data Processing: NumPy, SciPy, Matplotlib
Visualization: PIL, Matplotlib with custom color schemes
Authentication: Flask Sessions with secure cookie handling
PDF Generation: ReportLab for comprehensive reports
```

### Data Flow Architecture
```
User Authentication → Area Selection → Satellite Data Acquisition → 
Spectral Index Calculation → Risk Score Processing → 
Spatial Visualization → Report Generation
```

## 🛰️ Satellite Data Processing Engine

### Sentinel-2 Satellite Specifications
- **Constellation**: Two satellites (2A and 2B) for 5-day global revisit
- **Spectral Bands**: 13 bands from 443nm to 2190nm wavelength
- **Spatial Resolution**: 10m (visible/NIR), 20m (SWIR), 60m (atmospheric)
- **Data Product**: Level 2A (atmospherically corrected surface reflectance)
- **Coverage**: Global land monitoring since 2015

### Data Acquisition Pipeline

#### 🔐 Authentication & Configuration
```python
# Sentinel Hub OAuth2 authentication
SH_CLIENT_ID: OAuth2 client identifier
SH_CLIENT_SECRET: OAuth2 client secret (secure storage)
Access tokens: Automatically managed by sentinelhub library
```

#### 📏 Resolution Optimization
```python
def ensure_valid_dimensions(bbox, resolution):
    """
    Dynamic resolution adjustment for API limits (max 2500x2500 pixels)
    
    Examples:
    - Small area (<100 km²): 20m resolution (high detail)
    - Medium area (100-1000 km²): 30m resolution (medium detail)  
    - Large area (1000-5000 km²): 60m resolution (overview)
    - Very large area (>5000 km²): 100m resolution (overview)
    """
```

#### 🌍 Coordinate System Management
```python
def create_bbox_from_coords(min_lon, min_lat, max_lon, max_lat):
    """
    Input: WGS84 decimal degrees (standard GPS coordinates)
    Processing: Sentinel Hub internal projection handling
    Output: BBox object ready for satellite data requests
    
    Validation:
    - Longitude: -180° to +180° (global coverage)
    - Latitude: -90° to +90° (pole to pole)
    - Area validity: min < max for both dimensions
    """
```

## 🔬 Spectral Index Analysis

### 1. 🌱 Vegetation Health (NDVI)

#### Scientific Foundation
**Formula**: `NDVI = (NIR - Red) / (NIR + Red) = (B08 - B04) / (B08 + B04)`

**Spectral Physics**:
- **B04 (Red, 665nm)**: Strongly absorbed by chlorophyll for photosynthesis
- **B08 (NIR, 842nm)**: Strongly reflected by healthy vegetation leaf structure
- **Contrast**: Healthy vegetation shows dramatic difference between red absorption and NIR reflection

#### Risk Assessment Integration
```python
# NDVI-to-Risk Conversion Logic
vegetation_risk = np.where(
    ndvi > 0.6,   # Dense vegetation (forests, healthy crops)
    3,            # Moderate risk: Storm damage potential, but fire-resistant when moist
    np.where(
        ndvi > 0.2,   # Medium vegetation (grasslands, sparse trees)
        5,            # Medium risk: Balanced fire and storm risk
        7             # High risk: Sparse vegetation = fire-prone, less storm protection
    )
)
```

**Insurance Applications**:
- **Fire Risk**: Low NDVI = dry, sparse vegetation = high fire risk
- **Storm Risk**: High NDVI = dense vegetation = potential wind damage
- **Crop Risk**: NDVI trends indicate crop health and yield potential
- **Flood Risk**: Vegetation patterns affect water runoff and absorption

### 2. 💧 Water Stress (NDMI)

#### Scientific Foundation
**Formula**: `NDMI = (NIR - SWIR) / (NIR + SWIR) = (B08 - B11) / (B08 + B11)`

**Spectral Physics**:
- **B08 (NIR, 842nm)**: High reflectance for vegetation, less affected by water content
- **B11 (SWIR, 1610nm)**: Strongly absorbed by water molecules in plant tissue
- **Water Detection**: High NDMI = NIR >> SWIR = high water content

#### Risk Assessment Integration
```python
# NDMI-to-Risk Conversion Logic
water_risk = np.where(
    ndmi > 0.3,   # High moisture content
    3,            # Lower fire risk due to moisture
    np.where(
        ndmi > -0.1,  # Medium moisture content
        5,            # Medium fire risk
        8             # High fire risk due to drought stress
    )
)
```

**Insurance Applications**:
- **Drought Risk**: Low NDMI = water stress = crop failure risk
- **Fire Risk**: Low NDMI = dry vegetation = high fire risk
- **Irrigation Monitoring**: NDMI trends indicate irrigation effectiveness
- **Seasonal Patterns**: NDMI reveals seasonal moisture cycles

### 3. 🏢 Urban Detection (NDBI)

#### Scientific Foundation
**Formula**: `NDBI = (SWIR - NIR) / (SWIR + NIR) = (B11 - B08) / (B11 + B08)`

**Spectral Physics**:
- **B11 (SWIR, 1610nm)**: Higher reflectance from built materials (concrete, asphalt, metal)
- **B08 (NIR, 842nm)**: Very high reflectance from vegetation, lower from built surfaces
- **Urban Enhancement**: Built surfaces show opposite spectral behavior to vegetation

#### Risk Assessment Integration
```python
# NDBI-to-Risk Conversion Logic
urban_risk = np.where(
    ndbi > 0.1,   # Dense development
    7,            # High property risk
    np.where(
        ndbi > -0.2,  # Mixed development
        4,            # Medium property risk
        2             # Low property risk
    )
)
```

**Insurance Applications**:
- **Property Density**: Higher NDBI = more infrastructure = higher economic exposure
- **Urban Planning**: Identify development patterns and growth trends
- **Evacuation Planning**: Map population density for emergency response
- **Infrastructure Assessment**: Monitor urban expansion and density changes

### 4. 🔥 Burn Detection (NBR)

#### Scientific Foundation
**Formula**: `NBR = (NIR - SWIR2) / (NIR + SWIR2) = (B08 - B12) / (B08 + B12)`

**Spectral Physics**:
- **B08 (NIR, 842nm)**: High for healthy vegetation, dramatically reduced by fire damage
- **B12 (SWIR2, 2190nm)**: Sensitive to char and ash, increases after burning
- **Fire Detection**: Burned areas show low NIR and high SWIR2 = low/negative NBR

#### Risk Assessment Integration
```python
# NBR-to-Risk Conversion Logic
burn_risk = np.where(
    nbr > 0.3,   # Healthy unburned vegetation
    2,            # Low fire risk
    np.where(
        nbr > 0.1,  # Medium vegetation health
        5,            # Medium fire risk
        8             # High fire risk
    )
)
```

**Insurance Applications**:
- **Post-Fire Assessment**: Quantify burn severity and damage extent
- **Fire Risk Mapping**: Identify fire-prone areas before incidents
- **Recovery Monitoring**: Track vegetation regrowth after fires
- **Temporal Analysis**: Compare pre-fire vs post-fire conditions

### 5. 🏠 Roof Vulnerability (BREI - Custom Index)

#### Scientific Foundation
**Formula**: `BREI = (B11 + B04 - B08 - B02) / (B11 + B04 + B08 + B02)`

**Multi-Band Logic**:
- **B02 (Blue, 490nm)**: Atmospheric interference reduction
- **B04 (Red, 665nm)**: Enhances dry building materials (concrete, metal)
- **B08 (NIR, 842nm)**: Vegetation suppression (vegetation has high NIR)
- **B11 (SWIR, 1610nm)**: Building materials enhancement (dry surfaces)

#### Physical Interpretation
```javascript
// Numerator (B11 + B04 - B08 - B02):
//   + B11 (SWIR): Enhances dry building materials signal
//   + B04 (Red): Enhances reflectance of roof materials like concrete/metal
//   - B08 (NIR): Removes vegetation signal (vegetation has high NIR)
//   - B02 (Blue): Removes atmospheric/water interference
//
// Result: Positive values indicate exposed roof materials vulnerable to weather damage
```

**Insurance Applications**:
- **Hail Damage Risk**: Identify vulnerable roof materials (metal, asphalt shingles)
- **Wind Damage Assessment**: Detect exposed vs protected roofing
- **Material Analysis**: Differentiate roof types (tile, metal, membrane)
- **Maintenance Prioritization**: Flag roofs needing protective measures

### 6. 🌊 Drainage Assessment (DOPI - Custom Index)

#### Scientific Foundation
**Formula**: `DOPI = (1 - NDVI) * (B11 / B08)`

**Component Analysis**:
```javascript
// Step 1: Calculate NDVI for vegetation density
const ndvi = (s.B08 - s.B04) / (s.B08 + s.B04);

// Step 2: Inverse vegetation factor (sparse vegetation areas)
const inverse_vegetation = (1 - ndvi);

// Step 3: Moisture/built-up factor (SWIR/NIR ratio)
const moisture_buildup_factor = (s.B11 / s.B08);

// Step 4: Combined drainage obstruction indicator
const dopi = inverse_vegetation * moisture_buildup_factor;
```

**Physical Interpretation**:
- **High DOPI**: Sparse vegetation + high moisture/built surfaces = potential drainage problems
- **Low DOPI**: Well-vegetated areas or dry natural surfaces = good drainage
- **Application**: Identifies blocked drains, waterlogging, flood-prone areas

**Insurance Applications**:
- **Flood Risk**: Identify areas with poor water drainage
- **Urban Planning**: Map drainage efficiency in developed areas
- **Waterlogging Detection**: Find areas prone to water accumulation
- **Infrastructure Assessment**: Evaluate drainage system performance

## 🎯 Risk Calculation Methodology

### Individual Risk Scoring (1-10 Scale)

Each satellite index is converted to insurance risk scores using scientifically-based thresholds:

```python
RISK_SCALE_INTERPRETATION = {
    "1-2": "Very Low Risk (minimal insurance concern)",
    "3-4": "Low Risk (standard coverage adequate)", 
    "5-6": "Moderate Risk (enhanced monitoring recommended)",
    "7-8": "High Risk (premium adjustment consideration)",
    "9-10": "Critical Risk (immediate attention required)"
}
```

### Composite Risk Algorithm

```python
def calculate_composite_risk(risk_layers):
    """
    Final risk score = Average of all available individual risk factors
    
    Advantages:
    - Ensures missing data doesn't bias results
    - Provides comprehensive coverage when all factors available
    - Maintains consistent 1-10 scale regardless of factor availability
    - Allows partial analysis when some APIs fail
    """
    total_risk = np.zeros(reference_shape, dtype=np.float64)
    factor_count = 0
    
    for layer_name, layer_data in risk_layers.items():
        total_risk += layer_data.astype(np.float64)
        factor_count += 1
    
    composite_risk = total_risk / factor_count if factor_count > 0 else 5.0
    return np.clip(composite_risk, 1, 10)  # Ensure 1-10 range
```

## 📈 Time Series & Trend Analysis

### Temporal Analysis Architecture

#### Time Period Segmentation
```python
def generate_time_periods(start_date, end_date, interval_months):
    """
    Algorithm:
    1. Start from user-provided start date
    2. Create analysis periods of 3 months duration each
    3. Advance by user-specified interval (3, 6, or 12 months)
    4. Continue until end date is reached
    
    Example Timeline:
    2023-01-01 to 2024-12-31 (6-month intervals)
    ├── Period 1: 2023-01-01 to 2023-03-31 (Analysis: 2023-03-31)
    ├── Period 2: 2023-07-01 to 2023-09-30 (Analysis: 2023-09-30)
    ├── Period 3: 2024-01-01 to 2024-03-31 (Analysis: 2024-03-31)
    └── Period 4: 2024-07-01 to 2024-09-30 (Analysis: 2024-09-30)
    """
```

## 🔒 Authentication & Security

### Session-Based Authentication
```python
# Flask Session Configuration
app.secret_key = os.environ.get('SECRET_KEY', 'secure-production-key')

DEMO_CREDENTIALS = {
    'admin@customsat.it': 'password'  # Demo account for deployment
}

@login_required
def protected_route():
    """
    Security Features:
    - Session validation on every request
    - Automatic redirects for unauthenticated users
    - Session cleanup on logout
    - Flash messaging for user feedback
    """
```

## 📄 PDF Report Generation

### Comprehensive Reporting System

```python
def generate_pdf_report(analysis_data):
    """
    Report Components:
    1. Executive Summary: Overall risk assessment and key findings
    2. Area Information: Coordinates, size, resolution, analysis dates
    3. Risk Factor Breakdown: Individual factor scores and interpretations
    4. Trend Analysis: Temporal charts and statistical summaries
    5. Technical Details: Raw satellite indices and scientific values
    6. Recommendations: Risk management strategies and next steps
    """
```

## 🔧 Error Handling & Resilience

### API Failure Management

```python
def generate_simple_fallback(size=(256, 256), bbox=None):
    """
    Fallback Strategy for API Failures:
    
    1. Realistic Data Generation: Random values with realistic ranges
    2. Location-Based Variation: Use coordinates for regional patterns
    3. Consistent Format: Same structure as real satellite data
    4. User Notification: Clear messaging about fallback usage
    
    Purpose: Ensure application continues functioning during:
    - Sentinel Hub API outages
    - Network connectivity issues
    - Authentication failures
    - Quota exceeded scenarios
    """
```

## 🚀 Performance Optimization

### Processing Efficiency

#### Resolution Scaling Strategy
```python
# Dynamic Resolution Based on Area Size
RESOLUTION_STRATEGY = {
    "< 100 km²": "20m resolution (high detail)",
    "100-1000 km²": "30m resolution (medium detail)",
    "1000-5000 km²": "60m resolution (overview)",
    "> 5000 km²": "100m resolution (broad overview)"
}
```

## 📚 Dependencies & Environment

### Core Dependencies
```python
# requirements.txt
flask>=2.0.0                    # Web framework
sentinelhub>=3.6.0               # Satellite data API
numpy>=1.21.0                   # Numerical processing
scipy>=1.7.0                    # Scientific computing
matplotlib>=3.5.0               # Visualization
pillow>=8.3.0                   # Image processing
reportlab>=3.6.0                # PDF generation
python-dateutil>=2.8.0          # Date handling
python-dotenv>=0.19.0           # Environment variables
```

### Environment Setup
```bash
# Development Environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
pip install -r requirements.txt

# Environment Variables (.env file)
SH_CLIENT_ID=your_sentinel_hub_client_id
SH_CLIENT_SECRET=your_sentinel_hub_client_secret
SECRET_KEY=your_flask_secret_key
```

## 🎯 Development Guidelines

### Adding New Risk Factors

```python
def implement_new_factor():
    """
    Development Process:
    1. Create evalscript in evalscripts/ directory
    2. Add fetch function following existing patterns
    3. Implement risk conversion logic in process_risk_data()
    4. Define visualization color scheme
    5. Add comprehensive comments and documentation
    6. Test with both current and trend analysis modes
    """
```

### Code Quality Standards

```python
# Comment Requirements
"""
Every function must include:
1. Purpose and scientific background
2. Algorithm explanation with formulas
3. Parameter descriptions with types and ranges
4. Return value documentation
5. Error handling explanation
6. Usage examples where appropriate
"""
```

## 🔬 Scientific Validation

### Index Validation Sources
- **NASA Earth Science Division**: NDVI, NDMI, NBR standard methodologies
- **USGS Land Change Monitoring**: Burn severity classification thresholds
- **European Space Agency Copernicus**: Sentinel-2 data quality standards
- **Peer-Reviewed Literature**: Risk threshold validation from published research

### Quality Assurance Metrics
```python
QUALITY_METRICS = {
    "Data Coverage": "Minimum 70% valid pixels for analysis",
    "Cloud Coverage": "Maximum 80% cloud coverage filter",
    "Temporal Consistency": "Cross-period validation for trend analysis",
    "Spatial Accuracy": "10-20m geolocation accuracy verification"
}
```

## 🔮 Future Enhancements

### Planned Features
- **Machine Learning Integration**: AI-powered risk prediction models
- **Real-Time Monitoring**: Automated alerts for risk threshold breaches
- **Multi-Satellite Integration**: Combine Sentinel-2 with other satellite data
- **Historical Database**: Long-term risk trend storage and analysis
- **API Development**: RESTful API for third-party integrations

### Technical Roadmap
- **Performance**: GPU acceleration for large-scale processing
- **Scalability**: Microservices architecture for horizontal scaling
- **User Management**: Advanced authentication and role-based access
- **Customization**: User-defined risk factors and thresholds

---

## 📞 Support & Documentation

### Getting Help
- **Technical Issues**: Check logs for satellite API responses
- **Data Quality**: Verify Sentinel Hub credentials and quotas
- **Performance**: Monitor area size and resolution settings
- **Integration**: Review API documentation for custom implementations

### Contributing
- **Code Style**: Follow PEP 8 for Python code formatting
- **Documentation**: Update comments for any new functionality
- **Testing**: Include tests for new features and bug fixes
- **Pull Requests**: Use descriptive commit messages and clear PR descriptions

**The CustomSat platform represents the cutting edge of satellite-based insurance risk analysis, combining rigorous scientific methodology with practical business applications. Every component has been carefully designed and documented to ensure maintainability, extensibility, and scientific accuracy.** 
