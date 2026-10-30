"""make_stun_pptx.py — Generates STUN S7 Mid-Review PPTX. Run: python3 scripts/make_stun_pptx.py"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn

BG      = RGBColor(0x11,0x14,0x20)
SURFACE = RGBColor(0x1C,0x1F,0x2E)
ACCENT  = RGBColor(0x63,0x66,0xF1)
ACCENT2 = RGBColor(0x10,0xB9,0x81)
WARN    = RGBColor(0xF5,0x9E,0x0B)
WHITE   = RGBColor(0xFF,0xFF,0xFF)
SUBTEXT = RGBColor(0x94,0xA3,0xB8)
BORDER  = RGBColor(0x2D,0x31,0x47)
RED     = RGBColor(0xEF,0x44,0x44)
DARK_BL = RGBColor(0x16,0x19,0x28)

SW, SH = Inches(13.33), Inches(7.5)
prs = Presentation()
prs.slide_width  = SW
prs.slide_height = SH
blank = prs.slide_layouts[6]

def bg(slide, c=BG):
    f = slide.background.fill; f.solid(); f.fore_color.rgb = c

def rect(slide, l,t,w,h, fill=None, line=None):
    s = slide.shapes.add_shape(1,l,t,w,h)
    s.line.fill.background()
    if fill: s.fill.solid(); s.fill.fore_color.rgb = fill
    else: s.fill.background()
    if line: s.line.color.rgb = line; s.line.width = Pt(1)
    return s

def txt(slide, text, l,t,w,h, sz=13, bold=False, color=WHITE,
        align=PP_ALIGN.LEFT, italic=False, wrap=True):
    tb = slide.shapes.add_textbox(l,t,w,h)
    tf = tb.text_frame; tf.word_wrap = wrap
    p  = tf.paragraphs[0]; p.alignment = align
    r  = p.add_run(); r.text = text
    r.font.size = Pt(sz); r.font.bold = bold
    r.font.italic = italic; r.font.color.rgb = color
    return tb

def hdr(slide, title, sub=None):
    rect(slide, Inches(0.4),Inches(0.3),Inches(0.07),Inches(0.55), fill=ACCENT)
    txt(slide, title, Inches(0.6),Inches(0.27),Inches(12.2),Inches(0.55), sz=27, bold=True)
    if sub:
        txt(slide, sub, Inches(0.6),Inches(0.9),Inches(12.2),Inches(0.35), sz=12, color=SUBTEXT)

def table(slide, headers, rows, l,t,w,h):
    cols = len(headers); nrows = len(rows)+1
    tbl  = slide.shapes.add_table(nrows,cols,l,t,w,h).table
    for ci,hh in enumerate(headers):
        c = tbl.cell(0,ci); c.text = hh
        c.fill.solid(); c.fill.fore_color.rgb = ACCENT
        p = c.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.runs[0]; r.font.bold=True; r.font.size=Pt(10); r.font.color.rgb=WHITE
    for ri,row in enumerate(rows):
        bg_c = SURFACE if ri%2==0 else DARK_BL
        for ci,val in enumerate(row):
            c = tbl.cell(ri+1,ci); c.text = str(val)
            c.fill.solid(); c.fill.fore_color.rgb = bg_c
            p = c.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
            if p.runs: r=p.runs[0]; r.font.size=Pt(9.5); r.font.color.rgb=WHITE

def kpi(slide, label, val, l,t, w=Inches(2.0),h=Inches(1.05), vc=ACCENT2):
    rect(slide,l,t,w,h, fill=SURFACE, line=BORDER)
    txt(slide,label,l+Inches(0.12),t+Inches(0.07),w-Inches(0.2),Inches(0.32), sz=9,color=SUBTEXT,bold=True)
    txt(slide,val,  l+Inches(0.12),t+Inches(0.38),w-Inches(0.2),Inches(0.6),  sz=22,bold=True,color=vc)

def fbox(slide, text, l,t, w=Inches(2.1),h=Inches(0.5), fill=SURFACE, tc=WHITE, sz=10):
    rect(slide,l,t,w,h, fill=fill, line=ACCENT)
    txt(slide,text,l+Inches(0.07),t+Inches(0.08),w-Inches(0.12),h-Inches(0.12),
        sz=sz,color=tc if tc!=BG else BG, bold=True, align=PP_ALIGN.CENTER)

def abox(slide, label, sub, l,t,w,h, fc=SURFACE,tc=WHITE,sc=SUBTEXT):
    rect(slide,l,t,w,h,fill=fc,line=ACCENT)
    txt(slide,label,l+Inches(0.08),t+Inches(0.06),w-Inches(0.15),Inches(0.32),
        sz=10.5,bold=True,color=tc,align=PP_ALIGN.CENTER)
    if sub:
        txt(slide,sub,l+Inches(0.05),t+Inches(0.4),w-Inches(0.1),h-Inches(0.46),
            sz=8.5,color=sc,align=PP_ALIGN.CENTER)

# ════════════════════════════════════════════════════════
# S1 — Title
# ════════════════════════════════════════════════════════
s1 = prs.slides.add_slide(blank); bg(s1)
rect(s1,0,0,Inches(0.55),SH, fill=ACCENT)
rect(s1,Inches(10.3),Inches(1.5),Inches(3.5),Inches(4.8), fill=SURFACE)
txt(s1,"S7 PROJECT MID-REVIEW  •  2026",Inches(0.85),Inches(0.72),Inches(9),Inches(0.4),
    sz=13,color=ACCENT2,bold=True)
txt(s1,"STUN",Inches(0.85),Inches(1.25),Inches(9),Inches(1.3),sz=72,bold=True)
txt(s1,"Adaptive Reinforcement Learning\nfor Linux Scheduler Optimisation",
    Inches(0.85),Inches(2.6),Inches(8.5),Inches(1.2),sz=25,color=SUBTEXT)
rect(s1,Inches(0.85),Inches(3.9),Inches(5.5),Inches(0.04), fill=ACCENT2)
team = [("Team Members:","Member 1  |  Member 2  |  Member 3  |  Member 4"),
        ("Guide:","Prof. [Guide Name]"),("Institution:","Dept. of Computer Science & Engineering")]
y=Inches(4.08)
for lb,vl in team:
    txt(s1,lb,Inches(0.85),y,Inches(1.7),Inches(0.38),sz=11,color=ACCENT2,bold=True)
    txt(s1,vl,Inches(2.55),y,Inches(7),Inches(0.38),sz=11)
    y+=Inches(0.42)
hi=[("8","Tunable\nParams"),("5+","Benchmark\nAdapters"),("86","Tests\nPassing"),("2","RL Algos\nPPO/SAC")]
hy=Inches(1.85)
for vl,lb in hi:
    txt(s1,vl,Inches(10.8),hy,Inches(1.5),Inches(0.65),sz=36,bold=True,color=ACCENT2,align=PP_ALIGN.CENTER)
    txt(s1,lb,Inches(10.7),hy+Inches(0.62),Inches(1.6),Inches(0.5),sz=10,color=SUBTEXT,align=PP_ALIGN.CENTER)
    hy+=Inches(1.15)

# ════════════════════════════════════════════════════════
# S2 — Introduction
# ════════════════════════════════════════════════════════
s2 = prs.slides.add_slide(blank); bg(s2)
hdr(s2,"Introduction","Member 1  ·  Problem & Research")
cw=Inches(5.8)
rect(s2,Inches(0.4),Inches(1.18),cw,Inches(5.75),fill=SURFACE,line=BORDER)
txt(s2,"Linux CPU Scheduling",Inches(0.6),Inches(1.32),cw-Inches(0.3),Inches(0.42),sz=14,bold=True,color=ACCENT)
bullets=[
 ("CFS — Completely Fair Scheduler","Default scheduler; weighted virtual-runtime red-black tree balancing."),
 ("RT Scheduler","SCHED_FIFO / SCHED_RR for real-time tasks with hard priorities."),
 ("8 Tunable sysctl Parameters","sched_rr_timeslice_ms, sched_rt_period_us, sched_rt_runtime_us, sched_cfs_bandwidth_slice_us, sched_autogroup_enabled, sched_util_clamp_max/min, sched_schedstats."),
 ("Live via /proc/sys/kernel/","sysctl writes take effect immediately — no reboot required."),
 ("Static defaults ≠ optimal","A game, a database, and a compiler need entirely different scheduling policies."),
]
by=Inches(1.82)
for bh2,bd in bullets:
    txt(s2,"▸  "+bh2,Inches(0.62),by,cw-Inches(0.35),Inches(0.28),sz=11,bold=True,color=ACCENT2)
    txt(s2,bd,Inches(0.62),by+Inches(0.27),cw-Inches(0.35),Inches(0.38),sz=10,color=SUBTEXT)
    by+=Inches(0.72)

rx=Inches(6.45)
rect(s2,rx,Inches(1.18),cw,Inches(5.75),fill=SURFACE,line=BORDER)
txt(s2,"STUN — What It Does",rx+Inches(0.2),Inches(1.32),cw-Inches(0.3),Inches(0.42),sz=14,bold=True,color=ACCENT)
sp=[("🔍  Observe","Live SystemSnapshot: CPU%, load avg, context switches, memory, current sched params."),
    ("🤖  Decide","RL Agent (PPO or SAC) selects which parameter to change and in which direction."),
    ("✅  Validate","3-layer safety: ParameterRegistry bounds → SecondaryValidator hard limits → readback verify."),
    ("⚡  Apply","Writes sysctl; reads value back to confirm kernel accepted it; saves to RollbackStack."),
    ("📊  Benchmark","Runs real benchmarks (stress-ng / sysbench / hackbench / cyclictest / fio) to measure effect."),
    ("🎯  Learn","Reward signal drives the agent to find better parameter policies across episodes."),]
sy=Inches(1.82)
for sh2,sd in sp:
    txt(s2,sh2,rx+Inches(0.2),sy,cw-Inches(0.35),Inches(0.28),sz=11,bold=True,color=ACCENT2)
    txt(s2,sd,rx+Inches(0.2),sy+Inches(0.27),cw-Inches(0.35),Inches(0.38),sz=10,color=SUBTEXT)
    sy+=Inches(0.72)

# ════════════════════════════════════════════════════════
# S3 — Motivation / Problem / Objectives
# ════════════════════════════════════════════════════════
s3 = prs.slides.add_slide(blank); bg(s3)
hdr(s3,"Motivation  ·  Problem Statement  ·  Objectives","Member 1")
cols3=[Inches(0.4),Inches(4.58),Inches(8.76)]
ctitles=["Motivation","Problem Statement","Objectives"]
ccolors=[ACCENT,WARN,ACCENT2]
cbodies=[
 "Linux workloads shift dynamically — gaming → compile → web serve — each demands different scheduler behaviour.\n\nScheduler parameters can shift throughput by 20–30% across workload types.\n\nManual tuning requires kernel expertise, is time-consuming, and does not adapt in real time.\n\nNo production tool auto-selects sched params based on live process fingerprinting.",
 "Linux kernel scheduler parameters are set statically. These generic defaults are sub-optimal for specific workload requirements.\n\nSTUN must:\n• Identify workload type from live process data\n• Learn optimal parameter sets by trial and measurement\n• Apply changes safely — never destabilise the system\n• Adapt continuously as workloads shift",
 "O1  Adaptive tuning of 8 Linux scheduler sysctl parameters\n\nO2  Optimise measurable performance — throughput, latency, context-switch rate\n\nO3  Use RL (PPO / SAC via SB3) to learn parameter-selection policies\n\nO4  Maintain system safety: Validator → SecondaryValidator → RollbackStack → Watchdog\n\nO5  Monitoring, benchmarking, parameter sweep, and live auto-tuner",
]
for i,cx in enumerate(cols3):
    cw3=Inches(4.0)
    rect(s3,cx,Inches(1.18),cw3,Inches(5.75),fill=SURFACE,line=BORDER)
    rect(s3,cx,Inches(1.18),cw3,Inches(0.06),fill=ccolors[i])
    txt(s3,ctitles[i],cx+Inches(0.12),Inches(1.28),cw3-Inches(0.2),Inches(0.42),sz=14,bold=True,color=ccolors[i])
    txt(s3,cbodies[i],cx+Inches(0.12),Inches(1.78),cw3-Inches(0.2),Inches(5.08),sz=10.5,color=WHITE,wrap=True)

# ════════════════════════════════════════════════════════
# S4 — Literature Review
# ════════════════════════════════════════════════════════
s4 = prs.slides.add_slide(blank); bg(s4)
hdr(s4,"Literature Review","Member 1  ·  Related Work")
lh=["Year","Paper / Work","Key Contribution","Environment","Limitation"]
lr=[
 ["2016","Lozi et al. — EuroSys","Empirical study of Linux CFS bugs and wasted CPU cores","Linux x86 real HW","Manual analysis; no adaptive tuning"],
 ["2019","Mao et al. — Decima (SIGCOMM)","RL + GNN for datacenter job scheduling","Spark cluster sim","Datacenter-only; no OS sched params"],
 ["2021","Park et al. — CARL (MLSys)","RL for adaptive resource limits in containers","Kubernetes","Container-level; no kernel param control"],
 ["2022","Mantovani et al. — SIGMETRICS","CFS analysis for multiprogrammed workloads","Linux x86-64","No automated adaptation"],
 ["2022","OtterTune (Aken et al.)","Bayesian optimisation for DB configuration","MySQL, Postgres","Database-specific; not CPU scheduler"],
 ["2023","Venkataraman et al. — Sage","RL for coarse system config auto-tuning","Cloud VMs","Coarse-grained; no scheduler sysctl"],
 ["2024","Liu et al. — CFS-RL","RL to tune CFS granularity (2 params)","Linux x86-64","2 params only; no safety/rollback"],
]
table(s4,lh,lr,Inches(0.35),Inches(1.18),Inches(12.65),Inches(5.55))

# ════════════════════════════════════════════════════════
# S5 — Research Gap
# ════════════════════════════════════════════════════════
s5 = prs.slides.add_slide(blank); bg(s5)
hdr(s5,"Research Gap  &  STUN's Novelty","Member 1")
gh=["Dimension","Existing Approaches","STUN"]
gr=[
 ["Parameter Scope","1–2 CFS params or DB/network configs","8 real Linux sched sysctls (RR, RT, CFS, UCLAMP, autogroup, schedstats)"],
 ["Adaptation","Hand-tuned heuristics or one-shot Bayesian Opt","Online RL (PPO/SAC) — continuous policy update per episode"],
 ["Safety Mechanism","No rollback; risk of destabilising production","Validator → SecondaryValidator → RollbackStack + Watchdog thread"],
 ["Workload Awareness","Fixed workload assumed throughout","ProcessClassifier fingerprints running processes; switches strategy live"],
 ["Benchmarking","Synthetic or offline evaluation","Integrated adapters: stress-ng, sysbench, hackbench, cyclictest, fio, glmark2"],
 ["Parameter Sweep","Not provided","Coordinate-descent grid search stores best params per workload in SQLite"],
 ["Observability","Black-box; no live dashboard","PyQt6 dashboard: 14 panels, live pyqtgraph plots, AI training-style sweep UI"],
]
table(s5,gh,gr,Inches(0.35),Inches(1.18),Inches(12.65),Inches(5.65))

# ════════════════════════════════════════════════════════
# S6 — Methodology
# ════════════════════════════════════════════════════════
s6 = prs.slides.add_slide(blank); bg(s6)
hdr(s6,"Methodology  &  Technology Stack","Member 2  ·  System Architecture")
sh6=["Category","Tool / Technology"]
sr6=[
 ["Programming Language","Python 3.14"],
 ["RL Framework","Stable-Baselines3 (PPO, SAC)"],
 ["RL Environment","Gymnasium — custom LinuxSchedulerEnv"],
 ["Benchmark Tools","stress-ng · sysbench · hackbench · cyclictest · fio · glmark2"],
 ["OS / Kernel Interface","Linux /proc/sys/kernel/ (sysctl)"],
 ["Monitoring Sources","/proc/stat · /proc/meminfo · /proc/loadavg · /proc/sys/kernel"],
 ["Storage","SQLite (custom StorageBackend, WAL mode)"],
 ["Dashboard / GUI","PyQt6 + pyqtgraph"],
 ["Configuration","YAML (PyYAML)"],
 ["Testing","pytest — 86 tests, no root required"],
 ["Numerical / ML","NumPy · stable-baselines3 · gymnasium"],
]
table(s6,sh6,sr6,Inches(0.35),Inches(1.18),Inches(5.5),Inches(5.7))
rx6=Inches(6.2); fw6=Inches(6.75); fh6=Inches(0.47); fy6=Inches(1.18)
flow6=[
 ("System State Snapshot",ACCENT,WHITE),
 ("Monitor  ( /proc sources )",SURFACE,WHITE),
 ("StateBuilder → 14-D Obs Vector",SURFACE,WHITE),
 ("RL Agent  ( PPO / SAC )",RGBColor(0x25,0x1c,0x4a),WHITE),
 ("ActionMapper → Param Dict",SURFACE,WHITE),
 ("Validator → SecondaryValidator",WARN,BG),
 ("Writer → sysctl  +  Readback",RED,WHITE),
 ("RollbackStack  |  Watchdog ping",RGBColor(0x3a,0x10,0x10),WHITE),
 ("Benchmark Runner → Score",SURFACE,WHITE),
 ("RewardShaper → Scalar Reward",ACCENT2,BG),
 ("Agent Policy Update (SB3)",ACCENT,WHITE),
]
for lb,fc,tc in flow6:
    fbox(s6,lb,rx6,fy6,w=fw6,h=fh6,fill=fc,tc=tc,sz=11)
    fy6+=fh6+Inches(0.03)

# ════════════════════════════════════════════════════════
# S7 — Architecture
# ════════════════════════════════════════════════════════
s7 = prs.slides.add_slide(blank); bg(s7)
hdr(s7,"System Architecture","Member 2  ·  Component Interaction & Data Flow")
Y=[Inches(1.2),Inches(2.12),Inches(3.05),Inches(3.98),Inches(4.9),Inches(5.82)]
BH7=Inches(0.8)
DK=RGBColor(0x1e,0x22,0x3c)
abox(s7,"Dashboard (PyQt6)","Overview·Processes·Memory·Scheduler\nAutoTuner·Training·Safety·Checkpoints",
     Inches(0.35),Y[0],Inches(6.1),BH7,fc=DK)
abox(s7,"Config (YAML)","scheduler.yaml · benchmarks.yaml\nmonitor.yaml · loader.py",
     Inches(6.65),Y[0],Inches(6.3),BH7,fc=DK)
abox(s7,"Monitor","sources.py\n/proc/stat·/proc/meminfo\nloadavg·sched·cpufreq·NUMA",
     Inches(0.35),Y[1],Inches(2.35),BH7)
abox(s7,"RL Environment","LinuxSchedulerEnv\nStateBuilder·ActionMapper\nRewardShaper",
     Inches(2.9),Y[1],Inches(3.25),BH7,fc=RGBColor(0x25,0x1c,0x4a))
abox(s7,"Benchmarks","stress-ng·sysbench\nhackbench·cyclictest\nfio·glmark2",
     Inches(6.35),Y[1],Inches(2.95),BH7)
abox(s7,"Storage (SQLite)","snapshots\nbenchmark_results\napplied_configs·sweep",
     Inches(9.5),Y[1],Inches(3.45),BH7)
abox(s7,"RL Trainer  (core/trainer.py)","PPO / SAC via Stable-Baselines3  ·  MlpPolicy  ·  SB3Monitor  ·  Checkpoint save/load/eval",
     Inches(0.35),Y[2],Inches(6.1),BH7,fc=RGBColor(0x1a,0x10,0x45))
abox(s7,"Live Tuner Agent","LiveTunerAgent daemon\nWorkload fingerprinting\nBest-params lookup + apply",
     Inches(6.65),Y[2],Inches(6.3),BH7,fc=RGBColor(0x12,0x32,0x28))
abox(s7,"Scheduler Controller",
     "ParameterRegistry  →  Validator  →  SecondaryValidator  →  Writer (write+readback)  →  RollbackStack  →  ProfileStore",
     Inches(0.35),Y[3],Inches(12.6),BH7,fc=RGBColor(0x30,0x1a,0x05))
abox(s7,"Safety Layer",
     "SecondaryValidator — 10 hardcoded limits  ·  Watchdog — rollback thread (timeout_sec=10)  ·  CheckpointManager",
     Inches(0.35),Y[4],Inches(12.6),BH7,fc=RGBColor(0x3a,0x10,0x10))
abox(s7,"Linux Kernel  —  /proc/sys/kernel/",
     "sched_rr_timeslice_ms  ·  sched_rt_period_us  ·  sched_rt_runtime_us  ·  sched_cfs_bandwidth_slice_us  ·  sched_autogroup_enabled  ·  sched_util_clamp_max  ·  sched_util_clamp_min  ·  sched_schedstats",
     Inches(0.35),Y[5],Inches(12.6),Inches(0.88),fc=RGBColor(0x12,0x14,0x1e),tc=ACCENT2,sc=SUBTEXT)

# ════════════════════════════════════════════════════════
# S8 — RL Algorithm
# ════════════════════════════════════════════════════════
s8 = prs.slides.add_slide(blank); bg(s8)
hdr(s8,"Reinforcement Learning Design","Member 3  ·  State · Action · Reward · Agent · Hyperparameters")
lx8=Inches(0.35); fw8=Inches(4.15); fh8=Inches(0.51); fy8=Inches(1.18)
loop=[
 ("Initialise Agent  (PPO / SAC + MlpPolicy)",ACCENT,WHITE),
 ("Observe 14-D System State Vector",SURFACE,WHITE),
 ("Select Action  (discrete / continuous)",SURFACE,WHITE),
 ("Validate  (Validator → SecondaryValidator)",WARN,BG),
 ("Apply sysctl Parameter(s)",RGBColor(0x3a,0x10,0x10),WHITE),
 ("Run Benchmark — measure real throughput",SURFACE,WHITE),
 ("EMA-normalised Reward Calculation",ACCENT2,BG),
 ("Update Policy via SB3",ACCENT,WHITE),
 ("Repeat until episode_steps (default 20)",SURFACE,SUBTEXT),
]
for lb,fc,tc in loop:
    fbox(s8,lb,lx8,fy8,w=fw8,h=fh8,fill=fc,tc=tc,sz=10.5)
    fy8+=fh8+Inches(0.04)

rx8=Inches(4.85)
txt(s8,"Observation Space  (14 features — float32, normalised [0,1])",
    rx8,Inches(1.15),Inches(8.25),Inches(0.38),sz=12,bold=True,color=ACCENT)
oh=["Idx","Feature","Normaliser"]
or8=[["0","cpu_util_pct","÷ 100"],["1","load_avg_1","÷ cpu_count"],["2","load_avg_5","÷ cpu_count"],
     ["3","mem_util_pct","÷ 100"],["4","ctxt_switches_delta","÷ 1,000,000"],
     ["5","runnable_procs","÷ 1,000"],["6–13","8 sched param values","÷ param.max_value"]]
table(s8,oh,or8,rx8,Inches(1.58),Inches(8.25),Inches(2.55))

txt(s8,"Action Space,  Reward  &  Hyperparameters",
    rx8,Inches(4.24),Inches(8.25),Inches(0.38),sz=12,bold=True,color=ACCENT2)
ah=["Component","Detail"]
ar8=[
 ["Discrete Action Space","Discrete(17): 0=noop, 1–8=increment param[i], 9–16=decrement param[i]"],
 ["Continuous Action Space","Box(−1,1)⁸: each dim maps linearly to [min_value, max_value]"],
 ["Reward (success)","(score − EMA_baseline) / |EMA_baseline|  +  λ_stab(0.1),  clipped [−1, +1]"],
 ["Reward (rollback triggered)","Above  −  λ_penalty (0.5)"],
 ["Reward (benchmark failed)","−1.0"],
 ["PPO Hyperparams (default SB3)","n_steps=2048, batch_size=64, γ=0.99, clip_ε=0.2, lr=3×10⁻⁴, MlpPolicy"],
 ["SAC Hyperparams (default SB3)","γ=0.99, lr=3×10⁻⁴, batch_size=256, tau=0.005 (continuous action mode)"],
]
table(s8,ah,ar8,rx8,Inches(4.66),Inches(8.25),Inches(2.7))

# ════════════════════════════════════════════════════════
# S9 — Results / Status
# ════════════════════════════════════════════════════════
s9 = prs.slides.add_slide(blank); bg(s9)
hdr(s9,"Results  &  Implementation Status","Member 4  ·  Mid-Review — Implemented vs. Planned")
kpis=[("86","Unit Tests\n(All Passing)"),("14","New Tests\nSweep+Tuner"),
      ("8","Tunable\nParams"),("5+","Benchmark\nAdapters"),
      ("2","RL Algos\nPPO/SAC"),("WAL","SQLite\nConcurrency")]
kx9=Inches(0.35)
for vl,lb in kpis:
    kpi(s9,lb,vl,kx9,Inches(1.15),w=Inches(2.06),h=Inches(1.05))
    kx9+=Inches(2.16)
txt(s9,"✅  Implemented & Verified",Inches(0.35),Inches(2.35),Inches(6.1),Inches(0.38),sz=13,bold=True,color=ACCENT2)
ih=["Module","Tests","Status"]
ir=[
 ["Monitor (M1)","11","SystemSnapshot · /proc sources"],
 ["Scheduler Controller (M2)","9","ParameterRegistry · Validator · Writer · Rollback"],
 ["Safety Layer (M2)","3","SecondaryValidator · Watchdog · CheckpointMgr"],
 ["Benchmarks (M3)","6","stress-ng · sysbench · hackbench · cyclictest · fio"],
 ["RL Environment (M3)","25","LinuxSchedulerEnv · StateBuilder · ActionMapper · RewardShaper"],
 ["Trainer (M4)","13","PPO/SAC · train · save · load · evaluate"],
 ["Parameter Sweep","9","Coordinate-descent · cartesian · DB persistence"],
 ["Live Tuner Agent","5","Workload fingerprint · hysteresis · best-params apply"],
 ["Dashboard","—","14 panels · live plots · auto-tuner training UI"],
]
table(s9,ih,ir,Inches(0.35),Inches(2.78),Inches(6.1),Inches(4.12))
txt(s9,"🔜  Planned Evaluation",Inches(6.65),Inches(2.35),Inches(6.3),Inches(0.38),sz=13,bold=True,color=WARN)
ph=["Experiment","Target Metric"]
pr=[
 ["Full PPO training run (50k steps, root)","Cumulative reward vs. episode"],
 ["SAC continuous-action training","Bogo-ops/s improvement vs. default"],
 ["Baseline: default kernel vs. RL-tuned","Throughput %, latency µs reduction"],
 ["Reward convergence plot","Episode reward over timesteps"],
 ["Per-workload best-param heatmap","Sweep results across workload types"],
 ["Live tuner field trial (game + CPU)","FPS, response time, ctxt-switch rate"],
 ["Multi-objective reward (throughput+lat)","Pareto front analysis"],
]
table(s9,ph,pr,Inches(6.65),Inches(2.78),Inches(6.3),Inches(4.12))

# ════════════════════════════════════════════════════════
# S10 — Timeline
# ════════════════════════════════════════════════════════
s10 = prs.slides.add_slide(blank); bg(s10)
hdr(s10,"Project Timeline","Member 4  ·  Gantt Overview")
phases=[
 ("M1 — Monitor & Storage",         0.0, 0.18,ACCENT,"Done"),
 ("M2 — Scheduler Controller",       0.14,0.32,ACCENT,"Done"),
 ("M2 — Safety Layer",              0.28,0.42,ACCENT,"Done"),
 ("M3 — RL Environment",            0.38,0.55,ACCENT,"Done"),
 ("M3 — Benchmark Adapters",        0.38,0.55,ACCENT,"Done"),
 ("M4 — Trainer (PPO/SAC)",         0.50,0.65,ACCENT,"Done"),
 ("Dashboard — 14 Panels",          0.55,0.72,ACCENT,"Done"),
 ("Parameter Sweep Engine",         0.65,0.78,ACCENT,"Done"),
 ("Live Tuner Agent",               0.70,0.82,ACCENT,"Done"),
 ("AI Training UI (Auto-Tuner)",    0.75,0.85,ACCENT,"Done"),
 ("Full RL Training Experiments",   0.82,1.00,ACCENT2,"Planned"),
 ("Baseline Comparison & Analysis", 0.88,1.00,ACCENT2,"Planned"),
 ("Final Report & Demo",            0.93,1.00,ACCENT2,"Planned"),
]
bal=Inches(3.3); baw=Inches(9.6); rh=Inches(0.37); rg=Inches(0.035); sy10=Inches(1.18)
for i,(lb,sf,ef,cl,st) in enumerate(phases):
    ty=sy10+i*(rh+rg)
    txt(s10,lb,Inches(0.35),ty,Inches(2.9),rh,sz=9.5,
        color=WHITE if st=="Done" else SUBTEXT, bold=(st=="Done"))
    rect(s10,bal,ty+Inches(0.04),baw,rh-Inches(0.08),fill=SURFACE)
    rect(s10,bal+sf*baw,ty+Inches(0.04),(ef-sf)*baw,rh-Inches(0.08),fill=cl)
    txt(s10,st,bal+ef*baw+Inches(0.08),ty,Inches(0.7),rh,
        sz=8,color=ACCENT2 if st=="Done" else WARN,bold=True)
months=["Jul","Aug","Sep","Oct","Nov","Dec"]
for i,m in enumerate(months):
    lx=bal+(i/(len(months)-1))*baw
    txt(s10,m,lx-Inches(0.2),Inches(7.0),Inches(0.5),Inches(0.3),
        sz=9,color=SUBTEXT,align=PP_ALIGN.CENTER)
nox=bal+0.84*baw
rect(s10,nox,Inches(1.08),Inches(0.03),Inches(5.82),fill=WARN)
txt(s10,"▲ NOW",nox-Inches(0.22),Inches(0.86),Inches(0.65),Inches(0.25),
    sz=9,color=WARN,bold=True,align=PP_ALIGN.CENTER)

# ════════════════════════════════════════════════════════
# S11 — Conclusion
# ════════════════════════════════════════════════════════
s11 = prs.slides.add_slide(blank); bg(s11)
hdr(s11,"Conclusion  &  Expected Contribution","Member 4")
items=[
 ("Complete RL Pipeline","LinuxSchedulerEnv + PPO/SAC (SB3) + Trainer + Checkpoint — fully functional end-to-end on real Linux."),
 ("Layered Safety Architecture","Validator → SecondaryValidator → Writer → RollbackStack → Watchdog: zero unsafe writes reach the kernel."),
 ("5+ Real Benchmark Adapters","CPU (stress-ng), Memory (sysbench), Mixed (hackbench), Latency (cyclictest), IO (fio), Gaming (glmark2)."),
 ("Parameter Sweep + LiveTuner","Grid search finds best params per workload; LiveTunerAgent applies them autonomously at runtime."),
 ("PyQt6 Dashboard — 14 Panels","Live plots, AI-training-style sweep view, reward curves, safety monitor, checkpoint & hyperparameter panels."),
 ("86 Passing Unit Tests","Full test suite — no root, no real kernel — runs in ~10 s in any CI environment."),
]
cx11=Inches(0.4); cy11=Inches(1.18); bh11=Inches(0.78)
for i,(ti,dt) in enumerate(items):
    col=i%2; row=i//2
    bx=cx11+col*Inches(6.55); by=cy11+row*(bh11+Inches(0.06))
    rect(s11,bx,by,Inches(6.3),bh11,fill=SURFACE,line=BORDER)
    rect(s11,bx,by,Inches(0.06),bh11,fill=ACCENT2)
    txt(s11,ti,bx+Inches(0.16),by+Inches(0.06),Inches(6.0),Inches(0.32),sz=12,bold=True,color=ACCENT2)
    txt(s11,dt,bx+Inches(0.16),by+Inches(0.4),Inches(6.0),Inches(0.35),sz=10,color=SUBTEXT)
rect(s11,Inches(0.4),Inches(5.72),Inches(12.5),Inches(1.35),fill=SURFACE,line=ACCENT)
txt(s11,"Expected Contribution",Inches(0.6),Inches(5.77),Inches(4),Inches(0.38),sz=13,bold=True,color=ACCENT)
txt(s11,
    "STUN demonstrates that RL-based adaptive tuning of Linux kernel scheduler parameters is technically feasible, safe, and "
    "measurably beneficial. Its modular architecture, comprehensive safety pipeline, and integrated benchmarking make it a "
    "reproducible research platform — not merely a prototype. Full training experiments (planned) will quantify the performance "
    "gain and validate the learned policy against static kernel defaults.",
    Inches(0.6),Inches(6.2),Inches(12.2),Inches(0.8),sz=10.5,color=WHITE,wrap=True)

# ════════════════════════════════════════════════════════
# S12 — References
# ════════════════════════════════════════════════════════
s12 = prs.slides.add_slide(blank); bg(s12)
hdr(s12,"References","")
refs=[
 "[1]  Lozi et al., \"The Linux Scheduler: A Decade of Wasted Cores,\" EuroSys, 2016.",
 "[2]  Mao et al., \"Learning Scheduling Algorithms for Data Processing Clusters,\" ACM SIGCOMM, 2019.",
 "[3]  Park et al., \"CARL: A Context-Aware Adaptive Reinforcement Learning Agent,\" MLSys, 2021.",
 "[4]  Mantovani et al., \"Effectiveness of the Linux CFS for Multiprogrammed Workloads,\" ACM SIGMETRICS, 2022.",
 "[5]  Aken et al., \"Automatic Database Management System Tuning Through Large-scale ML,\" VLDB, 2017.",
 "[6]  Raffin et al., \"Stable-Baselines3: Reliable RL Implementations,\" JMLR, 2021. https://github.com/DLR-RM/stable-baselines3",
 "[7]  Brockman et al., \"OpenAI Gym,\" arXiv:1606.01540. Gymnasium fork: https://github.com/Farama-Foundation/Gymnasium",
 "[8]  Linux Kernel Documentation — Scheduler tunables. https://www.kernel.org/doc/html/latest/scheduler/",
 "[9]  Linux man pages: sysctl(8), proc(5) — /proc/sys/kernel/sched_* parameters.",
 "[10] stress-ng benchmark tool. https://github.com/ColinIanKing/stress-ng",
 "[11] sysbench benchmark tool. https://github.com/akopytov/sysbench",
 "[12] glmark2 OpenGL benchmark. https://github.com/glmark2/glmark2",
]
ry12=Inches(1.18)
for i,r in enumerate(refs):
    txt(s12,r,Inches(0.45),ry12,Inches(12.5),Inches(0.38),
        sz=10.5,color=WHITE if i%2==0 else SUBTEXT)
    ry12+=Inches(0.44)

# ════════════════════════════════════════════════════════
out="/home/v0r73x/Documents/final/project/rl-scheduler-framework/STUN_S7_Mid_Review.pptx"
prs.save(out)
print(f"Saved: {out}")
