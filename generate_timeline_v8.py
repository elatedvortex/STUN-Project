import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
import os

# 1. Generate PNG Diagram using Matplotlib (Clean, human-crafted aesthetic)
fig, ax = plt.subplots(figsize=(13.33, 5.2), facecolor="white")
ax.set_xlim(0, 14)
ax.set_ylim(0, 5)
ax.axis("off")

# Theme colors
CRIMSON = "#9E003E"
ORANGE  = "#D46B08"
GREY    = "#A0A0A0"
DARK    = "#222222"

# Timeline Spine
ax.plot([0.8, 13.2], [2.5, 2.5], color="#D0D0D0", lw=6, zorder=1, solid_capstyle="round")
ax.plot([0.8, 8.8], [2.5, 2.5], color=CRIMSON, lw=6, zorder=2, solid_capstyle="round") # Progress line

milestones = [
    # (x, label, date, title, desc, status)
    (1.2,  "M1", "Jul 2025", "Core Framework", "Registry, Controller\n& Storage Backend", "done"),
    (3.1,  "M2", "Jul 2025", "Safety System", "4-Layer Validator\n& Watchdog Rollback", "done"),
    (5.0,  "M3", "Aug 2025", "RL Environment", "Gymnasium Env,\nPPO & SAC Agents", "done"),
    (6.9,  "M4", "Aug 2025", "MLOps Dashboard", "18-Panel Monitoring\n& Auto-Tuner GUI", "done"),
    (8.8,  "M5", "Sep 2025", "Experimentation", "Parameter Sweeps\n& Workload Adapters", "active"),
    (10.7, "M6", "Oct 2025", "Evaluation", "Comparison vs CFS-RL\n& Default Linux", "future"),
    (12.6, "M7", "Nov 2025", "Final Review", "Production Setup\n& Paper Writing", "future"),
]

for idx, (x, code, date, title, desc, status) in enumerate(milestones):
    if status == "done":
        badge_bg, border_color, text_color = CRIMSON, CRIMSON, "white"
        card_bg = "#FAFAFA"
    elif status == "active":
        badge_bg, border_color, text_color = ORANGE, ORANGE, "white"
        card_bg = "#FFF9F4"
    else:
        badge_bg, border_color, text_color = GREY, GREY, "white"
        card_bg = "#FAFAFA"

    # Node circle on timeline spine
    ax.scatter(x, 2.5, s=450, color=badge_bg, edgecolors="white", linewidth=2.5, zorder=4)
    ax.text(x, 2.5, code, ha="center", va="center", color="white", fontsize=9, fontweight="bold", zorder=5)

    is_top = (idx % 2 == 0)
    card_y = 3.3 if is_top else 0.5
    stem_y_start = 2.75 if is_top else 2.25
    stem_y_end = 3.3 if is_top else 1.7

    # Connector line
    ax.plot([x, x], [stem_y_start, stem_y_end], color=border_color, lw=1.8, linestyle=":", zorder=3)

    # Card background box
    box = mpatches.FancyBboxPatch((x - 0.85, card_y), 1.7, 1.2,
                                  boxstyle="round,pad=0.08",
                                  facecolor=card_bg, edgecolor=border_color,
                                  lw=1.5, zorder=3)
    ax.add_patch(box)

    # Card Text
    ax.text(x, card_y + 0.95, date.upper(), ha="center", va="center", fontsize=7.5, fontweight="bold", color=border_color)
    ax.text(x, card_y + 0.65, title, ha="center", va="center", fontsize=9, fontweight="bold", color=DARK)
    ax.text(x, card_y + 0.30, desc, ha="center", va="center", fontsize=7.5, color="#555555", linespacing=1.2)

# Status Legend
ax.scatter(3.5, 0.15, s=150, color=CRIMSON)
ax.text(3.7, 0.15, "Completed (M1–M4)", va="center", fontsize=9, fontweight="bold", color=DARK)

ax.scatter(6.8, 0.15, s=150, color=ORANGE)
ax.text(7.0, 0.15, "In Progress (M5)", va="center", fontsize=9, fontweight="bold", color=DARK)

ax.scatter(9.8, 0.15, s=150, color=GREY)
ax.text(10.0, 0.15, "Upcoming (M6–M7)", va="center", fontsize=9, fontweight="bold", color=DARK)

img_path = "/home/v0r73x/Documents/final/project/rl-scheduler-framework/project_timeline.png"
fig.tight_layout()
fig.savefig(img_path, dpi=300, bbox_inches="tight")
plt.close(fig)
print(f"Generated PNG: {img_path}")

# 2. Update PPTX Presentation (v8) with this new graphic
with open('generate_ppt_v7.py', 'r') as f:
    code = f.read()

code = code.replace('S7_MidReview_STUN_v7.pptx', 'S7_MidReview_STUN_v8.pptx')

# Replace slide 10 function
new_slide_10 = """
def slide_timeline(prs):
    sl = csld(prs, "Project Roadmap & Timeline", 10)
    tb(sl, Inches(0.5), Inches(0.9), Inches(12), Inches(0.3), "Phased milestone progression from core architecture to benchmark validation and deployment.", SANS, Pt(13), DARK_GREY, it=True)
    sl.shapes.add_picture('/home/v0r73x/Documents/final/project/rl-scheduler-framework/project_timeline.png', Inches(0.3), Inches(1.4), width=Inches(12.73))
"""

import re
code = re.sub(r'def slide_timeline.*?def main', new_slide_10 + '\ndef main', code, flags=re.DOTALL)
code = code.replace('slide_timeline(prs)', 'slide_timeline(prs)')

with open('generate_ppt_v8.py', 'w') as f:
    f.write(code)

os.system('python3 generate_ppt_v8.py')
print("Generated updated PPTX v8!")
