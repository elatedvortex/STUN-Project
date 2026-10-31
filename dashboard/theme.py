"""
dashboard/theme.py — Centralised light/dark palettes, Qt styles, and live widget updates.

All colours are defined once here; every widget imports from this module
rather than scattering hex literals across the codebase.
"""

# ── Palette ─────────────────────────────────────────────────────────────────
BG_DEEP    = "#09090b"   # deepest background (zinc-950)
BG_CARD    = "#18181b"   # card / panel background (zinc-900)
BG_HOVER   = "#27272a"   # hover state (zinc-800)
BORDER     = "#3f3f46"   # subtle borders (zinc-700)
ACCENT     = "#6366f1"   # primary accent (indigo-500)
ACCENT2    = "#10b981"   # green (emerald-500)
WARN       = "#f59e0b"   # amber (amber-500)
DANGER     = "#ef4444"   # red (red-500)
TEXT_PRI   = "#f4f4f5"   # primary text (zinc-50)
TEXT_SEC   = "#a1a1aa"   # secondary / muted text (zinc-400)
TEXT_DIM   = "#52525b"   # very dim (zinc-600)

# Plot colours (cycling)
PLOT_COLORS = [
    "#6366f1",  # indigo
    "#10b981",  # emerald
    "#f59e0b",  # amber
    "#ef4444",  # red
    "#8b5cf6",  # violet
    "#0ea5e9",  # sky
]

# Pyqtgraph background
PG_BG = BG_CARD


STYLESHEET = f"""
/* ── Global ────────────────────────────────────────────── */
QWidget {{
    background-color: {BG_DEEP};
    color: {TEXT_PRI};
    font-family: "Inter", "Segoe UI", "SF Pro Display", -apple-system, sans-serif;
    font-size: 13px;
    border: none;
    outline: none;
}}

QMainWindow, QDialog {{
    background-color: {BG_DEEP};
}}

/* ── Scroll bars ────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {BG_CARD};
    width: 8px;
    margin: 0;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_SEC};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {BG_CARD};
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {TEXT_SEC};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Tabs ───────────────────────────────────────────────── */
QTabWidget::pane {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: -1px;
}}
QTabBar::tab {{
    background: {BG_DEEP};
    color: {TEXT_SEC};
    padding: 12px 24px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 4px;
    font-weight: 600;
    font-size: 14px;
}}
QTabBar::tab:selected {{
    background: {BG_CARD};
    color: {TEXT_PRI};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    background: {BG_HOVER};
    color: {TEXT_PRI};
}}

/* ── Buttons ────────────────────────────────────────────── */
QPushButton {{
    background: {BG_HOVER};
    color: {TEXT_PRI};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton:hover {{
    background: {ACCENT};
    border-color: {ACCENT};
    color: #ffffff;
}}
QPushButton:pressed {{
    background: #4f46e5;
}}
QPushButton#btn_danger {{
    background: transparent;
    border-color: {DANGER};
    color: {DANGER};
}}
QPushButton#btn_danger:hover {{
    background: {DANGER};
    color: #ffffff;
}}
QPushButton#btn_warn {{
    background: transparent;
    border-color: {WARN};
    color: {WARN};
}}
QPushButton#btn_warn:hover {{
    background: {WARN};
    color: #000000;
}}
QPushButton#btn_success {{
    background: transparent;
    border-color: {ACCENT2};
    color: {ACCENT2};
}}
QPushButton#btn_success:hover {{
    background: {ACCENT2};
    color: #000000;
}}

/* ── Labels ─────────────────────────────────────────────── */
QLabel#heading {{
    color: {TEXT_PRI};
    font-size: 16px;
    font-weight: 700;
}}
QLabel#subheading {{
    color: {TEXT_SEC};
    font-size: 13px;
}}
QLabel#stat_value {{
    color: {ACCENT};
    font-size: 32px;
    font-weight: 800;
}}
QLabel#stat_label {{
    color: {TEXT_SEC};
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    font-weight: 600;
}}

/* ── Table ──────────────────────────────────────────────── */
QTableWidget, QTableView {{
    background: {BG_CARD};
    gridline-color: transparent;
    alternate-background-color: {BG_DEEP};
    border-radius: 12px;
    font-size: 13px;
    selection-background-color: {ACCENT}33;
    selection-color: {ACCENT};
}}
QTableWidget::item, QTableView::item {{
    padding: 8px 12px;
    border: none;
    border-bottom: 1px solid {BORDER};
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background: {ACCENT}33;
    color: {ACCENT};
}}
QHeaderView::section {{
    background: {BG_DEEP};
    color: {TEXT_SEC};
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    padding: 10px 12px;
    border-bottom: 2px solid {BORDER};
    border-right: none;
}}

/* ── Sliders ────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    background: {BORDER};
    height: 6px;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: #818cf8;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 3px;
}}

/* ── Line edits ─────────────────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {BG_HOVER};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 12px;
    color: {TEXT_PRI};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {ACCENT};
    background: {BG_CARD};
}}
QComboBox::drop-down {{
    border: none;
    padding-right: 10px;
}}

/* ── Group box ──────────────────────────────────────────── */
QGroupBox {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: 20px;
    padding: 20px 16px 14px 16px;
    font-weight: 600;
    color: {TEXT_PRI};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    top: -10px;
    padding: 2px 10px;
    color: {ACCENT};
    background: {BG_DEEP};
    border: 1px solid {BORDER};
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.8px;
}}

/* ── Tool tip ───────────────────────────────────────────── */
QToolTip {{
    background: {BG_HOVER};
    color: {TEXT_PRI};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ── Status bar ─────────────────────────────────────────── */
QStatusBar {{
    background: {BG_DEEP};
    color: {TEXT_SEC};
    border-top: 1px solid {BORDER};
    font-size: 12px;
}}
"""


# Keep semantic chart colours stable when switching modes.
_DARK = {key: globals()[key] for key in (
    "BG_DEEP", "BG_CARD", "BG_HOVER", "BORDER", "ACCENT", "ACCENT2",
    "WARN", "DANGER", "TEXT_PRI", "TEXT_SEC", "TEXT_DIM",
)}
_LIGHT = {**_DARK, "BG_DEEP": "#f4f6fb", "BG_CARD": "#ffffff",
          "BG_HOVER": "#e8edf6", "BORDER": "#cbd5e1",
          "TEXT_PRI": "#111827", "TEXT_SEC": "#475569", "TEXT_DIM": "#64748b"}
_PALETTES = {"dark": _DARK, "light": _LIGHT}
_BASE_STYLESHEET = STYLESHEET
current_theme = "dark"


def recolor_stylesheet(stylesheet, old, new):
    """Update inline styles without rebuilding panels or losing their state."""
    import re
    colors = {value.lower(): new[key] for key, value in old.items()}

    def replace(match):
        base, alpha = match.group(1).lower(), match.group(2) or ""
        # White foregrounds on accent buttons are deliberate in both modes.
        prefix = stylesheet[:match.start()].rsplit(";", 1)[-1].rsplit("{", 1)[-1]
        if base == "#ffffff" and re.search(r"(?<![-\w])color\s*:\s*$", prefix):
            return match.group(0)
        return colors.get(base, base) + alpha

    return re.sub(r"(#[0-9a-fA-F]{6})([0-9a-fA-F]{2})?(?![0-9a-fA-F])", replace, stylesheet)


def set_theme(name):
    global current_theme, PG_BG, STYLESHEET
    if name not in _PALETTES:
        raise ValueError("Theme must be light or dark")
    globals().update(_PALETTES[name])
    current_theme = name
    PG_BG = BG_CARD
    STYLESHEET = recolor_stylesheet(_BASE_STYLESHEET, _DARK, _PALETTES[name])
    STYLESHEET += f"""
QPushButton:checked {{ background: {ACCENT}; color: #ffffff; border-color: {ACCENT}; }}
QComboBox QAbstractItemView {{ background: {BG_CARD}; color: {TEXT_PRI};
    selection-background-color: {ACCENT}; selection-color: #ffffff; }}
QTextEdit, QPlainTextEdit {{ background: {BG_CARD}; color: {TEXT_PRI}; }}
"""


def resolve_color(color):
    """Resolve legacy colour constants that were captured at module import."""
    return {_DARK[key]: value for key, value in _PALETTES[current_theme].items()}.get(color, color)


def apply_to_window(window, name):
    """Repaint the existing widget tree and plots; keep workers and data intact."""
    import re
    import pyqtgraph as pg
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QBrush, QPalette
    from PyQt6.QtWidgets import QApplication, QWidget, QTableWidget, QListWidget, QTextEdit

    old = dict(_PALETTES[current_theme])
    set_theme(name)
    new = _PALETTES[name]
    color_map = {value: new[key] for key, value in old.items()}
    app = QApplication.instance()
    palette = QPalette()
    for role, color in {
        QPalette.ColorRole.Window: BG_DEEP, QPalette.ColorRole.WindowText: TEXT_PRI,
        QPalette.ColorRole.Base: BG_CARD, QPalette.ColorRole.AlternateBase: BG_DEEP,
        QPalette.ColorRole.Text: TEXT_PRI, QPalette.ColorRole.Button: BG_HOVER,
        QPalette.ColorRole.ButtonText: TEXT_PRI, QPalette.ColorRole.Highlight: ACCENT,
        QPalette.ColorRole.HighlightedText: "#ffffff", QPalette.ColorRole.ToolTipBase: BG_CARD,
        QPalette.ColorRole.ToolTipText: TEXT_PRI, QPalette.ColorRole.PlaceholderText: TEXT_DIM,
    }.items():
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    pg.setConfigOption("background", PG_BG)
    pg.setConfigOption("foreground", TEXT_SEC)

    def recolor_item(item):
        if item is None:
            return
        brush = item.foreground()
        if brush.style() != Qt.BrushStyle.NoBrush:
            mapped = color_map.get(brush.color().name())
            if mapped:
                item.setForeground(QBrush(QColor(mapped)))

    for widget in [window, *window.findChildren(QWidget)]:
        css = widget.styleSheet()
        if css:
            widget.setStyleSheet(recolor_stylesheet(css, old, new))
        if isinstance(widget, pg.PlotWidget):
            widget.setBackground(PG_BG)
            plot = widget.getPlotItem()
            for axis_info in plot.axes.values():
                axis = axis_info["item"]
                axis.setPen(pg.mkPen(BORDER))
                axis.setTextPen(pg.mkPen(TEXT_SEC))
                if axis.labelText:
                    axis.setLabel(axis.labelText, units=axis.labelUnits,
                                  **{**axis.labelStyle, "color": TEXT_SEC})
            if plot.titleLabel.text:
                plot.setTitle(plot.titleLabel.text, color=TEXT_PRI)
            if plot.legend:
                for _, label in plot.legend.items:
                    label.setText(label.text, color=TEXT_PRI)
        if isinstance(widget, QTableWidget):
            for row in range(widget.rowCount()):
                for column in range(widget.columnCount()):
                    recolor_item(widget.item(row, column))
        if isinstance(widget, QListWidget):
            for row in range(widget.count()):
                recolor_item(widget.item(row))
        if isinstance(widget, QTextEdit) and widget.isReadOnly():
            scroll = widget.verticalScrollBar().value()
            html = widget.toHtml()
            html = re.sub(r'style="([^"]*)"',
                          lambda match: 'style="' + recolor_stylesheet(match.group(1), old, new) + '"', html)
            widget.setHtml(html)
            widget.verticalScrollBar().setValue(scroll)
        widget.update()
    window.setStyleSheet(STYLESHEET)
