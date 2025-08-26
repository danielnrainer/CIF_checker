"""
Comprehensive CIF file parser and field manager.

This module handles parsing actual CIF file content, extracting field values,
and managing both single-line and multiline CIF fields. It also provides
functionality for reformatting CIF files with proper line length handling.

This is different from CIF_field_parsing.py, which handles field definition
templates for validation purposes.

Classes:
    CIFField: Represents an actual field instance parsed from a CIF file
    CIFParser: Main parser class for processing CIF file content
"""

import re
from typing import Dict, Any, List, Tuple, Optional


class CIFField:
    """Represents a single CIF field instance parsed from a CIF file.
    
    This contains the actual value and metadata of a field found in a CIF file.
    This is different from CIFField in CIF_field_parsing.py, which
    represents field definition templates for validation.
    """
    
    def __init__(self, name: str, value: Any = None, is_multiline: bool = False, 
                 line_number: int = None, raw_lines: List[str] = None):
        self.name = name
        self.value = value
        self.is_multiline = is_multiline
        self.line_number = line_number  # Starting line number in the file
        self.raw_lines = raw_lines or []  # Original lines from the file
    
    def __repr__(self):
        return f"CIFField(name='{self.name}', value='{self.value}', multiline={self.is_multiline})"


class CIFParser:
    """Main parser class for processing CIF file content."""
    
    def __init__(self):
        self.fields: Dict[str, CIFField] = {}
        
    def parse_file(self, content: str) -> Dict[str, CIFField]:
        """Parse CIF content and return a dictionary of fields."""
        self.fields = {}
        lines = content.splitlines()
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                i += 1
                continue
            
            # Check if this line starts a field definition
            if line.startswith('_'):
                field_name, value, lines_consumed = self._parse_field(lines, i)
                if field_name:
                    self.fields[field_name] = CIFField(
                        name=field_name,
                        value=value,
                        is_multiline=self._is_multiline_value(value),
                        line_number=i + 1,
                        raw_lines=lines[i:i+lines_consumed]
                    )
                i += lines_consumed
            else:
                i += 1
                
        return self.fields
    
    def _parse_field(self, lines: List[str], start_index: int) -> Tuple[str, str, int]:
        """Parse a single field starting at the given line index.
        
        Returns:
            Tuple of (field_name, value, lines_consumed)
        """
        line = lines[start_index].strip()
        
        # Parse field name
        parts = line.split(maxsplit=1)
        if not parts or not parts[0].startswith('_'):
            return None, None, 1
        
        field_name = parts[0]
        
        # Check if value is on the same line
        if len(parts) > 1:
            value_part = parts[1].strip()
            
            # Check if it's a quoted string
            if (value_part.startswith("'") and value_part.endswith("'")) or \
               (value_part.startswith('"') and value_part.endswith('"')):
                return field_name, value_part[1:-1], 1
            
            # Check if it starts a multiline block
            if value_part == ';':
                return self._parse_multiline_value(lines, start_index + 1, field_name)
            
            # Check if content starts on same line as opening semicolon (;content...)
            if value_part.startswith(';') and len(value_part) > 1:
                return self._parse_multiline_value_with_content_on_first_line(lines, start_index, field_name)
            
            # Regular single-line value
            return field_name, value_part, 1
        
        # Value might be on the next line(s)
        if start_index + 1 < len(lines):
            next_line = lines[start_index + 1].strip()
            
            # Check if next line starts multiline block
            if next_line == ';':
                return self._parse_multiline_value(lines, start_index + 2, field_name)
            
            # Check if next line contains content starting with semicolon (;content...)
            if next_line.startswith(';') and len(next_line) > 1:
                return self._parse_multiline_value_with_content_on_first_line(lines, start_index + 1, field_name)
            
            # Single line value on next line
            if next_line and not next_line.startswith('_'):
                # Handle quoted values
                if (next_line.startswith("'") and next_line.endswith("'")) or \
                   (next_line.startswith('"') and next_line.endswith('"')):
                    return field_name, next_line[1:-1], 2
                return field_name, next_line, 2
        
        # No value found
        return field_name, None, 1
    
    def _parse_multiline_value(self, lines: List[str], start_index: int, field_name: str) -> Tuple[str, str, int]:
        """Parse a multiline value starting after the opening semicolon."""
        value_lines = []
        i = start_index
        
        # Handle case where content starts on the same line as opening semicolon
        if start_index > 0:
            prev_line = lines[start_index - 1].strip()
            if prev_line.startswith(';') and len(prev_line) > 1:
                # Content starts on same line as opening semicolon
                content = prev_line[1:].strip()
                if content:
                    value_lines.append(content)
                # Adjust to look for closing semicolon
                start_index_actual = start_index
            else:
                start_index_actual = start_index
        else:
            start_index_actual = start_index
        
        # Parse lines until closing semicolon
        while i < len(lines):
            line = lines[i]
            
            # Check for closing semicolon
            if line.strip() == ';':
                lines_consumed = i - start_index + 2  # +2 for opening and closing semicolons
                return field_name, '\n'.join(value_lines), lines_consumed
            
            # Add line to value (preserve original spacing)
            value_lines.append(line)
            i += 1
        
        # If we reach here, no closing semicolon was found
        lines_consumed = len(lines) - start_index + 1
        return field_name, '\n'.join(value_lines), lines_consumed
    
    def _parse_multiline_value_with_content_on_first_line(self, lines: List[str], start_index: int, field_name: str) -> Tuple[str, str, int]:
        """Parse multiline value where content starts on same line as opening semicolon."""
        line = lines[start_index].strip()
        
        # Extract content after the opening semicolon
        if line.startswith(';'):
            first_content = line[1:].strip()
            value_lines = [first_content] if first_content else []
            
            # Look for remaining lines until closing semicolon
            i = start_index + 1
            while i < len(lines):
                current_line = lines[i]
                
                # Check for closing semicolon
                if current_line.strip() == ';':
                    lines_consumed = i - start_index + 1
                    return field_name, '\n'.join(value_lines), lines_consumed
                
                # Add line to value (preserve original spacing)
                value_lines.append(current_line)
                i += 1
            
            # No closing semicolon found
            lines_consumed = len(lines) - start_index
            return field_name, '\n'.join(value_lines), lines_consumed
        
        # Fallback to regular parsing
        return field_name, None, 1
    
    def _is_multiline_value(self, value: str) -> bool:
        """Check if a value should be treated as multiline."""
        if not value:
            return False
        return '\n' in value or len(value) > 80
    
    def get_field(self, field_name: str) -> Optional[CIFField]:
        """Get a field by name."""
        return self.fields.get(field_name)
    
    def get_field_value(self, field_name: str) -> Optional[str]:
        """Get a field's value by name."""
        field = self.fields.get(field_name)
        return field.value if field else None
    
    def set_field_value(self, field_name: str, value: str):
        """Set a field's value."""
        if field_name in self.fields:
            self.fields[field_name].value = value
            self.fields[field_name].is_multiline = self._is_multiline_value(value)
        else:
            self.fields[field_name] = CIFField(
                name=field_name,
                value=value,
                is_multiline=self._is_multiline_value(value)
            )
    
    def generate_cif_content(self) -> str:
        """Generate CIF content from the current fields."""
        lines = []
        
        for field_name, field in self.fields.items():
            formatted_lines = self._format_field(field)
            lines.extend(formatted_lines)
        
        return '\n'.join(lines)
    
    def _format_field(self, field: CIFField) -> List[str]:
        """Format a CIF field for output with proper 80-character line length handling."""
        if field.value is None:
            return [field.name]
        
        # Check if we should use multiline format based on content or length
        needs_multiline = self._should_use_multiline_format(field.name, field.value)
        
        if needs_multiline or field.is_multiline:
            # Use multiline format with proper line breaking
            lines = [field.name, ';']
            
            # Break long lines within the multiline content
            content_lines = field.value.split('\n')
            for content_line in content_lines:
                if len(content_line) <= 80:
                    lines.append(content_line)
                else:
                    # Break long lines into multiple lines
                    broken_lines = self._break_long_line(content_line, 80)
                    lines.extend(broken_lines)
            
            lines.append(';')
            return lines
        else:
            # Single line format with proper quoting and length checking
            value = field.value
            
            # Determine if we need quotes
            needs_quotes = self._needs_quotes(value)
            formatted_value = f"'{value}'" if needs_quotes else value
            
            # Check total line length (field name + 4 spaces + value)
            total_length = len(field.name) + 4 + len(formatted_value)
            
            if total_length <= 80:
                # Fits on one line
                return [f"{field.name}    {formatted_value}"]
            else:
                # Too long for single line, use multiline format
                return [field.name, ';', value, ';']
    
    def _needs_quotes(self, value: str) -> bool:
        """Determine if a value needs to be quoted."""
        if not value:
            return False
        
        # Quote if contains spaces, commas, starts with semicolon or hash
        return (' ' in value or ',' in value or 
                value.startswith(';') or value.startswith('#') or
                value.startswith("'") or value.startswith('"'))
    
    def _break_long_line(self, text: str, max_length: int) -> List[str]:
        """Break a long line into multiple lines at word boundaries."""
        if len(text) <= max_length:
            return [text]
        
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            # Check if adding this word would exceed the limit
            word_length = len(word)
            space_needed = 1 if current_line else 0  # Space before word (if not first word)
            
            if current_length + space_needed + word_length <= max_length:
                # Add word to current line
                current_line.append(word)
                current_length += space_needed + word_length
            else:
                # Start new line
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = word_length
        
        # Add the last line if there are remaining words
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def list_fields(self) -> List[str]:
        """Return a list of all field names."""
        return list(self.fields.keys())
    
    def has_field(self, field_name: str) -> bool:
        """Check if a field exists."""
        return field_name in self.fields
    
    def reformat_for_line_length(self, content: str) -> str:
        """Reformat CIF content to ensure no line exceeds 80 characters while preserving loop structures.
        
        Args:
            content: The CIF content to reformat
            
        Returns:
            Reformatted CIF content with proper line length handling and preserved loops
        """
        lines = content.splitlines()
        reformatted_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines and preserve them
            if not line:
                reformatted_lines.append("")
                i += 1
                continue
            
            # Preserve comments
            if line.startswith('#'):
                reformatted_lines.append(lines[i])
                i += 1
                continue
            
            # Handle loop structures - preserve them entirely
            if line.startswith('loop_'):
                loop_lines, lines_consumed = self._extract_loop_structure(lines, i)
                # Validate that loop lines don't exceed 80 characters (but don't modify them)
                for loop_line in loop_lines:
                    if len(loop_line.strip()) <= 80:
                        reformatted_lines.append(loop_line)
                    else:
                        # For loop lines that are too long, we preserve them as-is
                        # since breaking them would destroy the loop structure
                        reformatted_lines.append(loop_line)
                i += lines_consumed
                continue
            
            # Handle individual fields (non-loop structures)
            if line.startswith('_'):
                field_lines, lines_consumed = self._reformat_individual_field(lines, i)
                reformatted_lines.extend(field_lines)
                i += lines_consumed
                continue
            
            # Handle data blocks and other CIF constructs
            if line.startswith('data_') or line.startswith('global_') or line.startswith('save_'):
                reformatted_lines.append(lines[i])
                i += 1
                continue
            
            # For any other lines, preserve as-is
            reformatted_lines.append(lines[i])
            i += 1
        
        return '\n'.join(reformatted_lines)
    
    def _extract_loop_structure(self, lines: List[str], start_index: int) -> Tuple[List[str], int]:
        """Extract a complete loop structure starting from loop_ keyword.
        
        Returns:
            Tuple of (loop_lines, lines_consumed)
        """
        loop_lines = []
        i = start_index
        
        # Add the loop_ line
        loop_lines.append(lines[i])
        i += 1
        
        # Collect all field names (lines starting with _)
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                loop_lines.append(lines[i])
                i += 1
                continue
            if line.startswith('_'):
                loop_lines.append(lines[i])
                i += 1
            else:
                break
        
        # Collect all data rows until we hit another field, loop, or end of data
        while i < len(lines):
            line = lines[i].strip()
            
            # Stop if we hit another CIF construct
            if (line.startswith('_') or line.startswith('loop_') or 
                line.startswith('data_') or line.startswith('global_') or 
                line.startswith('save_')):
                break
            
            # Add the data line (including empty lines within the loop)
            loop_lines.append(lines[i])
            i += 1
        
        return loop_lines, i - start_index
    
    def _reformat_individual_field(self, lines: List[str], start_index: int) -> Tuple[List[str], int]:
        """Reformat an individual CIF field for proper line length.
        
        Returns:
            Tuple of (formatted_lines, lines_consumed)
        """
        line = lines[start_index].strip()
        
        # Parse the field
        if ';' in line:
            # Multiline field starting on same line
            field_name = line.split()[0]
            if line.endswith(';') and line.count(';') == 2:
                # Single line with semicolons: _field ;value;
                value = line[line.find(';')+1:line.rfind(';')]
                if len(line) <= 80:
                    return [lines[start_index]], 1
                else:
                    # Convert to proper multiline format with line breaking
                    result_lines = [field_name, ';']
                    if len(value) > 80:
                        broken_lines = self._break_long_line(value, 80)
                        result_lines.extend(broken_lines)
                    else:
                        result_lines.append(value)
                    result_lines.append(';')
                    return result_lines, 1
            else:
                # True multiline field - preserve structure if already well-formatted
                field_lines = [lines[start_index]]  # Field name line
                content_lines = []
                i = start_index + 1
                
                # Collect content until closing semicolon
                while i < len(lines):
                    line = lines[i]
                    if line.strip() == ';' and i > start_index:
                        # Found closing semicolon
                        break
                    elif line.strip() != ';':  # Skip opening semicolon
                        content_lines.append(line)
                    i += 1
                
                # Check if any content lines are too long
                needs_reformatting = any(len(line.strip()) > 80 for line in content_lines)
                
                field_lines.append(';')
                if needs_reformatting:
                    # Only reformat if there are actually long lines
                    # Combine only the long lines and preserve structure of short ones
                    for line in content_lines:
                        if len(line.strip()) > 80:
                            # Break this long line
                            broken_lines = self._break_long_line(line.strip(), 80)
                            field_lines.extend(broken_lines)
                        else:
                            # Keep this line as-is
                            field_lines.append(line.rstrip())
                else:
                    # All lines are fine, preserve original structure
                    field_lines.extend(line.rstrip() for line in content_lines)
                
                field_lines.append(';')
                
                return field_lines, i - start_index + 1
        
        # Check if next line is semicolon (multiline field)
        if (start_index + 1 < len(lines) and 
            lines[start_index + 1].strip() == ';'):
            # Multiline field - preserve structure if already well-formatted
            field_name = lines[start_index].strip()
            content_lines = []
            i = start_index + 2  # Skip field name and opening semicolon
            
            # Collect content until closing semicolon
            while i < len(lines):
                line = lines[i]
                if line.strip() == ';':
                    # Found closing semicolon
                    break
                content_lines.append(line)
                i += 1
            
            # Check if any content lines are too long
            needs_reformatting = any(len(line.strip()) > 80 for line in content_lines)
            
            field_lines = [field_name, ';']
            if needs_reformatting:
                # Only reformat if there are actually long lines
                for line in content_lines:
                    if len(line.strip()) > 80:
                        # Break this long line
                        broken_lines = self._break_long_line(line.strip(), 80)
                        field_lines.extend(broken_lines)
                    else:
                        # Keep this line as-is
                        field_lines.append(line.rstrip())
            else:
                # All lines are fine, preserve original structure
                field_lines.extend(line.rstrip() for line in content_lines)
            
            field_lines.append(';')
            
            return field_lines, i - start_index + 1
        
        # Check if value is on the next line (field name alone on first line)
        if (start_index + 1 < len(lines) and 
            not lines[start_index + 1].strip().startswith('_') and
            not lines[start_index + 1].strip().startswith('loop_') and
            not lines[start_index + 1].strip().startswith('data_') and
            lines[start_index + 1].strip() and
            lines[start_index + 1].strip() != ';'):
            # Value is on next line - check if combined length is too long
            field_name = line
            value_line = lines[start_index + 1]
            combined_length = len(field_name) + len(value_line.strip()) + 4  # 4 spaces for formatting
            
            if combined_length <= 80:
                # Can combine into single line
                value = value_line.strip()
                if value.startswith("'") and value.endswith("'"):
                    formatted_line = f"{field_name}    {value}"
                elif value.startswith('"') and value.endswith('"'):
                    formatted_line = f"{field_name}    {value}"
                else:
                    formatted_line = f"{field_name}    {value}"
                return [formatted_line], 2
            else:
                # Too long even when combined, convert to multiline with proper line breaking
                value = value_line.strip()
                if value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                elif value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                
                # Break long value into multiple lines
                result_lines = [field_name, ';']
                if len(value) > 80:
                    broken_lines = self._break_long_line(value, 80)
                    result_lines.extend(broken_lines)
                else:
                    result_lines.append(value)
                result_lines.append(';')
                return result_lines, 2
        
        # Single line field
        original_line = lines[start_index]
        if len(original_line.strip()) <= 80:
            return [original_line], 1
        else:
            # Line is too long, need to convert to multiline with proper line breaking
            parts = line.split(None, 1)
            if len(parts) == 2:
                field_name, value = parts
                # Remove quotes if present
                if value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                elif value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                
                # Break long value into multiple lines
                result_lines = [field_name, ';']
                if len(value) > 80:
                    broken_lines = self._break_long_line(value, 80)
                    result_lines.extend(broken_lines)
                else:
                    result_lines.append(value)
                result_lines.append(';')
                return result_lines, 1
            else:
                # Field with no value or malformed, preserve as-is
                return [original_line], 1
    
    def _should_use_multiline_format(self, field_name: str, value: str) -> bool:
        """Determine if a field should use multiline format based on length and content."""
        if not value:
            return False
        
        # Always use multiline if value contains newlines
        if '\n' in value:
            return True
        
        # Calculate total line length (field name + spacing + quoted value)
        needs_quotes = self._needs_quotes(value)
        formatted_value = f"'{value}'" if needs_quotes else value
        total_length = len(field_name) + 4 + len(formatted_value)  # 4 spaces for formatting
        
        return total_length > 80
