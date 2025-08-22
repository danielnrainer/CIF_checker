"""
CIF Format Converter
Handles conversion between CIF 1.0 and CIF 2.0 formats using cif_core.dic.
"""

from typing import Dict, List, Tuple, Set, Optional
from enum import Enum
import re
from .cif_analyzer import CIFVersion

# Import the dictionary manager
try:
    from .cif_dictionary_manager import CIFDictionaryManager
except ImportError:
    # Fallback for when running as script
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from cif_dictionary_manager import CIFDictionaryManager


class CIFConverter:
    """Converts between CIF 1.0 and CIF 2.0 formats using cif_core.dic"""
    
    def __init__(self, dict_manager: Optional[CIFDictionaryManager] = None):
        self.dict_manager = dict_manager or CIFDictionaryManager()
        
        # Get all available fields from the dictionary
        self.all_fields = self.dict_manager.get_all_field_names()
        
        # Build comprehensive field mappings from the dictionary
        self.cif1_to_cif2_mappings = self._build_cif1_to_cif2_mappings()
        self.cif2_to_cif1_mappings = self._build_cif2_to_cif1_mappings()
        
        # Fields that are only valid in specific versions (based on dictionary analysis)
        self.cif1_only_fields = self._identify_cif1_only_fields()
        self.cif2_only_fields = self._identify_cif2_only_fields()

    def _build_cif1_to_cif2_mappings(self) -> Dict[str, str]:
        """Build CIF1 to CIF2 field mappings from the dictionary using alias information"""
        mappings = {}
        
        # Get alias mappings from the dictionary manager
        # This provides alias_name -> definition_id mappings from the CIF dictionary
        alias_mappings = self.dict_manager.get_alias_mappings()
        
        # Convert alias mappings to proper CIF1 -> CIF2 mappings
        # The aliases are the CIF1 forms, definition_ids are the CIF2 forms
        for alias, definition_id in alias_mappings.items():
            # Both alias and definition_id should start with '_'
            if alias.startswith('_') and definition_id.startswith('_'):
                mappings[alias] = definition_id
        
        # Add some manual mappings for special cases that aren't handled by aliases
        # or need specific handling that differs from the dictionary structure
        manual_mappings = {
            # Space group special cases (avoid conflicts with auto-generated mappings)
            '_symmetry_space_group_name_H-M': '_space_group.name_H-M_full',
            '_symmetry_cell_setting': '_space_group.crystal_system',
            
            # Legacy symmetry fields (these are deprecated in CIF2 but still commonly used)
            '_symmetry_equiv_pos_as_xyz': '_space_group_symop.operation_xyz',
            '_symmetry_equiv_pos_site_id': '_space_group_symop.id',
            
            # Additional common fields with non-obvious mappings
            '_symmetry_Int_Tables_number': '_space_group.IT_number',
        }
        
        # Only add manual mappings if the CIF2 field exists in dictionary
        for cif1_field, cif2_field in manual_mappings.items():
            # Remove underscore from cif2_field to check against dictionary
            cif2_field_no_underscore = cif2_field[1:] if cif2_field.startswith('_') else cif2_field
            if cif2_field_no_underscore in self.all_fields:
                mappings[cif1_field] = cif2_field
        
        return mappings

    def _build_cif2_to_cif1_mappings(self) -> Dict[str, str]:
        """Build CIF2 to CIF1 field mappings (reverse of CIF1->CIF2)"""
        return {v: k for k, v in self.cif1_to_cif2_mappings.items()}
    
    def _identify_cif1_only_fields(self) -> Set[str]:
        """Identify fields that only exist in CIF1 format"""
        # Since the dictionary is CIF2-based, we identify CIF1-only fields
        # as those that are commonly used in CIF1 but don't have direct CIF2 equivalents
        cif1_only = {
            '_symmetry_equiv_pos_as_xyz',
            '_symmetry_equiv_pos_site_id', 
            '_atom_sites_solution_hydrogens',
            '_atom_sites_solution_primary',
            '_atom_sites_solution_secondary',
            '_chemical_formula_analytical',  # Sometimes used in CIF1
            '_chemical_formula_structural',  # Sometimes used in CIF1
        }
        
        # Filter to only include fields that don't have CIF2 mappings
        return {field for field in cif1_only if field not in self.cif1_to_cif2_mappings}

    def _identify_cif2_only_fields(self) -> Set[str]:
        """Identify fields that only exist in CIF2 format"""
        # Fields that are clearly CIF2-only (have dots and no CIF1 equivalent would make sense)
        cif2_only = set()
        
        for field in self.all_fields:
            if '.' in field:
                # Check if this field has complex dot patterns that wouldn't exist in CIF1
                if field.count('.') > 1 or any(x in field for x in ['_su', '_esd', '_ls_', '_details']):
                    cif2_only.add(field)
        
        return cif2_only

    def _fields_are_related(self, field1: str, field2: str) -> bool:
        """Check if two fields are likely related (same base concept)"""
        # Simple heuristic: remove dots/underscores and compare
        normalized1 = field1.replace('_', '').replace('.', '').lower()
        normalized2 = field2.replace('_', '').replace('.', '').lower()
        
        # Check if one is a substring of the other (allowing for some difference)
        return (normalized1 in normalized2 or normalized2 in normalized1 or
                abs(len(normalized1) - len(normalized2)) <= 3)

    def convert_to_cif2(self, content: str) -> Tuple[str, List[str]]:
        """
        Convert CIF 1.0 content to CIF 2.0 format using dictionary-based mapping
        
        Args:
            content: CIF file content as string
            
        Returns:
            Tuple of (converted_content, list_of_changes)
        """
        changes = []
        lines = content.split('\n')
        converted_lines = []
        
        # Extract all fields present in the content
        present_fields = self._extract_fields_from_content(content)
        
        for line in lines:
            original_line = line
            line_changed = False
            
            # Check each present field for conversion opportunities
            for field in present_fields:
                if line.strip().startswith(field) and field in self.cif1_to_cif2_mappings:
                    cif2_field = self.cif1_to_cif2_mappings[field]
                    # Replace the field name
                    line = line.replace(field, cif2_field, 1)
                    changes.append(f"Converted field: {field} → {cif2_field}")
                    line_changed = True
                    break
            
            # Handle specific CIF1 patterns that need updating
            if not line_changed:
                line = self._update_cif1_patterns(line, changes)
            
            converted_lines.append(line)
        
        # Add CIF2 header if not present
        converted_content = '\n'.join(converted_lines)
        if '#\\#CIF_2.0' not in converted_content:
            converted_content = '#\\#CIF_2.0\n' + converted_content
            changes.append("Added CIF 2.0 header")
        
        # Add format explanation if fields were converted
        field_changes = [c for c in changes if 'Converted field:' in c]
        if field_changes:
            changes.append(f"Note: CIF 2.0 uses dot notation (e.g., '_cell.length_a') instead of underscores (e.g., '_cell_length_a')")
        
        return converted_content, changes

    def convert_to_cif1(self, content: str) -> Tuple[str, List[str]]:
        """
        Convert CIF 2.0 content to CIF 1.0 format using dictionary-based mapping
        
        Args:
            content: CIF file content as string
            
        Returns:
            Tuple of (converted_content, list_of_changes)
        """
        changes = []
        lines = content.split('\n')
        converted_lines = []
        
        # Extract all fields present in the content
        present_fields = self._extract_fields_from_content(content)
        
        for line in lines:
            original_line = line
            line_changed = False
            
            # Remove CIF2 header
            if line.strip() == '#\\#CIF_2.0':
                changes.append("Removed CIF 2.0 header")
                continue
            
            # Check each present field for conversion opportunities
            for field in present_fields:
                if line.strip().startswith(field) and field in self.cif2_to_cif1_mappings:
                    cif1_field = self.cif2_to_cif1_mappings[field]
                    # Replace the field name
                    line = line.replace(field, cif1_field, 1)
                    changes.append(f"Converted field: {field} → {cif1_field}")
                    line_changed = True
                    break
            
            # Handle specific CIF2 patterns that need updating
            if not line_changed:
                line = self._update_cif2_patterns(line, changes)
            
            converted_lines.append(line)
        
        converted_content = '\n'.join(converted_lines)
        
        # Add format explanation if fields were converted
        field_changes = [c for c in changes if 'Converted field:' in c]
        if field_changes:
            changes.append(f"Note: CIF 1.0 uses underscore notation (e.g., '_cell_length_a') instead of dots (e.g., '_cell.length_a')")
        
        return converted_content, changes

    def _extract_fields_from_content(self, content: str) -> Set[str]:
        """Extract all CIF field names from content"""
        fields = set()
        
        for line in content.split('\n'):
            line = line.strip()
            # Handle both CIF1 format (_field_name) and CIF2 format (category.field_name)
            if line.startswith('_'):
                # CIF1 format: _field_name
                match = re.match(r'^\s*(_[^\s]+)', line)
                if match:
                    field_name = match.group(1)
                    fields.add(field_name)
            elif '.' in line and not line.startswith('#') and not line.startswith('data_'):
                # CIF2 format: category.field_name
                match = re.match(r'^\s*([a-zA-Z][a-zA-Z0-9_]*\.[a-zA-Z0-9_]+)', line)
                if match:
                    field_name = match.group(1)
                    fields.add(field_name)
        
        return fields

    def _update_cif1_patterns(self, line: str, changes: List[str]) -> str:
        """Update CIF1-specific patterns for CIF2 compatibility"""
        
        # Convert symmetry operations format
        if line.strip().startswith('_symmetry_equiv_pos_as_xyz'):
            # This will need manual review as the format is quite different
            changes.append("Note: Symmetry operations may need manual review for CIF2 format")
        
        return line

    def _update_cif2_patterns(self, line: str, changes: List[str]) -> str:
        """Update CIF2-specific patterns for CIF1 compatibility"""
        
        # Convert space group operations format  
        if line.strip().startswith('_space_group_symop.operation_xyz'):
            # Convert to CIF1 format
            line = line.replace('_space_group_symop.operation_xyz', '_symmetry_equiv_pos_as_xyz', 1)
            changes.append("Converted space group operations to CIF1 format")
        
        return line

    def get_version_specific_fields(self, target_version: CIFVersion) -> Dict[str, List[str]]:
        """
        Get fields that are specific to a CIF version
        
        Args:
            target_version: Target CIF version
            
        Returns:
            Dictionary with 'required', 'recommended', and 'incompatible' field lists
        """
        if target_version == CIFVersion.CIF1:
            return {
                'required': ['_chemical_formula_sum', '_cell_length_a', '_cell_length_b', '_cell_length_c'],
                'recommended': list(self.cif1_to_cif2_mappings.keys()),
                'incompatible': list(self.cif2_only_fields)
            }
        elif target_version == CIFVersion.CIF2:
            return {
                'required': ['_chemical_formula.sum', '_cell.length_a', '_cell.length_b', '_cell.length_c'],
                'recommended': list(self.cif2_to_cif1_mappings.keys()),
                'incompatible': list(self.cif1_only_fields)
            }
        else:
            return {'required': [], 'recommended': [], 'incompatible': []}

    def suggest_missing_fields(self, content: str, target_version: CIFVersion) -> List[str]:
        """
        Suggest fields that should be added for the target CIF version
        
        Args:
            content: Current CIF content
            target_version: Target CIF version
            
        Returns:
            List of suggested field additions
        """
        suggestions = []
        version_fields = self.get_version_specific_fields(target_version)
        
        # Check for required fields
        for field in version_fields['required']:
            if field not in content:
                suggestions.append(f"Required field missing: {field}")
        
        # Check for recommended fields based on what's present
        for field in version_fields['recommended']:
            if field not in content:
                # Check if there's data that would benefit from this field
                if self._should_suggest_field(content, field, target_version):
                    suggestions.append(f"Recommended field: {field}")
        
        return suggestions

    def _should_suggest_field(self, content: str, field: str, target_version: CIFVersion) -> bool:
        """Determine if a field should be suggested based on content analysis"""
        
        # Basic heuristics for field suggestions
        if 'temperature' in field.lower() and ('temp' in content.lower() or 'k' in content.lower()):
            return True
        if 'wavelength' in field.lower() and ('diffr' in content.lower() or 'radiation' in content.lower()):
            return True
        if 'space_group' in field.lower() and ('space' in content.lower() or 'symmetry' in content.lower()):
            return True
            
        return False
