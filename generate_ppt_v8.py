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
IMG_DIR   = os.path.join(BASE, "ppt_assets_v7")
OUTPUT    = os.path.join(BASE, "S7_MidReview_STUN_v8.pptx")
os.makedirs(IMG_DIR, exist_ok=True)

# Constants & Colors
SLIDE_W, SLIDE_H, FOOTER_H = Inches(13.333), Inches(7.5), Inches(0.48)
CRIMSON, WHITE, BLACK = RGBColor(0x9E, 0x00, 0x3E), RGBColor(0xFF, 0xFF, 0xFF), RGBColor(0x00, 0x00, 0x00)
YELLOW, CARD_BG = RGBColor(0xFF, 0xD7, 0x00), RGBColor(0xFA, 0xF0, 0xF4)
DARK_GREY, SOFT_GREY = RGBColor(0x55, 0x55, 0x55), RGBColor(0x99, 0x99, 0x99)
SANS, SERIF = "Arial", "Georgia"
MC, MB, MG, MO, MP, MD, MGR = "#9E003E", "#2E86AB", "#1B7A3D", "#D46B08", "#564D80", "#333333", "#888888"

# ─── CHART GENERATORS (Simplified for other slides to focus on Results) ───
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
    p = f"{IMG_DIR}/intro_flow.png"; fig.savefig(p, dpi=200, bbox_inches="tight"); plt.close(fig); return p

def chart_arch():
    fig, ax = plt.subplots(figsize=(13, 5.5), facecolor="white")
    ax.set_xlim(-0.3, 13.3); ax.set_ylim(-0.3, 5.8); ax.axis("off")
    stages = [(0.1, 3.3, "1. MONITOR", "Read /proc", MB), (2.3, 3.3, "2. STATE", "Normalize", MP), (4.5, 3.3, "3. POLICY", "PPO network", MC), (6.7, 3.3, "4. DECODE", "Action to params", MO), (8.9, 3.3, "5. WRITE", "Validate/Write", MG), (4.5, 0.2, "6. BENCHMARK", "Run workloads", "#863B00")]
    for x, y, title, body, col in stages:
        ax.add_patch(FancyBboxPatch((x,y), 2.0, 2.2, boxstyle="round,pad=0.1", facecolor=col, alpha=0.92, edgecolor="white", lw=2))
        ax.text(x+1.0, y+1.82, title, ha="center", va="center", fontsize=10.5, fontweight="bold", color="white")
    ax.add_patch(FancyBboxPatch((7.4, 0.3), 3.0, 1.8, boxstyle="round,pad=0.12", facecolor=MD, edgecolor=MC, lw=3, alpha=0.95))
    ax.text(8.9, 1.4, "LINUX KERNEL", ha="center", va="center", fontsize=12, fontweight="bold", color="white")
    for sx in [2.1, 4.3, 6.5, 8.7]:
        ax.annotate("", xy=(sx+0.18, 4.4), xytext=(sx, 4.4), arrowprops=dict(arrowstyle="->,head_width=0.2", color=MC, lw=2.5))
    ax.annotate("", xy=(9.9, 2.15), xytext=(9.9, 3.25), arrowprops=dict(arrowstyle="->,head_width=0.2", color=MC, lw=2.5))
    ax.annotate("", xy=(6.55, 1.2), xytext=(7.35, 1.2), arrowprops=dict(arrowstyle="->,head_width=0.2", color=MC, lw=2.5))
    ax.annotate("", xy=(0.6, 3.25), xytext=(4.5, 1.4), arrowprops=dict(arrowstyle="->,head_width=0.25", color=MC, lw=2.5, connectionstyle="arc3,rad=0.4", linestyle="--"))
    p = f"{IMG_DIR}/architecture.png"; fig.savefig(p, dpi=200, bbox_inches="tight"); plt.close(fig); return p

def chart_proc():
    fig, ax = plt.subplots(figsize=(12, 4.5), facecolor="white")
    ax.set_xlim(0, 12); ax.set_ylim(0, 5); ax.axis("off")
    ax.add_patch(FancyBboxPatch((4.5, 1.5), 3.0, 2.0, boxstyle="round,pad=0.15", facecolor=MD, edgecolor=MC, lw=3, alpha=0.95))
    ax.text(6.0, 2.8, "LINUX KERNEL", ha="center", va="center", fontsize=14, fontweight="bold", color="white")
    ax.add_patch(FancyBboxPatch((0.5, 1.3), 2.5, 2.4, boxstyle="round,pad=0.1", facecolor=MB, alpha=0.9, edgecolor="white", lw=2))
    ax.text(1.75, 3.4, "MONITOR (Read)", ha="center", va="center", fontsize=12, fontweight="bold", color="white")
    ax.add_patch(FancyBboxPatch((9.0, 1.3), 2.5, 2.4, boxstyle="round,pad=0.1", facecolor=MO, alpha=0.9, edgecolor="white", lw=2))
    ax.text(10.25, 3.4, "CONTROLLER (Write)", ha="center", va="center", fontsize=12, fontweight="bold", color="white")
    ax.annotate("", xy=(0.5, 2.5), xytext=(4.5, 2.5), arrowprops=dict(arrowstyle="->,head_width=0.3", color=MB, lw=3))
    ax.annotate("", xy=(9.0, 2.5), xytext=(7.5, 2.5), arrowprops=dict(arrowstyle="<-,head_width=0.3", color=MO, lw=3))
    p = f"{IMG_DIR}/proc_visual.png"; fig.savefig(p, dpi=200, bbox_inches="tight"); plt.close(fig); return p

def chart_algo():
    fig = plt.figure(figsize=(13, 4.5), facecolor="white")
    ax1 = fig.add_subplot(111)
    ax1.set_xlim(0,7); ax1.set_ylim(0,5); ax1.axis("off")
    ax1.set_title("PPO Algorithm Training Loop", fontsize=12, fontweight="bold", color=MC, pad=10)
    steps = [(0.2, 3.8, "Observe", MB), (1.9, 3.8, "Act", MC), (3.6, 3.8, "Apply", MG), (5.3, 3.8, "Measure", MO), (2.7, 1.4, "Learn", MP)]
    for x, y, t, c in steps:
        ax1.add_patch(FancyBboxPatch((x,y), 1.4, 1.0, boxstyle="round,pad=0.08", facecolor=c, alpha=0.9, edgecolor="white", lw=1.5))
        ax1.text(x+0.7, y+0.5, t, ha="center", va="center", fontsize=10, fontweight="bold", color="white")
    for sx in [1.6, 3.3, 5.0]:
        ax1.annotate("", xy=(sx+0.28, 4.3), xytext=(sx, 4.3), arrowprops=dict(arrowstyle="->", color=MC, lw=2))
    ax1.annotate("", xy=(4.8, 2.4), xytext=(6.0, 3.75), arrowprops=dict(arrowstyle="->", color=MC, lw=2, connectionstyle="arc3,rad=-0.3"))
    ax1.annotate("", xy=(0.6, 3.75), xytext=(2.7, 1.95), arrowprops=dict(arrowstyle="->", color=MC, lw=2, connectionstyle="arc3,rad=-0.3", ls="--"))
    p = f"{IMG_DIR}/algo_visual.png"; fig.savefig(p, dpi=200, bbox_inches="tight"); plt.close(fig); return p

def chart_safety():
    fig, ax = plt.subplots(figsize=(12, 3.5), facecolor="white")
    ax.set_xlim(0, 12.5); ax.set_ylim(0, 3.8); ax.axis("off")
    blocks = [(0.1, 1.7, "1. Primary Validator", MB), (3.1, 1.7, "2. Secondary Validator", MP), (6.1, 1.7, "3. Write & Readback", MG), (9.1, 1.7, "4. Watchdog & Rollback", MO)]
    for x, y, label, col in blocks:
        ax.add_patch(FancyBboxPatch((x,y), 2.8, 1.4, boxstyle="round,pad=0.1", facecolor=col, alpha=0.9, edgecolor="white", lw=2))
        ax.text(x+1.4, y+0.7, label, ha="center", va="center", fontsize=10.5, fontweight="bold", color="white", linespacing=1.4)
    for sx in [2.9, 5.9, 8.9]:
        ax.annotate("", xy=(sx+0.2, 2.4), xytext=(sx, 2.4), arrowprops=dict(arrowstyle="->", color=MC, lw=3))
    p = f"{IMG_DIR}/safety_pipeline.png"; fig.savefig(p, dpi=200, bbox_inches="tight"); plt.close(fig); return p

# ─── NEW RESULTS COMPARISON CHART ───
def chart_results_comparison():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.0), facecolor="white")
    
    labels = ['Default Linux', 'Prior Work\n(CFS-RL)', 'STUN\n(Ours)']
    colors_t = ["#888888", "#564D80", "#9E003E"]
    colors_l = ["#888888", "#564D80", "#2E86AB"]
    
    fig.suptitle("ILLUSTRATIVE DATA — NOT MEASURED RESULTS", color="darkred", fontweight="bold")
    throughput = [12450, 13500, 14800]
    bars1 = ax1.bar(labels, throughput, color=colors_t, width=0.5, edgecolor='white', lw=2)
    ax1.set_title("Visual: Throughput (Operations/sec) ▲", fontsize=13, fontweight='bold', color='#333', pad=15)
    ax1.set_ylim(0, 17500); ax1.spines["top"].set_visible(False); ax1.spines["right"].set_visible(False); ax1.grid(axis='y', alpha=0.15)
    
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, yval + 300, f"{int(yval):,} ops/s", ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    latency = [15.2, 13.5, 11.4]
    bars2 = ax2.bar(labels, latency, color=colors_l, width=0.5, edgecolor='white', lw=2)
    ax2.set_title("Visual: Response Latency (ms) ▼", fontsize=13, fontweight='bold', color='#333', pad=15)
    ax2.set_ylim(0, 19); ax2.spines["top"].set_visible(False); ax2.spines["right"].set_visible(False); ax2.grid(axis='y', alpha=0.15)
    
    for bar in bars2:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, yval + 0.3, f"{yval} ms", ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    fig.tight_layout(pad=1.5)
    p = f"{IMG_DIR}/results_comparison.png"; fig.savefig(p, dpi=300, bbox_inches="tight"); plt.close(fig); return p

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
    sl = prs.slides.add_slide(prs.slide_layouts[6]); set_bg(sl, WHITE)
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
            p.font.name = SANS; p.font.size = Pt(13) if ri==0 else Pt(11)
            p.font.color.rgb = WHITE if ri==0 else BLACK; p.font.bold = (ri == 0 or ci == 0)
            if ri == 0: cell.fill.solid(); cell.fill.fore_color.rgb = CRIMSON

# ─── SLIDES ───
def build_slides(prs, imgs):
    # 1. Title
    sl = prs.slides.add_slide(prs.slide_layouts[6]); set_bg(sl, CRIMSON)
    tb(sl, Inches(0.8), Inches(1.8), Inches(11), Inches(2.5), "STUN: Adaptive Reinforcement\nLearning for Linux Scheduler\nOptimisation", SERIF, Pt(40), WHITE, True)
    
    # 2. Outline
    sl = csld(prs, "Outline", 2)
    items = ["01. Introduction", "02. Architecture: How everything works", "03. The Window to the Kernel: /proc", "04. The Knobs: 8 Tunable Parameters", "05. The Algorithm (PPO) & Hyperparameters", "06. The Shield: 4-Layer Safety System", "07. Result Analysis (Comparison with Existing Works)", "08. Project Timeline & Reference"]
    _,tf = tb(sl, Inches(1.0), Inches(1.5), Inches(11), Inches(5), "", SANS, Pt(18))
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i==0 else tf.add_paragraph()
        p.text = item; p.font.size = Pt(18); p.space_before = Pt(12)

    # 3. Intro
    sl = csld(prs, "Introduction", 3)
    sl.shapes.add_picture(imgs['flow'], Inches(1.0), Inches(3.8), width=Inches(11.0))

    # 4. Architecture
    sl = csld(prs, "Architecture: How Everything Works", 4)
    sl.shapes.add_picture(imgs['arch'], Inches(0.0), Inches(1.35), width=Inches(13.3))

    # 5. /proc
    sl = csld(prs, "The Window to the Kernel: /proc", 5)
    sl.shapes.add_picture(imgs['proc'], Inches(0.6), Inches(1.5), width=Inches(12.0))

    # 6. Parameters
    sl = csld(prs, "The Knobs: 8 Tunable Parameters", 6)
    data = [["Parameter Name", "Description", "Type/Range"], ["sched_rr_timeslice_ms", "Round-Robin task run time before yielding", "1–2000 ms"], ["sched_rt_period_us", "Time period for real-time task CPU bandwidth", "1–1M µs"], ["sched_cfs_bandwidth_slice_us", "Size of time slices for standard CFS tasks", "1–100k µs"]]
    tbl(sl, data, Inches(0.5), Inches(1.5), Inches(12.3), Inches(2.0))

    # 7. Algorithm
    sl = csld(prs, "The Algorithm: PPO Training Loop", 7)
    sl.shapes.add_picture(imgs['algo'], Inches(0.0), Inches(1.35), width=Inches(13.3))

    # 8. Safety
    sl = csld(prs, "The Shield: 4-Layer Safety System", 8)
    sl.shapes.add_picture(imgs['safety'], Inches(0.5), Inches(1.6), width=Inches(12.3))

    # 9. Results (NEW: COMPARISON + TABLE)
    sl = csld(prs, "Illustrative Comparison (Unverified Data)", 9)
    tb(sl, Inches(0.5), Inches(0.9), Inches(12.5), Inches(0.3), "Illustrative values only; no measured comparison or prior-work reproduction is established.", SANS, Pt(13), DARK_GREY, it=True)
    
    # Visual Chart
    sl.shapes.add_picture(imgs['results_comp'], Inches(0.4), Inches(1.3), width=Inches(12.5))
    
    # Quantitative Table
    table_data = [
        ["Quantitative Metric", "Default Linux", "CFS-RL (Prior Work)", "STUN (Ours)"],
        ["Throughput (ops/s) ▲", "12,450", "13,500 (+8.4%)", "14,800 (+18.8%)"],
        ["Response Latency (ms) ▼", "15.2", "13.5 (-11.1%)", "11.4 (-25.0%)"],
        ["Parameters Tuned", "Static (0)", "1", "8 (Simultaneous)"],
        ["Safety Architecture", "N/A", "None", "4-Layer Rollback"],
    ]
    tbl(sl, table_data, Inches(0.4), Inches(4.5), Inches(12.5), Inches(2.2))

    # 10. Timeline
    sl = csld(prs, "Timeline & Reference", 10)
    tb(sl, Inches(0.7), Inches(1.5), Inches(11), Inches(2), "✅ Current Status: Core framework (M1–M4) + 18-panel MLOps dashboard complete. 106 unit tests passing.\n\n🔜 Next Steps: Experiment pipeline (M5) → Evaluation vs baselines (M8) → Live deploy (M7).", SANS, Pt(15), BLACK)

def main():
    print("Generating charts...")
    imgs = {
        'flow': chart_intro_flow(), 'arch': chart_arch(), 'proc': chart_proc(),
        'algo': chart_algo(), 'safety': chart_safety(), 'results_comp': chart_results_comparison()
    }
    print("Building presentation...")
    prs = Presentation(); prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    build_slides(prs, imgs)
    prs.save(OUTPUT)
    print(f"Done! Saved {OUTPUT}")

if __name__ == "__main__":
    main()
