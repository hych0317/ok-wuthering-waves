import ctypes
import json
import os
import re

import numpy as np
import win32gui
from PIL import ImageGrab
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget
from qfluentwidgets import FluentIcon
from qfluentwidgets import ComboBox

from ok import Logger, og
from ok.gui.tasks.ConfigLabelAndWidget import ConfigLabelAndWidget
from src.task.DailyTask import DailyTask
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.BaseCombatTask import BaseCombatTask
from src.task.BaseWWTask import LOGIN_TEXTS
from src.task.MouseResetTask import MouseResetTask

account_pattern = re.compile(r'\*\*\*\*')
logger = Logger.get_logger(__name__)

FOLLOW_DAILY_CONFIG = '默认'
FARM_OPTIONS = [FOLLOW_DAILY_CONFIG, '无音区', '凝素领域', '模拟领域']
TACET_OPTIONS = [FOLLOW_DAILY_CONFIG] + [str(i) for i in range(1, 18)]
FORGERY_OPTIONS = [FOLLOW_DAILY_CONFIG] + [str(i) for i in range(1, 16)]
MATERIAL_OPTIONS = [FOLLOW_DAILY_CONFIG, '共鸣者经验', '武器经验', '贝币']
BOOL_OPTIONS = [FOLLOW_DAILY_CONFIG, '是', '否']
FARM_VALUE_MAP = {
    '无音区': 'Tacet Suppression',
    '凝素领域': 'Forgery Challenge',
    '模拟领域': 'Simulation Challenge',
}
MATERIAL_VALUE_MAP = {
    '共鸣者经验': 'Resonator EXP',
    '武器经验': 'Weapon EXP',
    '贝币': 'Shell Credit',
}
ACCOUNT_CONFIG_FIELDS = (
    ('刷', FARM_OPTIONS),
    ('无音', TACET_OPTIONS),
    ('凝素', FORGERY_OPTIONS),
    ('材料', MATERIAL_OPTIONS),
    ('梦魇', BOOL_OPTIONS),
    ('全梦魇', BOOL_OPTIONS),
)
ACCOUNT_CONFIG_WIDGET_PATCHED = False
ORIGINAL_CONFIG_WIDGET = None


def patch_account_config_widget():
    global ACCOUNT_CONFIG_WIDGET_PATCHED, ORIGINAL_CONFIG_WIDGET
    if ACCOUNT_CONFIG_WIDGET_PATCHED:
        return

    import ok.gui.tasks.ConfigItemFactory as factory

    ORIGINAL_CONFIG_WIDGET = factory.config_widget

    def patched_config_widget(config_type, config_desc, config, key, value, task):
        the_type = config_type.get(key) if config_type is not None else None
        if isinstance(the_type, dict) and the_type.get('type') == 'account_daily_config':
            return AccountDailyConfigRow(config_desc, config, key)
        if isinstance(the_type, dict) and the_type.get('type') == 'hidden_account_daily_config':
            return HiddenAccountConfigRow()
        return ORIGINAL_CONFIG_WIDGET(config_type, config_desc, config, key, value, task)

    factory.config_widget = patched_config_widget
    try:
        import ok.gui.tasks.ConfigCard as config_card
        config_card.config_widget = patched_config_widget
    except Exception:
        pass
    ACCOUNT_CONFIG_WIDGET_PATCHED = True


class AccountDailyConfigRow(ConfigLabelAndWidget):

    def __init__(self, config_desc, config, key: str):
        super().__init__(config_desc, config, key)
        value = config.get(key) or {}
        if not isinstance(value, dict):
            value = {}
        self.combo_boxes = {}
        for field, options in ACCOUNT_CONFIG_FIELDS:
            label = QLabel(og.app.tr(field))
            label.setObjectName('titleLabel')
            label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
            self.add_widget(label, stretch=0)

            combo_box = ComboBox()
            tr_dict = {}
            tr_options = []
            for option in options:
                tr = og.app.tr(option)
                tr_options.append(tr)
                tr_dict[tr] = option
            combo_box.addItems(tr_options)
            current = value.get(field, FOLLOW_DAILY_CONFIG)
            if current not in options:
                current = FOLLOW_DAILY_CONFIG
            combo_box.setCurrentIndex(options.index(current))
            combo_box.currentTextChanged.connect(
                lambda text, field=field, tr_dict=tr_dict: self._field_changed(field, tr_dict.get(text))
            )
            combo_box.setFixedWidth(self._combo_width(combo_box, tr_options))
            self.combo_boxes[field] = (combo_box, options)
            self.add_widget(combo_box, stretch=0)

    def _combo_width(self, combo_box, tr_options):
        fm = QFontMetrics(combo_box.font())
        return max(fm.horizontalAdvance(option) for option in tr_options) + 50

    def _field_changed(self, field, value):
        if value is None:
            return
        current = self.config.get(self.key) or {}
        if not isinstance(current, dict):
            current = {}
        current = dict(current)
        current[field] = value
        self.update_config(current)

    def update_value(self):
        value = self.config.get(self.key) or {}
        if not isinstance(value, dict):
            value = {}
        for field, (combo_box, options) in self.combo_boxes.items():
            current = value.get(field, FOLLOW_DAILY_CONFIG)
            if current not in options:
                current = FOLLOW_DAILY_CONFIG
            combo_box.setCurrentIndex(options.index(current))


class HiddenAccountConfigRow(QWidget):

    def __init__(self):
        super().__init__()
        self.setVisible(False)
        self.setFixedHeight(0)

    def update_value(self):
        pass


class MultiAccountDailyTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        patch_account_config_widget()
        self.name = "多账号一条龙"
        self.group_name = "Daily"
        self.group_icon = FluentIcon.CALENDAR
        self.icon = FluentIcon.PEOPLE
        self.supported_languages = ["zh_CN"]
        self.description = "多账号自动切换，依次执行每日一条龙任务"
        self.default_config = {
            '账号列表': '',
            '使用桌面截图': False,
            '全部完成后退出': False,
        }
        self.config_description = {
            '账号列表': '每行填写一个手机尾号（后4位），自动识别当前登录账号',
            '使用桌面截图': '登录界面使用桌面截图+真实鼠标点击（如果默认方式无法识别登录界面请开启）',
            '全部完成后退出': '所有账号完成后退出游戏并关闭软件',
        }
        self.config_type = {
            '账号列表': {'type': 'text_edit'},
        }
        self.add_exit_after_config()
        self._add_account_config_options()
        self.done_set = set()
        self.all_accounts = set()
        self.support_schedule_task = True

    @property
    def _use_desktop(self):
        return self.config.get('使用桌面截图', False)

    def run(self):
        WWOneTimeTask.run(self)
        accounts = self._parse_account_list()

        if not accounts:
            self._run_daily_for_account(None)
            return

        detected = self._switch_to_login_and_detect()
        queue = self._account_run_queue(accounts, detected)
        self.log_info(f'本次执行账号队列：{", ".join(f"****{suffix}" for suffix in queue)}')

        in_game = False
        for index, suffix in enumerate(queue):
            if index > 0 and in_game:
                self.log_info(f'准备切换到下一个账号：****{suffix}')
                self._switch_to_login()
                in_game = False

            if index == 0 and suffix == detected:
                self._login_selected_account(suffix)
            else:
                self._select_and_login_account(suffix)
            in_game = True
            self._run_daily_for_account(suffix)
            remaining = queue[index + 1:]
            self.log_info(f'剩余账号：{", ".join(f"****{item}" for item in remaining) or "无"}')

        self.log_info('所有账号一条龙已完成')

        if self.config.get('全部完成后退出'):
            if in_game:
                self._exit_game()
            self._exit_software()

    def _account_run_queue(self, accounts, detected):
        if detected and detected in accounts:
            return [detected] + [suffix for suffix in accounts if suffix != detected]
        if detected:
            self.log_info(f'当前选中账号 ****{detected} 不在账号列表中，改为从账号列表逐个选择执行')
        else:
            self.log_info('无法识别当前账号，改为从账号列表逐个选择执行')
        return list(accounts)

    def _add_account_config_options(self):
        accounts = self._read_configured_accounts()
        for suffix in accounts:
            key = self._account_config_key(suffix)
            self.default_config.setdefault(key, self._default_account_daily_config())
            self.config_description[key] = '默认=使用日常一条龙配置'
            self.config_type[key] = {'type': 'account_daily_config'}
            self.config_type[f'{suffix} 配置'] = {'type': 'hidden_account_daily_config'}
            for legacy_key in self._legacy_account_config_keys(suffix):
                self.config_type[legacy_key] = {'type': 'hidden_account_daily_config'}

    def _account_config_key(self, suffix):
        return suffix

    def _default_account_daily_config(self):
        return {field: FOLLOW_DAILY_CONFIG for field, _ in ACCOUNT_CONFIG_FIELDS}

    def _legacy_account_config_keys(self, suffix):
        prefix = f'{suffix} '
        return [f'{prefix}{field}' for field, _ in ACCOUNT_CONFIG_FIELDS]

    def _read_configured_accounts(self):
        raw = ''
        if isinstance(getattr(self, 'config', None), dict):
            raw = self.config.get('账号列表', '') or ''
        if not raw.strip():
            config_path = os.path.join(os.getcwd(), 'configs', 'MultiAccountDailyTask.json')
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    raw = json.load(f).get('账号列表', '') or ''
            except Exception:
                raw = ''
        return self._parse_account_text(raw)

    def _parse_account_text(self, raw):
        result = []
        for line in (raw or '').splitlines():
            line = line.strip()
            if line.isdigit() and len(line) == 4 and line not in result:
                result.append(line)
        return result

    def _run_daily_for_account(self, suffix):
        config_override = self._daily_config_override(suffix)
        if suffix:
            self.log_info(f'执行账号 ****{suffix} 日常配置：{config_override or "默认日常一条龙"}')

        daily_task = self.get_task_by_class(DailyTask)
        original_config = daily_task.config
        if config_override:
            daily_task.config = dict(original_config)
            daily_task.config.update(config_override)
        try:
            daily_task.run()
        finally:
            daily_task.config = original_config

    def _daily_config_override(self, suffix):
        if not suffix:
            return {}
        prefix = f'{suffix} '
        account_config = self.config.get(self._account_config_key(suffix))
        if not isinstance(account_config, dict):
            account_config = self.config.get(f'{suffix} 配置')
        if not isinstance(account_config, dict):
            account_config = {}
        override = {}
        farm = account_config.get('刷', self.config.get(f'{prefix}刷', FOLLOW_DAILY_CONFIG))
        tacet = account_config.get('无音', self.config.get(f'{prefix}无音', FOLLOW_DAILY_CONFIG))
        forgery = account_config.get('凝素', self.config.get(f'{prefix}凝素', FOLLOW_DAILY_CONFIG))
        material = account_config.get('材料', self.config.get(f'{prefix}材料', FOLLOW_DAILY_CONFIG))
        nightmare = account_config.get('梦魇', self.config.get(f'{prefix}梦魇', FOLLOW_DAILY_CONFIG))
        all_nightmare = account_config.get('全梦魇', self.config.get(f'{prefix}全梦魇', FOLLOW_DAILY_CONFIG))

        if farm != FOLLOW_DAILY_CONFIG:
            override['Which to Farm'] = FARM_VALUE_MAP[farm]
        if tacet != FOLLOW_DAILY_CONFIG:
            override['Which Tacet Suppression to Farm'] = int(tacet)
        if forgery != FOLLOW_DAILY_CONFIG:
            override['Which Forgery Challenge to Farm'] = int(forgery)
        if material != FOLLOW_DAILY_CONFIG:
            override['Material Selection'] = MATERIAL_VALUE_MAP[material]
        if nightmare != FOLLOW_DAILY_CONFIG:
            override['Farm Nightmare Nest for Daily Echo'] = nightmare == '是'
        if all_nightmare != FOLLOW_DAILY_CONFIG:
            override['Auto Farm all Nightmare Nest'] = all_nightmare == '是'
        return override

    def _parse_account_list(self):
        raw = self.config.get('账号列表', '')
        if not raw or not raw.strip():
            return []
        result = []
        for idx, line in enumerate(raw.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            if not line.isdigit():
                self.log_error(f'账号列表第{idx}行格式错误（必须为纯数字）："{line}"')
                continue
            if len(line) != 4:
                self.log_error(f'账号列表第{idx}行格式错误（应为4位尾号）："{line}"')
                continue
            result.append(line)
        if not result:
            self.log_error('账号列表中没有有效账号，请每行填写一个4位手机尾号')
        return result

    def _make_masked_pattern(self, suffix):
        return re.compile(rf'\d+\*+{re.escape(suffix)}')

    # ── Desktop screenshot & real mouse (for CEF login overlay) ──────

    def _bring_game_to_front(self):
        """Bring the game window to foreground so desktop screenshot captures it."""
        hwnd = self.hwnd.hwnd
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        self.sleep(0.3)

    def _screenshot_login_screen(self):
        """Desktop screenshot of game client area (captures CEF overlay)."""
        self._bring_game_to_front()
        hwnd = self.hwnd.hwnd
        _, _, client_w, client_h = win32gui.GetClientRect(hwnd)
        client_x, client_y = win32gui.ClientToScreen(hwnd, (0, 0))
        img = ImageGrab.grab(bbox=(client_x, client_y, client_x + client_w, client_y + client_h))
        return np.array(img)[..., ::-1]  # RGB→BGR

    def _ocr_login_screen(self, **kwargs):
        """OCR on desktop screenshot (framework capture misses CEF overlay)."""
        frame = self._screenshot_login_screen()
        return self.ocr(frame=frame, **kwargs)

    def _login_dialog_click(self, offset_x, offset_y, after_sleep=0.5):
        """Real mouse click at game-window-center + pixel offset.
        The login dialog is fixed 750x450 and always centered on the game window,
        so center-based offsets work at any resolution."""
        hwnd = self.hwnd.hwnd
        _, _, client_w, client_h = win32gui.GetClientRect(hwnd)
        client_x, client_y = win32gui.ClientToScreen(hwnd, (0, 0))
        abs_x = client_x + client_w // 2 + int(offset_x)
        abs_y = client_y + client_h // 2 + int(offset_y)
        self._bring_game_to_front()
        ctypes.windll.user32.SetCursorPos(abs_x, abs_y)
        self.sleep(0.05)
        ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)  # LEFTDOWN
        self.sleep(0.05)
        ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)  # LEFTUP
        if after_sleep > 0:
            self.sleep(after_sleep)

    # ── Unified helpers that branch on config ────────────────────────

    def _login_ocr(self):
        """OCR the login screen: desktop screenshot or framework capture."""
        if self._use_desktop:
            return self._ocr_login_screen()
        return self.ocr()

    def _click_center_offset(self, offset_x, offset_y, after_sleep=0.5):
        """Click at window-center + offset: real mouse or framework click."""
        if self._use_desktop:
            self._login_dialog_click(offset_x, offset_y, after_sleep=after_sleep)
        else:
            h, w = self.frame.shape[:2]
            rel_x = 0.5 + offset_x / w
            rel_y = 0.5 + offset_y / h
            self.click_relative(rel_x, rel_y, after_sleep=after_sleep)

    # ── Account switching logic ──────────────────────────────────────

    def _login_page_state(self, texts=None):
        texts = texts if texts is not None else self._login_ocr()
        right = self.box_of_screen(0.82, 0.15, 0.99, 0.75)
        center = self.box_of_screen(0.3, 0.3, 0.7, 0.8)

        if self.find_boxes(texts, match=re.compile(r'\d{3}\*+\d{4}')):
            return 'account_switch_overlay'
        if self.find_boxes(texts, boundary=center, match=['其他登录方式', '登录']):
            return 'account_switch_overlay'
        if self.find_boxes(texts, boundary=center, match=re.compile(r'确认登出')):
            return 'logout_confirm_dialog'
        if self.find_boxes(texts, match='点击连接') and self.find_boxes(texts, boundary=right, match='账号'):
            return 'connected_title_page'
        if self.find_boxes(texts, boundary=right, match=re.compile(r'登[入录]')):
            return 'logged_out_title_page'
        if self.find_boxes(texts, match=re.compile(r'Windows.{0,3}Product', re.IGNORECASE)):
            return 'login_webview'
        return None

    def _click_login_relative(self, rel_x, rel_y, after_sleep=0.5):
        if self._use_desktop:
            hwnd = self.hwnd.hwnd
            _, _, client_w, client_h = win32gui.GetClientRect(hwnd)
            self._login_dialog_click((rel_x - 0.5) * client_w, (rel_y - 0.5) * client_h, after_sleep=after_sleep)
        else:
            self.click_relative(rel_x, rel_y, after_sleep=after_sleep)

    def _click_login_text_or_relative(self, texts, match, rel_x, rel_y, boundary=None, after_sleep=0.5):
        boxes = self.find_boxes(texts, boundary=boundary, match=match) if boundary else self.find_boxes(texts, match=match)
        if boxes:
            box = max(boxes, key=lambda item: item.y)
            if self._use_desktop:
                hwnd = self.hwnd.hwnd
                _, _, client_w, client_h = win32gui.GetClientRect(hwnd)
                box_cx, box_cy = box.center()
                self._login_dialog_click(box_cx - client_w // 2, box_cy - client_h // 2, after_sleep=after_sleep)
            else:
                self.click(box, after_sleep=after_sleep)
            return True
        self._click_login_relative(rel_x, rel_y, after_sleep=after_sleep)
        return False

    def _advance_title_login_to_account_switch(self):
        texts = self._login_ocr()
        state = self._login_page_state(texts)
        if state:
            self.log_info(f'login page state: {state}')
        if state == 'account_switch_overlay':
            self._expect_logged_out_title_login = False
            return True
        if state == 'logout_confirm_dialog':
            self.log_info('确认登出当前账号')
            self._click_login_text_or_relative(
                texts, re.compile(r'确认登出'), 0.66, 0.75,
                boundary=self.box_of_screen(0.3, 0.3, 0.8, 0.9), after_sleep=2
            )
            self._expect_logged_out_title_login = True
            return False
        if state == 'connected_title_page':
            self.log_info('标题页已登录，打开账号登出确认')
            self._click_login_text_or_relative(
                texts, '账号', 0.945, 0.62,
                boundary=self.box_of_screen(0.82, 0.15, 0.99, 0.75), after_sleep=1
            )
            self.wait_until(
                lambda: self._login_page_state(self._login_ocr()) == 'logout_confirm_dialog',
                time_out=10, raise_if_not_found=False
            )
            texts = self._login_ocr()
            self.log_info('确认登出当前账号')
            self._click_login_text_or_relative(
                texts, re.compile(r'确认登出'), 0.66, 0.75,
                boundary=self.box_of_screen(0.3, 0.3, 0.8, 0.9), after_sleep=2
            )
            self._expect_logged_out_title_login = True
            return False
        if state == 'logged_out_title_page':
            self.log_info('标题页未登录，打开账号登录面板')
            self._expect_logged_out_title_login = False
            self._click_login_text_or_relative(
                texts, re.compile(r'登[入录]'), 0.945, 0.50,
                boundary=self.box_of_screen(0.82, 0.15, 0.99, 0.75), after_sleep=3
            )
            return False
        if getattr(self, '_expect_logged_out_title_login', False):
            self.log_info('登出后未识别到登入按钮，使用坐标打开账号登录面板')
            self._expect_logged_out_title_login = False
            self._click_login_text_or_relative(
                texts, re.compile(r'登[入录]'), 0.945, 0.50,
                boundary=self.box_of_screen(0.82, 0.15, 0.99, 0.75), after_sleep=3
            )
            return False
        if state == 'login_webview':
            self.log_info('login webview detected, wait without clicking to avoid entering game')
            self.sleep(1)
            return False
        return False

    def _detect_login_page_state(self, time_out=5):
        state = [None]

        def detect():
            state[0] = self._login_page_state()
            return bool(state[0])

        if self.wait_until(detect, time_out=time_out, raise_if_not_found=False):
            self.log_info(f'detected login page state: {state[0]}')
            return state[0]
        return None

    def _advance_login_page_to_account_switch(self, time_out=60):
        if self.wait_until(
                self._advance_title_login_to_account_switch,
                time_out=time_out, raise_if_not_found=False):
            self.log_info('已返回登录界面')
            return True
        return False

    def _is_terminal_menu_open(self):
        return bool(self.find_boxes(self.ocr(), match='终端'))

    def _open_terminal_menu(self):
        if self._is_terminal_menu_open():
            return True
        self.log_info('尝试按 ESC 打开终端菜单')
        self.send_key('esc', after_sleep=1.5)
        if self.wait_until(self._is_terminal_menu_open, time_out=10, raise_if_not_found=False):
            return True
        self.log_info('尝试点击菜单按钮打开终端菜单')
        self.open_esc_menu()
        if self.wait_until(self._is_terminal_menu_open, time_out=10, raise_if_not_found=False):
            return True
        self.log_info('尝试点击右上角终端入口')
        self.click_relative(0.955, 0.04, after_sleep=1.5)
        return self.wait_until(self._is_terminal_menu_open, time_out=10, raise_if_not_found=False)

    def _switch_to_login(self):
        self.log_info('正在返回登录界面')
        if self._detect_login_page_state(time_out=5):
            if not self._advance_login_page_to_account_switch(time_out=60):
                raise Exception('Can not open account switch login panel!')
            return

        self.log_info('未识别到登录界面，按游戏内流程返回登录')
        self.ensure_main(time_out=180)
        if not self._open_terminal_menu():
            raise Exception('Can not open terminal menu from main world!')
        self.click_relative(0.04, 0.96, after_sleep=1)
        self.wait_until(
            lambda: bool(self.find_boxes(self.ocr(), match='返回登录')),
            time_out=10, raise_if_not_found=False
        )
        texts = self.ocr()
        if btn := self.find_boxes(texts, match='返回登录'):
            self.click(btn, after_sleep=3)
        else:
            self.click_relative(0.67, 0.63, after_sleep=3)

        if not self._advance_login_page_to_account_switch(time_out=60):
            raise Exception('Can not open account switch login panel!')

    def _switch_to_login_and_detect(self):
        self._switch_to_login()
        suffix = self._detect_current_account_from_login()
        if suffix:
            self.log_info(f'检测到已完成账号：****{suffix}')
        else:
            self.log_info('无法识别当前登录账号')
        return suffix

    def _detect_current_account_from_login(self):
        texts = self._login_ocr()
        pattern = re.compile(r'\d{3}\*+(\d{4})')
        for box in texts:
            m = pattern.search(box.name)
            if m:
                return m.group(1)
        return None

    def _selected_account_anchor_y(self):
        return self.frame.shape[0] * 0.5 - 43

    def _selected_account_y_tolerance(self):
        return max(35, self.frame.shape[0] * 0.035)

    def _detect_selected_account_from_login(self, texts=None):
        texts = texts if texts is not None else self._login_ocr()
        pattern = re.compile(r'\d{3}\*+(\d{4})')
        selected_y = self._selected_account_anchor_y()
        tolerance = self._selected_account_y_tolerance()
        account_panel = self.box_of_screen(0.3, 0.25, 0.75, 0.65)
        candidates = []
        for box in texts:
            m = pattern.search(box.name)
            if not m:
                continue
            if not self.find_boxes([box], boundary=account_panel, match=pattern):
                continue
            if abs(box.center()[1] - selected_y) <= tolerance:
                candidates.append((box, m.group(1)))
        if not candidates:
            return None
        return min(candidates, key=lambda item: abs(item[0].center()[1] - selected_y))[1]

    def _click_account_in_list(self, suffix):
        pattern = self._make_masked_pattern(suffix)
        texts = self._login_ocr()
        selected_y = self._selected_account_anchor_y()
        tolerance = self._selected_account_y_tolerance()
        list_panel = self.box_of_screen(0.25, 0.15, 0.75, 0.9)
        candidates = []
        for box in texts:
            if not pattern.search(box.name):
                continue
            if not self.find_boxes([box], boundary=list_panel, match=pattern):
                continue
            if abs(box.center()[1] - selected_y) <= tolerance:
                continue
            candidates.append(box)
        if not candidates:
            return False

        box = min(candidates, key=lambda item: abs(item.center()[1] - selected_y))
        box_cx, box_cy = box.center()
        click_x = box_cx
        if self._use_desktop:
            hwnd = self.hwnd.hwnd
            _, _, client_w, client_h = win32gui.GetClientRect(hwnd)
            max_x = client_w // 2 + 200
            click_x = min(click_x, max_x)
            self._login_dialog_click(click_x - client_w // 2, box_cy - client_h // 2, after_sleep=0.5)
        else:
            h, w = self.frame.shape[:2]
            self.click_relative(click_x / w, box_cy / h, after_sleep=0.5)
        self.log_info(f'点击账号列表项：****{suffix} ({int(click_x)}, {int(box_cy)})')
        return True

    def _selected_account_matches(self, suffix, selected_account=None):
        selected = self._detect_selected_account_from_login()
        if selected_account is not None:
            selected_account[0] = selected
        return selected == suffix

    def _login_selected_account(self, suffix):
        self.log_info(f'正在登录当前选中账号{f"：****{suffix}" if suffix else ""}')
        texts = self._login_ocr()
        login_btn = self.find_boxes(texts, boundary=self.box_of_screen(0.3, 0.3, 0.7, 0.8), match=LOGIN_TEXTS)
        if login_btn and not self._use_desktop:
            self.click(login_btn, after_sleep=3)
        elif login_btn and self._use_desktop:
            box_cx, box_cy = login_btn[0].center()
            hwnd = self.hwnd.hwnd
            _, _, client_w, client_h = win32gui.GetClientRect(hwnd)
            self._login_dialog_click(box_cx - client_w // 2, box_cy - client_h // 2, after_sleep=3)
        else:
            self._click_center_offset(0, 95, after_sleep=3)
        self._logged_in = False
        self.ensure_main(time_out=180)
        self.log_info(f'登录成功{f"：****{suffix}" if suffix else ""}')

    def _exit_game(self):
        self.log_info('所有账号已完成，正在退出游戏')
        self.send_key('esc', after_sleep=1.5)
        self.wait_until(
            lambda: bool(self.find_boxes(self.ocr(), match='终端')),
            time_out=10, raise_if_not_found=False
        )
        self.click_relative(0.04, 0.96, after_sleep=1)
        self.wait_until(
            lambda: bool(self.find_boxes(self.ocr(), match='退出游戏')),
            time_out=10, raise_if_not_found=False
        )
        texts = self.ocr()
        if btn := self.find_boxes(texts, match='退出游戏'):
            self.click(btn, after_sleep=2)
        else:
            self.click_relative(0.32, 0.63, after_sleep=2)

    def _exit_software(self):
        self.log_info('正在关闭软件')
        self.exit_after_task = True

    def _click_login_button(self):
        texts = self._login_ocr()
        login_btn = self.find_boxes(texts, boundary=self.box_of_screen(0.3, 0.3, 0.7, 0.8), match=LOGIN_TEXTS)
        if login_btn and not self._use_desktop:
            self.click(login_btn, after_sleep=3)
        elif login_btn and self._use_desktop:
            box_cx, box_cy = login_btn[0].center()
            hwnd = self.hwnd.hwnd
            _, _, client_w, client_h = win32gui.GetClientRect(hwnd)
            self._login_dialog_click(box_cx - client_w // 2, box_cy - client_h // 2, after_sleep=3)
        else:
            self._click_center_offset(0, 95, after_sleep=3)
        return True

    def _select_and_login_account(self, suffix):
        self.log_info(f'正在选择账号：****{suffix}')
        mouse_reset_task = self.executor.get_task_by_class(MouseResetTask)
        mouse_reset_was_enabled = mouse_reset_task.enabled if mouse_reset_task else False
        if mouse_reset_was_enabled:
            mouse_reset_task.disable()
        try:
            selected_account = [None]
            max_retries = 5
            for attempt in range(1, max_retries + 1):
                if attempt > 1:
                    self.log_info(f'账号 ****{suffix} 未切换成功，重试选择（{attempt - 1}/{max_retries - 1}）')
                self.sleep(1)
                self._click_center_offset(270, -43, after_sleep=1)
                self.wait_until(
                    lambda: self._click_account_in_list(suffix),
                    time_out=10, raise_if_not_found=True
                )
                if self.wait_until(
                    lambda: self._selected_account_matches(suffix, selected_account),
                    time_out=5, raise_if_not_found=False
                ):
                    self.log_info(f'确认选中账号：****{suffix}')
                    break
            else:
                selected = selected_account[0]
                raise Exception(
                    f'Failed to select account ****{suffix} after {max_retries - 1} retries, '
                    f'current selected account is {f"****{selected}" if selected else "unknown"}'
                )
            self._click_login_button()
            self._logged_in = False
            self.ensure_main(time_out=180)
            self.log_info(f'登录成功：****{suffix}')
        finally:
            if mouse_reset_was_enabled:
                mouse_reset_task.enable()
