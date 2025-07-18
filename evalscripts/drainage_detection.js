//VERSION=3

/**
 * DOPI - Drainage Obstruction Proxy Index
 * 
 * Purpose: Identifies areas with potential drainage blockages or poor water flow
 * Algorithm: Combines vegetation sparseness with moisture/built-up indicators
 * 
 * Formula: (1 - NDVI) * (B11 / B08)
 * 
 * Components:
 * - (1 - NDVI): Inverse vegetation index - higher where vegetation is sparse/absent
 * - (B11 / B08): SWIR/NIR ratio - sensitive to moisture and built surfaces
 * 
 * Band Interpretation:
 * - B04 (Red): Used in NDVI calculation to identify vegetation
 * - B08 (NIR): High for vegetation, used in both NDVI and moisture detection
 * - B11 (SWIR): Sensitive to moisture content and built materials
 * 
 * Result Interpretation:
 * - High values: Areas with sparse vegetation AND high moisture/built surfaces
 * - Low values: Well-vegetated areas OR dry natural surfaces
 * - Identifies: Blocked drains, poor drainage in urban areas, waterlogged zones
 */

function setup(){ 
  return {
    // Required Sentinel-2 bands for DOPI calculation
    input: ["B08", "B04", "B11", "dataMask"], 
    output: {
      bands: 2,  // Band 1: DOPI value, Band 2: Data mask
      id: "drainage_detection",
      sampleType: "FLOAT32"  // Return floating point values for DOPI
    }
  };
}

function evaluatePixel(s){
  // DOPI - Drainage Obstruction Proxy Index (from specification document)
  // Formula: (1 - NDVI) * (B11 / B08)
  // 
  // Step 1: Calculate NDVI (Normalized Difference Vegetation Index)
  // NDVI = (NIR - Red) / (NIR + Red)
  // Range: -1 to +1, where +1 = dense vegetation, -1 = water/built surfaces
  const ndvi = (s.B08 - s.B04) / (s.B08 + s.B04);
  
  // Step 2: Calculate inverse vegetation factor (1 - NDVI)
  // This gives higher values where vegetation is sparse or absent
  // Range: 0 to 2, where 2 = no vegetation, 0 = dense vegetation
  const inverse_vegetation = (1 - ndvi);
  
  // Step 3: Calculate moisture/built-up factor (B11 / B08)
  // SWIR/NIR ratio is sensitive to:
  // - Soil moisture (higher SWIR when wet)
  // - Built surfaces (different spectral response than natural)
  // - Stagnant water areas
  const moisture_buildup_factor = (s.B11 / s.B08);
  
  // Step 4: Combine factors to get DOPI
  // High DOPI = sparse vegetation + high moisture/built surfaces
  // = potential drainage problems in urban/developed areas
  const value = inverse_vegetation * moisture_buildup_factor;
  
  // Return the calculated DOPI value and data validity mask
  // dataMask indicates if the pixel has valid data (1) or is cloud/shadow/invalid (0)
  return [value, s.dataMask];
  
  // OLD IMPLEMENTATION (commented out for reference):
  // Previous approach used minimum of NDVI and NDMI
  // Calculate vegetation index
  // const ndvi = (s.B08 - s.B04)/(s.B08 + s.B04);
  
  // Calculate water stress/moisture index
  // const ndmi = (s.B08 - s.B11)/(s.B08 + s.B11);
  
  // Combine to detect potential drainage issues
  // Higher values indicate potential areas with drainage issues
  // This will highlight areas with vegetation stress due to excess water
  // const value = Math.min(ndvi, ndmi);
} 