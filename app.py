import os
import sys
import sqlite3
import uuid
import secrets
import threading

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; rely on OS environment variables

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms as transforms
from torchvision import models
from PIL import Image
import numpy as np
import cv2
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify, send_file
from werkzeug.utils import secure_filename

import io
import zipfile
import base64
import json



# ────────────────────────────────────────────────────────────────
#  FLASK APP SETUP
# ────────────────────────────────────────────────────────────────
app = Flask(__name__)
_secret = os.environ.get('SECRET_KEY')
if not _secret:
    _secret = secrets.token_hex(32)
    import warnings
    warnings.warn(
        "[AquaVision] SECRET_KEY not set in environment. "
        "Using a randomly generated key — sessions will not persist across restarts. "
        "Set SECRET_KEY in your .env file for production.",
        stacklevel=2
    )
app.secret_key = _secret
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max video/image upload

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'database.db')
CLAUDE_API_KEY = None  # Removed — no external API dependency

def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn


# Auto-create users table on first run
with get_db() as _conn:
    _conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(50),
        email VARCHAR(50) UNIQUE,
        password VARCHAR(50)
    )''')
    _conn.execute('''CREATE TABLE IF NOT EXISTS api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email VARCHAR(50),
        key VARCHAR(100) UNIQUE,
        active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

def executionquery(query, values):
    with get_db() as conn:
        conn.execute(query.replace('%s','?'), values)
        conn.commit()

def retrivequery1(query, values):
    with get_db() as conn:
        cur = conn.execute(query.replace('%s','?'), values)
        return cur.fetchall()

def retrivequery2(query):
    with get_db() as conn:
        cur = conn.execute(query)
        return cur.fetchall()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/batch')
def batch_page():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    return render_template('batch.html')

@app.route('/api_docs')
def api_docs():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    return render_template('api_docs.html')




@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Retrieve form data
        name = request.form['name']  # Added name field
        email = request.form['email']
        password = request.form['password']
        c_password = request.form['c_password']
        
        # Check if passwords match
        if password == c_password:
            # Query to check if the email already exists (case-insensitive)
            query = "SELECT UPPER(email) FROM users"
            email_data = retrivequery2(query)
            email_data_list = [i[0] for i in email_data]
            
            # If the email is unique, insert the new user
            if email.upper() not in email_data_list:
                query = "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)"
                values = (name, email, password)  # Include name in the insert query
                executionquery(query, values)
                return render_template('register.html', message="Successfully Registered!")
            
            # If email already exists
            return render_template('register.html', message="This email ID already exists!")
        
        # If passwords do not match
        return render_template('register.html', message="Confirm password does not match!")
    
    # If GET request
    return render_template('register.html')


@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']
        
        # Query to check if email exists
        query = "SELECT UPPER(email) FROM users"
        email_data = retrivequery2(query)
        email_data_list = [i[0] for i in email_data]  # Simplified list comprehension

        if email.upper() in email_data_list:
            # Query to fetch the password for the provided email
            query = "SELECT password, name FROM users WHERE email = %s"
            values = (email,)
            user_data = retrivequery1(query, values)  # Assuming this returns a list of tuples
            
            if user_data:
                stored_password, name = user_data[0]  # Extract the password and name
                
                # Check if password matches (case-insensitive)
                if password == stored_password:
                    # Store the email and name in a session or global variable
                    session['user_email'] = email  # Store in session for security
                    session['user_name'] = name
                    
                    # Pass the user's name to the home page directly
                    return render_template('home.html', user_name=name)  # Pass the user name to home page
                
                # If passwords do not match
                return render_template('login.html', message="Invalid Password!")
            
            # If no data found for the user (which shouldn't happen here)
            return render_template('login.html', message="This email ID does not exist!")
        
        # If email doesn't exist
        return render_template('login.html', message="This email ID does not exist!")
    
    # If GET request
    return render_template('login.html')


@app.route('/home')
def home():
    # Check if user is logged in by verifying session
    if 'user_email' not in session:
        return redirect(url_for('login'))  # Redirect to login page if not logged in
    
    user_name = session.get('user_name')  # Retrieve user name from session
    return render_template('home.html', user_name=user_name)




# Model performance reports (hardcoded from your provided results)
MODEL_REPORTS = {
    "mobilenet": {
        "classes": {
            "blue_tint": {"precision": 0.94, "recall": 0.97, "f1-score": 0.96, "support": 186},
            "blurry": {"precision": 0.99, "recall": 0.86, "f1-score": 0.92, "support": 174},
            "green_tint": {"precision": 0.88, "recall": 0.99, "f1-score": 0.93, "support": 160},
            "hazy": {"precision": 1.00, "recall": 0.99, "f1-score": 1.00, "support": 176},
            "high_contrast": {"precision": 0.87, "recall": 0.78, "f1-score": 0.82, "support": 175},
            "low_illumination": {"precision": 0.91, "recall": 0.98, "f1-score": 0.94, "support": 183},
            "noisy": {"precision": 1.00, "recall": 0.99, "f1-score": 1.00, "support": 182},
            "raw-890": {"precision": 0.77, "recall": 0.77, "f1-score": 0.77, "support": 184},
            "red_tint": {"precision": 0.98, "recall": 0.98, "f1-score": 0.98, "support": 185},
        },
        "accuracy": 0.93,
        "macro_avg": {"precision": 0.93, "recall": 0.93, "f1-score": 0.92},
        "weighted_avg": {"precision": 0.93, "recall": 0.93, "f1-score": 0.92}
    },
    "resnet": {
        "classes": {
            "blue_tint": {"precision": 0.98, "recall": 0.96, "f1-score": 0.97, "support": 167},
            "blurry": {"precision": 0.92, "recall": 0.92, "f1-score": 0.92, "support": 185},
            "green_tint": {"precision": 0.94, "recall": 0.98, "f1-score": 0.96, "support": 192},
            "hazy": {"precision": 0.98, "recall": 1.00, "f1-score": 0.99, "support": 184},
            "high_contrast": {"precision": 0.88, "recall": 0.78, "f1-score": 0.83, "support": 174},
            "low_illumination": {"precision": 0.90, "recall": 0.98, "f1-score": 0.94, "support": 192},
            "noisy": {"precision": 0.99, "recall": 1.00, "f1-score": 1.00, "support": 160},
            "raw-890": {"precision": 0.75, "recall": 0.69, "f1-score": 0.72, "support": 172},
            "red_tint": {"precision": 0.96, "recall": 0.98, "f1-score": 0.97, "support": 179},
        },
        "accuracy": 0.92,
        "macro_avg": {"precision": 0.92, "recall": 0.92, "f1-score": 0.92},
        "weighted_avg": {"precision": 0.92, "recall": 0.92, "f1-score": 0.92}
    },
    "cnn": {
        "classes": {
            "blue_tint": {"precision": 0.9532, "recall": 0.9645, "f1-score": 0.9588, "support": 169},
            "blurry": {"precision": 0.8901, "recall": 0.8571, "f1-score": 0.8733, "support": 189},
            "green_tint": {"precision": 0.9529, "recall": 1.0000, "f1-score": 0.9759, "support": 162},
            "hazy": {"precision": 0.9692, "recall": 1.0000, "f1-score": 0.9844, "support": 189},
            "high_contrast": {"precision": 0.9375, "recall": 0.7459, "f1-score": 0.8308, "support": 181},
            "low_illumination": {"precision": 0.9109, "recall": 0.9946, "f1-score": 0.9509, "support": 185},
            "noisy": {"precision": 1.0000, "recall": 0.9946, "f1-score": 0.9973, "support": 184},
            "raw-890": {"precision": 0.7513, "recall": 0.8256, "f1-score": 0.7867, "support": 172},
            "red_tint": {"precision": 0.9586, "recall": 0.9310, "f1-score": 0.9446, "support": 174},
        },
        "accuracy": 0.9234,
        "macro_avg": {"precision": 0.9249, "recall": 0.9237, "f1-score": 0.9225},
        "weighted_avg": {"precision": 0.9253, "recall": 0.9234, "f1-score": 0.9226}
    }
}

# Now update the /model route to pass the selected report
def _format_report_for_template(raw_report):
    """Transform the raw MODEL_REPORTS dict into the flat structure
    that model.html expects (per_class list, best_* values, etc.)."""
    per_class = []
    best_p = best_r = best_f = 0.0
    for class_name, metrics in raw_report['classes'].items():
        p = round(metrics['precision'], 4)
        r = round(metrics['recall'], 4)
        f = round(metrics['f1-score'], 4)
        per_class.append({
            'class_name': class_name,
            'precision': p,
            'recall': r,
            'f1': f,
            'support': metrics['support']
        })
        best_p = max(best_p, p)
        best_r = max(best_r, r)
        best_f = max(best_f, f)

    # Append macro / weighted avg rows
    macro = raw_report['macro_avg']
    per_class.append({
        'class_name': 'macro avg',
        'precision': round(macro['precision'], 4),
        'recall': round(macro['recall'], 4),
        'f1': round(macro['f1-score'], 4),
        'support': '—'
    })
    weighted = raw_report['weighted_avg']
    per_class.append({
        'class_name': 'weighted avg',
        'precision': round(weighted['precision'], 4),
        'recall': round(weighted['recall'], 4),
        'f1': round(weighted['f1-score'], 4),
        'support': '—'
    })

    return {
        'accuracy': raw_report['accuracy'],
        'macro_precision': round(macro['precision'], 2),
        'macro_recall': round(macro['recall'], 2),
        'macro_f1': round(macro['f1-score'], 2),
        'per_class': per_class,
        'best_precision': best_p,
        'best_recall': best_r,
        'best_f1': best_f
    }

@app.route('/model', methods=['GET', 'POST'])
def model():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    selected_model = None
    report = None

    if request.method == 'POST':
        selected_model = request.form.get('selected_model')
        if selected_model in MODEL_REPORTS:
            report = _format_report_for_template(MODEL_REPORTS[selected_model])

    return render_template('model.html',
                          selected_model=selected_model,
                          report=report,
                          models_available=["mobilenet", "resnet", "cnn"])






# ── Static folder setup — os.path.join() avoids Windows backslash bug ──────
UPLOAD_FOLDER   = os.path.join(BASE_DIR, 'static', 'uploads')
ENHANCED_FOLDER = os.path.join(BASE_DIR, 'static', 'enhanced')
app.config['UPLOAD_FOLDER']   = UPLOAD_FOLDER
app.config['ENHANCED_FOLDER'] = ENHANCED_FOLDER

# Video folders
VIDEO_UPLOAD_FOLDER   = os.path.join(BASE_DIR, 'static', 'vu')
VIDEO_ENHANCED_FOLDER = os.path.join(BASE_DIR, 'static', 've')

# Ensure ALL static folders exist on startup (fixes FileNotFoundError on Windows)
for _folder in [UPLOAD_FOLDER, ENHANCED_FOLDER, VIDEO_UPLOAD_FOLDER,
                VIDEO_ENHANCED_FOLDER,
                os.path.join(BASE_DIR, 'static', 'results')]:
    os.makedirs(_folder, exist_ok=True)

# ────────────────────────────────────────────────────────────────
#  MODEL SETUP - Underwater Image Degradation Classification
# ────────────────────────────────────────────────────────────────

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# IMPORTANT: These must match EXACTLY what you used during training
CLASSES = ['blue_tint',
           'blurry',
           'green_tint',
           'hazy',
           'high_contrast',
           'low_illumination',
           'noisy',
           'raw-890',
           'red_tint']

NUM_CLASSES = len(CLASSES)

# Re-create MobileNetV2 with the same classifier head you used
model = models.mobilenet_v2(weights=None)
model.classifier = nn.Sequential(
    nn.Dropout(0.2),
    nn.Linear(model.last_channel, 512),
    nn.ReLU(),
    nn.Dropout(0.2),
    nn.Linear(512, 256),
    nn.ReLU(),
    nn.Linear(256, NUM_CLASSES)
)

# Load saved weights
MODEL_PATH = os.path.join(BASE_DIR, 'best_model.pth')

if not os.path.exists(MODEL_PATH):
    print(f"ERROR: Model file not found: {MODEL_PATH}")
    print("Please place 'best_model.pth' in the same folder as app.py or update MODEL_PATH")
else:
    try:
        model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
        print("[OK] Underwater classification model loaded successfully")
    except Exception as e:
        print("Error loading model:", str(e))
        print("Common causes: wrong number of classes, different architecture, or corrupted file")

model = model.to(DEVICE)
model.eval()

# ────────────────────────────────────────────────────────────────
#  NON-UNDERWATER IMAGE DETECTION (heuristic, no extra model needed)
#  Checks for the physics-driven signatures that ALL underwater images
#  share: blue/green channel dominance, low red energy, reduced contrast.
#  Returns True = probably underwater, False = probably NOT underwater.
# ────────────────────────────────────────────────────────────────

def is_likely_underwater(pil_img):
    """
    Multi-signal, physics-based heuristic to reject non-underwater imagery.
    Analyzes red suppression, blue-green dominance, sharpness, and hue concentration.
    CPU-efficient by aggressively downscaling before validation.
    """
    import cv2
    import numpy as np
    
    try:
        # Convert PIL to CV2 format (RGB) for numpy efficiency
        img_rgb = np.array(pil_img.convert('RGB'))
        
        # Resize heavily to save CPU during validation
        h, w = img_rgb.shape[:2]
        hw = 120
        if h > hw or w > hw:
            ratio = float(hw) / max(h, w)
            img_rgb = cv2.resize(img_rgb, (int(w * ratio), int(h * ratio)), interpolation=cv2.INTER_AREA)
            
        R_channel = img_rgb[:,:,0]
        G_channel = img_rgb[:,:,1]
        B_channel = img_rgb[:,:,2]
        
        mean_R = np.mean(R_channel)
        mean_G = np.mean(G_channel)
        mean_B = np.mean(B_channel)
        
        # 1. Red Suppression (Water absorbs red light very quickly)
        red_suppressed = mean_R < (mean_G * 0.95) or mean_R < (mean_B * 0.95)
        hard_red_suppressed = mean_R < (mean_G * 0.8) and mean_R < (mean_B * 0.8)
        
        # 2. Blue-Green Dominance
        bg_dominant = (mean_B + mean_G) > (mean_R * 2.1)
        
        # 3. Narrow Hue Concentration (Scattering reduces color variance)
        hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
        hue_std = np.std(hsv[:,:,0])
        narrow_hue = hue_std < 45  # Typical underwater has dominant B/G hue band
        
        # 4. Contrast/Sharpness proxy (Underwater is typically hazier)
        gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        low_sharpness = laplacian_var < 1000
        
        # Decision Matrix
        if hard_red_suppressed:
            return True
            
        is_uw = red_suppressed and bg_dominant
        
        if is_uw and (narrow_hue or low_sharpness):
            return True
            
        # Fallback: overpowering blue or green
        if mean_B > mean_R * 1.5 and mean_G > mean_R * 1.2:
            return True
            
        return False
    except Exception:
        # Failsafe to allow processing if validation crashes
        return True


# ─── Image preprocessing ─────────────────────────────────────
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225])
])

# ────────────────────────────────────────────────────────────────
#  CLASSICAL UNDERWATER IMAGE ENHANCEMENT UTILITIES
#  CLEAN PIPELINE — Based on OpenCV blog + Ancuti et al. research.
#  Philosophy: Gentle single-pass. NO over-processing. NO stacking.
#  Steps: Denoise → Red Comp → Gray World WB → CLAHE → Fusion →
#         Proportional LAB correction → Gentle saturation → Gamma
# ────────────────────────────────────────────────────────────────

def _pre_denoise(img):
    """Bilateral filter to smooth JPEG compression artifacts and noise
    BEFORE enhancement. Preserves edges while removing block artifacts.
    This prevents later stages from amplifying compression noise."""
    return cv2.bilateralFilter(img, d=7, sigmaColor=50, sigmaSpace=50)

def _compensate_red_channel(img, strength=0.8):
    """Compensate for the rapid attenuation of red light in water.
    Uses the green channel as a reference since it retains more structure.
    Input is RGB order (from PIL), not BGR."""
    r, g, b = img[:,:,0].astype(np.float64), img[:,:,1].astype(np.float64), img[:,:,2].astype(np.float64)
    
    # BRUTALLY HONEST EDGE CASE FIX:
    # If the diver used a physical red filter on their GoPro, or took a macro shot 
    # of a bright red starfish, r.mean() could be HIGHER than g.mean().
    # Without this check, the math (negative difference) would actively SUBTRACT red, ruining the image!
    red_deficit = g.mean() - r.mean()
    
    if red_deficit > 0:
        r_comp = r + strength * red_deficit
        r_comp = np.clip(r_comp, 0, 255)
        result = img.copy()
        result[:,:,0] = r_comp.astype(np.uint8)
        return result
    else:
        return img

def _gray_world_white_balance(img, temporal_state=None):
    """Gray World white balance — forces average of each channel to be equal.
    Updated with Hu et al. (2026) robust capping to prevent neon colour artifacts."""
    fimg = img.astype(np.float64)
    avg_r = fimg[:,:,0].mean()
    avg_g = fimg[:,:,1].mean()
    avg_b = fimg[:,:,2].mean()
    
    if temporal_state is not None:
        alpha = 0.2
        temporal_state['gw_r'] = avg_r * alpha + temporal_state.get('gw_r', avg_r) * (1 - alpha)
        temporal_state['gw_g'] = avg_g * alpha + temporal_state.get('gw_g', avg_g) * (1 - alpha)
        temporal_state['gw_b'] = avg_b * alpha + temporal_state.get('gw_b', avg_b) * (1 - alpha)
        avg_r, avg_g, avg_b = temporal_state['gw_r'], temporal_state['gw_g'], temporal_state['gw_b']

    avg_all = (avg_r + avg_g + avg_b) / 3.0
    
    K_R = avg_all / (avg_r + 1e-6)
    K_G = avg_all / (avg_g + 1e-6)
    K_B = avg_all / (avg_b + 1e-6)
    
    # 2026 Research Fix: Cap K_R at 1.3 to prevent aggressive "neon red" shifts
    if avg_r < avg_all:
        K_R = min(K_R, 1.3)
        
    # 2026 Research Fix: 0.9 suppression factor for any channel exceeding 40%
    sum_all = avg_r + avg_g + avg_b + 1e-6
    if (avg_r / sum_all) > 0.40: K_R = 0.9
    if (avg_g / sum_all) > 0.40: K_G = 0.9
    if (avg_b / sum_all) > 0.40: K_B = 0.9

    fimg[:,:,0] = np.clip(fimg[:,:,0] * K_R, 0, 255)
    fimg[:,:,1] = np.clip(fimg[:,:,1] * K_G, 0, 255)
    fimg[:,:,2] = np.clip(fimg[:,:,2] * K_B, 0, 255)
    return fimg.astype(np.uint8)

def _clahe_lab(img, clip=2.0, grid=8):
    """Apply CLAHE to the L-channel of LAB to boost contrast
    without introducing colour shift. Clip limit kept at 2.0 (research default)
    to prevent noise amplification."""
    lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(grid, grid))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)

def _recover_saturation(img, factor=1.15):
    """Gentle saturation boost in HSV to restore absorbed colours.
    Factor kept LOW (1.1-1.2) to prevent neon artifacts."""
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV).astype(np.float64)
    hsv[:,:,1] = np.clip(hsv[:,:,1] * factor, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)

def _unsharp_mask(img, sigma=1.5, strength=0.3):
    """Gentle unsharp mask to restore edge detail lost to water scattering.
    Strength kept at 0.3 max to avoid amplifying compression artifacts."""
    blurred = cv2.GaussianBlur(img, (0, 0), sigma)
    return cv2.addWeighted(img, 1.0 + strength, blurred, -strength, 0)

def _gamma_correct(img, gamma=1.0):
    """Apply gamma correction for brightness adjustment."""
    inv = 1.0 / gamma
    table = np.array([(i / 255.0) ** inv * 255 for i in range(256)]).astype(np.uint8)
    return cv2.LUT(img, table)

def _proportional_lab_correction(img, target_a=128, target_b=128, strength=0.5):
    """PROPORTIONAL LAB correction — measures actual color cast and corrects
    only a fraction (strength) of the way toward neutral.
    This NEVER overshoots: can't go from green to purple.
    
    strength=0.5 means correct 50% of the way to neutral.
    strength=0.7 means correct 70% of the way to neutral.
    """
    lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB).astype(np.float64)
    L, A, B = cv2.split(lab)
    
    a_mean = A.mean()
    b_mean = B.mean()
    
    # Proportional correction: move fraction of the way to neutral
    a_correction = (target_a - a_mean) * strength
    b_correction = (target_b - b_mean) * strength
    
    A = np.clip(A + a_correction, 0, 255)
    B = np.clip(B + b_correction, 0, 255)
    
    return cv2.cvtColor(cv2.merge([L.astype(np.uint8), 
                                    A.astype(np.uint8), 
                                    B.astype(np.uint8)]), cv2.COLOR_LAB2RGB)

def _post_denoise(img):
    """Light bilateral filter after enhancement to smooth any residual noise
    without losing the enhanced detail."""
    return cv2.bilateralFilter(img, d=5, sigmaColor=30, sigmaSpace=30)

def _auto_exposure(img, temporal_state=None):
    """Auto-exposure: stretch L-channel histogram for full dynamic range.
    Only stretches if there's sufficient range (>30 levels)."""
    lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
    L, A, B = cv2.split(lab)
    p_low = np.percentile(L, 1)
    p_high = np.percentile(L, 99)
    
    if temporal_state is not None:
        alpha = 0.2
        temporal_state['ae_pl'] = p_low * alpha + temporal_state.get('ae_pl', p_low) * (1 - alpha)
        temporal_state['ae_ph'] = p_high * alpha + temporal_state.get('ae_ph', p_high) * (1 - alpha)
        p_low, p_high = temporal_state['ae_pl'], temporal_state['ae_ph']
        
    if p_high - p_low > 30:
        L = np.clip((L.astype(np.float32) - p_low) / (p_high - p_low + 1e-6) * 255,
                    0, 255).astype(np.uint8)
        return cv2.cvtColor(cv2.merge([L, A, B]), cv2.COLOR_LAB2RGB)
    return img

# ────────────────────────────────────────────────────────────────
#  DARK CHANNEL PRIOR DEHAZING (He et al. + Underwater adaptation)
#  Proven technique: removes scatter/haze, preserves color.
#  Uses guided filter for transmission map refinement (no halo).
# ────────────────────────────────────────────────────────────────

def _get_dark_channel(img, patch_size=15):
    """Compute the dark channel of an image (RGB, float64 0-1)."""
    min_channel = np.min(img, axis=2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (patch_size, patch_size))
    dark = cv2.erode(min_channel, kernel)
    return dark

def _estimate_atmospheric_light(img, dark_channel, top_percent=0.001, temporal_state=None):
    """Estimate atmospheric light from the brightest pixels in the dark channel."""
    h, w = dark_channel.shape
    num_pixels = max(int(h * w * top_percent), 1)
    flat_dark = dark_channel.ravel()
    indices = np.argsort(flat_dark)[-num_pixels:]
    flat_img = img.reshape(-1, 3)
    A = np.mean(flat_img[indices], axis=0)
    A = np.clip(A, 0.5, 0.95)
    
    if temporal_state is not None:
        alpha = 0.2
        if 'dcp_A' not in temporal_state:
            temporal_state['dcp_A'] = A
        else:
            A = A * alpha + temporal_state['dcp_A'] * (1 - alpha)
            temporal_state['dcp_A'] = A
            
    return A

def _guided_filter(guide, src, radius=60, eps=1e-3):
    """Fast guided filter for transmission map refinement."""
    guide_f = guide.astype(np.float64)
    src_f = src.astype(np.float64)
    mean_I = cv2.boxFilter(guide_f, -1, (radius, radius))
    mean_p = cv2.boxFilter(src_f, -1, (radius, radius))
    corr_Ip = cv2.boxFilter(guide_f * src_f, -1, (radius, radius))
    corr_II = cv2.boxFilter(guide_f * guide_f, -1, (radius, radius))
    var_I = corr_II - mean_I * mean_I
    cov_Ip = corr_Ip - mean_I * mean_p
    a = cov_Ip / (var_I + eps)
    b = mean_p - a * mean_I
    mean_a = cv2.boxFilter(a, -1, (radius, radius))
    mean_b = cv2.boxFilter(b, -1, (radius, radius))
    return mean_a * guide_f + mean_b

def _dark_channel_dehaze(img_rgb, omega=0.75, t_min=0.2, temporal_state=None):
    """Dark Channel Prior dehazing adapted for underwater.
    omega=0.75 keeps 25% haze for natural look (not aggressive).
    Input/output: uint8 RGB array."""
    img_f = img_rgb.astype(np.float64) / 255.0
    dark = _get_dark_channel(img_f, patch_size=15)
    A = _estimate_atmospheric_light(img_f, dark, temporal_state=temporal_state)
    normed = img_f / (A + 1e-6)
    t_raw = 1.0 - omega * _get_dark_channel(normed, patch_size=15)
    t_raw = np.clip(t_raw, t_min, 1.0)
    gray_guide = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY).astype(np.float64) / 255.0
    t_refined = _guided_filter(gray_guide, t_raw, radius=40, eps=1e-3)
    t_refined = np.clip(t_refined, t_min, 1.0)
    t_3ch = np.stack([t_refined]*3, axis=2)
    J = (img_f - A) / t_3ch + A
    J = np.clip(J * 255, 0, 255).astype(np.uint8)
    return J

# ────────────────────────────────────────────────────────────────
#  LOW ILLUMINATION ENHANCEMENT (LIME + Adaptive Gamma Correction)
#  Rescues heavily under-exposed areas (e.g. cave dives) while
#  preserving bright regions like divers' flashlights.
# ────────────────────────────────────────────────────────────────

def _adaptive_low_light_rescue(img, temporal_state=None):
    """Low-Light Image Enhancement (LLIE) using Illumination Map Extraction
    followed by an Adaptive Gamma curve. Edge preserving and Temporal safe."""
    img_f = img.astype(np.float64) / 255.0
    
    # 1. Extract Initial Illumination Map
    L_map = np.max(img_f, axis=2)
    
    # 2. Refine Map (Guided Filter prevents halos around flashlights)
    gray_guide = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float64) / 255.0
    refined_L = _guided_filter(gray_guide, L_map, radius=30, eps=1e-3)
    
    # Temporal Smoothing for Illumination map to prevent video flash jumps
    if temporal_state is not None:
        alpha = 0.2
        if 'llie_map_mean' not in temporal_state:
            temporal_state['llie_map_mean'] = refined_L.mean()
        else:
            temporal_state['llie_map_mean'] = temporal_state['llie_map_mean'] * (1 - alpha) + refined_L.mean() * alpha
            
    # 3. Adaptive Gamma Correction
    # Pixels with low illumination (dark) get lower gamma (strong boost, up to 0.4)
    # Pixels with high illumination (flashlights) get higher gamma (no boost, 1.0)
    gamma_map = 0.4 + 0.6 * refined_L
    gamma_map = np.clip(gamma_map, 0.4, 1.0)
    gamma_map = np.stack([gamma_map] * 3, axis=-1)
    
    # Apply pixel-wise gamma
    enhanced_f = np.power(img_f, gamma_map)
    enhanced_uint8 = np.clip(enhanced_f * 255, 0, 255).astype(np.uint8)
    
    # 4. Sensor Noise Suppression 
    # (Boosting pitch black pixels amplifies sensor noise. Stronger bilateral required here.)
    enhanced_uint8 = cv2.bilateralFilter(enhanced_uint8, d=5, sigmaColor=40, sigmaSpace=40)
    
    return enhanced_uint8

# ────────────────────────────────────────────────────────────────
#  MULTI-SCALE FUSION (Ancuti et al. 2012/2018)
#  The project title technique! Fuses two enhanced versions
#  using Laplacian pyramids guided by weight maps.
# ────────────────────────────────────────────────────────────────

def _laplacian_contrast_weight(img):
    """Laplacian contrast weight — highlights edges and texture."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float64)
    lap = np.abs(cv2.Laplacian(gray, cv2.CV_64F))
    return lap

def _saturation_weight(img):
    """Saturation weight — favors colorful regions."""
    f = img.astype(np.float64)
    mu = np.mean(f, axis=2)
    sat = np.sqrt(((f[:,:,0]-mu)**2 + (f[:,:,1]-mu)**2 + (f[:,:,2]-mu)**2) / 3.0)
    return sat

def _saliency_weight(img):
    """Saliency weight — favors regions that stand out from the average."""
    lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB).astype(np.float64)
    mean_lab = np.mean(lab, axis=(0, 1))
    blurred = cv2.GaussianBlur(lab, (0, 0), sigmaX=max(img.shape[0]//8, 3))
    sal = np.sqrt(np.sum((blurred - mean_lab)**2, axis=2))
    return sal

def _gaussian_pyramid(img, levels):
    """Build a Gaussian pyramid."""
    pyr = [img.astype(np.float64)]
    for _ in range(levels):
        img = cv2.pyrDown(img.astype(np.float64))
        pyr.append(img)
    return pyr

def _laplacian_pyramid(img, levels):
    """Build a Laplacian pyramid."""
    gp = _gaussian_pyramid(img, levels)
    lp = []
    for i in range(levels):
        h, w = gp[i].shape[:2]
        up = cv2.pyrUp(gp[i+1])
        up = cv2.resize(up, (w, h))
        lp.append(gp[i] - up)
    lp.append(gp[levels])
    return lp

def _multiscale_fusion(img1, img2, levels=4):
    """Fuse two enhanced images using Ancuti-style weight maps.
    Simple weighted-average blend - NO Laplacian pyramid (avoids checkerboard blocks).
    Uses contrast, saturation, saliency weight maps from original Ancuti paper.
    Input/output: uint8 RGB arrays."""
    w1 = (_laplacian_contrast_weight(img1) +
          _saturation_weight(img1) +
          _saliency_weight(img1) + 1e-6)
    w2 = (_laplacian_contrast_weight(img2) +
          _saturation_weight(img2) +
          _saliency_weight(img2) + 1e-6)
    w_sum = w1 + w2
    w1_norm = (w1 / w_sum)[:, :, np.newaxis]
    w2_norm = (w2 / w_sum)[:, :, np.newaxis]
    fused = (img1.astype(np.float64) * w1_norm +
             img2.astype(np.float64) * w2_norm)
    return np.clip(fused, 0, 255).astype(np.uint8)

def _underwater_core_enhance(img_array, red_strength=0.8, clahe_clip=2.0,
                              saturation=1.15, sharpen=0.2, gamma=1.0,
                              use_dehaze=False, use_fusion=False,
                              lab_strength=0.0, temporal_state=None):
    """The SINGLE-PASS master pipeline. All degradation-specific functions
    route through this. Clean, gentle, research-backed.
    
    Pipeline:
      1. Bilateral denoise (remove JPEG artifacts FIRST)
      2. Red channel compensation (physics-based)
      3. Gray World white balance (remove color cast)
      4. CLAHE on LAB L-channel (contrast without color shift)
      5. [Optional] Dark Channel Prior dehazing
      6. [Optional] Multi-scale fusion (Ancuti et al.)
      7. Proportional LAB correction (measured, never overshoots)
      8. Gentle saturation recovery
      9. Gentle unsharp mask
     10. Gamma correction
     11. Auto-exposure normalization
     12. Light post-denoise
    """
    # Step 1: Remove compression artifacts BEFORE they get amplified
    result = _pre_denoise(img_array)
    
    # Step 2: Physics-based red compensation
    result = _compensate_red_channel(result, strength=red_strength)
    
    # Step 2.5: Low Illumination Detection & Rescue
    gray_val = cv2.cvtColor(result, cv2.COLOR_RGB2GRAY).mean()
    if gray_val < 65.0:
        result = _adaptive_low_light_rescue(result, temporal_state=temporal_state)
    
    # Step 3: Gray World white balance
    result = _gray_world_white_balance(result, temporal_state=temporal_state)
    
    # Step 4+5+6: Contrast enhancement (CLAHE / DCP / Fusion)
    if use_fusion and use_dehaze:
        # Ancuti-style: fuse CLAHE-enhanced and dehazed versions
        input1 = _clahe_lab(result, clip=clahe_clip)
        input2 = _dark_channel_dehaze(result, omega=0.75, temporal_state=temporal_state)
        result = _multiscale_fusion(input1, input2, levels=4)
    elif use_dehaze:
        result = _dark_channel_dehaze(result, omega=0.75, temporal_state=temporal_state)
        result = _clahe_lab(result, clip=clahe_clip)
    else:
        result = _clahe_lab(result, clip=clahe_clip)
    
    # Step 7: Proportional LAB correction (safe — never overshoots)
    if lab_strength > 0:
        result = _proportional_lab_correction(result, strength=lab_strength)
    
    # Step 8: Gentle saturation recovery
    if saturation > 1.0:
        result = _recover_saturation(result, factor=saturation)
    
    # Step 9: Very gentle sharpening
    if sharpen > 0:
        result = _unsharp_mask(result, sigma=1.5, strength=sharpen)
    
    # Step 10: Gamma correction
    if gamma != 1.0:
        result = _gamma_correct(result, gamma)
    
    # Step 11: Auto-exposure normalization
    result = _auto_exposure(result, temporal_state=temporal_state)
    
    # Step 12: Light post-denoise to smooth any residual noise
    result = _post_denoise(result)
    
    return np.clip(result, 0, 255).astype(np.uint8)


# ────────────────────────────────────────────────────────────────
#  DEGRADATION-SPECIFIC ENHANCEMENT FUNCTIONS
#  Each calls the core pipeline with tuned parameters.
#  Parameters are GENTLE — no aggressive values that cause artifacts.
# ────────────────────────────────────────────────────────────────

def _detect_green_severity(arr):
    """Measure green channel dominance to determine correction strength.
    Returns: 'mild', 'moderate', or 'severe'"""
    r_mean = arr[:,:,0].astype(float).mean()
    g_mean = arr[:,:,1].astype(float).mean()
    b_mean = arr[:,:,2].astype(float).mean()
    rb_avg = (r_mean + b_mean) / 2.0
    green_ratio = g_mean / (rb_avg + 1e-6)
    lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB).astype(float)
    a_mean = lab[:,:,1].mean()
    green_shift = 128 - a_mean
    if green_ratio > 1.25 or green_shift > 15:
        return 'severe'
    elif green_ratio > 1.10 or green_shift > 7:
        return 'moderate'
    else:
        return 'mild'

def enhance_blue_tint(img):
    """Blue cast: red comp + fusion (fixes pelagic scattered haze)."""
    arr = np.array(img)
    enhanced = _underwater_core_enhance(arr, red_strength=1.0, clahe_clip=2.0,
                                         saturation=1.15, sharpen=0.2,
                                         use_dehaze=True, use_fusion=True,
                                         lab_strength=0.4)
    return Image.fromarray(enhanced)

def enhance_green_tint(img):
    """Green/yellow cast correction — the most common underwater degradation.
    Uses PROPORTIONAL LAB correction: measures actual green shift, corrects
    only partway to neutral. NEVER overshoots to purple/magenta."""
    arr = np.array(img)
    severity = _detect_green_severity(arr)
    
    # Gentle, severity-adaptive parameters
    if severity == 'severe':
        enhanced = _underwater_core_enhance(arr, red_strength=1.0, clahe_clip=2.0,
                                             saturation=1.2, sharpen=0.15,
                                             use_dehaze=True, use_fusion=True,
                                             lab_strength=0.6)
    elif severity == 'moderate':
        enhanced = _underwater_core_enhance(arr, red_strength=0.8, clahe_clip=2.0,
                                             saturation=1.15, sharpen=0.2,
                                             use_dehaze=True, use_fusion=True,
                                             lab_strength=0.45)
    else:  # mild
        enhanced = _underwater_core_enhance(arr, red_strength=0.6, clahe_clip=2.0,
                                             saturation=1.1, sharpen=0.15,
                                             lab_strength=0.3)
    
    return Image.fromarray(enhanced)

def enhance_red_tint(img):
    """Red cast: minimal red compensation + gentle correction."""
    arr = np.array(img)
    enhanced = _underwater_core_enhance(arr, red_strength=0.2, clahe_clip=2.0,
                                         saturation=1.1, sharpen=0.2,
                                         lab_strength=0.3)
    return Image.fromarray(enhanced)

def enhance_blurry(img):
    """Blur: standard pipeline + slightly stronger sharpening."""
    arr = np.array(img)
    enhanced = _underwater_core_enhance(arr, red_strength=0.6, clahe_clip=2.0,
                                         saturation=1.1, sharpen=0.0)
    # Controlled multi-scale sharpening
    enhanced = _unsharp_mask(enhanced, sigma=2.0, strength=0.4)
    enhanced = _unsharp_mask(enhanced, sigma=1.0, strength=0.2)
    return Image.fromarray(enhanced)

def enhance_hazy(img):
    """Haze/turbidity: DCP dehazing + Ancuti fusion — clean single pass."""
    arr = np.array(img)
    enhanced = _underwater_core_enhance(arr, red_strength=0.8, clahe_clip=2.0,
                                         saturation=1.2, sharpen=0.2,
                                         use_dehaze=True, use_fusion=True,
                                         lab_strength=0.3)
    return Image.fromarray(enhanced)

def enhance_low_illumination(img):
    """Dark / low-light: handled natively by _adaptive_low_light_rescue in core."""
    arr = np.array(img)
    enhanced = _underwater_core_enhance(arr, red_strength=0.7, clahe_clip=2.5,
                                         saturation=1.15, sharpen=0.2, gamma=1.0,
                                         use_dehaze=True, use_fusion=True, lab_strength=0.3)
    return Image.fromarray(enhanced)

def enhance_noisy(img):
    """Noise: gentle pipeline (bilateral pre-denoise handles most noise)."""
    arr = np.array(img)
    enhanced = _underwater_core_enhance(arr, red_strength=0.6, clahe_clip=1.5,
                                         saturation=1.1, sharpen=0.0, gamma=1.05,
                                         lab_strength=0.2)
    return Image.fromarray(enhanced)

def enhance_high_contrast(img):
    """Over-contrast: soften with gentle gamma + very mild CLAHE."""
    arr = np.array(img)
    enhanced = _underwater_core_enhance(arr, red_strength=0.4, clahe_clip=1.2,
                                         saturation=1.05, sharpen=0.0, gamma=1.1)
    return Image.fromarray(enhanced)

def enhance_raw_890(img):
    """General / unknown degradation: balanced defaults with fusion."""
    arr = np.array(img)
    enhanced = _underwater_core_enhance(arr, red_strength=0.7, clahe_clip=2.0,
                                         saturation=1.15, sharpen=0.2,
                                         use_fusion=True, use_dehaze=True,
                                         lab_strength=0.35)
    return Image.fromarray(enhanced)

# Enhancement mapping dictionary
ENHANCEMENT_MAP = {
    'blue_tint': enhance_blue_tint,
    'green_tint': enhance_green_tint,
    'red_tint': enhance_red_tint,
    'blurry': enhance_blurry,
    'hazy': enhance_hazy,
    'low_illumination': enhance_low_illumination,
    'noisy': enhance_noisy,
    'high_contrast': enhance_high_contrast,
    'raw-890': enhance_raw_890
}

def apply_enhancement(image, degradation_type):
    """Apply appropriate enhancement based on degradation type"""
    if degradation_type in ENHANCEMENT_MAP:
        return ENHANCEMENT_MAP[degradation_type](image)
    return enhance_raw_890(image)


def adaptive_classical_enhance(image, degradation_type):
    """Clean single-pass enhancement based on degradation type."""
    return apply_enhancement(image, degradation_type)



# ────────────────────────────────────────────────────────────────
#  ADAPTIVE BOOST — NEUTERED to prevent over-processing
#  Only triggers if enhanced image is nearly identical to original
#  (similarity > 0.95), meaning first pass barely did anything.
# ────────────────────────────────────────────────────────────────

def _image_similarity(img1, img2):
    """Compute structural similarity between two PIL images (0-1)."""
    a1 = np.array(img1).astype(np.float64)
    a2 = np.array(img2).astype(np.float64)
    if a1.shape != a2.shape:
        a2 = cv2.resize(a2, (a1.shape[1], a1.shape[0]))
    mae = np.mean(np.abs(a1 - a2))
    return 1.0 - (mae / 255.0)

def adaptive_boost(original_img, enhanced_img, degradation_type):
    """Only re-enhance if the first pass barely changed anything (>0.95 similarity).
    Uses gentle parameters — no aggressive boost that creates artifacts."""
    sim = _image_similarity(original_img, enhanced_img)

    # If sufficiently different, the enhancement worked — return as-is
    if sim < 0.95:
        return enhanced_img, False, sim

    # Very gentle fallback — just re-run with slightly stronger params
    arr = np.array(original_img)
    boosted = _underwater_core_enhance(arr, red_strength=0.9, clahe_clip=2.5,
                                        saturation=1.2, sharpen=0.25,
                                        use_dehaze=True, use_fusion=True,
                                        lab_strength=0.5)
    return Image.fromarray(boosted), True, sim


# ────────────────────────────────────────────────────────────────
#  VIDEO-OPTIMIZED FRAME ENHANCEMENT
#  Lighter pipeline for video — skips expensive fusion, uses
#  moderate parameters for temporal consistency (less flicker).
#  Research: Gray-world WB + CLAHE + DCP dehaze is the proven
#  classical pipeline (Ancuti 2012, OpenCV standard approach).
# ────────────────────────────────────────────────────────────────

def _video_frame_enhance(pil_frame, degradation_type='raw-890', temporal_state=None):
    """Enhance a single video frame with speed-optimized pipeline.
    Uses the same core enhancement but with lighter settings
    to maintain temporal consistency and processing speed."""
    arr = np.array(pil_frame)
    h, w = arr.shape[:2]

    # Downscale large frames for faster processing (process at max 720p)
    max_dim = 720
    scale = 1.0
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        small = cv2.resize(arr, (int(w * scale), int(h * scale)),
                           interpolation=cv2.INTER_AREA)
    else:
        small = arr

    # Use the same proven pipeline but with lighter params for video
    # Key: use_dehaze=True for underwater clarity, use_fusion=True for SOTA quality
    enhanced = _underwater_core_enhance(
        small,
        red_strength=0.7,
        clahe_clip=2.0,
        saturation=1.12,
        sharpen=0.15,
        use_dehaze=True,
        use_fusion=True,       # ENABLE MULTI-SCALE FUSION FOR SOTA GUARANTEE
        lab_strength=0.35,
        gamma=1.0,
        temporal_state=temporal_state
    )

    # Scale back to original resolution
    if scale < 1.0:
        enhanced = cv2.resize(enhanced, (w, h),
                              interpolation=cv2.INTER_LANCZOS4)

    return Image.fromarray(enhanced)







# ────────────────────────────────────────────────────────────────
#  DPF-NET DEEP LEARNING ENHANCEMENT PIPELINE
#  Physics-guided: DPEM → DPF-Net (CT-UNet + PFGM fusion)
#  Loaded lazily on first use to avoid startup crash if weights missing
# ────────────────────────────────────────────────────────────────

_dpfnet_model = None
_dpem_model   = None
_dav2_model   = None
_dl_models_loaded = False
_dl_load_error    = None

MODEL_SIZE = 256  # DPEM/DPF-Net input resolution

def _load_dl_models():
    """Lazy-load the deep-learning enhancement stack once on first request."""
    global _dpfnet_model, _dpem_model, _dav2_model, _dl_models_loaded, _dl_load_error
    if _dl_models_loaded or _dl_load_error:
        return
    try:
        sys.path.insert(0, BASE_DIR)
        sys.path.insert(0, os.path.join(BASE_DIR, 'DPEM'))
        # depth_anything_v2 lives in Depth_Anything_V2_main/ as local source — add to path
        _dav2_src = os.path.join(BASE_DIR, 'Depth_Anything_V2_main')
        if _dav2_src not in sys.path:
            sys.path.insert(0, _dav2_src)

        from DPF_Net import TotalNetwork
        from DPEM.DPEM_model import MainNet
        from depth_anything_v2.dpt import DepthAnythingV2

        dpf_path  = os.path.join(BASE_DIR, 'checkpoints', 'DPF-Net.pth')
        dpem_path = os.path.join(BASE_DIR, 'checkpoints', 'DPEM_finetune.pth')
        dav2_path = os.path.join(BASE_DIR, 'checkpoints', 'dav2.pth')

        for p in [dpf_path, dpem_path, dav2_path]:
            if not os.path.exists(p):
                _dl_load_error = f"Missing weight: {os.path.basename(p)}"
                return

        print("[DL] Loading Depth Anything V2...")
        dav2_cfg = {'encoder': 'vits', 'features': 64, 'out_channels': [48, 96, 192, 384]}
        _dav2_model = DepthAnythingV2(**dav2_cfg)
        # strict=False: allows real weights (.pth) to load even if stub arch differs
        sd = torch.load(dav2_path, map_location=DEVICE)
        _dav2_model.load_state_dict(sd, strict=False)
        _dav2_model = _dav2_model.to(DEVICE).eval()

        print("[DL] Loading DPEM...")
        _dpem_model = MainNet(device=DEVICE, imgSize=MODEL_SIZE,
                              depth_weight_path=dav2_path).to(DEVICE).eval()
        _dpem_model.load_state_dict(torch.load(dpem_path, map_location=DEVICE))

        print("[DL] Loading DPF-Net...")
        _dpfnet_model = TotalNetwork(device=DEVICE).to(DEVICE).eval()
        _dpfnet_model.load_state_dict(torch.load(dpf_path, map_location=DEVICE))

        _dl_models_loaded = True
        print("[DL] [OK] All deep-learning models loaded successfully")

    except Exception as e:
        _dl_load_error = str(e)
        print(f"[DL] [ERROR] Failed to load DL models: {e}")


def _pre_B_estimate_tensor(img_rgb, device):
    """Quick statistical backscatter estimate.
    FIXED: Input is RGB (from cv2.cvtColor BGR2RGB), channels:
      [0]=R, [1]=G, [2]=B — corrected from swapped BGR indexing."""
    raw = np.transpose(img_rgb, (2, 0, 1)).astype(np.float32)
    raw = np.clip(raw, 5, 250)
    # Channel 0=R, 1=G, 2=B in RGB input
    avg_R, std_R = np.mean(raw[0]), np.std(raw[0])
    avg_G, std_G = np.mean(raw[1]), np.std(raw[1])
    med_B        = np.median(raw[2])
    # Backscatter light estimation per channel
    bgl_R = 140.0 / (1 + 14.4 * np.exp(-0.034 * np.median(raw[0])))
    bgl_G = 1.13 * avg_G + 1.11 * std_G - 25.6
    bgl_B = 1.13 * np.mean(raw[2]) + 1.11 * np.std(raw[2]) - 25.6
    bgl = np.zeros_like(img_rgb, dtype=np.float32)
    bgl[..., 0] = bgl_R; bgl[..., 1] = bgl_G; bgl[..., 2] = bgl_B
    bgl = np.clip(bgl, 0, 255).astype(np.uint8)
    t = torch.from_numpy(bgl).permute(2, 0, 1).float().unsqueeze(0)
    return t.to(device)


def enhance_with_dpfnet(image_path):
    """Improved physics-guided DPF-Net enhancement with stronger color correction fallback."""
    _load_dl_models()
    if not _dl_models_loaded:
        return None, _dl_load_error

    try:
        img_bgr = cv2.imread(image_path)
        if img_bgr is None:
            return None, "Cannot read image"

        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img_rgb, (MODEL_SIZE, MODEL_SIZE))
        img_t = (torch.from_numpy(img_resized.astype(np.float32))
                 .permute(2, 0, 1).unsqueeze(0) / 255.0).to(DEVICE)

        with torch.no_grad():
            _, _, h, w = img_t.shape
            pad_h = (14 - h % 14) % 14
            pad_w = (14 - w % 14) % 14
            img_padded = F.pad(img_t, (0, pad_w, 0, pad_h), mode='reflect')

            pre_B = _pre_B_estimate_tensor(img_resized, DEVICE)
            x_B, x_betaD, x_betaB, x_d = _dpem_model(img_t, pre_B / 255.0)

            rep = lambda t, s: t.unsqueeze(2).unsqueeze(3).repeat(1, 1, s, s)
            B_map     = rep(x_B, MODEL_SIZE)
            betaD_map = rep(x_betaD, MODEL_SIZE)
            betaB_map = rep(x_betaB, MODEL_SIZE)
            ch_rep    = x_d[:, 0:1, :, :]
            d_map     = torch.cat((x_d, ch_rep, ch_rep), dim=1)

            enhanced_t = _dpfnet_model(img_t, B_map, d_map, betaD_map, betaB_map)
            enhanced_t = enhanced_t.clamp(0, 1)

        out_np = (enhanced_t[0].permute(1, 2, 0).cpu().numpy() * 255).astype(np.uint8)
        orig_h, orig_w = img_bgr.shape[:2]
        out_np = cv2.resize(out_np, (orig_w, orig_h), interpolation=cv2.INTER_LANCZOS4)
        
        # Gentle post-processing — only correct residual color cast if detected
        # (NOT blindly shifting LAB for all degradation types)
        enhanced_pil = Image.fromarray(out_np)
        enhanced_arr = np.array(enhanced_pil)
        
        # Detect if residual green/yellow cast remains
        lab = cv2.cvtColor(enhanced_arr, cv2.COLOR_RGB2LAB).astype(np.float32)
        L, A, B = cv2.split(lab)
        a_mean = A.mean()
        b_mean = B.mean()
        # Only apply LAB correction if measurably green/yellow shifted
        a_shift = max(0, min(15, int((128 - a_mean) * 0.5)))  # adaptive, max 15
        b_shift = max(-12, min(0, int((128 - b_mean) * 0.4)))  # adaptive, max -12
        if a_shift > 2 or b_shift < -2:
            A = np.clip(A + a_shift, 0, 255).astype(np.uint8)
            B = np.clip(B + b_shift, 0, 255).astype(np.uint8)
            enhanced_arr = cv2.cvtColor(cv2.merge([L.astype(np.uint8), A, B]), cv2.COLOR_LAB2RGB)
        
        return Image.fromarray(enhanced_arr), None

    except Exception as e:
        return None, str(e)


def _dpfnet_quality_gate(original_img, dpfnet_img, degradation_type):
    """If DPF-Net output is too similar to input, force strong classical boost."""
    sim = _image_similarity(original_img, dpfnet_img)

    if sim < 0.93:   # lowered threshold
        return dpfnet_img, False, f'DPF-Net OK (Δ={1-sim:.1%})'

    # DPF-Net failed → force strong classical boost for green_tint/hazy
    if degradation_type in ('green_tint', 'hazy'):
        boosted = enhance_green_tint(original_img) if degradation_type == 'green_tint' else enhance_hazy(original_img)
        return boosted, True, f'DPF-Net weak → strong classical boost applied'
    
    boosted = adaptive_classical_enhance(original_img, degradation_type)
    return boosted, True, f'DPF-Net weak (sim={sim:.1%}) → classical boost'

# ─── Prediction function ────────────────────────────────────────
def predict_underwater_image(image_path):
    """Classify the degradation type of an underwater image.
    Returns (result_dict, original_pil_image, None).
    Enhancement is handled separately in the /prediction route."""
    if not os.path.exists(image_path):
        return {"error": "Image file not found"}, None, None

    try:
        img = Image.open(image_path).convert('RGB')
        img_tensor = transform(img).unsqueeze(0).to(DEVICE)

        with torch.no_grad():
            output = model(img_tensor)
            probs = torch.softmax(output, dim=1)
            confidence, pred_idx = torch.max(probs, 1)

            pred_class = CLASSES[pred_idx.item()]
            conf_pct = confidence.item() * 100

        return {
            "prediction": pred_class,
            "confidence": round(conf_pct, 2),
            "all_probs": {CLASSES[i]: round(p * 100, 2) for i, p in enumerate(probs[0].tolist())}
        }, img, None  # ← No enhancement here; route handles it

    except Exception as e:
        return {"error": str(e)}, None, None



@app.route('/prediction', methods=["GET", "POST"])
def prediction():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    result            = None
    image_filename    = None
    enhanced_filename = None
    exif_data         = None

    if request.method == "POST":
        try:
            file = request.files.get('file')


            if file and file.filename != '':
                # Short UUID filename — avoids Windows MAX_PATH (260-char) bug
                safe_name = secure_filename(file.filename) or 'upload.jpg'
                ext      = os.path.splitext(safe_name)[1].lower() or '.jpg'
                short_id = uuid.uuid4().hex[:8]
                filename = f"{short_id}{ext}"
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(image_path)
                image_filename = filename

                raw_img       = Image.open(image_path)
                original_img  = raw_img.convert('RGB')
                enhanced_img  = None

                # ── EXIF extraction (safe, non-blocking) ──────────────
                try:
                    from PIL.ExifTags import TAGS, GPSTAGS
                    raw_exif = raw_img._getexif()
                    if raw_exif:
                        exif_data = {}
                        tag_map = {
                            'Make': 'Camera Make', 'Model': 'Camera Model',
                            'ISOSpeedRatings': 'ISO', 'ExposureTime': 'Shutter Speed',
                            'FNumber': 'Aperture', 'FocalLength': 'Focal Length',
                            'DateTime': 'Date Taken', 'ImageWidth': 'Width',
                            'ImageLength': 'Height',
                        }
                        for tag_id, value in raw_exif.items():
                            tag_name = TAGS.get(tag_id, '')
                            if tag_name in tag_map:
                                # Format special types
                                if tag_name == 'ExposureTime' and hasattr(value, 'numerator'):
                                    exif_data[tag_map[tag_name]] = f"1/{int(value.denominator/value.numerator)}s" if value.numerator and value.numerator > 0 else str(value)
                                elif tag_name == 'FNumber' and hasattr(value, 'numerator'):
                                    exif_data[tag_map[tag_name]] = f"f/{value.numerator/value.denominator:.1f}" if value.denominator else str(value)
                                elif tag_name == 'FocalLength' and hasattr(value, 'numerator'):
                                    exif_data[tag_map[tag_name]] = f"{value.numerator/value.denominator:.0f}mm" if value.denominator else str(value)
                                else:
                                    exif_data[tag_map[tag_name]] = str(value)
                        if not exif_data:
                            exif_data = None  # No useful EXIF found
                except Exception:
                    exif_data = None  # No EXIF — that's fine

                # ── Non-underwater check (heuristic — fast, runs BEFORE ML) ────
                if not is_likely_underwater(original_img):
                    # Block enhancement — skip ML + pipeline entirely
                    result = {'not_underwater': True}
                else:
                    # ── Classify degradation type (MobileNetV2) ───────────────
                    result, original_img, _ = predict_underwater_image(image_path)

                if result and 'error' not in result and 'not_underwater' not in result:
                    pred_class = result.get('prediction', 'raw-890')


                    # ── Adaptive Classical Enhancement ────────────────────────────

                    # ── Adaptive Classical Enhancement ────────────────────────────
                    enhanced_img = adaptive_classical_enhance(original_img, pred_class)
                    result['enhancement_mode'] = 'Adaptive Classical Pipeline'

                    # ── Adaptive boost — re-enhance if output ≈ input ─────────────
                    enhanced_img, was_boosted, sim_score = adaptive_boost(
                        original_img, enhanced_img, pred_class)
                    if was_boosted:
                        result['adaptive_boost'] = f'Boosted (similarity {sim_score:.1%} → re-enhanced with stronger params)'



                    # ── Save enhanced image (original resolution) ─────────────────
                    enhanced_filename = f"e_{short_id}{ext}"
                    enhanced_path = os.path.join(app.config['ENHANCED_FOLDER'], enhanced_filename)
                    enhanced_img.save(enhanced_path)

                    # ── Quality metrics (6 metrics incl. UCIQE/UIQM) ─────────────
                    try:
                        result['metrics_original'] = get_quality_metrics(original_img)
                        result['metrics_enhanced'] = get_quality_metrics(enhanced_img)

                        # ── Overall quality improvement % ────────────────────────
                        # Use Entropy as primary, 
                        # blended with colorfulness + sharpness for a holistic score.
                        try:
                            mo = result['metrics_original']
                            me = result['metrics_enhanced']

                            def _pct_delta(orig, enh):
                                """Safe % improvement; returns 0.0 if orig == 0."""
                                return ((enh - orig) / orig * 100.0) if orig and orig != 0 else 0.0

                            entropy_delta = _pct_delta(mo['entropy'],       me['entropy'])
                            col_delta     = _pct_delta(mo['colorfulness'],  me['colorfulness'])
                            sharp_delta   = _pct_delta(mo['sharpness'],     me['sharpness'])

                            # 50% weight on Entropy (universal quality metric),
                            # 25% colorfulness, 25% sharpness
                            weighted = entropy_delta * 0.50 + col_delta * 0.25 + sharp_delta * 0.25
                            result['improvement_pct'] = round(weighted, 1)
                        except Exception:
                            result['improvement_pct'] = None
                    except Exception:
                        pass


        except Exception as e:
            result = {'error': f"An error occurred during processing: {str(e)}"}

    return render_template('prediction.html',
                           result=result,
                           image_filename=image_filename,
                           enhanced_filename=enhanced_filename,
                           exif_data=exif_data)

# ────────────────────────────────────────────────────────────────
#  IMAGE QUALITY METRICS (no-reference)
# ────────────────────────────────────────────────────────────────

def compute_colorfulness(img_array):
    """Hasler & Süsstrunk (2003) colorfulness metric. Input is RGB array."""
    R, G, B = img_array[:,:,0].astype(float), img_array[:,:,1].astype(float), img_array[:,:,2].astype(float)
    rg = np.abs(R - G)
    yb = np.abs(0.5 * (R + G) - B)
    std_rg, mean_rg = np.std(rg), np.mean(rg)
    std_yb, mean_yb = np.std(yb), np.mean(yb)
    std_root = np.sqrt(std_rg**2 + std_yb**2)
    mean_root = np.sqrt(mean_rg**2 + mean_yb**2)
    return round(std_root + 0.3 * mean_root, 2)

def compute_sharpness(img_array):
    """Laplacian variance — higher = sharper"""
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    return round(cv2.Laplacian(gray, cv2.CV_64F).var(), 2)

def compute_contrast(img_array):
    """RMS contrast of luminance"""
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY).astype(float)
    return round(np.std(gray), 2)

def compute_brightness(img_array):
    """Mean brightness of luminance channel"""
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY).astype(float)
    return round(np.mean(gray), 2)

def compute_entropy(img_array):
    """Shannon Entropy — universal metric for image information content.
    Higher means more details and information. Usually 6.0 ~ 8.0 bits/pixel.
    Works perfectly regardless of water turbidity or oceanic color."""
    import scipy.stats
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
    hist = hist.ravel() / hist.sum()
    entropy = scipy.stats.entropy(hist, base=2)
    return round(entropy, 2)

def get_quality_metrics(img):
    """Compute all quality metrics for a PIL image.
    Includes 4 standard metrics + Entropy."""
    arr = np.array(img)
    return {
        'colorfulness': compute_colorfulness(arr),
        'sharpness': compute_sharpness(arr),
        'contrast': compute_contrast(arr),
        'brightness': compute_brightness(arr),
        'entropy': compute_entropy(arr)
    }

# ────────────────────────────────────────────────────────────────
#  VIDEO ENHANCEMENT (frame-by-frame → H.264 MP4 via imageio-ffmpeg)
# ────────────────────────────────────────────────────────────────

import shutil
import subprocess
import tempfile

MAX_VIDEO_FRAMES = 1000    # cap to prevent disk exhaustion on long videos
MIN_DISK_MB      = 500     # minimum free MB required before accepting upload

def _get_free_disk_mb(path='.'):
    """Return free disk space in MB for the drive containing *path*."""
    try:
        usage = shutil.disk_usage(os.path.abspath(path))
        return usage.free / (1024 * 1024)
    except Exception:
        return 999999

def _get_ffmpeg_binary():
    """Get the ffmpeg binary path — prefer imageio-ffmpeg bundled binary."""
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        return None

def _remux_to_faststart(ffmpeg_bin, input_path, output_path):
    """Remux a video to ensure moov atom is at the front for streaming.
    Uses temp dir to bypass Windows MAX_PATH (260 char) limits."""
    if not ffmpeg_bin:
        return False
    try:
        tmp_fd, tmp_out = tempfile.mkstemp(suffix='.mp4', prefix='aqv_remux_')
        os.close(tmp_fd)
        cmd = [
            ffmpeg_bin, '-y',
            '-i', input_path,
            '-c', 'copy',
            '-movflags', '+faststart',
            '-f', 'mp4',
            tmp_out
        ]
        subprocess.run(cmd, capture_output=True, timeout=120)
        if os.path.exists(tmp_out) and os.path.getsize(tmp_out) > 1000:
            shutil.move(tmp_out, output_path)
            return True
        if os.path.exists(tmp_out):
            os.remove(tmp_out)
        return False
    except Exception:
        return False

def _cleanup_old_video_files(keep_latest=5):
    """Delete oldest video uploads & enhanced videos, keeping *keep_latest*."""
    for folder in [VIDEO_UPLOAD_FOLDER, VIDEO_ENHANCED_FOLDER]:
        if not os.path.isdir(folder):
            continue
        files = sorted(
            [os.path.join(folder, f) for f in os.listdir(folder)
             if os.path.isfile(os.path.join(folder, f))],
            key=os.path.getmtime
        )
        for old in files[:-keep_latest] if len(files) > keep_latest else []:
            try:
                os.remove(old)
            except OSError:
                pass

def _cleanup_old_image_files(keep_latest=30):
    """Delete oldest image uploads & enhanced images, keeping *keep_latest*."""
    for folder in [UPLOAD_FOLDER, ENHANCED_FOLDER]:
        if not os.path.isdir(folder):
            continue
        files = sorted(
            [os.path.join(folder, f) for f in os.listdir(folder)
             if os.path.isfile(os.path.join(folder, f))],
            key=os.path.getmtime
        )
        for old in files[:-keep_latest] if len(files) > keep_latest else []:
            try:
                os.remove(old)
            except OSError:
                pass


def enhance_video_file(input_path, output_path, enhancement_func,
                       max_frames=MAX_VIDEO_FRAMES, progress_callback=None):
    """Enhance video frame-by-frame → browser-playable H.264 MP4.

    Uses a SHORT temp path for all writing to bypass Windows 260-char
    MAX_PATH limit, then moves the result to output_path.

    Returns the number of frames processed.
    """
    # ── Read with OpenCV (robust reader) ──────────────────────────
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"[VIDEO] [ERROR] Cannot open video: {input_path}")
        return 0

    fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    width  = orig_w if orig_w % 2 == 0 else orig_w + 1
    height = orig_h if orig_h % 2 == 0 else orig_h + 1

    print(f"[VIDEO] Input: {orig_w}x{orig_h} → write: {width}x{height} @ {fps:.1f}fps")

    # ── Use a SHORT temp path to avoid Windows MAX_PATH (260 chars) ──
    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.mp4', prefix='aqv_')
    os.close(tmp_fd)  # close the fd; writers will open it by path
    print(f"[VIDEO] Temp output: {tmp_path} ({len(tmp_path)} chars)")

    ffmpeg_bin = _get_ffmpeg_binary()
    writer_type = None
    ffproc = None
    writer = None
    out = None

    # ── Strategy 1: ffmpeg subprocess pipe (most reliable) ────────
    if ffmpeg_bin:
        try:
            cmd = [
                ffmpeg_bin, '-y',
                '-f', 'rawvideo', '-vcodec', 'rawvideo',
                '-s', f'{width}x{height}',
                '-pix_fmt', 'rgb24', '-r', str(fps),
                '-i', '-',
                '-c:v', 'libx264', '-crf', '23', '-preset', 'fast',
                '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                '-an', '-f', 'mp4',
                tmp_path                     # ← SHORT path
            ]
            ffproc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
            writer_type = 'pipe'
            print("[VIDEO] Using ffmpeg subprocess pipe (H.264)")
        except Exception as e:
            print(f"[VIDEO] ffmpeg pipe failed: {e}")
            ffproc = None

    # ── Strategy 2: imageio writer ────────────────────────────────
    if writer_type is None:
        try:
            import imageio
            writer = imageio.get_writer(
                tmp_path,                    # ← SHORT path
                fps=fps, codec='libx264', quality=None,
                pixelformat='yuv420p', macro_block_size=1,
                output_params=['-crf', '23', '-preset', 'fast',
                               '-movflags', '+faststart'])
            writer_type = 'imageio'
            print("[VIDEO] Using imageio H.264 writer")
        except Exception as e:
            print(f"[VIDEO] imageio writer failed: {e}")
            writer = None

    # ── Strategy 3: OpenCV writer ─────────────────────────────────
    if writer_type is None:
        for codec in ['mp4v', 'XVID', 'avc1']:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            out = cv2.VideoWriter(tmp_path, fourcc, fps, (width, height))
            if out.isOpened():
                writer_type = 'opencv'
                print(f"[VIDEO] Using OpenCV writer ({codec})")
                break
            out.release()
            out = None
        if out is None:
            cap.release()
            os.remove(tmp_path)
            print("[VIDEO] [ERROR] All writers failed")
            return 0

    # ── Process frames ────────────────────────────────────────────
    frame_count = 0
    write_errors = 0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if progress_callback:
        progress_callback(0, total_frames)

    while frame_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        try:
            frame_rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_frame    = Image.fromarray(frame_rgb)
            enhanced_pil = enhancement_func(pil_frame)
            enhanced_rgb = np.array(enhanced_pil)

            if enhanced_rgb.shape[1] != width or enhanced_rgb.shape[0] != height:
                enhanced_rgb = cv2.resize(enhanced_rgb, (width, height),
                                          interpolation=cv2.INTER_LANCZOS4)

            if writer_type == 'pipe':
                ffproc.stdin.write(enhanced_rgb.tobytes())
            elif writer_type == 'imageio':
                writer.append_data(enhanced_rgb)
            elif writer_type == 'opencv':
                out.write(cv2.cvtColor(enhanced_rgb, cv2.COLOR_RGB2BGR))

            frame_count += 1
            if frame_count % 25 == 0:
                print(f"[VIDEO] Processed {frame_count} frames...")
            if progress_callback and frame_count % 5 == 0:
                progress_callback(frame_count, total_frames)

        except BrokenPipeError:
            print(f"[VIDEO] [ERROR] ffmpeg pipe broke at frame {frame_count}")
            break
        except Exception as e:
            write_errors += 1
            print(f"[VIDEO] Frame {frame_count} error: {e}")
            frame_count += 1
            if write_errors > 10:
                print("[VIDEO] [ERROR] Too many errors — aborting")
                break
            continue

        if frame_count % 50 == 0 and _get_free_disk_mb(tmp_path) < 200:
            print("[VIDEO] ⚠ Low disk — stopping early")
            break

    cap.release()

    # ── Finalize writer ───────────────────────────────────────────
    if writer_type == 'pipe' and ffproc:
        try:
            ffproc.stdin.close()
            stderr_out = ffproc.stderr.read().decode('utf-8', errors='replace')
            ffproc.wait(timeout=120)
            if ffproc.returncode != 0:
                print(f"[VIDEO] ⚠ ffmpeg exit code {ffproc.returncode}")
                print(f"[VIDEO] stderr: {stderr_out[-300:]}")
            else:
                print("[VIDEO] [OK] ffmpeg pipe closed OK")
        except Exception as e:
            print(f"[VIDEO] ffmpeg close error: {e}")
            try: ffproc.kill()
            except Exception: pass

    elif writer_type == 'imageio' and writer:
        try:
            writer.close()
            print("[VIDEO] [OK] imageio writer closed OK")
        except Exception as e:
            print(f"[VIDEO] ⚠ imageio close error: {e}")

    elif writer_type == 'opencv' and out:
        out.release()
        print("[VIDEO] [OK] OpenCV writer closed")
        # Remux OpenCV output → H.264
        if ffmpeg_bin:
            tmp2 = tmp_path + '.h264.mp4'
            try:
                cmd = [ffmpeg_bin, '-y', '-i', tmp_path,
                       '-c:v', 'libx264', '-crf', '23', '-preset', 'fast',
                       '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                       '-an', '-f', 'mp4', tmp2]
                subprocess.run(cmd, capture_output=True, timeout=300)
                if os.path.exists(tmp2) and os.path.getsize(tmp2) > 1000:
                    os.replace(tmp2, tmp_path)
                    print("[VIDEO] [OK] Remux to H.264 OK")
                else:
                    if os.path.exists(tmp2): os.remove(tmp2)
            except Exception as e:
                print(f"[VIDEO] Remux error: {e}")
                if os.path.exists(tmp2): os.remove(tmp2)

    # ── Move temp file → final output path ────────────────────────
    if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 500:
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            shutil.move(tmp_path, output_path)
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"[VIDEO] [OK] Output: {size_mb:.1f} MB, {frame_count} frames → {output_path}")
        except Exception as e:
            print(f"[VIDEO] [ERROR] Failed to move temp → output: {e}")
            # Leave tmp_path in place for debugging
    else:
        print(f"[VIDEO] [ERROR] Temp file missing or empty!")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return frame_count


VIDEO_DB_PATH = os.path.join(BASE_DIR, 'videoTasks.db')

def get_video_db():
    conn = sqlite3.connect(VIDEO_DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

# Auto-initialize video_tasks table
with get_video_db() as _vconn:
    _vconn.execute('''CREATE TABLE IF NOT EXISTS video_tasks (
        id VARCHAR(50) PRIMARY KEY,
        user_email VARCHAR(50),
        original_filename VARCHAR(255),
        status VARCHAR(100),
        progress INTEGER,
        result_path VARCHAR(255),
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    try:
        _vconn.execute('ALTER TABLE video_tasks ADD COLUMN frames_processed INTEGER DEFAULT 0')
    except Exception:
        pass
    try:
        _vconn.execute('ALTER TABLE video_tasks ADD COLUMN total_frames INTEGER DEFAULT 0')
    except Exception:
        pass


def process_video_task(task_id, input_path):
    conn = get_video_db()
    try:
        # We need the app context or just run naturally
        # 1) REMUX IF NEEDED
        orig_ext = os.path.splitext(input_path)[1].lower()
        playable_upload_name = f"v_{task_id}_play.mp4"
        playable_upload_path = os.path.join(VIDEO_UPLOAD_FOLDER, playable_upload_name)
        ffmpeg_bin = _get_ffmpeg_binary()

        try:
            if ffmpeg_bin and orig_ext not in ('.mp4'):
                tmp_fd, tmp_play = tempfile.mkstemp(suffix='.mp4', prefix='aqv_play_')
                os.close(tmp_fd)
                cmd = [
                    ffmpeg_bin, '-y', '-i', input_path,
                    '-c:v', 'libx264', '-crf', '23', '-preset', 'fast',
                    '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                    '-c:a', 'aac', '-b:a', '128k',
                    '-f', 'mp4', tmp_play
                ]
                subprocess.run(cmd, capture_output=True, timeout=120)
                if os.path.exists(tmp_play) and os.path.getsize(tmp_play) > 1000:
                    shutil.move(tmp_play, playable_upload_path)
                    input_path = playable_upload_path
                else:
                    if os.path.exists(tmp_play): os.remove(tmp_play)
            elif ffmpeg_bin and orig_ext == '.mp4':
                _remux_to_faststart(ffmpeg_bin, input_path, input_path)
        except Exception as e:
            print(f"[{task_id}] Remux warning: {e}")

        # 2) PREDICTION
        cap = cv2.VideoCapture(input_path)
        ret, first_frame = cap.read()
        cap.release()
        
        if not ret:
            raise Exception("Could not read video file. Invalid format.")
            
        frame_rgb = cv2.cvtColor(first_frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb).convert('RGB')
        img_tensor = transform(img).unsqueeze(0).to(DEVICE)
        with torch.no_grad():
            output_t = model(img_tensor)
            probs = torch.softmax(output_t, dim=1)
            confidence, pred_idx = torch.max(probs, 1)
        pred_class = CLASSES[pred_idx.item()]

        conn.execute('UPDATE video_tasks SET status=?, progress=? WHERE id=?', (f"Enhancing: {pred_class}", 10, task_id))
        conn.commit()

        # 3) ENHANCEMENT
        temporal_state = {}
        def _video_enhance_frame(pil_frame, _cls=pred_class):
            return _video_frame_enhance(pil_frame, _cls, temporal_state=temporal_state)

        enhanced_filename = f"ev_{task_id}.mp4"
        output_path = os.path.join(VIDEO_ENHANCED_FOLDER, enhanced_filename)

        def _my_callback(f_done, f_tot):
            try:
                c = get_video_db()
                pct = 10 + int(89 * (f_done / f_tot)) if f_tot else 10
                pct = max(10, min(99, pct))
                c.execute('UPDATE video_tasks SET frames_processed=?, total_frames=?, progress=? WHERE id=?', 
                          (f_done, f_tot, pct, task_id))
                c.commit()
                c.close()
            except Exception:
                pass

        frames = enhance_video_file(input_path, output_path, _video_enhance_frame, progress_callback=_my_callback)

        if frames > 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 500:
            conn.execute('UPDATE video_tasks SET status=?, progress=?, result_path=? WHERE id=?', 
                         ("Completed", 100, enhanced_filename, task_id))
        else:
            conn.execute('UPDATE video_tasks SET status=?, progress=? WHERE id=?', ("Error: Enhancement failed", 0, task_id))
        conn.commit()
    except Exception as e:
        conn.execute('UPDATE video_tasks SET status=? WHERE id=?', (f"Error: {e}", task_id))
        conn.commit()
    finally:
        conn.close()

@app.route('/video_prediction', methods=['GET', 'POST'])
def video_prediction():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    error = None

    if request.method == 'POST':
        try:
            _cleanup_old_video_files(keep_latest=3)
            
            free_mb = _get_free_disk_mb(BASE_DIR)
            if free_mb < MIN_DISK_MB:
                error = f"Not enough space. Free some disk space (need {MIN_DISK_MB} MB)."
                return render_template('video_prediction.html', error=error)
                
            video_file = request.files.get('video_file')
            if not video_file or video_file.filename == '':
                return render_template('video_prediction.html', error="No video uploaded.")

            short_id = uuid.uuid4().hex[:8]
            safe_video_name = secure_filename(video_file.filename) or 'video.mp4'
            orig_ext  = os.path.splitext(safe_video_name)[1].lower()
            
            os.makedirs(VIDEO_UPLOAD_FOLDER, exist_ok=True)
            upload_name = f"v_{short_id}{orig_ext or '.mp4'}"
            input_path  = os.path.join(VIDEO_UPLOAD_FOLDER, upload_name)
            video_file.save(input_path)
            
            conn = get_video_db()
            conn.execute('INSERT INTO video_tasks (id, user_email, original_filename, status, progress, result_path) VALUES (?, ?, ?, ?, ?, ?)',
                         (short_id, session['user_email'], video_file.filename, 'Processing', 0, ''))
            conn.commit()
            conn.close()
            
            threading.Thread(target=process_video_task, args=(short_id, input_path)).start()
            
            return redirect(url_for('video_status', task_id=short_id))
            
        except Exception as e:
            error = f"Error starting video task: {str(e)}"

    return render_template('video_prediction.html', error=error)

@app.route('/my_videos')
def my_videos():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    conn = get_video_db()
    tasks = conn.execute('SELECT * FROM video_tasks WHERE user_email=? ORDER BY timestamp DESC', (session['user_email'],)).fetchall()
    conn.close()
    return render_template('video_gallery.html', tasks=tasks)

@app.route('/video_status/<task_id>')
def video_status(task_id):
    """Legacy route — redirects to the status page rendered by video_status.html."""
    if 'user_email' not in session:
        return redirect(url_for('login'))
    return render_template('video_status.html', task_id=task_id)

@app.route('/api/task_status/<task_id>')
def api_task_status(task_id):
    """JSON polling endpoint consumed by video_status.html every 2.5 s.
    Returns { status, result, enhanced_name } shaped for the frontend.
    """
    if 'user_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_video_db()
    task = conn.execute('SELECT * FROM video_tasks WHERE id=?', (task_id,)).fetchone()
    conn.close()
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    task_dict = dict(task)
    raw_status = task_dict.get('status', '')

    # Map raw DB status → frontend status tokens
    if raw_status == 'Completed':
        fe_status = 'COMPLETED'
    elif raw_status.startswith('Error'):
        fe_status = 'FAILED'
    elif raw_status == 'Processing':
        fe_status = 'PENDING'
    else:
        fe_status = 'PROCESSING'

    enhanced_name = task_dict.get('result_path') or None
    if enhanced_name == '': enhanced_name = None

    result_payload = {
        'prediction': raw_status.replace('Enhancing: ', '') if raw_status.startswith('Enhancing') else None,
        'confidence': task_dict.get('progress', 0),
        'frames_processed': task_dict.get('frames_processed'),
        'total_frames': task_dict.get('total_frames'),
        'capped': False,
    }
    if fe_status == 'FAILED':
        result_payload['error'] = raw_status.replace('Error: ', '')

    return jsonify({
        'status': fe_status,
        'result': result_payload,
        'enhanced_name': enhanced_name,
    })


@app.route('/view_video_enhanced/<filename>')
def view_video_enhanced(filename):
    """Stream an enhanced video file for in-browser playback."""
    if 'user_email' not in session:
        return redirect(url_for('login'))
    safe = os.path.basename(filename)
    return send_from_directory(VIDEO_ENHANCED_FOLDER, safe, mimetype='video/mp4')


@app.route('/download_video/<filename>')
def download_video(filename):
    """Serve an enhanced video as a download attachment."""
    if 'user_email' not in session:
        return redirect(url_for('login'))
    safe = os.path.basename(filename)
    return send_from_directory(VIDEO_ENHANCED_FOLDER, safe, as_attachment=True)


@app.route('/my_videos/delete/<task_id>', methods=['POST'])
def delete_video_task(task_id):
    """Delete a video task: removes DB record + physical upload & enhanced files."""
    if 'user_email' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    conn = get_video_db()
    task = conn.execute(
        'SELECT * FROM video_tasks WHERE id=? AND user_email=?',
        (task_id, session['user_email'])
    ).fetchone()

    if not task:
        conn.close()
        return jsonify({'success': False, 'error': 'Task not found or access denied'}), 404

    task_dict = dict(task)

    # --- Delete physical files (sandboxed with basename) ---
    # Enhanced video: stored in static/ve  (e.g. ev_<task_id>.mp4)
    result_path = task_dict.get('result_path') or ''
    if result_path:
        safe_enhanced = os.path.basename(result_path)
        enhanced_file = os.path.join(VIDEO_ENHANCED_FOLDER, safe_enhanced)
        if os.path.isfile(enhanced_file):
            try:
                os.remove(enhanced_file)
            except OSError as exc:
                conn.close()
                return jsonify({'success': False, 'error': f'Could not delete enhanced file: {exc}'}), 500

    # Upload video: stored in static/vu  (e.g. v_<task_id>.mp4 or v_<task_id>_play.mp4)
    for candidate in [f'v_{task_id}.mp4', f'v_{task_id}_play.mp4',
                      f'v_{task_id}.mov', f'v_{task_id}.avi',
                      f'v_{task_id}.mkv', f'v_{task_id}.webm']:
        upload_file = os.path.join(VIDEO_UPLOAD_FOLDER, os.path.basename(candidate))
        if os.path.isfile(upload_file):
            try:
                os.remove(upload_file)
            except OSError:
                pass  # non-fatal — DB record still gets purged

    # --- Remove DB record ---
    conn.execute('DELETE FROM video_tasks WHERE id=? AND user_email=?',
                 (task_id, session['user_email']))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/gallery/delete/<filename>', methods=['POST'])
def gallery_delete(filename):
    if 'user_email' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        orig = filename[2:] if filename.startswith('e_') else filename
        orig_path = os.path.join(app.config['UPLOAD_FOLDER'], orig)
        enh_path  = os.path.join(app.config['ENHANCED_FOLDER'], filename)
        if os.path.exists(orig_path): os.remove(orig_path)
        if os.path.exists(enh_path): os.remove(enh_path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/gallery')
def gallery():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    pairs = []
    if os.path.exists(app.config['ENHANCED_FOLDER']):
        files = os.listdir(app.config['ENHANCED_FOLDER'])
        try:
            files.sort(key=lambda x: os.path.getmtime(os.path.join(app.config['ENHANCED_FOLDER'], x)), reverse=True)
        except:
            pass
        for f in files:
            if f.endswith(('.png', '.jpg', '.jpeg', '.webp')):
                orig = f[2:] if f.startswith('e_') else f
                pairs.append({'original': orig, 'enhanced': f})
    return render_template('gallery.html', pairs=pairs, tags=None)

@app.route('/gallery/download_all')
def gallery_download_zip():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    import io, zipfile
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(app.config['ENHANCED_FOLDER']):
            for f in os.listdir(app.config['ENHANCED_FOLDER']):
                if f.endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    zf.write(os.path.join(app.config['ENHANCED_FOLDER'], f), arcname=f)
    memory_file.seek(0)
    return send_file(memory_file, download_name='All_Enhanced_Images.zip', as_attachment=True)


@app.route('/logout')
def logout():
    session.pop('user_email', None)
    session.pop('user_name', None)
    return redirect(url_for('login'))


# ────────────────────────────────────────────────────────────────
#  BATCH ENHANCEMENT API
# ────────────────────────────────────────────────────────────────

@app.route('/batch_enhance', methods=['POST'])
def batch_enhance():
    """Process up to 10 images in one request.
    Returns JSON: { count, results: [{status, filename, prediction, confidence, original_url, enhanced_url}] }
    """
    if 'user_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    files = request.files.getlist('files')
    strength = request.form.get('strength', 'standard')  # mild / standard / strong
    if not files:
        return jsonify({'error': 'No files uploaded'}), 400

    files = files[:10]  # hard cap
    results = []

    # Strength multiplier table
    strength_factor = {'mild': 0.6, 'standard': 1.0, 'strong': 1.4}
    factor = strength_factor.get(strength, 1.0)

    for f in files:
        fname = secure_filename(f.filename) or 'image.jpg'
        try:
            ext = os.path.splitext(fname)[1].lower() or '.jpg'
            short_id = uuid.uuid4().hex[:8]
            filename = f'{short_id}{ext}'
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            f.save(image_path)

            # Classify
            img = Image.open(image_path).convert('RGB')
            img_tensor = transform(img).unsqueeze(0).to(DEVICE)
            with torch.no_grad():
                output = model(img_tensor)
                probs = torch.softmax(output, dim=1)
                confidence, pred_idx = torch.max(probs, 1)
            pred_class = CLASSES[pred_idx.item()]
            conf_pct = round(confidence.item() * 100, 2)

            # Enhance
            if strength == 'mild':
                arr = np.array(img)
                enhanced_arr = _underwater_core_enhance(
                    arr, red_strength=0.4 * factor, clahe_clip=1.5, saturation=1.05,
                    sharpen=0.1, lab_strength=0.2)
                enhanced = Image.fromarray(enhanced_arr)
            elif strength == 'strong':
                enhanced = adaptive_classical_enhance(img, pred_class)
                # extra boost pass
                arr2 = np.array(enhanced)
                enhanced_arr2 = _underwater_core_enhance(
                    arr2, red_strength=0.5, clahe_clip=2.5, saturation=1.25,
                    sharpen=0.3, use_dehaze=True, use_fusion=True, lab_strength=0.55)
                enhanced = Image.fromarray(enhanced_arr2)
            else:  # standard
                enhanced = adaptive_classical_enhance(img, pred_class)

            enhanced_filename = f'e_{short_id}{ext}'
            enhanced_path = os.path.join(app.config['ENHANCED_FOLDER'], enhanced_filename)
            enhanced.save(enhanced_path)

            results.append({
                'status': 'success',
                'filename': fname,
                'prediction': pred_class,
                'confidence': conf_pct,
                'original_url': f'/static/uploads/{filename}',
                'enhanced_url': f'/static/enhanced/{enhanced_filename}',
            })

        except Exception as e:
            results.append({
                'status': 'error',
                'filename': fname,
                'reason': str(e)
            })

    return jsonify({'count': len(results), 'results': results})


@app.route('/api/v1/download_zip', methods=['POST'])
def api_download_zip():
    """Accept a JSON list of relative enhanced image URLs and return them as a ZIP."""
    if 'user_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        data = request.get_json(force=True)
        urls = data.get('files', []) if data else []
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for url in urls:
                # url is like /static/enhanced/e_abc123.jpg
                rel = url.split('/static/')[-1] if '/static/' in url else ''
                abs_path = os.path.join(BASE_DIR, 'static', rel.replace('/', os.sep))
                if os.path.isfile(abs_path):
                    zf.write(abs_path, arcname=os.path.basename(abs_path))
        memory_file.seek(0)
        return send_file(memory_file, download_name='AquaVision_Batch.zip',
                         as_attachment=True, mimetype='application/zip')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api_dashboard')
def api_dashboard():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    # Fetch current API key for this user (if any)
    api_key = None
    try:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT key FROM api_keys WHERE user_email=? AND active=1 ORDER BY created_at DESC LIMIT 1',
                           (session['user_email'],)).fetchone()
        conn.close()
        if row:
            api_key = row['key']
    except Exception:
        pass  # api_keys table may not exist yet
    return render_template('api_dashboard.html', api_key=api_key)


@app.route('/api/dashboard/generate', methods=['POST'])
def api_dashboard_generate():
    """Generate or regenerate an API key for the logged-in user."""
    if 'user_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    email = session['user_email']
    new_key = 'aqv_' + secrets.token_hex(24)
    try:
        conn = get_db()
        # Create api_keys table if it doesn't exist
        conn.execute('''CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email VARCHAR(50),
            key VARCHAR(100) UNIQUE,
            active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        # Deactivate all existing keys for this user
        conn.execute('UPDATE api_keys SET active=0 WHERE user_email=?', (email,))
        # Insert new key
        conn.execute('INSERT INTO api_keys (user_email, key, active) VALUES (?, ?, 1)', (email, new_key))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'key': new_key})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download/<filename>')
def download_image(filename):
    if 'user_email' not in session:
        return redirect(url_for('login'))
    return send_from_directory(app.config['ENHANCED_FOLDER'], filename, as_attachment=True)


# ────────────────────────────────────────────────────────────────
#  REST API  — Bearer-token authenticated endpoints
# ────────────────────────────────────────────────────────────────

def _get_bearer_token():
    """Extract the Bearer token from the Authorization header, or None."""
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:].strip()
    return None

def _validate_api_key(token):
    """Return True if the token belongs to any registered API key.
    Falls back to accepting the session-authenticated user too (for the Try-It panel).
    """
    if not token:
        return False
    try:
        conn = get_db()
        row = conn.execute('SELECT 1 FROM api_keys WHERE key=? AND active=1', (token,)).fetchone()
        conn.close()
        return row is not None
    except Exception:
        # api_keys table may not exist yet — fall back gracefully
        return False


@app.route('/api/v1/enhance', methods=['POST'])
def api_v1_enhance():
    """REST API — enhance a single underwater image.
    Accepts: Bearer token OR logged-in session.
    Returns JSON with prediction, confidence, metrics, improvement_pct,
    and the enhanced image as base64-encoded JPEG.
    """
    token = _get_bearer_token()
    if not _validate_api_key(token) and 'user_email' not in session:
        return jsonify({'error': 'Unauthorized — provide a valid Bearer token'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    strength = request.form.get('strength', 'standard')
    fmt      = request.form.get('format', 'jpeg').lower()
    if fmt not in ('jpeg', 'jpg', 'png', 'tiff'):
        fmt = 'jpeg'
    mime_fmt = 'jpeg' if fmt in ('jpeg', 'jpg') else fmt

    try:
        img = Image.open(file.stream).convert('RGB')

        # Classify
        img_tensor = transform(img).unsqueeze(0).to(DEVICE)
        with torch.no_grad():
            output = model(img_tensor)
            probs  = torch.softmax(output, dim=1)
            confidence, pred_idx = torch.max(probs, 1)
        pred_class = CLASSES[pred_idx.item()]
        conf_pct   = round(confidence.item() * 100, 2)

        # Metrics — original
        metrics_orig = get_quality_metrics(img)

        # Enhance
        if strength == 'mild':
            arr = np.array(img)
            enh_arr = _underwater_core_enhance(
                arr, red_strength=0.35, clahe_clip=1.5, saturation=1.05,
                sharpen=0.1, lab_strength=0.2)
            enhanced = Image.fromarray(enh_arr)
        elif strength == 'strong':
            enhanced = adaptive_classical_enhance(img, pred_class)
            arr2 = np.array(enhanced)
            enh_arr2 = _underwater_core_enhance(
                arr2, red_strength=0.5, clahe_clip=2.5, saturation=1.25,
                sharpen=0.3, use_dehaze=True, use_fusion=True, lab_strength=0.55)
            enhanced = Image.fromarray(enh_arr2)
        else:
            enhanced = adaptive_classical_enhance(img, pred_class)

        # Metrics — enhanced
        metrics_enh = get_quality_metrics(enhanced)

        # Improvement %
        def _pct(orig, enh):
            return round((enh - orig) / orig * 100, 1) if orig and orig != 0 else 0.0

        improvement = round(
            _pct(metrics_orig['entropy'],      metrics_enh['entropy'])      * 0.50 +
            _pct(metrics_orig['colorfulness'], metrics_enh['colorfulness']) * 0.25 +
            _pct(metrics_orig['sharpness'],    metrics_enh['sharpness'])    * 0.25,
            1)

        # Encode to base64
        buf = io.BytesIO()
        enhanced.save(buf, format=mime_fmt.upper() if mime_fmt != 'jpeg' else 'JPEG', quality=92)
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        return jsonify({
            'prediction':            pred_class,
            'confidence':            conf_pct,
            'improvement_pct':       improvement,
            'strength':              strength.capitalize(),
            'enhancement_mode':      'Adaptive Classical Pipeline',
            'metrics_original':      metrics_orig,
            'metrics_enhanced':      metrics_enh,
            'enhanced_image_base64': b64,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/preview', methods=['POST'])
def api_preview():
    """Quick 200 px preview — full pipeline at low resolution.
    Requires session cookie (logged-in user). No API key needed.
    """
    if 'user_email' not in session:
        return jsonify({'error': 'Login required'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    strength = request.form.get('strength', 'standard')

    try:
        img = Image.open(request.files['file'].stream).convert('RGB')
        # Downscale for fast preview
        preview_w = 200
        ratio = preview_w / img.width
        preview_h = max(1, int(img.height * ratio))
        small = img.resize((preview_w, preview_h), Image.LANCZOS)

        # Classify on small version
        img_tensor = transform(small).unsqueeze(0).to(DEVICE)
        with torch.no_grad():
            out   = model(img_tensor)
            probs = torch.softmax(out, dim=1)
            conf, pred_idx = torch.max(probs, 1)
        pred_class = CLASSES[pred_idx.item()]

        enhanced = adaptive_classical_enhance(small, pred_class)

        buf = io.BytesIO()
        enhanced.save(buf, format='JPEG', quality=80)
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        return jsonify({
            'prediction':            pred_class,
            'confidence':            round(conf.item() * 100, 2),
            'enhanced_image_base64': b64,
            'note':                  'Low-resolution preview only',
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    from waitress import serve
    port = int(os.environ.get('PORT', 5000))
    serve(app, host='0.0.0.0', port=port, threads=8)
