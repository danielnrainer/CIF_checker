# CIF Checker v2.0 - Modernized Crystallographic File Validator

A powerful, high-performance CIF (Crystallographic Information File) viewer and validator designed for crystallographers working with electron diffraction and other crystallographic methods.

## 🚀 Key Features

### **Performance & Intelligence**
- **⚡ Lazy-loading CIF dictionary** - 90%+ performance improvement with instant access to 1116+ field definitions
- **🧠 Intelligent method detection** - Automatically identifies electron diffraction, X-ray, neutron, and other crystallographic methods
- **🔍 Universal field support** - Recognizes all CIF field names including special characters and alternative forms

### **Modern GUI & Analysis**
- **💻 Intuitive PyQt6 interface** with syntax highlighting and smart validation
- **📊 Comprehensive analysis** - Method detection, field validation, and detailed reporting
- **🎨 Advanced syntax highlighting** - Real-time field recognition with proper pattern matching

### **Validation & Standards**
- **📋 CIF Core Dictionary 3.3.0** (2025) - Latest crystallographic standards
- **🔄 CIF1/CIF2 compatibility** - Automatic format detection and field normalization
- **⚠️ Smart error reporting** - Context-aware validation with helpful suggestions

## 🛠️ Installation

### Requirements
- Python 3.8+
- PyQt6>=6.4.0
- PyInstaller>=6.0.0 (for standalone executable)

### Quick Start
```bash
# Clone the repository
git clone https://github.com/danielnrainer/CIF_checker.git
cd CIF_checker

# Install dependencies
pip install -r requirements.txt

# Run the application
python src/main.py
```

### Standalone Executable
Create a standalone .exe file using PyInstaller:
```bash
pyinstaller CIF_checker.spec
```

## 📁 Project Structure

```
CIF_checker/
├── src/
│   ├── main.py                          # Application entry point
│   ├── gui/
│   │   └── main_window.py              # Main GUI interface
│   └── utils/
│       ├── cif_dictionary_manager.py   # Lazy-loading CIF dictionary
│       ├── cif_analyzer.py             # Comprehensive CIF analysis
│       └── CIF_field_parsing.py        # Legacy field parsing utilities
├── cif_core.dic                        # CIF Core Dictionary (28,871 lines)
├── requirements.txt                     # Python dependencies
└── CIF_checker.spec                    # PyInstaller configuration
```

## 🎯 Usage

1. **Open CIF file** - Use the file browser or drag & drop
2. **Automatic analysis** - Method detection and field validation happen instantly
3. **Review results** - Check missing fields, validation errors, and suggestions
4. **Syntax highlighting** - Navigate through your CIF with intelligent field highlighting

## 🔧 Advanced Features

### Method Detection
Automatically detects crystallographic methods:
- **Electron Diffraction** (3D ED, cRED, MicroED)
- **X-ray Diffraction** (Single crystal, powder)
- **Neutron Diffraction**
- **Synchrotron methods**

### Field Validation
- **Required fields** checking based on detected method
- **Field format validation** according to CIF standards
- **Cross-field consistency** checks
- **Deprecation warnings** for outdated fields

## 🏗️ Architecture

Built with modern Python practices:
- **Lazy loading** - Only loads dictionary fields when needed
- **Modular design** - Separate concerns for parsing, analysis, and GUI
- **Performance optimized** - Efficient regex patterns and caching
- **Extensible** - Easy to add new validation rules and field definitions

## 📊 Performance

- **Startup time**: <2 seconds (vs. 20+ seconds in v1.0)
- **Field lookup**: Instant (1116 fields indexed)
- **Memory usage**: ~50MB (vs. 200MB+ when fully loading dictionary)
- **Analysis speed**: Real-time validation of large CIF files

## 🤝 Contributing

This project is actively developed for the crystallographic community. Contributions welcome!

## 📄 License

See LICENSE file for details.

---

*CIF Checker v2.0 - Built for modern crystallography workflows*

