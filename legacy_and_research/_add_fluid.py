import os

base = r'c:\Users\Govardhan\Downloads\AquaVision_Final_Project\AquaVision\templates'
templates = ['register.html', 'video_prediction.html', 'gallery.html', 'batch.html', 'api_docs.html', 'about.html', 'model.html']

for f in templates:
    path = os.path.join(base, f)
    with open(path, 'r', encoding='utf-8') as fh:
        content = fh.read()
    
    old = '<div class="ocean-bg"></div>'
    new = '<div class="ocean-bg"></div>\n    <canvas id="fluidBg"></canvas>'
    
    if old in content and 'fluidBg' not in content:
        content = content.replace(old, new, 1)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(content)
        print(f'Updated: {f}')
    else:
        print(f'Skipped: {f} (already has fluidBg or no ocean-bg found)')
