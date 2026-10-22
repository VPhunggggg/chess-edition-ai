# Chess Edition — Desktop Chess with Negamax AI

Game cờ vua chạy offline bằng Python và Pygame, hỗ trợ hai người chơi trên cùng máy hoặc đấu với AI ở ba mức độ khó. Giao diện có theme bàn cờ, hai bộ quân cờ, avatar, nhạc nền và lịch sử trận đấu.

## Tính năng

- Chế độ PvP, PvAI và chuỗi trận best-of-N.
- AI Negamax với alpha-beta pruning, iterative deepening, transposition table và quiescence search theo mức độ khó.
- Gợi ý nước đi, hoàn tác, tạm dừng, đầu hàng, đồng hồ và xem lại nước đi.
- Tài khoản cục bộ, bảng xếp hạng, lịch sử nước đi CSV và kết quả trận JSON.
- Giao diện Pygame có thể thay đổi kích thước cửa sổ và tùy chỉnh hình ảnh/âm thanh.

Tài liệu chi tiết của dự án gốc: [TINH_NANG_GAME.md](TINH_NANG_GAME.md).

## Chạy từ mã nguồn

Yêu cầu Python 3.11 trở lên. Trên Windows PowerShell:

```powershell
git clone https://github.com/VPhunggggg/chess-edition-ai.git
cd chess-edition-ai
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Trên Linux/macOS, dùng `python3 -m venv .venv`, kích hoạt môi trường bằng `source .venv/bin/activate`, sau đó chạy `python -m pip install -r requirements.txt` và `python main.py`. Cần Tkinter nếu dùng hộp thoại chọn file/tài khoản; tên gói hệ thống phụ thuộc bản phân phối.

Khởi chạy từ thư mục gốc của dự án để các đường dẫn tương đối đến `assets/` và `data/` hoạt động đúng. Cài đặt, tài khoản và lịch sử cá nhân được tạo trong `data/` khi sử dụng và được loại khỏi Git.

## Bản Windows

Tệp `ChessEdition.exe` đi kèm ZIP gốc được giữ nguyên tại [Windows release](https://github.com/VPhunggggg/chess-edition-ai/releases/tag/windows-build).

Tải tệp vào thư mục gốc của repo, cạnh `assets/` và `data/`, rồi chạy từ thư mục đó. Bản thực thi này chưa được build lại hoặc kiểm thử trong quá trình đăng repo; kiểm tra mã nguồn không xác nhận bản `.exe` tương ứng hoàn toàn với mã hiện tại.

Để tự build trên Windows, cài các thư viện ở trên rồi chạy:

```powershell
python -m pip install pyinstaller
python build_exe.py
```

Script build có sẵn tạo bản thực thi trong `dist/`. Thư mục `build/`, `dist/` và các gói trung gian được loại khỏi Git.

## Cấu trúc

```text
main.py                 Điểm khởi chạy và vòng lặp ứng dụng Pygame
core/                   Luật cờ, AI, tài khoản, cấu hình và lịch sử
scenes/                 Menu, thiết lập, ván đấu và kết quả
chess_app/ui/           Widget, theme và bố cục giao diện
assets/                 Hình ảnh, avatar, quân cờ và nhạc
data/                   Dữ liệu cục bộ, tạo trong quá trình sử dụng
build_exe.py            Script đóng gói Windows bằng PyInstaller
ChessEdition.spec       Cấu hình PyInstaller có sẵn
TINH_NANG_GAME.md        Tài liệu tính năng gốc
```

Các tệp `index.html`, `styles.css` và `menu.js` là bản minh họa menu web đi kèm; một số nút dùng thông báo mẫu. Ứng dụng chơi cờ đầy đủ được khởi chạy qua `main.py`.
