//VERSION=3

/**
 * NDMI - Normalized Difference Moisture Index (also called Water Stress Index)
 * 
 * Purpose: Measures vegetation water content and moisture stress
 * Algorithm: Compares NIR reflectance with SWIR absorption by water molecules
 * 
 * Formula: (NIR - SWIR) / (NIR + SWIR) = (B08 - B11) / (B08 + B11)
 * 
 * Scientific Basis:
 * - Water strongly absorbs short-wave infrared (SWIR) radiation
 * - Vegetation with high water content shows low SWIR reflectance
 * - NIR remains high for healthy vegetation regardless of water content
 * - The contrast reveals moisture levels within vegetation
 * 
 * Result Range: -1 to +1
 * - > 0.3: High moisture content (well-watered vegetation)
 * - 0.1-0.3: Moderate moisture content
 * - 0.0-0.1: Low moisture (water stress beginning)
 * - -0.1-0.0: Significant water stress
 * - < -0.1: Severe water stress or drought conditions
 * 
 * Fire Risk Application:
 * - Lower NDMI = Drier vegetation = Higher fire risk
 * - Higher NDMI = Moist vegetation = Lower fire risk
 * - Critical for wildfire early warning systems
 */

function setup(){ 
  return {
    // Required Sentinel-2 bands for NDMI calculation
    input: ["B08", "B11", "dataMask"], 
    output: {
      bands: 2,  // Band 1: NDMI value, Band 2: Data mask
      id: "water_stress",
      sampleType: "FLOAT32"  // Return floating point values for NDMI (-1 to +1)
    }
  };
}

function evaluatePixel(s){
  // NDMI calculation using standard formula
  // (Near Infrared - Short Wave Infrared) / (Near Infrared + Short Wave Infrared)
  // 
  // B08 (NIR, 842nm): High reflectance for vegetation, less affected by water content
  // B11 (SWIR, 1610nm): Strongly absorbed by water molecules in plant tissue
  // 
  // High NDMI = NIR >> SWIR = high water content in vegetation
  // Low NDMI = NIR ≈ SWIR = low water content (drought stress)
  const value = (s.B08 - s.B11) / (s.B08 + s.B11);
  
  // Return the calculated NDMI value and data validity mask
  // dataMask indicates if the pixel has valid data (1) or is cloud/shadow/invalid (0)
  return [value, s.dataMask];
} 