import numpy as np
from PIL import Image
from scipy import ndimage

def segment_lines_rlsa(img: Image.Image, min_w=60, min_h=15, max_h=180):
    w, h = img.size
    gray = np.array(img.convert("L"), dtype=np.uint8)
    
    # 1. Background normalization / Otsu-like ink detection
    # Ink is darker than background
    mean_val = np.mean(gray)
    std_val = np.std(gray)
    thresh = max(40, mean_val - 0.45 * std_val)
    ink = (gray < thresh)
    
    # 2. Horizontal smearing (anisotropic morphological closing/dilation)
    # Smear horizontally to bridge spaces between words on the same line
    # but keep vertical dilation very small so lines don't merge
    h_kernel_w = max(25, int(w * 0.035)) # ~40-45 pixels at 1240 width
    h_struct = np.ones((3, h_kernel_w), dtype=bool)
    smeared = ndimage.binary_dilation(ink, structure=h_struct)
    
    # Optional small vertical closing to fill character interiors
    v_struct = np.ones((5, 3), dtype=bool)
    smeared = ndimage.binary_closing(smeared, structure=v_struct)
    
    # 3. Label connected components
    labeled, num_features = ndimage.label(smeared)
    slices = ndimage.find_objects(labeled)
    
    boxes = []
    for sl in slices:
        if sl is None:
            continue
        y_slice, x_slice = sl
        y1, y2 = y_slice.start, y_slice.stop
        x1, x2 = x_slice.start, x_slice.stop
        box_w = x2 - x1
        box_h = y2 - y1
        
        # Filter noise or tiny specks
        if box_w >= min_w and box_h >= min_h and box_h <= max_h:
            # Add padding for ascenders/descenders
            pad_y = int(box_h * 0.25)
            pad_x = 10
            ny1 = max(0, y1 - pad_y)
            ny2 = min(h, y2 + pad_y)
            nx1 = max(0, x1 - pad_x)
            nx2 = min(w, x2 + pad_x)
            boxes.append((nx1, ny1, nx2, ny2))
            
    # 4. Sort lines top-to-bottom
    # If two boxes overlap vertically significantly (>50%), sort left-to-right
    boxes.sort(key=lambda b: (b[1], b[0]))
    
    # 5. Merge lines that are on the exact same vertical baseline band
    merged = []
    for b in boxes:
        if not merged:
            merged.append(b)
            continue
        prev = merged[-1]
        # Check vertical overlap
        overlap_y = min(prev[3], b[3]) - max(prev[1], b[1])
        min_h_overlap = min(prev[3] - prev[1], b[3] - b[1])
        if overlap_y > 0.6 * min_h_overlap and (b[0] - prev[2] < 80): # adjacent on same line
            # Merge
            new_box = (min(prev[0], b[0]), min(prev[1], b[1]), max(prev[2], b[2]), max(prev[3], b[3]))
            merged[-1] = new_box
        else:
            merged.append(b)
            
    return merged

img = Image.open('../storage/uploads/debug_page_1.png')
boxes = segment_lines_rlsa(img)
print(f"Segmented {len(boxes)} lines from debug_page_1.png ({img.size})")
for i, b in enumerate(boxes[:15]):
    print(f"  Line {i:02d}: x=({b[0]:4d}, {b[2]:4d}) y=({b[1]:4d}, {b[3]:4d}) w={b[2]-b[0]:4d} h={b[3]-b[1]:3d}")
