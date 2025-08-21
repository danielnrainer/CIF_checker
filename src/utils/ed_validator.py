"""
3D Electron Diffraction (3D ED) Validator
Conference-ready validation system for 3D ED CIF files

This module provides specialized validation for 3D electron diffraction experiments,
ensuring compliance with the latest CIF core dictionary standards for conference presentation.
"""

import json
import math
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from enum import Enum

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
    """Conference-ready 3D Electron Diffraction CIF validator"""
    
    def __init__(self):
        self.config = self._load_config()
        self.validation_results = []
        
    def _load_config(self) -> Dict:
        """Load 3D ED validation configuration"""
        config_path = Path(__file__).parent.parent / "gui" / "field_definitions_3d_ed.json"
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Fallback minimal config for conference demo
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
    
    def validate_cif_content(self, cif_content: str) -> Dict[str, Any]:
        """
        Main validation function for conference demo
        Returns comprehensive validation report for 3D ED
        """
        self.validation_results = []
        
        # Extract fields from CIF content
        fields = self._extract_fields(cif_content)
        
        # Check if this is actually a 3D ED experiment
        is_3d_ed = self._detect_3d_ed_method(fields)
        
        if not is_3d_ed:
            return {
                "method_detected": "Unknown/Not 3D ED",
                "validation_status": "not_applicable",
                "message": "This does not appear to be a 3D electron diffraction experiment"
            }
        
        # Perform comprehensive validation
        self._validate_essential_fields(fields)
        self._validate_field_values(fields)
        self._validate_consistency_rules(fields)
        
        # Generate conference-ready report
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
    
    def _detect_3d_ed_method(self, fields: Dict[str, str]) -> bool:
        """
        Detect if this is a 3D ED experiment - critical for conference demo
        """
        # Primary detection: radiation probe
        probe_field = fields.get('_diffrn_radiation.probe', '').lower()
        if 'electron' in probe_field:
            return True
            
        # Secondary detection: voltage field (specific to electron diffraction)
        if '_diffrn_source.voltage' in fields:
            try:
                voltage = float(fields['_diffrn_source.voltage'])
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
    
    def _validate_essential_fields(self, fields: Dict[str, str]):
        """Validate essential fields for conference presentation"""
        essential_fields = self.config.get("required_fields", {}).get("essential", [])
        
        for field in essential_fields:
            if field in fields:
                value = fields[field].strip()
                if value and value not in ['?', '.']:
                    self.validation_results.append(
                        ValidationResult(field, "pass", f"Present: {value}", ValidationLevel.ESSENTIAL)
                    )
                else:
                    self.validation_results.append(
                        ValidationResult(field, "fail", "Field present but empty", ValidationLevel.ESSENTIAL)
                    )
            else:
                self.validation_results.append(
                    ValidationResult(field, "missing", "Essential field missing", ValidationLevel.ESSENTIAL)
                )
    
    def _validate_field_values(self, fields: Dict[str, str]):
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
    
    def _validate_consistency_rules(self, fields: Dict[str, str]):
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
        """Generate comprehensive validation report for conference presentation"""
        
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
        
        # Conference-specific summary
        conference_summary = self._generate_conference_summary(status_counts, fields)
        
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
            "conference_summary": conference_summary,
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_conference_summary(self, status_counts: Dict, fields: Dict[str, str]) -> str:
        """Generate a summary suitable for conference presentation"""
        
        if status_counts["fail"] == 0 and status_counts["missing"] == 0:
            return "✅ CONFERENCE READY: This 3D ED CIF meets all essential validation criteria and follows current best practices."
        
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
            recommendations.append("Excellent! This CIF is ready for publication and conference presentation.")
            
        return recommendations
