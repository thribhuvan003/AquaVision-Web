import os
import sys
sys.path.append(r'C:\temp\dav2')

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from DPF_Net import TotalNetwork
from DPEM import DPEM_model
from depth_anything_v2.dpt import DepthAnythingV2
import glob

def test_inference():
    print("Testing ML Pipeline completely...")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")
    
    dpf_net_weight_path   = "./checkpoints/DPF-Net.pth"
    dpem_weight_path      = "./checkpoints/DPEM_finetune.pth"
    depth_model_path      = "./checkpoints/dav2.pth"
    
    # Check if models exist
    for p in [dpf_net_weight_path, dpem_weight_path, depth_model_path]:
        if not os.path.exists(p):
            print(f"ERROR: Model weight missing at {p}")
            return False

    try:
        # 1. Load Models
        print("Loading DepthAnything...")
        depth_configs = {'vits': {'encoder': 'vits', 'features': 64, 'out_channels': [48, 96, 192, 384]}}
        depth_anything = DepthAnythingV2(**depth_configs['vits'])
        depth_anything.load_state_dict(torch.load(depth_model_path, map_location='cpu'))
        depth_anything = depth_anything.to(device).eval()
        
        print("Loading DPEM...")
        MODEL_SIZE = 256
        dpem = DPEM_model.MainNet(device=device, imgSize=MODEL_SIZE, depth_weight_path=depth_model_path).to(device).eval()
        dpem.load_state_dict(torch.load(dpem_weight_path, map_location=device))
        
        print("Loading DPF-Net...")
        model = TotalNetwork(device=device).eval()
        model.load_state_dict(torch.load(dpf_net_weight_path, map_location=device))
        
        # 2. Find an image
        images = glob.glob("**/*.jpg", recursive=True) + glob.glob("**/*.png", recursive=True)
        # filter out the python files, checkpoints, etc just in case
        images = [i for i in images if 'checkpoints' not in i]
        
        if not images:
            print("No test images found. Creating a blank dummy image for testing.")
            img = np.zeros((256, 256, 3), dtype=np.uint8)
        else:
            test_img_path = images[0]
            print(f"Testing on image: {test_img_path}")
            img = cv2.imread(test_img_path)
            if img is None:
                img = np.zeros((256, 256, 3), dtype=np.uint8)
        
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img_rgb, (MODEL_SIZE, MODEL_SIZE))
        img_tensor = torch.from_numpy(img_resized.astype(np.float32)).permute(2, 0, 1).unsqueeze(0) / 255.0
        img_tensor = img_tensor.to(device)
        
        # 3. Inference
        with torch.no_grad():
            _, _, h, w = img_tensor.shape
            pad_h = (14 - h % 14) % 14
            pad_w = (14 - w % 14) % 14
            img_padded = F.pad(img_tensor, (0, pad_w, 0, pad_h), mode='reflect')
            depth_padded = depth_anything(img_padded)
            
            if depth_padded.dim() == 2:
                depth_padded = depth_padded.unsqueeze(0).unsqueeze(0)
            elif depth_padded.dim() == 3:
                depth_padded = depth_padded.unsqueeze(1)
            depth_map = depth_padded[:, :, :h, :w]
            
            dark_channel = torch.min(img_tensor, dim=1, keepdim=True)[0]
            bl_value = torch.quantile(dark_channel.view(1, -1), 0.98) 
            bl = bl_value.view(1, 1, 1, 1)
            
            pre_B_replicated = bl.repeat(1, 3, MODEL_SIZE, MODEL_SIZE)
            x_B, x_beta_D, x_beta_B, x_d = dpem(img_tensor, pre_B_replicated)
            
            replicated_x_B     = x_B.unsqueeze(2).unsqueeze(3).repeat(1, 1, MODEL_SIZE, MODEL_SIZE)
            replicated_x_beta_D = x_beta_D.unsqueeze(2).unsqueeze(3).repeat(1, 1, MODEL_SIZE, MODEL_SIZE)
            replicated_x_beta_B = x_beta_B.unsqueeze(2).unsqueeze(3).repeat(1, 1, MODEL_SIZE, MODEL_SIZE)
            
            channel_replica = x_d[:, 0:1, :, :]
            replicated_x_d = torch.cat((x_d, channel_replica, channel_replica), dim=1)
            
            outputs = model(img_tensor, replicated_x_B, replicated_x_d, replicated_x_beta_D, replicated_x_beta_B)
            enhanced = outputs[0].clamp(0, 1)
            print("Success! Output shape:", enhanced.shape)
            return True
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    test_inference()
