"""
Script để xóa tất cả dữ liệu tài khoản và người chơi đã lưu.
Chạy: python clear_users.py
"""

import sys
import io
import os
import json

# Set UTF-8 encoding for output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from core.auth import clear_all_users

def clear_match_results():
    """Xóa tất cả kết quả trận đấu."""
    results_file = os.path.join(".", "data", "match_results.json")
    try:
        os.makedirs(os.path.dirname(results_file), exist_ok=True)
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump([], f)
        return True
    except Exception:
        return False

def clear_match_history():
    """Xóa tất cả lịch sử các nước đi."""
    history_file = os.path.join(".", "data", "match_history.csv")
    try:
        os.makedirs(os.path.dirname(history_file), exist_ok=True)
        # Giữ lại header
        with open(history_file, "w", encoding="utf-8") as f:
            f.write("set_id,game_index,move_index,player_name,piece,from,to,fen_after,timestamp\n")
        return True
    except Exception:
        return False

if __name__ == "__main__":
    print("Đang xóa tất cả dữ liệu tài khoản và người chơi...")
    
    success_count = 0
    total_count = 3
    
    # Xóa tài khoản
    if clear_all_users():
        print("✓ Đã xóa thành công tất cả tài khoản đã đăng ký!")
        success_count += 1
    else:
        print("✗ Có lỗi xảy ra khi xóa dữ liệu tài khoản.")
    
    # Xóa kết quả trận đấu
    if clear_match_results():
        print("✓ Đã xóa thành công tất cả kết quả trận đấu!")
        success_count += 1
    else:
        print("✗ Có lỗi xảy ra khi xóa kết quả trận đấu.")
    
    # Xóa lịch sử các nước đi
    if clear_match_history():
        print("✓ Đã xóa thành công tất cả lịch sử các nước đi!")
        success_count += 1
    else:
        print("✗ Có lỗi xảy ra khi xóa lịch sử các nước đi.")
    
    print(f"\n{'='*50}")
    print(f"Hoàn thành: {success_count}/{total_count} file đã được xóa thành công!")
    print(f"{'='*50}")

