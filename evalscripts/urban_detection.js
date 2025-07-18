//VERSION=3

/**
 * NDBI - Normalized Difference Built-up Index
 * 
 * Purpose: Identifies urban and built-up areas in satellite imagery
 * Algorithm: Exploits the spectral difference between built surfaces and vegetation
 * 
 * Formula: (SWIR - NIR) / (SWIR + NIR) = (B11 - B08) / (B11 + B08)
 * 
 * Scientific Basis:
 * - Built surfaces (concrete, asphalt, metal) have higher SWIR reflectance than vegetation
 * - Vegetation has very high NIR reflectance due to leaf structure
 * - Urban materials typically show opposite spectral behavior to vegetation
 * - The index enhances urban areas while suppressing vegetation
 * 
 * Result Range: -1 to +1
 * - > 0.1: Strong built-up areas (dense urban, industrial)
 * - 0.0-0.1: Moderate built-up (suburban, mixed development)
 * - -0.1-0.0: Sparse built-up or bare soil
 * - < -0.1: Natural vegetation or water bodies
 * 
 * Risk Assessment Application:
 * - Higher NDBI = More built infrastructure = Higher property density
 * - Useful for assessing potential economic impact of disasters
 * - Helps identify areas needing evacuation planning
 */

function setup(){ 
  return {
    // Required Sentinel-2 bands for NDBI calculation
    input: ["B11", "B08", "dataMask"], 
    output: {
      bands: 2,  // Band 1: NDBI value, Band 2: Data mask
      id: "urban_detection",
      sampleType: "FLOAT32"  // Return floating point values for NDBI (-1 to +1)
    }
  };
}

function evaluatePixel(s){
  // NDBI calculation using standard formula
  // (Short Wave Infrared - Near Infrared) / (Short Wave Infrared + Near Infrared)
  // 
  // B11 (SWIR, 1610nm): Higher reflectance from built materials (concrete, asphalt)
  // B08 (NIR, 842nm): Very high reflectance from vegetation, lower from built surfaces
  // 
  // High NDBI = SWIR >> NIR = built-up areas
  // Low NDBI = SWIR << NIR = vegetation-covered areas
  const value = (s.B11 - s.B08) / (s.B11 + s.B08);
  
  // Return the calculated NDBI value and data validity mask
  // dataMask indicates if the pixel has valid data (1) or is cloud/shadow/invalid (0)
  return [value, s.dataMask];
} 