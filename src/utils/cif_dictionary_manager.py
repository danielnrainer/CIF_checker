"""
CIF Dictionary Manager with Lazy Loading
Efficiently manages CIF field definitions without parsing the entire dictionary upfront.
"""

import re
import os
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CIFFieldInfo:
    """Information about a single CIF field"""
    name: str
    description: str
    type: str
    mandatory: bool = False
    enumeration: Optional[List[str]] = None
    example: Optional[str] = None
    category: Optional[str] = None
    related_fields: Optional[List[str]] = None


class CIFDictionaryManager:
    """
    Smart CIF dictionary manager that only loads field information when needed.
    
    Features:
    - Lazy loading: Only parse fields when requested
    - Category-based loading: Bulk load related fields
    - Intelligent caching: Remember frequently used fields
    - Fast field extraction: Quickly find which fields are in a CIF
    """
    
    def __init__(self, dict_path: Optional[str] = None):
        """Initialize the dictionary manager"""
        self.dict_path = dict_path or self._find_cif_dict()
        self._cached_fields: Dict[str, CIFFieldInfo] = {}
        self._field_categories: Dict[str, List[str]] = {}
        self._loaded_categories: Set[str] = set()
        self._dict_content: Optional[str] = None
        self._field_positions: Dict[str, tuple] = {}  # (start_line, end_line)
        self._alias_to_definition: Dict[str, str] = {}  # Maps aliases to definition IDs
        
        # Initialize field position index for fast lookup
        self._build_field_index()
    
    def _find_cif_dict(self) -> str:
        """Find the cif_core.dic file in the project"""
        current_dir = Path(__file__).parent.parent.parent
        dict_file = current_dir / "cif_core.dic"
        
        if dict_file.exists():
            return str(dict_file)
        else:
            raise FileNotFoundError("cif_core.dic not found in project directory")
    
    def _build_field_index(self):
        """Build an index of field positions for fast lookup without full parsing"""
        if not os.path.exists(self.dict_path):
            print(f"Warning: CIF dictionary not found at {self.dict_path}")
            return
        
        print("Building CIF field index...")
        with open(self.dict_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        current_field = None
        start_line = 0
        in_field_definition = False
        current_definition_id = None
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Look for save_ blocks that contain field definitions
            if line_stripped.startswith('save_') and not line_stripped == 'save_':
                # Save previous field if exists
                if current_field and in_field_definition:
                    self._field_positions[current_field] = (start_line, i-1)
                
                in_field_definition = False
                current_field = None
                current_definition_id = None
                start_line = i
            
            # Look for _definition.id lines within save_ blocks
            elif line_stripped.startswith('_definition.id') and start_line is not None:
                # Extract field name from definition.id
                parts = line_stripped.split()
                if len(parts) >= 2:
                    field_name = parts[1].strip("'\"")
                    if field_name.startswith('_'):
                        # Remove the leading underscore for our internal indexing
                        current_field = field_name[1:]
                        current_definition_id = field_name
                        in_field_definition = True
            
            # Look for _alias.definition_id lines within save_ blocks
            elif line_stripped.startswith('_alias.definition_id') and current_definition_id:
                # Extract alias field name
                parts = line_stripped.split()
                if len(parts) >= 2:
                    alias_name = parts[1].strip("'\"")
                    if alias_name.startswith('_'):
                        # Map alias to the current definition ID
                        self._alias_to_definition[alias_name] = current_definition_id
            
            # Handle aliases in loop blocks (multiple aliases can be listed in a loop)
            elif in_field_definition and current_definition_id:
                # Check if this line contains an alias field name
                # Format could be: '_alias_name'  or  '_alias_name'  2003-10-04  etc.
                if line_stripped.startswith("'_") and line_stripped.count("'") >= 2:
                    # Extract just the field name part (before any additional info)
                    first_quote = line_stripped.find("'")
                    second_quote = line_stripped.find("'", first_quote + 1)
                    if second_quote > first_quote:
                        alias_name = line_stripped[first_quote+1:second_quote]
                        if alias_name.startswith('_'):
                            self._alias_to_definition[alias_name] = current_definition_id
            
            # Handle end of save_ block
            elif line_stripped == 'save_' and current_field and in_field_definition:
                self._field_positions[current_field] = (start_line, i)
                in_field_definition = False
                current_field = None
        
        # Don't forget the last field
        if current_field and in_field_definition:
            self._field_positions[current_field] = (start_line, len(lines)-1)
        
        print(f"Indexed {len(self._field_positions)} CIF fields and {len(self._alias_to_definition)} aliases")

    def get_all_field_names(self) -> Set[str]:
        """Get all available field names from the dictionary"""
        return set(self._field_positions.keys())
    
    def get_alias_mappings(self) -> Dict[str, str]:
        """
        Get all alias to definition ID mappings.
        
        Returns:
            Dictionary mapping alias field names to their definition IDs
        """
        return self._alias_to_definition.copy()
    
    def resolve_alias(self, field_name: str) -> str:
        """
        Resolve a field name that might be an alias to its definition ID.
        
        Args:
            field_name: Field name that might be an alias
            
        Returns:
            The definition ID if the field is an alias, otherwise the original field name
        """
        return self._alias_to_definition.get(field_name, field_name)
    
    def get_field_info(self, field_name: str) -> Optional[CIFFieldInfo]:
        """
        Get information about a specific field (lazy loading)
        
        Args:
            field_name: CIF field name (e.g., '_cell_length_a' or '_cell.length_a')
        
        Returns:
            CIFFieldInfo object or None if field not found
        """
        # Normalize field name (handle both CIF1 and CIF2 formats)
        normalized_name = self._normalize_field_name(field_name)
        
        # Check cache first
        if normalized_name in self._cached_fields:
            return self._cached_fields[normalized_name]
        
        # Load field on demand
        field_info = self._load_field_on_demand(normalized_name)
        if field_info:
            self._cached_fields[normalized_name] = field_info
        
        return field_info
    
    def _normalize_field_name(self, field_name: str) -> str:
        """
        Normalize field names to handle CIF1 (_field_name) and CIF2 (_category.item) formats
        """
        # Remove leading underscore for processing
        clean_name = field_name.lstrip('_')
        
        # Convert CIF1 underscore notation to CIF2 dot notation for dictionary lookup
        # _cell_length_a -> cell.length_a
        if '.' not in clean_name and '_' in clean_name:
            # Find the first underscore and convert it to a dot
            parts = clean_name.split('_', 1)
            if len(parts) == 2:
                clean_name = f"{parts[0]}.{parts[1]}"
        
        return clean_name
    
    def _load_field_on_demand(self, field_name: str) -> Optional[CIFFieldInfo]:
        """Load a specific field definition from the dictionary"""
        if field_name not in self._field_positions:
            return None
        
        if self._dict_content is None:
            with open(self.dict_path, 'r', encoding='utf-8') as f:
                self._dict_content = f.read()
        
        start_line, end_line = self._field_positions[field_name]
        lines = self._dict_content.split('\n')[start_line:end_line+1]
        
        return self._parse_field_definition(field_name, lines)
    
    def _parse_field_definition(self, field_name: str, lines: List[str]) -> CIFFieldInfo:
        """Parse field definition from dictionary lines"""
        description = ""
        field_type = "text"
        enumeration = None
        example = None
        category = None
        
        in_description = False
        description_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Extract description
            if line.startswith('_definition.update'):
                in_description = True
                continue
            elif line.startswith('_description.text') or in_description:
                if line.startswith(';'):
                    # Multiline description
                    description_lines.append(line[1:])
                elif line.endswith(';'):
                    description_lines.append(line[:-1])
                    in_description = False
                elif in_description:
                    description_lines.append(line)
            
            # Extract type information
            elif line.startswith('_type.contents'):
                field_type = line.split()[-1] if len(line.split()) > 1 else "text"
            
            # Extract enumeration values
            elif line.startswith('_enumeration_set.state'):
                if enumeration is None:
                    enumeration = []
                value = line.split()[-1].strip("'\"")
                enumeration.append(value)
            
            # Extract category
            elif line.startswith('_name.category_id'):
                category = line.split()[-1].strip("'\"")
            
            # Extract example
            elif line.startswith('_example.case'):
                example = line.split('_example.case')[-1].strip().strip("'\"")
        
        description = ' '.join(description_lines).strip()
        
        return CIFFieldInfo(
            name=f"_{field_name}",
            description=description,
            type=field_type,
            enumeration=enumeration,
            example=example,
            category=category
        )
    
    def extract_present_fields(self, cif_path: str) -> Set[str]:
        """
        Quickly extract which fields are present in a CIF file without full parsing
        
        Args:
            cif_path: Path to CIF file
        
        Returns:
            Set of field names found in the file
        """
        present_fields = set()
        
        try:
            with open(cif_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find all CIF field patterns
            # CIF field names are terminated by whitespace - captures everything after _
            field_pattern = r'_([^\s]+)'
            matches = re.findall(field_pattern, content)
            
            for match in matches:
                present_fields.add(f"_{match}")
        
        except Exception as e:
            print(f"Error reading CIF file {cif_path}: {e}")
        
        return present_fields
    
    def preload_category(self, category: str):
        """
        Bulk load all fields in a specific category
        
        Args:
            category: Category name (e.g., 'cell', 'diffrn', 'atom_site')
        """
        if category in self._loaded_categories:
            return
        
        # Find all fields in this category
        category_fields = []
        for field_name in self._field_positions.keys():
            if field_name.startswith(category + '_') or field_name.startswith(category + '.'):
                field_info = self.get_field_info(field_name)
                if field_info:
                    category_fields.append(field_name)
        
        self._field_categories[category] = category_fields
        self._loaded_categories.add(category)
        
        print(f"Preloaded {len(category_fields)} fields for category '{category}'")
    
    def get_category_fields(self, category: str) -> List[str]:
        """Get all field names in a category"""
        if category not in self._loaded_categories:
            self.preload_category(category)
        
        return self._field_categories.get(category, [])
    
    def is_valid_field(self, field_name: str) -> bool:
        """Check if a field name exists in the CIF dictionary"""
        normalized_name = self._normalize_field_name(field_name)
        return normalized_name in self._field_positions
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get statistics about cache usage"""
        return {
            "total_fields_indexed": len(self._field_positions),
            "cached_fields": len(self._cached_fields),
            "loaded_categories": len(self._loaded_categories),
            "cache_hit_rate": len(self._cached_fields) / max(1, len(self._field_positions)) * 100
        }
    
    def clear_cache(self):
        """Clear all cached field information"""
        self._cached_fields.clear()
        self._field_categories.clear()
        self._loaded_categories.clear()
        print("Cache cleared")


# Convenience function for quick field checking
def get_cif_field_info(field_name: str, dict_manager: Optional[CIFDictionaryManager] = None) -> Optional[CIFFieldInfo]:
    """
    Quick function to get field information
    
    Args:
        field_name: CIF field name
        dict_manager: Optional existing manager instance
    
    Returns:
        CIFFieldInfo or None
    """
    if dict_manager is None:
        dict_manager = CIFDictionaryManager()
    
    return dict_manager.get_field_info(field_name)


if __name__ == "__main__":
    # Test the lazy loading system
    print("Testing CIF Dictionary Manager...")
    
    manager = CIFDictionaryManager()
    print(f"Cache stats: {manager.get_cache_stats()}")
    
    # Show some indexed field names for debugging
    field_names = list(manager._field_positions.keys())
    print(f"\nFirst 10 indexed fields: {field_names[:10]}")
    print(f"Sample cell-related fields: {[f for f in field_names if 'cell' in f][:5]}")
    print(f"Sample diffrn-related fields: {[f for f in field_names if 'diffrn' in f][:5]}")
    
    # Test field lookup - use both CIF1 and CIF2 formats
    test_fields = [
        '_cell_length_a',      # CIF1 format
        '_cell.length_a',      # CIF2 format
        'cell.length_a',       # Direct format
        '_diffrn_radiation_probe',  # CIF1 format (might not exist)
        '_diffrn.radiation_probe',  # CIF2 format (might not exist)
        '_atom_site_label',         # CIF1 format
        '_atom_site.label'          # CIF2 format
    ]
    
    for field in test_fields:
        print(f"\nTesting field: {field}")
        info = manager.get_field_info(field)
        if info:
            print(f"  ✅ Found: {info.name}")
            print(f"  Description: {info.description[:80]}...")
            print(f"  Type: {info.type}")
            print(f"  Category: {info.category}")
            if info.enumeration:
                print(f"  Allowed values: {info.enumeration[:3]}...")  # Show first 3 values
        else:
            print(f"  ❌ Field not found")
    
    print(f"\nFinal cache stats: {manager.get_cache_stats()}")
