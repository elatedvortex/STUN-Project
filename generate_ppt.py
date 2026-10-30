#!/usr/bin/env python3
"""
Generate the S7 Project Mid-Review PowerPoint presentation for
STUN: Adaptive Reinforcement Learning for Linux Scheduler Optimisation.
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE

# ── Constants ──────────────────────────────────────────────────────────
SLIDE_W = Inches(13.333)  # 16:9 widescreen
SLIDE_H = Inches(7.5)

CRIMSON = RGBColor(0x9E, 0x00, 0x3E)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
BLACK   = RGBColor(0x00, 0x00, 0x00)
YELLOW  = RGBColor(0xFF, 0xD7, 0x00)
GREEN   = RGBColor(0x00, 0x80, 0x00)
LIGHT_GREY = RGBColor(0xF0, 0xF0, 0xF0)

SANS_FONT  = "Arial"
SERIF_FONT = "Georgia"
MONO_FONT  = "Consolas"

FOOTER_H = Inches(0.55)


# ── Helper functions ──────────────────────────────────────────────────

def set_slide_bg(slide, color):
    """Set the background color of a slide."""
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_textbox(slide, left, top, width, height, text="",
                font_name=SANS_FONT, font_size=Pt(14), font_color=BLACK,
                bold=False, italic=False, alignment=PP_ALIGN.LEFT,
                word_wrap=True):
    """Add a simple text box and return the (textbox, text_frame) pair."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = word_wrap
    p = tf.paragraphs[0]
    p.text = text
    p.font.name = font_name
    p.font.size = font_size
    p.font.color.rgb = font_color
    p.font.bold = bold
    p.font.italic = italic
    p.alignment = alignment
    return txBox, tf


def add_paragraph(tf, text, font_name=SANS_FONT, font_size=Pt(14),
                  font_color=BLACK, bold=False, space_before=Pt(6),
                  space_after=Pt(4), alignment=PP_ALIGN.LEFT, level=0):
    """Append a new paragraph to a text frame."""
    p = tf.add_paragraph()
    p.text = text
    p.font.name = font_name
    p.font.size = font_size
    p.font.color.rgb = font_color
    p.font.bold = bold
    p.space_before = space_before
    p.space_after = space_after
    p.alignment = alignment
    p.level = level
    return p


def add_run(paragraph, text, font_name=SANS_FONT, font_size=Pt(14),
            font_color=BLACK, bold=False, italic=False):
    """Add a run to an existing paragraph."""
    run = paragraph.add_run()
    run.text = text
    run.font.name = font_name
    run.font.size = font_size
    run.font.color.rgb = font_color
    run.font.bold = bold
    run.font.italic = italic
    return run


def add_bullet(tf, text, font_name=SANS_FONT, font_size=Pt(16),
               font_color=BLACK, bold=False, level=0):
    """Add a bullet-point paragraph."""
    p = tf.add_paragraph()
    p.text = text
    p.font.name = font_name
    p.font.size = font_size
    p.font.color.rgb = font_color
    p.font.bold = bold
    p.level = level
    p.space_before = Pt(6)
    p.space_after = Pt(4)
    return p


def add_content_footer(slide, slide_num):
    """Add the thick crimson footer band with slide number and logo text."""
    footer_top = SLIDE_H - FOOTER_H
    # Thick crimson band
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), footer_top, SLIDE_W, FOOTER_H
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = CRIMSON
    shape.line.fill.background()

    # Slide number (bottom left)
    add_textbox(slide, Inches(0.4), footer_top + Pt(4),
                Inches(1), FOOTER_H - Pt(8),
                text=str(slide_num),
                font_name=SANS_FONT, font_size=Pt(12),
                font_color=WHITE, bold=True,
                alignment=PP_ALIGN.LEFT)

    # Logo placeholder text (bottom right)
    add_textbox(slide, SLIDE_W - Inches(4), footer_top + Pt(4),
                Inches(3.7), FOOTER_H - Pt(8),
                text="Amrita Vishwa Vidyapeetham",
                font_name=SANS_FONT, font_size=Pt(11),
                font_color=WHITE, bold=False,
                alignment=PP_ALIGN.RIGHT)


def add_content_slide_title(slide, title_text):
    """Add the serif, crimson slide title at the top-left."""
    add_textbox(slide, Inches(0.6), Inches(0.3), Inches(12), Inches(0.7),
                text=title_text,
                font_name=SERIF_FONT, font_size=Pt(30),
                font_color=CRIMSON, bold=True)


def new_content_slide(prs, title_text, slide_num):
    """Create a new blank content slide with white bg, title, and footer."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout
    set_slide_bg(slide, WHITE)
    add_content_slide_title(slide, title_text)
    add_content_footer(slide, slide_num)
    return slide


def add_table(slide, rows, cols, data, left, top, width, height,
              header_bg=CRIMSON, header_font_color=WHITE,
              body_font_size=Pt(11), header_font_size=Pt(12)):
    """Add a table to the slide with styled header row."""
    table_shape = slide.shapes.add_table(rows, cols, left, top, width, height)
    table = table_shape.table

    # Set column widths equally
    col_w = int(width / cols)
    for i in range(cols):
        table.columns[i].width = col_w

    # Fill data
    for r_idx, row_data in enumerate(data):
        for c_idx, cell_text in enumerate(row_data):
            cell = table.cell(r_idx, c_idx)
            cell.text = str(cell_text)
            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.name = SANS_FONT
                if r_idx == 0:
                    paragraph.font.size = header_font_size
                    paragraph.font.color.rgb = header_font_color
                    paragraph.font.bold = True
                else:
                    paragraph.font.size = body_font_size
                    paragraph.font.color.rgb = BLACK
            # Header row background
            if r_idx == 0:
                cell_fill = cell.fill
                cell_fill.solid()
                cell_fill.fore_color.rgb = header_bg

    return table


def add_rounded_rect(slide, left, top, width, height, text,
                     fill_color=CRIMSON, font_color=WHITE,
                     font_size=Pt(9), font_name=SANS_FONT, bold=False):
    """Add a rounded rectangle with centered text."""
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.color.rgb = fill_color
    tf = shape.text_frame
    tf.word_wrap = True
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    p = tf.paragraphs[0]
    p.text = text
    p.font.name = font_name
    p.font.size = font_size
    p.font.color.rgb = font_color
    p.font.bold = bold
    tf.auto_size = MSO_AUTO_SIZE.NONE
    # Vertically center text
    tf.paragraphs[0].space_before = Pt(0)
    tf.paragraphs[0].space_after = Pt(0)
    return shape


def add_arrow(slide, start_left, start_top, end_left, end_top, color=CRIMSON):
    """Add a connector arrow between two points."""
    # Use a freeform line (notched right arrow shape as connector)
    from pptx.enum.shapes import MSO_SHAPE
    connector = slide.shapes.add_connector(
        1,  # straight connector
        start_left, start_top, end_left, end_top
    )
    connector.line.color.rgb = color
    connector.line.width = Pt(2)
    # Set end arrow
    connector.end_x = end_left
    connector.end_y = end_top
    return connector


# ── SLIDE BUILDERS ────────────────────────────────────────────────────

def build_slide_1(prs):
    """Title Slide — Crimson background, white text."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    set_slide_bg(slide, CRIMSON)

    # --- Top-left: Logo placeholder text ---
    add_textbox(slide, Inches(0.5), Inches(0.3), Inches(3), Inches(0.5),
                text="Amrita Vishwa Vidyapeetham",
                font_name=SANS_FONT, font_size=Pt(13),
                font_color=WHITE, bold=True)

    # Thin vertical yellow line beside logo area
    line = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(3.6), Inches(0.2), Pt(3), Inches(0.7)
    )
    line.fill.solid()
    line.fill.fore_color.rgb = YELLOW
    line.line.fill.background()

    # --- Top-right: S7 PROJECT MID REVIEW ---
    add_textbox(slide, SLIDE_W - Inches(4.5), Inches(0.35),
                Inches(4.2), Inches(0.5),
                text="S7 PROJECT MID REVIEW",
                font_name=SANS_FONT, font_size=Pt(15),
                font_color=WHITE, bold=False,
                alignment=PP_ALIGN.RIGHT)

    # --- Main Title (center-left, large) ---
    add_textbox(slide, Inches(0.8), Inches(2.0), Inches(11), Inches(2.0),
                text="STUN: Adaptive Reinforcement\nLearning for Linux Scheduler\nOptimisation",
                font_name=SERIF_FONT, font_size=Pt(38),
                font_color=WHITE, bold=True,
                alignment=PP_ALIGN.LEFT)

    # --- Bottom-left: Team members (two-column look) ---
    team_box, team_tf = add_textbox(
        slide, Inches(0.8), Inches(5.0), Inches(6), Inches(2.2),
        text="", font_name=SANS_FONT, font_size=Pt(13), font_color=WHITE
    )

    members = [
        ("Ashutosh Vats",    "AM.SC.U4CSE23013"),
        ("Hridya Jain",      "AM.SC.U4CSE23040"),
        ("Sakar Shrestha",   "AM.SC.U4CSE23076"),
        ("Sudhir Kumar Sah", "AM.SC.U4CSE23080"),
    ]

    for i, (name, roll) in enumerate(members):
        if i == 0:
            p = team_tf.paragraphs[0]
        else:
            p = team_tf.add_paragraph()
        p.text = f"{name}    {roll}"
        p.font.name = SANS_FONT
        p.font.size = Pt(13)
        p.font.color.rgb = WHITE
        p.space_before = Pt(3)
        p.space_after = Pt(2)

    # --- Bottom-right: Guided by ---
    guide_box, guide_tf = add_textbox(
        slide, SLIDE_W - Inches(5.5), Inches(5.2), Inches(5.0), Inches(1.8),
        text="", font_name=SANS_FONT, font_size=Pt(13), font_color=WHITE,
        alignment=PP_ALIGN.RIGHT
    )
    p0 = guide_tf.paragraphs[0]
    p0.text = "GUIDED BY"
    p0.font.name = SANS_FONT
    p0.font.size = Pt(12)
    p0.font.color.rgb = YELLOW
    p0.font.bold = True
    p0.alignment = PP_ALIGN.RIGHT

    p1 = guide_tf.add_paragraph()
    p1.text = "Dr. Don S."
    p1.font.name = SANS_FONT
    p1.font.size = Pt(16)
    p1.font.color.rgb = WHITE
    p1.font.bold = True
    p1.alignment = PP_ALIGN.RIGHT

    p2 = guide_tf.add_paragraph()
    p2.text = "Dept. of Computer Science & Engineering"
    p2.font.name = SANS_FONT
    p2.font.size = Pt(12)
    p2.font.color.rgb = WHITE
    p2.alignment = PP_ALIGN.RIGHT


def build_slide_2(prs):
    """Outline slide."""
    slide = new_content_slide(prs, "Outline", 2)

    _, tf = add_textbox(slide, Inches(0.8), Inches(1.3),
                        Inches(11), Inches(5.5),
                        text="", font_name=SANS_FONT, font_size=Pt(18))

    items = [
        "Introduction",
        "Problem Definition",
        "Literature Review Summary",
        "Research Gap",
        "Methodology",
        "Design / Architecture",
        "Algorithms (if any)",
        "Result Analysis",
        "Project Time Line (Plan)",
        "Reference",
    ]
    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = item
        p.font.name = SANS_FONT
        p.font.size = Pt(18)
        p.font.color.rgb = BLACK
        p.space_before = Pt(8)
        p.space_after = Pt(4)
        p.level = 0


def build_slide_3(prs):
    """INTRODUCTION slide — paragraph-based, with bold terms and a flow."""
    slide = new_content_slide(prs, "INTRODUCTION", 3)

    # Main content area
    body_box, tf = add_textbox(
        slide, Inches(0.7), Inches(1.2), Inches(11.8), Inches(5.0),
        text="", font_name=SANS_FONT, font_size=Pt(14)
    )

    # Line 1: Bold subtitle
    p0 = tf.paragraphs[0]
    p0.text = "STUN: Adaptive Reinforcement Learning for Runtime Linux Scheduler Optimisation"
    p0.font.name = SANS_FONT
    p0.font.size = Pt(16)
    p0.font.color.rgb = CRIMSON
    p0.font.bold = True
    p0.space_after = Pt(14)

    # Paragraph: Linux CPU Scheduler
    p1 = tf.add_paragraph()
    p1.space_before = Pt(10)
    r1a = p1.add_run()
    r1a.text = "Linux CPU Scheduler  "
    r1a.font.name = SANS_FONT
    r1a.font.size = Pt(14)
    r1a.font.color.rgb = BLACK
    r1a.font.bold = True
    r1b = p1.add_run()
    r1b.text = ("The Linux scheduler decides how runnable tasks share the available "
                "CPU cores — which task runs, on which core, and for how long.")
    r1b.font.name = SANS_FONT
    r1b.font.size = Pt(14)
    r1b.font.color.rgb = BLACK

    # Paragraph: Scheduler Parameters
    p2 = tf.add_paragraph()
    p2.space_before = Pt(10)
    r2a = p2.add_run()
    r2a.text = "Scheduler Parameters  "
    r2a.font.name = SANS_FONT
    r2a.font.size = Pt(14)
    r2a.font.color.rgb = BLACK
    r2a.font.bold = True
    r2b = p2.add_run()
    r2b.text = ("Linux exposes configurable kernel controls that influence scheduling "
                "behaviour, such as ")
    r2b.font.name = SANS_FONT
    r2b.font.size = Pt(14)
    r2b.font.color.rgb = BLACK
    r2c = p2.add_run()
    r2c.text = "time-slice, real-time CPU bandwidth, task migration/grouping, and utilisation limits."
    r2c.font.name = SANS_FONT
    r2c.font.size = Pt(14)
    r2c.font.color.rgb = BLACK
    r2c.font.bold = True

    # Paragraph: Our Project
    p3 = tf.add_paragraph()
    p3.space_before = Pt(10)
    r3a = p3.add_run()
    r3a.text = "Our Project  "
    r3a.font.name = SANS_FONT
    r3a.font.size = Pt(14)
    r3a.font.color.rgb = BLACK
    r3a.font.bold = True
    r3b = p3.add_run()
    r3b.text = ("STUN investigates whether live system telemetry + Reinforcement Learning "
                "can be used to select suitable scheduler-parameter adjustments while the "
                "system is running.")
    r3b.font.name = SANS_FONT
    r3b.font.size = Pt(14)
    r3b.font.color.rgb = BLACK

    # Bottom bold line
    p4 = tf.add_paragraph()
    p4.space_before = Pt(14)
    p4.text = ("Same hardware, different workload conditions, potentially different "
               "optimal scheduler settings.")
    p4.font.name = SANS_FONT
    p4.font.size = Pt(15)
    p4.font.color.rgb = CRIMSON
    p4.font.bold = True

    # Flow at the very bottom
    flow_box, flow_tf = add_textbox(
        slide, Inches(1.5), Inches(6.15), Inches(10), Inches(0.5),
        text="", font_name=SANS_FONT, font_size=Pt(15),
        alignment=PP_ALIGN.CENTER
    )
    fp = flow_tf.paragraphs[0]
    fp.text = "Workload  →  System State  →  RL Policy  →  Scheduler Adjustment"
    fp.font.name = SANS_FONT
    fp.font.size = Pt(15)
    fp.font.color.rgb = CRIMSON
    fp.font.bold = True
    fp.alignment = PP_ALIGN.CENTER


def build_slide_4(prs):
    """Problem Definition slide."""
    slide = new_content_slide(prs, "Problem Definition", 4)

    _, tf = add_textbox(slide, Inches(0.8), Inches(1.4),
                        Inches(11), Inches(5.0),
                        text="", font_name=SANS_FONT, font_size=Pt(18))

    items = [
        ("Motivation", False),
        ("The Linux kernel scheduler ships with default parameters tuned for "
         "general-purpose workloads. However, specialised workloads (real-time "
         "audio, HPC, cloud microservices) often benefit from different settings, "
         "and manually tuning sysctl knobs requires deep expertise.", True),
        ("Problem Statement", False),
        ("Can a Reinforcement Learning agent, using only live /proc telemetry, "
         "learn to select near-optimal scheduler parameters at runtime — "
         "without manual intervention or workload-specific heuristics?", True),
        ("Objectives", False),
        ("Build a safe, automated pipeline: Monitor → RL → Scheduler → Benchmark → Reward.", True),
        ("Train PPO/SAC agents that outperform Linux defaults on throughput and latency benchmarks.", True),
        ("Ensure defence-in-depth safety: 3-layer validation, rollback stack, watchdog.", True),
    ]

    for i, (text, is_sub) in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = text
        p.font.name = SANS_FONT
        p.font.size = Pt(15) if is_sub else Pt(18)
        p.font.color.rgb = BLACK if is_sub else CRIMSON
        p.font.bold = not is_sub
        p.space_before = Pt(12) if not is_sub else Pt(4)
        p.space_after = Pt(4)
        p.level = 1 if is_sub else 0


def build_slide_5(prs):
    """Literature Review Summary — table."""
    slide = new_content_slide(prs, "Literature Review Summary", 5)

    # Instruction text
    add_textbox(slide, Inches(0.7), Inches(1.2), Inches(11), Inches(0.5),
                text="Key Literature Reviewed (presentation should not exceed 10 mins)",
                font_name=SANS_FONT, font_size=Pt(13),
                font_color=RGBColor(0x66, 0x66, 0x66), italic=True)

    data = [
        ["Year", "Paper / Key Contribution", "Demerit", "Dataset / Workload", "Evaluation Metrics"],
        ["2019", "ghOSt (Google) — user-space\nscheduler framework",
         "Requires custom kernel module;\nnot transparent to stock kernels",
         "Google production traces", "Tail latency, throughput"],
        ["2020", "Decima (MIT) — RL for\njob scheduling in data centres",
         "Focuses on job scheduling,\nnot kernel-level parameters",
         "Spark TPC-H workloads", "Job completion time"],
        ["2021", "PARTIES — QoS-aware\nresource partitioning via RL",
         "Limited to LLC / memory\nbandwidth partitioning",
         "SPEC CPU + Tailbench", "QoS violation rate, IPC"],
        ["2022", "SmartSched — RL-tuned CFS\nbandwidth controls",
         "Only tunes 2 parameters;\nno safety rollback mechanism",
         "stress-ng, sysbench", "Throughput, CPU util %"],
        ["2023", "CFS-RL (Chen et al.) — PPO\nfor CFS time-slice tuning",
         "Single-parameter tuning;\nlimited generalisability",
         "Synthetic CPU-bound loads", "Scheduling latency (μs)"],
    ]
    add_table(slide, len(data), 5, data,
              Inches(0.5), Inches(1.8), Inches(12.3), Inches(4.8),
              body_font_size=Pt(10), header_font_size=Pt(11))


def build_slide_6(prs):
    """Research Gap slide."""
    slide = new_content_slide(prs, "Research Gap", 6)

    _, tf = add_textbox(slide, Inches(0.8), Inches(1.4),
                        Inches(11), Inches(5.0),
                        text="", font_name=SANS_FONT, font_size=Pt(16))

    gaps = [
        "Existing work tunes only 1–2 scheduler parameters; STUN manages 8 "
        "parameters simultaneously via a unified action space.",
        "No prior system provides runtime safety guarantees (validation + "
        "rollback + watchdog) during RL-driven kernel modification.",
        "Previous approaches use offline training; STUN targets online, "
        "closed-loop adaptation using live /proc telemetry.",
        "Literature lacks multi-benchmark evaluation — most papers test on a "
        "single synthetic workload. STUN benchmarks across 5 tools "
        "(stress-ng, sysbench, hackbench, cyclictest, fio).",
        "No existing framework exposes a Gymnasium-compliant environment for "
        "Linux scheduler tuning, limiting reproducibility and comparison.",
    ]

    for i, gap in enumerate(gaps):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = gap
        p.font.name = SANS_FONT
        p.font.size = Pt(15)
        p.font.color.rgb = BLACK
        p.space_before = Pt(10)
        p.space_after = Pt(6)
        p.level = 0


def build_slide_7(prs):
    """Methodology — table of tools and methods."""
    slide = new_content_slide(prs, "Methodology", 7)

    data = [
        ["Category", "Tool / Technology", "Details"],
        ["Language", "Python 3.11+", "Core framework language"],
        ["RL Framework", "Stable-Baselines3 2.3+ (PyTorch)", "PPO and SAC algorithm implementations"],
        ["Gym Interface", "Gymnasium 0.29+", "Standard RL environment interface"],
        ["Dashboard", "PyQt6 + pyqtgraph", "Real-time system monitoring GUI"],
        ["Storage", "SQLite (stdlib sqlite3)", "Snapshots, benchmark results, configs"],
        ["Configuration", "YAML (PyYAML)", "Experiment & component configuration"],
        ["Testing", "pytest 8.0+", "67 unit tests, ~7 s, no root needed"],
        ["Kernel Interface", "/proc filesystem + sysctl", "Read system state, write scheduler params"],
        ["Benchmarks", "stress-ng, sysbench, hackbench,\ncyclictest, fio", "5 pluggable benchmark adapters"],
        ["Platform", "Linux (kernel 5.15+)", "Target OS with scheduler sysctl support"],
        ["Hardware", "x86_64 multi-core CPU", "Standard server / workstation hardware"],
    ]

    add_table(slide, len(data), 3, data,
              Inches(0.5), Inches(1.3), Inches(12.3), Inches(5.2),
              body_font_size=Pt(11), header_font_size=Pt(12))

    # The stray 'j' from the original
    add_textbox(slide, Inches(12), Inches(6.5), Inches(0.5), Inches(0.3),
                text="j", font_name=SANS_FONT, font_size=Pt(10),
                font_color=RGBColor(0xCC, 0xCC, 0xCC))


def build_slide_8(prs):
    """Design / Architecture — paragraph form + circular flow diagram."""
    slide = new_content_slide(prs, "Design / Architecture", 8)

    # Subtitle
    add_textbox(slide, Inches(0.7), Inches(1.15), Inches(8), Inches(0.4),
                text="One Closed Loop, Six Stages",
                font_name=SANS_FONT, font_size=Pt(16),
                font_color=RGBColor(0x55, 0x55, 0x55), italic=True)

    # Paragraph descriptions
    _, tf = add_textbox(slide, Inches(0.7), Inches(1.6), Inches(12.2), Inches(2.3),
                        text="", font_name=SANS_FONT, font_size=Pt(12))

    stages_text = [
        "① The monitor reads /proc — CPU, load, memory, context switches.",
        "② The StateBuilder turns those raw readings into a normalised observation vector.",
        "③ The policy network picks an action — just a number.",
        "④ The ActionMapper decodes that number back into real scheduler parameters.",
        "⑤ The controller validates them and writes them to the kernel, with a readback.",
        "⑥ The benchmark suite measures what that configuration actually did, and turns it into a single reward.",
    ]

    for i, st in enumerate(stages_text):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = st
        p.font.name = SANS_FONT
        p.font.size = Pt(12)
        p.font.color.rgb = BLACK
        p.space_before = Pt(2)
        p.space_after = Pt(1)

    p_last = tf.add_paragraph()
    p_last.text = "That reward feeds back into stage one and the lap repeats."
    p_last.font.name = SANS_FONT
    p_last.font.size = Pt(12)
    p_last.font.color.rgb = CRIMSON
    p_last.font.bold = True
    p_last.space_before = Pt(6)

    # ── Circular Flow Diagram (6 blocks + central kernel block) ──
    # Layout: blocks arranged in an oval pattern

    block_w = Inches(1.9)
    block_h = Inches(0.75)

    # Positions for the 6 outer blocks (roughly circular)
    # Top row: blocks 1, 2, 3
    # Bottom row: blocks 6, 5 (reversed for circular flow)
    # Center: Linux Kernel

    center_x = Inches(6.7)
    center_y = Inches(5.6)

    positions = [
        (Inches(0.5),  Inches(4.4)),   # Block 1 - top left
        (Inches(2.7),  Inches(4.4)),   # Block 2
        (Inches(4.9),  Inches(4.4)),   # Block 3
        (Inches(8.5),  Inches(4.4)),   # Block 4
        (Inches(10.7), Inches(4.4)),   # Block 5
        (Inches(10.7), Inches(5.8)),   # Block 6 - bottom right
    ]

    # Central kernel block
    kernel_x = Inches(7.2)
    kernel_y = Inches(5.6)
    kernel_w = Inches(2.6)
    kernel_h = Inches(1.1)

    block_labels = [
        "1. monitor/\nRead the machine",
        "2. rl/state.py\nBuild the\nobservation",
        "3. core/trainer.py\nPolicy picks\nan action",
        "4. rl/action.py\nDecode to\nparameters",
        "5. scheduler/\nValidate\nand write",
        "6. benchmarks/\nMeasure, score,\nreward",
    ]

    block_colors = [
        RGBColor(0x2E, 0x86, 0xAB),  # Blue
        RGBColor(0x56, 0x4D, 0x80),  # Purple
        RGBColor(0x9E, 0x00, 0x3E),  # Crimson
        RGBColor(0xD4, 0x6B, 0x08),  # Orange
        RGBColor(0x1B, 0x7A, 0x3D),  # Green
        RGBColor(0x86, 0x3B, 0x00),  # Brown
    ]

    # Reposition for a cleaner horizontal flow layout
    row_y = Inches(4.2)
    row2_y = Inches(5.9)
    x_positions_top = [Inches(0.4), Inches(2.65), Inches(4.9), Inches(9.0), Inches(11.0)]
    x_positions_bot = [Inches(0.4), Inches(11.0)]

    # Cleaner layout: blocks 1-4 in a row, block 5 connects to kernel, block 6 at bottom
    flow_positions = [
        (Inches(0.3),  row_y),     # 1
        (Inches(2.5),  row_y),     # 2
        (Inches(4.7),  row_y),     # 3
        (Inches(6.9),  row_y),     # 4
        (Inches(9.1),  row_y),     # 5
        (Inches(4.7),  row2_y),    # 6
    ]

    for i, (bx, by) in enumerate(flow_positions):
        add_rounded_rect(slide, bx, by, block_w, block_h + Inches(0.15),
                         block_labels[i],
                         fill_color=block_colors[i],
                         font_color=WHITE,
                         font_size=Pt(9),
                         bold=True)

    # Central kernel block (between block 5 and block 6)
    add_rounded_rect(slide, Inches(7.0), row2_y, Inches(2.8), Inches(0.9),
                     "The System Under Test\nLINUX KERNEL",
                     fill_color=RGBColor(0x33, 0x33, 0x33),
                     font_color=WHITE, font_size=Pt(11), bold=True)

    # Arrow labels between blocks (using simple text boxes as arrow indicators)
    arrow_positions = [
        (Inches(2.15), row_y + Inches(0.3), "→"),
        (Inches(4.4),  row_y + Inches(0.3), "→"),
        (Inches(6.6),  row_y + Inches(0.3), "→"),
        (Inches(8.8),  row_y + Inches(0.3), "→"),
    ]
    for ax, ay, at in arrow_positions:
        add_textbox(slide, ax, ay, Inches(0.35), Inches(0.3),
                    text=at, font_name=SANS_FONT, font_size=Pt(20),
                    font_color=CRIMSON, bold=True, alignment=PP_ALIGN.CENTER)

    # Arrow from block 5 down to kernel
    add_textbox(slide, Inches(9.9), Inches(5.3), Inches(0.35), Inches(0.5),
                text="↓", font_name=SANS_FONT, font_size=Pt(20),
                font_color=CRIMSON, bold=True, alignment=PP_ALIGN.CENTER)

    # Arrow from kernel to block 6
    add_textbox(slide, Inches(6.6), row2_y + Inches(0.2), Inches(0.35), Inches(0.5),
                text="←", font_name=SANS_FONT, font_size=Pt(20),
                font_color=CRIMSON, bold=True, alignment=PP_ALIGN.CENTER)

    # Arrow from block 6 back to block 1 (loop)
    add_textbox(slide, Inches(2.3), row2_y + Inches(0.2), Inches(0.35), Inches(0.5),
                text="←", font_name=SANS_FONT, font_size=Pt(20),
                font_color=CRIMSON, bold=True, alignment=PP_ALIGN.CENTER)

    # Loop-back label
    add_textbox(slide, Inches(0.3), row2_y + Inches(0.05), Inches(1.9), Inches(0.9),
                text="↑ reward loops\nback to stage 1",
                font_name=SANS_FONT, font_size=Pt(10),
                font_color=CRIMSON, bold=True, alignment=PP_ALIGN.CENTER)


def build_slide_9(prs):
    """Sequence diagram: Inside one env.step()."""
    slide = new_content_slide(prs, "", 9)

    # Custom title with mixed formatting
    title_box, title_tf = add_textbox(
        slide, Inches(0.6), Inches(0.3), Inches(12), Inches(0.7),
        text="", font_name=SANS_FONT, font_size=Pt(28)
    )
    tp = title_tf.paragraphs[0]
    r1 = tp.add_run()
    r1.text = "Inside one "
    r1.font.name = SANS_FONT
    r1.font.size = Pt(28)
    r1.font.color.rgb = BLACK
    r1.font.bold = True
    r2 = tp.add_run()
    r2.text = "env.step()"
    r2.font.name = MONO_FONT
    r2.font.size = Pt(28)
    r2.font.color.rgb = GREEN
    r2.font.bold = True
    r3 = tp.add_run()
    r3.text = ": action in, reward out"
    r3.font.name = SANS_FONT
    r3.font.size = Pt(28)
    r3.font.color.rgb = BLACK
    r3.font.bold = True

    # ── Build a text-based sequence diagram ──
    # 5 participant columns
    participants = [
        ("Trainer\n(core/)", RGBColor(0x9E, 0x00, 0x3E)),
        ("Environment\n(rl/)", RGBColor(0x2E, 0x86, 0xAB)),
        ("Controller\n(scheduler/\n+ safety/)", RGBColor(0x1B, 0x7A, 0x3D)),
        ("Kernel\n(/proc/sys)", RGBColor(0x33, 0x33, 0x33)),
        ("Benchmarks\n(benchmarks/)", RGBColor(0xD4, 0x6B, 0x08)),
    ]

    col_w = Inches(2.2)
    start_x = Inches(0.5)
    header_y = Inches(1.3)
    header_h = Inches(0.9)

    # Draw participant boxes
    for i, (label, color) in enumerate(participants):
        x = start_x + i * col_w + Inches(i * 0.15)
        add_rounded_rect(slide, x, header_y, Inches(2.0), header_h,
                         label, fill_color=color, font_color=WHITE,
                         font_size=Pt(11), bold=True)

        # Vertical lifeline (dashed effect using thin rect)
        line = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            x + Inches(0.97), header_y + header_h,
            Pt(2), Inches(4.0)
        )
        line.fill.solid()
        line.fill.fore_color.rgb = RGBColor(0xBB, 0xBB, 0xBB)
        line.line.fill.background()

    # Sequence arrows (text-based representation)
    arrows_data = [
        (0, 1, "1. action", Inches(2.5)),
        (1, 2, "2. mapped parameters", Inches(3.1)),
        (2, 3, "3. write + readback", Inches(3.7)),
        (1, 4, "4. run benchmark on\n    the new configuration", Inches(4.3)),
        (4, 1, "5. raw score +\n    fresh snapshot", Inches(5.0)),
        (1, 0, "6. obs, reward, done", Inches(5.7)),
    ]

    for src, dst, label, y_pos in arrows_data:
        src_x = start_x + src * col_w + Inches(src * 0.15) + Inches(1.0)
        dst_x = start_x + dst * col_w + Inches(dst * 0.15) + Inches(1.0)

        # Arrow direction indicator
        if dst > src:
            arrow_text = "─" * max(3, (dst - src) * 5) + "→"
            ax = src_x
            aw = dst_x - src_x + Inches(0.2)
            align = PP_ALIGN.LEFT
        else:
            arrow_text = "←" + "─" * max(3, (src - dst) * 5)
            ax = dst_x
            aw = src_x - dst_x + Inches(0.2)
            align = PP_ALIGN.RIGHT

        # Label above arrow
        label_x = min(src_x, dst_x)
        label_w = abs(dst_x - src_x) + Inches(0.5)
        add_textbox(slide, label_x, y_pos - Pt(16), label_w, Inches(0.4),
                    text=label, font_name=SANS_FONT, font_size=Pt(10),
                    font_color=CRIMSON, bold=True, alignment=PP_ALIGN.CENTER)

        # Arrow line
        add_textbox(slide, ax, y_pos + Pt(4), aw, Inches(0.25),
                    text=arrow_text, font_name=MONO_FONT, font_size=Pt(10),
                    font_color=RGBColor(0x66, 0x66, 0x66), alignment=align)


def build_slide_10(prs):
    """Algorithms (if any)."""
    slide = new_content_slide(prs, "Algorithms (if any)", 10)

    _, tf = add_textbox(slide, Inches(0.8), Inches(1.4),
                        Inches(11), Inches(5.0),
                        text="", font_name=SANS_FONT, font_size=Pt(16))

    items = [
        ("Emphasis: Novelty / Innovation", True),
        ("Gymnasium-compliant RL environment for kernel scheduler tuning — "
         "first of its kind with multi-parameter action space.", False),
        ("Defence-in-depth safety pipeline: 3-layer validation → write → "
         "readback → rollback stack → watchdog.", False),
        ("Training and Testing Steps", True),
        ("Training: PPO (Proximal Policy Optimisation) via Stable-Baselines3. "
         "Discrete action space: 3 actions per parameter (nudge up / down / no-op).", False),
        ("Episode = 50 steps. Each step: observe → act → benchmark → reward.", False),
        ("Testing: evaluate() runs 10 episodes with deterministic policy; "
         "reports mean ± std reward.", False),
        ("Hyperparameter Values", True),
        ("Learning rate: 3×10⁻⁴  |  Batch size: 64  |  n_steps: 2048  |  "
         "Epochs per update: 10", False),
        ("γ (discount): 0.99  |  GAE λ: 0.95  |  Clip range: 0.2  |  "
         "Entropy coeff: 0.01", False),
        ("EMA α (reward baseline): 0.1  |  Rollback penalty: −0.5  |  "
         "Stability bonus: +0.1", False),
    ]

    for i, (text, is_header) in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = text
        p.font.name = SANS_FONT
        p.font.size = Pt(16) if is_header else Pt(13)
        p.font.color.rgb = CRIMSON if is_header else BLACK
        p.font.bold = is_header
        p.space_before = Pt(14) if is_header else Pt(4)
        p.space_after = Pt(4)
        p.level = 0 if is_header else 1


def build_slide_11(prs):
    """Result Analysis."""
    slide = new_content_slide(prs, "Result Analysis", 11)

    _, tf = add_textbox(slide, Inches(0.8), Inches(1.3),
                        Inches(11), Inches(1.0),
                        text="", font_name=SANS_FONT, font_size=Pt(15))

    items = [
        "Comparison with existing works (SOTA)",
        "Should include both visual and quantitative results",
        "Quantitative results in TABLE below",
    ]
    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = item
        p.font.name = SANS_FONT
        p.font.size = Pt(15)
        p.font.color.rgb = BLACK
        p.space_before = Pt(6)

    # Placeholder results table
    data = [
        ["Method", "Benchmark", "Throughput\nImprovement", "Latency\nReduction", "Safety\nViolations"],
        ["Linux Defaults", "stress-ng", "baseline", "baseline", "N/A"],
        ["Hand-Tuned", "stress-ng", "+8%", "−5%", "N/A"],
        ["SmartSched (2022)", "stress-ng", "+12%", "−9%", "3 rollbacks"],
        ["STUN (Ours)", "stress-ng", "TBD", "TBD", "0 (by design)"],
        ["Linux Defaults", "hackbench", "baseline", "baseline", "N/A"],
        ["STUN (Ours)", "hackbench", "TBD", "TBD", "0 (by design)"],
    ]

    add_table(slide, len(data), 5, data,
              Inches(0.5), Inches(3.0), Inches(12.3), Inches(3.5),
              body_font_size=Pt(11))


def build_slide_12(prs):
    """Project Time Line (Plan)."""
    slide = new_content_slide(prs, "Project Time Line (Plan)", 12)

    # Current Status section
    _, tf1 = add_textbox(slide, Inches(0.8), Inches(1.3),
                         Inches(11), Inches(0.5),
                         text="Current Status",
                         font_name=SANS_FONT, font_size=Pt(20),
                         font_color=CRIMSON, bold=True)

    status_data = [
        ["Milestone", "Description", "Status"],
        ["M1", "System Monitor + SQLite Storage", "✅ Complete"],
        ["M2", "Scheduler Controller + Safety Pipeline", "✅ Complete"],
        ["M3", "RL Environment + Benchmark Adapters", "✅ Complete"],
        ["M4", "Trainer (PPO/SAC) + Checkpointing", "✅ Complete"],
        ["Testing", "67 unit tests, all passing", "✅ Complete"],
        ["Dashboard", "PyQt6 live monitoring GUI", "✅ Complete"],
    ]
    add_table(slide, len(status_data), 3, status_data,
              Inches(0.5), Inches(1.9), Inches(12.3), Inches(2.5),
              body_font_size=Pt(11))

    # Future Plan section
    _, tf2 = add_textbox(slide, Inches(0.8), Inches(4.6),
                         Inches(11), Inches(0.5),
                         text="Future Plan",
                         font_name=SANS_FONT, font_size=Pt(20),
                         font_color=CRIMSON, bold=True)

    future_data = [
        ["Phase", "Description", "Timeline"],
        ["M5", "Experiment Pipeline + Reproducibility", "~2 weeks"],
        ["M6", "Multi-Workload Training + Curriculum Learning", "~2 weeks"],
        ["M7", "Live Deployment Mode (systemd service)", "~3 weeks"],
        ["M8", "Rigorous Evaluation vs. SOTA Baselines", "~1 week"],
        ["M9", "Dashboard v2 — RL Training Visualisation", "~1 week"],
    ]
    add_table(slide, len(future_data), 3, future_data,
              Inches(0.5), Inches(5.2), Inches(12.3), Inches(1.6),
              body_font_size=Pt(11))


def build_slide_13(prs):
    """Reference — blank body."""
    slide = new_content_slide(prs, "Reference", 13)

    # Leave body blank as instructed
    add_textbox(slide, Inches(0.8), Inches(2.5), Inches(11), Inches(1.0),
                text="[References to be added]",
                font_name=SANS_FONT, font_size=Pt(14),
                font_color=RGBColor(0xBB, 0xBB, 0xBB), italic=True)


# ── MAIN ──────────────────────────────────────────────────────────────

def main():
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    build_slide_1(prs)
    build_slide_2(prs)
    build_slide_3(prs)
    build_slide_4(prs)
    build_slide_5(prs)
    build_slide_6(prs)
    build_slide_7(prs)
    build_slide_8(prs)
    build_slide_9(prs)
    build_slide_10(prs)
    build_slide_11(prs)
    build_slide_12(prs)
    build_slide_13(prs)

    output_path = "S7_MidReview_STUN.pptx"
    prs.save(output_path)
    print(f"✅ Presentation saved to: {output_path}")
    print(f"   {len(prs.slides)} slides generated.")


if __name__ == "__main__":
    main()
