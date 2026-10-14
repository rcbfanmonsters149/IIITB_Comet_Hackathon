import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

os.makedirs("report_assets", exist_ok=True)

# Set global styles
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['axes.edgecolor'] = '#CBD5E1'
plt.rcParams['axes.linewidth'] = 0.8

# -------------------------------------------------------------
# 1. Architecture Flow Diagram (Figure 1)
# -------------------------------------------------------------
def make_architecture_diagram():
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 50)
    ax.axis('off')

    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#FFFFFF')

    # Top Header Banner
    ax.add_patch(plt.Rectangle((2, 43), 96, 6, facecolor='#1E3A8A', edgecolor='none', zorder=1))
    ax.text(50, 46, "MULTI-MODAL SENSOR INGESTION & EDGE ACTUATION PIPELINE", color='white', 
            fontsize=10.5, fontweight='bold', ha='center', va='center')

    # Box 1: CAM
    ax.add_patch(plt.Rectangle((4, 25), 28, 15, facecolor='#EFF6FF', edgecolor='#3B82F6', linewidth=1.5, zorder=2))
    ax.text(18, 37.5, "LAYER 1: CAM (VISION)", color='#1E40AF', fontsize=9, fontweight='bold', ha='center', va='center')
    ax.text(18, 32.5, "• YuNet Deep Face Detection\n• SFace 128-d Embeddings\n• Multi-Factor Biological Liveness\n  (Laplacian + YCrCb + Tremor)", 
            color='#1E293B', fontsize=7.2, ha='center', va='center')

    # Box 2: WIFI
    ax.add_patch(plt.Rectangle((36, 25), 28, 15, facecolor='#F0FDF4', edgecolor='#10B981', linewidth=1.5, zorder=2))
    ax.text(50, 37.5, "LAYER 2: WIFI (PROXIMITY)", color='#065F46', fontsize=9, fontweight='bold', ha='center', va='center')
    ax.text(50, 32.5, "• RSSI Signal Monitoring\n• Log-Distance Path Loss Model\n• Near-Field Threshold (<=1.0m)\n• MAC Cryptographic Binding", 
            color='#1E293B', fontsize=7.2, ha='center', va='center')

    # Box 3: AUDIO
    ax.add_patch(plt.Rectangle((68, 25), 28, 15, facecolor='#FEF3C7', edgecolor='#F59E0B', linewidth=1.5, zorder=2))
    ax.text(82, 37.5, "LAYER 3: AUDIO (ACOUSTICS)", color='#92400E', fontsize=9, fontweight='bold', ha='center', va='center')
    ax.text(82, 32.5, "• 19.0 kHz Ultrasonic Token\n• Air-Absorption Attenuation\n• SNR Threshold (>=20 dB)\n• Spoken Dynamic Challenge", 
            color='#1E293B', fontsize=7.2, ha='center', va='center')

    # Arrows down to Fusion Gateway
    for x in [18, 50, 82]:
        ax.annotate('', xy=(x, 19), xytext=(x, 25),
                    arrowprops=dict(facecolor='#64748B', edgecolor='#475569', width=1.5, headwidth=6, headlength=6))

    # Fusion Gateway Box
    ax.add_patch(plt.Rectangle((10, 10), 80, 9, facecolor='#F8FAFC', edgecolor='#475569', linewidth=1.8, linestyle='-', zorder=2))
    ax.text(50, 15.5, "SPATIAL-TEMPORAL AI FUSION GATEWAY", color='#0F172A', fontsize=9.5, fontweight='bold', ha='center', va='center')
    ax.text(50, 12.2, "Confidence Score = 0.45(Face Match) + 0.30(WiFi Proximity) + 0.25(Ultrasonic Audio) | Multi-Factor Gatekeeper", 
            color='#334155', fontsize=7.5, ha='center', va='center')

    # Arrows to Actions
    ax.annotate('', xy=(28, 6.5), xytext=(35, 10),
                arrowprops=dict(facecolor='#16A34A', edgecolor='#15803D', width=1.5, headwidth=6, headlength=6))
    ax.annotate('', xy=(72, 6.5), xytext=(65, 10),
                arrowprops=dict(facecolor='#DC2626', edgecolor='#B91C1C', width=1.5, headwidth=6, headlength=6))

    # Access Granted Box
    ax.add_patch(plt.Rectangle((6, 1), 42, 5.5, facecolor='#DCFCE7', edgecolor='#16A34A', linewidth=1.5, zorder=2))
    ax.text(27, 4.5, "ACCESS GRANTED (MCU ACTUATION)", color='#14532D', fontsize=8, fontweight='bold', ha='center', va='center')
    ax.text(27, 2.2, "Energize Relay (12V Strike) • Green LED • Success Chime", color='#166534', fontsize=7, ha='center', va='center')

    # Access Denied Box
    ax.add_patch(plt.Rectangle((52, 1), 42, 5.5, facecolor='#FEE2E2', edgecolor='#DC2626', linewidth=1.5, zorder=2))
    ax.text(73, 4.5, "ACCESS DENIED (SECURITY DEFENSE)", color='#7F1D1D', fontsize=8, fontweight='bold', ha='center', va='center')
    ax.text(73, 2.2, "Hold Lock Secure • Pulsing Red Warning LED • Security Alarm", color='#991B1B', fontsize=7, ha='center', va='center')

    plt.tight_layout()
    plt.savefig("report_assets/fig1_architecture.png", dpi=300, bbox_inches='tight')
    plt.close()

# -------------------------------------------------------------
# 2. Fusion Weights & Anti-Spoofing Sub-Weights (Figure 2)
# -------------------------------------------------------------
def make_weights_diagram():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 3.6), dpi=300)
    fig.patch.set_facecolor('#FFFFFF')

    # Fusion Weights Donut
    labels1 = ['CAM (Vision & Liveness)\n45%', 'WIFI (RF Proximity)\n30%', 'AUDIO (Ultrasonic Token)\n25%']
    sizes1 = [45, 30, 25]
    colors1 = ['#2563EB', '#10B981', '#F59E0B']
    explode1 = (0.04, 0.02, 0.02)

    wedges1, texts1 = ax1.pie(sizes1, explode=explode1, labels=labels1, colors=colors1,
                              startangle=140, textprops=dict(color="#1E293B", fontsize=8, fontweight='bold'),
                              wedgeprops=dict(width=0.45, edgecolor='white', linewidth=2))
    ax1.set_title("Overall Fusion Weights\n$S_{fused} = 0.45 S_{face} + 0.30 S_{wifi} + 0.25 S_{audio}$", 
                  fontsize=9, fontweight='bold', color='#1E3A8A', pad=8)

    # Liveness Breakdown Donut
    labels2 = ['Texture Sharpness\n(Laplacian Var) 40%', 'Color Chrominance\n(YCrCb Space) 35%', 'Micro-Motion\n(Tremor) 25%']
    sizes2 = [40, 35, 25]
    colors2 = ['#6366F1', '#EC4899', '#14B8A6']
    explode2 = (0.04, 0.02, 0.02)

    wedges2, texts2 = ax2.pie(sizes2, explode=explode2, labels=labels2, colors=colors2,
                              startangle=140, textprops=dict(color="#1E293B", fontsize=8, fontweight='bold'),
                              wedgeprops=dict(width=0.45, edgecolor='white', linewidth=2))
    ax2.set_title("Biological Liveness Sub-Weights\n$S_{live} = 0.40 S_{tex} + 0.35 S_{chroma} + 0.25 S_{motion}$", 
                  fontsize=9, fontweight='bold', color='#1E3A8A', pad=8)

    plt.tight_layout()
    plt.savefig("report_assets/fig2_weights.png", dpi=300, bbox_inches='tight')
    plt.close()

# -------------------------------------------------------------
# 3. Latency Breakdown Bar Chart (Figure 3)
# -------------------------------------------------------------
def make_latency_diagram():
    fig, ax = plt.subplots(figsize=(8.5, 3.2), dpi=300)
    fig.patch.set_facecolor('#FFFFFF')

    stages = [
        'YuNet Face Detection',
        'SFace 128-d Feature Embedding',
        'Biological Liveness Checks',
        'Wi-Fi RSSI Scanning & Model',
        'Audio Ultrasonic FFT & SNR',
        'Fusion Gate & MCU Dispatch'
    ]
    latencies = [14.2, 18.5, 4.8, 2.1, 2.4, 0.6]
    colors = ['#3B82F6', '#2563EB', '#8B5CF6', '#10B981', '#F59E0B', '#64748B']

    y_pos = np.arange(len(stages))
    bars = ax.barh(y_pos, latencies, color=colors, height=0.55, edgecolor='none')

    ax.set_yticks(y_pos)
    ax.set_yticklabels(stages, fontsize=8, fontweight='bold', color='#1E293B')
    ax.invert_yaxis()
    ax.set_xlabel('Processing Latency (Milliseconds)', fontsize=8.5, fontweight='bold', color='#1E3A8A')
    ax.set_title('End-to-End Pipeline Latency Profiling (Total: 42.6 ms)', fontsize=9.5, fontweight='bold', color='#1E3A8A', pad=10)
    ax.set_xlim(0, 24)
    ax.grid(axis='x', linestyle='--', alpha=0.5, color='#CBD5E1')

    for bar, val in zip(bars, latencies):
        ax.text(val + 0.4, bar.get_y() + bar.get_height()/2, f"{val:.1f} ms", 
                va='center', ha='left', fontsize=7.5, fontweight='bold', color='#334155')

    ax.text(18.5, 4.5, "Total Loop:\n42.6 ms\n(> 23 FPS)", bbox=dict(boxstyle="round,pad=0.4", facecolor="#DCFCE7", edgecolor="#16A34A"),
            fontsize=8, fontweight='bold', color='#15803D', ha='center')

    plt.tight_layout()
    plt.savefig("report_assets/fig3_latency.png", dpi=300, bbox_inches='tight')
    plt.close()

# -------------------------------------------------------------
# 4. Scenario Evaluation & Decision Comparison (Figure 4)
# -------------------------------------------------------------
def make_scenario_diagram():
    fig, ax = plt.subplots(figsize=(8.5, 3.2), dpi=300)
    fig.patch.set_facecolor('#FFFFFF')

    scenarios = ['Scenario 1\nNormal Authorized\nWalk-up', 
                 'Scenario 2\nPhoto Presentation\nAttack (Spoof)', 
                 'Scenario 3\nAccidental Walk-by\n(Corridor 3.8m)', 
                 'Scenario 4\nStolen Device\n(Stranger with Phone)']
    
    scores = [94.8, 49.6, 63.3, 36.9]
    bar_colors = ['#16A34A', '#DC2626', '#EAB308', '#DC2626']
    decisions = ['ACCESS_GRANTED', 'DENIED (SPOOF)', 'DENIED (FAR)', 'DENIED (STOLEN)']

    x = np.arange(len(scenarios))
    width = 0.50

    bars = ax.bar(x, scores, width=width, color=bar_colors, edgecolor='#1E293B', linewidth=0.8)

    ax.axhline(y=70.0, color='#64748B', linestyle='--', linewidth=1.2, label='Unlock Composite Threshold (70%)')

    ax.set_ylabel('Composite Multi-Modal Confidence (%)', fontsize=8.5, fontweight='bold', color='#1E3A8A')
    ax.set_title('Empirical Scenario Validation & Fusion Decision Outcomes', fontsize=9.5, fontweight='bold', color='#1E3A8A', pad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios, fontsize=7.5, fontweight='bold', color='#1E293B')
    ax.set_ylim(0, 115)
    ax.grid(axis='y', linestyle=':', alpha=0.6, color='#CBD5E1')
    ax.legend(loc='upper right', fontsize=7.5)

    for i, (bar, score, dec) in enumerate(zip(bars, scores, decisions)):
        ax.text(bar.get_x() + bar.get_width()/2, score + 2.5, f"{score:.1f}%", 
                ha='center', va='bottom', fontsize=8, fontweight='bold', color='#0F172A')
        ax.text(bar.get_x() + bar.get_width()/2, score / 2, dec,
                ha='center', va='center', fontsize=7, fontweight='bold', color='white', rotation=0)

    plt.tight_layout()
    plt.savefig("report_assets/fig4_scenarios.png", dpi=300, bbox_inches='tight')
    plt.close()

# -------------------------------------------------------------
# 5. RF Path Loss Distance Model (Figure 5)
# -------------------------------------------------------------
def make_rf_path_loss_diagram():
    fig, ax = plt.subplots(figsize=(8.5, 3.0), dpi=300)
    fig.patch.set_facecolor('#FFFFFF')

    d = np.linspace(0.2, 10.0, 300)
    tx_power = -40.0
    n = 2.4
    rssi = tx_power - 10.0 * n * np.log10(d)

    ax.plot(d, rssi, color='#1E3A8A', linewidth=2.2, label=r'Log-Distance Model: $RSSI = -40 - 24 \cdot \log_{10}(d)$')

    ax.axvspan(0.2, 1.0, color='#DCFCE7', alpha=0.6, label='Immediate Unlock Zone (d <= 1.0m, RSSI >= -48 dBm)')
    ax.axvspan(1.0, 3.5, color='#FEF3C7', alpha=0.6, label='Corridor Walk-By Zone (1.0m < d <= 3.5m)')
    ax.axvspan(3.5, 10.0, color='#FEE2E2', alpha=0.5, label='Far / Out-of-Range Zone (d > 3.5m)')

    ax.axhline(y=-48.0, color='#16A34A', linestyle='--', linewidth=1.1, label='Unlock RSSI Threshold (-48 dBm)')
    ax.axvline(x=1.0, color='#16A34A', linestyle=':', linewidth=1.1)

    ax.set_xlabel('Distance from Terminal (Meters)', fontsize=8.5, fontweight='bold', color='#1E3A8A')
    ax.set_ylabel('Received Signal Strength Indicator (dBm)', fontsize=8.5, fontweight='bold', color='#1E3A8A')
    ax.set_title('Wi-Fi RF Proximity Calibration: Log-Distance Path Loss Model', fontsize=9.5, fontweight='bold', color='#1E3A8A', pad=10)
    ax.set_xlim(0, 10)
    ax.set_ylim(-95, -30)
    ax.grid(True, linestyle=':', alpha=0.6, color='#94A3B8')
    ax.legend(loc='upper right', fontsize=7, framealpha=0.9)

    plt.tight_layout()
    plt.savefig("report_assets/fig5_rf_model.png", dpi=300, bbox_inches='tight')
    plt.close()

if __name__ == '__main__':
    print("Regenerating optimized report asset figures...")
    make_architecture_diagram()
    make_weights_diagram()
    make_latency_diagram()
    make_scenario_diagram()
    make_rf_path_loss_diagram()
    print("All report figures updated successfully in report_assets/")
