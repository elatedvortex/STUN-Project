from pptx import Presentation
prs = Presentation("STUN_S7_Mid_Review.pptx")
for i, slide in enumerate(prs.slides):
    print(f"--- Slide {i+1} ---")
    for j, shape in enumerate(slide.shapes):
        if shape.has_text_frame:
            print(f"Shape {j}: {shape.text.replace(chr(10), ' | ')}")
