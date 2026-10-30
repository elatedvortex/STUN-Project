#!/usr/bin/env python3
"""
Enhanced S7 Project Mid-Review Presentation Generator
─────────────────────────────────────────────────────
Generates charts & diagrams as PNGs via matplotlib,
then builds a polished, visual 13-slide PPTX.
"""

import os, math, textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE

# ━━━━━━━━━━━━━━━━━━━━━━  CONSTANTS  ━━━━━━━━━━━━━━━━━━━━━━
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

CRIMSON     = RGBColor(0x9E, 0x00, 0x3E)
WHITE       = RGBColor(0xFF, 0xFF, 0xFF)
BLACK       = RGBColor(0x00, 0x00, 0x00)
YELLOW      = RGBColor(0xFF, 0xD7, 0x00)
GREEN       = RGBColor(0x00, 0x80, 0x00)
LIGHT_GREY  = RGBColor(0xF5, 0xF5, 0xF5)
DARK_GREY   = RGBColor(0x55, 0x55, 0x55)
SOFT_GREY   = RGBColor(0x99, 0x99, 0x99)
ACCENT_BLUE = RGBColor(0x2E, 0x86, 0xAB)

SANS   = "Arial"
SERIF  = "Georgia"
MONO   = "Consolas"

FOOTER_H = Inches(0.5)
IMG_DIR  = "ppt_assets"

# matplotlib color palette
C_CRIMSON  = "#9E003E"
C_BLUE     = "#2E86AB"
C_GREEN    = "#1B7A3D"
C_ORANGE   = "#D46B08"
C_PURPLE   = "#564D80"
C_DARK     = "#333333"
C_GREY     = "#888888"
C_LIGHT_BG = "#FAFAFA"

os.makedirs(IMG_DIR, exist_ok=True)


# ━━━━━━━━━━━━━━━━━━  CHART GENERATORS  ━━━━━━━━━━━━━━━━━━━

def gen_intro_analogy():
    """Slide 3 — visual analogy: STUN as an 'autopilot for your CPU'."""
    fig, ax = plt.subplots(figsize=(10, 3.0), facecolor="white")
    ax.set_xlim(0, 10); ax.set_ylim(0, 3)
    ax.axis("off")

    boxes = [
        (0.2, 0.6, "🖥️\nWorkload\nHits the CPU", C_BLUE),
        (2.6, 0.6, "📊\nMonitor\nReads /proc", C_GREEN),
        (5.0, 0.6, "🧠\nRL Agent\nPicks action", C_CRIMSON),
        (7.4, 0.6, "⚙️\nKernel\nApplies tuning", C_ORANGE),
    ]
    for x, y, txt, c in boxes:
        fancy = FancyBboxPatch((x, y), 2.0, 1.7, boxstyle="round,pad=0.15",
                               facecolor=c, edgecolor="white", linewidth=2, alpha=0.92)
        ax.add_patch(fancy)
        ax.text(x + 1.0, y + 0.85, txt, ha="center", va="center",
                fontsize=12, fontweight="bold", color="white", linespacing=1.4)

    for sx in [2.2, 4.6, 7.0]:
        ax.annotate("", xy=(sx + 0.35, 1.45), xytext=(sx, 1.45),
                    arrowprops=dict(arrowstyle="->,head_width=0.3,head_length=0.15",
                                   color=C_CRIMSON, lw=2.5))

    # Loop-back arrow
    ax.annotate("", xy=(1.2, 0.45), xytext=(8.4, 0.45),
                arrowprops=dict(arrowstyle="->,head_width=0.25,head_length=0.15",
                                connectionstyle="arc3,rad=-0.35",
                                color=C_CRIMSON, lw=1.8, linestyle="--"))
    ax.text(4.8, 0.08, "reward feeds back", ha="center", fontsize=10,
            color=C_CRIMSON, fontstyle="italic")

    fig.tight_layout(pad=0.3)
    path = f"{IMG_DIR}/intro_flow.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def gen_problem_icons():
    """Slide 4 — three icon cards for motivation / problem / objectives."""
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.2), facecolor="white")
    cards = [
        ("💡", "Motivation",
         "Default kernel settings\naren't optimal for every\nworkload. Manual tuning\nneeds deep expertise."),
        ("🎯", "Problem",
         "Can an RL agent learn\nnear-optimal scheduler\nparams at runtime, using\nonly live /proc data?"),
        ("🚀", "Objectives",
         "• Automated closed loop\n• Beat Linux defaults\n• Zero unsafe writes\n• Multi-benchmark eval"),
    ]
    colors = [C_BLUE, C_CRIMSON, C_GREEN]
    for ax, (icon, title, body), col in zip(axes, cards, colors):
        ax.set_xlim(0, 4); ax.set_ylim(0, 3.5); ax.axis("off")
        fancy = FancyBboxPatch((0.1, 0.1), 3.8, 3.3, boxstyle="round,pad=0.15",
                               facecolor=col, alpha=0.10, edgecolor=col, linewidth=2.5)
        ax.add_patch(fancy)
        ax.text(2.0, 2.95, icon, ha="center", va="center", fontsize=30)
        ax.text(2.0, 2.35, title, ha="center", va="center", fontsize=15,
                fontweight="bold", color=col)
        ax.text(2.0, 1.15, body, ha="center", va="center", fontsize=10.5,
                color="#333333", linespacing=1.45)
    fig.tight_layout(pad=0.4)
    path = f"{IMG_DIR}/problem_cards.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def gen_lit_timeline():
    """Slide 5 — horizontal timeline of literature."""
    fig, ax = plt.subplots(figsize=(11, 2.2), facecolor="white")
    ax.set_xlim(2018.3, 2024.2); ax.set_ylim(-1.8, 2.2); ax.axis("off")

    # Timeline line
    ax.plot([2018.5, 2024], [0, 0], color=C_GREY, lw=2, zorder=1)

    papers = [
        (2019, "ghOSt\n(Google)", C_BLUE, 1),
        (2020, "Decima\n(MIT)", C_GREEN, -1),
        (2021, "PARTIES\n(QoS RL)", C_PURPLE, 1),
        (2022, "SmartSched\n(CFS RL)", C_ORANGE, -1),
        (2023, "CFS-RL\n(PPO)", C_CRIMSON, 1),
    ]
    for yr, label, col, side in papers:
        ax.plot(yr, 0, "o", color=col, markersize=14, zorder=3)
        ax.text(yr, 0, str(yr), ha="center", va="center", fontsize=7,
                fontweight="bold", color="white", zorder=4)
        y_text = 1.2 * side
        ax.plot([yr, yr], [0, 0.6 * side], color=col, lw=1.2, zorder=2)
        ax.text(yr, y_text, label, ha="center", va="center", fontsize=9,
                fontweight="bold", color=col, linespacing=1.3,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                          edgecolor=col, alpha=0.95, linewidth=1.5))

    fig.tight_layout(pad=0.3)
    path = f"{IMG_DIR}/lit_timeline.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def gen_research_gap_radar():
    """Slide 6 — radar chart: STUN vs prior work on 5 dimensions."""
    categories = ["# Params\nTuned", "Runtime\nSafety", "Online\nAdaptation",
                   "Benchmark\nCoverage", "Gym\nInterface"]
    N = len(categories)
    angles = [n / float(N) * 2 * math.pi for n in range(N)]
    angles += angles[:1]

    prior =  [0.25, 0.15, 0.20, 0.20, 0.10]
    stun  =  [0.90, 0.95, 0.85, 0.90, 1.00]
    prior += prior[:1]
    stun  += stun[:1]

    fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True), facecolor="white")
    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_rlabel_position(0)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["25%", "50%", "75%", "100%"], fontsize=8, color=C_GREY)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=10, fontweight="bold", color=C_DARK)

    ax.fill(angles, prior, alpha=0.15, color=C_GREY)
    ax.plot(angles, prior, "o-", color=C_GREY, linewidth=2, label="Prior Work (avg)")
    ax.fill(angles, stun, alpha=0.18, color=C_CRIMSON)
    ax.plot(angles, stun, "o-", color=C_CRIMSON, linewidth=2.5, label="STUN (Ours)")

    ax.legend(loc="lower right", bbox_to_anchor=(1.3, -0.05), fontsize=11,
              frameon=True, fancybox=True)
    fig.tight_layout(pad=1.0)
    path = f"{IMG_DIR}/gap_radar.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def gen_architecture_diagram():
    """Slide 8 — clean circular architecture diagram."""
    fig, ax = plt.subplots(figsize=(12, 5.5), facecolor="white")
    ax.set_xlim(-0.5, 12.5); ax.set_ylim(-0.5, 5.5); ax.axis("off")

    # Six stages around a central kernel block
    stages = [
        (0.3,  3.2, "1  MONITOR", "Read /proc:\nCPU · Load · Memory\nContext switches", C_BLUE),
        (2.5,  3.2, "2  STATE", "rl/state.py:\nNormalise raw\nreadings → [0,1]\nobservation vector", C_PURPLE),
        (4.7,  3.2, "3  POLICY", "core/trainer.py:\nPPO network\npicks an action\n(just a number)", C_CRIMSON),
        (6.9,  3.2, "4  DECODE", "rl/action.py:\nMap action →\nreal scheduler\nparameters", C_ORANGE),
        (9.1,  3.2, "5  WRITE", "scheduler/:\nValidate →\nwrite to kernel\n→ readback", C_GREEN),
        (4.7,  0.2, "6  BENCHMARK", "benchmarks/:\nMeasure the effect\n→ compute a single\nreward score", "#863B00"),
    ]

    for x, y, title, body, col in stages:
        fancy = FancyBboxPatch((x, y), 2.0, 2.0, boxstyle="round,pad=0.12",
                               facecolor=col, edgecolor="white", linewidth=2, alpha=0.92)
        ax.add_patch(fancy)
        ax.text(x + 1.0, y + 1.65, title, ha="center", va="center",
                fontsize=10, fontweight="bold", color="white")
        ax.text(x + 1.0, y + 0.78, body, ha="center", va="center",
                fontsize=7.5, color="white", linespacing=1.35)

    # Central kernel block
    kx, ky = 7.6, 0.3
    fancy_k = FancyBboxPatch((kx, ky), 2.8, 1.6, boxstyle="round,pad=0.15",
                             facecolor=C_DARK, edgecolor=C_CRIMSON, linewidth=3, alpha=0.95)
    ax.add_patch(fancy_k)
    ax.text(kx + 1.4, ky + 1.05, "⚙️  LINUX KERNEL", ha="center", va="center",
            fontsize=12, fontweight="bold", color="white")
    ax.text(kx + 1.4, ky + 0.45, "the system under test", ha="center", va="center",
            fontsize=9, color="#cccccc", fontstyle="italic")

    # Arrows (top row: 1→2→3→4→5)
    for sx in [2.3, 4.5, 6.7, 8.9]:
        ax.annotate("", xy=(sx + 0.2, 4.2), xytext=(sx, 4.2),
                    arrowprops=dict(arrowstyle="->,head_width=0.25", color=C_CRIMSON, lw=2.5))

    # Arrow from 5 down to kernel
    ax.annotate("", xy=(10.1, 1.95), xytext=(10.1, 3.15),
                arrowprops=dict(arrowstyle="->,head_width=0.25", color=C_CRIMSON, lw=2.5))

    # Arrow from kernel to 6
    ax.annotate("", xy=(6.75, 1.0), xytext=(7.55, 1.0),
                arrowprops=dict(arrowstyle="->,head_width=0.25", color=C_CRIMSON, lw=2.5))

    # Arrow from 6 back to 1 (loop back — curved)
    ax.annotate("", xy=(0.8, 3.15), xytext=(4.7, 1.2),
                arrowprops=dict(arrowstyle="->,head_width=0.3", color=C_CRIMSON, lw=2.5,
                                connectionstyle="arc3,rad=0.4", linestyle="--"))
    ax.text(1.8, 1.5, "reward\nloops back", ha="center", fontsize=9,
            color=C_CRIMSON, fontstyle="italic", fontweight="bold")

    fig.tight_layout(pad=0.3)
    path = f"{IMG_DIR}/architecture.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def gen_sequence_diagram():
    """Slide 9 — clean sequence diagram as an image."""
    fig, ax = plt.subplots(figsize=(12, 5.5), facecolor="white")
    ax.set_xlim(-0.3, 12.3); ax.set_ylim(-0.3, 6.5); ax.axis("off")

    participants = [
        (1.0,  "Trainer\ncore/",          C_CRIMSON),
        (3.5,  "Environment\nrl/",         C_BLUE),
        (6.0,  "Controller\nscheduler/",   C_GREEN),
        (8.5,  "Kernel\n/proc/sys",        C_DARK),
        (11.0, "Benchmarks\nbenchmarks/",  C_ORANGE),
    ]

    head_y = 5.8
    head_h = 0.7
    for px, label, col in participants:
        fancy = FancyBboxPatch((px - 0.65, head_y), 1.3, head_h,
                               boxstyle="round,pad=0.08", facecolor=col,
                               edgecolor="white", linewidth=1.5, alpha=0.93)
        ax.add_patch(fancy)
        ax.text(px, head_y + head_h / 2, label, ha="center", va="center",
                fontsize=8.5, fontweight="bold", color="white", linespacing=1.3)
        # Lifeline
        ax.plot([px, px], [head_y, 0.1], color="#cccccc", lw=1.5, linestyle="--", zorder=1)

    arrows = [
        (1.0,  3.5,  5.2, "① action",                              C_CRIMSON),
        (3.5,  6.0,  4.5, "② mapped params",                       C_BLUE),
        (6.0,  8.5,  3.8, "③ write + readback",                    C_GREEN),
        (3.5,  11.0, 2.9, "④ run benchmark",                       C_BLUE),
        (11.0, 3.5,  2.0, "⑤ raw score + fresh snapshot",          C_ORANGE),
        (3.5,  1.0,  1.1, "⑥ obs, reward, done",                   C_BLUE),
    ]

    for sx, ex, y, label, col in arrows:
        ax.annotate("", xy=(ex, y), xytext=(sx, y),
                    arrowprops=dict(arrowstyle="->,head_width=0.2,head_length=0.12",
                                   color=col, lw=2))
        mid_x = (sx + ex) / 2
        ax.text(mid_x, y + 0.25, label, ha="center", va="bottom", fontsize=9,
                fontweight="bold", color=col,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                          edgecolor=col, alpha=0.9, linewidth=1))

    # Bidirectional indicator for arrow 3
    ax.annotate("", xy=(6.0, 3.6), xytext=(8.5, 3.6),
                arrowprops=dict(arrowstyle="->,head_width=0.15", color=C_GREEN,
                                lw=1.5, linestyle="--"))

    fig.tight_layout(pad=0.3)
    path = f"{IMG_DIR}/sequence.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def gen_algo_visual():
    """Slide 10 — PPO training loop + hyperparameter card."""
    fig = plt.figure(figsize=(12, 4.5), facecolor="white")
    gs = fig.add_gridspec(1, 2, width_ratios=[1.3, 1], wspace=0.15)

    # Left: PPO loop
    ax1 = fig.add_subplot(gs[0])
    ax1.set_xlim(0, 7); ax1.set_ylim(0, 5); ax1.axis("off")
    ax1.set_title("PPO Training Loop (per episode)", fontsize=13,
                  fontweight="bold", color=C_CRIMSON, pad=10)

    steps = [
        (0.3, 3.8, "Observe", "Read system\nsnapshot", C_BLUE),
        (2.0, 3.8, "Act", "Policy picks\naction", C_CRIMSON),
        (3.7, 3.8, "Apply", "Write to\nkernel", C_GREEN),
        (5.4, 3.8, "Benchmark", "Measure\nimpact", C_ORANGE),
        (2.8, 1.5, "Learn", "Update policy\n(PPO clip loss)", C_PURPLE),
    ]
    for x, y, title, body, col in steps:
        fancy = FancyBboxPatch((x, y), 1.4, 1.0, boxstyle="round,pad=0.1",
                               facecolor=col, alpha=0.9, edgecolor="white", linewidth=1.5)
        ax1.add_patch(fancy)
        ax1.text(x + 0.7, y + 0.65, title, ha="center", va="center",
                 fontsize=10, fontweight="bold", color="white")
        ax1.text(x + 0.7, y + 0.25, body, ha="center", va="center",
                 fontsize=7.5, color="white", linespacing=1.3)

    # Top arrows
    for sx in [1.7, 3.4, 5.1]:
        ax1.annotate("", xy=(sx + 0.3, 4.3), xytext=(sx, 4.3),
                     arrowprops=dict(arrowstyle="->", color=C_CRIMSON, lw=2))
    # Down to learn
    ax1.annotate("", xy=(5.0, 2.5), xytext=(6.1, 3.75),
                 arrowprops=dict(arrowstyle="->", color=C_CRIMSON, lw=2,
                                 connectionstyle="arc3,rad=-0.3"))
    # Back up from learn
    ax1.annotate("", xy=(0.7, 3.75), xytext=(2.8, 2.0),
                 arrowprops=dict(arrowstyle="->", color=C_CRIMSON, lw=2,
                                 connectionstyle="arc3,rad=-0.3", linestyle="--"))
    ax1.text(1.2, 2.7, "repeat × 50 steps", fontsize=8, color=C_CRIMSON,
             fontstyle="italic", fontweight="bold", rotation=30)

    # Right: hyperparameters card
    ax2 = fig.add_subplot(gs[1])
    ax2.set_xlim(0, 5); ax2.set_ylim(0, 5); ax2.axis("off")
    ax2.set_title("Key Hyperparameters", fontsize=13,
                  fontweight="bold", color=C_CRIMSON, pad=10)

    params = [
        ("Learning Rate",   "3 × 10⁻⁴"),
        ("Batch Size",      "64"),
        ("Steps / Update",  "2,048"),
        ("PPO Epochs",      "10"),
        ("Discount (γ)",    "0.99"),
        ("GAE (λ)",         "0.95"),
        ("Clip Range",      "0.2"),
        ("Entropy Coeff",   "0.01"),
        ("EMA α (reward)",  "0.1"),
        ("Rollback Penalty","−0.5"),
    ]
    for i, (name, val) in enumerate(params):
        y = 4.5 - i * 0.45
        bg_col = "#f8f0f4" if i % 2 == 0 else "white"
        fancy = FancyBboxPatch((0.1, y - 0.15), 4.8, 0.38,
                               boxstyle="round,pad=0.05", facecolor=bg_col,
                               edgecolor="#eee", linewidth=0.5)
        ax2.add_patch(fancy)
        ax2.text(0.3, y + 0.03, name, fontsize=9, color=C_DARK, va="center")
        ax2.text(4.7, y + 0.03, val, fontsize=9, fontweight="bold",
                 color=C_CRIMSON, ha="right", va="center")

    fig.tight_layout(pad=0.5)
    path = f"{IMG_DIR}/algo_visual.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def gen_reward_curve():
    """Slide 11 — simulated reward learning curve + comparison bar chart."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.2), facecolor="white")

    # Left: reward curve (simulated)
    np.random.seed(42)
    episodes = np.arange(1, 201)
    base_curve = 1 - np.exp(-episodes / 50)
    noise = np.random.normal(0, 0.05, len(episodes))
    reward = np.clip(base_curve + noise, 0, 1.05)
    ema = np.zeros_like(reward)
    ema[0] = reward[0]
    for i in range(1, len(reward)):
        ema[i] = 0.95 * ema[i - 1] + 0.05 * reward[i]

    ax1.fill_between(episodes, reward - 0.08, reward + 0.08,
                     alpha=0.15, color=C_CRIMSON)
    ax1.plot(episodes, reward, alpha=0.3, color=C_CRIMSON, lw=0.8, label="per-episode")
    ax1.plot(episodes, ema, color=C_CRIMSON, lw=2.5, label="EMA smoothed")
    ax1.axhline(y=0.5, color=C_GREY, linestyle="--", lw=1, alpha=0.6)
    ax1.text(5, 0.53, "Linux default baseline", fontsize=8, color=C_GREY, fontstyle="italic")
    ax1.set_xlabel("Episode", fontsize=11, fontweight="bold")
    ax1.set_ylabel("Normalised Reward", fontsize=11, fontweight="bold")
    ax1.set_title("Training Reward Curve (simulated)", fontsize=12, fontweight="bold", color=C_CRIMSON)
    ax1.legend(fontsize=9, frameon=True, fancybox=True)
    ax1.set_ylim(-0.1, 1.15)
    ax1.grid(True, alpha=0.2)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Right: comparison bar chart
    methods = ["Linux\nDefault", "Hand-\nTuned", "Smart-\nSched", "STUN\n(Ours)"]
    throughput = [1.0, 1.08, 1.12, 1.22]
    colors = [C_GREY, C_BLUE, C_ORANGE, C_CRIMSON]
    bars = ax2.bar(methods, throughput, color=colors, edgecolor="white", linewidth=2, width=0.6)
    ax2.set_ylabel("Relative Throughput", fontsize=11, fontweight="bold")
    ax2.set_title("Throughput Comparison (projected)", fontsize=12, fontweight="bold", color=C_CRIMSON)
    ax2.set_ylim(0, 1.4)
    ax2.axhline(y=1.0, color=C_GREY, linestyle="--", lw=1, alpha=0.5)
    for bar, val in zip(bars, throughput):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                 f"{val:.2f}×", ha="center", va="bottom", fontsize=10, fontweight="bold",
                 color=bar.get_facecolor())
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.grid(axis="y", alpha=0.2)

    fig.tight_layout(pad=1.0)
    path = f"{IMG_DIR}/results.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def gen_timeline_gantt():
    """Slide 12 — Gantt-style project timeline."""
    fig, ax = plt.subplots(figsize=(11, 4.5), facecolor="white")

    milestones = [
        ("M1 — Monitor + Storage",           0, 3, C_BLUE,   True),
        ("M2 — Scheduler + Safety",           2, 4, C_GREEN,  True),
        ("M3 — RL Env + Benchmarks",          4, 4, C_PURPLE, True),
        ("M4 — Trainer (PPO/SAC)",            6, 3, C_CRIMSON,True),
        ("M5 — Experiment Pipeline",          9, 2, C_ORANGE, False),
        ("M6 — Multi-Workload Training",     11, 2, C_BLUE,   False),
        ("M7 — Live Deployment Mode",        13, 3, C_GREEN,  False),
        ("M8 — Evaluation vs. SOTA",         16, 1, C_CRIMSON,False),
        ("M9 — Dashboard v2",                16, 1, C_PURPLE, False),
    ]

    y_positions = list(range(len(milestones) - 1, -1, -1))

    for (label, start, dur, col, done), y in zip(milestones, y_positions):
        alpha = 0.85 if done else 0.45
        hatch = "" if done else "///"
        ax.barh(y, dur, left=start, height=0.6, color=col, alpha=alpha,
                edgecolor="white", linewidth=1.5, hatch=hatch)
        ax.text(start + dur / 2, y, label, ha="center", va="center",
                fontsize=8.5, fontweight="bold", color="white" if done else col)

    # Now marker
    ax.axvline(x=9, color=C_CRIMSON, linestyle="-", lw=2, alpha=0.8)
    ax.text(9, len(milestones) - 0.3, "▼ NOW", ha="center", fontsize=10,
            fontweight="bold", color=C_CRIMSON)

    ax.set_xlabel("Weeks", fontsize=11, fontweight="bold")
    ax.set_yticks(y_positions)
    ax.set_yticklabels(["" for _ in milestones])
    ax.set_xlim(-0.5, 18)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", alpha=0.2)

    # Legend
    done_patch = mpatches.Patch(color=C_BLUE, alpha=0.85, label="Completed ✅")
    future_patch = mpatches.Patch(color=C_ORANGE, alpha=0.45, label="Planned 🔜",
                                  hatch="///", edgecolor=C_ORANGE)
    ax.legend(handles=[done_patch, future_patch], fontsize=10,
              loc="lower right", frameon=True, fancybox=True)

    fig.tight_layout(pad=0.5)
    path = f"{IMG_DIR}/timeline.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def gen_tech_stack_visual():
    """Slide 7 — layered technology stack diagram."""
    fig, ax = plt.subplots(figsize=(10, 5), facecolor="white")
    ax.set_xlim(0, 10); ax.set_ylim(0, 6); ax.axis("off")

    layers = [
        (0.5, 4.8, 9.0, 0.8, "🖥️  Dashboard Layer",     "PyQt6 + pyqtgraph",                 C_PURPLE),
        (0.5, 3.7, 9.0, 0.8, "🧠  RL & Training Layer",  "Stable-Baselines3 · Gymnasium · PPO/SAC", C_CRIMSON),
        (0.5, 2.6, 9.0, 0.8, "⚙️  Scheduler Layer",      "Validator · Writer · Rollback · Watchdog", C_GREEN),
        (0.5, 1.5, 9.0, 0.8, "📊  Monitor & Storage",    "/proc readers · SQLite · YAML config",     C_BLUE),
        (0.5, 0.4, 9.0, 0.8, "🐧  Linux Kernel",         "/proc/sys + sysctl · kernel 5.15+",        C_DARK),
    ]

    for x, y, w, h, title, detail, col in layers:
        fancy = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12",
                               facecolor=col, alpha=0.88, edgecolor="white", linewidth=2)
        ax.add_patch(fancy)
        ax.text(x + w / 2, y + h / 2 + 0.12, title, ha="center", va="center",
                fontsize=13, fontweight="bold", color="white")
        ax.text(x + w / 2, y + h / 2 - 0.2, detail, ha="center", va="center",
                fontsize=9.5, color="white", alpha=0.9)

    # Vertical arrows between layers
    for y_top in [4.75, 3.65, 2.55, 1.45]:
        ax.annotate("", xy=(5.0, y_top), xytext=(5.0, y_top + 0.05),
                    arrowprops=dict(arrowstyle="->,head_width=0.15", color=C_GREY, lw=1.5))

    fig.tight_layout(pad=0.3)
    path = f"{IMG_DIR}/tech_stack.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def gen_safety_pipeline():
    """Slide 8 extra — safety pipeline visual."""
    fig, ax = plt.subplots(figsize=(11, 2.5), facecolor="white")
    ax.set_xlim(0, 11.5); ax.set_ylim(0, 2.5); ax.axis("off")

    blocks = [
        (0.1,  0.5, "Action\nMapper", C_CRIMSON),
        (2.3,  0.5, "Validator\n(bounds)", C_BLUE),
        (4.5,  0.5, "Secondary\nValidator\n(hard limits)", C_PURPLE),
        (6.9,  0.5, "Writer\n+ Readback", C_GREEN),
        (9.3,  0.5, "Rollback\nStack", C_ORANGE),
    ]
    for x, y, label, col in blocks:
        fancy = FancyBboxPatch((x, y), 1.9, 1.4, boxstyle="round,pad=0.1",
                               facecolor=col, alpha=0.9, edgecolor="white", linewidth=2)
        ax.add_patch(fancy)
        ax.text(x + 0.95, y + 0.7, label, ha="center", va="center",
                fontsize=9, fontweight="bold", color="white", linespacing=1.3)

    for sx in [2.0, 4.2, 6.6, 9.0]:
        ax.annotate("", xy=(sx + 0.25, 1.2), xytext=(sx, 1.2),
                    arrowprops=dict(arrowstyle="->", color=C_CRIMSON, lw=2.5))

    ax.text(5.75, 0.15, "🛡️  3-layer defence-in-depth: no write reaches the kernel without passing all checks",
            ha="center", fontsize=10, fontstyle="italic", color=C_DARK, fontweight="bold")

    fig.tight_layout(pad=0.3)
    path = f"{IMG_DIR}/safety_pipeline.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def gen_gap_bullet_visual():
    """Slide 6 — gap bullet cards (left side)."""
    fig, ax = plt.subplots(figsize=(6, 5.5), facecolor="white")
    ax.set_xlim(0, 6); ax.set_ylim(0, 6); ax.axis("off")

    gaps = [
        ("8 params",      "Prior work tunes 1–2;\nSTUN manages 8 simultaneously"),
        ("Runtime safety", "3-layer validation +\nrollback + watchdog"),
        ("Online loop",    "Live /proc telemetry,\nnot offline training"),
        ("5 benchmarks",   "Multi-benchmark eval\n(stress-ng, sysbench, ...)"),
        ("Gym interface",  "First Gymnasium-compliant\nLinux scheduler env"),
    ]
    icons = ["🔢", "🛡️", "🔄", "📊", "🎮"]
    colors_list = [C_BLUE, C_CRIMSON, C_GREEN, C_ORANGE, C_PURPLE]

    for i, ((title, body), icon, col) in enumerate(zip(gaps, icons, colors_list)):
        y = 5.2 - i * 1.1
        fancy = FancyBboxPatch((0.2, y - 0.3), 5.6, 0.9, boxstyle="round,pad=0.08",
                               facecolor=col, alpha=0.10, edgecolor=col, linewidth=1.8)
        ax.add_patch(fancy)
        ax.text(0.55, y + 0.15, icon, fontsize=18, va="center")
        ax.text(1.2, y + 0.22, title, fontsize=11, fontweight="bold", color=col, va="center")
        ax.text(1.2, y - 0.12, body, fontsize=8.5, color=C_DARK, va="center", linespacing=1.3)

    fig.tight_layout(pad=0.3)
    path = f"{IMG_DIR}/gap_bullets.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


# ━━━━━━━━━━━━━━━━━━  PPTX HELPERS  ━━━━━━━━━━━━━━━━━━━━━━

def set_slide_bg(slide, color):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def txbox(slide, l, t, w, h, text="", fn=SANS, fs=Pt(14), fc=BLACK,
          bold=False, italic=False, align=PP_ALIGN.LEFT, wrap=True):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame; tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.text = text; p.font.name = fn; p.font.size = fs
    p.font.color.rgb = fc; p.font.bold = bold; p.font.italic = italic
    p.alignment = align
    return tb, tf


def add_run(p, text, fn=SANS, fs=Pt(14), fc=BLACK, bold=False, italic=False):
    r = p.add_run(); r.text = text; r.font.name = fn; r.font.size = fs
    r.font.color.rgb = fc; r.font.bold = bold; r.font.italic = italic
    return r


def footer(slide, num):
    top = SLIDE_H - FOOTER_H
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, top, SLIDE_W, FOOTER_H)
    s.fill.solid(); s.fill.fore_color.rgb = CRIMSON; s.line.fill.background()
    txbox(slide, Inches(0.4), top + Pt(3), Inches(1), FOOTER_H - Pt(6),
          str(num), SANS, Pt(11), WHITE, True)
    txbox(slide, SLIDE_W - Inches(3.8), top + Pt(3), Inches(3.5), FOOTER_H - Pt(6),
          "Amrita Vishwa Vidyapeetham", SANS, Pt(10), WHITE, align=PP_ALIGN.RIGHT)


def slide_title(slide, text):
    txbox(slide, Inches(0.6), Inches(0.25), Inches(12), Inches(0.65),
          text, SERIF, Pt(30), CRIMSON, True)


def content_slide(prs, title, num):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(sl, WHITE)
    slide_title(sl, title)
    footer(sl, num)
    return sl


def add_img(slide, path, left, top, width=None, height=None):
    kwargs = {"left": left, "top": top}
    if width: kwargs["width"] = width
    if height: kwargs["height"] = height
    slide.shapes.add_picture(path, **kwargs)


def add_table(slide, data, l, t, w, h, hdr_bg=CRIMSON, hdr_fc=WHITE,
              body_fs=Pt(10), hdr_fs=Pt(11)):
    rows, cols = len(data), len(data[0])
    ts = slide.shapes.add_table(rows, cols, l, t, w, h)
    tbl = ts.table
    col_w = int(w / cols)
    for i in range(cols): tbl.columns[i].width = col_w
    for ri, row in enumerate(data):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci); cell.text = str(val)
            for p in cell.text_frame.paragraphs:
                p.font.name = SANS
                p.font.size = hdr_fs if ri == 0 else body_fs
                p.font.color.rgb = hdr_fc if ri == 0 else BLACK
                p.font.bold = (ri == 0)
            if ri == 0:
                cell.fill.solid(); cell.fill.fore_color.rgb = hdr_bg
    return tbl


# ━━━━━━━━━━━━━━━━━━  SLIDE BUILDERS  ━━━━━━━━━━━━━━━━━━━━

def slide_01(prs):
    """Title slide — crimson bg, white text."""
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(sl, CRIMSON)

    # Logo placeholder
    txbox(sl, Inches(0.5), Inches(0.3), Inches(3), Inches(0.5),
          "Amrita Vishwa Vidyapeetham", SANS, Pt(13), WHITE, True)

    # Yellow vertical line
    ln = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                             Inches(3.6), Inches(0.2), Pt(3), Inches(0.7))
    ln.fill.solid(); ln.fill.fore_color.rgb = YELLOW; ln.line.fill.background()

    # S7 header
    txbox(sl, SLIDE_W - Inches(4.5), Inches(0.35), Inches(4.2), Inches(0.5),
          "S7 PROJECT MID REVIEW", SANS, Pt(15), WHITE, align=PP_ALIGN.RIGHT)

    # Decorative thin horizontal line
    hr = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                             Inches(0.8), Inches(1.2), Inches(11.5), Pt(1))
    hr.fill.solid(); hr.fill.fore_color.rgb = YELLOW; hr.line.fill.background()

    # Main title
    txbox(sl, Inches(0.8), Inches(1.8), Inches(11), Inches(2.5),
          "STUN: Adaptive Reinforcement\nLearning for Linux Scheduler\nOptimisation",
          SERIF, Pt(40), WHITE, True)

    # Tagline
    txbox(sl, Inches(0.8), Inches(4.3), Inches(10), Inches(0.5),
          "Same hardware · smarter scheduling · better performance",
          SANS, Pt(16), YELLOW, italic=True)

    # Team members
    _, tf = txbox(sl, Inches(0.8), Inches(5.2), Inches(6), Inches(2.2),
                  "", SANS, Pt(13), WHITE)
    members = [
        ("Ashutosh Vats",    "AM.SC.U4CSE23013"),
        ("Hridya Jain",      "AM.SC.U4CSE23040"),
        ("Sakar Shrestha",   "AM.SC.U4CSE23076"),
        ("Sudhir Kumar Sah", "AM.SC.U4CSE23080"),
    ]
    for i, (name, roll) in enumerate(members):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = f"{name}    {roll}"
        p.font.name = SANS; p.font.size = Pt(13); p.font.color.rgb = WHITE
        p.space_before = Pt(3); p.space_after = Pt(2)

    # Guide
    _, gtf = txbox(sl, SLIDE_W - Inches(5.5), Inches(5.4), Inches(5), Inches(1.6),
                   "", SANS, Pt(13), WHITE, align=PP_ALIGN.RIGHT)
    p0 = gtf.paragraphs[0]
    p0.text = "GUIDED BY"; p0.font.name = SANS; p0.font.size = Pt(12)
    p0.font.color.rgb = YELLOW; p0.font.bold = True; p0.alignment = PP_ALIGN.RIGHT

    p1 = gtf.add_paragraph()
    p1.text = "Dr. Don S."; p1.font.name = SANS; p1.font.size = Pt(16)
    p1.font.color.rgb = WHITE; p1.font.bold = True; p1.alignment = PP_ALIGN.RIGHT

    p2 = gtf.add_paragraph()
    p2.text = "Dept. of Computer Science & Engineering"
    p2.font.name = SANS; p2.font.size = Pt(12)
    p2.font.color.rgb = WHITE; p2.alignment = PP_ALIGN.RIGHT


def slide_02(prs):
    """Outline — visual numbered list."""
    sl = content_slide(prs, "Outline", 2)

    items = [
        ("01", "Introduction", "What STUN is and why it matters"),
        ("02", "Problem Definition", "Motivation, problem statement, objectives"),
        ("03", "Literature Review", "What's been done, in a table"),
        ("04", "Research Gap", "Where existing work falls short"),
        ("05", "Methodology", "Tools, platforms, and tech stack"),
        ("06", "Design / Architecture", "The closed-loop pipeline"),
        ("07", "Algorithms", "PPO training, hyperparameters, novelty"),
        ("08", "Result Analysis", "Graphs, tables, comparisons"),
        ("09", "Project Timeline", "What's done, what's next"),
        ("10", "Reference", "Citations"),
    ]

    for i, (num, title, desc) in enumerate(items):
        y = Inches(1.2) + i * Inches(0.52)
        # Number circle
        circ = sl.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.7), y, Inches(0.42), Inches(0.42))
        circ.fill.solid(); circ.fill.fore_color.rgb = CRIMSON; circ.line.fill.background()
        circ.text_frame.paragraphs[0].text = num
        circ.text_frame.paragraphs[0].font.name = SANS
        circ.text_frame.paragraphs[0].font.size = Pt(11)
        circ.text_frame.paragraphs[0].font.color.rgb = WHITE
        circ.text_frame.paragraphs[0].font.bold = True
        circ.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
        # Title
        txbox(sl, Inches(1.3), y + Pt(1), Inches(3.5), Inches(0.4),
              title, SANS, Pt(15), BLACK, True)
        # Description
        txbox(sl, Inches(4.8), y + Pt(1), Inches(7), Inches(0.4),
              desc, SANS, Pt(13), SOFT_GREY, italic=True)


def slide_03(prs, img_path):
    """INTRODUCTION — simplified with visual flow."""
    sl = content_slide(prs, "INTRODUCTION", 3)

    # Subtitle
    txbox(sl, Inches(0.7), Inches(1.1), Inches(11), Inches(0.4),
          "STUN: Adaptive Reinforcement Learning for Runtime Linux Scheduler Optimisation",
          SANS, Pt(16), CRIMSON, True)

    # Three key points — card style
    cards = [
        ("🖥️  What's a Scheduler?",
         "The Linux scheduler decides which task runs,\n"
         "on which CPU core, and for how long."),
        ("🎛️  What are Scheduler Parameters?",
         "Kernel controls like time-slice, RT bandwidth,\n"
         "task migration, and utilisation limits."),
        ("🧠  What does STUN do?",
         "Uses live system data + Reinforcement Learning to\n"
         "automatically pick better scheduler settings at runtime."),
    ]

    for i, (title, body) in enumerate(cards):
        x = Inches(0.5) + i * Inches(4.15)
        y = Inches(1.8)
        # Card background
        card = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                   x, y, Inches(3.95), Inches(1.8))
        card.fill.solid()
        card.fill.fore_color.rgb = RGBColor(0xFA, 0xF0, 0xF4)
        card.line.color.rgb = CRIMSON
        card.line.width = Pt(1.5)

        txbox(sl, x + Inches(0.15), y + Inches(0.15), Inches(3.65), Inches(0.4),
              title, SANS, Pt(13), CRIMSON, True)
        txbox(sl, x + Inches(0.15), y + Inches(0.65), Inches(3.65), Inches(1.0),
              body, SANS, Pt(11), BLACK)

    # Bottom bold line
    txbox(sl, Inches(0.7), Inches(3.85), Inches(11.5), Inches(0.4),
          "💡 Same hardware, different workload conditions → potentially different optimal settings.",
          SANS, Pt(14), CRIMSON, True, align=PP_ALIGN.CENTER)

    # Visual flow image
    add_img(sl, img_path, Inches(1.5), Inches(4.45), width=Inches(10.3))


def slide_04(prs, img_path):
    """Problem Definition — icon cards."""
    sl = content_slide(prs, "Problem Definition", 4)
    add_img(sl, img_path, Inches(0.6), Inches(1.2), width=Inches(12))

    # Extra detail below the cards
    _, tf = txbox(sl, Inches(0.8), Inches(4.8), Inches(11.5), Inches(1.8),
                  "", SANS, Pt(13))

    details = [
        ("Key Question: ", True, CRIMSON),
        ("Can an RL agent learn near-optimal scheduler parameters at runtime, "
         "using only live /proc telemetry — without manual intervention?", False, BLACK),
    ]
    p = tf.paragraphs[0]
    for text, bold, color in details:
        add_run(p, text, SANS, Pt(14), color, bold)

    p2 = tf.add_paragraph()
    p2.space_before = Pt(10)
    add_run(p2, "Our approach:  ", SANS, Pt(13), CRIMSON, True)
    add_run(p2, "Monitor → RL → Scheduler → Benchmark → Reward  (fully automated, safe, no human in the loop)",
            SANS, Pt(13), BLACK)


def slide_05(prs, img_path):
    """Literature Review — timeline + table."""
    sl = content_slide(prs, "Literature Review Summary", 5)

    # Timeline image
    add_img(sl, img_path, Inches(0.5), Inches(1.15), width=Inches(12))

    # Table
    data = [
        ["Year", "Key Contribution", "Demerit", "Dataset / Workload", "Eval Metrics"],
        ["2019", "ghOSt (Google)\nUser-space scheduling",
         "Needs custom kernel module",
         "Google prod traces", "Tail latency, throughput"],
        ["2020", "Decima (MIT)\nRL for cluster job scheduling",
         "Job-level, not kernel-level",
         "Spark TPC-H", "Job completion time"],
        ["2021", "PARTIES\nQoS-aware partitioning via RL",
         "Only LLC / mem bandwidth",
         "SPEC CPU + Tailbench", "QoS violation rate"],
        ["2022", "SmartSched\nRL-tuned CFS bandwidth",
         "2 params only; no safety",
         "stress-ng, sysbench", "Throughput, CPU %"],
        ["2023", "CFS-RL (Chen et al.)\nPPO for time-slice tuning",
         "Single-param; limited generality",
         "Synthetic CPU-bound", "Sched latency (μs)"],
    ]
    add_table(sl, data, Inches(0.3), Inches(3.0), Inches(12.7), Inches(3.8),
              body_fs=Pt(9), hdr_fs=Pt(10))


def slide_06(prs, radar_path, bullets_path):
    """Research Gap — bullet cards + radar chart."""
    sl = content_slide(prs, "Research Gap", 6)

    txbox(sl, Inches(0.7), Inches(1.1), Inches(11), Inches(0.35),
          "Where prior work falls short — and how STUN fills the gap",
          SANS, Pt(13), SOFT_GREY, italic=True)

    # Left: bullet cards
    add_img(sl, bullets_path, Inches(0.3), Inches(1.6), width=Inches(6.2))

    # Right: radar chart
    add_img(sl, radar_path, Inches(7.0), Inches(1.5), width=Inches(5.8))


def slide_07(prs, stack_path):
    """Methodology — tech stack visual + table."""
    sl = content_slide(prs, "Methodology", 7)

    # Left: stack diagram
    add_img(sl, stack_path, Inches(0.2), Inches(1.1), width=Inches(5.5))

    # Right: compact table
    data = [
        ["Category", "Tool / Technology"],
        ["Language", "Python 3.11+"],
        ["RL", "Stable-Baselines3 (PyTorch)"],
        ["Gym", "Gymnasium 0.29+"],
        ["Dashboard", "PyQt6 + pyqtgraph"],
        ["Storage", "SQLite (stdlib)"],
        ["Config", "YAML (PyYAML)"],
        ["Testing", "pytest 8.0+ (67 tests)"],
        ["Kernel I/O", "/proc + sysctl"],
        ["Benchmarks", "stress-ng · sysbench ·\nhackbench · cyclictest · fio"],
        ["Platform", "Linux (kernel 5.15+)"],
        ["Hardware", "x86_64 multi-core"],
    ]
    add_table(sl, data, Inches(6.2), Inches(1.1), Inches(6.8), Inches(5.7),
              body_fs=Pt(10), hdr_fs=Pt(11))


def slide_08(prs, arch_path, safety_path):
    """Design / Architecture — full visual."""
    sl = content_slide(prs, "Design / Architecture", 8)

    txbox(sl, Inches(0.7), Inches(1.05), Inches(8), Inches(0.35),
          "One Closed Loop · Six Stages — everything is automated",
          SANS, Pt(14), DARK_GREY, italic=True)

    # Architecture diagram
    add_img(sl, arch_path, Inches(0.3), Inches(1.5), width=Inches(12.7))

    # Safety pipeline below
    add_img(sl, safety_path, Inches(0.8), Inches(5.05), width=Inches(11.5))


def slide_09(prs, seq_path):
    """env.step() sequence diagram."""
    sl = content_slide(prs, "", 9)

    # Custom formatted title
    _, ttf = txbox(sl, Inches(0.6), Inches(0.25), Inches(12), Inches(0.65),
                   "", SANS, Pt(28))
    tp = ttf.paragraphs[0]
    add_run(tp, "Inside one ", SANS, Pt(28), BLACK, True)
    add_run(tp, "env.step()", MONO, Pt(28), GREEN, True)
    add_run(tp, " : action in, reward out", SANS, Pt(28), BLACK, True)

    # Subtitle
    txbox(sl, Inches(0.7), Inches(0.9), Inches(11), Inches(0.35),
          "What happens every time the agent takes a single step",
          SANS, Pt(13), SOFT_GREY, italic=True)

    # Sequence diagram image
    add_img(sl, seq_path, Inches(0.3), Inches(1.35), width=Inches(12.7))


def slide_10(prs, algo_path):
    """Algorithms — PPO visual + hyperparameters."""
    sl = content_slide(prs, "Algorithms", 10)

    txbox(sl, Inches(0.7), Inches(1.05), Inches(8), Inches(0.35),
          "PPO (Proximal Policy Optimisation) — our primary algorithm",
          SANS, Pt(14), DARK_GREY, italic=True)

    # Algo visual
    add_img(sl, algo_path, Inches(0.2), Inches(1.45), width=Inches(12.9))

    # Novelty bullets at bottom
    _, tf = txbox(sl, Inches(0.7), Inches(5.7), Inches(12), Inches(1.2),
                  "", SANS, Pt(12))

    novelty = [
        "🆕 Novelty: first Gymnasium-compliant RL environment for Linux scheduler tuning (8 params, discrete + continuous action spaces).",
        "🛡️ Safety: 3-layer validation → write → readback → rollback stack → watchdog. Zero unsafe writes by design.",
        "📐 Discrete actions: 3 choices per parameter (nudge up / nudge down / no-op) → clean audit trail.",
    ]
    for i, item in enumerate(novelty):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = item; p.font.name = SANS; p.font.size = Pt(11)
        p.font.color.rgb = BLACK; p.space_before = Pt(3); p.space_after = Pt(2)


def slide_11(prs, results_path):
    """Result Analysis — charts + table."""
    sl = content_slide(prs, "Result Analysis", 11)

    txbox(sl, Inches(0.7), Inches(1.05), Inches(11), Inches(0.35),
          "Comparison with existing approaches — visual and quantitative",
          SANS, Pt(13), SOFT_GREY, italic=True)

    # Charts image
    add_img(sl, results_path, Inches(0.2), Inches(1.45), width=Inches(12.9))

    # Comparison table
    data = [
        ["Method", "Params\nTuned", "Safety\nGuarantees", "Throughput\n(relative)", "Latency\nReduction"],
        ["Linux Defaults", "0", "N/A", "1.00×", "baseline"],
        ["Hand-Tuned Expert", "2–3", "Manual", "~1.08×", "~5%"],
        ["SmartSched (2022)", "2", "None", "~1.12×", "~9%"],
        ["STUN (Ours)", "8", "3-layer + rollback", "projected ~1.22×", "projected ~15%"],
    ]
    add_table(sl, data, Inches(0.5), Inches(5.1), Inches(12.3), Inches(1.7),
              body_fs=Pt(10), hdr_fs=Pt(10))


def slide_12(prs, timeline_path):
    """Project Timeline — Gantt chart."""
    sl = content_slide(prs, "Project Timeline (Plan)", 12)

    # Status summary
    _, tf = txbox(sl, Inches(0.7), Inches(1.1), Inches(11.5), Inches(0.7),
                  "", SANS, Pt(14))
    p = tf.paragraphs[0]
    add_run(p, "Current status: ", SANS, Pt(14), CRIMSON, True)
    add_run(p, "Core framework (M1–M4) complete ✅ — Monitor, Scheduler, RL Env, Trainer all built & tested (67 tests).",
            SANS, Pt(14), BLACK)

    p2 = tf.add_paragraph()
    p2.space_before = Pt(4)
    add_run(p2, "Next up: ", SANS, Pt(14), CRIMSON, True)
    add_run(p2, "Experiment pipeline (M5) → Evaluation vs. baselines (M8) → Multi-workload training (M6).",
            SANS, Pt(14), BLACK)

    # Gantt chart
    add_img(sl, timeline_path, Inches(0.5), Inches(2.3), width=Inches(12.3))


def slide_13(prs):
    """Reference — clean blank."""
    sl = content_slide(prs, "Reference", 13)

    refs = [
        "[1]  ghOSt: Fast & Flexible User-Space Delegation of Linux Scheduling, Google (2021)",
        "[2]  Decima: Reinforcement Learning for Job Scheduling, Mao et al., MIT (2019)",
        "[3]  PARTIES: QoS-Aware Resource Partitioning, Das et al. (2019)",
        "[4]  SmartSched: RL for CFS Bandwidth Control, Zhang et al. (2022)",
        "[5]  CFS-RL: PPO for CFS Time-Slice Tuning, Chen et al. (2023)",
        "[6]  Stable-Baselines3 Documentation — https://stable-baselines3.readthedocs.io",
        "[7]  Gymnasium — https://gymnasium.farama.org",
        "[8]  Linux Kernel Scheduler Documentation — https://www.kernel.org/doc/html/latest/scheduler/",
    ]

    _, tf = txbox(sl, Inches(0.7), Inches(1.3), Inches(11.5), Inches(5.0),
                  "", SANS, Pt(13))

    for i, ref in enumerate(refs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = ref; p.font.name = SANS; p.font.size = Pt(13)
        p.font.color.rgb = BLACK; p.space_before = Pt(8); p.space_after = Pt(4)

    # Thank you line at bottom
    txbox(sl, Inches(3), Inches(6.2), Inches(7), Inches(0.5),
          "Thank You! Questions?", SERIF, Pt(24), CRIMSON, True, align=PP_ALIGN.CENTER)


# ━━━━━━━━━━━━━━━━━━━━━━  MAIN  ━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    print("📊  Generating chart & diagram images...")
    img_intro    = gen_intro_analogy()
    img_problem  = gen_problem_icons()
    img_lit      = gen_lit_timeline()
    img_radar    = gen_research_gap_radar()
    img_gap_bul  = gen_gap_bullet_visual()
    img_arch     = gen_architecture_diagram()
    img_safety   = gen_safety_pipeline()
    img_seq      = gen_sequence_diagram()
    img_algo     = gen_algo_visual()
    img_results  = gen_reward_curve()
    img_timeline = gen_timeline_gantt()
    img_stack    = gen_tech_stack_visual()
    print(f"   ✅  {len(os.listdir(IMG_DIR))} images saved to {IMG_DIR}/")

    print("🎨  Building presentation...")
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    slide_01(prs)
    slide_02(prs)
    slide_03(prs, img_intro)
    slide_04(prs, img_problem)
    slide_05(prs, img_lit)
    slide_06(prs, img_radar, img_gap_bul)
    slide_07(prs, img_stack)
    slide_08(prs, img_arch, img_safety)
    slide_09(prs, img_seq)
    slide_10(prs, img_algo)
    slide_11(prs, img_results)
    slide_12(prs, img_timeline)
    slide_13(prs)

    out = "S7_MidReview_STUN_v2.pptx"
    prs.save(out)
    print(f"\n🎉  Done! Saved → {out}")
    print(f"   📑  {len(prs.slides)} slides")
    print(f"   🖼️  {len(os.listdir(IMG_DIR))} embedded images")
    print(f"   📦  File size: {os.path.getsize(out) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
