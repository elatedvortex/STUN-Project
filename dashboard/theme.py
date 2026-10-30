"""
dashboard/theme.py — Centralised dark theme palette + Qt stylesheet.

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
