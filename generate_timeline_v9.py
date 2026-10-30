import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import shutil
import os

# 1. Generate PNG Diagram using Matplotlib (Without Dates)
fig, ax = plt.subplots(figsize=(13.33, 4.8), facecolor="white")
ax.set_xlim(0, 14)
ax.set_ylim(0, 4.6)
ax.axis("off")

# Theme colors
CRIMSON = "#9E003E"
ORANGE  = "#D46B08"
GREY    = "#A0A0A0"
DARK    = "#222222"

# Timeline Spine
ax.plot([0.8, 13.2], [2.3, 2.3], color="#E0E0E0", lw=6, zorder=1, solid_capstyle="round")
ax.plot([0.8, 8.8], [2.3, 2.3], color=CRIMSON, lw=6, zorder=2, solid_capstyle="round") # Progress line

milestones = [
    # (x, code, title, desc, status)
    (1.2,  "M1", "Core Framework", "Registry, Controller\n& Storage Backend", "done"),
    (3.1,  "M2", "Safety System", "4-Layer Validator\n& Watchdog Rollback", "done"),
    (5.0,  "M3", "RL Environment", "Gymnasium Env,\nPPO & SAC Agents", "done"),
    (6.9,  "M4", "MLOps Dashboard", "18-Panel Monitoring\n& Auto-Tuner GUI", "done"),
    (8.8,  "M5", "Experimentation", "Parameter Sweeps\n& Workload Adapters", "active"),
    (10.7, "M6", "Evaluation", "Comparison vs CFS-RL\n& Default Linux", "future"),
    (12.6, "M7", "Final Review", "Production Setup\n& Paper Writing", "future"),
]

for idx, (x, code, title, desc, status) in enumerate(milestones):
    if status == "done":
        badge_bg, border_color = CRIMSON, CRIMSON
        card_bg = "#FAFAFA"
    elif status == "active":
        badge_bg, border_color = ORANGE, ORANGE
        card_bg = "#FFF9F4"
    else:
        badge_bg, border_color = GREY, GREY
        card_bg = "#FAFAFA"

    # Node circle on timeline spine
    ax.scatter(x, 2.3, s=450, color=badge_bg, edgecolors="white", linewidth=2.5, zorder=4)
    ax.text(x, 2.3, code, ha="center", va="center", color="white", fontsize=9, fontweight="bold", zorder=5)

    is_top = (idx % 2 == 0)
    card_y = 3.0 if is_top else 0.5
    stem_y_start = 2.55 if is_top else 2.05
    stem_y_end = 3.0 if is_top else 1.65

    # Connector line
    ax.plot([x, x], [stem_y_start, stem_y_end], color=border_color, lw=1.8, linestyle=":", zorder=3)

    # Card background box
    box = mpatches.FancyBboxPatch((x - 0.85, card_y), 1.7, 1.15,
                                  boxstyle="round,pad=0.08",
                                  facecolor=card_bg, edgecolor=border_color,
                                  lw=1.5, zorder=3)
    ax.add_patch(box)

    # Card Text (Centered vertically since date is removed)
    ax.text(x, card_y + 0.80, title, ha="center", va="center", fontsize=9.5, fontweight="bold", color=DARK)
    ax.text(x, card_y + 0.38, desc, ha="center", va="center", fontsize=7.8, color="#555555", linespacing=1.25)

# Status Legend
ax.scatter(3.5, 0.1, s=140, color=CRIMSON)
ax.text(3.7, 0.1, "Completed (M1–M4)", va="center", fontsize=9, fontweight="bold", color=DARK)

ax.scatter(6.8, 0.1, s=140, color=ORANGE)
ax.text(7.0, 0.1, "In Progress (M5)", va="center", fontsize=9, fontweight="bold", color=DARK)

ax.scatter(9.8, 0.1, s=140, color=GREY)
ax.text(10.0, 0.1, "Upcoming (M6–M7)", va="center", fontsize=9, fontweight="bold", color=DARK)

img_path = "/home/v0r73x/Documents/final/project/rl-scheduler-framework/project_timeline.png"
fig.tight_layout()
fig.savefig(img_path, dpi=300, bbox_inches="tight")
plt.close(fig)
print(f"Generated PNG without dates: {img_path}")

# Copy to artifact folder for preview
artifact_path = "/home/v0r73x/.gemini/antigravity/brain/3f92f86b-5d20-4187-a32c-99ab4a6a4ecb/project_timeline.png"
shutil.copy2(img_path, artifact_path)

# Regenerate PPT v8 with new timeline image
os.system('python3 generate_ppt_v8.py')
print("Updated PPTX v8 with dateless timeline!")
