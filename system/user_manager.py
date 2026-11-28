"""
TianOS 用户管理器 (singleton)
================================
负责:
  - 从 data/users.json 读取 / 保存用户列表
  - 首次运行时生成默认账户 (admin / user)
  - verify_user() 验证登录
  - get/set_current_user() 管理全局登录状态
"""

import json
import os
import threading
from typing import Dict, List, Optional, Any

# 用户数据文件: TianOS/data/users.json
_USERS_FILE = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "users.json"))

# 默认账户 (首次运行 / 数据缺失时自动生成)
# 注意: 密码为空 = 尚未配置登录密码, 此时不显示登录界面
DEFAULT_USERS: List[Dict[str, str]] = [
    {"username": "admin", "password": "", "role": "admin", "display_name": "管理员"},
    {"username": "user", "password": "", "role": "standard", "display_name": "标准用户"},
]


class UserManager:
    """用户管理器单例"""

    _instance: Optional["UserManager"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._users_file = _USERS_FILE
        self._users: List[Dict[str, Any]] = []
        self._current_user: Optional[Dict[str, Any]] = None
        self._load()
        self._ensure_default_users()

    # ---------- 持久化 ----------

    def _load(self) -> None:
        """从 users.json 加载用户列表"""
        try:
            if os.path.exists(self._users_file):
                with open(self._users_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._users = data
                    return
                if isinstance(data, dict) and isinstance(data.get("users"), list):
                    self._users = data["users"]
                    return
        except Exception as e:
            print(f"[UserManager] 加载用户数据失败: {e}")
        self._users = []

    def _save(self) -> None:
        """保存用户列表到 users.json"""
        try:
            os.makedirs(os.path.dirname(self._users_file), exist_ok=True)
            with open(self._users_file, "w", encoding="utf-8") as f:
                json.dump(self._users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[UserManager] 保存用户数据失败: {e}")

    def _ensure_default_users(self) -> None:
        """确保默认账户存在 (admin 管理员 / user 标准用户)"""
        names = {u.get("username") for u in self._users}
        added = False
        for default in DEFAULT_USERS:
            if default["username"] not in names:
                self._users.append(dict(default))
                added = True
        if added:
            self._save()

    # ---------- 查询 ----------

    def get_users(self) -> List[Dict[str, Any]]:
        """返回所有用户列表"""
        return list(self._users)

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """按用户名查找用户"""
        for u in self._users:
            if u.get("username") == username:
                return u
        return None

    def verify_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """验证用户名密码，通过则返回用户信息 dict，否则返回 None"""
        user = self.get_user(username)
        if user is not None and user.get("password") == password:
            return user
        return None

    def any_password_set(self) -> bool:
        """是否存在已设置密码的账户。
        True = 至少有一名用户设置了非空密码 (系统需要登录界面);
        False = 所有账户密码均为空 (首次使用, 直接进入桌面, 无需登录)。
        """
        return any(
            str(u.get("password", "")).strip() != ""
            for u in self._users
        )

    def is_username_available(self, username: str) -> bool:
        """判断用户名是否可用 (未占用)"""
        return self.get_user(username) is None

    # ---------- 全局登录状态 ----------

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """返回当前登录用户 (未登录返回 None)"""
        return self._current_user

    def set_current_user(self, user: Optional[Dict[str, Any]]) -> None:
        """设置当前登录用户 (None 表示注销)"""
        self._current_user = user

    def is_logged_in(self) -> bool:
        """是否已经登录"""
        return self._current_user is not None

    def is_current_admin(self) -> bool:
        """当前登录用户是否拥有管理员权限"""
        return bool(self._current_user and self._current_user.get("role") == "admin")

    # ---------- 用户管理 (增删改) ----------

    def add_user(self, username: str, password: str, role: str = "standard",
                 display_name: str = "") -> bool:
        """新增用户，成功返回 True"""
        if not username or self.get_user(username) is not None:
            return False
        self._users.append({
            "username": username,
            "password": password,
            "role": role if role in ("admin", "standard") else "standard",
            "display_name": display_name or username,
        })
        self._save()
        return True

    def remove_user(self, username: str) -> bool:
        """删除用户 (不可删除当前登录用户)"""
        if username == (self._current_user or {}).get("username"):
            return False
        before = len(self._users)
        self._users = [u for u in self._users if u.get("username") != username]
        if len(self._users) != before:
            self._save()
            return True
        return False

    def update_user(self, username: str, password: str = None,
                    role: str = None, display_name: str = None) -> bool:
        """更新用户信息，成功返回 True"""
        user = self.get_user(username)
        if user is None:
            return False
        if password is not None:
            user["password"] = password
        if role is not None and role in ("admin", "standard"):
            user["role"] = role
        if display_name is not None:
            user["display_name"] = display_name
        self._save()
        # 若修改的是当前登录用户，同步更新内存状态
        if self._current_user and self._current_user.get("username") == username:
            self._current_user = user
        return True


# 全局单例
user_manager = UserManager()