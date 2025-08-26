# 3D Electron Diffraction Field Definitions Guide

## Overview
This guide explains how to edit the `field_definitions_3d_ed.json` file to customize field validation, suggestions, defaults, and requirements for 3D electron diffraction CIF files.

## File Location
`src/gui/field_definitions_3d_ed.json`

---

## File Structure

### 1. **Metadata Section**
```json
{
  "name": "3D Electron Diffraction (3D ED)",
  "description": "Comprehensive validation profile for 3D electron diffraction structure determination",
  "version": "2025.2",
  "cif_core_version": "3.3.0",
  "last_updated": "2025-08-22",
  "references": [
    "https://github.com/COMCIFS/cif_ed/blob/main/docs/recommendations.md",
    "CIF Core Dictionary 3.3.0 (2025)",
    "Manual field definitions from previous CIF_checker versions"
  ]
}
```
**Purpose**: Basic information about the validation profile.

---

### 2. **Method Detection** ⚡
```json
"method_detection": {
  "required_fields": ["_diffrn_radiation.probe"],
  "required_values": {
    "_diffrn_radiation.probe": ["electron"]
  },
  "indicator_fields": [
    "_diffrn_source.voltage",
    "_diffrn_detector.type", 
    "_diffrn_detector.make"
  ],
  "keywords": ["electron", "tem", "precession", "microed", "3d ed", "cred", "pedt", "nanocrystal"]
}
```

**How to Edit**:
- **`required_fields`**: Fields that MUST be present to trigger 3D ED validation
- **`required_values`**: Specific values that must match (case-insensitive)
- **`indicator_fields`**: Fields that suggest this is a 3D ED experiment
- **`keywords`**: Text patterns in field values that indicate 3D ED

---

### 3. **Required Fields** 📋
```json
"required_fields": {
  "essential": [
    "_diffrn_radiation.probe",
    "_diffrn_radiation_wavelength.value",
    "_diffrn_source.voltage"
  ],
  
  "highly_recommended": [
    "_diffrn_source.description",
    "_diffrn_source.make",
    "_exptl_crystal.colour"
  ],
  
  "method_specific": [
    "_diffrn_detector.area_resol_mean",
    "_diffrn_source.current",
    "_diffrn_measurement.specimen_support"
  ]
}
```

**How to Edit**:
- **`essential`**: Fields that are absolutely required for valid 3D ED
- **`highly_recommended`**: Important fields that should be present
- **`method_specific`**: Fields specific to certain 3D ED techniques
- **Add/Remove Fields**: Simply add or remove field names from these arrays

---

### 4. **Field Validation Rules** 🔍
```json
"field_validation": {
  "_diffrn_source.voltage": {
    "type": "numeric",
    "units": "kV",
    "typical_range": [80, 300],
    "common_values": [80, 120, 200, 300],
    "priority": "essential"
  },
  
  "_diffrn_ambient_environment": {
    "allowed_values": ["vacuum", "helium", "nitrogen", "air", "cryogenic"],
    "default": "vacuum",
    "priority": "standard"
  }
}
```

**Validation Properties**:
- **`type`**: "numeric", "text", "enumerated"
- **`units`**: Units for the field value
- **`typical_range`**: [min, max] for numeric fields
- **`common_values`**: Array of typical values
- **`allowed_values`**: Restricted list of acceptable values
- **`default`**: Default value to suggest
- **`priority`**: "critical", "essential", "recommended", "standard"
- **`format_requirements`**: Text description of required format
- **`constraints`**: Additional validation rules

**Adding New Validation**:
```json
"_your_field_name": {
  "type": "numeric",
  "units": "degrees",
  "typical_range": [0, 360],
  "default": "90",
  "priority": "recommended",
  "format_requirements": "numeric value between 0 and 360 degrees"
}
```

---

### 5. **Default Values and Suggestions** 💡

**To Add Default Values**:
```json
"field_validation": {
  "_your_field": {
    "default": "your_default_value",
    "description": "Description shown to user",
    "validation_rules": "Additional help text"
  }
}
```

**Examples**:
```json
"_diffrn_ambient_temperature": {
  "type": "numeric",
  "units": "K",
  "default": "293",
  "description": "Room temperature measurement",
  "typical_range": [100, 400]
},

"_diffrn_radiation.probe": {
  "required_value": "electron",
  "default": "electron",
  "description": "Must be 'electron' for electron diffraction"
}
```

---

### 6. **Method-Specific Requirements** 🎯
```json
"method_specific": {
  "3D_ED": {
    "requires_any": [
      "_diffrn_measurement.method_precession",
      "_diffrn.precession_semi_angle"
    ],
    "recommended": [
      "_diffrn_source.convergence_angle",
      "_exptl_crystal.mosaicity"
    ]
  },
  
  "precession": {
    "requires": [
      "_diffrn.precession_semi_angle",
      "_diffrn_measurement.method_precession"
    ]
  }
}
```

**How to Edit**:
- **`requires_any`**: At least one of these fields must be present
- **`requires`**: All of these fields must be present
- **`recommended`**: These fields should be present for this method

---

### 7. **Common Values Lists** 📚
```json
"common_detectors": [
  "Rigaku HyPix-ED",
  "Rigaku HyPix-Arc", 
  "ASI Timpix",
  "TVIPS XF-416"
],

"common_sources": [
  "electron gun",
  "LaB6",
  "tungsten", 
  "FEG"
]
```

**Purpose**: These arrays provide dropdown suggestions for users.

---

## How to Add New Field Definitions

### Step 1: Add to Required Fields
```json
"required_fields": {
  "essential": [
    "_your_new_field"
  ]
}
```

### Step 2: Add Validation Rules
```json
"field_validation": {
  "_your_new_field": {
    "type": "numeric",
    "units": "your_units",
    "default": "default_value",
    "description": "User-friendly description",
    "typical_range": [min, max],
    "priority": "essential"
  }
}
```

### Step 3: Add to Method-Specific (if applicable)
```json
"method_specific": {
  "your_method": {
    "recommended": [
      "_your_new_field"
    ]
  }
}
```

---

## Complete Example: Adding a New Field

Let's add `_diffrn_crystal.orientation`:

### 1. Add to Required Fields
```json
"required_fields": {
  "highly_recommended": [
    "_diffrn_crystal.orientation"
  ]
}
```

### 2. Add Validation
```json
"field_validation": {
  "_diffrn_crystal.orientation": {
    "type": "text",
    "allowed_values": ["random", "preferred", "single"],
    "default": "random",
    "description": "Crystal orientation relative to electron beam",
    "priority": "recommended",
    "format_requirements": "Must be one of: random, preferred, single"
  }
}
```

### 3. Add to Method-Specific
```json
"method_specific": {
  "3D_ED": {
    "recommended": [
      "_diffrn_crystal.orientation"
    ]
  }
}
```

---

## Testing Your Changes

1. **Save the JSON file**
2. **Restart the CIF Checker application**
3. **Run 3D ED validation** on a test file
4. **Check the field editing dialog** to see your new defaults and suggestions

---

## Field Priority Levels

- **`critical`**: Must be present and correct for valid 3D ED
- **`essential`**: Required for complete structure determination
- **`recommended`**: Should be present for best practices
- **`standard`**: Optional but useful information
- **`method_specific`**: Required only for specific techniques

---

## Validation Types

### Numeric Fields
```json
{
  "type": "numeric",
  "units": "kV",
  "typical_range": [80, 300],
  "default": "200"
}
```

### Enumerated Fields
```json
{
  "allowed_values": ["vacuum", "helium", "nitrogen"],
  "default": "vacuum"
}
```

### Text Fields
```json
{
  "type": "text",
  "format_requirements": "Free text description",
  "default": "Unknown"
}
```

---

## Best Practices

1. **Always include a default value** for user convenience
2. **Use clear, descriptive field descriptions**
3. **Set appropriate priority levels** to guide users
4. **Include typical ranges** for numeric fields
5. **Use standard units** consistently
6. **Test changes** with real CIF files
7. **Keep the JSON valid** - check syntax after editing

---

## Common Mistakes to Avoid

❌ **Invalid JSON syntax** (missing commas, quotes)  
❌ **Inconsistent field names** (mixing CIF1/CIF2 formats)  
❌ **Missing required properties** (type, priority)  
❌ **Unrealistic typical ranges**  
❌ **Conflicting validation rules**  

✅ **Valid JSON with proper syntax**  
✅ **Consistent CIF2 field naming**  
✅ **Complete field definitions**  
✅ **Realistic, tested ranges**  
✅ **Clear, non-conflicting rules**  

---

This guide provides everything needed to customize the 3D ED field definitions according to your specific requirements and validation needs.
