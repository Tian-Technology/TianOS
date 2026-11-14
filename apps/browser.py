"""
TianOS Tian浏览器
轻量网页浏览器 - 基于 QtWebEngine (Chromium) 真实渲染网页，支持完整排版、图片和脚本。
"""

# 应用元数据 - 用于桌面图标自动发现
APP_NAME = "Tian浏览器"
APP_ICON = "🌍"
APP_ICON_FILE = "imageres 021.png"
APP_COLOR = "#00ccff"

from urllib.parse import quote as _quote

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QToolButton,
    QStatusBar, QFrame, QProgressBar
)
from PyQt6.QtCore import Qt, QUrl, QCoreApplication
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage, QWebEngineProfile

# 伪装成 Chrome 的 User-Agent，避免网站（如 Bilibili）拒绝播放 HTML5 视频
CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

HOME_URL = "tian://home"
PLAYER_URL = "tian://player"


def _build_home_html() -> str:
    return """
    <html><head><style>
      body { background:#10131f; color:#e8eaf2; font-family:'Microsoft YaHei'; text-align:center; }
      h1 { font-size:44px; color:#00ccff; margin-top:60px; }
      p.sub { color:#8899bb; font-size:13px; }
      .links { margin-top:40px; }
      .links a { display:inline-block; margin:8px 12px; padding:10px 22px;
                 color:#b7c4e0; text-decoration:none; border:1px solid #2a3550;
                 border-radius:8px; background:#171c2c; font-size:14px; }
      .links a:hover { background:#1f2640; color:#00ccff; border-color:#00ccff; }
    </style></head><body>
      <h1>🌍 Tian浏览器</h1>
      <p class="sub">在上方地址栏输入网址或搜索内容，开始浏览网页</p>
      <div class="links">
        <a href="https://www.bing.com">Bing 搜索</a>
        <a href="https://www.baidu.com">百度</a>
        <a href="https://www.bilibili.com">哔哩哔哩</a>
        <a href="https://www.qq.com">腾讯网</a>
        <a href="https://www.zhihu.com">知乎</a>
        <a href="tian://player">▶ HTML5 播放器</a>
      </div>
    </body></html>
    """


def _build_player_html() -> str:
    """内置 HTML5 播放器页面：可粘贴视频/音频直链播放"""
    return """
    <html><head><style>
      body { background:#10131f; color:#e8eaf2; font-family:'Microsoft YaHei'; text-align:center; }
      .wrap { max-width:960px; margin:40px auto; padding:0 20px; }
      h1 { font-size:36px; color:#00ccff; margin-bottom:8px; }
      .sub { color:#8899bb; font-size:13px; }
      .bar { margin:26px 0 22px; display:flex; gap:10px; }
      input { flex:1; padding:10px 16px; border-radius:8px; border:1px solid #2a3550;
              background:#171c2c; color:#e8eaf2; font-size:14px; outline:none; }
      input:focus { border-color:#00ccff; }
      button { padding:0 22px; border:none; border-radius:8px; background:#00ccff;
               color:#06121f; font-weight:bold; font-size:14px; cursor:pointer; }
      button:hover { background:#22d8ff; }
      video { width:100%; max-height:72vh; background:#000; border-radius:10px; }
      .hint { color:#5a6b8c; font-size:12px; margin-top:14px; line-height:1.8; }
    </style></head><body>
      <div class="wrap">
        <h1>▶ HTML5 播放器</h1>
        <p class="sub">支持 mp4 / webm / ogg / m3u8 等 HTML5 视频源，也可播放音频直链</p>
        <div class="bar">
          <input id="src" placeholder="粘贴视频或音频直链，例如 https://example.com/movie.mp4" />
          <button onclick="play(document.getElementById('src').value)">播放</button>
        </div>
        <video id="video" controls autoplay></video>
        <p class="hint">提示：直接输入网址即可播放网站内嵌视频；也支持本地拖入或打开本地文件后播放。</p>
      </div>
      <script>
        function play(url){
          var v = document.getElementById('video');
          url = (url || '').trim();
          if(!url) return;
          v.src = url; v.load();
          var p = v.play();
          if(p) p.catch(function(e){ alert('无法播放: ' + e.message); });
        }
        document.getElementById('src').addEventListener('keydown', function(e){
          if(e.key === 'Enter') play(this.value);
        });
      </script>
    </body></html>
    """


class _BrowserPage(QWebEnginePage):
    """自定义页面：target=_blank 等新窗口请求在当前页加载，避免弹出空白窗"""
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)

    def createWindow(self, _wtype):
        return self


class Browser(QWidget):
    """Tian浏览器 - 主窗口（基于 QtWebEngine 真实渲染网页）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tian浏览器")
        self.setMinimumSize(860, 600)

        # QtWebEngine 需要合法的应用名，否则可能警告
        if not QCoreApplication.applicationName():
            QCoreApplication.setApplicationName("TianOS")
            QCoreApplication.setOrganizationName("TianOS")

        self._history: list = []          # 访问历史
        self._history_index: int = -1
        self._current_url: str = HOME_URL

        self._setup_ui()
        self.view.urlChanged.connect(self._on_url_changed)
        self.view.titleChanged.connect(self._on_title_changed)
        self.view.loadStarted.connect(self._on_load_started)
        self.view.loadProgress.connect(self._on_load_progress)
        self.view.loadFinished.connect(self._on_load_finished)
        self._go_home()

    # ---------- 界面 ----------

    def _nav_button(self, text, tip):
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setFixedSize(30, 30)
        b.setStyleSheet("""
            QToolButton {
                color: #cdd6ea; background: transparent;
                border: none; border-radius: 6px;
                font-size: 15px;
            }
            QToolButton:hover { background: rgba(255,255,255,0.09); }
            QToolButton:disabled { color: #4a5168; }
        """)
        return b

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setStyleSheet("Browser { background-color:#131624; }")

        # 地址栏工具栏
        toolbar = QFrame()
        toolbar.setFixedHeight(54)
        toolbar.setStyleSheet("""
            QFrame { background-color:#1b2030; border-bottom:1px solid #2a3550; }
        """)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(10, 8, 10, 8)
        tl.setSpacing(6)

        self.btn_back = self._nav_button("◀", "后退")
        self.btn_fwd = self._nav_button("▶", "前进")
        self.btn_reload = self._nav_button("⟳", "刷新")
        self.btn_home = self._nav_button("🏠", "主页")
        self.btn_player = self._nav_button("🎬", "HTML5 播放器")
        self.btn_back.clicked.connect(self._go_back)
        self.btn_fwd.clicked.connect(self._go_forward)
        self.btn_reload.clicked.connect(lambda: self.view.reload())
        self.btn_home.clicked.connect(self._go_home)
        self.btn_player.clicked.connect(lambda: self._navigate(PLAYER_URL))

        self.address = QLineEdit()
        self.address.setFixedHeight(34)
        self.address.setClearButtonEnabled(True)
        self.address.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255,255,255,0.07);
                color: #e8eaf2; border: 1px solid #2a3550;
                border-radius: 8px; padding: 0 14px; font-size: 13px;
            }
            QLineEdit:focus { border-color:#00ccff; background-color: rgba(255,255,255,0.10); }
        """)
        self.address.returnPressed.connect(self._navigate_from_bar)

        self.btn_go = QToolButton()
        self.btn_go.setText("前往")
        self.btn_go.setFixedHeight(34)
        self.btn_go.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_go.setStyleSheet("""
            QToolButton {
                color:#06121f; font-weight:bold;
                background:#00ccff; border:none; border-radius:8px; padding:0 18px;
            }
            QToolButton:hover { background:#22d8ff; }
        """)
        self.btn_go.clicked.connect(self._navigate_from_bar)

        tl.addWidget(self.btn_back)
        tl.addWidget(self.btn_fwd)
        tl.addWidget(self.btn_reload)
        tl.addWidget(self.btn_home)
        tl.addWidget(self.btn_player)
        tl.addWidget(self.address, 1)
        tl.addWidget(self.btn_go)
        layout.addWidget(toolbar)

        # 页面 - 真实 Chromium 渲染引擎
        self.view = QWebEngineView()
        # 使用独立的 profile，避免与默认 profile 冲突
        self._profile = QWebEngineProfile("TianOS", self.view)
        # 伪装 UA 为 Chrome，绕过 Bilibili 等网站对浏览器的 HTML5 支持检测
        self._profile.setHttpUserAgent(CHROME_USER_AGENT)
        # 持久化存储目录，保证 Cookie/缓存生效
        self._profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        page = _BrowserPage(self._profile, self.view)
        self.view.setPage(page)
        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
        # 允许 HTML5 媒体自动播放与全屏，保证视频/音频可正常播放
        settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        # 主页深色底，避免加载瞬间白屏闪烁
        self.view.page().setBackgroundColor(QColor("#10131f"))
        layout.addWidget(self.view, 1)

        # 加载进度条
        self.progress = QProgressBar()
        self.progress.setFixedHeight(3)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.hide()
        self.progress.setStyleSheet("""
            QProgressBar { background:transparent; border:none; }
            QProgressBar::chunk { background:#00ccff; }
        """)
        layout.addWidget(self.progress)

        self.status = QStatusBar()
        self.status.setStyleSheet("""
            QStatusBar { background:#1b2030; color:#7d89a6; font-size:11px; }
        """)
        layout.addWidget(self.status)
        self.status.showMessage("就绪")

    # ---------- 导航 ----------

    def _clean_input(self, text: str) -> str:
        text = text.strip()
        if not text:
            return ""
        if text == PLAYER_URL:
            return PLAYER_URL
        if text.startswith("tian://"):
            return "tian://home"
        if text.startswith("http://") or text.startswith("https://"):
            return text
        # 若看起来像网址（含点且无空格）
        if "." in text and " " not in text:
            return "https://" + text
        # 否则当作搜索
        return "https://www.bing.com/search?q=" + _quote(text)

    def _navigate_from_bar(self):
        url = self._clean_input(self.address.text())
        if url:
            self._navigate(url)

    def _go_back(self):
        self.view.back()

    def _go_forward(self):
        self.view.forward()

    def _go_home(self):
        self._navigate(HOME_URL)

    def _navigate(self, url: str, push: bool = True):
        if url.startswith("tian://") or url.startswith("about:"):
            if url == PLAYER_URL or url.startswith("about:player"):
                target, html, label = PLAYER_URL, _build_player_html(), "HTML5 播放器"
            else:
                target, html, label = HOME_URL, _build_home_html(), "主页"
            self._current_url = target
            self.address.setText(target)
            self.view.setHtml(html, QUrl(target))
            self.view.page().setBackgroundColor(QColor("#10131f"))
            self.status.showMessage(label)
            if push:
                self._record_history(target, push)
            self._update_buttons()
            return

        self._current_url = url
        self.address.setText(url)
        if push:
            self._record_history(url, True)
        self.status.showMessage("正在加载: " + url)
        self.view.setUrl(QUrl(url))

    def _record_history(self, url: str, push: bool):
        if push:
            # 丢弃当前向前的历史
            self._history = self._history[: self._history_index + 1]
            self._history.append(url)
            self._history_index = len(self._history) - 1

    def _update_buttons(self):
        self.btn_back.setEnabled(self.view.history().canGoBack())
        self.btn_fwd.setEnabled(self.view.history().canGoForward())

    # ---------- 引擎信号 ----------

    def _on_url_changed(self, url: QUrl):
        text = url.toString()
        if text == "tian://home" or text.startswith("about:tian"):
            self.address.setText("tian://home")
            self._current_url = HOME_URL
        elif text == PLAYER_URL or text.startswith("about:tianosplayer"):
            self.address.setText(PLAYER_URL)
            self._current_url = PLAYER_URL
        else:
            self.address.setText(text)
            self._current_url = text
        # 同步历史当前项为最终真实 URL
        if self._history:
            self._history[self._history_index] = self._current_url
        self._update_buttons()

    def _on_title_changed(self, title: str):
        if title:
            self.setWindowTitle(f"{title} - Tian浏览器")

    def _on_load_started(self):
        self.progress.setValue(0)
        self.progress.show()

    def _on_load_progress(self, value: int):
        self.progress.setValue(int(value))
        self.progress.show()

    def _on_load_finished(self, ok: bool):
        self.progress.hide()
        status = "已完成 · " + self._current_url if ok else "页面加载失败"
        self.status.showMessage(status)
        self._update_buttons()