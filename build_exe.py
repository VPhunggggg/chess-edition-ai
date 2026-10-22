"""
Script để build file .exe cho game Chess
Chạy: python build_exe.py
"""

import os
import sys
import io
import subprocess

# Set UTF-8 encoding for output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    print("=" * 60)
    print("Building Chess Game Executable")
    print("=" * 60)
    
    # Kiểm tra PyInstaller
    try:
        import PyInstaller
        print("✓ PyInstaller da duoc cai dat")
    except ImportError:
        print("✗ PyInstaller chua duoc cai dat")
        print("Dang cai dat PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✓ Da cai dat PyInstaller")
    
    # Tên file output
    app_name = "ChessEdition"
    
    # Xóa file exe cũ nếu có
    old_exe_paths = [
        os.path.join("dist", f"{app_name}.exe"),
        f"{app_name}.exe",  # Trong thư mục hiện tại
    ]
    for old_exe in old_exe_paths:
        if os.path.exists(old_exe):
            try:
                os.remove(old_exe)
                print(f"✓ Da xoa file exe cu: {old_exe}")
            except Exception as e:
                print(f"⚠ Khong the xoa file exe cu {old_exe}: {e}")
    
    # Đường dẫn đến icon
    icon_path = os.path.join("assets", "Decorate", "icongame.ico")
    if not os.path.exists(icon_path):
        icon_path = None
        print("⚠ Khong tim thay file icon, se build khong co icon")
    else:
        print(f"✓ Tim thay icon: {icon_path}")
    
    # Lệnh PyInstaller
    cmd = [
        "pyinstaller",
        "--name", app_name,
        "--onefile",  # Tạo file .exe duy nhất
        "--windowed",  # Không hiện console window
    ]
    
    # Thêm icon nếu có
    if icon_path:
        cmd.extend(["--icon", icon_path])
    else:
        cmd.append("--icon=NONE")
    
    # Thêm các tham số khác
    cmd.extend([
        "--add-data", "assets;assets",  # Bao gồm thư mục assets
        "--add-data", "data;data",  # Bao gồm thư mục data
        "--hidden-import", "pygame",
        "--hidden-import", "chess",
        "--hidden-import", "tkinter",
        "--hidden-import", "core",
        "--hidden-import", "scenes",
        "--hidden-import", "chess_app",
        "--collect-all", "pygame",
        "main.py"
    ])
    
    print("\nDang build file .exe...")
    print("Lenh:", " ".join(cmd))
    print("\n" + "=" * 60)
    
    try:
        subprocess.check_call(cmd)
        print("\n" + "=" * 60)
        print("✓ Build thanh cong!")
        print(f"File .exe duoc tao tai: dist\\{app_name}.exe")
        print(f"Hoac: {app_name}.exe trong thu muc hien tai")
        print("=" * 60)
    except subprocess.CalledProcessError as e:
        print("\n" + "=" * 60)
        print("✗ Build that bai!")
        print(f"Loi: {e}")
        print("=" * 60)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

