import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os

IMG_DIR = "/home/v0r73x/Documents/final/project/rl-scheduler-framework/ppt_assets_v5"
os.makedirs(IMG_DIR, exist_ok=True)

def generate_before_after():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5), facecolor="white")
    
    fig.suptitle("ILLUSTRATIVE DATA — NOT MEASURED RESULTS", color="darkred", fontweight="bold")

    # Colors
    col_default = "#888888"
    col_stun_t = "#9E003E" # Crimson for Throughput
    col_stun_l = "#2E86AB" # Blue for Latency
    
    # 1. Throughput Chart
    labels = ['Default Linux\n(CFS Base)', 'STUN Agent\n(Optimised)']
    throughput = [12450, 14800]
    
    bars1 = ax1.bar(labels, throughput, color=[col_default, col_stun_t], width=0.6, edgecolor='white', lw=2)
    ax1.set_title("Throughput (Operations/sec)\n▲ Higher is Better", fontsize=13, fontweight='bold', color='#333', pad=15)
    ax1.set_ylim(0, 17500)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.grid(axis='y', alpha=0.15)
    
    # Add values on top
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, yval + 300, f"{int(yval):,} ops/s", 
                 ha='center', va='bottom', fontsize=11, fontweight='bold')
                 
    # Add improvement annotation
    ax1.annotate('+18.8% Boost!', xy=(1, 14800), xytext=(0.5, 16000),
                arrowprops=dict(facecolor=col_stun_t, arrowstyle='->', lw=2, color=col_stun_t),
                fontsize=11, fontweight='bold', color=col_stun_t, ha='center')

    # 2. Latency Chart
    latency = [15.2, 11.4]
    
    bars2 = ax2.bar(labels, latency, color=[col_default, col_stun_l], width=0.6, edgecolor='white', lw=2)
    ax2.set_title("Response Latency (ms)\n▼ Lower is Better", fontsize=13, fontweight='bold', color='#333', pad=15)
    ax2.set_ylim(0, 19)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.grid(axis='y', alpha=0.15)
    
    # Add values on top
    for bar in bars2:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, yval + 0.3, f"{yval} ms", 
                 ha='center', va='bottom', fontsize=11, fontweight='bold')
                 
    # Add improvement annotation
    ax2.annotate('-25.0% Latency!', xy=(1, 11.4), xytext=(0.5, 14.0),
                arrowprops=dict(facecolor=col_stun_l, arrowstyle='->', lw=2, color=col_stun_l),
                fontsize=11, fontweight='bold', color=col_stun_l, ha='center')

    fig.tight_layout(pad=2.0)
    p = f"{IMG_DIR}/before_after_results.png"
    fig.savefig(p, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Generated: {p}")

generate_before_after()
