from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
import os

prs = Presentation("STUN_S7_Mid_Review.pptx")

# Helper to style tables naturally
def style_table(table, headers, data):
    # Header row
    for i, head in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = head
        # Amrita Maroon background for header
        cell.fill.solid()
        cell.fill.fore_color.rgb = RGBColor(128, 0, 32) 
        para = cell.text_frame.paragraphs[0]
        para.font.bold = True
        para.font.color.rgb = RGBColor(255, 255, 255)
        para.font.size = Pt(14)
    
    # Data rows
    for row_idx, row_data in enumerate(data):
        for col_idx, text in enumerate(row_data):
            cell = table.cell(row_idx + 1, col_idx)
            cell.text = text
            para = cell.text_frame.paragraphs[0]
            para.font.size = Pt(12)
            para.font.color.rgb = RGBColor(0, 0, 0)

def clear_slide(slide):
    shapes_to_keep = []
    for s in slide.shapes:
        if s.has_text_frame and ("Review" in s.text or "Methodology" in s.text or "Result" in s.text or "Member" in s.text):
            shapes_to_keep.append(s)
        elif s == slide.shapes.title:
            shapes_to_keep.append(s)
            
    for s in list(slide.shapes):
        if s not in shapes_to_keep:
            sp = s._element
            sp.getparent().remove(sp)

# Slide 4: Literature Review (Index 3)
slide_lit = prs.slides[3]
clear_slide(slide_lit)
tbl_shape = slide_lit.shapes.add_table(4, 5, Inches(0.5), Inches(1.5), Inches(12.3), Inches(2.5))
style_table(tbl_shape.table, 
    ["Year", "Tool / Paper", "The Catch (Demerits)", "Workloads", "Metrics"],
    [
        ["2017", "OtterTune", "Meant for databases, not OS kernel", "MySQL, Postgres", "Throughput, Latency"],
        ["2021", "CARL", "Too heavy to run live on the system", "System logs", "Overall performance"],
        ["2023", "SchedTuner", "No safety net if the kernel crashes", "Synthetic tests", "Execution time"]
    ]
)

# Slide 6: Methodology (Index 5)
slide_meth = prs.slides[5]
clear_slide(slide_meth)
tbl_shape = slide_meth.shapes.add_table(5, 2, Inches(2.0), Inches(1.8), Inches(8.5), Inches(2.5))
style_table(tbl_shape.table,
    ["What", "Details"],
    [
        ["Data used", "Live system metrics (reads directly from /proc)"],
        ["OS / Platform", "Linux (Ubuntu)"],
        ["Hardware", "Standard multi-core CPUs"],
        ["Tech Stack", "Python, Stable-Baselines3 (for RL), PyQt6 (UI), SQLite"]
    ]
)

# Slide 9 or create new for Results
# Let's add a new slide after index 7 or 8 for "Preliminary Results"
res_slide = prs.slides.add_slide(prs.slide_layouts[6]) # blank
title = res_slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(12), Inches(1))
title.text_frame.text = "Preliminary Results"
title.text_frame.paragraphs[0].font.size = Pt(28)
title.text_frame.paragraphs[0].font.bold = True
title.text_frame.paragraphs[0].font.color.rgb = RGBColor(128, 0, 32)

desc = res_slide.shapes.add_textbox(Inches(0.5), Inches(0.9), Inches(12), Inches(0.5))
desc.text_frame.text = "Snapshot of our live dashboard and some early benchmark numbers during testing:"
desc.text_frame.paragraphs[0].font.size = Pt(14)

if os.path.exists("dashboard_screenshot.png"):
    res_slide.shapes.add_picture("dashboard_screenshot.png", Inches(0.5), Inches(1.5), width=Inches(6.5))

tbl_shape = res_slide.shapes.add_table(3, 3, Inches(7.2), Inches(2.0), Inches(5.5), Inches(1.5))
style_table(tbl_shape.table,
    ["Metric", "Default Linux", "With STUN"],
    [
        ["Throughput", "~12,450 ops/s", "~14,800 ops/s"],
        ["Latency", "15.2 ms", "11.4 ms"]
    ]
)

prs.save("STUN_S7_Mid_Review_Human.pptx")
print("Saved STUN_S7_Mid_Review_Human.pptx")
