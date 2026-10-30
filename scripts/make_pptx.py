#!/usr/bin/env python3
"""Generate the project presentation as a .pptx file."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import os

# Paths
IMG_DIR = os.path.expanduser(
    "~/.gemini/antigravity/brain/00f2d80e-2af7-4709-b293-1359a1a2fc90"
)
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "RL_Scheduler_Presentation.pptx")

# Colors
BG = RGBColor(0x0F, 0x11, 0x1A)
ACCENT = RGBColor(0x3B, 0x82, 0xF6)
GREEN = RGBColor(0x10, 0xB9, 0x81)
PURPLE = RGBColor(0xA7, 0x8B, 0xFA)
ORANGE = RGBColor(0xF5, 0x9E, 0x0B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GRAY = RGBColor(0x94, 0xA3, 0xB8)
DARK = RGBColor(0x1E, 0x29, 0x3B)
RED = RGBColor(0xEF, 0x44, 0x44)

IMAGES = {
    "title": "slide_title_1788423784852.png",
    "mdp": "slide_mdp_1788423799459.png",
    "arch": "slide_architecture_1788423813138.png",
    "team": "slide_team_1788424102883.png",
    "m1": "slide_member1_1788424117668.png",
    "db": "slide_database_1788424053935.png",
    "safety": "slide_safety_1788423861464.png",
    "state": "slide_state_space_1788423840461.png",
    "reward": "slide_reward_math_1788423827033.png",
    "bench": "slide_benchmarks_1788424023401.png",
    "ppo": "slide_ppo_1788423877973.png",
    "curve": "slide_training_curve_1788424038508.png",
    "test": "slide_testing_1788424065540.png",
}


def img(name):
    return os.path.join(IMG_DIR, IMAGES[name])


def set_bg(slide, color=BG):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_title_text(slide, text, left, top, width, height,
                   size=28, color=WHITE, bold=True, align=PP_ALIGN.LEFT):
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top),
                                     Inches(width), Inches(height))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.alignment = align
    return tf


def add_body(slide, text, left, top, width, height,
             size=14, color=GRAY, bold=False):
    return add_title_text(slide, text, left, top, width, height,
                          size=size, color=color, bold=bold)


def add_bullet_frame(slide, items, left, top, width, height,
                     size=13, color=GRAY):
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top),
                                     Inches(width), Inches(height))
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = item
        p.font.size = Pt(size)
        p.font.color.rgb = color
        p.space_after = Pt(4)
    return tf


def add_image_centered(slide, name, top_inches=1.0, max_h=5.8):
    path = img(name)
    if not os.path.exists(path):
        add_body(slide, f"[Image not found: {name}]", 1, 3, 8, 1, size=16, color=RED)
        return
    from PIL import Image as PILImage
    try:
        with PILImage.open(path) as im:
            iw, ih = im.size
    except Exception:
        iw, ih = 1024, 1024

    slide_w = 10.0
    aspect = iw / ih
    h = min(max_h, slide_w / aspect)
    w = h * aspect
    if w > slide_w:
        w = slide_w
        h = w / aspect
    left = (slide_w - w) / 2
    slide.shapes.add_picture(path, Inches(left), Inches(top_inches),
                             Inches(w), Inches(h))


def make_table(slide, rows, left, top, width, row_h, col_widths=None,
               header_color=ACCENT, body_color=GRAY):
    n_rows = len(rows)
    n_cols = len(rows[0])
    tbl_shape = slide.shapes.add_table(n_rows, n_cols,
                                       Inches(left), Inches(top),
                                       Inches(width), Inches(row_h * n_rows))
    tbl = tbl_shape.table
    if col_widths:
        for i, w in enumerate(col_widths):
            tbl.columns[i].width = Inches(w)

    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = tbl.cell(r, c)
            cell.text = str(val)
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(11)
                p.font.color.rgb = WHITE if r == 0 else body_color
                p.font.bold = (r == 0)
            cell.fill.solid()
            cell.fill.fore_color.rgb = DARK if r == 0 else BG
    return tbl


def build():
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]  # blank

    # ── Slide 1: Title ────────────────────────────────
    s = prs.slides.add_slide(blank)
    set_bg(s)
    add_image_centered(s, "title", top_inches=0.0, max_h=7.5)

    # ── Slide 2: MDP ─────────────────────────────────
    s = prs.slides.add_slide(blank)
    set_bg(s)
    add_title_text(s, "Problem Statement & MDP Formulation", 0.5, 0.2, 9, 0.6,
                   size=24, color=ACCENT)
    add_image_centered(s, "mdp", top_inches=0.9, max_h=4.5)
    make_table(s, [
        ["MDP Component", "Mapping"],
        ["State S", "SystemSnapshot — CPU%, load avg, memory, ctxt switches, sched params"],
        ["Action A", "Discrete(2N+1) — increment / decrement / no-op for N=10 params"],
        ["Transition P", "Kernel parameter writes via sysctl -w + readback verification"],
        ["Reward R", "EMA-normalised benchmark score + stability bonus − rollback penalty"],
    ], 0.5, 5.6, 9.0, 0.35, col_widths=[2.0, 7.0])

    # ── Slide 3: Architecture ─────────────────────────
    s = prs.slides.add_slide(blank)
    set_bg(s)
    add_title_text(s, "System Architecture — 4 Layers", 0.5, 0.2, 9, 0.6,
                   size=24, color=ACCENT)
    add_image_centered(s, "arch", top_inches=0.9, max_h=6.4)

    # ── Slide 4: Team Ownership ──────────────────────
    s = prs.slides.add_slide(blank)
    set_bg(s)
    add_title_text(s, "Team Ownership Matrix", 0.5, 0.2, 9, 0.6,
                   size=24, color=ACCENT)
    add_image_centered(s, "team", top_inches=0.9, max_h=4.8)
    make_table(s, [
        ["Member", "Primary Ownership", "Key Modules", "Tests"],
        ["1", "Monitoring, Storage, Dashboard", "monitor/, storage/, dashboard/", "11"],
        ["2", "Scheduler Controller & Safety", "scheduler/, safety/", "12"],
        ["3", "RL Environment & Benchmarks", "rl/, benchmarks/", "31"],
        ["4", "Training, Integration, Evaluation", "core/, scripts/", "13"],
    ], 0.5, 6.0, 9.0, 0.28, col_widths=[1.0, 3.0, 3.5, 1.5])

    # ── Slide 5: Member 1 ────────────────────────────
    s = prs.slides.add_slide(blank)
    set_bg(s)
    add_title_text(s, "Member 1: System Monitoring Pipeline", 0.5, 0.2, 9, 0.6,
                   size=24, color=GREEN)
    add_image_centered(s, "m1", top_inches=0.9, max_h=4.2)
    add_body(s, "CPU Utilisation:  cpu% = 100 × (Δtotal − Δidle) / Δtotal",
             0.5, 5.2, 9, 0.4, size=14, color=WHITE, bold=True)
    make_table(s, [
        ["File", "Lines", "Purpose"],
        ["monitor/sources.py", "369", "7 MetricSource implementations"],
        ["monitor/collector.py", "108", "Monitor — capability detection + snapshot assembly"],
        ["monitor/types.py", "74", "SystemSnapshot + ProcessInfo frozen dataclasses"],
        ["storage/db.py", "277", "StorageBackend — SQLite with 3 tables"],
        ["dashboard/app.py", "321", "PyQt6 MainWindow with 4-tab dashboard"],
    ], 0.5, 5.7, 9.0, 0.28, col_widths=[2.5, 0.8, 5.7])

    # ── Slide 5b: Database Schema ────────────────────
    s = prs.slides.add_slide(blank)
    set_bg(s)
    add_title_text(s, "Member 1: Storage & Audit Trail (SQLite)", 0.5, 0.2, 9, 0.6,
                   size=24, color=GREEN)
    add_image_centered(s, "db", top_inches=0.9, max_h=6.2)

    # ── Slide 6: Member 2 — Safety ──────────────────
    s = prs.slides.add_slide(blank)
    set_bg(s)
    add_title_text(s, "Member 2: Scheduler Controller & Safety", 0.5, 0.2, 9, 0.6,
                   size=24, color=ACCENT)
    add_image_centered(s, "safety", top_inches=0.9, max_h=4.5)
    add_bullet_frame(s, [
        "∀p ∈ P :  min_p  ≤  v_p  ≤  max_p    (bounds check)",
        "verify(p) ≡ read(sysctl_path) = written_value    (readback)",
        "∀i : t_ping(i) − t_ping(i−1) < τ_timeout    (watchdog invariant)",
    ], 0.5, 5.5, 9, 1.0, size=13, color=WHITE)
    make_table(s, [
        ["File", "Lines", "Purpose"],
        ["scheduler/registry.py", "22", "ParameterRegistry — name → ParameterMeta"],
        ["scheduler/validator.py", "25", "Validator — type-check + bounds-check"],
        ["scheduler/backend.py", "103", "SysctlBackend — subprocess R/W + timeout"],
        ["scheduler/controller.py", "118", "SchedulerController — full pipeline"],
        ["safety/validator.py", "71", "SecondaryValidator — independent hard limits"],
        ["safety/watchdog.py", "67", "Watchdog — daemon thread, lock-guarded"],
        ["safety/checkpoint.py", "59", "CheckpointManager — atomic JSON, 0600 perms"],
    ], 0.3, 6.3, 9.4, 0.15, col_widths=[2.5, 0.7, 6.2])

    # ── Slide 6b: Parameter Registry ─────────────────
    s = prs.slides.add_slide(blank)
    set_bg(s)
    add_title_text(s, "Member 2: Tunable Parameter Registry (10 Parameters)",
                   0.5, 0.2, 9, 0.6, size=24, color=ACCENT)
    make_table(s, [
        ["Parameter", "Sysctl Path", "Range"],
        ["sched_min_granularity_ns", "kernel.sched_min_granularity_ns", "100K – 100M"],
        ["sched_wakeup_granularity_ns", "kernel.sched_wakeup_granularity_ns", "100K – 100M"],
        ["sched_rr_timeslice_ms", "kernel.sched_rr_timeslice_ms", "1 – 2,000"],
        ["sched_rt_period_us", "kernel.sched_rt_period_us", "1 – 1,000,000"],
        ["sched_rt_runtime_us", "kernel.sched_rt_runtime_us", "−1 – 1,000,000"],
        ["sched_cfs_bandwidth_slice_us", "kernel.sched_cfs_bandwidth_slice_us", "1 – 100,000"],
        ["sched_autogroup_enabled", "kernel.sched_autogroup_enabled", "0 – 1"],
        ["sched_util_clamp_max", "kernel.sched_util_clamp_max", "0 – 1024"],
        ["sched_util_clamp_min", "kernel.sched_util_clamp_min", "0 – 1024"],
        ["sched_schedstats", "kernel.sched_schedstats", "0 – 1"],
    ], 0.5, 1.0, 9.0, 0.45, col_widths=[3.5, 3.5, 2.0])

    # ── Slide 7: Member 3 — State Space ─────────────
    s = prs.slides.add_slide(blank)
    set_bg(s)
    add_title_text(s, "Member 3: RL Environment — State Space", 0.5, 0.2, 9, 0.6,
                   size=24, color=PURPLE)
    add_image_centered(s, "state", top_inches=0.9, max_h=6.2)

    # ── Slide 7b: Reward Shaping ─────────────────────
    s = prs.slides.add_slide(blank)
    set_bg(s)
    add_title_text(s, "Member 3: Reward Shaping (EMA-Normalised Delta)",
                   0.5, 0.2, 9, 0.6, size=24, color=PURPLE)
    add_image_centered(s, "reward", top_inches=0.9, max_h=6.2)

    # ── Slide 7c: Benchmarks ─────────────────────────
    s = prs.slides.add_slide(blank)
    set_bg(s)
    add_title_text(s, "Member 3: Benchmark Suite & Evaluation", 0.5, 0.2, 9, 0.6,
                   size=24, color=PURPLE)
    add_image_centered(s, "bench", top_inches=0.9, max_h=6.2)

    # ── Slide 8: Member 4 — PPO ──────────────────────
    s = prs.slides.add_slide(blank)
    set_bg(s)
    add_title_text(s, "Member 4: Training — PPO with Discrete Actions",
                   0.5, 0.2, 9, 0.6, size=24, color=ORANGE)
    add_image_centered(s, "ppo", top_inches=0.9, max_h=6.2)

    # ── Slide 8b: Training Curve ─────────────────────
    s = prs.slides.add_slide(blank)
    set_bg(s)
    add_title_text(s, "Member 4: Training Convergence", 0.5, 0.2, 9, 0.6,
                   size=24, color=ORANGE)
    add_image_centered(s, "curve", top_inches=0.9, max_h=5.0)
    make_table(s, [
        ["File", "Lines", "Purpose"],
        ["core/trainer.py", "229", "Trainer — wraps SB3 PPO/SAC"],
        ["core/checkpoint.py", "104", "SchedulerCheckpointCallback — .zip + meta.json"],
        ["core/loop.py", "123", "EpisodeRunner — watchdog lifecycle"],
        ["scripts/run_training.py", "221", "CLI: --dry-run, --load, --algorithm"],
    ], 0.5, 6.2, 9.0, 0.24, col_widths=[2.8, 0.7, 5.5])

    # ── Slide 9: Testing ─────────────────────────────
    s = prs.slides.add_slide(blank)
    set_bg(s)
    add_title_text(s, "Testing & Validation", 0.5, 0.2, 9, 0.6,
                   size=24, color=ACCENT)
    add_image_centered(s, "test", top_inches=0.9, max_h=6.2)

    # ── Slide 10: Tech Stack ─────────────────────────
    s = prs.slides.add_slide(blank)
    set_bg(s)
    add_title_text(s, "Technology Stack", 0.5, 0.2, 9, 0.6,
                   size=24, color=ACCENT)
    make_table(s, [
        ["Layer", "Technology", "Purpose"],
        ["Language", "Python 3.11+", "Core framework"],
        ["RL Framework", "Stable-Baselines3 2.3+ (PyTorch)", "PPO / SAC algorithms"],
        ["Gym Interface", "Gymnasium 0.29+", "Environment API"],
        ["Dashboard", "PyQt6 + pyqtgraph", "Live GUI with 4 panels"],
        ["Storage", "SQLite (sqlite3 stdlib)", "Audit trail + metrics"],
        ["Configuration", "YAML (PyYAML)", "Single-source-of-truth config"],
        ["Testing", "pytest 8.0+", "67 tests, fakes/stubs"],
        ["Kernel Interface", "/proc + sysctl", "Parameter read/write"],
    ], 0.5, 1.0, 9.0, 0.55, col_widths=[2.0, 4.0, 3.0])

    # ── Slide 11: Summary ────────────────────────────
    s = prs.slides.add_slide(blank)
    set_bg(s)
    add_title_text(s, "Summary & Contributions", 0.5, 0.2, 9, 0.6,
                   size=24, color=ACCENT)
    make_table(s, [
        ["Metric", "Value"],
        ["Total Python files", "35+ source files"],
        ["Total lines of code", "~5,000+ LoC"],
        ["Test coverage", "67 tests, all passing"],
        ["Tunable parameters", "10 kernel sched params"],
        ["Benchmark adapters", "5 (stress-ng, sysbench, hackbench, cyclictest, fio)"],
        ["Safety layers", "3 validators + watchdog + rollback"],
        ["RL algorithms", "PPO (discrete) + SAC (continuous)"],
        ["Dashboard panels", "4 (Overview, Processes, Memory, Scheduler)"],
        ["Database tables", "3 (snapshot, benchmark_result, applied_config)"],
    ], 1.5, 1.2, 7.0, 0.5, col_widths=[2.5, 4.5])
    add_title_text(s, "Monitor  →  RL Env  →  Scheduler Controller  →  Trainer",
                   0.5, 6.2, 9, 0.5, size=20, color=GREEN, align=PP_ALIGN.CENTER)

    # Save
    prs.save(OUT)
    print(f"✓ Saved to {OUT}")


if __name__ == "__main__":
    build()
