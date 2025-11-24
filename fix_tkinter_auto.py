"""
Automatic Tkinter/Tcl Fix Script for Python 3.14
This script attempts to fix missing Tcl/Tk files by downloading and installing them.
"""

import os
import sys
import urllib.request
import zipfile
import shutil
from pathlib import Path


def get_python_path():
    """Get the Python installation directory."""
    return Path(sys.executable).parent


def check_tkinter():
    """Check if Tkinter is working."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.destroy()
        return True
    except Exception as e:
        print(f"Tkinter check failed: {e}")
        return False


def download_tcl_tk():
    """Download Tcl/Tk files for Python 3.14."""
    print("Downloading Tcl/Tk files...")
    
    python_path = get_python_path()
    tcl_dir = python_path / "tcl"
    
    # Create tcl directory if it doesn't exist
    tcl_dir.mkdir(exist_ok=True)
    
    # URLs for Tcl/Tk 8.6 (compatible with Python 3.14)
    tcl_url = "https://github.com/python/cpython-bin-deps/archive/refs/heads/tcltk-8.6.13.zip"
    
    try:
        # Download
        zip_path = python_path / "tcltk.zip"
        print(f"Downloading from {tcl_url}...")
        urllib.request.urlretrieve(tcl_url, zip_path)
        
        # Extract
        print("Extracting files...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(python_path / "tcltk_temp")
        
        # Move files to correct location
        temp_dir = python_path / "tcltk_temp" / "cpython-bin-deps-tcltk-8.6.13"
        
        # Copy tcl and tk directories
        for item in ["tcl8.6", "tk8.6"]:
            src = temp_dir / item
            dst = tcl_dir / item
            if src.exists():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                print(f"Copied {item}")
        
        # Cleanup
        zip_path.unlink()
        shutil.rmtree(python_path / "tcltk_temp")
        
        print("[OK] Tcl/Tk files installed successfully!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to download/install Tcl/Tk: {e}")
        return False


def set_environment_variables():
    """Set TCL_LIBRARY and TK_LIBRARY environment variables."""
    python_path = get_python_path()
    tcl_dir = python_path / "tcl"
    
    tcl_lib = str(tcl_dir / "tcl8.6")
    tk_lib = str(tcl_dir / "tk8.6")
    
    print(f"\nSetting environment variables:")
    print(f"TCL_LIBRARY = {tcl_lib}")
    print(f"TK_LIBRARY = {tk_lib}")
    
    # Set for current session
    os.environ["TCL_LIBRARY"] = tcl_lib
    os.environ["TK_LIBRARY"] = tk_lib
    
    # Set permanently (Windows)
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "TCL_LIBRARY", 0, winreg.REG_SZ, tcl_lib)
            winreg.SetValueEx(key, "TK_LIBRARY", 0, winreg.REG_SZ, tk_lib)
            winreg.CloseKey(key)
            print("[OK] Environment variables set permanently")
        except Exception as e:
            print(f"[WARNING] Could not set permanent environment variables: {e}")
            print("  You may need to run this script as administrator")


def main():
    """Main function."""
    print("="*60)
    print("Tkinter/Tcl Fix Script for Python 3.14")
    print("="*60)
    print()
    
    # Check current status
    print("Checking Tkinter status...")
    if check_tkinter():
        print("[OK] Tkinter is already working!")
        return 0
    
    print("[ERROR] Tkinter is not working. Attempting to fix...\n")
    
    # Show Python path
    python_path = get_python_path()
    print(f"Python installation: {python_path}\n")
    
    # Attempt automatic fix
    print("Method 1: Downloading Tcl/Tk files...")
    if download_tcl_tk():
        set_environment_variables()
        
        print("\n" + "="*60)
        print("Fix attempt completed!")
        print("="*60)
        print("\nPlease:")
        print("1. Close this terminal")
        print("2. Open a NEW terminal")
        print("3. Run: python -m tkinter")
        print("\nIf a window appears, Tkinter is fixed!")
        return 0
    
    # If automatic fix failed, show manual instructions
    print("\n" + "="*60)
    print("Automatic fix failed. Please try manual installation:")
    print("="*60)
    print("\nOption 1: Reinstall Python 3.14")
    print("  1. Download from: https://www.python.org/downloads/")
    print("  2. During installation, check 'tcl/tk and IDLE'")
    print()
    print("Option 2: Use Python 3.12 (more stable)")
    print("  1. Download from: https://www.python.org/downloads/release/python-3120/")
    print("  2. Install and create virtual environment")
    print()
    print("See fix_tkinter.md for detailed instructions.")
    
    return 1


if __name__ == "__main__":
    sys.exit(main())
