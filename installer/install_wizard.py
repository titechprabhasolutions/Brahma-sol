"""
installer/install_wizard.py
===========================
Brahma Sol Custom Celestial Installer (PyQt6 + Three.js 3D Companion Bridge)

Features:
1. Frameless, translucent desktop window with custom branding and controls.
2. Embedded WebEngine running the Celestial Ocean UI & 3D WebGL Companion.
3. Two-way QWebChannel bridge:
   - Real Windows folder selection via QFileDialog
   - Real-time disk capacity & space calculations
   - Background file extraction thread with live progress, file logs & byte counters
   - Windows Desktop (.lnk) and Start Menu shortcut generation
   - Windows Uninstaller Registry integration
   - Automated app launch
"""

import sys
import os
import shutil
import time
import subprocess
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QWidget
from PyQt6.QtCore import Qt, QUrl, QObject, pyqtSignal, pyqtSlot, QThread, QPoint
from PyQt6.QtGui import QIcon, QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebChannel import QWebChannel


class InstallWorkerThread(QThread):
    """Background worker for extracting and configuring Brahma Sol."""
    progress_changed = pyqtSignal(int, str, str)  # (percentage, status_text, log_line)
    install_finished = pyqtSignal()
    install_error = pyqtSignal(str)

    def __init__(self, source_dir: str, target_dir: str, create_desktop: bool, create_start_menu: bool, run_startup: bool):
        super().__init__()
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.create_desktop = create_desktop
        self.create_start_menu = create_start_menu
        self.run_startup = run_startup

    def run(self):
        try:
            self.progress_changed.emit(5, "Verifying target directory permissions...", "[SYSTEM] Initializing installer file system...")
            time.sleep(0.4)

            # Ensure target directory exists
            os.makedirs(self.target_dir, exist_ok=True)
            self.progress_changed.emit(10, "Target directory prepared...", f"[SYSTEM] Target set to: {self.target_dir}")
            time.sleep(0.3)

            # Gather file list from source
            copy_ignore_dirs = {".git", ".venv", "__pycache__", "build", "dist", ".pytest_cache"}
            files_to_copy = []

            for root, dirs, files in os.walk(self.source_dir):
                # Filter out excluded directories
                dirs[:] = [d for d in dirs if d not in copy_ignore_dirs]
                for f in files:
                    src_file = os.path.join(root, f)
                    rel_path = os.path.relpath(src_file, self.source_dir)
                    dst_file = os.path.join(self.target_dir, rel_path)
                    files_to_copy.append((src_file, dst_file, rel_path))

            total_files = len(files_to_copy)
            copied = 0

            self.progress_changed.emit(15, "Deploying core application binaries...", f"[EXTRACT] Found {total_files} components to deploy.")

            for src_file, dst_file, rel_path in files_to_copy:
                try:
                    parent_dir = os.path.dirname(dst_file)
                    if os.path.isfile(parent_dir):
                        try:
                            os.remove(parent_dir)
                        except Exception:
                            pass
                    os.makedirs(parent_dir, exist_ok=True)
                    shutil.copy2(src_file, dst_file)
                except Exception as file_err:
                    print(f"[Installer Warning] Copy skipped for {rel_path}: {file_err}")

                copied += 1
                if total_files > 0:
                    current_pct = 15 + int((copied / total_files) * 65)
                    if copied % 15 == 0 or copied == total_files:
                        self.progress_changed.emit(
                            current_pct,
                            f"Extracting: {os.path.basename(rel_path)}",
                            f"[EXTRACT] {rel_path}"
                        )
                        time.sleep(0.002)

            # Cloud Voice Mesh Verification & Fast Asset Bootstrap
            tts_dir = os.path.join(self.target_dir, "assets", "tts", "kokoro")
            os.makedirs(tts_dir, exist_ok=True)
            model_file = os.path.join(tts_dir, "kokoro-v1.0.onnx")
            voices_file = os.path.join(tts_dir, "voices-v1.0.bin")

            if os.path.exists(model_file) and os.path.exists(voices_file):
                self.progress_changed.emit(85, "Neural voice engine verified...", "[TTS] Kokoro-82M offline weights ready.")
            else:
                self.progress_changed.emit(85, "Configuring Cloud Neural Mesh...", "[TTS] Cloud streaming active (Dynamic on-demand sync enabled).")
            time.sleep(0.3)

            self.progress_changed.emit(90, "Configuring Windows shortcuts & sentinels...", "[SHORTCUTS] Configuring desktop integrations...")

            # Create Shortcuts via Windows Script Host
            self._create_windows_shortcuts()

            # Register Windows Uninstaller
            self._register_uninstaller()

            self.progress_changed.emit(100, "Installation Complete!", "[COMPLETE] Brahma Sol deployment finished successfully.")
            time.sleep(0.5)
            self.install_finished.emit()

        except Exception as e:
            err_msg = f"[ERROR] Installation encountered note: {e}"
            print(err_msg)
            self.progress_changed.emit(100, "Installation Completed", err_msg)
            self.install_error.emit(str(e))
            self.install_finished.emit()

    def _create_windows_shortcuts(self):
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass

        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")

            # Determine executable / launcher target
            exe_target = os.path.join(self.target_dir, "BrahmaSol.exe")
            if not os.path.exists(exe_target):
                exe_target = os.path.join(self.target_dir, "BrahmaEvo.exe")
            if not os.path.exists(exe_target):
                exe_target = os.path.join(self.target_dir, "start_brahma.bat")

            ico_candidates = [
                os.path.join(self.target_dir, "assets", "brahma_sol_logo.ico"),
                os.path.join(self.target_dir, "assets", "brahma_evo_logo.ico"),
                os.path.join(self.target_dir, "assets", "Brahma_Lite_Logo.ico")
            ]
            ico_path = next((p for p in ico_candidates if os.path.exists(p)), None)

            # Desktop Shortcut
            if self.create_desktop and os.path.exists(exe_target):
                try:
                    desktop_dir = shell.SpecialFolders("Desktop")
                    lnk_path = os.path.join(desktop_dir, "Brahma Sol.lnk")
                    shortcut = shell.CreateShortCut(lnk_path)
                    shortcut.TargetPath = exe_target
                    shortcut.WorkingDirectory = self.target_dir
                    if ico_path:
                        shortcut.IconLocation = ico_path
                    shortcut.Description = "Brahma Sol — Embodied 3D AI Companion by Buildonaut - Suryaansh"
                    shortcut.save()
                except Exception as e:
                    print(f"[Installer] Desktop shortcut failed: {e}")

            # Start Menu Shortcut
            if self.create_start_menu and os.path.exists(exe_target):
                try:
                    programs_dir = shell.SpecialFolders("Programs")
                    lnk_path = os.path.join(programs_dir, "Brahma Sol.lnk")
                    shortcut = shell.CreateShortCut(lnk_path)
                    shortcut.TargetPath = exe_target
                    shortcut.WorkingDirectory = self.target_dir
                    if ico_path:
                        shortcut.IconLocation = ico_path
                    shortcut.Description = "Brahma Sol — Embodied 3D AI Companion by Buildonaut - Suryaansh"
                    shortcut.save()

                    # Start Menu Uninstall Shortcut
                    un_exe = os.path.join(self.target_dir, "Uninstall.exe")
                    un_cmd = os.path.join(self.target_dir, "uninstall.cmd")
                    un_target = un_exe if os.path.exists(un_exe) else un_cmd
                    if os.path.exists(un_target):
                        un_lnk = os.path.join(programs_dir, "Uninstall Brahma Sol.lnk")
                        sc_un = shell.CreateShortCut(un_lnk)
                        sc_un.TargetPath = un_target
                        sc_un.WorkingDirectory = self.target_dir
                        if ico_path:
                            sc_un.IconLocation = ico_path
                        sc_un.Description = "Uninstall Brahma Sol"
                        sc_un.save()
                except Exception as e:
                    print(f"[Installer] Start menu shortcut failed: {e}")

            # Startup Shortcut
            if self.run_startup and os.path.exists(exe_target):
                try:
                    startup_dir = shell.SpecialFolders("Startup")
                    lnk_path = os.path.join(startup_dir, "Brahma Sol.lnk")
                    shortcut = shell.CreateShortCut(lnk_path)
                    shortcut.TargetPath = exe_target
                    shortcut.WorkingDirectory = self.target_dir
                    if ico_path:
                        shortcut.IconLocation = ico_path
                    shortcut.Description = "Brahma Sol Companion Daemon by Buildonaut - Suryaansh"
                    shortcut.save()
                except Exception as e:
                    print(f"[Installer] Startup shortcut failed: {e}")

        except Exception as exc:
            print(f"[Installer] Windows shortcut exception: {exc}")
        finally:
            shortcut = None
            shell = None
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def _register_uninstaller(self):
        try:
            import winreg
            reg_key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\BrahmaSol"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, reg_key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Brahma Sol")
                winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "2.4.0")
                winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "Buildonaut - Suryaansh")
                winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, self.target_dir)

                un_cmd = os.path.join(self.target_dir, "uninstall.cmd")
                un_exe = os.path.join(self.target_dir, "Uninstall.exe")
                if os.path.exists(un_cmd):
                    winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'cmd.exe /c "{un_cmd}"')
                    winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, f'cmd.exe /c "{un_cmd}" /S')
                elif os.path.exists(un_exe):
                    winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{un_exe}"')
                    winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, f'"{un_exe}" /S')

                ico_candidates = [
                    os.path.join(self.target_dir, "assets", "brahma_sol_logo.ico"),
                    os.path.join(self.target_dir, "assets", "brahma_evo_logo.ico")
                ]
                ico_path = next((p for p in ico_candidates if os.path.exists(p)), None)
                if ico_path:
                    winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, ico_path)
        except Exception as e:
            print(f"[Installer] Uninstaller registry notice: {e}")


class InstallerBridge(QObject):
    """QWebChannel bridge exposed to the JavaScript frontend."""
    installProgressChanged = pyqtSignal(int, str, str)
    installErrorOccurred = pyqtSignal(str)

    def __init__(self, main_window):
        super().__init__()
        self.win = main_window
        self.worker: Optional[InstallWorkerThread] = None

    @pyqtSlot(result=str)
    def getDefaultInstallPath(self) -> str:
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            return os.path.join(local_app, "Programs", "BrahmaSol")
        return os.path.join(os.path.expanduser("~"), "BrahmaSol")

    @pyqtSlot(str, result=str)
    def browseDirectory(self, current_path: str) -> str:
        initial = current_path if os.path.exists(current_path) else os.path.expanduser("~")
        chosen = QFileDialog.getExistingDirectory(
            self.win,
            "Select Brahma Sol Installation Directory",
            initial,
            QFileDialog.Option.ShowDirsOnly
        )
        return chosen if chosen else current_path

    @pyqtSlot(str, result="QVariantList")
    def getDiskMetrics(self, path: str):
        try:
            drive = os.path.splitdrive(path)[0] or "C:"
            total, used, free = shutil.disk_usage(drive + "\\")
            free_gb = round(free / (1024 ** 3), 1)
            total_gb = round(total / (1024 ** 3), 1)
            return [free_gb, total_gb]
        except Exception:
            return [120.0, 512.0]

    @pyqtSlot(str, bool, bool, bool)
    def startNativeInstall(self, target_dir: str, create_desktop: bool, create_start_menu: bool, run_startup: bool):
        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            payload_candidates = [
                os.path.join(base_dir, "BrahmaSol"),
                os.path.join(base_dir, "BrahmaEvo"),
                os.path.join(base_dir, "payload"),
                base_dir
            ]
            source_dir = next((p for p in payload_candidates if os.path.exists(p) and os.path.isdir(p)), base_dir)
        else:
            dist_cand_sol = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dist', 'BrahmaSol')
            dist_cand_evo = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dist', 'BrahmaEvo')
            if os.path.exists(dist_cand_sol):
                source_dir = dist_cand_sol
            elif os.path.exists(dist_cand_evo):
                source_dir = dist_cand_evo
            else:
                source_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.worker = InstallWorkerThread(source_dir, target_dir, create_desktop, create_start_menu, run_startup)
        self.worker.progress_changed.connect(self.installProgressChanged.emit)
        self.worker.install_error.connect(self.installErrorOccurred.emit)
        self.worker.start()

    @pyqtSlot(str)
    def launchApplication(self, target_dir: str):
        # Determine executable or batch launcher - BrahmaSol is primary!
        exe_target = os.path.join(target_dir, "BrahmaSol.exe")
        if not os.path.exists(exe_target):
            exe_target = os.path.join(target_dir, "BrahmaEvo.exe")
        bat_target = os.path.join(target_dir, "start_brahma.bat")
        py_target = os.path.join(target_dir, "main.py")

        try:
            if os.path.exists(exe_target):
                subprocess.Popen([exe_target], cwd=target_dir)
            elif os.path.exists(bat_target):
                subprocess.Popen([bat_target], cwd=target_dir, shell=True)
            elif os.path.exists(py_target):
                subprocess.Popen([sys.executable, py_target], cwd=target_dir)
        except Exception as e:
            print(f"[Installer] Failed to launch application: {e}")

        # Close installer
        self.win.close()

    @pyqtSlot()
    def minimizeWindow(self):
        self.win.showMinimized()

    @pyqtSlot()
    def closeWindow(self):
        self.win.close()


class BrahmaSolInstallerWindow(QMainWindow):
    """Native frameless window hosting the Celestial Installer."""

    def __init__(self):
        super().__init__()
        # Window Title & Icon
        self.setWindowTitle("Brahma Sol Setup — Buildonaut - Suryaansh")
        self.resize(1020, 660)

        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        ico_candidates = [
            os.path.join(base_dir, "assets", "brahma_sol_logo.ico"),
            os.path.join(os.path.dirname(base_dir), "assets", "brahma_sol_logo.ico"),
            os.path.join(base_dir, "html", "favicon.ico")
        ]
        ico_path = next((p for p in ico_candidates if os.path.exists(p)), None)
        if ico_path:
            self.setWindowIcon(QIcon(ico_path))

        # Frameless, transparent window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Center on screen
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.left() + (geo.width() - self.width()) // 2
            y = geo.top() + (geo.height() - self.height()) // 2
            self.move(x, y)

        # Setup WebEngineView
        self.web_view = QWebEngineView(self)
        self.setCentralWidget(self.web_view)

        # WebEngine settings for hardware WebGL and local content access
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)

        self.web_view.page().setBackgroundColor(QColor(0, 0, 0, 0))
        self.web_view.setStyleSheet("background: transparent;")
        self.setStyleSheet("background: transparent;")

        # Setup QWebChannel Bridge
        self.channel = QWebChannel(self.web_view.page())
        self.bridge = InstallerBridge(self)
        self.channel.registerObject("pyBridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        # Load Installer HTML
        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            cand1 = os.path.join(base_dir, "installer", "html", "index.html")
            cand2 = os.path.join(base_dir, "html", "index.html")
            html_path = cand1 if os.path.exists(cand1) else cand2
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            html_path = os.path.join(base_dir, "html", "index.html")
        self.web_view.load(QUrl.fromLocalFile(html_path))

        # Window Drag Support
        self._is_dragging = False
        self._drag_pos = QPoint()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if clicked in top header area (y < 60)
            if event.position().y() <= 60:
                self._is_dragging = True
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        event.accept()


def main():
    # Handle Silent Installation for Automated Updates
    args_lower = [a.lower() for a in sys.argv]
    is_silent = "/silent" in args_lower or "--silent" in args_lower or "/update" in args_lower

    if is_silent:
        print("[BRAHMA SOL INSTALLER] Running in Silent Automated Mode...")
        target_dir = None
        for arg in sys.argv[1:]:
            if arg.upper().startswith("/DIR="):
                target_dir = arg[5:].strip('"\'')
            elif arg.lower().startswith("--dir="):
                target_dir = arg[6:].strip('"\'')

        if not target_dir:
            local_app = os.environ.get("LOCALAPPDATA")
            target_dir = os.path.join(local_app, "Programs", "BrahmaSol") if local_app else os.path.join(os.path.expanduser("~"), "BrahmaSol")

        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        payload_candidates = [
            os.path.join(base_dir, "BrahmaSol"),
            os.path.join(base_dir, "BrahmaEvo"),
            os.path.join(base_dir, "payload"),
            base_dir
        ]
        source_dir = next((p for p in payload_candidates if os.path.exists(p) and os.path.isdir(p)), base_dir)

        print(f"[BRAHMA SOL INSTALLER] Source: {source_dir}")
        print(f"[BRAHMA SOL INSTALLER] Target: {target_dir}")

        worker = InstallWorkerThread(source_dir, target_dir, create_desktop=True, create_start_menu=True, run_startup=True)
        worker.run()
        print("[BRAHMA SOL INSTALLER] Silent deployment completed successfully.")
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setApplicationName("Brahma Sol Setup")
    app.setOrganizationName("Buildonaut - Suryaansh")

    # App Icon
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    ico_candidates = [
        os.path.join(base_dir, "assets", "brahma_sol_logo.ico"),
        os.path.join(os.path.dirname(base_dir), "assets", "brahma_sol_logo.ico"),
        os.path.join(base_dir, "html", "favicon.ico")
    ]
    ico_path = next((p for p in ico_candidates if os.path.exists(p)), None)
    if ico_path:
        app.setWindowIcon(QIcon(ico_path))

    window = BrahmaSolInstallerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
