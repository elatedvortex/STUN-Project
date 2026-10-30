import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os
import shutil
import re

BASE      = "/home/v0r73x/Documents/final/project/rl-scheduler-framework"
IMG_DIR   = os.path.join(BASE, "ppt_assets_v9")
OUTPUT    = os.path.join(BASE, "S7_MidReview_STUN_v9.pptx")
os.makedirs(IMG_DIR, exist_ok=True)

# 1. Generate Workload-Specific Breakdown Chart
fig, ax = plt.subplots(figsize=(12, 3.8), facecolor="white")

workloads = ['CPU Heavy\n(stress-ng)', 'Interactive\n(cyclictest)', 'Mixed Load\n(hackbench)', 'Memory / IO\n(sysbench/fio)']
baseline  = [100.0, 100.0, 100.0, 100.0]
prior_work = [108.4, 111.1, 106.5, 107.2]  # CFS-RL % normalized
stun_ours  = [118.8, 125.0, 118.9, 121.4]  # STUN % normalized

x = np.arange(len(workloads))
width = 0.25

rects1 = ax.bar(x - width, baseline, width, label='Default Linux (100%)', color='#888888', edgecolor='white', lw=1.5)
rects2 = ax.bar(x, prior_work, width, label='CFS-RL (Prior Work)', color='#564D80', edgecolor='white', lw=1.5)
rects3 = ax.bar(x + width, stun_ours, width, label='STUN (Ours)', color='#9E003E', edgecolor='white', lw=1.5)

ax.set_ylabel('Normalized Performance (%)', fontsize=11, fontweight='bold', color='#333333')
ax.set_title('ILLUSTRATIVE DATA — Not Measured Workload Gains', fontsize=13, fontweight='bold', color='#333333', pad=15)
ax.set_xticks(x)
ax.set_xticklabels(workloads, fontsize=10, fontweight='bold', color='#333333')
ax.set_ylim(80, 135)
ax.axhline(100, color='#666666', linestyle='--', linewidth=1.2, alpha=0.7)
ax.legend(loc='upper left', frameon=True, facecolor='white', edgecolor='#cccccc', fontsize=9)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.grid(axis='y', alpha=0.15)

# Value annotations
for bar in rects3:
    yval = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, yval + 1.2, f"+{yval-100:.1f}%", ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#9E003E')

fig.tight_layout()
wl_img_path = f"{IMG_DIR}/workload_breakdown.png"
fig.savefig(wl_img_path, dpi=300, bbox_inches="tight")
plt.close(fig)
print(f"Generated workload chart: {wl_img_path}")

# 2. Build full presentation PPT v9 with expanded 2-slide Results
with open('generate_ppt_v7.py', 'r') as f:
    code = f.read()

# Replace output file name
code = code.replace('S7_MidReview_STUN_v7.pptx', 'S7_MidReview_STUN_v9.pptx')
code = code.replace('ppt_assets_v7', 'ppt_assets_v9')

# Update Outline to include 11 slides
old_outline_items = 'items = ["01. Introduction", "02. Architecture: How everything works", "03. The Window to the Kernel: /proc", "04. The Knobs: 8 Tunable Parameters", "05. The Algorithm (PPO) & Hyperparameters", "06. The Shield: 4-Layer Safety System", "07. Result Analysis (Comparison with Existing Works)", "08. Project Timeline & Reference"]'
new_outline_items = 'items = ["01. Introduction", "02. Architecture: How everything works", "03. The Window to the Kernel: /proc", "04. The Knobs: 8 Tunable Parameters", "05. The Algorithm (PPO) & Hyperparameters", "06. The Shield: 4-Layer Safety System", "07. Result Analysis: Baseline & Prior Work", "08. Evaluation Plan: Measurements Pending", "09. Project Roadmap & Timeline"]'
code = code.replace(old_outline_items, new_outline_items)

# Add slide 9 and slide 10 (expanded results) and slide 11 (timeline)
new_slides_code = """
    # 9. Results Part 1: Comparison with Existing Works
    sl = csld(prs, "Illustrative Comparison (Unverified Data)", 9)
    tb(sl, Inches(0.5), Inches(0.9), Inches(12.5), Inches(0.3), "Illustrative values only; no measured comparison or prior-work reproduction is established.", SANS, Pt(13), DARK_GREY, it=True)
    sl.shapes.add_picture(imgs['results_comp'], Inches(0.4), Inches(1.3), width=Inches(12.5))
    
    table_data = [
        ["Quantitative Metric", "Default Linux", "CFS-RL (Prior Work)", "STUN (Ours)"],
        ["Throughput (ops/s) ▲", "12,450", "13,500 (+8.4%)", "14,800 (+18.8%)"],
        ["Response Latency (ms) ▼", "15.2", "13.5 (-11.1%)", "11.4 (-25.0%)"],
        ["Parameters Tuned", "Static (0)", "1", "8 (Simultaneous)"],
        ["Safety Architecture", "N/A", "None", "4-Layer Rollback"],
    ]
    tbl(sl, table_data, Inches(0.4), Inches(4.5), Inches(12.5), Inches(2.2))

    # 10. Results Part 2: Workload Breakdown & System Efficiency (NEW)
    sl = csld(prs, "Evaluation Plan: Measurements Pending", 10)
    tb(sl, Inches(0.5), Inches(0.9), Inches(12.5), Inches(0.3), "Measurements pending. These targets do not establish performance or production safety.", SANS, Pt(13), DARK_GREY, it=True)
    sl.shapes.add_picture(f"{IMG_DIR}/workload_breakdown.png", Inches(0.4), Inches(1.3), width=Inches(12.5))
    
    efficiency_data = [
        ["System Overhead / Stability Metric", "Measured Value", "Target Threshold", "Status"],
        ["Agent Inference Latency", "Not measured", "< 1.0 ms", "Pending validation"],
        ["Telemetry CPU Overhead", "Not measured", "< 2.0% CPU", "Pending validation"],
        ["Memory Footprint", "Not measured", "< 100 MB RAM", "Pending validation"],
        ["Watchdog Recovery Time", "Not measured", "< 10.0 ms", "Pending validation"],
        ["Kernel Stability Record", "Not measured", "0 Panics", "Pending validation"],
    ]
    tbl(sl, efficiency_data, Inches(0.4), Inches(4.5), Inches(12.5), Inches(2.2))

    # 11. Timeline (Dateless timeline image)
    sl = csld(prs, "Project Roadmap & Timeline", 11)
    tb(sl, Inches(0.5), Inches(0.9), Inches(12), Inches(0.3), "Phased milestone progression from core architecture to benchmark validation and deployment.", SANS, Pt(13), DARK_GREY, it=True)
    sl.shapes.add_picture('/home/v0r73x/Documents/final/project/rl-scheduler-framework/project_timeline.png', Inches(0.3), Inches(1.4), width=Inches(12.73))
"""

code = re.sub(r'# 9. Results.*def main', new_slides_code + '\ndef main', code, flags=re.DOTALL)

with open('generate_ppt_v9.py', 'w') as f:
    f.write(code)

os.system('python3 generate_ppt_v9.py')
print("Generated updated PPTX v9 successfully!")
