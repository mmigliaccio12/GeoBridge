//VERSION=3

/**
 * NDVI - Normalized Difference Vegetation Index
 * 
 * Purpose: Measures vegetation health, density, and photosynthetic activity
 * Algorithm: Exploits the strong absorption of red light and high reflectance of NIR by healthy vegetation
 * 
 * Formula: (NIR - Red) / (NIR + Red) = (B08 - B04) / (B08 + B04)
 * 
 * Scientific Basis:
 * - Healthy vegetation absorbs red light (B04) for photosynthesis
 * - Healthy vegetation strongly reflects near-infrared light (B08) due to leaf structure
 * - The contrast between these two bands indicates vegetation vigor
 * 
 * Result Range: -1 to +1
 * - > 0.6: Dense, healthy vegetation (forests, crops in growing season)
 * - 0.3-0.6: Moderate vegetation (grasslands, sparse forests)
 * - 0.1-0.3: Sparse vegetation (dry grasslands, agricultural areas)
 * - 0.0-0.1: Very sparse vegetation or bare soil
 * - < 0.0: Water bodies, built surfaces, snow, clouds
 * 
 * Fire Risk Application:
 * - Higher NDVI = More vegetation fuel available
 * - Lower NDVI during dry season = Stressed, flammable vegetation
 */

function setup(){ 
  return {
    // Required Sentinel-2 bands for NDVI calculation
    input: ["B08", "B04", "dataMask"], 
    output: {
      bands: 2,  // Band 1: NDVI value, Band 2: Data mask
      id: "veg_health",
      sampleType: "FLOAT32"  // Return floating point values for NDVI (-1 to +1)
    }
  };
}

function evaluatePixel(s){
  // NDVI calculation using standard formula
  // (Near Infrared - Red) / (Near Infrared + Red)
  // 
  // B08 (NIR, 842nm): Strongly reflected by healthy plant tissue
  // B04 (Red, 665nm): Strongly absorbed by chlorophyll for photosynthesis
  // 
  // Note: Sentinel-2 L2A data comes scaled by 10,000
  // DN = 10000 * REFLECTANCE, so we work directly with DN values
  
  // Check for valid data and handle edge cases
  if (s.dataMask === 0 || s.B08 + s.B04 === 0) {
    // No valid data or both bands are zero - return nodata value
    return [0, 0];  // 0 value with 0 mask indicates no data
  }
  
  // Calculate NDVI with scaled values (DN values are 10000 * reflectance)
  // The scaling factor cancels out in the ratio: (10000*NIR - 10000*Red)/(10000*NIR + 10000*Red)
  const value = (s.B08 - s.B04) / (s.B08 + s.B04);
  
  // Handle potential NaN/Inf values
  if (!isFinite(value)) {
    return [0, 0];
  }
  
  // Return the calculated NDVI value and data validity mask
  // dataMask indicates if the pixel has valid data (1) or is cloud/shadow/invalid (0)
  return [value, s.dataMask];
} 