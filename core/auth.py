from __future__ import annotations

import os
import json
import hashlib
import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Tuple


USERS_FILE = os.path.join(".", "data", "users.json")


def _ensure_store() -> None:
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _load_users() -> Dict[str, dict]:
    _ensure_store()
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_users(users: Dict[str, dict]) -> None:
    _ensure_store()
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def _hash_password(username: str, password: str) -> str:
    # Simple salted hash using username as salt
    h = hashlib.sha256()
    h.update((username + "::" + password).encode("utf-8"))
    return h.hexdigest()


def register(username: str, password: str) -> bool:
    username = (username or "").strip()
    if not username or not password:
        return False
    users = _load_users()
    if username in users:
        return False
    # Initialize user with password hash and default stats
    users[username] = {
        "hash": _hash_password(username, password),
        "wins": 0,
        "total_games": 0,
        "win_rate": 0.0,
        "registration_date": time.time()  # Lưu thời gian đăng ký để dùng làm tiebreaker
    }
    _save_users(users)
    return True


def authenticate(username: str, password: str) -> bool:
    users = _load_users()
    if username not in users:
        return False
    return users[username].get("hash") == _hash_password(username, password)


def _create_form_fields(parent: ttk.Frame) -> Tuple[ttk.Entry, ttk.Entry]:
    """Helper function to create username and password fields"""
    ttk.Label(parent, text="Username:").grid(column=0, row=0, sticky="w", pady=(0, 6))
    ent_user = ttk.Entry(parent, width=28)
    ent_user.grid(column=0, row=1, sticky="ew")

    ttk.Label(parent, text="Password:").grid(column=0, row=2, sticky="w", pady=(10, 6))
    ent_pass = ttk.Entry(parent, width=28, show="*")
    ent_pass.grid(column=0, row=3, sticky="ew")
    
    return ent_user, ent_pass


def show_login_dialog() -> Optional[str]:
    # Returns username if logged in successfully, None otherwise
    root = tk.Tk()
    root.title("Login")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    frm = ttk.Frame(root, padding=12)
    frm.grid()

    ent_user, ent_pass = _create_form_fields(frm)

    btn_row = ttk.Frame(frm)
    btn_row.grid(column=0, row=4, pady=(14, 0))

    result = {"user": None}

    def do_login():
        u = ent_user.get().strip()
        p = ent_pass.get()
        if authenticate(u, p):
            result["user"] = u
            root.destroy()
        else:
            messagebox.showerror("Login failed", "Invalid username or password")

    def do_cancel():
        root.destroy()

    def open_register():
        show_register_dialog(parent=root)

    ttk.Button(btn_row, text="Login", command=do_login).grid(column=0, row=0, padx=6)
    ttk.Button(btn_row, text="Cancel", command=do_cancel).grid(column=1, row=0, padx=6)

    link = ttk.Label(frm, text="Don't have an account? Register now", foreground="#2A6FEE", cursor="hand2")
    link.grid(column=0, row=5, pady=(10, 0))
    link.bind("<Button-1>", lambda e: open_register())

    ent_user.focus_set()
    root.mainloop()
    return result["user"]


def show_register_dialog(parent: Optional[tk.Tk] = None) -> Optional[str]:
    win = tk.Toplevel(parent) if parent else tk.Tk()
    win.title("Register")
    win.resizable(False, False)
    win.attributes("-topmost", True)

    frm = ttk.Frame(win, padding=12)
    frm.grid()

    ent_user, ent_pass = _create_form_fields(frm)

    ttk.Label(frm, text="Confirm Password:").grid(column=0, row=4, sticky="w", pady=(10, 6))
    ent_c = ttk.Entry(frm, width=28, show="*")
    ent_c.grid(column=0, row=5, sticky="ew")

    result = {"user": None}

    def do_register():
        u = ent_user.get().strip()
        p = ent_pass.get()
        c = ent_c.get()
        if not u or not p:
            messagebox.showwarning("Register", "Please enter username and password")
            return
        if p != c:
            messagebox.showwarning("Register", "Passwords do not match")
            return
        if register(u, p):
            messagebox.showinfo("Register", "Registered successfully. You can login now.")
            result["user"] = u
            win.destroy()
        else:
            messagebox.showerror("Register", "Username already exists or invalid input")

    ttk.Button(frm, text="Register", command=do_register).grid(column=0, row=6, pady=(12, 0))

    ent_user.focus_set()
    win.grab_set()
    win.wait_window()
    return result["user"]


def clear_all_users() -> bool:
    """
    Xóa tất cả dữ liệu tài khoản đã đăng ký.
    Trả về True nếu thành công, False nếu có lỗi.
    """
    try:
        _save_users({})
        return True
    except Exception:
        return False


