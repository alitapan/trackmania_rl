import subprocess
import time
import pydirectinput
import pygetwindow as gw
import psutil
import win32gui
import win32process

class TrackmaniaGameInstance:
    def __init__(self, telemetry_bridge, title_keyword="Trackmania"):
        """
        Initializes the TrackmaniaGameInstance instance.

        This method will launch Trackmania via Uplay.
        It will then wait for the game window to appear, and navigate to the downloaded
        track menu. If any of these steps fail, it will raise an exception.

        Args:
            telemetry_bridge (TelemetryBridge): The TelemetryBridge instance to use.
            title_keyword (str, optional): The keyword to look for in the game window
                title. Defaults to "Trackmania".

        Raises:
            Exception: If any step in the initialization fails.
        """
        self.bridge = telemetry_bridge
        self.game_pid = None
        self.game_window = None
        self.title_keyword = title_keyword

        try:
            self._launch_game_via_uplay()
            self._find_trackmania_process()
            time.sleep(5)  # Give time for window to appear
            self._find_game_window_by_pid()
            self._wait_for_main_menu()
            self._navigate_to_downloaded_track()

        except Exception as e:
            print("[TrackmaniaEnv] Failed to initialize:", e)
            raise

    def _launch_game_via_uplay(self):
        print("[TrackmaniaEnv] Launching game via uplay://...")
        subprocess.Popen(["cmd", "/c", "start", "uplay://launch/5595/0"])
        time.sleep(5)

    def _find_trackmania_process(self, timeout=60):
        """Find the Trackmania.exe process and store its PID.

        This function waits up to ``timeout`` seconds for the process to appear.
        If the process is not found, a :py:class:`TimeoutError` is raised.

        The process is found by iterating over all processes and checking if the
        name contains "trackmania". If no such process is found, this function
        falls back to checking all window titles and looking for a window with
        a title that contains "trackmania". The first matching window's PID is
        used as a fallback.
        """
        print("[TrackmaniaEnv] Looking for Trackmania.exe process...")
        end_time = time.time() + timeout
        while time.time() < end_time:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and "trackmania" in proc.info['name'].lower():
                    self.game_pid = proc.info['pid']
                    print(f"[TrackmaniaEnv] Found Trackmania PID: {self.game_pid}")
                    return

            # --- fallback: check window title ---
            import win32gui
            def callback(hwnd, pid_list):
                title = win32gui.GetWindowText(hwnd)
                if "trackmania" in title.lower():
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    pid_list.append(pid)

            pid_guess = []
            win32gui.EnumWindows(callback, pid_guess)
            if pid_guess:
                self.game_pid = pid_guess[0]
                print(f"[TrackmaniaEnv] Fallback window-based PID: {self.game_pid}")
                return

            time.sleep(1)
        raise TimeoutError("Trackmania.exe process not found.")

    def _find_game_window_by_pid(self, timeout=60):
        """
        Find the game window by iterating over all windows and checking if the
        window title contains "Trackmania" and the PID matches the Trackmania
        process.

        Args:
            timeout (int, optional): Timeout in seconds. Defaults to 60.

        Raises:
            TimeoutError: If no visible Trackmania window is found after the
                given timeout.
        """
        print("[TrackmaniaEnv] Scanning windows for Trackmania...")

        end_time = time.time() + timeout

        def is_trackmania_window(hwnd, target_pid):
            if not win32gui.IsWindowVisible(hwnd):
                return False
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            title = win32gui.GetWindowText(hwnd)
            return pid == target_pid and title and "trackmania" in title.lower()

        # STEP 1: Get correct Trackmania PID
        trackmania_pid = None
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and "trackmania.exe" == proc.info['name'].lower():
                trackmania_pid = proc.info['pid']
                print(f"[TrackmaniaEnv] Found Trackmania PID: {trackmania_pid}")
                break

        if not trackmania_pid:
            raise RuntimeError("Could not find Trackmania.exe running.")

        # STEP 2: Wait for window to appear
        while time.time() < end_time:
            hwnds = []
            win32gui.EnumWindows(lambda hwnd, result: result.append(hwnd)
                                if is_trackmania_window(hwnd, trackmania_pid) else None, hwnds)

            if hwnds:
                hwnd = hwnds[0]
                title = win32gui.GetWindowText(hwnd)
                print(f"[TrackmaniaEnv] Game window found: '{title}'")
                self.game_window = gw.Window(hwnd)
                return

            time.sleep(1)

        raise TimeoutError("No visible Trackmania window found.")

    def _wait_for_main_menu(self, timeout=300):
        """
        Wait for the main menu to appear in the game.

        Monitor telemetry for the main menu state and wait until it is detected.
        If the main menu is not detected within the specified timeout, raise a
        `TimeoutError`.

        :param timeout: Time in seconds to wait for the main menu to appear.
        :raises TimeoutError: Main menu not detected in time.
        """
        print("[TrackmaniaEnv] Waiting for main menu via telemetry...")
        end_time = time.time() + timeout
        while time.time() < end_time:
            telemetry = self.bridge.get_latest_telemetry()
            if telemetry and telemetry.in_main_menu:
                print("[TrackmaniaEnv] Main menu detected.")
                time.sleep(5)
                return
            self.press_key("enter")  # Skip cutscene
            time.sleep(0.2)
        raise TimeoutError("Main menu not detected in time.")
    
    def press_key(self, key):
        pydirectinput.press(key)
        
    def _navigate_to_downloaded_track(self):
        print("[TrackmaniaEnv] Navigating to track...")
        steps = [
            "enter",      # "Play"
            #"pageup",     # "Local"
            "right",      
            "right",      
            "enter",      # "Play a track"
            "enter",      # "My Local Tracks"
            "right",      
            "enter",      # "Downloaded"
            "enter",      # Launch first track
        ]
        for key in steps:
            self.press_key(key)
            time.sleep(0.2)