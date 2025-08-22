"""
CIF Analyzer - Comprehensive CIF File Analysis
Detects CIF format version, crystallography methods, and field presence.
"""

import re
import os
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
from enum import Enum

try:
    from .cif_dictionary_manager import CIFDictionaryManager
except ImportError:
    # For standalone testing
    from cif_dictionary_manager import CIFDictionaryManager


class CIFVersion(Enum):
    """CIF format versions"""
    CIF1 = "1.0"
    CIF2 = "2.0"
    UNKNOWN = "unknown"


class CrystallographyMethod(Enum):
    """Supported crystallography methods"""
    CORE = "core_crystallography"           # Essential fields for any structure
    ELECTRON_DIFFRACTION = "electron_diffraction"  # 3D electron diffraction
    HIGH_PRESSURE = "high_pressure"         # High-pressure crystallography
    POWDER_DIFFRACTION = "powder_diffraction"  # Powder diffraction
    SINGLE_CRYSTAL = "single_crystal"       # Single crystal diffraction
    NEUTRON_DIFFRACTION = "neutron_diffraction"  # Neutron diffraction
    SYNCHROTRON = "synchrotron"             # Synchrotron radiation
    MAGNETIC_STRUCTURES = "magnetic_structures"  # Magnetic crystallography
    MODULATED_STRUCTURES = "modulated_structures"  # Modulated/incommensurate
    TWINNED_STRUCTURES = "twinned_structures"  # Twinned crystals


@dataclass
class CIFAnalysisResult:
    """Results of CIF file analysis"""
    file_path: str
    cif_version: CIFVersion
    detected_methods: List[CrystallographyMethod]
    present_fields: Set[str]
    field_count: int
    format_indicators: Dict[str, List[str]]  # Evidence for format/method detection
    confidence_scores: Dict[str, float]      # Confidence in each detection
    recommendations: List[str]               # Suggested actions/missing fields


class CIFAnalyzer:
    """
    Comprehensive CIF file analyzer that detects:
    - CIF format version (CIF1 vs CIF2)
    - Crystallography methods being used
    - Present fields and their categories
    - Validation recommendations
    """
    
    def __init__(self, dict_manager: Optional[CIFDictionaryManager] = None):
        """Initialize the CIF analyzer"""
        self.dict_manager = dict_manager or CIFDictionaryManager()
        
        # CIF version detection patterns
        self.cif2_indicators = [
            r'##CIF_2\.0',             # CIF2 header
            r'_[a-zA-Z]+\.[a-zA-Z]+',  # Dot notation fields
            r'save_frame',             # Save frames
            r'loop_\s*_[a-zA-Z]+\.[a-zA-Z]+',  # Loop with dot notation
        ]
        
        self.cif1_indicators = [
            r'#\\#CIF_1\.',            # CIF1 header
            r'data_[a-zA-Z0-9_]+',     # Data blocks
            r'_[a-zA-Z]+_[a-zA-Z]+',   # Underscore notation fields
        ]
        
        # Method detection patterns
        self.method_indicators = {
            CrystallographyMethod.ELECTRON_DIFFRACTION: {
                'required_fields': ['_diffrn_radiation.probe', '_diffrn_radiation_probe'],  # Both CIF1 and CIF2
                'required_values': {
                    '_diffrn_radiation.probe': ['electron'],
                    '_diffrn_radiation_probe': ['electron'],
                    '_diffrn_radiation.type': ['electron'],
                    '_diffrn_radiation_type': ['electron']
                },
                'indicator_fields': [
                    '_diffrn_detector.type', '_diffrn_detector_type', '_exptl_crystal.preparation',
                    '_diffrn_measurement.device_type', '_diffrn_measurement_device_type',
                    '_diffrn_source.voltage', '_diffrn_source_voltage'
                ],
                'keywords': ['electron', 'tem', 'precession', 'microed', '3d ed']
            },
            
            CrystallographyMethod.HIGH_PRESSURE: {
                'indicator_fields': [
                    '_diffrn.ambient_pressure', '_diffrn_ambient_pressure',
                    '_exptl_crystal.pressure_history', '_cell.pressure'
                ],
                'keywords': ['pressure', 'diamond anvil', 'high pressure', 'gpa', 'kbar']
            },
            
            CrystallographyMethod.POWDER_DIFFRACTION: {
                'required_fields': ['_diffrn_measurement.method'],
                'required_values': {
                    '_diffrn_measurement.method': ['powder']
                },
                'indicator_fields': [
                    '_pd_',  # Prefix pattern - will match any field starting with _pd_
                    '_powder_',  # Prefix pattern - will match any field starting with _powder_
                    '_pd_meas_number_of_points',
                    '_pd_proc_ls_prof_R_factor'
                ],
                'keywords': ['powder', 'bragg-brentano', 'rietveld']
            },
            
            CrystallographyMethod.NEUTRON_DIFFRACTION: {
                'required_fields': ['_diffrn_radiation.probe', '_diffrn_radiation_probe'],  # Both CIF1 and CIF2
                'required_values': {
                    '_diffrn_radiation.probe': ['neutron'],
                    '_diffrn_radiation_probe': ['neutron'],
                    '_diffrn_radiation.type': ['neutron'],
                    '_diffrn_radiation_type': ['neutron']
                },
                'indicator_fields': [
                    '_diffrn_radiation_wavelength', '_diffrn_radiation.wavelength', 
                    '_diffrn_source.type', '_diffrn_source_type'
                ],
                'keywords': ['neutron', 'reactor', 'spallation']
            },
            
            CrystallographyMethod.SYNCHROTRON: {
                'indicator_fields': [
                    '_diffrn_radiation.type', '_diffrn_source.details',
                    '_diffrn_detector.details'
                ],
                'keywords': ['synchrotron', 'beamline', 'undulator', 'wiggler']
            },
            
            CrystallographyMethod.MAGNETIC_STRUCTURES: {
                'indicator_fields': [
                    '_atom_site_moment', '_magnetic_', '_atom_site_magnetic_',
                    '_space_group_magn'
                ],
                'keywords': ['magnetic', 'moment', 'spin', 'antiferromagnetic']
            },
            
            CrystallographyMethod.MODULATED_STRUCTURES: {
                'indicator_fields': [
                    '_cell_modulation_dimension', '_atom_site_displace_',
                    '_cell_wave_vector_', '_atom_site_occ_special_func'
                ],
                'keywords': ['modulated', 'incommensurate', 'superspace', 'satellite']
            },
            
            # CrystallographyMethod.TWINNED_STRUCTURES: {
            #     'indicator_fields': [
            #         '_twin_', '_refln_F_', '_reflns_twin_',
            #         '_twin_individual_id', '_twin_formation_mechanism'
            #     ],
            #     'keywords': ['twin', 'twinning', 'domain', 'hklf5']
            # }
        }
    
    def analyze_cif_file(self, cif_path: str) -> CIFAnalysisResult:
        """
        Perform comprehensive analysis of a CIF file
        
        Args:
            cif_path: Path to the CIF file
            
        Returns:
            CIFAnalysisResult with all analysis results
        """
        # Read file content
        try:
            with open(cif_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            raise ValueError(f"Could not read CIF file {cif_path}: {e}")
        
        # Extract present fields
        present_fields = self._extract_fields(content)
        
        # Detect CIF version
        cif_version, version_indicators = self._detect_cif_version(content, present_fields)
        
        # Detect crystallography methods
        detected_methods, method_indicators, confidence_scores = self._detect_methods(
            content, present_fields
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            cif_version, detected_methods, present_fields
        )
        
        # Combine format indicators
        format_indicators = {
            'cif_version': version_indicators,
            **method_indicators
        }
        
        return CIFAnalysisResult(
            file_path=cif_path,
            cif_version=cif_version,
            detected_methods=detected_methods,
            present_fields=present_fields,
            field_count=len(present_fields),
            format_indicators=format_indicators,
            confidence_scores=confidence_scores,
            recommendations=recommendations
        )
    
    def _extract_fields(self, content: str) -> Set[str]:
        """Extract all CIF field names from content"""
        fields = set()
        
        # Pattern for CIF fields - field names are terminated by whitespace
        # This captures everything after _ until whitespace (space, tab, newline)
        field_pattern = r'_([^\s]+)'
        matches = re.findall(field_pattern, content, re.MULTILINE)
        
        for match in matches:
            fields.add(f"_{match}")
        
        return fields
    
    def _detect_cif_version(self, content: str, fields: Set[str]) -> Tuple[CIFVersion, List[str]]:
        """
        Detect CIF version from content and field patterns
        
        Returns:
            Tuple of (CIFVersion, list of evidence)
        """
        evidence = []
        cif2_score = 0
        cif1_score = 0
        
        # Check for explicit version headers (highest priority)
        if re.search(r'#\\#CIF_2\.0', content):
            evidence.append("CIF2 header found")
            cif2_score += 20  # Much higher weight for explicit header
        elif re.search(r'#\\#CIF_1\.', content):
            evidence.append("CIF1 header found")
            cif1_score += 20
        elif re.search(r'##CIF_2\.0', content):
            # This is an incorrect format, but still indicates intention for CIF2
            evidence.append("Malformed CIF2 header found (should be #\\#CIF_2.0)")
            cif2_score += 5
        
        # Check field notation patterns (lower weight)
        dot_notation_count = len([f for f in fields if '.' in f.lstrip('_')])
        underscore_notation_count = len([f for f in fields if '.' not in f.lstrip('_') and '_' in f.lstrip('_')])
        
        if dot_notation_count > 0:
            evidence.append(f"Dot notation fields found ({dot_notation_count})")
            cif2_score += dot_notation_count * 0.5
        
        if underscore_notation_count > 0:
            evidence.append(f"Underscore notation fields found ({underscore_notation_count})")
            cif1_score += underscore_notation_count * 0.2
        
        # Check for CIF2-specific constructs
        if re.search(r'save_[a-zA-Z]', content):
            evidence.append("Save frames found")
            cif2_score += 5
        
        # Determine version based on scores
        if cif2_score > cif1_score:
            return CIFVersion.CIF2, evidence
        elif cif1_score > cif2_score:
            return CIFVersion.CIF1, evidence
        else:
            evidence.append("Mixed or unclear format indicators")
            return CIFVersion.UNKNOWN, evidence
    
    def _detect_methods(self, content: str, fields: Set[str]) -> Tuple[List[CrystallographyMethod], Dict[str, List[str]], Dict[str, float]]:
        """
        Detect crystallography methods from content and fields
        
        Returns:
            Tuple of (detected_methods, evidence_dict, confidence_scores)
        """
        detected_methods = []
        method_evidence = {}
        confidence_scores = {}
        
        content_lower = content.lower()
        
        # First, check for explicit radiation probe types to determine the primary method
        radiation_probe = self._extract_radiation_probe(content, fields)
        
        for method, indicators in self.method_indicators.items():
            evidence = []
            score = 0.0
            
            # Special handling for radiation-based methods (electron, neutron)
            if method in [CrystallographyMethod.ELECTRON_DIFFRACTION, CrystallographyMethod.NEUTRON_DIFFRACTION]:
                if 'required_values' in indicators:
                    # Check if radiation probe matches this method
                    probe_match = False
                    for field, values in indicators['required_values'].items():
                        if 'probe' in field.lower():
                            for value in values:
                                if radiation_probe and value.lower() == radiation_probe.lower():
                                    evidence.append(f"Radiation probe confirmed: {value}")
                                    score += 10.0  # High score for confirmed probe type
                                    probe_match = True
                                    break
                    
                    # If probe doesn't match, skip this method (avoid false positives)
                    if not probe_match and radiation_probe:
                        continue
                    
                    # If no probe detected but keywords suggest this method, be more cautious
                    if not radiation_probe:
                        # Check for specific keywords in content
                        if 'keywords' in indicators:
                            found_keywords = []
                            for keyword in indicators['keywords']:
                                if keyword.lower() in content_lower:
                                    found_keywords.append(keyword)
                                    score += 0.5
                            
                            if found_keywords:
                                evidence.append(f"Keywords found: {found_keywords}")
                        
                        # Require more evidence if no explicit probe is found
                        if score < 2.0:
                            continue
            else:
                # Standard detection for non-radiation methods
                # Check required fields
                if 'required_fields' in indicators:
                    for field in indicators['required_fields']:
                        if any(self._normalize_field(field) == self._normalize_field(f) for f in fields):
                            evidence.append(f"Required field found: {field}")
                            score += 2.0
                
                # Check required field values
                if 'required_values' in indicators:
                    for field, values in indicators['required_values'].items():
                        if any(self._normalize_field(field) == self._normalize_field(f) for f in fields):
                            # Look for the specific values in content
                            for value in values:
                                if value.lower() in content_lower:
                                    evidence.append(f"Required value found: {field} = {value}")
                                    score += 3.0
                
                # Check indicator fields
                if 'indicator_fields' in indicators:
                    found_indicators = []
                    for field_pattern in indicators['indicator_fields']:
                        # More precise matching - either exact match or prefix match for patterns ending with _
                        if field_pattern.endswith('_'):
                            # Prefix pattern like '_pd_' - match fields starting with this pattern
                            matching_fields = [f for f in fields if f.startswith(field_pattern)]
                        else:
                            # Exact field name - match exactly or normalized versions
                            matching_fields = [f for f in fields if f == field_pattern or 
                                             self._normalize_field(f) == self._normalize_field(field_pattern)]
                        
                        if matching_fields:
                            found_indicators.extend(matching_fields)
                            score += 1.0
                    
                    if found_indicators:
                        evidence.append(f"Indicator fields: {found_indicators[:3]}")
                
                # Check keywords in content
                if 'keywords' in indicators:
                    found_keywords = []
                    for keyword in indicators['keywords']:
                        if keyword.lower() in content_lower:
                            found_keywords.append(keyword)
                            score += 0.5
                    
                    if found_keywords:
                        evidence.append(f"Keywords found: {found_keywords}")
            
            # Determine if method is detected with stricter criteria
            confidence = min(score / 10.0, 1.0)  # Normalize to 0-1
            
            # For methods with required values, require higher confidence
            has_required_values = 'required_values' in indicators and indicators['required_values']
            required_threshold = 3.0 if has_required_values else 1.0
            
            if score > required_threshold:
                detected_methods.append(method)
                method_evidence[method.value] = evidence
                confidence_scores[method.value] = confidence
        
        return detected_methods, method_evidence, confidence_scores
    
    def _extract_radiation_probe(self, content: str, fields: Set[str]) -> Optional[str]:
        """Extract the radiation probe type from CIF content"""
        probe_fields = ['_diffrn_radiation.probe', '_diffrn_radiation_probe']
        
        for field in probe_fields:
            # Check if this field exists in the CIF
            field_pattern = field.replace('.', r'\.')
            # Look for the field followed by its value (handle quotes)
            match = re.search(rf'{field_pattern}\s+([\'"]?)([^\s\'"]+)\1', content, re.IGNORECASE)
            if match:
                return match.group(2).lower()
        
        return None
    
    def _normalize_field(self, field_name: str) -> str:
        """Normalize field name for comparison"""
        clean = field_name.lstrip('_').lower()
        # Convert between CIF1 and CIF2 formats for comparison
        if '.' not in clean and '_' in clean:
            parts = clean.split('_', 1)
            if len(parts) == 2:
                clean = f"{parts[0]}.{parts[1]}"
        return clean
    
    def _generate_recommendations(self, cif_version: CIFVersion, methods: List[CrystallographyMethod], 
                                fields: Set[str]) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []
        
        # CIF version recommendations
        if cif_version == CIFVersion.UNKNOWN:
            recommendations.append("⚠️  CIF format version unclear - consider adding explicit version header")
        elif cif_version == CIFVersion.CIF1:
            recommendations.append("📝 Consider migrating to CIF2 format for better compatibility")
        
        # Method-specific recommendations
        for method in methods:
            if method == CrystallographyMethod.ELECTRON_DIFFRACTION:
                if not any('_diffrn_radiation.probe' in f or '_diffrn_radiation_probe' in f for f in fields):
                    recommendations.append("🔬 Add _diffrn_radiation.probe = 'electron' for ED validation")
                
                if not any('_diffrn_detector.type' in f or '_diffrn_detector_type' in f for f in fields):
                    recommendations.append("📹 Consider adding detector type information for ED")
        
        # Field completeness recommendations
        essential_fields = ['_cell_length_a', '_cell_length_b', '_cell_length_c',
                          '_cell_angle_alpha', '_cell_angle_beta', '_cell_angle_gamma',
                          '_space_group_name_H-M_alt']
        
        missing_essential = []
        for field in essential_fields:
            if not any(self._normalize_field(field) == self._normalize_field(f) for f in fields):
                missing_essential.append(field)
        
        if missing_essential:
            recommendations.append(f"📊 Missing essential fields: {missing_essential[:3]}")
        
        return recommendations
    
    def get_method_requirements(self, method: CrystallographyMethod) -> Dict[str, List[str]]:
        """Get field requirements for a specific method"""
        if method in self.method_indicators:
            return {
                'required': self.method_indicators[method].get('required_fields', []),
                'recommended': self.method_indicators[method].get('indicator_fields', [])
            }
        return {'required': [], 'recommended': []}
    
    def is_field_valid(self, field_name: str) -> bool:
        """Check if a field is valid according to CIF dictionary"""
        return self.dict_manager.is_valid_field(field_name)


# Convenience functions
def analyze_cif(cif_path: str, analyzer: Optional[CIFAnalyzer] = None) -> CIFAnalysisResult:
    """Quick function to analyze a CIF file"""
    if analyzer is None:
        analyzer = CIFAnalyzer()
    return analyzer.analyze_cif_file(cif_path)


def detect_cif_version(cif_path: str) -> CIFVersion:
    """Quick function to detect CIF version only"""
    analyzer = CIFAnalyzer()
    result = analyzer.analyze_cif_file(cif_path)
    return result.cif_version


if __name__ == "__main__":
    # Test the CIF analyzer
    print("Testing CIF Analyzer...")
    
    # Create a test CIF content
    test_cif_content = """
#\\#CIF_2.0
data_test

_cell.length_a    10.0
_cell.length_b    10.0  
_cell.length_c    10.0
_cell.angle_alpha 90.0
_cell.angle_beta  90.0
_cell.angle_gamma 90.0

_diffrn_radiation.probe electron
_diffrn_detector.type   'CCD'
_exptl_crystal.preparation 'ion beam milling'

loop_
_atom_site.label
_atom_site.fract_x
_atom_site.fract_y
_atom_site.fract_z
C1 0.0 0.0 0.0
O1 0.5 0.5 0.5
"""
    
    # Save test content
    test_file = "test_cif_analysis.cif"
    with open(test_file, 'w') as f:
        f.write(test_cif_content)
    
    try:
        # Analyze the test file
        analyzer = CIFAnalyzer()
        result = analyzer.analyze_cif_file(test_file)
        
        print(f"\n📁 File: {result.file_path}")
        print(f"📝 CIF Version: {result.cif_version.value}")
        print(f"🔬 Detected Methods: {[m.value for m in result.detected_methods]}")
        print(f"📊 Field Count: {result.field_count}")
        
        print(f"\n🔍 Format Evidence:")
        for category, evidence in result.format_indicators.items():
            if evidence:
                print(f"  {category}: {evidence}")
        
        print(f"\n📈 Confidence Scores:")
        for method, score in result.confidence_scores.items():
            print(f"  {method}: {score:.2f}")
        
        print(f"\n💡 Recommendations:")
        for rec in result.recommendations:
            print(f"  {rec}")
        
    finally:
        # Clean up test file
        if os.path.exists(test_file):
            os.remove(test_file)
