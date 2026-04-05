import re

with open('templates/prediction.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace UCIQE and UIQM with Entropy
pattern = re.compile(r'<div class="metric-card underwater">.*?<h4><i class="fas fa-water" style="color:var\(--green\)"></i> UCIQE.*?<div class="metric-card underwater">.*?<h4><i class="fas fa-chart-line" style="color:var\(--green\)"></i> UIQM.*?</div>\s*</div>', re.DOTALL)

entropy_card = '''<div class="metric-card underwater">
                      <h4><i class="fas fa-water" style="color:var(--green)"></i> Entropy <span style="font-size:0.5rem;opacity:0.5;font-weight:400">UNIVERSAL</span> <span class="tip-btn" tabindex="0" data-tip="Shannon Entropy (0-8 bits). Higher = richer information and detail distribution.">?</span></h4>
                      <div class="metric-row"><span class="lbl">Original</span><span class="val orig">{{ result.metrics_original.entropy }}</span></div>
                      <div class="mbar"><div class="mbar-fill" data-width="{{ [result.metrics_original.entropy * 12.5, 100] | min }}%"></div></div>
                      <div class="metric-row"><span class="lbl">Enhanced</span><span class="val enh">{{ result.metrics_enhanced.entropy }}</span></div>
                      <div class="mbar"><div class="mbar-fill" data-width="{{ [result.metrics_enhanced.entropy * 12.5, 100] | min }}%"></div></div>
                  </div>'''

content = re.sub(pattern, entropy_card, content)

# Also fix the text 
content = content.replace("12-stage adaptive pipeline + UCIQE + UIQM quality metrics", "12-stage adaptive underwater pipeline + Universal quality metrics")
content = content.replace("UCIQE + UIQM quality metrics computed", "Universal quality metrics computed")

with open('templates/prediction.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated prediction.html UI")
