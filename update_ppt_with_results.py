import shutil
import os

with open('generate_ppt_v4.py', 'r') as f:
    code = f.read()

# Replace the output file name
code = code.replace('S7_MidReview_STUN_v4.pptx', 'S7_MidReview_STUN_v5.pptx')
code = code.replace('ppt_assets_v4', 'ppt_assets_v5')

# Replace the slide_results function
new_slide_results = """
def slide_results(prs, dash_shot):
    sl = csld(prs, "Result Analysis: Before vs. After STUN", 8)
    tb(sl, Inches(0.5), Inches(1.0), Inches(12), Inches(0.3), "By allowing the RL agent to tune the parameters dynamically, we achieve significant performance gains.", SANS, Pt(14), DARK_GREY, it=True)
    
    # Insert the new Before/After graph
    img(sl, f"{IMG_DIR}/before_after_results.png", Inches(0.3), Inches(1.5), w=Inches(8.5))
    
    # Dashboard overlay
    img(sl, dash_shot, Inches(9.0), Inches(2.2), w=Inches(4.0))
    tb(sl, Inches(9.0), Inches(1.9), Inches(4.0), Inches(0.3), "Live Dashboard Interface ↓", SANS, Pt(11), CRIMSON, True, al=PP_ALIGN.CENTER)
    
    cards = [
        ("🚀 Throughput (+18.8%)", "For heavy computing tasks, the agent groups parameters efficiently to process ~2,350 more ops/sec."),
        ("⚡ Latency (-25.0%)", "For interactive tasks (like web servers), the agent shrinks time-slices, making the system respond 3.8ms faster."),
    ]
    for i, (t, b) in enumerate(cards):
        y = Inches(5.8) + (i * Inches(0.8))
        tb(sl, Inches(0.5), y, Inches(8.5), Inches(0.8), f"{t}: {b}", SANS, Pt(12), BLACK, True, wrap=True)
"""

import re
code = re.sub(r'def slide_results.*?def slide_timeline', new_slide_results + '\ndef slide_timeline', code, flags=re.DOTALL)

# Update main function call
code = code.replace('slide_results(prs, img_reward, dash_copy)', 'slide_results(prs, dash_copy)')

with open('generate_ppt_v5.py', 'w') as f:
    f.write(code)

os.system('chmod +x generate_ppt_v5.py')
os.system('./generate_ppt_v5.py')
