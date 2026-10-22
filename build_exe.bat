@echo off
chcp 65001 >nul
echo ============================================================
echo Building Chess Game Executable
echo ============================================================
echo.

REM Kiểm tra Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ✗ Python chưa được cài đặt!
    pause
    exit /b 1
)

echo ✓ Python đã được cài đặt
echo.

REM Cài đặt PyInstaller nếu chưa có
python -m pip install pyinstaller

echo.
echo Đang build file .exe...
echo.

REM Kiểm tra icon
if exist "assets\Decorate\icongame.ico" (
    echo ✓ Tim thay icon: assets\Decorate\icongame.ico
    pyinstaller --name ChessEdition --onefile --windowed --icon "assets\Decorate\icongame.ico" --add-data "assets;assets" --add-data "data;data" --hidden-import pygame --hidden-import chess --hidden-import tkinter --hidden-import core --hidden-import scenes --hidden-import chess_app --collect-all pygame main.py
) else (
    echo ⚠ Khong tim thay file icon, se build khong co icon
    pyinstaller --name ChessEdition --onefile --windowed --add-data "assets;assets" --add-data "data;data" --hidden-import pygame --hidden-import chess --hidden-import tkinter --hidden-import core --hidden-import scenes --hidden-import chess_app --collect-all pygame main.py
)

if errorlevel 1 (
    echo.
    echo ✗ Build thất bại!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo ✓ Build thành công!
echo File .exe được tạo tại: dist\ChessEdition.exe
echo ============================================================
pause

