"""
3D Electron Diffraction (3D ED) Validator
Specialized validation system for 3D ED CIF files

This module provides specialized validation for 3D electron diffraction experiments,
ensuring compliance with the latest CIF core dictionary standards.
"""

import json
import math
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from enum import Enum

# Import for CIF version detection
try:
    from .cif_analyzer import CIFVersion
except ImportError:
    # Fallback for when running as script
    import sys
    sys.path.append('..')
    from cif_analyzer import CIFVersion

class ValidationLevel(Enum):
    ESSENTIAL = "essential"
    HIGHLY_RECOMMENDED = "highly_recommended" 
    METHOD_SPECIFIC = "method_specific"

class ValidationResult:
    def __init__(self, field: str, status: str, message: str, level: ValidationLevel):
        self.field = field
        self.status = status  # 'pass', 'fail', 'warning', 'missing'
        self.message = message
        self.level = level

class ED3DValidator:
    """3D Electron Diffraction CIF validator with CIF version support"""
    
    def __init__(self):
        self.config = self._load_config()
        self.validation_results = []
        
        # Field mappings between CIF1 and CIF2 for ED-specific fields
        self.cif1_to_cif2_fields = {
            # Radiation fields
            '_diffrn_radiation_probe': '_diffrn_radiation.probe',
            '_diffrn_radiation_wavelength': '_diffrn_radiation.wavelength',
            '_diffrn_radiation_type': '_diffrn_radiation.type',
            
            # Source fields
            '_diffrn_source_voltage': '_diffrn_source.voltage',
            '_diffrn_source_current': '_diffrn_source.current',
            '_diffrn_source_size': '_diffrn_source.size',
            '_diffrn_source_type': '_diffrn_source.type',
            
            # Detector fields
            '_diffrn_detector_type': '_diffrn_detector.type',
            '_diffrn_detector_area_resol_mean': '_diffrn_detector.area_resol_mean',
            
            # Measurement fields
            '_diffrn_measurement_device_type': '_diffrn_measurement.device_type',
            '_diffrn_measurement_device_details': '_diffrn_measurement.device_details',
            
            # Ambient conditions
            '_diffrn_ambient_temperature': '_diffrn.ambient_temperature',
            '_diffrn_ambient_pressure': '_diffrn.ambient_pressure',
        }
        
        # Reverse mapping
        self.cif2_to_cif1_fields = {v: k for k, v in self.cif1_to_cif2_fields.items()}
        
    def _load_config(self) -> Dict:
        """Load 3D ED validation configuration"""
        config_path = Path(__file__).parent.parent / "gui" / "field_definitions_3d_ed.json"
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Fallback minimal config
            return {
                "required_fields": {
                    "essential": [
                        "_diffrn_radiation.probe",
                        "_diffrn_radiation.wavelength", 
                        "_diffrn_source.voltage",
                        "_diffrn_detector.type"
                    ]
                },
                "field_validation": {
                    "_diffrn_radiation.probe": {"required_value": "electron"}
                }
            }
    
    def validate_cif_content(self, cif_content: str, cif_version: Optional[CIFVersion] = None) -> Dict[str, Any]:
        """
        Main validation function for 3D ED CIF files with CIF version support
        
        Args:
            cif_content: The CIF file content as string
            cif_version: Detected CIF version (CIF1, CIF2, or None for auto-detect)
            
        Returns:
            Comprehensive validation report
        """
        self.validation_results = []
        
        # Auto-detect CIF version if not provided
        if cif_version is None:
            cif_version = self._detect_cif_version(cif_content)
        
        # Extract fields from CIF content
        fields = self._extract_fields(cif_content)
        
        # Check if this is actually a 3D ED experiment (version-aware)
        is_3d_ed = self._detect_3d_ed_method(fields, cif_version)
        
        if not is_3d_ed:
            return {
                "method_detected": "Unknown/Not 3D ED",
                "validation_status": "not_applicable",
                "message": f"This does not appear to be a 3D electron diffraction experiment (checked for {cif_version.value if cif_version else 'unknown'} format)"
            }
        
        # Perform comprehensive validation with version awareness
        self._validate_essential_fields(fields, cif_version)
        self._validate_field_values(fields, cif_version)
        self._validate_consistency_rules(fields, cif_version)
        
        # Generate validation report
        return self._generate_validation_report(fields)
    
    def _extract_fields(self, cif_content: str) -> Dict[str, str]:
        """Extract all CIF fields and their values"""
        fields = {}
        
        # Enhanced pattern to capture all CIF field formats
        field_pattern = r'^\s*(_[^\s]+)\s+(.+?)(?=\s*$|\s*#)'
        
        for line in cif_content.split('\n'):
            line = line.strip()
            if line.startswith('_'):
                match = re.match(field_pattern, line)
                if match:
                    field_name = match.group(1)
                    field_value = match.group(2).strip().strip("'\"")
                    fields[field_name] = field_value
        
        return fields
    
    def _detect_cif_version(self, cif_content: str) -> CIFVersion:
        """Simple CIF version detection"""
        if '#\\#CIF_2.0' in cif_content:
            return CIFVersion.CIF2
        elif '#\\#CIF_1' in cif_content or any(field.count('.') == 0 for field in re.findall(r'_\w+(?:\.\w+)*', cif_content)):
            return CIFVersion.CIF1
        else:
            # Default to CIF1 if uncertain
            return CIFVersion.CIF1
    
    def _get_version_appropriate_field(self, field_name: str, cif_version: CIFVersion) -> str:
        """Convert field name to version-appropriate format"""
        if cif_version == CIFVersion.CIF1:
            # Convert CIF2 to CIF1 if needed
            return self.cif2_to_cif1_fields.get(field_name, field_name)
        elif cif_version == CIFVersion.CIF2:
            # Convert CIF1 to CIF2 if needed
            return self.cif1_to_cif2_fields.get(field_name, field_name)
        else:
            return field_name
    
    def _check_field_exists(self, fields: Dict[str, str], field_name: str, cif_version: CIFVersion) -> Tuple[bool, str]:
        """Check if a field exists in version-appropriate format"""
        # Check exact match first
        if field_name in fields:
            return True, field_name
        
        # Check version-appropriate format
        version_field = self._get_version_appropriate_field(field_name, cif_version)
        if version_field in fields:
            return True, version_field
        
        # Check the opposite version format as fallback
        if cif_version == CIFVersion.CIF1:
            alt_field = self.cif1_to_cif2_fields.get(field_name, field_name)
        else:
            alt_field = self.cif2_to_cif1_fields.get(field_name, field_name)
        
        if alt_field in fields:
            return True, alt_field
        
        return False, field_name

    def _detect_3d_ed_method(self, fields: Dict[str, str], cif_version: CIFVersion) -> bool:
        """
        Detect if this is a 3D ED experiment with version awareness
        """
        # Primary detection: radiation probe (check both CIF1 and CIF2 formats)
        probe_fields = ['_diffrn_radiation.probe', '_diffrn_radiation_probe']
        for probe_field in probe_fields:
            exists, actual_field = self._check_field_exists(fields, probe_field, cif_version)
            if exists:
                probe_value = fields.get(actual_field, '').lower()
                if 'electron' in probe_value:
                    return True
        
        # Check radiation type as well
        type_fields = ['_diffrn_radiation.type', '_diffrn_radiation_type']
        for type_field in type_fields:
            exists, actual_field = self._check_field_exists(fields, type_field, cif_version)
            if exists:
                type_value = fields.get(actual_field, '').lower()
                if 'electron' in type_value:
                    return True
            
        # Secondary detection: voltage field (specific to electron diffraction)
        voltage_fields = ['_diffrn_source.voltage', '_diffrn_source_voltage']
        for voltage_field in voltage_fields:
            exists, actual_field = self._check_field_exists(fields, voltage_field, cif_version)
            if exists:
                try:
                    voltage = float(fields[actual_field])
                    if 80 <= voltage <= 300:  # Typical electron microscope range
                        return True
                except ValueError:
                    pass
        
        # Tertiary detection: keywords in detector/source descriptions
        ed_keywords = ['electron', 'tem', 'precession', 'microed', '3d ed', 'cred']
        for field_value in fields.values():
            if any(keyword in field_value.lower() for keyword in ed_keywords):
                return True
                
        return False
    
    def _validate_essential_fields(self, fields: Dict[str, str], cif_version: CIFVersion):
        """Validate essential fields for 3D ED with version awareness"""
        essential_fields = self.config.get("required_fields", {}).get("essential", [])
        
        for field in essential_fields:
            exists, actual_field = self._check_field_exists(fields, field, cif_version)
            if exists:
                value = fields[actual_field].strip()
                if value and value not in ['?', '.']:
                    version_note = f" (found as {actual_field})" if actual_field != field else ""
                    self.validation_results.append(
                        ValidationResult(field, "pass", f"Present: {value}{version_note}", ValidationLevel.ESSENTIAL)
                    )
                else:
                    self.validation_results.append(
                        ValidationResult(field, "fail", f"Field present but empty (found as {actual_field})", ValidationLevel.ESSENTIAL)
                    )
            else:
                self.validation_results.append(
                    ValidationResult(field, "missing", "Essential field missing", ValidationLevel.ESSENTIAL)
                )
    
    def _validate_field_values(self, fields: Dict[str, str], cif_version: CIFVersion):
        """Validate specific field values according to 3D ED standards"""
        validations = self.config.get("field_validation", {})
        
        for field, rules in validations.items():
            if field not in fields:
                continue
                
            value = fields[field]
            
            # Check required values
            if "required_value" in rules:
                expected = rules["required_value"].lower()
                actual = value.lower()
                if expected in actual:
                    self.validation_results.append(
                        ValidationResult(field, "pass", f"Correct value: {value}", ValidationLevel.ESSENTIAL)
                    )
                else:
                    self.validation_results.append(
                        ValidationResult(field, "fail", f"Expected '{expected}', found '{value}'", ValidationLevel.ESSENTIAL)
                    )
            
            # Check numeric ranges
            if "typical_range" in rules and "type" in rules and rules["type"] == "numeric":
                try:
                    numeric_value = float(value)
                    min_val, max_val = rules["typical_range"]
                    if min_val <= numeric_value <= max_val:
                        self.validation_results.append(
                            ValidationResult(field, "pass", f"Value in typical range: {value}", ValidationLevel.HIGHLY_RECOMMENDED)
                        )
                    else:
                        self.validation_results.append(
                            ValidationResult(field, "warning", f"Value {value} outside typical range [{min_val}, {max_val}]", ValidationLevel.HIGHLY_RECOMMENDED)
                        )
                except ValueError:
                    self.validation_results.append(
                        ValidationResult(field, "fail", f"Expected numeric value, found '{value}'", ValidationLevel.ESSENTIAL)
                    )
    
    def _validate_consistency_rules(self, fields: Dict[str, str], cif_version: CIFVersion):
        """Validate consistency rules specific to 3D ED"""
        
        # Rule 1: Voltage-wavelength consistency (relativistic calculation)
        if "_diffrn_source.voltage" in fields and "_diffrn_radiation.wavelength" in fields:
            try:
                voltage = float(fields["_diffrn_source.voltage"]) * 1000  # Convert kV to V
                wavelength = float(fields["_diffrn_radiation.wavelength"])
                
                # Relativistic calculation for electron wavelength
                # Correct relativistic formula: λ = h / p
                # where p = √[(E_kinetic + mc²)² - (mc²)²] / c
                # Constants (CODATA 2018 values):
                h = 6.62607015e-34  # Planck constant (J·s)
                m = 9.1093837015e-31  # Electron rest mass (kg)
                e = 1.602176634e-19  # Elementary charge (C)
                c = 299792458  # Speed of light (m/s)
                
                # Energies
                kinetic_energy = e * voltage  # Kinetic energy in Joules
                rest_energy = m * c**2  # Rest mass energy
                total_energy = kinetic_energy + rest_energy
                
                # Relativistic momentum: p = √(E_total² - E_rest²) / c
                momentum = math.sqrt(total_energy**2 - rest_energy**2) / c
                
                # de Broglie wavelength
                expected_wavelength = h / momentum * 1e10  # Convert m to Å
                
                # Allow 2% tolerance (tighter than before due to better calculation)
                tolerance = 0.02
                if abs(wavelength - expected_wavelength) / expected_wavelength <= tolerance:
                    self.validation_results.append(
                        ValidationResult("voltage_wavelength", "pass", 
                                       f"Wavelength {wavelength}Å consistent with {voltage/1000}kV (relativistic calc.)", 
                                       ValidationLevel.ESSENTIAL)
                    )
                else:
                    self.validation_results.append(
                        ValidationResult("voltage_wavelength", "warning", 
                                       f"Wavelength {wavelength}Å inconsistent with {voltage/1000}kV (expected {expected_wavelength:.4f}Å, relativistic)", 
                                       ValidationLevel.ESSENTIAL)
                    )
            except (ValueError, ZeroDivisionError):
                pass
        
        # Rule 2: Crystal size ordering
        size_fields = ["_exptl_crystal.size_max", "_exptl_crystal.size_mid", "_exptl_crystal.size_min"]
        sizes = []
        
        for field in size_fields:
            if field in fields:
                try:
                    size = float(fields[field])
                    sizes.append((field, size))
                except ValueError:
                    pass
        
        if len(sizes) >= 2:
            sizes.sort(key=lambda x: x[1], reverse=True)
            original_order = [fields.get(field, 0) for field in size_fields if field in fields]
            expected_order = [str(size[1]) for size in sizes]
            
            if original_order == expected_order:
                self.validation_results.append(
                    ValidationResult("crystal_sizes", "pass", "Crystal sizes properly ordered", ValidationLevel.HIGHLY_RECOMMENDED)
                )
            else:
                self.validation_results.append(
                    ValidationResult("crystal_sizes", "warning", "Crystal sizes may not be properly ordered (max ≥ mid ≥ min)", ValidationLevel.HIGHLY_RECOMMENDED)
                )
    
    def _generate_validation_report(self, fields: Dict[str, str]) -> Dict[str, Any]:
        """Generate comprehensive validation report"""
        
        # Count results by status
        status_counts = {"pass": 0, "fail": 0, "warning": 0, "missing": 0}
        for result in self.validation_results:
            status_counts[result.status] += 1
        
        # Determine overall status
        if status_counts["fail"] > 0 or status_counts["missing"] > 0:
            overall_status = "issues_found"
        elif status_counts["warning"] > 0:
            overall_status = "warnings"
        else:
            overall_status = "excellent"
        
        # Generate detailed results
        detailed_results = []
        for result in self.validation_results:
            detailed_results.append({
                "field": result.field,
                "status": result.status,
                "message": result.message,
                "level": result.level.value
            })
        
        # Generate validation summary
        validation_summary = self._generate_validation_summary(status_counts, fields)
        
        return {
            "method_detected": "3D Electron Diffraction",
            "validation_status": overall_status,
            "summary": {
                "total_checks": len(self.validation_results),
                "passed": status_counts["pass"],
                "failed": status_counts["fail"], 
                "warnings": status_counts["warning"],
                "missing": status_counts["missing"]
            },
            "detailed_results": detailed_results,
            "validation_summary": validation_summary,
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_validation_summary(self, status_counts: Dict, fields: Dict[str, str]) -> str:
        """Generate a summary of validation results"""
        
        if status_counts["fail"] == 0 and status_counts["missing"] == 0:
            return "✅ VALIDATION PASSED: This 3D ED CIF meets all essential validation criteria and follows current best practices."
        
        issues = []
        if status_counts["missing"] > 0:
            issues.append(f"{status_counts['missing']} essential fields missing")
        if status_counts["fail"] > 0:
            issues.append(f"{status_counts['fail']} validation failures")
        if status_counts["warning"] > 0:
            issues.append(f"{status_counts['warning']} recommendations for improvement")
            
        return f"⚠️ NEEDS ATTENTION: {', '.join(issues)}. Please address these issues before publication."
    
    def _generate_recommendations(self) -> List[str]:
        """Generate actionable recommendations for improvement"""
        recommendations = []
        
        missing_essential = [r for r in self.validation_results if r.status == "missing" and r.level == ValidationLevel.ESSENTIAL]
        if missing_essential:
            recommendations.append(f"Add the following essential fields: {', '.join([r.field for r in missing_essential])}")
        
        failed_validations = [r for r in self.validation_results if r.status == "fail"]
        if failed_validations:
            recommendations.append("Review and correct the failed field validations listed above")
        
        warnings = [r for r in self.validation_results if r.status == "warning"]
        if warnings:
            recommendations.append("Consider addressing the warnings to improve data quality")
            
        if not recommendations:
            recommendations.append("Excellent! This CIF is ready for publication.")
            
        return recommendations
