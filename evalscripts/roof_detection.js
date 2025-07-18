//VERSION=3

/**
 * BREI - Bare Roof Exposure Index
 * 
 * Purpose: Identifies roofs that are exposed and vulnerable to weather damage
 * Algorithm: Uses spectral differences between bare roof materials and protected surfaces
 * 
 * Formula: (B11 + B04 - B08 - B02) / (B11 + B04 + B08 + B02)
 * 
 * Band Interpretation:
 * - B02 (Blue): High reflectance for water, atmosphere - subtracted to reduce false positives
 * - B04 (Red): High reflectance for dry materials like concrete, metal roofs - added
 * - B08 (NIR): High reflectance for vegetation, low for bare surfaces - subtracted to exclude vegetation
 * - B11 (SWIR): High reflectance for dry building materials - added to enhance roof signal
 * 
 * Result Range: Typically -1 to +1
 * - Positive values: Likely exposed roof materials (concrete, metal, asphalt)
 * - Negative values: Vegetation-covered or protected surfaces
 * - Higher positive values: More vulnerable to hail/wind damage
 */

function setup(){ 
  return {
    // Required Sentinel-2 bands for BREI calculation
    input: ["B02", "B04", "B08", "B11", "dataMask"], 
    output: {
      bands: 2,  // Band 1: BREI value, Band 2: Data mask
      id: "roof_detection",
      sampleType: "FLOAT32"  // Return floating point values for BREI (-1 to +1)
    }
  };
}

function evaluatePixel(s){
  // BREI - Bare Roof Exposure Index (from specification document)
  // Formula: (B11 + B4 - B8 - B2) / (B11 + B4 + B8 + B2)
  // 
  // Logic:
  // Numerator (B11 + B04 - B08 - B02):
  //   + B11 (SWIR): Enhances dry building materials signal
  //   + B04 (Red): Enhances reflectance of roof materials like concrete/metal
  //   - B08 (NIR): Removes vegetation signal (vegetation has high NIR)
  //   - B02 (Blue): Removes atmospheric/water interference
  //
  // Denominator (B11 + B04 + B08 + B02): Normalizes the index to -1 to +1 range
  //
  // Result: Positive values indicate exposed roof materials vulnerable to weather damage
  const value = (s.B11 + s.B04 - s.B08 - s.B02) / (s.B11 + s.B04 + s.B08 + s.B02);
  
  // Return the calculated BREI value and data validity mask
  // dataMask indicates if the pixel has valid data (1) or is cloud/shadow/invalid (0)
  return [value, s.dataMask];
  
  // OLD IMPLEMENTATION (commented out for reference):
  // Previous custom approach used multiple indices combination
  // Multiple band combination to detect roof materials
  // This will return a value that can be used to identify potential unprotected roofs
  // Blue, Red, NIR, and SWIR bands are used for better discrimination of roof materials
  
  // Calculate multiple indices to help with roof detection
  // const ndvi = (s.B08 - s.B04)/(s.B08 + s.B04); // Vegetation index
  // const ndbi = (s.B11 - s.B08)/(s.B11 + s.B08); // Built-up index
  // const blue_red_ratio = s.B02/s.B04; // Helpful for some roof materials
  
  // Combine indices to detect roof areas (higher values indicate potential roof materials)
  // const value = (ndbi + 1)/2 * (1 - (ndvi + 1)/2) * blue_red_ratio;
} 