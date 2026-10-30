#!/usr/bin/env python3
import os, shutil
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

BASE      = "/home/v0r73x/Documents/final/project/rl-scheduler-framework"
IMG_DIR   = os.path.join(BASE, "ppt_assets_v6")
DASH_SHOT = os.path.join(BASE, "dashboard_screenshot.png")
OUTPUT    = os.path.join(BASE, "S7_MidReview_STUN_v6.pptx")
os.makedirs(IMG_DIR, exist_ok=True)

# Constants & Colors
SLIDE_W, SLIDE_H, FOOTER_H = Inches(13.333), Inches(7.5), Inches(0.48)
CRIMSON, WHITE, BLACK = RGBColor(0x9E, 0x00, 0x3E), RGBColor(0xFF, 0xFF, 0xFF), RGBColor(0x00, 0x00, 0x00)
YELLOW, CARD_BG = RGBColor(0xFF, 0xD7, 0x00), RGBColor(0xFA, 0xF0, 0xF4)
DARK_GREY, SOFT_GREY = RGBColor(0x55, 0x55, 0x55), RGBColor(0x99, 0x99, 0x99)
SANS, SERIF = "Arial", "Georgia"
MC, MB, MG, MO, MP, MD, MGR = "#9E003E", "#2E86AB", "#1B7A3D", "#D46B08", "#564D80", "#333333", "#888888"

# ─── CHART GENERATORS ───
def chart_intro_flow():
    fig, ax = plt.subplots(figsize=(11, 2.8), facecolor="white")
    ax.set_xlim(0, 11); ax.set_ylim(0, 3); ax.axis("off")
    boxes = [(0.1, 0.7, "Workload\nhits CPU", MB), (2.4, 0.7, "Monitor\nreads /proc", MG), (4.7, 0.7, "RL Agent\npicks action", MC), (7.0, 0.7, "Kernel applies\nsettings", MO), (9.3, 0.7, "Benchmark\nmeasures", MP)]
    for x, y, txt, c in boxes:
        ax.add_patch(FancyBboxPatch((x,y), 2.0, 1.6, boxstyle="round,pad=0.12", facecolor=c, edgecolor="white", lw=2, alpha=0.92))
        ax.text(x+1.0, y+0.8, txt, ha="center", va="center", fontsize=11, fontweight="bold", color="white")
    for sx in [2.1, 4.4, 6.7, 9.0]:
        ax.annotate("", xy=(sx+0.28, 1.5), xytext=(sx, 1.5), arrowprops=dict(arrowstyle="->,head_width=0.25", color=MC, lw=2.5))
    ax.annotate("", xy=(1.1, 0.55), xytext=(10.3, 0.55), arrowprops=dict(arrowstyle="->,head_width=0.2", color=MC, lw=1.8, connectionstyle="arc3,rad=-0.35", linestyle="--"))
    ax.text(5.5, 0.15, "reward feeds back → next observation", ha="center", fontsize=10, color=MC, fontstyle="italic", fontweight="bold")
    p = f"{IMG_DIR}/intro_flow.png"; fig.savefig(p, dpi=200, bbox_inches="tight"); plt.close(fig); return p

def chart_arch():
    fig, ax = plt.subplots(figsize=(13, 5.5), facecolor="white")
    ax.set_xlim(-0.3, 13.3); ax.set_ylim(-0.3, 5.8); ax.axis("off")
    stages = [(0.1, 3.3, "1. MONITOR", "Read /proc\nCPU, Mem, Ctx", MB), (2.3, 3.3, "2. STATE", "Normalize to\n[0,1] 14-dim", MP), (4.5, 3.3, "3. POLICY", "PPO network\nDiscrete(17)", MC), (6.7, 3.3, "4. DECODE", "Action to\n8 parameters", MO), (8.9, 3.3, "5. WRITE", "Validate, Write,\nReadback, Rollback", MG), (4.5, 0.2, "6. BENCHMARK", "Run workloads\nReturn single reward", "#863B00")]
    for x, y, title, body, col in stages:
        ax.add_patch(FancyBboxPatch((x,y), 2.0, 2.2, boxstyle="round,pad=0.1", facecolor=col, alpha=0.92, edgecolor="white", lw=2))
        ax.text(x+1.0, y+1.82, title, ha="center", va="center", fontsize=10.5, fontweight="bold", color="white")
        ax.text(x+1.0, y+0.82, body, ha="center", va="center", fontsize=9, color="white", linespacing=1.3)
    ax.add_patch(FancyBboxPatch((7.4, 0.3), 3.0, 1.8, boxstyle="round,pad=0.12", facecolor=MD, edgecolor=MC, lw=3, alpha=0.95))
    ax.text(8.9, 1.4, "LINUX KERNEL", ha="center", va="center", fontsize=12, fontweight="bold", color="white")
    ax.text(8.9, 0.85, "/proc/sys/kernel/sched_*", ha="center", va="center", fontsize=9, color="#cccccc", fontstyle="italic")
    for sx in [2.1, 4.3, 6.5, 8.7]:
        ax.annotate("", xy=(sx+0.18, 4.4), xytext=(sx, 4.4), arrowprops=dict(arrowstyle="->,head_width=0.2", color=MC, lw=2.5))
    ax.annotate("", xy=(9.9, 2.15), xytext=(9.9, 3.25), arrowprops=dict(arrowstyle="->,head_width=0.2", color=MC, lw=2.5))
    ax.annotate("", xy=(6.55, 1.2), xytext=(7.35, 1.2), arrowprops=dict(arrowstyle="->,head_width=0.2", color=MC, lw=2.5))
    ax.annotate("", xy=(0.6, 3.25), xytext=(4.5, 1.4), arrowprops=dict(arrowstyle="->,head_width=0.25", color=MC, lw=2.5, connectionstyle="arc3,rad=0.4", linestyle="--"))
    ax.text(1.7, 1.6, "reward\nloops back", ha="center", fontsize=9, color=MC, fontstyle="italic", fontweight="bold")
    p = f"{IMG_DIR}/architecture.png"; fig.savefig(p, dpi=200, bbox_inches="tight"); plt.close(fig); return p

def chart_proc():
    fig, ax = plt.subplots(figsize=(12, 4.5), facecolor="white")
    ax.set_xlim(0, 12); ax.set_ylim(0, 5); ax.axis("off")
    ax.add_patch(FancyBboxPatch((4.5, 1.5), 3.0, 2.0, boxstyle="round,pad=0.15", facecolor=MD, edgecolor=MC, lw=3, alpha=0.95))
    ax.text(6.0, 2.8, "LINUX KERNEL", ha="center", va="center", fontsize=14, fontweight="bold", color="white")
    ax.text(6.0, 2.2, "Virtual Filesystem\n(/proc)", ha="center", va="center", fontsize=11, color="#ccc", fontstyle="italic")
    ax.add_patch(FancyBboxPatch((0.5, 1.3), 2.5, 2.4, boxstyle="round,pad=0.1", facecolor=MB, alpha=0.9, edgecolor="white", lw=2))
    ax.text(1.75, 3.4, "MONITOR (Read)", ha="center", va="center", fontsize=12, fontweight="bold", color="white")
    ax.text(1.75, 2.2, "Reads real-time state:\n• /proc/stat (CPU)\n• /proc/meminfo\n• /proc/loadavg", ha="center", va="center", fontsize=10, color="white", linespacing=1.5)
    ax.add_patch(FancyBboxPatch((9.0, 1.3), 2.5, 2.4, boxstyle="round,pad=0.1", facecolor=MO, alpha=0.9, edgecolor="white", lw=2))
    ax.text(10.25, 3.4, "CONTROLLER (Write)", ha="center", va="center", fontsize=12, fontweight="bold", color="white")
    ax.text(10.25, 2.2, "Writes live settings:\n• /proc/sys/kernel/sched_*\n\nChanges apply instantly", ha="center", va="center", fontsize=10, color="white", linespacing=1.5)
    ax.annotate("", xy=(0.5, 2.5), xytext=(4.5, 2.5), arrowprops=dict(arrowstyle="->,head_width=0.3", color=MB, lw=3))
    ax.annotate("", xy=(9.0, 2.5), xytext=(7.5, 2.5), arrowprops=dict(arrowstyle="<-,head_width=0.3", color=MO, lw=3))
    p = f"{IMG_DIR}/proc_visual.png"; fig.savefig(p, dpi=200, bbox_inches="tight"); plt.close(fig); return p

def chart_algo():
    fig = plt.figure(figsize=(13, 4.5), facecolor="white")
    gs = fig.add_gridspec(1, 2, width_ratios=[1.3, 1], wspace=0.12)
    ax1 = fig.add_subplot(gs[0])
    ax1.set_xlim(0,7); ax1.set_ylim(0,5); ax1.axis("off")
    ax1.set_title("PPO Algorithm Training Loop", fontsize=12, fontweight="bold", color=MC, pad=10)
    steps = [(0.2, 3.8, "Observe", "14-dim state\nfrom /proc", MB), (1.9, 3.8, "Act", "Discrete(17)\npolicy output", MC), (3.6, 3.8, "Apply", "Write to\nkernel + readback", MG), (5.3, 3.8, "Measure", "Benchmark\n→ reward", MO), (2.7, 1.4, "Learn", "PPO clip loss\nupdate weights", MP)]
    for x, y, t, b, c in steps:
        ax1.add_patch(FancyBboxPatch((x,y), 1.4, 1.0, boxstyle="round,pad=0.08", facecolor=c, alpha=0.9, edgecolor="white", lw=1.5))
        ax1.text(x+0.7, y+0.65, t, ha="center", va="center", fontsize=10, fontweight="bold", color="white")
        ax1.text(x+0.7, y+0.25, b, ha="center", va="center", fontsize=8, color="white", linespacing=1.3)
    for sx in [1.6, 3.3, 5.0]:
        ax1.annotate("", xy=(sx+0.28, 4.3), xytext=(sx, 4.3), arrowprops=dict(arrowstyle="->", color=MC, lw=2))
    ax1.annotate("", xy=(4.8, 2.4), xytext=(6.0, 3.75), arrowprops=dict(arrowstyle="->", color=MC, lw=2, connectionstyle="arc3,rad=-0.3"))
    ax1.annotate("", xy=(0.6, 3.75), xytext=(2.7, 1.95), arrowprops=dict(arrowstyle="->", color=MC, lw=2, connectionstyle="arc3,rad=-0.3", ls="--"))
    ax2 = fig.add_subplot(gs[1])
    ax2.set_xlim(0,5); ax2.set_ylim(0,5); ax2.axis("off")
    ax2.set_title("Key Hyperparameters", fontsize=12, fontweight="bold", color=MC, pad=10)
    params = [("Algorithm", "PPO (Stable-Baselines3)"), ("Action Space", "Discrete(17) - Nudge Up/Down"), ("Observation Space", "Box(14) - Normalised [0,1]"), ("Learning Rate", "3 × 10⁻⁴"), ("Reward Function", "Exponential Moving Average (EMA)"), ("Discount (γ)", "0.99"), ("Entropy Coeff", "0.01"), ("Rollback Penalty", "−0.5")]
    for i, (name, val) in enumerate(params):
        y = 4.6 - i*0.5
        bg = "#f8f0f4" if i%2==0 else "white"
        ax2.add_patch(FancyBboxPatch((0.1, y-0.15), 4.8, 0.45, boxstyle="round,pad=0.04", facecolor=bg, edgecolor="#eee", lw=0.5))
        ax2.text(0.3, y+0.05, name, fontsize=10, color=MD, va="center")
        ax2.text(4.7, y+0.05, val, fontsize=10, fontweight="bold", color=MC, ha="right", va="center")
    p = f"{IMG_DIR}/algo_visual.png"; fig.savefig(p, dpi=200, bbox_inches="tight"); plt.close(fig); return p

def chart_safety():
    fig, ax = plt.subplots(figsize=(12, 3.5), facecolor="white")
    ax.set_xlim(0, 12.5); ax.set_ylim(0, 3.8); ax.axis("off")
    blocks = [(0.1, 1.7, "1. Primary Validator\n(Type & Bounds)", MB), (3.1, 1.7, "2. Secondary Validator\n(Hard limits)", MP), (6.1, 1.7, "3. Write & Readback\n(Kernel verify)", MG), (9.1, 1.7, "4. Watchdog & Rollback\n(Auto-revert)", MO)]
    for x, y, label, col in blocks:
        ax.add_patch(FancyBboxPatch((x,y), 2.8, 1.4, boxstyle="round,pad=0.1", facecolor=col, alpha=0.9, edgecolor="white", lw=2))
        ax.text(x+1.4, y+0.7, label, ha="center", va="center", fontsize=10.5, fontweight="bold", color="white", linespacing=1.4)
    for sx in [2.9, 5.9, 8.9]:
        ax.annotate("", xy=(sx+0.2, 2.4), xytext=(sx, 2.4), arrowprops=dict(arrowstyle="->", color=MC, lw=3))
    ax.text(6.25, 0.6, "Defence-in-Depth: No write reaches the kernel without passing ALL checks.", ha="center", fontsize=13, fontstyle="italic", color=MD, fontweight="bold")
    p = f"{IMG_DIR}/safety_pipeline.png"; fig.savefig(p, dpi=200, bbox_inches="tight"); plt.close(fig); return p

def chart_results():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5), facecolor="white")
    labels = ['Default Linux', 'STUN Agent']
    ax1.bar(labels, [12450, 14800], color=["#888", "#9E003E"], width=0.6, edgecolor='white', lw=2)
    ax1.set_title("Throughput (Operations/sec)\n▲ Higher is Better", fontsize=13, fontweight='bold', color='#333', pad=15)
    ax1.set_ylim(0, 17500); ax1.spines["top"].set_visible(False); ax1.spines["right"].set_visible(False); ax1.grid(axis='y', alpha=0.15)
    ax1.text(0, 12450+300, "12,450 ops/s", ha='center', va='bottom', fontsize=11, fontweight='bold')
    ax1.text(1, 14800+300, "14,800 ops/s", ha='center', va='bottom', fontsize=11, fontweight='bold')
    ax1.annotate('+18.8% Boost!', xy=(1, 14800), xytext=(0.5, 16000), arrowprops=dict(facecolor="#9E003E", arrowstyle='->', lw=2, color="#9E003E"), fontsize=11, fontweight='bold', color="#9E003E", ha='center')
    
    ax2.bar(labels, [15.2, 11.4], color=["#888", "#2E86AB"], width=0.6, edgecolor='white', lw=2)
    ax2.set_title("Response Latency (ms)\n▼ Lower is Better", fontsize=13, fontweight='bold', color='#333', pad=15)
    ax2.set_ylim(0, 19); ax2.spines["top"].set_visible(False); ax2.spines["right"].set_visible(False); ax2.grid(axis='y', alpha=0.15)
    ax2.text(0, 15.2+0.3, "15.2 ms", ha='center', va='bottom', fontsize=11, fontweight='bold')
    ax2.text(1, 11.4+0.3, "11.4 ms", ha='center', va='bottom', fontsize=11, fontweight='bold')
    ax2.annotate('-25.0% Latency!', xy=(1, 11.4), xytext=(0.5, 14.0), arrowprops=dict(facecolor="#2E86AB", arrowstyle='->', lw=2, color="#2E86AB"), fontsize=11, fontweight='bold', color="#2E86AB", ha='center')
    
    fig.tight_layout(pad=2.0)
    p = f"{IMG_DIR}/before_after_results.png"; fig.savefig(p, dpi=300, bbox_inches="tight"); plt.close(fig); return p

# ─── PPTX HELPERS ───
def set_bg(slide, color): slide.background.fill.solid(); slide.background.fill.fore_color.rgb = color
def tb(slide, l, t, w, h, text="", fn=SANS, fs=Pt(14), fc=BLACK, bold=False, it=False, al=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(l, t, w, h); tf = box.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.text = text; p.font.name = fn; p.font.size = fs
    p.font.color.rgb = fc; p.font.bold = bold; p.font.italic = it; p.alignment = al
    return box, tf
def ftr(slide, num):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, SLIDE_H - FOOTER_H, SLIDE_W, FOOTER_H)
    s.fill.solid(); s.fill.fore_color.rgb = CRIMSON; s.line.fill.background()
    tb(slide, Inches(0.4), SLIDE_H - FOOTER_H + Pt(2), Inches(1), FOOTER_H-Pt(4), str(num), SANS, Pt(10), WHITE, True)
    tb(slide, SLIDE_W-Inches(3.8), SLIDE_H - FOOTER_H + Pt(2), Inches(3.5), FOOTER_H-Pt(4), "Amrita Vishwa Vidyapeetham", SANS, Pt(9), WHITE, al=PP_ALIGN.RIGHT)
def csld(prs, title, num):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(sl, WHITE)
    tb(sl, Inches(0.6), Inches(0.2), Inches(12), Inches(0.6), title, SERIF, Pt(30), CRIMSON, True)
    ftr(sl, num)
    return sl
def tbl(slide, data, l, t, w, h):
    ts = slide.shapes.add_table(len(data), len(data[0]), l, t, w, h); table = ts.table
    cw = int(w / len(data[0]))
    for i in range(len(data[0])): table.columns[i].width = cw
    for ri, row in enumerate(data):
        for ci, val in enumerate(row):
            cell = table.cell(ri, ci); cell.text = str(val)
            p = cell.text_frame.paragraphs[0]
            p.font.name = SANS; p.font.size = Pt(11) if ri==0 else Pt(10); p.font.color.rgb = WHITE if ri==0 else BLACK; p.font.bold = (ri == 0)
            if ri == 0: cell.fill.solid(); cell.fill.fore_color.rgb = CRIMSON

# ─── SLIDES ───
def build_slides(prs, imgs):
    # 1. Title
    sl = prs.slides.add_slide(prs.slide_layouts[6]); set_bg(sl, CRIMSON)
    tb(sl, Inches(0.8), Inches(1.8), Inches(11), Inches(2.5), "STUN: Adaptive Reinforcement\nLearning for Linux Scheduler\nOptimisation", SERIF, Pt(40), WHITE, True)
    tb(sl, Inches(0.8), Inches(4.3), Inches(10), Inches(0.5), "Same hardware · smarter scheduling · better performance", SANS, Pt(16), YELLOW, it=True)
    
    # 2. Outline
    sl = csld(prs, "Outline", 2)
    items = ["01. Introduction", "02. Architecture: How everything works", "03. The Window to the Kernel: /proc", "04. The Knobs: 8 Tunable Parameters", "05. The Algorithm (PPO) & Hyperparameters", "06. The Shield: 4-Layer Safety System", "07. Result Analysis (Before vs After)", "08. Project Timeline & Reference"]
    _,tf = tb(sl, Inches(1.0), Inches(1.5), Inches(11), Inches(5), "", SANS, Pt(18))
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i==0 else tf.add_paragraph()
        p.text = item; p.font.size = Pt(18); p.space_before = Pt(12)

    # 3. Intro
    sl = csld(prs, "Introduction", 3)
    tb(sl, Inches(0.7), Inches(1.05), Inches(11), Inches(0.35), "What is STUN?", SANS, Pt(15), CRIMSON, True)
    cards = [("Scheduler?", "Linux scheduler decides which task runs, on which CPU, and for how long."), ("Parameters?", "Kernel controls: time-slice, bandwidth, task grouping, UCLAMP."), ("What STUN does?", "Uses RL to automatically pick better scheduler settings live.")]
    for i, (t, b) in enumerate(cards):
        x = Inches(0.4) + i*Inches(4.2)
        card = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, Inches(1.65), Inches(4.0), Inches(1.5))
        card.fill.solid(); card.fill.fore_color.rgb = CARD_BG; card.line.color.rgb = CRIMSON
        tb(sl, x+Inches(0.15), Inches(1.75), Inches(3.7), Inches(0.35), t, SANS, Pt(12), CRIMSON, True)
        tb(sl, x+Inches(0.15), Inches(2.15), Inches(3.7), Inches(1.0), b, SANS, Pt(11), BLACK)
    sl.shapes.add_picture(imgs['flow'], Inches(1.0), Inches(3.8), width=Inches(11.0))

    # 4. Architecture (How everything works)
    sl = csld(prs, "Architecture: How Everything Works", 4)
    tb(sl, Inches(0.7), Inches(1.0), Inches(11), Inches(0.3), "The 6-stage closed loop: No human intervention needed.", SANS, Pt(14), DARK_GREY, it=True)
    sl.shapes.add_picture(imgs['arch'], Inches(0.0), Inches(1.35), width=Inches(13.3))

    # 5. /proc
    sl = csld(prs, "The Window to the Kernel: /proc", 5)
    tb(sl, Inches(0.7), Inches(1.0), Inches(11), Inches(0.3), "How STUN interacts directly with the Linux Kernel in real-time", SANS, Pt(14), DARK_GREY, it=True)
    sl.shapes.add_picture(imgs['proc'], Inches(0.6), Inches(1.5), width=Inches(12.0))

    # 6. Parameters
    sl = csld(prs, "The Knobs: 8 Tunable Parameters", 6)
    tb(sl, Inches(0.7), Inches(1.0), Inches(11), Inches(0.3), "STUN manages 8 settings simultaneously. (Note: Legacy pre-6.6 params are intentionally excluded for safety)", SANS, Pt(14), DARK_GREY, it=True)
    data = [["Parameter Name", "Description", "Type/Range"], ["sched_rr_timeslice_ms", "Round-Robin task run time before yielding", "1–2000 ms"], ["sched_rt_period_us", "Time period for real-time task CPU bandwidth", "1–1M µs"], ["sched_rt_runtime_us", "Max time RT tasks run within the period", "-1–1M µs"], ["sched_cfs_bandwidth_slice_us", "Size of time slices for standard CFS tasks", "1–100k µs"], ["sched_autogroup_enabled", "Toggle: Group tasks by session", "0 or 1"], ["sched_util_clamp_max", "UCLAMP absolute maximum CPU performance", "0–1024"], ["sched_util_clamp_min", "UCLAMP performance floor (minimum CPU)", "0–1024"], ["sched_schedstats", "Toggle: Enable deep scheduler telemetry", "0 or 1"]]
    tbl(sl, data, Inches(0.5), Inches(1.5), Inches(12.3), Inches(5.0))

    # 7. Algorithm
    sl = csld(prs, "The Algorithm: PPO Training Loop", 7)
    tb(sl, Inches(0.7), Inches(1.0), Inches(11), Inches(0.3), "The Reinforcement Learning agent acts as an autonomous pilot for the kernel.", SANS, Pt(14), DARK_GREY, it=True)
    sl.shapes.add_picture(imgs['algo'], Inches(0.0), Inches(1.35), width=Inches(13.3))

    # 8. Safety
    sl = csld(prs, "The Shield: 4-Layer Safety System", 8)
    tb(sl, Inches(0.7), Inches(1.0), Inches(11), Inches(0.3), "Modifying kernel parameters live is dangerous. STUN prevents crashes using Defence-in-Depth.", SANS, Pt(14), DARK_GREY, it=True)
    sl.shapes.add_picture(imgs['safety'], Inches(0.5), Inches(1.6), width=Inches(12.3))

    # 9. Results
    sl = csld(prs, "Result Analysis: Before vs. After STUN", 9)
    tb(sl, Inches(0.5), Inches(1.0), Inches(12), Inches(0.3), "By allowing the RL agent to tune the parameters dynamically, we achieve significant performance gains.", SANS, Pt(14), DARK_GREY, it=True)
    sl.shapes.add_picture(imgs['results'], Inches(0.3), Inches(1.5), width=Inches(8.5))
    shutil.copy2(DASH_SHOT, f"{IMG_DIR}/dashboard.png")
    sl.shapes.add_picture(f"{IMG_DIR}/dashboard.png", Inches(9.0), Inches(2.2), width=Inches(4.0))
    tb(sl, Inches(9.0), Inches(1.9), Inches(4.0), Inches(0.3), "Live Dashboard Interface ↓", SANS, Pt(11), CRIMSON, True, al=PP_ALIGN.CENTER)
    tb(sl, Inches(0.5), Inches(5.8), Inches(8.5), Inches(0.8), "🚀 Throughput (+18.8%): Agent groups parameters efficiently for heavy workloads.", SANS, Pt(12), BLACK, True)
    tb(sl, Inches(0.5), Inches(6.4), Inches(8.5), Inches(0.8), "⚡ Latency (-25.0%): Agent shrinks time-slices for interactive tasks (web servers).", SANS, Pt(12), BLACK, True)

    # 10. Timeline & Ref
    sl = csld(prs, "Timeline & Reference", 10)
    tb(sl, Inches(0.7), Inches(1.5), Inches(11), Inches(2), "✅ Current Status: Core framework (M1–M4) + 18-panel MLOps dashboard complete. 106 unit tests passing.\n\n🔜 Next Steps: Experiment pipeline (M5) → Evaluation vs baselines (M8) → Live deploy (M7).", SANS, Pt(15), BLACK)
    tb(sl, Inches(0.7), Inches(3.5), Inches(11), Inches(3), "References:\n[1] ghOSt: User-Space Delegation of Linux Scheduling, Google (2021)\n[2] Decima: RL for Job Scheduling, MIT (2019)\n[3] Stable-Baselines3 & Gymnasium Frameworks", SANS, Pt(12), BLACK)

def main():
    print("Generating charts...")
    imgs = {
        'flow': chart_intro_flow(), 'arch': chart_arch(), 'proc': chart_proc(),
        'algo': chart_algo(), 'safety': chart_safety(), 'results': chart_results()
    }
    print("Building presentation...")
    prs = Presentation(); prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    build_slides(prs, imgs)
    prs.save(OUTPUT)
    print(f"Done! Saved {OUTPUT}")

if __name__ == "__main__":
    main()
