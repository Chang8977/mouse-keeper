"""UI translations.

Deliberately just a dict plus a ``t()`` rather than gettext and .po files: there
are only a few dozen strings, so compiling .mo files and maintaining a locale
tree would cost far more than it returns, and a onedir exe would need extra
resource-path handling on top.

English is the base language. A string missing from another language falls back
to English rather than showing a raw key.

Log messages do not go through here. Logs exist for troubleshooting, fixed
English is simpler, and it keeps a single log from ending up half in one
language and half in another because someone changed a setting midway.
"""

from __future__ import annotations

import ctypes
from typing import Any

#: language code -> (display name, font)
#: The font is per language: YaHei has no Hangul and Segoe UI has no CJK
#: ideographs, so one font for everything would render tofu boxes.
LANGUAGES: dict[str, tuple[str, str]] = {
    "en": ("English", "Segoe UI"),
    "zh-Hans": ("简体中文", "Microsoft YaHei UI"),
    "zh-Hant": ("繁體中文", "Microsoft JhengHei UI"),
    "ja": ("日本語", "Yu Gothic UI"),
    "ko": ("한국어", "Malgun Gothic"),
    "de": ("Deutsch", "Segoe UI"),
    "fr": ("Français", "Segoe UI"),
    "es": ("Español", "Segoe UI"),
    "pt": ("Português", "Segoe UI"),
    "ru": ("Русский", "Segoe UI"),
}

DEFAULT = "en"

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "state_running": "Running",
        "state_paused": "Paused",
        "state_stopped": "Auto-stopped",
        "state_locked": "Locked",
        "detail_start": "Click here to start",
        "detail_limit": "Run-time limit reached",
        "detail_locked": "Inactive while locked, resumes automatically",
        "detail_uptime": "Up {d}",
        "detail_injections": "{n} moves",
        "detail_idle": "idle {n}s",
        "dur_hm": "{h}h {m}m",
        "dur_ms": "{m}m {s}s",
        "dur_s": "{s}s",
        "row_mode": "Mode",
        "opt_smart": "Smart",
        "opt_force": "Always",
        "row_cadence": "Interval · sec",
        "row_autostop": "Auto-stop · hours",
        "opt_unlimited": "Off",
        "row_keep_display": "Also block screen-off / sleep",
        "row_autostart": "Start with Windows",
        "row_autostart_stale": "Start with Windows (broken — click to fix)",
        "row_logging": "Write log file",
        "row_open_config": "Open config folder",
        "row_language": "Language",
        "row_back": "Back",
        "row_quit": "Quit",
        "notify_started": "Keep-alive started",
        "notify_paused": "Keep-alive paused",
        "notify_hotkey_fail": "Hotkey unavailable: {err}",
        "notify_autostop": "Ran for {h:g} hours, keep-alive stopped automatically.",
        "notify_autostart_on": "Will start with Windows",
        "notify_autostart_off": "Removed from startup",
        "notify_autostart_fail": "Could not change startup setting: {err}",
        "msg_already_running": "{app} is already running — check the system tray.",
        "msg_crashed": "{app} exited unexpectedly:\n\n{err}",
    },
    "zh-Hans": {
        "state_running": "运行中",
        "state_paused": "已暂停",
        "state_stopped": "已自动停止",
        "state_locked": "已锁屏",
        "detail_start": "点这里开始保活",
        "detail_limit": "已达到运行时长上限",
        "detail_locked": "锁屏期间无效，解锁后自动继续",
        "detail_uptime": "已运行 {d}",
        "detail_injections": "移动 {n} 次",
        "detail_idle": "空闲 {n}s",
        "dur_hm": "{h} 小时 {m} 分",
        "dur_ms": "{m} 分 {s} 秒",
        "dur_s": "{s} 秒",
        "row_mode": "模式",
        "opt_smart": "智能",
        "opt_force": "始终",
        "row_cadence": "间隔 · 秒",
        "row_autostop": "自动停止 · 小时",
        "opt_unlimited": "关",
        "row_keep_display": "同时阻止息屏 / 睡眠",
        "row_autostart": "开机自启",
        "row_autostart_stale": "开机自启（已失效，点一下修复）",
        "row_logging": "记录日志",
        "row_open_config": "打开配置文件夹",
        "row_language": "语言",
        "row_back": "返回",
        "row_quit": "退出",
        "notify_started": "已开始保活",
        "notify_paused": "已暂停保活",
        "notify_hotkey_fail": "热键不可用：{err}",
        "notify_autostop": "已连续运行 {h:g} 小时，自动停止保活。",
        "notify_autostart_on": "已设为开机自启",
        "notify_autostart_off": "已取消开机自启",
        "notify_autostart_fail": "设置开机自启失败：{err}",
        "msg_already_running": "{app} 已经在运行了，请看系统托盘。",
        "msg_crashed": "{app} 异常退出：\n\n{err}",
    },
    "zh-Hant": {
        "state_running": "執行中",
        "state_paused": "已暫停",
        "state_stopped": "已自動停止",
        "state_locked": "已鎖定",
        "detail_start": "點這裡開始保持活動",
        "detail_limit": "已達到執行時間上限",
        "detail_locked": "鎖定期間無效，解鎖後自動繼續",
        "detail_uptime": "已執行 {d}",
        "detail_injections": "移動 {n} 次",
        "detail_idle": "閒置 {n}s",
        "dur_hm": "{h} 小時 {m} 分",
        "dur_ms": "{m} 分 {s} 秒",
        "dur_s": "{s} 秒",
        "row_mode": "模式",
        "opt_smart": "智慧",
        "opt_force": "永遠",
        "row_cadence": "間隔 · 秒",
        "row_autostop": "自動停止 · 小時",
        "opt_unlimited": "關",
        "row_keep_display": "同時防止螢幕關閉 / 睡眠",
        "row_autostart": "開機時啟動",
        "row_autostart_stale": "開機時啟動（已失效，點一下修復）",
        "row_logging": "寫入記錄檔",
        "row_open_config": "開啟設定資料夾",
        "row_language": "語言",
        "row_back": "返回",
        "row_quit": "結束",
        "notify_started": "已開始保持活動",
        "notify_paused": "已暫停保持活動",
        "notify_hotkey_fail": "快速鍵無法使用：{err}",
        "notify_autostop": "已連續執行 {h:g} 小時，自動停止。",
        "notify_autostart_on": "已設為開機時啟動",
        "notify_autostart_off": "已取消開機時啟動",
        "notify_autostart_fail": "設定開機啟動失敗：{err}",
        "msg_already_running": "{app} 已經在執行，請查看系統匣。",
        "msg_crashed": "{app} 異常結束：\n\n{err}",
    },
    "ja": {
        "state_running": "実行中",
        "state_paused": "一時停止中",
        "state_stopped": "自動停止しました",
        "state_locked": "ロック中",
        "detail_start": "ここをクリックして開始",
        "detail_limit": "実行時間の上限に達しました",
        "detail_locked": "ロック中は無効です。解除後に自動で再開します",
        "detail_uptime": "稼働 {d}",
        "detail_injections": "{n} 回移動",
        "detail_idle": "アイドル {n}s",
        "dur_hm": "{h} 時間 {m} 分",
        "dur_ms": "{m} 分 {s} 秒",
        "dur_s": "{s} 秒",
        "row_mode": "モード",
        "opt_smart": "スマート",
        "opt_force": "常時",
        "row_cadence": "間隔 · 秒",
        "row_autostop": "自動停止 · 時間",
        "opt_unlimited": "なし",
        "row_keep_display": "画面オフ / スリープも防ぐ",
        "row_autostart": "Windows 起動時に開始",
        "row_autostart_stale": "Windows 起動時に開始（無効 — クリックで修復）",
        "row_logging": "ログを記録する",
        "row_open_config": "設定フォルダーを開く",
        "row_language": "言語",
        "row_back": "戻る",
        "row_quit": "終了",
        "notify_started": "キープアライブを開始しました",
        "notify_paused": "キープアライブを一時停止しました",
        "notify_hotkey_fail": "ホットキーを使用できません: {err}",
        "notify_autostop": "{h:g} 時間連続で実行したため自動停止しました。",
        "notify_autostart_on": "Windows 起動時に開始します",
        "notify_autostart_off": "スタートアップから削除しました",
        "notify_autostart_fail": "スタートアップ設定に失敗しました: {err}",
        "msg_already_running": "{app} はすでに実行中です。通知領域を確認してください。",
        "msg_crashed": "{app} が予期せず終了しました:\n\n{err}",
    },
    "ko": {
        "state_running": "실행 중",
        "state_paused": "일시 중지됨",
        "state_stopped": "자동 중지됨",
        "state_locked": "잠김",
        "detail_start": "여기를 클릭하여 시작",
        "detail_limit": "실행 시간 한도에 도달했습니다",
        "detail_locked": "잠금 중에는 작동하지 않으며 해제 후 자동 재개됩니다",
        "detail_uptime": "가동 {d}",
        "detail_injections": "{n}회 이동",
        "detail_idle": "유휴 {n}s",
        "dur_hm": "{h}시간 {m}분",
        "dur_ms": "{m}분 {s}초",
        "dur_s": "{s}초",
        "row_mode": "모드",
        "opt_smart": "스마트",
        "opt_force": "항상",
        "row_cadence": "간격 · 초",
        "row_autostop": "자동 중지 · 시간",
        "opt_unlimited": "끔",
        "row_keep_display": "화면 꺼짐 / 절전도 방지",
        "row_autostart": "Windows 시작 시 실행",
        "row_autostart_stale": "Windows 시작 시 실행 (손상됨 — 클릭하여 복구)",
        "row_logging": "로그 파일 기록",
        "row_open_config": "설정 폴더 열기",
        "row_language": "언어",
        "row_back": "뒤로",
        "row_quit": "종료",
        "notify_started": "유지 기능을 시작했습니다",
        "notify_paused": "유지 기능을 일시 중지했습니다",
        "notify_hotkey_fail": "단축키를 사용할 수 없습니다: {err}",
        "notify_autostop": "{h:g}시간 연속 실행되어 자동으로 중지했습니다.",
        "notify_autostart_on": "Windows 시작 시 실행됩니다",
        "notify_autostart_off": "시작 프로그램에서 제거했습니다",
        "notify_autostart_fail": "시작 프로그램 설정 실패: {err}",
        "msg_already_running": "{app}이(가) 이미 실행 중입니다. 알림 영역을 확인하세요.",
        "msg_crashed": "{app}이(가) 예기치 않게 종료되었습니다:\n\n{err}",
    },
    "de": {
        "state_running": "Aktiv",
        "state_paused": "Pausiert",
        "state_stopped": "Autom. gestoppt",
        "state_locked": "Gesperrt",
        "detail_start": "Zum Starten hier klicken",
        "detail_limit": "Laufzeitlimit erreicht",
        "detail_locked": "Bei Sperre inaktiv, setzt automatisch fort",
        "detail_uptime": "Läuft {d}",
        "detail_injections": "{n} Bewegungen",
        "detail_idle": "inaktiv {n}s",
        "dur_hm": "{h} Std. {m} Min.",
        "dur_ms": "{m} Min. {s} Sek.",
        "dur_s": "{s} Sek.",
        "row_mode": "Modus",
        "opt_smart": "Smart",
        "opt_force": "Immer",
        "row_cadence": "Intervall · Sek.",
        "row_autostop": "Auto-Stopp · Std.",
        "opt_unlimited": "Aus",
        "row_keep_display": "Bildschirm / Ruhezustand blockieren",
        "row_autostart": "Mit Windows starten",
        "row_autostart_stale": "Mit Windows starten (defekt — klicken)",
        "row_logging": "Protokoll schreiben",
        "row_open_config": "Konfigurationsordner öffnen",
        "row_language": "Sprache",
        "row_back": "Zurück",
        "row_quit": "Beenden",
        "notify_started": "Aktivhaltung gestartet",
        "notify_paused": "Aktivhaltung pausiert",
        "notify_hotkey_fail": "Tastenkürzel nicht verfügbar: {err}",
        "notify_autostop": "Nach {h:g} Stunden automatisch gestoppt.",
        "notify_autostart_on": "Startet jetzt mit Windows",
        "notify_autostart_off": "Aus dem Autostart entfernt",
        "notify_autostart_fail": "Autostart konnte nicht geändert werden: {err}",
        "msg_already_running": "{app} läuft bereits — siehe Infobereich.",
        "msg_crashed": "{app} wurde unerwartet beendet:\n\n{err}",
    },
    "fr": {
        "state_running": "Actif",
        "state_paused": "En pause",
        "state_stopped": "Arrêt automatique",
        "state_locked": "Verrouillé",
        "detail_start": "Cliquez ici pour démarrer",
        "detail_limit": "Durée maximale atteinte",
        "detail_locked": "Inactif si verrouillé, reprend automatiquement",
        "detail_uptime": "Actif depuis {d}",
        "detail_injections": "{n} mouvements",
        "detail_idle": "inactif {n}s",
        "dur_hm": "{h} h {m} min",
        "dur_ms": "{m} min {s} s",
        "dur_s": "{s} s",
        "row_mode": "Mode",
        "opt_smart": "Intelligent",
        "opt_force": "Toujours",
        "row_cadence": "Intervalle · s",
        "row_autostop": "Arrêt auto · h",
        "opt_unlimited": "Désactivé",
        "row_keep_display": "Empêcher écran / veille",
        "row_autostart": "Démarrer avec Windows",
        "row_autostart_stale": "Démarrer avec Windows (invalide — cliquez)",
        "row_logging": "Écrire un journal",
        "row_open_config": "Ouvrir le dossier de config",
        "row_language": "Langue",
        "row_back": "Retour",
        "row_quit": "Quitter",
        "notify_started": "Maintien activé",
        "notify_paused": "Maintien en pause",
        "notify_hotkey_fail": "Raccourci indisponible : {err}",
        "notify_autostop": "Arrêt automatique après {h:g} heures.",
        "notify_autostart_on": "Démarrera avec Windows",
        "notify_autostart_off": "Retiré du démarrage",
        "notify_autostart_fail": "Échec du réglage de démarrage : {err}",
        "msg_already_running": "{app} est déjà en cours — voir la zone de notification.",
        "msg_crashed": "{app} s'est arrêté de façon inattendue :\n\n{err}",
    },
    "es": {
        "state_running": "Activo",
        "state_paused": "En pausa",
        "state_stopped": "Detenido automáticamente",
        "state_locked": "Bloqueado",
        "detail_start": "Haz clic aquí para iniciar",
        "detail_limit": "Límite de tiempo alcanzado",
        "detail_locked": "Inactivo al bloquear, se reanuda solo",
        "detail_uptime": "Activo {d}",
        "detail_injections": "{n} movimientos",
        "detail_idle": "inactivo {n}s",
        "dur_hm": "{h} h {m} min",
        "dur_ms": "{m} min {s} s",
        "dur_s": "{s} s",
        "row_mode": "Modo",
        "opt_smart": "Inteligente",
        "opt_force": "Siempre",
        "row_cadence": "Intervalo · s",
        "row_autostop": "Parada auto · h",
        "opt_unlimited": "No",
        "row_keep_display": "Evitar apagado / suspensión",
        "row_autostart": "Iniciar con Windows",
        "row_autostart_stale": "Iniciar con Windows (roto — haz clic)",
        "row_logging": "Guardar registro",
        "row_open_config": "Abrir carpeta de configuración",
        "row_language": "Idioma",
        "row_back": "Atrás",
        "row_quit": "Salir",
        "notify_started": "Mantenimiento iniciado",
        "notify_paused": "Mantenimiento en pausa",
        "notify_hotkey_fail": "Atajo no disponible: {err}",
        "notify_autostop": "Detenido automáticamente tras {h:g} horas.",
        "notify_autostart_on": "Se iniciará con Windows",
        "notify_autostart_off": "Eliminado del inicio",
        "notify_autostart_fail": "No se pudo cambiar el inicio: {err}",
        "msg_already_running": "{app} ya se está ejecutando — mira la bandeja del sistema.",
        "msg_crashed": "{app} se cerró inesperadamente:\n\n{err}",
    },
    "pt": {
        "state_running": "Ativo",
        "state_paused": "Pausado",
        "state_stopped": "Parado automaticamente",
        "state_locked": "Bloqueado",
        "detail_start": "Clique aqui para iniciar",
        "detail_limit": "Limite de execução atingido",
        "detail_locked": "Inativo quando bloqueado, retoma sozinho",
        "detail_uptime": "Ativo há {d}",
        "detail_injections": "{n} movimentos",
        "detail_idle": "ocioso {n}s",
        "dur_hm": "{h} h {m} min",
        "dur_ms": "{m} min {s} s",
        "dur_s": "{s} s",
        "row_mode": "Modo",
        "opt_smart": "Inteligente",
        "opt_force": "Sempre",
        "row_cadence": "Intervalo · s",
        "row_autostop": "Parada auto · h",
        "opt_unlimited": "Não",
        "row_keep_display": "Impedir tela desligada / suspensão",
        "row_autostart": "Iniciar com o Windows",
        "row_autostart_stale": "Iniciar com o Windows (quebrado — clique)",
        "row_logging": "Gravar log",
        "row_open_config": "Abrir pasta de configuração",
        "row_language": "Idioma",
        "row_back": "Voltar",
        "row_quit": "Sair",
        "notify_started": "Manutenção iniciada",
        "notify_paused": "Manutenção pausada",
        "notify_hotkey_fail": "Atalho indisponível: {err}",
        "notify_autostop": "Parado automaticamente após {h:g} horas.",
        "notify_autostart_on": "Iniciará com o Windows",
        "notify_autostart_off": "Removido da inicialização",
        "notify_autostart_fail": "Falha ao alterar a inicialização: {err}",
        "msg_already_running": "{app} já está em execução — veja a área de notificação.",
        "msg_crashed": "{app} encerrou inesperadamente:\n\n{err}",
    },
    "ru": {
        "state_running": "Работает",
        "state_paused": "Приостановлено",
        "state_stopped": "Остановлено автоматически",
        "state_locked": "Заблокировано",
        "detail_start": "Нажмите здесь, чтобы начать",
        "detail_limit": "Достигнут предел времени работы",
        "detail_locked": "Не работает при блокировке, возобновится само",
        "detail_uptime": "Работает {d}",
        "detail_injections": "движений: {n}",
        "detail_idle": "простой {n}s",
        "dur_hm": "{h} ч {m} мин",
        "dur_ms": "{m} мин {s} с",
        "dur_s": "{s} с",
        "row_mode": "Режим",
        "opt_smart": "Умный",
        "opt_force": "Всегда",
        "row_cadence": "Интервал · с",
        "row_autostop": "Автостоп · ч",
        "opt_unlimited": "Выкл",
        "row_keep_display": "Также не гасить экран / сон",
        "row_autostart": "Запуск с Windows",
        "row_autostart_stale": "Запуск с Windows (путь неверен — нажмите)",
        "row_logging": "Вести журнал",
        "row_open_config": "Открыть папку настроек",
        "row_language": "Язык",
        "row_back": "Назад",
        "row_quit": "Выход",
        "notify_started": "Поддержание активности включено",
        "notify_paused": "Поддержание активности приостановлено",
        "notify_hotkey_fail": "Горячая клавиша недоступна: {err}",
        "notify_autostop": "Остановлено автоматически через {h:g} ч.",
        "notify_autostart_on": "Будет запускаться с Windows",
        "notify_autostart_off": "Удалено из автозагрузки",
        "notify_autostart_fail": "Не удалось изменить автозагрузку: {err}",
        "msg_already_running": "{app} уже запущен — проверьте область уведомлений.",
        "msg_crashed": "{app} завершился с ошибкой:\n\n{err}",
    },
}

_current = DEFAULT


def available() -> list[tuple[str, str]]:
    """[(code, display name)] in the order LANGUAGES declares them."""
    return [(code, name) for code, (name, _font) in LANGUAGES.items()]


def detect() -> str:
    """Guess from the Windows display language, falling back to English."""
    try:
        buf = ctypes.create_unicode_buffer(85)
        if ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85):
            tag = buf.value  # 形如 zh-CN / ja-JP / pt-BR
        else:
            return DEFAULT
    except OSError:
        return DEFAULT

    low = tag.lower()
    if low.startswith("zh"):
        # Traditional-Chinese region tags (TW/HK/MO) plus an explicit Hant script
        return "zh-Hant" if any(k in low for k in ("hant", "-tw", "-hk", "-mo")) else "zh-Hans"
    primary = low.split("-")[0]
    return primary if primary in LANGUAGES else DEFAULT


def resolve(code: str | None) -> str:
    """Turn a config value -- possibly "auto", possibly a language we dropped --
    into a language that actually exists."""
    if not code or code == "auto":
        return detect()
    return code if code in LANGUAGES else DEFAULT


def set_language(code: str | None) -> str:
    global _current
    _current = resolve(code)
    return _current


def current() -> str:
    return _current


def font_family() -> str:
    return LANGUAGES[_current][1]


def t(key: str, **kwargs: Any) -> str:
    """Look up a string in the current language.

    Falls back to English when missing, and to the key itself as a last resort.
    """
    text = STRINGS.get(_current, {}).get(key) or STRINGS[DEFAULT].get(key) or key
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        # A bad placeholder in a translation must not crash the UI; retry with
        # the English original.
        fallback = STRINGS[DEFAULT].get(key, key)
        try:
            return fallback.format(**kwargs)
        except Exception:
            return fallback
