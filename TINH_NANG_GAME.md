# TÀI LIỆU TÍNH NĂNG GAME CỜ VUA

## 📋 MỤC LỤC
1. [Tổng quan](#tổng-quan)
2. [Chế độ chơi](#chế-độ-chơi)
3. [Hệ thống AI](#hệ-thống-ai)
4. [Giao diện người dùng](#giao-diện-người-dùng)
5. [Tùy chỉnh và Cài đặt](#tùy-chỉnh-và-cài-đặt)
6. [Tính năng trong game](#tính-năng-trong-game)
7. [Hệ thống người dùng](#hệ-thống-người-dùng)
8. [Lưu trữ và Lịch sử](#lưu-trữ-và-lịch-sử)
9. [Phím tắt](#phím-tắt)
10. [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)

---

## 🎮 TỔNG QUAN

**Chess New** là một game cờ vua đầy đủ tính năng được phát triển bằng Python và Pygame, hỗ trợ chơi người với người (PvP) và chơi với AI (PvAI). Game có giao diện hiện đại, hệ thống AI thông minh với nhiều mức độ khó, và nhiều tính năng tùy chỉnh.

---

## 🎯 CHẾ ĐỘ CHƠI

### 1. Chế độ PvP (Người với Người)
- Hai người chơi có thể chơi cùng nhau trên cùng một máy
- Hỗ trợ đổi bên giữa các ván (swap sides)
- Theo dõi điểm số riêng cho mỗi bên (White/Black)

### 2. Chế độ PvAI (Người với AI)
- Chơi với AI thông minh với 3 mức độ khó
- Có thể chọn bên đi trước (White/Black/Random)
- Hỗ trợ đổi bên giữa các ván để công bằng

### 3. Best-of-N Series
- Hỗ trợ chơi nhiều ván liên tiếp (Best-of-3, Best-of-5, Best-of-7, Best-of-9)
- Theo dõi tổng điểm thắng/thua
- Tính điểm hiệu quả (effective score) sau khi trừ penalty

---

## 🤖 HỆ THỐNG AI

### Mức độ khó AI

#### **Easy (Dễ)**
- Độ sâu tìm kiếm: 6 nước
- Thời gian suy nghĩ: 2000ms (2 giây)
- Tỷ lệ ngẫu nhiên: 10%
- Tỷ lệ sai lầm: 2%
- Sử dụng đánh giá vị trí, khả năng di chuyển, an toàn vua, cấu trúc tốt, kiểm soát trung tâm, phối hợp quân

#### **Medium (Trung bình)**
- Độ sâu tìm kiếm: 8 nước
- Thời gian suy nghĩ: 4000ms (4 giây)
- Tỷ lệ ngẫu nhiên: 0% (luôn chọn nước tốt nhất)
- Tỷ lệ sai lầm: 0%
- Sử dụng tất cả các tính năng đánh giá với trọng số cao hơn

#### **Hard (Khó)**
- Độ sâu tìm kiếm: 12 nước
- Thời gian suy nghĩ: 8000ms (8 giây)
- Tỷ lệ ngẫu nhiên: 0%
- Tỷ lệ sai lầm: 0%
- Sử dụng tất cả các tính năng đánh giá với trọng số tối đa

### Thuật toán AI

#### **Negamax với Alpha-Beta Pruning**
- Tối ưu hóa tìm kiếm với cắt tỉa alpha-beta
- Giảm đáng kể số lượng nước cần đánh giá

#### **Transposition Table (Bảng chuyển vị)**
- Lưu trữ các vị trí đã đánh giá để tái sử dụng
- Giới hạn 100,000 entries để tránh tràn bộ nhớ
- Tăng tốc độ tính toán đáng kể

#### **Killer Moves Heuristic**
- Ưu tiên các nước đi đã gây ra beta cutoff ở cùng độ sâu
- Cải thiện thứ tự nước đi để tăng hiệu quả cắt tỉa

#### **History Heuristic**
- Theo dõi các nước đi tốt trong quá khứ
- Sử dụng để sắp xếp thứ tự nước đi

#### **Quiescence Search (Tìm kiếm tĩnh)**
- Tiếp tục tìm kiếm trong các vị trí không ổn định (có thể bắt quân)
- Đảm bảo đánh giá chính xác hơn ở cuối cây tìm kiếm
- Chỉ sử dụng ở mức Medium và Hard

### Hàm đánh giá vị trí

#### **1. Material Evaluation (Đánh giá vật chất)**
- Giá trị quân cờ: Tốt (100), Mã (320), Tượng (330), Xe (500), Hậu (900), Vua (20000)

#### **2. Position Evaluation (Đánh giá vị trí)**
- Sử dụng Piece Square Tables (PST)
- Ưu tiên các quân ở vị trí trung tâm
- Phạt các quân ở vị trí biên

#### **3. Mobility Evaluation (Đánh giá khả năng di chuyển)**
- Đếm số nước đi hợp lệ
- Weighted mobility: nước đi từ quân có giá trị cao hơn được ưu tiên

#### **4. King Safety (An toàn vua)**
- Kiểm tra vua có bị chiếu không
- Đánh giá pawn shield (lá chắn tốt)
- Đếm số quân tấn công vua

#### **5. Pawn Structure (Cấu trúc tốt)**
- Phát hiện và phạt doubled pawns (tốt xếp chồng)
- Phát hiện và phạt isolated pawns (tốt cô lập)
- Thưởng passed pawns (tốt thông)

#### **6. Center Control (Kiểm soát trung tâm)**
- Đánh giá sự kiểm soát các ô trung tâm (e4, e5, d4, d5)
- Tính số quân tấn công các ô trung tâm

#### **7. Piece Coordination (Phối hợp quân)**
- Thưởng khi có cặp tượng khác màu (bishop pair)
- Đánh giá sự phối hợp giữa các quân

---

## 🎨 GIAO DIỆN NGƯỜI DÙNG

### Hệ thống Scene (Màn hình)

#### **1. Menu Scene (Màn hình Menu)**
- Màn hình chính với các tùy chọn:
  - Đăng nhập/Đăng ký
  - Bắt đầu game
  - Xem lịch sử
  - Cài đặt
  - Thoát

#### **2. Login Scene (Màn hình Đăng nhập)**
- Giao diện đăng nhập với background tùy chỉnh
- Hỗ trợ nhập tên người dùng và mật khẩu
- Hiển thị cursor nhấp nháy khi nhập
- Hỗ trợ Tab để chuyển giữa các trường
- Enter để đăng nhập, ESC để quay lại

#### **3. Register Scene (Màn hình Đăng ký)**
- Đăng ký tài khoản mới
- Xác thực mật khẩu
- Lưu trữ an toàn với hash

#### **4. Setup Scene (Màn hình Thiết lập)**
- Cấu hình trước khi bắt đầu game:
  - Tên người chơi
  - Giới tính (Male/Female/Other)
  - Avatar (từ thư mục assets/avatars)
  - Chế độ chơi (PvP/PvAI)
  - Bên đi trước (White/Black/Random)
  - Độ khó AI (Easy/Medium/Hard)
  - Best-of-N (3/5/7/9)
  - Đổi bên giữa các ván
  - Theme bàn cờ
  - Skin quân cờ
  - Nhạc menu và nhạc trong game
  - Kích thước bàn cờ
  - Giới hạn thời gian mỗi nước
  - Số lần Undo/Hint tối đa

#### **5. Match Scene (Màn hình Chơi game)**
- Giao diện chơi game chính:
  - Bàn cờ với highlight nước đi hợp lệ
  - Panel thông tin bên phải
  - Danh sách nước đi
  - Quân cờ đã bắt
  - Thông tin người chơi và avatar
  - Đồng hồ đếm ngược
  - Các nút điều khiển

#### **6. Game End Scene (Màn hình Kết thúc ván)**
- Hiển thị khi kết thúc một ván:
  - Ảnh thắng/thua
  - Nút Replay (chơi lại)
  - Nút Exit (thoát về menu)
  - Hỗ trợ phím tắt (R/Enter để replay, E/ESC để exit)

#### **7. Results Scene (Màn hình Kết quả)**
- Hiển thị kết quả Best-of-N series:
  - Tổng điểm thắng/thua
  - Điểm hiệu quả (sau khi trừ penalty)
  - Người thắng cuộc

### Hệ thống UI hiện đại

#### **Responsive Layout System**
- Tự động điều chỉnh theo kích thước cửa sổ
- Scale factor dựa trên độ phân giải
- Font size tự động điều chỉnh
- Layout cache để tối ưu hiệu suất

#### **UI Components**
- **Button**: Nút với hover effect, shadow, gradient
- **Panel**: Panel với background và border
- **Card**: Card component với shadow
- **Tooltip**: Tooltip hiển thị thông tin khi hover
- **Toast**: Thông báo popup tạm thời

#### **Theme System**
- Hỗ trợ nhiều theme:
  - `default_dark`: Theme tối mặc định
  - `default_light`: Theme sáng
  - Có thể mở rộng thêm theme mới

---

## ⚙️ TÙY CHỈNH VÀ CÀI ĐẶT

### Theme bàn cờ
- **Classic**: Theme cổ điển với màu be và nâu
- **High Contrast**: Theme độ tương phản cao

### Skin quân cờ
- **Classic**: Quân cờ cổ điển
- **Dark Fantasy**: Quân cờ phong cách dark fantasy
- Có thể thêm skin mới vào thư mục `assets/pieces/`

### Avatar
- Chọn avatar từ thư mục `assets/avatars/`
- Hỗ trợ nhiều định dạng ảnh
- Tự động scale để vừa với kích thước hiển thị

### Nhạc nền
- **Menu Music**: Nhạc nền cho menu (mặc định: ost.mp3)
- **Match Music**: Nhạc nền khi chơi game (mặc định: nhac.mp3)
- Tự động quét các file nhạc trong thư mục `assets/Music/` và `assets/Decorate/`
- Có thể chọn từ danh sách nhạc có sẵn
- Volume: 40% (0.4)

### Kích thước cửa sổ
- Mặc định: 1200x720
- Có thể thay đổi trong Setup Scene
- Hỗ trợ resize cửa sổ
- Giới hạn tối thiểu: 1024x768
- Tự động điều chỉnh kích thước bàn cờ

### Kích thước bàn cờ
- Mặc định: 640px
- Có thể zoom bằng Ctrl + +/- hoặc trong Setup Scene
- Giới hạn: 480px - 1024px
- Tự động tính toán lại kích thước cửa sổ

---

## 🎮 TÍNH NĂNG TRONG GAME

### 1. Undo (Hoàn tác)
- Mỗi người chơi có số lần Undo giới hạn (mặc định: 3)
- Theo dõi riêng cho mỗi bên (White/Black)
- Sử dụng Undo sẽ bị trừ điểm trong Best-of-N series
- Hiển thị số lần Undo còn lại

### 2. Hint (Gợi ý)
- Mỗi người chơi có số lần Hint giới hạn (mặc định: 3)
- Hiển thị nước đi tốt nhất được đề xuất
- Animation fade in/out cho hint
- Pulse animation cho nước đi tốt nhất
- Sử dụng Hint sẽ bị trừ điểm trong Best-of-N series
- Hiển thị số lần Hint còn lại

### 3. New Game (Ván mới)
- Bắt đầu ván mới trong cùng Best-of-N series
- Giữ nguyên cấu hình và điểm số
- Tự động đổi bên nếu bật swap sides

### 4. Pause (Tạm dừng)
- Tạm dừng game
- Có thể tiếp tục sau

### 5. Resign (Đầu hàng)
- Đầu hàng và kết thúc ván hiện tại
- Đối thủ thắng ván đó

### 6. Move Highlighting (Highlight nước đi)
- Highlight ô đã chọn
- Hiển thị các nước đi hợp lệ từ ô đã chọn
- Highlight nước đi cuối cùng
- Sử dụng marker image (a.png) để đánh dấu nước đi hợp lệ

### 7. Legal Move Validation (Kiểm tra nước đi hợp lệ)
- Chỉ cho phép nước đi hợp lệ
- Hiển thị thông báo nếu không phải lượt của bạn
- Tự động bỏ chọn nếu click vào ô không hợp lệ

### 8. Move List (Danh sách nước đi)
- Hiển thị tất cả nước đi trong ván
- Format: "1. e4 e5 2. Nf3 Nc6 ..."
- Scroll được nếu danh sách dài
- Click vào nước đi để xem lại (review mode)

### 9. Review Mode (Chế độ xem lại)
- Click vào nước đi trong danh sách để xem lại
- Hiển thị vị trí tại thời điểm đó
- Có thể quay lại chơi tiếp

### 10. Captured Pieces (Quân cờ đã bắt)
- Hiển thị các quân cờ đã bắt của mỗi bên
- Sắp xếp theo thứ tự bắt được
- Hiển thị bằng icon quân cờ

### 11. Game Over Detection (Phát hiện kết thúc game)
- Tự động phát hiện khi game kết thúc:
  - Checkmate (Chiếu hết)
  - Stalemate (Hòa do hết nước)
  - Insufficient material (Hòa do thiếu quân)
  - 50-move rule (Luật 50 nước)
  - Threefold repetition (Lặp lại 3 lần)
  - Timeout (Hết thời gian)

### 12. Timer (Đồng hồ đếm ngược)
- Giới hạn thời gian mỗi nước (mặc định: 30 giây)
- Hiển thị thời gian còn lại
- Cảnh báo khi sắp hết thời gian
- Tự động kết thúc nếu hết thời gian

### 13. Center Message (Thông báo trung tâm)
- Hiển thị thông báo ở giữa bàn cờ:
  - "It's not your turn"
  - "Invalid move"
  - Các thông báo khác
- Tự động ẩn sau vài giây

### 14. Toast Notifications (Thông báo popup)
- Hiển thị thông báo tạm thời:
  - "Undo used"
  - "Hint used"
  - "Game over"
  - Các thông báo khác
- Tự động biến mất sau vài giây

---

## 👤 HỆ THỐNG NGƯỜI DÙNG

### Đăng ký
- Tạo tài khoản mới với username và password
- Mật khẩu được hash an toàn
- Lưu trữ trong file `data/users.json`

### Đăng nhập
- Đăng nhập với username và password
- Lưu thông tin người dùng hiện tại
- Tự động đăng nhập lại khi khởi động game

### Quản lý tài khoản
- Lưu thông tin người chơi:
  - Tên
  - Giới tính
  - Avatar
  - Tài khoản đăng nhập
- Liên kết kết quả game với tài khoản để xếp hạng

### Xóa tài khoản
- Có script `clear_users.py` để xóa tất cả tài khoản
- Cẩn thận khi sử dụng!

---

## 💾 LƯU TRỮ VÀ LỊCH SỬ

### Lưu trữ cài đặt
- File: `data/settings.json`
- Lưu tất cả cài đặt:
  - Kích thước cửa sổ
  - Fullscreen mode
  - Kích thước bàn cờ
  - Theme
  - Skin quân cờ
  - Độ khó AI
  - Giới hạn thời gian
  - Số lần Undo/Hint
  - Người dùng hiện tại
  - Nhạc nền

### Lịch sử nước đi
- File: `data/match_history.csv`
- Ghi lại tất cả nước đi:
  - Set ID
  - Game index
  - Move index
  - Tên người chơi
  - Quân cờ
  - Ô đi từ/đến
  - FEN sau nước đi
  - Timestamp
  - Chế độ chơi
  - Độ khó AI
  - Bên đi trước
  - Lý do kết thúc

### Kết quả game
- File: `data/match_results.json`
- Lưu kết quả Best-of-N series:
  - Set ID
  - Chế độ chơi
  - Độ khó AI
  - Thông tin người chơi
  - Điểm thắng/thua
  - Penalty (Undo/Hint)
  - Người thắng cuộc
  - Thời gian kết thúc

### Async Writing
- Sử dụng background thread để ghi lịch sử
- Không làm gián đoạn gameplay
- Batch writing để tối ưu hiệu suất

---

## ⌨️ PHÍM TẮT

### Phím tắt toàn cục
- **F11** hoặc **Alt+Enter**: Toggle fullscreen
- **Ctrl + +/-**: Zoom in/out bàn cờ
- **F9**: Toggle telemetry overlay
- **F10**: Toggle telemetry logging
- **Ctrl + T**: Toggle theme (Classic/High Contrast)

### Phím tắt trong game
- **R** hoặc **Enter**: Replay (trong Game End Scene)
- **E** hoặc **ESC**: Exit (trong Game End Scene)
- **ESC**: Quay lại menu (trong các scene khác)

### Phím tắt nhập liệu
- **Tab**: Chuyển giữa các trường nhập
- **Enter**: Xác nhận (đăng nhập, bắt đầu game, etc.)
- **ESC**: Hủy/Quay lại
- **Backspace**: Xóa ký tự

---

## 📊 TELEMETRY (Đo lường hiệu suất)

### Frame Statistics
- FPS (Frames per second)
- Frame time (ms)
- Update time (ms)
- Render time (ms)
- Number of updated rects

### AI Statistics
- AI thinking time (ms)
- Search depth
- Nodes evaluated
- Transposition table hits

### Toggle
- **F9**: Bật/tắt overlay
- **F10**: Bật/tắt logging

---

## 🎵 ÂM THANH

### Nhạc nền
- Hỗ trợ file MP3
- Tự động phát lặp lại
- Volume: 40%
- Có thể tắt/bật trong cài đặt

### Hiệu ứng âm thanh
- (Có thể thêm trong tương lai)

---

## 🔧 YÊU CẦU HỆ THỐNG

### Python
- Python 3.11 trở lên

### Dependencies
- `pygame`: Thư viện đồ họa và âm thanh
- `python-chess`: Thư viện xử lý cờ vua

### Cài đặt
```bash
pip install pygame python-chess
```

### Chạy game
```bash
python main.py
```

### Build executable
- Sử dụng PyInstaller
- File spec: `ChessEdition.spec`
- Script build: `build_exe.bat` hoặc `build_exe.py`

---

## 📁 CẤU TRÚC THƯ MỤC

```
ChessNew/
├── assets/
│   ├── avatars/          # Avatar người chơi
│   ├── Decorate/         # Ảnh UI và background
│   ├── Music/            # File nhạc
│   └── pieces/           # Skin quân cờ
│       ├── classic/
│       └── dark fantasy/
├── chess_app/
│   └── ui/               # Hệ thống UI
├── core/                 # Core modules
│   ├── ai_difficulty.py  # Cấu hình AI
│   ├── assets.py         # Quản lý assets
│   ├── auth.py           # Xác thực người dùng
│   ├── chess_engine.py   # Engine cờ vua
│   ├── config.py         # Cấu hình
│   ├── history.py        # Lịch sử
│   ├── settings.py       # Cài đặt
│   ├── telemetry.py      # Đo lường hiệu suất
│   └── ui_theme.py       # Theme UI
├── data/                 # Dữ liệu lưu trữ
│   ├── match_history.csv
│   ├── match_results.json
│   ├── settings.json
│   └── users.json
├── scenes/               # Các màn hình
│   ├── game_end_scene.py
│   ├── match_scene.py
│   ├── menu_scene.py
│   ├── results_scene.py
│   └── setup_scene.py
└── main.py              # Entry point
```

---

## 🎯 TÍNH NĂNG NỔI BẬT

1. **AI thông minh** với 3 mức độ khó và nhiều kỹ thuật tối ưu
2. **Giao diện hiện đại** với responsive layout và theme system
3. **Best-of-N series** với theo dõi điểm số chi tiết
4. **Hệ thống Undo/Hint** với giới hạn và penalty
5. **Lưu trữ đầy đủ** lịch sử nước đi và kết quả game
6. **Tùy chỉnh cao** với nhiều theme, skin, và cài đặt
7. **Hỗ trợ PvP và PvAI** với nhiều tùy chọn
8. **Telemetry system** để đo lường và tối ưu hiệu suất
9. **Hệ thống người dùng** với đăng ký/đăng nhập
10. **Nhạc nền** với nhiều lựa chọn

---

## 📝 GHI CHÚ

- Game chạy offline, không cần kết nối internet
- Hỗ trợ Windows, macOS, Linux
- Thiếu ảnh sẽ tự động fallback về placeholder
- Tất cả cài đặt được lưu tự động
- Lịch sử được ghi bất đồng bộ để không làm gián đoạn gameplay

