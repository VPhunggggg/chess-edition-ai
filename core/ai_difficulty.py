"""
AI难度配置和评估函数
支持3个难度级别：Easy, Medium, Hard
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple
import chess


# 棋子基础价值
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}


@dataclass
class DifficultyConfig:
    """AI难度配置"""
    name: str
    search_depth: int
    randomness: float  # 0.0-1.0，从最佳移动中随机选择的概率
    think_time_ms: int  # 思考时间（毫秒）
    blunder_chance: float  # 0.0-1.0，选择次优移动的概率
    use_position_eval: bool
    use_mobility_eval: bool
    use_king_safety: bool
    use_pawn_structure: bool
    use_center_control: bool
    use_piece_coordination: bool
    evaluation_weights: Dict[str, float]


# 难度配置 - Tối ưu hóa để tăng độ khó AI
AI_DIFFICULTY_CONFIGS: Dict[str, DifficultyConfig] = {
    "easy": DifficultyConfig(
        name="Easy",
        search_depth=6,  # Tăng từ 5 lên 6 để AI suy nghĩ sâu hơn
        randomness=0.10,  # Giảm từ 15% xuống 10% để ít random hơn
        think_time_ms=2000,  # Tăng từ 1500 lên 2000ms để có thời gian suy nghĩ
        blunder_chance=0.02,  # Giảm từ 3% xuống 2% để ít sai lầm hơn
        use_position_eval=True,
        use_mobility_eval=True,
        use_king_safety=True,  # Bật king safety cho Easy
        use_pawn_structure=True,  # Bật pawn structure cho Easy
        use_center_control=True,  # Bật center control cho Easy
        use_piece_coordination=True,  # Bật coordination cho Easy
        evaluation_weights={
            "material": 1.0,
            "position": 0.6,  # Tăng từ 0.5 lên 0.6
            "mobility": 0.4,  # Tăng từ 0.3 lên 0.4
            "king_safety": 0.4,  # Tăng từ 0.3 lên 0.4
            "pawn_structure": 0.3,  # Thêm pawn structure
            "center_control": 0.3,  # Tăng từ 0.2 lên 0.3
            "coordination": 0.2,  # Thêm coordination
        }
    ),
    "medium": DifficultyConfig(
        name="Medium",
        search_depth=8,  # Tăng từ 7 lên 8 để suy nghĩ sâu hơn
        randomness=0.0,  # Giảm từ 1% xuống 0% để luôn chọn nước tốt nhất
        think_time_ms=4000,  # Tăng từ 3500 lên 4000ms
        blunder_chance=0.0,
        use_position_eval=True,
        use_mobility_eval=True,
        use_king_safety=True,
        use_pawn_structure=True,
        use_center_control=True,
        use_piece_coordination=True,
        evaluation_weights={
            "material": 1.0,
            "position": 0.9,  # Tăng từ 0.8 lên 0.9
            "mobility": 0.7,  # Tăng từ 0.6 lên 0.7
            "king_safety": 0.8,  # Tăng từ 0.7 lên 0.8
            "pawn_structure": 0.7,  # Tăng từ 0.6 lên 0.7
            "center_control": 0.6,  # Tăng từ 0.5 lên 0.6
            "coordination": 0.45,  # Tăng từ 0.35 lên 0.45
        }
    ),
    "hard": DifficultyConfig(
        name="Hard",
        search_depth=12,  # Tăng từ 10 lên 12 để suy nghĩ rất sâu
        randomness=0.0,  # Luôn chọn nước tốt nhất
        think_time_ms=8000,  # Tăng từ 6000 lên 8000ms để có thời gian suy nghĩ sâu
        blunder_chance=0.0,
        use_position_eval=True,
        use_mobility_eval=True,
        use_king_safety=True,
        use_pawn_structure=True,
        use_center_control=True,
        use_piece_coordination=True,
        evaluation_weights={
            "material": 1.0,
            "position": 1.2,  # Tăng từ 1.0 lên 1.2 - vượt tối đa
            "mobility": 0.9,  # Tăng từ 0.8 lên 0.9
            "king_safety": 1.0,  # Tăng từ 0.9 lên 1.0 - tối đa
            "pawn_structure": 0.8,  # Tăng từ 0.7 lên 0.8
            "center_control": 0.7,  # Tăng từ 0.6 lên 0.7
            "coordination": 0.6,  # Tăng từ 0.5 lên 0.6
        }
    ),
}


# 棋子位置表（Piece Square Tables）
# 中心位置给予奖励，边缘位置给予惩罚

KNIGHT_TABLE = [
    [-50, -40, -30, -30, -30, -30, -40, -50],
    [-40, -20,   0,   0,   0,   0, -20, -40],
    [-30,   0,  10,  15,  15,  10,   0, -30],
    [-30,   5,  15,  20,  20,  15,   5, -30],
    [-30,   0,  15,  20,  20,  15,   0, -30],
    [-30,   5,  10,  15,  15,  10,   5, -30],
    [-40, -20,   0,   5,   5,   0, -20, -40],
    [-50, -40, -30, -30, -30, -30, -40, -50],
]

BISHOP_TABLE = [
    [-20, -10, -10, -10, -10, -10, -10, -20],
    [-10,   0,   0,   0,   0,   0,   0, -10],
    [-10,   0,   5,  10,  10,   5,   0, -10],
    [-10,   5,   5,  10,  10,   5,   5, -10],
    [-10,   0,  10,  10,  10,  10,   0, -10],
    [-10,  10,  10,  10,  10,  10,  10, -10],
    [-10,   5,   0,   0,   0,   0,   5, -10],
    [-20, -10, -10, -10, -10, -10, -10, -20],
]

ROOK_TABLE = [
    [0,  0,  0,  0,  0,  0,  0,  0],
    [5, 10, 10, 10, 10, 10, 10,  5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [0,  0,  0,  5,  5,  0,  0,  0],
]

QUEEN_TABLE = [
    [-20, -10, -10, -5, -5, -10, -10, -20],
    [-10,   0,   0,  0,  0,   0,   0, -10],
    [-10,   0,   5,  5,  5,   5,   0, -10],
    [-5,   0,   5,  5,  5,   5,   0,  -5],
    [0,   0,   5,  5,  5,   5,   0,   0],
    [-10,   5,   5,  5,  5,   5,   5, -10],
    [-10,   0,   5,  0,  0,   0,   0, -10],
    [-20, -10, -10, -5, -5, -10, -10, -20],
]

PAWN_TABLE = [
    [0,  0,  0,  0,  0,  0,  0,  0],
    [50, 50, 50, 50, 50, 50, 50, 50],
    [10, 10, 20, 30, 30, 20, 10, 10],
    [5,  5, 10, 25, 25, 10,  5,  5],
    [0,  0,  0, 20, 20,  0,  0,  0],
    [5, -5, -10,  0,  0, -10, -5,  5],
    [5, 10, 10, -20, -20, 10, 10,  5],
    [0,  0,  0,  0,  0,  0,  0,  0],
]


def get_piece_square_value(piece: chess.Piece, square: int) -> int:
    """获取棋子在特定位置的价值"""
    file = chess.square_file(square)
    rank = chess.square_rank(square)
    
    # 对于黑方，翻转rank
    if not piece.color:
        rank = 7 - rank
    
    if piece.piece_type == chess.KNIGHT:
        return KNIGHT_TABLE[rank][file]
    elif piece.piece_type == chess.BISHOP:
        return BISHOP_TABLE[rank][file]
    elif piece.piece_type == chess.ROOK:
        return ROOK_TABLE[rank][file]
    elif piece.piece_type == chess.QUEEN:
        return QUEEN_TABLE[rank][file]
    elif piece.piece_type == chess.PAWN:
        return PAWN_TABLE[rank][file]
    return 0


def evaluate_material(board: chess.Board) -> int:
    """评估材料价值"""
    score = 0
    for piece_type, value in PIECE_VALUES.items():
        score += len(board.pieces(piece_type, True)) * value
        score -= len(board.pieces(piece_type, False)) * value
    return score


def evaluate_position(board: chess.Board) -> int:
    """评估棋子位置价值"""
    score = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            value = get_piece_square_value(piece, square)
            if piece.color:
                score += value
            else:
                score -= value
    return score


def evaluate_mobility(board: chess.Board) -> int:
    """评估移动性（可用移动数量）- Tối ưu với weighted mobility"""
    current_turn = board.turn
    
    # Tính mobility cho cả hai bên
    board.turn = True
    white_moves = len(list(board.legal_moves))
    board.turn = False
    black_moves = len(list(board.legal_moves))
    
    # Restore turn
    board.turn = current_turn
    
    # Weighted mobility: moves từ quân có giá trị cao hơn
    white_weighted = 0
    black_weighted = 0
    
    board.turn = True
    for move in board.legal_moves:
        piece = board.piece_at(move.from_square)
        if piece:
            white_weighted += PIECE_VALUES.get(piece.piece_type, 0) // 100
    board.turn = False
    for move in board.legal_moves:
        piece = board.piece_at(move.from_square)
        if piece:
            black_weighted += PIECE_VALUES.get(piece.piece_type, 0) // 100
    
    board.turn = current_turn
    
    # Kết hợp raw mobility và weighted mobility
    raw_diff = (white_moves - black_moves) * 5
    weighted_diff = (white_weighted - black_weighted) * 2
    
    return raw_diff + weighted_diff


def evaluate_king_safety(board: chess.Board) -> int:
    """评估王的安全性 - Cải thiện với pawn shield và attack evaluation"""
    score = 0
    current_turn = board.turn
    
    # 检查王是否被将军
    board.turn = True
    if board.is_check():
        score -= 50  # 白方被将军
    board.turn = False
    if board.is_check():
        score += 50  # 黑方被将军
    
    board.turn = current_turn
    
    # 检查王周围的安全
    white_king = board.king(True)
    black_king = board.king(False)
    
    if white_king is not None:
        king_file = chess.square_file(white_king)
        king_rank = chess.square_rank(white_king)
        
        # Pawn shield: pawns ở phía trước vua
        protection = 0
        pawn_shield = 0
        for df in [-1, 0, 1]:
            for dr in [1, 2]:  # Phía trước vua (rank cao hơn)
                f = king_file + df
                r = king_rank + dr
                if 0 <= f < 8 and 0 <= r < 8:
                    sq = chess.square(f, r)
                    piece = board.piece_at(sq)
                    if piece and piece.color:
                        if piece.piece_type == chess.PAWN:
                            pawn_shield += 1
                        protection += 1
        
        # Đếm số quân tấn công vua
        attackers = len(board.attackers(False, white_king))
        score += protection * 5 + pawn_shield * 10 - attackers * 15
    
    if black_king is not None:
        king_file = chess.square_file(black_king)
        king_rank = chess.square_rank(black_king)
        
        protection = 0
        pawn_shield = 0
        for df in [-1, 0, 1]:
            for dr in [-1, -2]:  # Phía trước vua (rank thấp hơn)
                f = king_file + df
                r = king_rank + dr
                if 0 <= f < 8 and 0 <= r < 8:
                    sq = chess.square(f, r)
                    piece = board.piece_at(sq)
                    if piece and not piece.color:
                        if piece.piece_type == chess.PAWN:
                            pawn_shield += 1
                        protection += 1
        
        attackers = len(board.attackers(True, black_king))
        score -= (protection * 5 + pawn_shield * 10 - attackers * 15)
    
    return score


def evaluate_pawn_structure(board: chess.Board) -> int:
    """评估兵结构"""
    score = 0
    
    # 检查叠兵（doubled pawns）
    for file in range(8):
        white_pawns = len(board.pieces(chess.PAWN, True) & chess.BB_FILES[file])
        black_pawns = len(board.pieces(chess.PAWN, False) & chess.BB_FILES[file])
        
        if white_pawns > 1:
            score -= 20 * (white_pawns - 1)  # 叠兵惩罚
        if black_pawns > 1:
            score += 20 * (black_pawns - 1)
    
    # 检查孤兵（isolated pawns）
    for file in range(8):
        white_pawns = board.pieces(chess.PAWN, True) & chess.BB_FILES[file]
        black_pawns = board.pieces(chess.PAWN, False) & chess.BB_FILES[file]
        
        # 检查相邻列是否有兵
        has_adjacent_white = False
        has_adjacent_black = False
        for adj_file in [file - 1, file + 1]:
            if 0 <= adj_file < 8:
                if board.pieces(chess.PAWN, True) & chess.BB_FILES[adj_file]:
                    has_adjacent_white = True
                if board.pieces(chess.PAWN, False) & chess.BB_FILES[adj_file]:
                    has_adjacent_black = True
        
        if white_pawns and not has_adjacent_white:
            score -= 15  # 孤兵惩罚
        if black_pawns and not has_adjacent_black:
            score += 15
    
    # 检查通路兵（passed pawns）
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.piece_type == chess.PAWN:
            file = chess.square_file(square)
            rank = chess.square_rank(square)
            
            # 检查前方是否有敌方兵
            is_passed = True
            for r in range(rank + 1, 8) if piece.color else range(rank - 1, -1, -1):
                for f in [file - 1, file, file + 1]:
                    if 0 <= f < 8:
                        sq = chess.square(f, r)
                        opp_pawn = board.piece_at(sq)
                        if opp_pawn and opp_pawn.piece_type == chess.PAWN and opp_pawn.color != piece.color:
                            is_passed = False
                            break
                if not is_passed:
                    break
            
            if is_passed:
                # 通路兵奖励，越靠近底线奖励越大
                bonus = (7 - rank) * 20 if piece.color else rank * 20
                if piece.color:
                    score += bonus
                else:
                    score -= bonus
    
    return score


def evaluate_center_control(board: chess.Board) -> int:
    """评估中心控制"""
    score = 0
    center_squares = [chess.E4, chess.E5, chess.D4, chess.D5]
    
    for square in center_squares:
        piece = board.piece_at(square)
        if piece:
            if piece.color:
                score += 10
            else:
                score -= 10
        
        # 检查是否被攻击
        attackers_white = len(board.attackers(True, square))
        attackers_black = len(board.attackers(False, square))
        score += (attackers_white - attackers_black) * 5
    
    return score


def evaluate_piece_coordination(board: chess.Board) -> int:
    """评估棋子协调性"""
    score = 0
    
    # 检查双象
    white_bishops = board.pieces(chess.BISHOP, True)
    black_bishops = board.pieces(chess.BISHOP, False)
    
    if len(white_bishops) == 2:
        # 检查是否是不同颜色的象
        bishop_squares = list(white_bishops)
        if len(bishop_squares) == 2:
            sq1_color = (chess.square_file(bishop_squares[0]) + chess.square_rank(bishop_squares[0])) % 2
            sq2_color = (chess.square_file(bishop_squares[1]) + chess.square_rank(bishop_squares[1])) % 2
            if sq1_color != sq2_color:
                score += 30  # 双象优势
    
    if len(black_bishops) == 2:
        bishop_squares = list(black_bishops)
        if len(bishop_squares) == 2:
            sq1_color = (chess.square_file(bishop_squares[0]) + chess.square_rank(bishop_squares[0])) % 2
            sq2_color = (chess.square_file(bishop_squares[1]) + chess.square_rank(bishop_squares[1])) % 2
            if sq1_color != sq2_color:
                score -= 30
    
    return score


def evaluate_position_advanced(board: chess.Board, difficulty: str) -> int:
    """根据难度级别评估位置"""
    config = AI_DIFFICULTY_CONFIGS.get(difficulty, AI_DIFFICULTY_CONFIGS["medium"])
    weights = config.evaluation_weights
    
    score = 0
    
    # 材料评估（总是使用）
    material = evaluate_material(board)
    score += material * weights.get("material", 1.0)
    
    # 位置评估
    if config.use_position_eval and weights.get("position", 0) > 0:
        position = evaluate_position(board)
        score += position * weights.get("position", 0)
    
    # 移动性评估
    if config.use_mobility_eval and weights.get("mobility", 0) > 0:
        mobility = evaluate_mobility(board)
        score += mobility * weights.get("mobility", 0)
    
    # 王安全评估
    if config.use_king_safety and weights.get("king_safety", 0) > 0:
        king_safety = evaluate_king_safety(board)
        score += king_safety * weights.get("king_safety", 0)
    
    # 兵结构评估
    if config.use_pawn_structure and weights.get("pawn_structure", 0) > 0:
        pawn_structure = evaluate_pawn_structure(board)
        score += pawn_structure * weights.get("pawn_structure", 0)
    
    # 中心控制评估
    if config.use_center_control and weights.get("center_control", 0) > 0:
        center_control = evaluate_center_control(board)
        score += center_control * weights.get("center_control", 0)
    
    # 棋子协调性评估
    if config.use_piece_coordination and weights.get("coordination", 0) > 0:
        coordination = evaluate_piece_coordination(board)
        score += coordination * weights.get("coordination", 0)
    
    # 根据当前回合调整分数
    return score if board.turn else -score

