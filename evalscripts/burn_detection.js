//VERSION=3

/**
 * NBR - Normalized Burn Ratio
 * 
 * Purpose: Detects burned areas and assesses burn severity in vegetation
 * Algorithm: Compares NIR reflectance with SWIR2 to identify fire-damaged vegetation
 * 
 * Formula: (NIR - SWIR2) / (NIR + SWIR2) = (B08 - B12) / (B08 + B12)
 * 
 * Scientific Basis:
 * - Healthy vegetation has high NIR reflectance (internal leaf structure)
 * - Burned vegetation loses NIR reflectance due to cell damage
 * - SWIR2 (2190nm) penetrates deeper and is sensitive to moisture and char
 * - Fire creates ash and char that increase SWIR2 reflectance
 * 
 * Result Range: -1 to +1
 * - > 0.3: Healthy, unburned vegetation
 * - 0.1-0.3: Moderate vegetation or light burn severity
 * - 0.0-0.1: Sparse vegetation or moderate burn severity
 * - -0.1-0.0: High burn severity (significant vegetation loss)
 * - < -0.1: Very high burn severity (complete vegetation destruction)
 * 
 * Burn Detection Application:
 * - Pre-fire NBR vs Post-fire NBR = Burn severity assessment
 * - Lower NBR = Higher burn severity or fire risk
 * - Used for post-fire damage assessment and recovery monitoring
 */

function setup(){ 
  return {
    // Required Sentinel-2 bands for NBR calculation
    input: ["B08", "B12", "dataMask"], 
    output: {
      bands: 2,  // Band 1: NBR value, Band 2: Data mask
      id: "burn_detection",
      sampleType: "FLOAT32"  // Return floating point values for NBR (-1 to +1)
    }
  };
}

function evaluatePixel(s){
  // NBR calculation using standard formula
  // (Near Infrared - Short Wave Infrared 2) / (Near Infrared + Short Wave Infrared 2)
  // 
  // B08 (NIR, 842nm): High for healthy vegetation, dramatically reduced by fire damage
  // B12 (SWIR2, 2190nm): Sensitive to char and ash, increases after burning
  // 
  // Healthy vegetation: High NIR, moderate SWIR2 = High NBR
  // Burned areas: Low NIR, high SWIR2 = Low/negative NBR
  // The greater the difference between pre and post-fire NBR, the more severe the burn
  const value = (s.B08 - s.B12) / (s.B08 + s.B12);
  
  // Return the calculated NBR value and data validity mask
  // dataMask indicates if the pixel has valid data (1) or is cloud/shadow/invalid (0)
  return [value, s.dataMask];
} 