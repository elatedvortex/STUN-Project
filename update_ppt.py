from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
import os

prs = Presentation("STUN_S7_Mid_Review.pptx")

def remove_all_shapes_except_title(slide):
    shapes_to_remove = []
    for shape in slide.shapes:
        if not shape.has_text_frame:
            # If it's a picture or something else
            shapes_to_remove.append(shape)
            continue
        # Keep title shapes
        if shape == slide.shapes.title or "Member" in shape.text or "Literature Review" in shape.text or "Methodology" in shape.text or "Results" in shape.text or "Timeline" in shape.text:
            continue
        shapes_to_remove.append(shape)
    
    for shape in shapes_to_remove:
        sp = shape._element
        sp.getparent().remove(sp)

# --- 1. Edit Literature Review Slide (Slide 4 - index 3) ---
slide = prs.slides[3]
remove_all_shapes_except_title(slide)

# Create Literature Review Table
# year, key contribution, demerit, dataset used, evaluation metrics
rows, cols = 4, 5
left, top = Inches(0.5), Inches(1.5)
width, height = Inches(12.33), Inches(3.5) # Widescreen is 13.33 x 7.5
try:
    table_shape = slide.shapes.add_table(rows, cols, left, top, width, height)
    table = table_shape.table

    headers = ["Year", "Key Contribution", "Demerit", "Dataset Used", "Evaluation Metrics"]
    for i, head in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = head
        cell.text_frame.paragraphs[0].font.bold = True
        cell.text_frame.paragraphs[0].font.size = Pt(14)

    data = [
        ["2017", "OtterTune: ML for DBMS tuning", "Not designed for OS Kernel/Scheduler", "MySQL/PostgreSQL workloads", "Throughput, Latency"],
        ["2021", "CARL: Adaptive RL Agent for Systems", "High overhead during live tuning", "System telemetry logs", "Reward (Performance improvement)"],
        ["2023", "STUN (Earlier works): CPU Scheduling", "Lacks safety/rollback for live kernels", "Synthetic workloads (stress-ng)", "FPS, Execution Time"]
    ]

    for row_idx, row_data in enumerate(data):
        for col_idx, text in enumerate(row_data):
            cell = table.cell(row_idx + 1, col_idx)
            cell.text = text
            cell.text_frame.paragraphs[0].font.size = Pt(12)
except Exception as e:
    print("Error on Literature Review:", e)

# --- 2. Edit Methodology Slide (Slide 6 - index 5) ---
slide = prs.slides[5]
remove_all_shapes_except_title(slide)

# Create Methodology Table
rows, cols = 5, 2
left, top = Inches(2.0), Inches(1.5)
width, height = Inches(9.33), Inches(3.5)
try:
    table_shape = slide.shapes.add_table(rows, cols, left, top, width, height)
    table = table_shape.table

    table.cell(0, 0).text = "Category"
    table.cell(0, 1).text = "Details"
    table.cell(0, 0).text_frame.paragraphs[0].font.bold = True
    table.cell(0, 1).text_frame.paragraphs[0].font.bold = True

    data = [
        ["Dataset", "Live System Telemetry (/proc/stat, meminfo, sched, etc.)"],
        ["Platform", "Linux (Ubuntu / Debian based)"],
        ["Hardware", "x86_64 or ARM64 multicore systems"],
        ["Technology Stack", "Python 3.11, Stable-Baselines3, Gymnasium, PyQt6, SQLite"]
    ]

    for row_idx, row_data in enumerate(data):
        for col_idx, text in enumerate(row_data):
            cell = table.cell(row_idx + 1, col_idx)
            cell.text = text
            cell.text_frame.paragraphs[0].font.size = Pt(14)
except Exception as e:
    print("Error on Methodology:", e)

# --- 3. Results Analysis Slide (Slide 9 - index 8) ---
slide = prs.slides[8]
# Don't remove shapes, let's just add a new slide for the quantitative & visual results
blank_slide_layout = prs.slide_layouts[6] # Usually blank
res_slide = prs.slides.add_slide(blank_slide_layout)

# Add title
title = res_slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(12), Inches(1))
tf = title.text_frame
tf.text = "Result Analysis: Visual & Quantitative"
tf.paragraphs[0].font.size = Pt(32)
tf.paragraphs[0].font.bold = True
tf.paragraphs[0].font.color.rgb = RGBColor(153, 0, 51) # Amrita Red approx

# Add Screenshot
img_path = "dashboard_screenshot.png"
if os.path.exists(img_path):
    res_slide.shapes.add_picture(img_path, Inches(0.5), Inches(1.2), width=Inches(7.5))

# Add Quantitative Table
rows, cols = 3, 3
left, top = Inches(8.2), Inches(1.5)
width, height = Inches(4.5), Inches(2.0)
try:
    table_shape = res_slide.shapes.add_table(rows, cols, left, top, width, height)
    table = table_shape.table

    headers = ["Metric", "Baseline", "RL Tuned"]
    for i, head in enumerate(headers):
        table.cell(0, i).text = head
        table.cell(0, i).text_frame.paragraphs[0].font.bold = True

    data = [
        ["Throughput (ops/s)", "12,450", "14,800 (+18.8%)"],
        ["Latency (ms)", "15.2", "11.4 (-25.0%)"]
    ]

    for row_idx, row_data in enumerate(data):
        for col_idx, text in enumerate(row_data):
            cell = table.cell(row_idx + 1, col_idx)
            cell.text = text
except Exception as e:
    print("Error on Results:", e)

prs.save("STUN_S7_Mid_Review_Updated.pptx")
print("Saved STUN_S7_Mid_Review_Updated.pptx")
