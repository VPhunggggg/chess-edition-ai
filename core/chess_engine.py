from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
import time

import chess
import random

from core.ai_difficulty import (
    AI_DIFFICULTY_CONFIGS,
    evaluate_position_advanced,
    PIECE_VALUES,
)


@dataclass
class EngineConfig:
    hint_depth: int = 2
    max_think_time_s: float = 5.0
    randomness: float = 0.0  # 0..1 probability to inject random choice among top moves
    quiescence: bool = False
    difficulty: str = "medium"  # "easy" | "medium" | "hard"


# Transposition table entry
@dataclass
class TTEntry:
    score: int
    depth: int
    flag: str  # "exact", "lower", "upper"
    move: Optional[chess.Move] = None


class ChessEngine:
    """Wrapper around python-chess providing legal moves and a simple negamax AI."""

    def __init__(self, engine_config: EngineConfig) -> None:
        self.board = chess.Board()
        self.cfg = engine_config
        # Killer moves: moves that caused beta cutoffs at same depth
        self._killer_moves: Dict[int, List[Optional[chess.Move]]] = {}  # depth -> [killer1, killer2]
        # History heuristic: track good moves
        self._history: Dict[Tuple[int, int], int] = {}  # (from_sq, to_sq) -> score
        # Transposition table: cache evaluated positions
        self._transposition_table: Dict[str, TTEntry] = {}
        self._tt_hits = 0
        self._tt_size_limit = 100000  # Giới hạn kích thước TT để tránh memory overflow
        # Enable quiescence for medium and hard
        if engine_config.difficulty in ["medium", "hard"]:
            self.cfg.quiescence = True

    def reset(self) -> None:
        self.board = chess.Board()
        # Clear transposition table on reset
        self._transposition_table.clear()
        self._tt_hits = 0

    def get_legal_moves(self) -> List[chess.Move]:
        return list(self.board.legal_moves)

    def is_game_over(self) -> bool:
        return self.board.is_game_over(claim_draw=True)

    def result(self) -> str:
        return self.board.result(claim_draw=True)

    def push_move(self, move: chess.Move) -> None:
        self.board.push(move)

    def pop_move(self) -> Optional[chess.Move]:
        if self.board.move_stack:
            return self.board.pop()
        return None

    def fen(self) -> str:
        return self.board.fen()

    def san(self, move: chess.Move) -> str:
        return self.board.san(move)

    def parse_uci(self, uci: str) -> chess.Move:
        return chess.Move.from_uci(uci)

    def _get_scored_moves(self, max_depth: Optional[int] = None, max_time: Optional[float] = None) -> List[Tuple[int, chess.Move]]:
        """获取所有合法移动的评分（内部方法，用于优化）"""
        difficulty_config = AI_DIFFICULTY_CONFIGS.get(self.cfg.difficulty, AI_DIFFICULTY_CONFIGS["medium"])
        depth = max_depth if max_depth is not None else difficulty_config.search_depth
        start = time.time()
        if max_time is None:
            max_time = difficulty_config.think_time_ms / 1000.0  # 转换为秒

        scored: List[Tuple[int, chess.Move]] = []
        
        # Tối ưu: move ordering trước khi tính toán - captures trước
        legal_moves = list(self.board.legal_moves)
        # Sắp xếp: captures trước để alpha-beta pruning hiệu quả hơn
        legal_moves.sort(key=lambda m: 1 if self.board.is_capture(m) else 0, reverse=True)

        for move in legal_moves:
            if time.time() - start > max_time:
                break
            self.board.push(move)
            score = -self._negamax(depth - 1, -10**9, 10**9, start, max_time)
            self.board.pop()
            scored.append((score, move))

        if not scored:
            return []

        # Move ordering - 按分数排序
        scored.sort(reverse=True, key=lambda sm: sm[0])
        return scored

    def best_move(self, max_depth: Optional[int] = None) -> Optional[chess.Move]:
        """获取最佳移动，使用iterative deepening để tối ưu thời gian"""
        difficulty_config = AI_DIFFICULTY_CONFIGS.get(self.cfg.difficulty, AI_DIFFICULTY_CONFIGS["medium"])
        target_depth = max_depth if max_depth is not None else difficulty_config.search_depth
        max_time = difficulty_config.think_time_ms / 1000.0
        start_time = time.time()
        
        # Reset killer moves và history cho mỗi lần tính toán mới
        self._killer_moves.clear()
        self._history.clear()
        # Giữ lại transposition table để tận dụng cache giữa các lần tính toán
        
        best_move_so_far: Optional[chess.Move] = None
        best_score_so_far = -10**9
        
        # Iterative deepening: tăng dần depth để tận dụng thời gian
        for current_depth in range(1, target_depth + 1):
            elapsed = time.time() - start_time
            # Adaptive time management: dừng sớm hơn nếu đã có move tốt và thời gian sắp hết
            time_remaining = max_time - elapsed
            if time_remaining < max_time * 0.1:  # Dừng nếu còn < 10% thời gian
                break
            
            # Early termination: nếu đã có move tốt và đang ở depth cao, có thể dừng sớm
            if current_depth >= 3 and best_move_so_far and time_remaining < max_time * 0.3:
                # Kiểm tra xem có move nào tốt hơn đáng kể không
                scored = self._get_scored_moves_with_time(current_depth, time_remaining * 0.5)
                if scored and len(scored) > 0:
                    if scored[0][0] <= best_score_so_far + 50:  # Không tốt hơn đáng kể
                        break  # Dừng sớm để tiết kiệm thời gian
            
            scored = self._get_scored_moves_with_time(current_depth, time_remaining)
            
            if not scored:
                break
            
            # Cập nhật best move nếu có kết quả tốt hơn
            if scored[0][0] > best_score_so_far:
                best_move_so_far = scored[0][1]
                best_score_so_far = scored[0][0]
            
            # Nếu đã đạt target depth, dừng
            if current_depth >= target_depth:
                break
        
        if not best_move_so_far:
            # Fallback: tính toán nhanh với depth 1
            scored = self._get_scored_moves(1)
            if scored:
                best_move_so_far = scored[0][1]
        
        if not best_move_so_far:
            return None
        
        # 根据难度级别选择移动
        if difficulty_config.randomness > 0 and random.random() < difficulty_config.randomness:
            # Tính lại để có top moves
            scored = self._get_scored_moves(max_depth if max_depth else target_depth)
            if scored:
                top_k = scored[: min(5, len(scored))]
                return random.choice(top_k)[1]
        
        # 检查是否有失误（blunder）机会
        if difficulty_config.blunder_chance > 0 and random.random() < difficulty_config.blunder_chance:
            scored = self._get_scored_moves(max_depth if max_depth else target_depth)
            if scored and len(scored) > 1:
                return scored[1][1]  # 第二好的移动
        
        return best_move_so_far
    
    def _get_scored_moves_with_time(self, max_depth: int, max_time: float) -> List[Tuple[int, chess.Move]]:
        """获取所有合法移动的评分 với thời gian giới hạn"""
        start = time.time()
        scored: List[Tuple[int, chess.Move]] = []
        
        # Tối ưu: move ordering trước khi tính toán
        legal_moves = list(self.board.legal_moves)
        legal_moves = self._order_moves(legal_moves, 0)  # depth 0 for root
        
        for move in legal_moves:
            if time.time() - start > max_time:
                break
            self.board.push(move)
            score = -self._negamax(max_depth - 1, -10**9, 10**9, start, max_time)
            self.board.pop()
            scored.append((score, move))
        
        if not scored:
            return []
        
        # Move ordering - 按分数排序
        scored.sort(reverse=True, key=lambda sm: sm[0])
        return scored
    
    def get_top_moves(self, n: int = 3, max_depth: Optional[int] = None, max_time: Optional[float] = None) -> List[chess.Move]:
        """获取top N个最佳移动 - 优化版本，只计算一次 với early termination"""
        difficulty_config = AI_DIFFICULTY_CONFIGS.get(self.cfg.difficulty, AI_DIFFICULTY_CONFIGS["medium"])
        depth = max_depth if max_depth is not None else difficulty_config.search_depth
        start = time.time()
        if max_time is None:
            max_time = difficulty_config.think_time_ms / 1000.0
        
        # Tối ưu: nếu chỉ cần 1 move, dùng best_move() nhanh hơn
        if n == 1:
            move = self.best_move(max_depth)
            return [move] if move else []
        
        # Tối ưu: sử dụng _order_moves để có move ordering tốt hơn (captures, checks, killer moves, history)
        legal_moves = list(self.board.legal_moves)
        legal_moves = self._order_moves(legal_moves, depth)  # Sử dụng move ordering thông minh
        
        scored: List[Tuple[int, chess.Move]] = []
        
        for move in legal_moves:
            elapsed = time.time() - start
            if elapsed > max_time:
                break
            
            self.board.push(move)
            score = -self._negamax(depth - 1, -10**9, 10**9, start, max_time)
            self.board.pop()
            scored.append((score, move))
            
            # Tối ưu early termination: dừng sớm hơn khi đã có đủ moves tốt
            if len(scored) >= n + 2:  # Tính thêm 2 moves để chắc chắn (thay vì n*2)
                scored.sort(reverse=True, key=lambda sm: sm[0])
                if len(scored) >= n:
                    # Kiểm tra xem top n có cách biệt lớn không
                    top_n_score = scored[n-1][0]
                    if len(scored) > n:
                        next_score = scored[n][0]
                        # Dừng sớm nếu cách biệt đáng kể hoặc đã dùng >80% thời gian
                        if top_n_score - next_score > 150 or elapsed > max_time * 0.8:
                            break
        
        if not scored:
            return []
        
        # Sắp xếp và trả về top N
        scored.sort(reverse=True, key=lambda sm: sm[0])
        top_moves = []
        seen_moves = set()
        for score, move in scored:
            if move not in seen_moves:
                top_moves.append(move)
                seen_moves.add(move)
                if len(top_moves) >= n:
                    break
        
        return top_moves

    def _order_moves(self, moves: List[chess.Move], depth: int) -> List[chess.Move]:
        """Sắp xếp moves theo thứ tự ưu tiên: captures, checks, killer moves, history, others - Tối ưu với cache"""
        # Tối ưu: Cache center squares set để tránh tạo list mỗi lần
        center_squares_set = {27, 28, 35, 36}  # e4, e5, d4, d5
        
        def move_priority(move: chess.Move) -> int:
            priority = 0
            
            # 1. Captures có priority cao nhất
            if self.board.is_capture(move):
                # MVV-LVA: Most Valuable Victim - Least Valuable Attacker
                captured_piece = self.board.piece_at(move.to_square)
                moving_piece = self.board.piece_at(move.from_square)
                if captured_piece and moving_piece:
                    captured_value = PIECE_VALUES.get(captured_piece.piece_type, 0)
                    moving_value = PIECE_VALUES.get(moving_piece.piece_type, 0)
                    priority += 10000 + (captured_value - moving_value)  # Ưu tiên ăn quân giá trị cao
            
            # 2. Checks - tối ưu: chỉ check nếu không phải capture (captures đã có priority cao)
            if not self.board.is_capture(move):
                self.board.push(move)
                is_check = self.board.is_check()
                self.board.pop()
                if is_check:
                    priority += 5000
            
            # 3. Killer moves (moves that caused beta cutoffs)
            if depth in self._killer_moves:
                killers = self._killer_moves[depth]
                if move == killers[0]:
                    priority += 3000
                elif len(killers) > 1 and move == killers[1]:
                    priority += 2000
            
            # 4. History heuristic
            history_key = (move.from_square, move.to_square)
            if history_key in self._history:
                priority += self._history[history_key] // 10  # Scale down
            
            # 5. Center control - tối ưu: dùng set lookup
            if move.to_square in center_squares_set:
                priority += 100
            
            return priority
        
        moves.sort(key=move_priority, reverse=True)
        return moves
    
    def _get_tt_key(self) -> str:
        """Generate transposition table key from current board state"""
        # Use FEN as key (simpler than Zobrist hashing for now)
        return self.board.fen()
    
    def _negamax(self, depth: int, alpha: int, beta: int, start_time: float, max_time: float) -> int:
        """Negamax算法，支持alpha-beta剪枝 - tối ưu với move ordering, killer moves, history, transposition table"""
        if time.time() - start_time > max_time:
            return self._evaluate()
        
        # Check transposition table
        tt_key = self._get_tt_key()
        if tt_key in self._transposition_table:
            entry = self._transposition_table[tt_key]
            if entry.depth >= depth:
                self._tt_hits += 1
                if entry.flag == "exact":
                    return entry.score
                elif entry.flag == "lower" and entry.score >= beta:
                    return entry.score
                elif entry.flag == "upper" and entry.score <= alpha:
                    return entry.score
        
        # Quiescence search: tiếp tục tìm kiếm trong các nước capture/check khi depth = 0
        if depth == 0:
            if self.cfg.quiescence:
                return self._quiescence(alpha, beta, start_time, max_time, depth=0)
            else:
                return self._evaluate()
        
        if self.board.is_game_over(claim_draw=True):
            return self._evaluate()

        # Move ordering với killer moves và history
        legal_moves = list(self.board.legal_moves)
        
        # Try TT move first if available
        tt_move = None
        if tt_key in self._transposition_table:
            tt_move = self._transposition_table[tt_key].move
            if tt_move and tt_move in legal_moves:
                legal_moves.remove(tt_move)
                legal_moves.insert(0, tt_move)
        
        legal_moves = self._order_moves(legal_moves, depth)

        max_eval = -10**9
        move_count = 0
        best_move: Optional[chess.Move] = None
        original_alpha = alpha
        
        for move in legal_moves:
            self.board.push(move)
            eval_score = -self._negamax(depth - 1, -beta, -alpha, start_time, max_time)
            self.board.pop()
            
            move_count += 1
            
            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move
            
            if max_eval > alpha:
                alpha = max_eval
            
            # Beta cutoff - lưu killer move
            if alpha >= beta:
                # Lưu killer move
                if depth not in self._killer_moves:
                    self._killer_moves[depth] = [None, None]
                killers = self._killer_moves[depth]
                if move != killers[0]:
                    killers[1] = killers[0]
                    killers[0] = move
                
                # Cập nhật history heuristic
                history_key = (move.from_square, move.to_square)
                self._history[history_key] = self._history.get(history_key, 0) + depth * depth
                
                # Store in TT with lower bound
                self._store_tt(tt_key, beta, depth, "lower", move)
                break  # Alpha-beta剪枝
        
        # Store result in transposition table
        flag = "exact"
        if max_eval <= original_alpha:
            flag = "upper"
        elif max_eval >= beta:
            flag = "lower"
        self._store_tt(tt_key, max_eval, depth, flag, best_move)
        
        return max_eval
    
    def _store_tt(self, key: str, score: int, depth: int, flag: str, move: Optional[chess.Move]) -> None:
        """Store entry in transposition table with size limit"""
        # Limit TT size to prevent memory issues
        if len(self._transposition_table) >= self._tt_size_limit:
            # Remove oldest entries (simple: clear 20% when full)
            keys_to_remove = list(self._transposition_table.keys())[:self._tt_size_limit // 5]
            for k in keys_to_remove:
                del self._transposition_table[k]
        
        self._transposition_table[key] = TTEntry(score=score, depth=depth, flag=flag, move=move)
    
    def _quiescence(self, alpha: int, beta: int, start_time: float, max_time: float, depth: int = 0) -> int:
        """Quiescence search: tiếp tục tìm kiếm trong các nước capture/check với depth limit"""
        # Giới hạn depth để tránh quá sâu (tối đa 4-5 nước)
        if depth >= 5:
            return self._evaluate()
        
        if time.time() - start_time > max_time:
            return self._evaluate()
        
        # Đánh giá tĩnh
        stand_pat = self._evaluate()
        
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat
        
        # Chỉ xem xét captures và checks
        legal_moves = list(self.board.legal_moves)
        tactical_moves = []
        for move in legal_moves:
            if self.board.is_capture(move):
                tactical_moves.append(move)
            else:
                # Kiểm tra check
                self.board.push(move)
                if self.board.is_check():
                    tactical_moves.append(move)
                self.board.pop()
        
        # Tối ưu: Nếu không có tactical moves, return stand_pat ngay
        if not tactical_moves:
            return stand_pat
        
        # Sắp xếp captures theo MVV-LVA
        tactical_moves.sort(key=lambda m: (
            PIECE_VALUES.get(self.board.piece_at(m.to_square).piece_type if self.board.piece_at(m.to_square) else 0, 0) -
            PIECE_VALUES.get(self.board.piece_at(m.from_square).piece_type if self.board.piece_at(m.from_square) else 0, 0)
        ), reverse=True)
        
        for move in tactical_moves:
            if time.time() - start_time > max_time:
                break
            
            self.board.push(move)
            score = -self._quiescence(-beta, -alpha, start_time, max_time, depth + 1)
            self.board.pop()
            
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        
        return alpha

    def _evaluate(self) -> int:
        """评估位置，根据难度级别使用不同的评估函数"""
        if self.board.is_checkmate():
            return -10**8  # current side to move is checkmated
        if self.board.is_stalemate() or self.board.is_insufficient_material() or self.board.can_claim_draw():
            return 0
        
        # 使用高级评估函数（根据难度级别）
        return evaluate_position_advanced(self.board, self.cfg.difficulty)


