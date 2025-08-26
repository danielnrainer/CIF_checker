"""
Field Equivalence Manager
Handles CIF field equivalence checking across CIF1/CIF2 formats and dictionary aliases.
Prevents duplicate equivalent fields and ensures format consistency.
"""

from typing import Set, Optional, Dict, List, Tuple

# Try relative imports first, fall back to absolute for testing
try:
    from .cif_dictionary_manager import CIFDictionaryManager
    from .cif_converter import CIFConverter
    from .cif_analyzer import CIFAnalyzer, CIFVersion
except ImportError:
    # Fallback for standalone testing
    from cif_dictionary_manager import CIFDictionaryManager
    from cif_converter import CIFConverter
    from cif_analyzer import CIFAnalyzer, CIFVersion


class FieldEquivalenceManager:
    """
    Manages field equivalence checking to prevent duplicate fields
    and ensure format consistency across CIF1/CIF2 and aliases.
    """
    
    def __init__(self, dict_manager: Optional[CIFDictionaryManager] = None):
        """Initialize the field equivalence manager"""
        self.dict_manager = dict_manager or CIFDictionaryManager()
        self.converter = CIFConverter(dict_manager)
        self.analyzer = CIFAnalyzer(dict_manager)
        
        # Build comprehensive equivalence mappings
        self.alias_mappings = self.dict_manager.get_alias_mappings()
        self.reverse_alias_mappings = {v: k for k, v in self.alias_mappings.items()}
        
        # CIF format mappings
        self.cif1_to_cif2 = self.converter.cif1_to_cif2_mappings
        self.cif2_to_cif1 = self.converter.cif2_to_cif1_mappings
        
        # Build comprehensive field equivalence groups
        self.equivalence_groups = self._build_equivalence_groups()
    
    def _build_equivalence_groups(self) -> Dict[str, Set[str]]:
        """
        Build groups of equivalent fields (aliases, CIF1/CIF2 variants)
        
        Returns:
            Dictionary mapping canonical field names to sets of equivalent fields
        """
        groups = {}
        processed_fields = set()
        
        # Get all known fields from dictionary
        all_fields = self.dict_manager.get_all_field_names()
        
        for field in all_fields:
            if field in processed_fields:
                continue
                
            # Build equivalence group for this field
            equivalent_fields = self._find_all_equivalents(field)
            
            # Use the canonical field (usually the definition_id) as the group key
            canonical_field = self._get_canonical_field(equivalent_fields)
            groups[canonical_field] = equivalent_fields
            
            # Mark all fields in this group as processed
            processed_fields.update(equivalent_fields)
        
        return groups
    
    def _find_all_equivalents(self, field: str) -> Set[str]:
        """Find all equivalent forms of a field"""
        equivalents = {field}
        
        # Add aliases (both directions)
        if field in self.alias_mappings:
            equivalents.add(self.alias_mappings[field])
        if field in self.reverse_alias_mappings:
            equivalents.add(self.reverse_alias_mappings[field])
        
        # Add CIF1/CIF2 variants
        if field in self.cif1_to_cif2:
            equivalents.add(self.cif1_to_cif2[field])
        if field in self.cif2_to_cif1:
            equivalents.add(self.cif2_to_cif1[field])
        
        # Add derived variations (e.g., underscore vs dot notation)
        for equiv_field in list(equivalents):
            equivalents.update(self._get_format_variants(equiv_field))
        
        return equivalents
    
    def _get_format_variants(self, field: str) -> Set[str]:
        """Get CIF1/CIF2 format variants of a field"""
        variants = set()
        
        if not field.startswith('_'):
            return variants
        
        field_without_underscore = field[1:]
        
        # CIF1 format: _category_item -> CIF2 format: _category.item
        if '_' in field_without_underscore and '.' not in field_without_underscore:
            # This looks like CIF1 format
            parts = field_without_underscore.split('_', 1)
            if len(parts) == 2:
                cif2_variant = f"_{parts[0]}.{parts[1]}"
                variants.add(cif2_variant)
        
        # CIF2 format: _category.item -> CIF1 format: _category_item
        elif '.' in field_without_underscore and '_' not in field_without_underscore.split('.')[0]:
            # This looks like CIF2 format
            cif1_variant = field.replace('.', '_')
            variants.add(cif1_variant)
        
        return variants
    
    def _get_canonical_field(self, equivalent_fields: Set[str]) -> str:
        """
        Get the canonical field name from a set of equivalents.
        Prefer definition_id (from dictionary) over aliases.
        """
        # Look for fields that are definition_ids (not aliases)
        definition_ids = set()
        for field in equivalent_fields:
            if field not in self.alias_mappings:  # Not an alias
                definition_ids.add(field)
        
        if definition_ids:
            # Prefer CIF2 format if available
            cif2_fields = {f for f in definition_ids if '.' in f}
            if cif2_fields:
                return sorted(cif2_fields)[0]  # Return alphabetically first
            else:
                return sorted(definition_ids)[0]
        
        # Fallback to any field in the group
        return sorted(equivalent_fields)[0]
    
    def are_fields_equivalent(self, field1: str, field2: str) -> bool:
        """Check if two fields are equivalent"""
        if field1 == field2:
            return True
        
        # Find which groups these fields belong to
        group1 = self.get_equivalence_group(field1)
        group2 = self.get_equivalence_group(field2)
        
        return group1 is not None and group1 == group2
    
    def get_equivalence_group(self, field: str) -> Optional[str]:
        """Get the canonical group name for a field"""
        for canonical_field, equivalent_fields in self.equivalence_groups.items():
            if field in equivalent_fields:
                return canonical_field
        return None
    
    def get_all_equivalents(self, field: str) -> Set[str]:
        """Get all equivalent forms of a field"""
        group_key = self.get_equivalence_group(field)
        if group_key:
            return self.equivalence_groups[group_key].copy()
        return {field}
    
    def check_for_equivalent_fields(self, content: str, target_field: str) -> List[str]:
        """
        Check if any equivalent fields already exist in the content
        
        Args:
            content: CIF file content
            target_field: Field we want to add
            
        Returns:
            List of equivalent fields already present in the content
        """
        # Extract all fields from content
        present_fields = self._extract_fields_from_content(content)
        
        # Get all equivalents of the target field
        target_equivalents = self.get_all_equivalents(target_field)
        
        # Find which equivalents are already present
        present_equivalents = []
        for field in present_fields:
            if field in target_equivalents:
                present_equivalents.append(field)
        
        return present_equivalents
    
    def suggest_format_consistent_field(self, content: str, target_field: str) -> str:
        """
        Suggest the most format-consistent version of a field based on existing content
        
        Args:
            content: CIF file content
            target_field: Field we want to add
            
        Returns:
            Recommended field name that's consistent with the file format
        """
        # Detect the current file format
        cif_version = self.analyzer._detect_cif_version(content, 
                                                       self._extract_fields_from_content(content))[0]
        
        # Get all equivalent forms
        equivalents = self.get_all_equivalents(target_field)
        
        # Choose based on detected format
        if cif_version == CIFVersion.CIF2:
            # Prefer CIF2 format (dot notation)
            cif2_fields = [f for f in equivalents if '.' in f]
            if cif2_fields:
                return sorted(cif2_fields)[0]
        elif cif_version == CIFVersion.CIF1:
            # Prefer CIF1 format (underscore notation)
            cif1_fields = [f for f in equivalents if '.' not in f and '_' in f]
            if cif1_fields:
                return sorted(cif1_fields)[0]
        
        # Fallback to canonical field
        return self.get_equivalence_group(target_field) or target_field
    
    def get_duplicate_prevention_report(self, content: str) -> Dict[str, List[str]]:
        """
        Generate a report of potential duplicate fields in the content
        
        Args:
            content: CIF file content
            
        Returns:
            Dictionary mapping canonical fields to lists of duplicates found
        """
        present_fields = self._extract_fields_from_content(content)
        duplicates = {}
        
        # Group present fields by their equivalence groups
        field_groups = {}
        for field in present_fields:
            group_key = self.get_equivalence_group(field)
            if group_key:
                if group_key not in field_groups:
                    field_groups[group_key] = []
                field_groups[group_key].append(field)
        
        # Find groups with multiple fields (duplicates)
        for group_key, fields in field_groups.items():
            if len(fields) > 1:
                duplicates[group_key] = fields
        
        return duplicates
    
    def resolve_duplicates(self, content: str, prefer_format: Optional[CIFVersion] = None) -> Tuple[str, List[str]]:
        """
        Resolve duplicate equivalent fields in content
        
        Args:
            content: CIF file content
            prefer_format: Preferred CIF format (auto-detect if None)
            
        Returns:
            Tuple of (cleaned_content, list_of_changes)
        """
        if prefer_format is None:
            prefer_format = self.analyzer._detect_cif_version(content, 
                                                             self._extract_fields_from_content(content))[0]
        
        changes = []
        lines = content.split('\n')
        cleaned_lines = []
        removed_fields = set()
        
        for line in lines:
            line_field = self._extract_field_from_line(line)
            
            if line_field and line_field not in removed_fields:
                # Check if this field has duplicates
                equivalents = self.get_all_equivalents(line_field)
                
                # Find the preferred field for this group
                preferred_field = self._get_preferred_field_for_format(equivalents, prefer_format)
                
                if line_field != preferred_field:
                    # Replace field name with preferred form
                    new_line = line.replace(line_field, preferred_field, 1)
                    cleaned_lines.append(new_line)
                    changes.append(f"Converted field: {line_field} → {preferred_field}")
                    
                    # Mark other equivalents as removed
                    for equiv in equivalents:
                        if equiv != preferred_field:
                            removed_fields.add(equiv)
                else:
                    cleaned_lines.append(line)
                    # Mark other equivalents as removed
                    for equiv in equivalents:
                        if equiv != line_field:
                            removed_fields.add(equiv)
            elif line_field and line_field in removed_fields:
                # Skip this line - it's a duplicate
                changes.append(f"Removed duplicate field: {line_field}")
            else:
                # Not a field line, keep as-is
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines), changes
    
    def _get_preferred_field_for_format(self, equivalents: Set[str], format_version: CIFVersion) -> str:
        """Get the preferred field name for a specific CIF format"""
        if format_version == CIFVersion.CIF2:
            # Prefer dot notation
            cif2_fields = [f for f in equivalents if '.' in f]
            if cif2_fields:
                return sorted(cif2_fields)[0]
        elif format_version == CIFVersion.CIF1:
            # Prefer underscore notation
            cif1_fields = [f for f in equivalents if '.' not in f and '_' in f]
            if cif1_fields:
                return sorted(cif1_fields)[0]
        
        # Fallback to canonical field
        canonical = self.get_equivalence_group(list(equivalents)[0])
        return canonical or sorted(equivalents)[0]
    
    def _extract_fields_from_content(self, content: str) -> Set[str]:
        """Extract all CIF field names from content"""
        fields = set()
        
        for line in content.split('\n'):
            field = self._extract_field_from_line(line)
            if field:
                fields.add(field)
        
        return fields
    
    def _extract_field_from_line(self, line: str) -> Optional[str]:
        """Extract field name from a single line"""
        line = line.strip()
        if line.startswith('_'):
            # Extract the field name (first word)
            parts = line.split()
            if parts:
                return parts[0]
        return None


# Example usage and testing
if __name__ == "__main__":
    # Fix imports for standalone testing
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    
    from cif_dictionary_manager import CIFDictionaryManager
    from cif_converter import CIFConverter
    from cif_analyzer import CIFAnalyzer, CIFVersion
    
    print("Testing Field Equivalence Manager...")
    
    manager = FieldEquivalenceManager()
    
    # Test equivalence checking
    test_pairs = [
        ('_cell_length_a', '_cell.length_a'),
        ('_cell_length_a', '_cell_measurement_temperature'),
        ('_diffrn_radiation_probe', '_diffrn_radiation.probe'),
        ('_space_group_IT_number', '_symmetry_Int_Tables_number'),
    ]
    
    print("\nEquivalence Tests:")
    for field1, field2 in test_pairs:
        equivalent = manager.are_fields_equivalent(field1, field2)
        print(f"  {field1} ≡ {field2}: {equivalent}")
        
        if equivalent:
            equivalents = manager.get_all_equivalents(field1)
            print(f"    All equivalents: {sorted(equivalents)}")
    
    # Test with sample CIF content
    test_content = """
#\\#CIF_1.1
data_test

_cell_length_a    10.0
_cell.length_b    10.0
_cell_length_c    10.0
_diffrn_radiation_probe  electron
_diffrn_radiation.probe  electron
"""
    
    print(f"\nDuplicate Detection:")
    duplicates = manager.get_duplicate_prevention_report(test_content)
    for group, fields in duplicates.items():
        print(f"  Group {group}: {fields}")
    
    print(f"\nEquivalent Field Check for '_cell.length_a':")
    existing = manager.check_for_equivalent_fields(test_content, '_cell.length_a')
    print(f"  Already present: {existing}")
    
    print(f"\nFormat Suggestion for '_cell_length_b' in this content:")
    suggested = manager.suggest_format_consistent_field(test_content, '_cell_length_b')
    print(f"  Suggested: {suggested}")
