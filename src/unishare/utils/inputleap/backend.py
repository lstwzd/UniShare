"""
InputLeap 纯 Python 后端
基于 pynput 库实现跨平台键鼠共享
"""
from typing import Dict, Callable

from src.unishare.core.logger import log


class InputLeapBackend:
    """
    跨平台键鼠共享实现
    使用 pynput 捕获/注入键盘鼠标事件
    通过 TCP 协议传输事件命令 (JSON over length-prefixed TCP)
    """

    def __init__(self):
        self._running = False
        self._keyboard_listener = None
        self._mouse_listener = None

    @property
    def running(self) -> bool:
        return self._running

    def start_capture(self, callback: Callable):
        try:
            from pynput.keyboard import Listener as KListener
            from pynput.mouse import Listener as MListener

            self._running = True

            def on_move(x, y):
                if self._running:
                    callback({"type": "mouse_move", "x": x, "y": y})

            def on_click(x, y, button, pressed):
                if self._running:
                    from pynput.mouse import Button
                    name = "left" if button == Button.left else ("right" if button == Button.right else "middle")
                    callback({"type": "mouse_click", "x": x, "y": y, "button": name, "pressed": pressed})

            def on_scroll(x, y, dx, dy):
                if self._running:
                    callback({"type": "mouse_scroll", "x": x, "y": y, "dx": dx, "dy": dy})

            def on_press(key):
                if self._running:
                    try:
                        k = key.char if hasattr(key, 'char') else str(key).replace("'", "")
                        callback({"type": "key_press", "key": k})
                    except:
                        pass

            def on_release(key):
                if self._running:
                    try:
                        k = key.char if hasattr(key, 'char') else str(key).replace("'", "")
                        callback({"type": "key_release", "key": k})
                    except:
                        pass

            self._keyboard_listener = KListener(on_press=on_press, on_release=on_release)
            self._mouse_listener = MListener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
            self._keyboard_listener.start()
            self._mouse_listener.start()
            return True

        except Exception as e:
            log.error(f"[InputLeap] 启动输入捕获失败: {e}")
            self._running = False
            return False

    def stop_capture(self):
        self._running = False
        if self._keyboard_listener:
            try:
                self._keyboard_listener.stop()
            except:
                pass
        if self._mouse_listener:
            try:
                self._mouse_listener.stop()
            except:
                pass

    @staticmethod
    def execute_command(command: Dict):
        from pynput.keyboard import Key, Controller as KController
        from pynput.mouse import Button, Controller as MController

        mouse = MController()
        keyboard = KController()
        cmd_type = command.get("type", "")

        try:
            if cmd_type == "mouse_move":
                mouse.position = (command["x"], command["y"])
            elif cmd_type == "mouse_click":
                btn_map = {"left": Button.left, "right": Button.right, "middle": Button.middle}
                btn = btn_map.get(command.get("button", "left"), Button.left)
                pressed = command.get("pressed", True)
                if pressed:
                    mouse.press(btn)
                else:
                    mouse.release(btn)
            elif cmd_type == "mouse_scroll":
                mouse.scroll(command.get("dx", 0), command.get("dy", 0))
            elif cmd_type == "mouse_drag_start":
                btn_map = {"left": Button.left, "right": Button.right, "middle": Button.middle}
                btn = btn_map.get(command.get("button", "left"), Button.left)
                mouse.press(btn)
            elif cmd_type == "mouse_drag_end":
                btn_map = {"left": Button.left, "right": Button.right, "middle": Button.middle}
                btn = btn_map.get(command.get("button", "left"), Button.left)
                mouse.release(btn)
            elif cmd_type == "screen_switch":
                pass
            elif cmd_type == "key_press":
                key = _parse_key(command.get("key", ""))
                if key:
                    keyboard.press(key)
            elif cmd_type == "key_release":
                key = _parse_key(command.get("key", ""))
                if key:
                    keyboard.release(key)
        except Exception as e:
            log.error(f"[InputLeap] 执行命令失败 {cmd_type}: {e}")

    @staticmethod
    def get_name() -> str:
        return "Python (pynput)"


def _parse_key(key_str: str):
    from pynput.keyboard import Key
    key_map = {
        'space': Key.space, 'enter': Key.enter, 'tab': Key.tab,
        'backspace': Key.backspace, 'delete': Key.delete, 'escape': Key.esc,
        'shift': Key.shift, 'shift_r': Key.shift_r,
        'ctrl': Key.ctrl, 'ctrl_r': Key.ctrl_r,
        'alt': Key.alt, 'alt_r': Key.alt_r, 'alt_gr': Key.alt_gr,
        'cmd': Key.cmd, 'cmd_r': Key.cmd_r,
        'up': Key.up, 'down': Key.down, 'left': Key.left, 'right': Key.right,
        'page_up': Key.page_up, 'page_down': Key.page_down,
        'home': Key.home, 'end': Key.end,
        'caps_lock': Key.caps_lock, 'num_lock': Key.num_lock,
        'print_screen': Key.print_screen, 'scroll_lock': Key.scroll_lock,
        'pause': Key.pause, 'insert': Key.insert,
        'menu': Key.menu, 'f1': Key.f1, 'f2': Key.f2, 'f3': Key.f3,
        'f4': Key.f4, 'f5': Key.f5, 'f6': Key.f6, 'f7': Key.f7,
        'f8': Key.f8, 'f9': Key.f9, 'f10': Key.f10, 'f11': Key.f11, 'f12': Key.f12,
    }
    if key_str in key_map:
        return key_map[key_str]
    return key_str


def get_backend():
    try:
        import pynput
        return InputLeapBackend()
    except ImportError:
        return None
