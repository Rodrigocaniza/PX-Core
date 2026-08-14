from pathlib import Path
import sys

python_root = Path(sys.base_prefix)
datas = [
    (str(python_root / "tcl" / "tcl8.6"), "_tcl_data"),
    (str(python_root / "tcl" / "tk8.6"), "_tk_data"),
]
binaries = [
    (str(python_root / "DLLs" / "_tkinter.pyd"), "."),
    (str(python_root / "DLLs" / "tcl86t.dll"), "."),
    (str(python_root / "DLLs" / "tk86t.dll"), "."),
]
