from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import threading
import queue


@dataclass
class MoveRecord:
    set_id: str
    game_index: int
    move_index: int
    player_name: str
    piece: str
    from_sq: str
    to_sq: str
    fen_after: str
    timestamp: float
    mode: str = ""
    ai_difficulty: str = ""
    side_to_move_before: str = ""  # "W" or "B"
    result_reason: str = ""


class HistoryWriter:
    """Handles writing move history to CSV and set results to JSON."""

    def __init__(self, csv_path: str, results_json_path: str) -> None:
        self.csv_path = csv_path
        self.results_json_path = results_json_path
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        os.makedirs(os.path.dirname(results_json_path), exist_ok=True)
        self._ensure_csv_header()
        # Async write queue to avoid UI stutter on move commit
        self._queue: "queue.Queue[MoveRecord]" = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._worker, name="HistoryWriterWorker", daemon=True)
        self._worker_thread.start()

    def _ensure_csv_header(self) -> None:
        if not os.path.exists(self.csv_path) or os.path.getsize(self.csv_path) == 0:
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "set_id",
                    "game_index",
                    "move_index",
                    "player_name",
                    "piece",
                    "from",
                    "to",
                    "fen_after",
                    "timestamp",
                    "mode",
                    "ai_difficulty",
                    "side_to_move_before",
                    "result_reason",
                ])

    def append_move(self, record: MoveRecord) -> None:
        # Enqueue for background write to keep main thread responsive
        try:
            self._queue.put_nowait(record)
        except Exception:
            # Fallback to synchronous write only if queue fails (should be rare)
            try:
                with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        record.set_id,
                        record.game_index,
                        record.move_index,
                        record.player_name,
                        record.piece,
                        record.from_sq,
                        record.to_sq,
                        record.fen_after,
                        f"{record.timestamp:.3f}",
                        record.mode,
                        record.ai_difficulty,
                        record.side_to_move_before,
                        record.result_reason,
                    ])
            except Exception as e:
                print(f"[History] Error writing CSV (sync fallback): {e}")

    def _worker(self) -> None:
        """Background worker that batches CSV writes."""
        try:
            while not self._stop_event.is_set():
                try:
                    # Wait for at least one record
                    first: MoveRecord = self._queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                batch: List[MoveRecord] = [first]
                # Drain additional records without blocking to batch writes
                while True:
                    try:
                        batch.append(self._queue.get_nowait())
                    except queue.Empty:
                        break
                # Perform a single append for the batch
                try:
                    with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        for record in batch:
                            writer.writerow([
                                record.set_id,
                                record.game_index,
                                record.move_index,
                                record.player_name,
                                record.piece,
                                record.from_sq,
                                record.to_sq,
                                record.fen_after,
                                f"{record.timestamp:.3f}",
                                record.mode,
                                record.ai_difficulty,
                                record.side_to_move_before,
                                record.result_reason,
                            ])
                except Exception as e:
                    print(f"[History] Error writing CSV (async): {e}")
                finally:
                    # Mark task done for the whole batch
                    for _ in batch:
                        self._queue.task_done()
        except Exception as e:
            print(f"[History] Worker crashed: {e}")

    def close(self) -> None:
        """Signal background worker to stop and flush remaining records."""
        self._stop_event.set()
        try:
            # Flush any remaining records synchronously
            remaining: List[MoveRecord] = []
            while True:
                try:
                    remaining.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            if remaining:
                with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    for record in remaining:
                        writer.writerow([
                            record.set_id,
                            record.game_index,
                            record.move_index,
                            record.player_name,
                            record.piece,
                            record.from_sq,
                            record.to_sq,
                            record.fen_after,
                            f"{record.timestamp:.3f}",
                            record.mode,
                            record.ai_difficulty,
                            record.side_to_move_before,
                            record.result_reason,
                        ])
        except Exception as e:
            print(f"[History] Error during close flush: {e}")

    def write_set_result(self, result: Dict[str, Any]) -> None:
        # Append into JSON list file
        try:
            data: List[Dict[str, Any]] = []
            if os.path.exists(self.results_json_path) and os.path.getsize(self.results_json_path) > 0:
                with open(self.results_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data.append(result)
            with open(self.results_json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[History] Error writing results.json: {e}")


