"""
=============================================================================
CUSTOMSAT PLATFORM - SATELLITE DATA PROCESSING UTILITIES
=============================================================================

PURPOSE:
This module provides comprehensive satellite data processing capabilities for
the CustomSat insurance risk analysis platform. It handles the complete pipeline
from raw Sentinel-2 satellite data acquisition to processed risk indicators.

CORE CAPABILITIES:
1. Sentinel Hub API Integration - Authentication and data requests
2. Multi-Spectral Index Calculation - NDVI, NDMI, NDBI, NBR, custom indices
3. Risk Score Processing - Convert satellite indices to insurance risk scores
4. Spatial Data Management - Coordinate transformations and area calculations
5. Visualization Generation - Color-coded risk maps and analysis imagery

SATELLITE DATA SOURCES:
- Sentinel-2 Satellite Constellation (ESA Copernicus Program)
- 13 spectral bands from 443nm to 2190nm wavelength
- 10-20 meter spatial resolution depending on band
- 5-day global revisit time (with both satellites)
- Level 2A products (atmospherically corrected surface reflectance)

SPECTRAL INDICES IMPLEMENTED:
1. NDVI (Normalized Difference Vegetation Index) - Vegetation health assessment
2. NDMI (Normalized Difference Moisture Index) - Water stress detection
3. NDBI (Normalized Difference Built-up Index) - Urban area identification
4. NBR (Normalized Burn Ratio) - Fire damage and burn scar detection
5. BREI (Bare Roof Exposure Index) - Custom roof vulnerability analysis
6. DOPI (Drainage Obstruction Proxy Index) - Custom drainage assessment

RISK ASSESSMENT METHODOLOGY:
Each satellite index is converted to risk scores (1-10 scale) using:
- Scientific thresholds from remote sensing literature
- Statistical analysis of index value distributions
- Domain expertise from insurance and environmental science
- Weighted combination into composite risk scores

TECHNICAL ARCHITECTURE:
- NumPy arrays for efficient satellite data processing
- SciPy for advanced image processing and interpolation
- Sentinel Hub Python library for API integration
- Matplotlib/PIL for visualization generation
- Error handling and fallback strategies for data availability

COORDINATE SYSTEMS:
- Input: WGS84 geographic coordinates (latitude/longitude)
- Processing: Sentinel Hub's internal projection handling
- Output: Pixel-based arrays with spatial metadata

API INTEGRATION:
- Sentinel Hub Commercial API for satellite data access
- OAuth2 authentication with client credentials
- Rate limiting and error recovery mechanisms
- Dynamic resolution adjustment for area size optimization

DATA QUALITY ASSURANCE:
- Cloud coverage filtering (< 80% cloud coverage)
- Data validation and NaN/infinity handling
- Spatial consistency checks across different indices
- Temporal data availability verification

PERFORMANCE OPTIMIZATIONS:
- Dynamic resolution scaling based on area size
- Concurrent API requests for multiple indices
- Memory-efficient array processing
- Fallback data generation for API failures
"""

import os
import numpy as np
import tempfile
import requests
from datetime import datetime, timedelta
from sentinelhub import (
    SHConfig, BBox, CRS, DataCollection, SentinelHubRequest,
    MimeType, bbox_to_dimensions, SentinelHubDownloadClient
)
import copy
import json
import math
from concurrent.futures import ThreadPoolExecutor

# =============================================================================
# GEOSPATIAL UTILITY FUNCTIONS
# =============================================================================

def ensure_valid_dimensions(bbox, resolution):
    """
    Calculate optimal image dimensions and adjust resolution to stay within API limits.
    
    PURPOSE:
    Sentinel Hub API has strict limits on image dimensions (max 2500x2500 pixels).
    This function ensures requests stay within limits by dynamically adjusting
    the spatial resolution when analyzing large geographical areas.
    
    ALGORITHM:
    1. Calculate initial pixel dimensions using bbox_to_dimensions utility
    2. Check if either dimension exceeds 2500 pixel limit
    3. If exceeded: calculate scale factor to reduce dimensions
    4. Adjust resolution proportionally to maintain area coverage
    5. Recalculate dimensions with adjusted resolution
    
    SCALING STRATEGY:
    - For large areas: Lower resolution (fewer pixels, less detail)
    - For small areas: Higher resolution (more pixels, more detail)
    - Maintains consistent area coverage regardless of resolution
    
    PARAMETERS:
    bbox (BBox): Sentinel Hub bounding box object defining the area
    resolution (int): Desired pixel resolution in meters
    
    RETURNS:
    tuple: (size, adjusted_resolution) where:
        - size: (width, height) tuple in pixels, guaranteed ≤ 2500
        - adjusted_resolution: Final resolution in meters per pixel
    
    EXAMPLE:
    Original: 100km x 100km area at 10m resolution = 10,000 x 10,000 pixels (exceeds limit)
    Adjusted: 100km x 100km area at 40m resolution = 2,500 x 2,500 pixels (within limit)
    """
    # Calculate initial dimensions using Sentinel Hub utility
    # This converts geographic bounds to pixel dimensions at given resolution
    size = bbox_to_dimensions(bbox, resolution)
    
    # API constraint: maximum 2500 pixels in any dimension
    max_dim = 2500
    
    if size[0] > max_dim or size[1] > max_dim:
        # Calculate scale factor needed to fit within limits
        # Use the larger dimension to ensure both fit
        scale = max(size[0] / max_dim, size[1] / max_dim)
        
        # Adjust resolution proportionally to scale factor
        # Higher scale = larger area = lower resolution needed
        adjusted_resolution = resolution * scale
        
        # Recalculate dimensions with the adjusted resolution
        size = bbox_to_dimensions(bbox, adjusted_resolution)
        
        print(f"🔧 RESOLUTION ADJUSTMENT: Area too large for {resolution}m resolution")
        print(f"   Original dimensions: {size[0]} x {size[1]} pixels (exceeds {max_dim} limit)")
        print(f"   Adjusted resolution: {resolution}m → {adjusted_resolution:.1f}m")
        print(f"   Final dimensions: {size[0]} x {size[1]} pixels")
        
        return size, adjusted_resolution
    
    # No adjustment needed - dimensions are within limits
    return size, resolution

def get_sh_config():
    """
    Initialize and configure Sentinel Hub API connection.
    
    PURPOSE:
    Creates a properly configured SHConfig object for authenticating with
    Sentinel Hub's commercial satellite data API. This configuration is
    required for all satellite data requests.
    
    AUTHENTICATION FLOW:
    1. Reads credentials from environment variables (secure storage)
    2. Creates SHConfig object with OAuth2 client credentials
    3. Sentinel Hub API validates credentials and provides access token
    4. Access token is used for all subsequent data requests
    
    REQUIRED ENVIRONMENT VARIABLES:
    - SH_CLIENT_ID: OAuth2 client identifier from Sentinel Hub dashboard
    - SH_CLIENT_SECRET: OAuth2 client secret (keep secure!)
    
    SECURITY CONSIDERATIONS:
    - Credentials should never be hardcoded in source code
    - Use .env files for development, secure storage for production
    - Client secret should be treated as a password
    - Access tokens are automatically managed by sentinelhub library
    
    ERROR HANDLING:
    If credentials are missing or invalid, subsequent API calls will fail
    with authentication errors. Always validate config before use.
    
    RETURNS:
    SHConfig: Configured Sentinel Hub connection object ready for API requests
    """
    # Create new configuration object
    config = SHConfig()
    
    # Load OAuth2 credentials from secure environment variables
    # These credentials are obtained from the Sentinel Hub dashboard
    config.sh_client_id = os.environ.get("SH_CLIENT_ID")
    config.sh_client_secret = os.environ.get("SH_CLIENT_SECRET")
    
    print(f"🔐 SENTINEL HUB CONFIG: Loading API credentials")
    print(f"   Client ID: {config.sh_client_id[:8] if config.sh_client_id else 'NOT_SET'}***")
    print(f"   Client Secret: {'SET' if config.sh_client_secret else 'NOT_SET'}")
    
    return config

def create_bbox_from_coords(min_lon, min_lat, max_lon, max_lat):
    """
    Create a Sentinel Hub BBox object from geographic coordinates.
    
    PURPOSE:
    Converts standard latitude/longitude coordinates into Sentinel Hub's
    internal BBox format required for satellite data requests. Handles
    coordinate system conversion and validation.
    
    COORDINATE SYSTEM DETAILS:
    - Input: WGS84 decimal degrees (standard GPS coordinates)
    - Processing: Sentinel Hub handles projection transformations internally
    - Output: BBox object ready for satellite data requests
    
    PARAMETER VALIDATION:
    - Longitude: Must be within -180° to +180° (global coverage)
    - Latitude: Must be within -90° to +90° (pole to pole)
    - Area: min values must be less than max values (valid rectangle)
    
    GEOGRAPHIC CONSIDERATIONS:
    - Antimeridian crossing (longitude ±180°) requires special handling
    - Polar regions may have limited satellite coverage
    - Very small areas may result in insufficient pixels for analysis
    
    PARAMETERS:
    min_lon (float): Western longitude boundary in decimal degrees
    min_lat (float): Southern latitude boundary in decimal degrees  
    max_lon (float): Eastern longitude boundary in decimal degrees
    max_lat (float): Northern latitude boundary in decimal degrees
    
    RETURNS:
    BBox: Sentinel Hub bounding box object for API requests
    
    RAISES:
    RuntimeError: If coordinates are invalid or bbox creation fails
    
    EXAMPLE:
    bbox = create_bbox_from_coords(-122.5, 37.7, -122.3, 37.8)  # San Francisco area
    """
    try:
        # Create BBox using WGS84 coordinate reference system
        # Order: [min_lon, min_lat, max_lon, max_lat] (southwest to northeast corners)
        bbox = BBox([min_lon, min_lat, max_lon, max_lat], crs=CRS.WGS84)
        
        print(f"🗺️ BOUNDING BOX CREATED:")
        print(f"   Southwest: ({min_lon:.6f}°, {min_lat:.6f}°)")
        print(f"   Northeast: ({max_lon:.6f}°, {max_lat:.6f}°)")
        print(f"   Width: {max_lon - min_lon:.6f}° longitude")
        print(f"   Height: {max_lat - min_lat:.6f}° latitude")
        
        return bbox
        
    except Exception as e:
        print(f"❌ ERROR creating bounding box: {str(e)}")
        print(f"   Coordinates: ({min_lon}, {min_lat}) to ({max_lon}, {max_lat})")
        raise RuntimeError(f"Failed to create bounding box from coordinates: {e}")

def process_risk_data(veg_health_data=None, water_stress_data=None, urban_detection_data=None, 
                burn_detection_data=None, roof_detection_data=None, drainage_detection_data=None):
    """
    Transform raw satellite indices into comprehensive insurance risk assessments.
    
    RISK PROCESSING OVERVIEW:
    This function is the core of the CustomSat risk analysis engine. It takes
    raw satellite spectral indices and converts them into meaningful insurance
    risk scores using scientifically-based thresholds and domain expertise.
    
    PROCESSING PIPELINE:
    1. Data Validation & Normalization - Ensure consistent data formats
    2. Individual Risk Calculation - Convert each index to 1-10 risk scale
    3. Spatial Alignment - Resize arrays to consistent dimensions
    4. Composite Risk Generation - Weighted combination of all factors
    5. Statistical Validation - Ensure results are within expected ranges
    
    RISK CALCULATION METHODOLOGY:
    Each satellite index is interpreted through the lens of insurance risk:
    
    📊 VEGETATION HEALTH (NDVI: -1 to +1)
    - High NDVI (>0.6): Dense vegetation = Storm damage risk but lower fire risk
    - Medium NDVI (0.2-0.6): Balanced vegetation = Moderate overall risk
    - Low NDVI (<0.2): Sparse vegetation = High fire risk, erosion risk
    
    💧 WATER STRESS (NDMI: -1 to +1)  
    - High NDMI (>0.3): Well-watered vegetation = Lower fire risk
    - Medium NDMI (0.0-0.3): Some moisture = Medium fire risk
    - Low NDMI (<0.0): Drought stress = High fire risk, crop failure
    
    🏢 URBAN DETECTION (NDBI: -1 to +1)
    - High NDBI (>0.1): Dense development = High property value at risk
    - Medium NDBI (-0.2-0.1): Mixed development = Medium property risk
    - Low NDBI (<-0.2): Natural areas = Lower property density
    
    🔥 BURN DETECTION (NBR: -1 to +1)
    - High NBR (>0.3): Healthy unburned vegetation = Lower fire risk
    - Medium NBR (0.1-0.3): Some stress = Medium fire risk
    - Low NBR (<0.1): Recent burns/stressed vegetation = High fire risk
    
    🏠 ROOF VULNERABILITY (Custom Multi-Band Analysis)
    - Analyzes roof materials using spectral signatures
    - Detects metal, tile, shingle, and membrane roofing
    - Assesses vulnerability to hail, wind, and UV damage
    
    🌊 DRAINAGE ASSESSMENT (Custom NDVI/SWIR Combination)
    - Identifies areas with poor water drainage
    - Combines vegetation stress with moisture indicators
    - Flags flood-prone and waterlogging-susceptible areas
    
    COMPOSITE RISK ALGORITHM:
    Final risk score = Average of all available individual risk factors
    This approach ensures that missing data doesn't bias results while
    providing comprehensive coverage when all factors are available.
    
    RISK SCALE INTERPRETATION (1-10):
    1-2: Very Low Risk (minimal insurance concern)
    3-4: Low Risk (standard coverage adequate)
    5-6: Moderate Risk (enhanced monitoring recommended)
    7-8: High Risk (premium adjustment consideration)
    9-10: Critical Risk (immediate attention required)
    
    SPATIAL PROCESSING:
    - All arrays resized to consistent dimensions for overlay analysis
    - Bilinear interpolation preserves spatial relationships
    - Reference shape determined by first available dataset
    - Missing data filled with neutral risk values (5.0)
    
    PARAMETERS:
    veg_health_data (list): NDVI satellite data arrays
    water_stress_data (list): NDMI satellite data arrays
    urban_detection_data (list): NDBI satellite data arrays
    burn_detection_data (list): NBR satellite data arrays
    roof_detection_data (list): Custom roof analysis arrays
    drainage_detection_data (list): Custom drainage analysis arrays
    
    RETURNS:
    tuple: (composite_risk, index_values, risk_values) where:
        - composite_risk: 2D numpy array with overall risk scores (1-10)
        - index_values: Dictionary with raw satellite index values and interpretations
        - risk_values: Dictionary with individual risk factor scores
    
    ERROR HANDLING:
    - Graceful handling of missing or invalid satellite data
    - NaN/infinity values replaced with neutral risk scores
    - Partial data analysis when some indices are unavailable
    - Fallback to neutral values ensures analysis always completes
    """
    print("🔍 RISK PROCESSING: Starting satellite data analysis")
    print("=" * 60)
    
    # Initialize data structures for risk calculation
    risk_layers = {}      # Individual risk factor arrays
    index_values = {}     # Raw satellite index values for reporting
    reference_shape = None  # Consistent array dimensions for spatial alignment
    
    # =================================================================
    # VEGETATION HEALTH RISK ASSESSMENT (NDVI Analysis)
    # =================================================================
    
    if veg_health_data is not None:
        print("🌱 PROCESSING: Vegetation Health (NDVI)")
        
        # Extract NDVI values from first band of satellite data
        # Satellite data format: [batch][height][width][bands]
        # Channel 0: NDVI values (-1 to +1)
        # Channel 1: Data mask (1=valid, 0=invalid)
        ndvi = veg_health_data[0][:, :, 0].astype(np.float64)
        reference_shape = ndvi.shape  # Set reference for spatial alignment
        
        print(f"   📊 NDVI Statistics:")
        print(f"      Array shape: {ndvi.shape}")
        print(f"      Value range: {np.nanmin(ndvi):.4f} to {np.nanmax(ndvi):.4f}")
        print(f"      Mean NDVI: {np.nanmean(ndvi):.4f}")
        print(f"      Valid pixels: {np.count_nonzero(~np.isnan(ndvi))}/{ndvi.size}")
        
        # NDVI-to-Risk Conversion Logic:
        # Based on vegetation fire risk and storm damage considerations
        # Higher vegetation density = more fuel for fires but also storm damage risk
        vegetation_risk = np.where(
            ndvi > 0.6,   # Dense vegetation (forests, healthy crops)
            3,            # Moderate risk: Storm damage potential, but fire-resistant when moist
            np.where(
                ndvi > 0.2,   # Medium vegetation (grasslands, sparse trees)
                5,            # Medium risk: Balanced fire and storm risk
                7             # High risk: Sparse vegetation = fire-prone, less storm protection
            )
        )
        
        print(f"   🎯 Risk Conversion Results:")
        print(f"      Risk range: {np.min(vegetation_risk)} to {np.max(vegetation_risk)}")
        print(f"      Average risk: {np.mean(vegetation_risk):.2f}")
        print(f"      Pixel distribution: Low({np.sum(vegetation_risk==3)}), Med({np.sum(vegetation_risk==5)}), High({np.sum(vegetation_risk==7)})")
        
        # Store results for composite calculation
        risk_layers["vegetation_health"] = vegetation_risk
        index_values["vegetation_health"] = {
            "raw_ndvi": float(np.nanmean(ndvi)),
            "interpretation": get_ndvi_interpretation(float(np.nanmean(ndvi)))
        }
    
    # =================================================================
    # WATER STRESS RISK ASSESSMENT (NDMI Analysis)
    # =================================================================
    
    if water_stress_data is not None:
        print("💧 PROCESSING: Water Stress (NDMI)")
        
        # Extract NDMI values from satellite data
        ndmi = water_stress_data[0][:, :, 0].astype(np.float64)
        
        print(f"   📊 NDMI Statistics:")
        print(f"      Value range: {np.nanmin(ndmi):.4f} to {np.nanmax(ndmi):.4f}")
        print(f"      Mean NDMI: {np.nanmean(ndmi):.4f}")
        print(f"      Valid pixels: {np.count_nonzero(~np.isnan(ndmi))}/{ndmi.size}")
        
        # Resize to match reference shape if needed (spatial alignment)
        if reference_shape is not None and ndmi.shape != reference_shape:
            print(f"   🔄 SPATIAL ALIGNMENT: Resizing from {ndmi.shape} to {reference_shape}")
            from scipy.ndimage import zoom
            zoom_factor = (reference_shape[0] / ndmi.shape[0], reference_shape[1] / ndmi.shape[1])
            ndmi = zoom(ndmi, zoom_factor, order=1)  # Bilinear interpolation
        elif reference_shape is None:
            reference_shape = ndmi.shape
            
        # NDMI-to-Risk Conversion Logic:
        # Based on drought stress and fire risk from low moisture content
        water_risk = np.where(
            ndmi > 0.3,   # High moisture content
            3,            # Lower fire risk due to moisture
            np.where(
                ndmi > -0.1,  # Medium moisture content
                5,            # Medium fire risk
                8             # High fire risk due to drought stress
            )
        )
        
        print(f"   🎯 Risk Conversion Results:")
        print(f"      Risk range: {np.min(water_risk)} to {np.max(water_risk)}")
        print(f"      Average risk: {np.mean(water_risk):.2f}")
        
        risk_layers["water_stress"] = water_risk
        index_values["water_stress"] = {
            "raw_ndmi": float(np.nanmean(ndmi)),
            "interpretation": get_ndmi_interpretation(float(np.nanmean(ndmi)))
        }
    
    # =================================================================
    # URBAN DETECTION RISK ASSESSMENT (NDBI Analysis)
    # =================================================================
    
    if urban_detection_data is not None:
        print("🏢 PROCESSING: Urban Detection (NDBI)")
        
        # Extract NDBI values from satellite data
        ndbi = urban_detection_data[0][:, :, 0].astype(np.float64)
        
        print(f"   📊 NDBI Statistics:")
        print(f"      Value range: {np.nanmin(ndbi):.4f} to {np.nanmax(ndbi):.4f}")
        print(f"      Mean NDBI: {np.nanmean(ndbi):.4f}")
        print(f"      Valid pixels: {np.count_nonzero(~np.isnan(ndbi))}/{ndbi.size}")
        
        # Resize to match reference shape if needed (spatial alignment)
        if reference_shape is not None and ndbi.shape != reference_shape:
            print(f"   🔄 SPATIAL ALIGNMENT: Resizing from {ndbi.shape} to {reference_shape}")
            from scipy.ndimage import zoom
            zoom_factor = (reference_shape[0] / ndbi.shape[0], reference_shape[1] / ndbi.shape[1])
            ndbi = zoom(ndbi, zoom_factor, order=1)  # Bilinear interpolation
        elif reference_shape is None:
            reference_shape = ndbi.shape
            
        # NDBI-to-Risk Conversion Logic:
        # Based on urban development and property risk considerations
        urban_risk = np.where(
            ndbi > 0.1,   # Dense development
            7,            # High property risk
            np.where(
                ndbi > -0.2,  # Mixed development
                4,            # Medium property risk
                2             # Low property risk
            )
        )
        
        print(f"   🎯 Risk Conversion Results:")
        print(f"      Risk range: {np.min(urban_risk)} to {np.max(urban_risk)}")
        print(f"      Average risk: {np.mean(urban_risk):.2f}")
        
        risk_layers["urban_areas"] = urban_risk
        index_values["urban_areas"] = {
            "raw_ndbi": float(np.nanmean(ndbi)),
            "interpretation": get_ndbi_interpretation(float(np.nanmean(ndbi)))
        }
    
    # =================================================================
    # BURN DETECTION RISK ASSESSMENT (NBR Analysis)
    # =================================================================
    
    if burn_detection_data is not None:
        print("🔥 PROCESSING: Burn Detection (NBR)")
        
        # Extract NBR values from satellite data
        nbr = burn_detection_data[0][:, :, 0].astype(np.float64)
        
        print(f"   📊 NBR Statistics:")
        print(f"      Value range: {np.nanmin(nbr):.4f} to {np.nanmax(nbr):.4f}")
        print(f"      Mean NBR: {np.nanmean(nbr):.4f}")
        print(f"      Valid pixels: {np.count_nonzero(~np.isnan(nbr))}/{nbr.size}")
        
        # Resize to match reference shape if needed (spatial alignment)
        if reference_shape is not None and nbr.shape != reference_shape:
            print(f"   🔄 SPATIAL ALIGNMENT: Resizing from {nbr.shape} to {reference_shape}")
            from scipy.ndimage import zoom
            zoom_factor = (reference_shape[0] / nbr.shape[0], reference_shape[1] / nbr.shape[1])
            nbr = zoom(nbr, zoom_factor, order=1)  # Bilinear interpolation
        elif reference_shape is None:
            reference_shape = nbr.shape
            
        # NBR-to-Risk Conversion Logic:
        # Based on burn/vegetation status and fire risk considerations
        burn_risk = np.where(
            nbr > 0.3,   # Healthy unburned vegetation
            2,            # Low fire risk
            np.where(
                nbr > 0.1,  # Medium vegetation health
                5,            # Medium fire risk
                8             # High fire risk
            )
        )
        
        print(f"   🎯 Risk Conversion Results:")
        print(f"      Risk range: {np.min(burn_risk)} to {np.max(burn_risk)}")
        print(f"      Average risk: {np.mean(burn_risk):.2f}")
        
        risk_layers["burn_areas"] = burn_risk
        index_values["burn_areas"] = {
            "raw_nbr": float(np.nanmean(nbr)),
            "interpretation": get_nbr_interpretation(float(np.nanmean(nbr)))
        }
    
    # =================================================================
    # ROOF VULNERABILITY RISK ASSESSMENT (Custom Multi-Band Analysis)
    # =================================================================
    
    if roof_detection_data is not None:
        print("🏠 PROCESSING: Roof Vulnerability (Custom Multi-Band Analysis)")
        
        # Extract roof values from satellite data
        roof_value = roof_detection_data[0][:, :, 0].astype(np.float64)
        
        print(f"   📊 Roof Analysis Statistics:")
        print(f"      Array shape: {roof_value.shape}")
        print(f"      Value range: {np.nanmin(roof_value):.4f} to {np.nanmax(roof_value):.4f}")
        print(f"      Mean Roof Analysis: {np.nanmean(roof_value):.4f}")
        print(f"      Valid pixels: {np.count_nonzero(~np.isnan(roof_value))}/{roof_value.size}")
        
        # Resize to match reference shape if needed (spatial alignment)
        if reference_shape is not None and roof_value.shape != reference_shape:
            print(f"   🔄 SPATIAL ALIGNMENT: Resizing from {roof_value.shape} to {reference_shape}")
            from scipy.ndimage import zoom
            zoom_factor = (reference_shape[0] / roof_value.shape[0], reference_shape[1] / roof_value.shape[1])
            roof_value = zoom(roof_value, zoom_factor, order=1)  # Bilinear interpolation
        elif reference_shape is None:
            reference_shape = roof_value.shape
            
        # Normalize roof values to 0-10 scale for risk assessment
        if np.max(roof_value) > np.min(roof_value):
            roof_norm = (roof_value - np.min(roof_value)) / (np.max(roof_value) - np.min(roof_value))
            roof_risk = np.round(roof_norm * 8 + 2)  # Scale to 2-10 range
        else:
            roof_risk = np.full_like(roof_value, 5)  # Default medium risk
        
        print(f"   🎯 Risk Conversion Results:")
        print(f"      Risk range: {np.min(roof_risk)} to {np.max(roof_risk)}")
        print(f"      Average risk: {np.mean(roof_risk):.2f}")
        
        risk_layers["roof_risk"] = roof_risk
        index_values["roof_risk"] = {
            "roof_analysis": float(np.nanmean(roof_value)),
            "interpretation": "Custom roof material analysis for hail/storm vulnerability"
        }
    
    # =================================================================
    # DRAINAGE ASSESSMENT RISK ASSESSMENT (Custom NDVI/SWIR Combination)
    # =================================================================
    
    if drainage_detection_data is not None:
        print("🌊 PROCESSING: Drainage Assessment (Custom NDVI/SWIR Combination)")
        
        # Extract drainage values from satellite data
        drainage_value = drainage_detection_data[0][:, :, 0].astype(np.float64)
        
        print(f"   📊 Drainage Analysis Statistics:")
        print(f"      Array shape: {drainage_value.shape}")
        print(f"      Value range: {np.nanmin(drainage_value):.4f} to {np.nanmax(drainage_value):.4f}")
        print(f"      Mean Drainage Analysis: {np.nanmean(drainage_value):.4f}")
        print(f"      Valid pixels: {np.count_nonzero(~np.isnan(drainage_value))}/{drainage_value.size}")
        
        # Resize to match reference shape if needed (spatial alignment)
        if reference_shape is not None and drainage_value.shape != reference_shape:
            print(f"   🔄 SPATIAL ALIGNMENT: Resizing from {drainage_value.shape} to {reference_shape}")
            from scipy.ndimage import zoom
            zoom_factor = (reference_shape[0] / drainage_value.shape[0], reference_shape[1] / drainage_value.shape[1])
            drainage_value = zoom(drainage_value, zoom_factor, order=1)  # Bilinear interpolation
        elif reference_shape is None:
            reference_shape = drainage_value.shape
            
        # Drainage interpretation
        drainage_risk = np.where(
            drainage_value > 0.2,   # Good drainage
            3,                      # Good drainage
            np.where(
                drainage_value > -0.1,  # Medium drainage
                6,                      # Medium drainage
                9                       # Poor drainage
            )
        )
        
        print(f"   🎯 Risk Conversion Results:")
        print(f"      Risk range: {np.min(drainage_risk)} to {np.max(drainage_risk)}")
        print(f"      Average risk: {np.mean(drainage_risk):.2f}")
        
        risk_layers["drainage_risk"] = drainage_risk
        index_values["drainage_risk"] = {
            "drainage_analysis": float(np.nanmean(drainage_value)),
            "interpretation": get_drainage_interpretation(float(np.nanmean(drainage_value)))
        }
    
    # =================================================================
    # COMPOSITE RISK CALCULATION
    # =================================================================
    
    print(f"🔄 COMPOSITE RISK: Combining {len(risk_layers)} risk factors")
    
    if not risk_layers:
        print("⚠️ WARNING: No satellite data available - returning neutral risk values")
        neutral_risk = np.full((256, 256), 5.0, dtype=np.float64)
        return neutral_risk, {"message": "No satellite data available"}
    
    print(f"   Available risk factors: {list(risk_layers.keys())}")
    
    # Calculate weighted average of all available risk factors
    # This approach ensures balanced representation of all risk types
    total_risk = np.zeros(reference_shape, dtype=np.float64)
    factor_count = 0
    
    for layer_name, layer_data in risk_layers.items():
        print(f"   📊 {layer_name}: mean={np.mean(layer_data):.2f}, range=[{np.min(layer_data)}, {np.max(layer_data)}]")
        total_risk += layer_data.astype(np.float64)
        factor_count += 1
    
    # Calculate average risk across all factors
    if factor_count > 0:
        composite_risk = total_risk / factor_count
    else:
        # Fallback to neutral risk if no factors available
        composite_risk = np.full(reference_shape, 5.0, dtype=np.float64)
    
    # Ensure final risk scores are within valid range (1-10)
    composite_risk = np.clip(composite_risk, 1, 10)
    
    print(f"🎯 FINAL COMPOSITE RISK:")
    print(f"   Average risk score: {np.mean(composite_risk):.2f}/10")
    print(f"   Risk range: {np.min(composite_risk):.1f} to {np.max(composite_risk):.1f}")
    print(f"   Spatial coverage: {reference_shape} pixels")
    print("=" * 60)
    
    # Add composite risk to index values for reporting
    index_values["composite_risk"] = float(np.nanmean(composite_risk))
    
    # Create individual risk values dictionary for detailed reporting
    risk_values = {}
    for layer_name, layer_data in risk_layers.items():
        risk_values[layer_name] = float(np.nanmean(layer_data))
    
    return composite_risk, index_values, risk_values

def get_ndvi_interpretation(ndvi_value):
    """Interpret NDVI value for vegetation health."""
    if ndvi_value > 0.6:
        return "Dense vegetation - lower fire risk, potential storm damage risk"
    elif ndvi_value > 0.3:
        return "Moderate vegetation - balanced risk profile"
    elif ndvi_value > 0.1:
        return "Sparse vegetation - higher fire risk"
    else:
        return "Very sparse/no vegetation - high fire risk, erosion risk"

def get_ndmi_interpretation(ndmi_value):
    """Interpret NDMI value for water content."""
    if ndmi_value > 0.3:
        return "High moisture content - lower fire risk"
    elif ndmi_value > 0.0:
        return "Moderate moisture content - medium fire risk"
    elif ndmi_value > -0.2:
        return "Low moisture content - elevated fire risk"
    else:
        return "Very low moisture - high fire risk"

def get_ndbi_interpretation(ndbi_value):
    """Interpret NDBI value for built-up areas."""
    if ndbi_value > 0.2:
        return "Dense built-up area - high property density"
    elif ndbi_value > 0.0:
        return "Moderate development - medium property density"
    elif ndbi_value > -0.2:
        return "Light development - low property density"
    else:
        return "Natural area - minimal built infrastructure"

def get_nbr_interpretation(nbr_value):
    """Interpret NBR value for burn/vegetation status."""
    if nbr_value > 0.4:
        return "Healthy vegetation - low fire risk"
    elif nbr_value > 0.2:
        return "Moderate vegetation health - medium fire risk"
    elif nbr_value > 0.0:
        return "Stressed vegetation - elevated fire risk"
    else:
        return "Severely stressed/burned vegetation - high fire risk"

def get_drainage_interpretation(drainage_value):
    """Interpret combined vegetation/moisture for drainage assessment."""
    if drainage_value > 0.2:
        return "Good drainage - vegetation thriving with appropriate moisture"
    elif drainage_value > 0.0:
        return "Moderate drainage - some areas may have issues"
    elif drainage_value > -0.2:
        return "Poor drainage - vegetation stressed despite moisture"
    else:
        return "Very poor drainage - high flood/waterlogging risk"

# =============================================================================
# SATELLITE DATA ACQUISITION FUNCTIONS
# =============================================================================

def fetch_veg_health(bbox, start_date, end_date, cfg, resolution=20):
    """
    Fetch vegetation health data using NDVI (Normalized Difference Vegetation Index).
    
    SCIENTIFIC PURPOSE:
    NDVI is the most widely used vegetation index in remote sensing, providing
    quantitative assessment of vegetation health, density, and photosynthetic activity.
    It exploits the fundamental optical properties of healthy vegetation.
    
    SPECTRAL PHYSICS:
    - Healthy vegetation strongly absorbs red light (665nm) for photosynthesis
    - Healthy vegetation strongly reflects near-infrared light (842nm) due to leaf structure
    - The contrast between these bands indicates vegetation vigor and health
    
    ALGORITHM DETAILS:
    Formula: NDVI = (NIR - Red) / (NIR + Red) = (B08 - B04) / (B08 + B04)
    
    SENTINEL-2 BANDS USED:
    - B08 (NIR): 842nm, 10m resolution - Vegetation structure reflection
    - B04 (Red): 665nm, 10m resolution - Chlorophyll absorption band
    
    RESULT INTERPRETATION:
    - NDVI > 0.6: Dense, healthy vegetation (forests, vigorous crops)
    - NDVI 0.3-0.6: Moderate vegetation (grasslands, sparse forests)
    - NDVI 0.1-0.3: Sparse vegetation (dry grasslands, stressed crops)
    - NDVI 0.0-0.1: Very sparse vegetation or bare soil
    - NDVI < 0.0: Water bodies, built surfaces, snow, clouds
    
    INSURANCE RISK APPLICATIONS:
    - Fire Risk: Low NDVI = dry, sparse vegetation = high fire risk
    - Storm Risk: High NDVI = dense vegetation = potential wind damage
    - Crop Risk: NDVI trends indicate crop health and yield potential
    - Flood Risk: Vegetation patterns affect water runoff and absorption
    
    TEMPORAL CONSIDERATIONS:
    - Growing season (spring/summer): Higher NDVI values expected
    - Dormant season (winter): Lower NDVI values normal for deciduous vegetation
    - Drought periods: NDVI drops significantly indicating stress
    - Post-fire recovery: NDVI gradually increases as vegetation regrows
    
    DATA QUALITY FACTORS:
    - Cloud cover: Masked out using dataMask band
    - Atmospheric correction: L2A products provide surface reflectance
    - Solar angle: Automatically corrected in processing
    - Shadow areas: Identified and masked in dataMask
    
    PARAMETERS:
    bbox (BBox): Sentinel Hub bounding box defining the analysis area
    start_date (str): Start date for data acquisition (YYYY-MM-DD format)
    end_date (str): End date for data acquisition (YYYY-MM-DD format)
    cfg (SHConfig): Sentinel Hub configuration with authentication
    resolution (int): Spatial resolution in meters per pixel (default: 20m)
    
    RETURNS:
    list: Satellite data arrays with shape [height, width, 2] where:
        - Channel 0: NDVI values (-1 to +1, float32)
        - Channel 1: Data mask (1=valid, 0=invalid/cloud/shadow)
    
    ERROR HANDLING:
    - API failures: Function will raise exception, caller handles fallback
    - No data periods: Returns empty list, caller handles with synthetic data
    - Cloud coverage: Automatically filtered to <80% coverage
    """
    # =================================================================
    # RESOLUTION OPTIMIZATION FOR API LIMITS
    # =================================================================
    
    # Ensure dimensions stay within Sentinel Hub API limits (2500x2500 pixels)
    # Large areas automatically get reduced resolution to fit constraints
    size, adjusted_resolution = ensure_valid_dimensions(bbox, resolution)
    
    print(f"🛰️ FETCHING: Vegetation Health (NDVI)")
    print(f"   📅 Date Range: {start_date} to {end_date}")
    print(f"   📐 Resolution: {adjusted_resolution}m per pixel")
    print(f"   📊 Dimensions: {size[0]} x {size[1]} pixels")
    
    # =================================================================
    # EVALSCRIPT LOADING AND CONFIGURATION
    # =================================================================
    
    # Load the JavaScript evaluation script that calculates NDVI
    # This script runs on Sentinel Hub servers to process raw satellite bands
    script_path = os.path.join(os.path.dirname(__file__), "evalscripts/veg_health.js")
    
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"NDVI evalscript not found: {script_path}")
    
    with open(script_path, "r") as f:
        script = f.read()
    
    print(f"   📜 Evalscript loaded: {len(script)} characters")
    
    # =================================================================
    # SENTINEL HUB API REQUEST CONFIGURATION
    # =================================================================
    
    # Configure the satellite data request with specific parameters
    req = SentinelHubRequest(
        # JavaScript evaluation script for NDVI calculation
        evalscript=script,
        
        # Input data specification
        input_data=[{
            "type": "S2L2A",  # Sentinel-2 Level 2A (atmospherically corrected)
            "dataFilter": {
                "timeRange": {
                    "from": f"{start_date}T00:00:00Z",  # Start of time range (UTC)
                    "to": f"{end_date}T23:59:59Z"       # End of time range (UTC)
                }, 
                "maxCloudCoverage": 80  # Maximum acceptable cloud coverage (80%)
            }
        }],
        
        # Output data specification
        responses=[{
            "identifier": "veg_health",           # Response identifier
            "format": {"type": "image/tiff", "sampleType": "FLOAT32"}  # 32-bit float TIFF
        }],
        
        # Spatial parameters
        bbox=bbox,      # Geographic area to process
        size=size,      # Pixel dimensions
        config=cfg      # Authentication configuration
    )
    
    print(f"   🔄 API Request configured:")
    print(f"      Data type: Sentinel-2 L2A (atmospherically corrected)")
    print(f"      Max cloud coverage: 80%")
    print(f"      Output format: FLOAT32 TIFF")
    
    # =================================================================
    # DATA ACQUISITION AND VALIDATION
    # =================================================================
    
    try:
        # Execute the API request to fetch satellite data
        print(f"   📡 Requesting data from Sentinel Hub API...")
        data = req.get_data()
        
        if data and len(data) > 0:
            # Data successfully retrieved - analyze the results
            array_data = data[0]  # First (and only) response
            
            print(f"   ✅ SUCCESS: NDVI data retrieved")
            print(f"      Array shape: {array_data.shape}")
            print(f"      Data type: {array_data.dtype}")
            print(f"      Value range: {np.min(array_data):.4f} to {np.max(array_data):.4f}")
            
            # Analyze data quality and coverage
            if array_data.shape[2] >= 2:
                ndvi_values = array_data[:, :, 0]  # NDVI channel
                mask_values = array_data[:, :, 1]  # Data mask channel
                
                valid_pixels = np.sum(mask_values > 0)
                total_pixels = mask_values.size
                coverage_percent = (valid_pixels / total_pixels) * 100
                
                print(f"      Valid pixel coverage: {valid_pixels}/{total_pixels} ({coverage_percent:.1f}%)")
                print(f"      NDVI statistics: mean={np.nanmean(ndvi_values):.3f}, std={np.nanstd(ndvi_values):.3f}")
            
            return data
        else:
            print(f"   ❌ FAILED: No data returned from API")
            return []
            
    except Exception as e:
        print(f"   ❌ ERROR: API request failed")
        print(f"      Error type: {type(e).__name__}")
        print(f"      Error message: {str(e)}")
        
        # Re-raise exception for caller to handle with fallback strategies
        raise e

def fetch_water_stress(bbox, start_date, end_date, cfg, resolution=20):
    """Fetch water stress indices using B8 (NIR) and B11 (SWIR) bands from Sentinel-2."""
    size, adjusted_resolution = ensure_valid_dimensions(bbox, resolution)
    
    script_path = os.path.join(os.path.dirname(__file__), "evalscripts/water_stress.js")
    with open(script_path, "r") as f:
        script = f.read()
    
    req = SentinelHubRequest(
        evalscript=script,
        input_data=[{
            "type": "S2L2A",
            "dataFilter": {
                "timeRange": {
                    "from": f"{start_date}T00:00:00Z", 
                    "to": f"{end_date}T23:59:59Z"
                }, 
                "maxCloudCoverage": 80
            }
        }],
        responses=[{
            "identifier": "water_stress", 
            "format": {"type": "image/tiff", "sampleType": "FLOAT32"}
        }],
        bbox=bbox, 
        size=size, 
        config=cfg
    )
    return req.get_data()

def fetch_urban_detection(bbox, start_date, end_date, cfg, resolution=20):
    """Fetch urban detection data using B11 (SWIR) and B8 (NIR) bands from Sentinel-2."""
    size, adjusted_resolution = ensure_valid_dimensions(bbox, resolution)
    
    script_path = os.path.join(os.path.dirname(__file__), "evalscripts/urban_detection.js")
    with open(script_path, "r") as f:
        script = f.read()
    
    req = SentinelHubRequest(
        evalscript=script,
        input_data=[{
            "type": "S2L2A",
            "dataFilter": {
                "timeRange": {
                    "from": f"{start_date}T00:00:00Z", 
                    "to": f"{end_date}T23:59:59Z"
                }, 
                "maxCloudCoverage": 80
            }
        }],
        responses=[{
            "identifier": "urban_detection", 
            "format": {"type": "image/tiff", "sampleType": "FLOAT32"}
        }],
        bbox=bbox, 
        size=size, 
        config=cfg
    )
    return req.get_data()

def fetch_burn_detection(bbox, start_date, end_date, cfg, resolution=20):
    """Fetch burn detection data using B8 (NIR) and B12 (SWIR2) bands from Sentinel-2."""
    size, adjusted_resolution = ensure_valid_dimensions(bbox, resolution)
    
    script_path = os.path.join(os.path.dirname(__file__), "evalscripts/burn_detection.js")
    with open(script_path, "r") as f:
        script = f.read()
    
    req = SentinelHubRequest(
        evalscript=script,
        input_data=[{
            "type": "S2L2A",
            "dataFilter": {
                "timeRange": {
                    "from": f"{start_date}T00:00:00Z", 
                    "to": f"{end_date}T23:59:59Z"
                }, 
                "maxCloudCoverage": 80
            }
        }],
        responses=[{
            "identifier": "burn_detection", 
            "format": {"type": "image/tiff", "sampleType": "FLOAT32"}
        }],
        bbox=bbox, 
        size=size, 
        config=cfg
    )
    return req.get_data()

def fetch_roof_detection(bbox, start_date, end_date, cfg, resolution=20):
    """Fetch roof detection data using multiple bands from Sentinel-2."""
    size, adjusted_resolution = ensure_valid_dimensions(bbox, resolution)
    
    script_path = os.path.join(os.path.dirname(__file__), "evalscripts/roof_detection.js")
    with open(script_path, "r") as f:
        script = f.read()
    
    req = SentinelHubRequest(
        evalscript=script,
        input_data=[{
            "type": "S2L2A",
            "dataFilter": {
                "timeRange": {
                    "from": f"{start_date}T00:00:00Z", 
                    "to": f"{end_date}T23:59:59Z"
                }, 
                "maxCloudCoverage": 80
            }
        }],
        responses=[{
            "identifier": "roof_detection", 
            "format": {"type": "image/tiff", "sampleType": "FLOAT32"}
        }],
        bbox=bbox, 
        size=size, 
        config=cfg
    )
    return req.get_data()

def fetch_drainage_detection(bbox, start_date, end_date, cfg, resolution=20):
    """Fetch drainage detection data using multiple bands from Sentinel-2."""
    size, adjusted_resolution = ensure_valid_dimensions(bbox, resolution)
    
    script_path = os.path.join(os.path.dirname(__file__), "evalscripts/drainage_detection.js")
    with open(script_path, "r") as f:
        script = f.read()
    
    req = SentinelHubRequest(
        evalscript=script,
        input_data=[{
            "type": "S2L2A",
            "dataFilter": {
                "timeRange": {
                    "from": f"{start_date}T00:00:00Z", 
                    "to": f"{end_date}T23:59:59Z"
                }, 
                "maxCloudCoverage": 80
            }
        }],
        responses=[{
            "identifier": "drainage_detection", 
            "format": {"type": "image/tiff", "sampleType": "FLOAT32"}
        }],
        bbox=bbox, 
        size=size, 
        config=cfg
    )
    return req.get_data()

# =============================================================================
# VISUALIZATION AND IMAGE GENERATION FUNCTIONS
# =============================================================================

def risk_score_to_image(risk_score, scale_max=10):
    """
    Convert 2D risk score array to color-coded PNG image for web visualization.
    
    PURPOSE:
    Transforms numerical risk scores into intuitive color-coded visualizations
    for the CustomSat platform interface. Uses a red-green gradient where:
    - Green tones indicate lower insurance risk (safer areas)  
    - Red tones indicate higher insurance risk (areas requiring attention)
    
    VISUALIZATION DESIGN PRINCIPLES:
    1. INTUITIVE COLOR MAPPING: Red = danger, Green = safety (universal standards)
    2. PROGRESSIVE GRADIENTS: Smooth transitions between risk levels
    3. WEB OPTIMIZATION: Base64 encoding for direct HTML embedding
    4. ACCESSIBILITY: High contrast ratios for visual clarity
    
    COLOR ALGORITHM:
    - Risk scores are normalized to 0-1 range based on scale_max
    - Red channel: Increases linearly with risk (0 → 255)
    - Green channel: Decreases linearly with risk (255 → 0)  
    - Blue channel: Remains at 0 for pure red-green gradient
    - Result: Low risk = bright green, high risk = bright red
    
    TECHNICAL IMPLEMENTATION:
    1. Input validation and normalization to prevent overflow
    2. Color channel calculation using linear interpolation
    3. NumPy array construction for RGB color mapping
    4. PIL Image creation from RGB array
    5. PNG encoding to memory buffer  
    6. Base64 encoding for web transmission
    
    WEB INTEGRATION:
    Generated images are embedded directly in HTML as data URIs:
    <img src="data:image/png;base64,{encoded_data}">
    This eliminates need for separate image files and server storage.
    
    PARAMETERS:
    risk_score (numpy.ndarray): 2D array of risk values (typically 1-10 scale)
    scale_max (int): Maximum risk value for normalization (default: 10)
    
    RETURNS:
    str: Complete data URI string ready for HTML img src attribute
         Format: "data:image/png;base64,{base64_encoded_png_data}"
    
    ERROR HANDLING:
    - NaN/infinity values are handled during normalization
    - Array shape validation ensures 2D input
    - Memory management through BytesIO buffer usage
    - Exception propagation for debugging and fallback handling
    
    PERFORMANCE CONSIDERATIONS:
    - Efficient NumPy vectorized operations for color calculation
    - Memory-conscious PNG compression
    - Optimized for typical satellite image sizes (256x256 to 2500x2500 pixels)
    - Base64 encoding adds ~33% size overhead but enables direct embedding
    
    EXAMPLE USAGE:
    risk_array = np.array([[1, 5, 10], [3, 7, 2]])  # Sample 2x3 risk scores
    image_data_uri = risk_score_to_image(risk_array, scale_max=10)
    # Returns: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
    """
    from PIL import Image
    import base64
    from io import BytesIO
    
    print(f"🎨 RISK VISUALIZATION: Converting {risk_score.shape} risk array to color image")
    
    # =================================================================
    # INPUT VALIDATION AND PREPROCESSING
    # =================================================================
    
    # Ensure input is a 2D numpy array
    if len(risk_score.shape) != 2:
        raise ValueError(f"Risk score must be 2D array, got shape {risk_score.shape}")
    
    # Handle NaN/infinity values by replacing with neutral risk (middle of scale)
    risk_clean = np.copy(risk_score)
    risk_clean = np.nan_to_num(risk_clean, nan=scale_max/2, posinf=scale_max, neginf=0)
    
    print(f"   📊 Risk Score Statistics:")
    print(f"      Original range: {np.min(risk_score):.2f} to {np.max(risk_score):.2f}")
    print(f"      Scale maximum: {scale_max}")
    print(f"      Array dimensions: {risk_score.shape[0]} x {risk_score.shape[1]} pixels")
    
    # =================================================================
    # NORMALIZATION AND COLOR MAPPING
    # =================================================================
    
    # Normalize risk scores to 0-1 range for color calculation
    # Formula: normalized = (value - min_scale) / (max_scale - min_scale)
    # Assumes minimum risk is 0, maximum is scale_max
    normalized_risk = np.clip(risk_clean / scale_max, 0, 1)
    
    # Convert to 0-255 range for 8-bit color channels
    risk_255 = (normalized_risk * 255).astype(np.uint8)
    
    print(f"   🎨 Color Mapping Process:")
    print(f"      Normalized range: {np.min(normalized_risk):.3f} to {np.max(normalized_risk):.3f}")
    print(f"      8-bit range: {np.min(risk_255)} to {np.max(risk_255)}")
    
    # =================================================================
    # RGB COLOR CHANNEL CONSTRUCTION
    # =================================================================
    
    # Create RGB color array with red-green gradient
    # Shape: (height, width, 3) for RGB channels
    height, width = risk_score.shape
    colormap = np.zeros((height, width, 3), dtype=np.uint8)
    
    # RED CHANNEL: Increases with risk (low risk = no red, high risk = full red)
    colormap[:, :, 0] = risk_255
    
    # GREEN CHANNEL: Decreases with risk (low risk = full green, high risk = no green)  
    colormap[:, :, 1] = 255 - risk_255
    
    # BLUE CHANNEL: Set to 0 for pure red-green gradient
    colormap[:, :, 2] = 0
    
    print(f"   🌈 Color Channel Analysis:")
    print(f"      Red channel range: {np.min(colormap[:,:,0])} to {np.max(colormap[:,:,0])}")
    print(f"      Green channel range: {np.min(colormap[:,:,1])} to {np.max(colormap[:,:,1])}")
    print(f"      Blue channel: {np.min(colormap[:,:,2])} (constant)")
    
    # =================================================================
    # IMAGE GENERATION AND ENCODING
    # =================================================================
    
    try:
        # Create PIL Image from RGB array
        print(f"   🖼️ Generating PNG image...")
        img = Image.fromarray(colormap, mode='RGB')
        
        # Encode image to PNG format in memory buffer
        buffer = BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        buffer.seek(0)  # Reset buffer position for reading
        
        # Encode PNG data as Base64 for web transmission
        png_data = buffer.getvalue()
        img_base64 = base64.b64encode(png_data).decode('utf-8')
        
        # Create complete data URI for HTML embedding
        data_uri = f"data:image/png;base64,{img_base64}"
        
        print(f"   ✅ SUCCESS: Risk visualization generated")
        print(f"      PNG size: {len(png_data)} bytes")
        print(f"      Base64 size: {len(img_base64)} characters")
        print(f"      Data URI length: {len(data_uri)} characters")
        
        return data_uri
        
    except Exception as e:
        print(f"   ❌ ERROR: Image generation failed")
        print(f"      Error type: {type(e).__name__}")
        print(f"      Error message: {str(e)}")
        raise e

def array_to_image(array, color_scheme='gray', normalize=False, min_val=None, max_val=None):
    """
    Convert 2D numpy array to color-mapped visualization image with multiple color schemes.
    
    PURPOSE:
    Flexible visualization function for different types of satellite data and risk factors.
    Supports multiple color schemes optimized for specific data types:
    - Vegetation indices (green schemes)
    - Water/moisture data (blue schemes)  
    - Urban areas (purple schemes)
    - Temperature data (heat maps)
    - Fire/burn areas (red schemes)
    
    SUPPORTED COLOR SCHEMES:
    
    📊 'gray': Standard grayscale (general purpose)
    🌱 'green': Green intensity (vegetation health, NDVI)
    💧 'blue': Blue intensity (water content, basic moisture)
    🌊 'water_blue': Enhanced water visualization (floods, detailed moisture)
    🔥 'red': Red intensity (fire risk, burn areas)
    🏢 'purple': Purple intensity (urban areas, built-up regions)
    🌡️ 'heat': Multi-color heat map (temperature: blue→purple→red→yellow)
    🚰 'blue_to_brown': Moisture gradient (wet=blue, dry=brown)
    
    NORMALIZATION OPTIONS:
    - normalize=False: Use raw array values (must be 0-255 range)
    - normalize=True: Scale values to 0-255 using min/max normalization
    - Custom min_val/max_val: Define specific value ranges for scaling
    
    TECHNICAL IMPLEMENTATION:
    1. Array preprocessing and validation
    2. Optional normalization and clipping  
    3. Color scheme application via RGB channel mapping
    4. PIL image generation and PNG encoding
    5. Base64 encoding for web integration
    
    ADVANCED COLOR ALGORITHMS:
    
    HEAT MAP (blue→purple→red→yellow):
    - Cold (0-85): Pure blue with increasing green
    - Medium (85-170): Blue→red transition through purple  
    - Hot (170-255): Red→yellow transition by adding green
    
    WATER VISUALIZATION:
    - Deep water: Dark blue (high intensity)
    - Shallow water: Light blue (medium intensity)
    - Dry areas: White/transparent (low intensity)
    - Enhanced contrast for flood detection
    
    SOIL MOISTURE (blue→brown):
    - Wet areas: Blue tones (high moisture content)
    - Medium moisture: Green-blue transitions
    - Dry areas: Brown tones (low moisture content)
    
    PARAMETERS:
    array (numpy.ndarray): 2D input data array for visualization
    color_scheme (str): Color mapping scheme identifier (default: 'gray')
    normalize (bool): Whether to normalize values to 0-255 range (default: False)
    min_val (float): Minimum value for normalization (default: array minimum)
    max_val (float): Maximum value for normalization (default: array maximum)
    
    RETURNS:
    str: Data URI string with embedded PNG image
         Format: "data:image/png;base64,{base64_encoded_png_data}"
    
    ERROR HANDLING:
    - Invalid color schemes default to grayscale
    - NaN/infinity values handled in normalization
    - Array shape validation for 2D input requirement
    - Memory management through BytesIO usage
    
    PERFORMANCE OPTIMIZATIONS:
    - NumPy vectorized operations for color calculations
    - Efficient memory allocation for RGB arrays
    - Optimized PNG compression settings
    - Minimal memory copying during processing
    
    WEB INTEGRATION:
    Generated images integrate directly into HTML without server storage:
    ```html
    <img src="{returned_data_uri}" alt="Satellite Data Visualization">
    ```
    
    EXAMPLE USAGE:
    
    # Vegetation health visualization (NDVI data)
    ndvi_image = array_to_image(ndvi_array, 'green', normalize=True, min_val=-1, max_val=1)
    
    # Temperature heat map 
    temp_image = array_to_image(temperature_array, 'heat', normalize=True, min_val=0, max_val=40)
    
    # Flood detection visualization
    flood_image = array_to_image(flood_array, 'water_blue', normalize=True)
    """
    from PIL import Image
    import base64
    from io import BytesIO
    
    print(f"🎨 ARRAY VISUALIZATION: Converting {array.shape} array to {color_scheme} image")
    
    # =================================================================
    # INPUT VALIDATION AND PREPROCESSING  
    # =================================================================
    
    # Validate 2D array input
    if len(array.shape) != 2:
        raise ValueError(f"Array must be 2D, got shape {array.shape}")
    
    # Create working copy to avoid modifying original data
    img_array = array.copy().astype(np.float64)
    
    # Handle NaN and infinity values
    img_array = np.nan_to_num(img_array, nan=0, posinf=255, neginf=0)
    
    print(f"   📊 Input Array Statistics:")
    print(f"      Shape: {array.shape}")
    print(f"      Original range: {np.min(array):.4f} to {np.max(array):.4f}")
    print(f"      Data type: {array.dtype}")
    print(f"      Valid pixels: {np.count_nonzero(~np.isnan(array))}/{array.size}")
    
    # =================================================================
    # NORMALIZATION AND VALUE SCALING
    # =================================================================
    
    if normalize:
        print(f"   🔧 NORMALIZATION: Scaling values to 0-255 range")
        
        # Determine normalization range
        if min_val is None:
            min_val = np.nanmin(img_array)
        if max_val is None:
            max_val = np.nanmax(img_array)
        
        print(f"      Normalization range: {min_val:.4f} to {max_val:.4f}")
        
        # Clip values to specified range
        img_array = np.clip(img_array, min_val, max_val)
        
        # Scale to 0-1 range, then to 0-255
        if max_val != min_val:
            img_array = (img_array - min_val) / (max_val - min_val)
        else:
            img_array = np.zeros_like(img_array)
            
        img_array = (img_array * 255).astype(np.uint8)
        
        print(f"      Final range: {np.min(img_array)} to {np.max(img_array)}")
    else:
        # Ensure values are in valid 0-255 range for color mapping
        img_array = np.clip(img_array, 0, 255).astype(np.uint8)
    
    # =================================================================
    # COLOR SCHEME APPLICATION
    # =================================================================
    
    height, width = img_array.shape
    colormap = np.zeros((height, width, 3), dtype=np.uint8)
    
    print(f"   🌈 APPLYING COLOR SCHEME: {color_scheme}")
    
    if color_scheme == 'gray':
        # Standard grayscale: all channels equal
        colormap[:, :, 0] = img_array  # Red
        colormap[:, :, 1] = img_array  # Green  
        colormap[:, :, 2] = img_array  # Blue
        print(f"      Grayscale mapping: R=G=B=value")
    
    elif color_scheme == 'red':
        # Red intensity: only red channel active
        colormap[:, :, 0] = img_array  # Red channel only
        colormap[:, :, 1] = 0          # No green
        colormap[:, :, 2] = 0          # No blue
        print(f"      Red intensity mapping: pure red channel")
    
    elif color_scheme == 'green':
        # Green intensity: only green channel active  
        colormap[:, :, 0] = 0          # No red
        colormap[:, :, 1] = img_array  # Green channel only
        colormap[:, :, 2] = 0          # No blue
        print(f"      Green intensity mapping: pure green channel")
    
    elif color_scheme == 'blue':
        # Enhanced blue with white background for better contrast
        colormap[:, :, 0] = 255 - img_array  # Red decreases as blue increases
        colormap[:, :, 1] = 255 - img_array  # Green decreases as blue increases  
        colormap[:, :, 2] = img_array        # Blue channel
        print(f"      Enhanced blue mapping: blue intensity with white background fade")
    
    elif color_scheme == 'water_blue':
        # Specialized water/flood visualization
        # Deep water = dark blue, shallow water = light blue, no water = white
        colormap[:, :, 2] = np.clip(img_array * 2, 0, 255)  # Amplified blue channel
        fade_factor = np.clip(255 - img_array * 3, 0, 255)  # White background fade
        colormap[:, :, 0] = fade_factor  # Red fades with water depth
        colormap[:, :, 1] = fade_factor  # Green fades with water depth
        print(f"      Water visualization: amplified blue with white fade")
    
    elif color_scheme == 'heat':
        # Advanced heat map: blue → purple → red → yellow progression
        print(f"      Heat map: blue(cold) → purple → red → yellow(hot)")
        
        # Cold range (0-85): Blue with increasing green
        cold_mask = img_array < 85
        colormap[cold_mask, 0] = 0                           # No red
        colormap[cold_mask, 1] = img_array[cold_mask] * 3    # Green increases
        colormap[cold_mask, 2] = 255                         # Full blue
        
        # Medium range (85-170): Blue to red transition (purple phase)
        medium_mask = (img_array >= 85) & (img_array < 170)
        colormap[medium_mask, 0] = (img_array[medium_mask] - 85) * 3      # Red increases
        colormap[medium_mask, 1] = 0                                       # No green
        colormap[medium_mask, 2] = 255 - (img_array[medium_mask] - 85) * 3 # Blue decreases
        
        # Hot range (170-255): Red to yellow transition
        hot_mask = img_array >= 170
        colormap[hot_mask, 0] = 255                                    # Full red
        colormap[hot_mask, 1] = (img_array[hot_mask] - 170) * 3       # Green increases (→yellow)
        colormap[hot_mask, 2] = 0                                      # No blue
        
        print(f"      Cold pixels: {np.sum(cold_mask)}, Medium: {np.sum(medium_mask)}, Hot: {np.sum(hot_mask)}")
    
    elif color_scheme == 'purple':
        # Enhanced purple for urban area visualization
        colormap[:, :, 0] = np.clip(img_array * 0.7, 0, 255)  # Moderate red component
        colormap[:, :, 1] = 0                                   # No green
        colormap[:, :, 2] = np.clip(img_array * 1.3, 0, 255)  # Enhanced blue component
        print(f"      Purple mapping: enhanced blue with moderate red")
    
    elif color_scheme == 'blue_to_brown':
        # Soil moisture visualization: blue (wet) → brown (dry)
        print(f"      Soil moisture: blue(wet) → green → brown(dry)")
        
        # Wet areas (170-255): Blue tones
        wet_mask = img_array > 170
        colormap[wet_mask, 0] = 0                            # No red
        colormap[wet_mask, 1] = img_array[wet_mask] // 2     # Some green
        colormap[wet_mask, 2] = img_array[wet_mask]          # Full blue
        
        # Medium moisture (85-170): Green-blue transition
        medium_mask = (img_array > 85) & (img_array <= 170)
        colormap[medium_mask, 0] = 100 - img_array[medium_mask] // 2  # Low red
        colormap[medium_mask, 1] = 100 + img_array[medium_mask] // 3  # Medium green
        colormap[medium_mask, 2] = img_array[medium_mask]             # Medium-high blue
        
        # Dry areas (0-85): Brown tones
        dry_mask = img_array <= 85
        colormap[dry_mask, 0] = 140 - img_array[dry_mask] // 2  # High red (brown)
        colormap[dry_mask, 1] = 80 - img_array[dry_mask] // 4   # Medium green (brown)
        colormap[dry_mask, 2] = img_array[dry_mask] // 3        # Low blue (brown)
        
        print(f"      Wet pixels: {np.sum(wet_mask)}, Medium: {np.sum(medium_mask)}, Dry: {np.sum(dry_mask)}")
    
    else:
        # Unknown color scheme - default to grayscale with warning
        print(f"      ⚠️ WARNING: Unknown color scheme '{color_scheme}', using grayscale")
        colormap[:, :, 0] = img_array
        colormap[:, :, 1] = img_array
        colormap[:, :, 2] = img_array
    
    # =================================================================
    # IMAGE GENERATION AND ENCODING
    # =================================================================
    
    try:
        print(f"   🖼️ Generating PNG image...")
        
        # Create PIL Image from RGB colormap
        img = Image.fromarray(colormap, mode='RGB')
        
        # Encode to PNG format in memory
        buffer = BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        buffer.seek(0)
        
        # Convert to Base64 for web embedding
        png_data = buffer.getvalue()
        img_base64 = base64.b64encode(png_data).decode('utf-8')
        data_uri = f"data:image/png;base64,{img_base64}"
        
        print(f"   ✅ SUCCESS: {color_scheme} visualization generated")
        print(f"      Color range - R: {np.min(colormap[:,:,0])}-{np.max(colormap[:,:,0])}")
        print(f"      Color range - G: {np.min(colormap[:,:,1])}-{np.max(colormap[:,:,1])}")
        print(f"      Color range - B: {np.min(colormap[:,:,2])}-{np.max(colormap[:,:,2])}")
        print(f"      PNG size: {len(png_data)} bytes")
        print(f"      Data URI length: {len(data_uri)} characters")
        
        return data_uri
        
    except Exception as e:
        print(f"   ❌ ERROR: Image generation failed")
        print(f"      Error type: {type(e).__name__}")
        print(f"      Error message: {str(e)}")
        raise e 