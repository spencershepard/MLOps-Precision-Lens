import os
import cv2
import numpy as np
import logging
import random
import shutil
from PIL import Image, ImageDraw, ImageFilter

def create_synthetic_anomalies(normal_images_dir, output_test_dir, output_mask_dir, num_anomalies=10, exclude_dir=None):
    """
    Create synthetic anomalous images and their corresponding masks.
    
    Args:
        normal_images_dir: Directory containing normal images
        output_test_dir: Directory to save anomalous test images
        output_mask_dir: Directory to save anomaly masks
        num_anomalies: Number of synthetic anomalies to create
        exclude_dir: Directory containing files to exclude from being used as anomalies
    
    Returns:
        List of directory paths containing the synthetic anomalies
    """
    # Clean directories before creating new anomalies
    os.makedirs(output_test_dir, exist_ok=True)
    os.makedirs(output_mask_dir, exist_ok=True)
    
    # Get list of normal images
    image_files = []
    for ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']:
        image_files.extend([f for f in os.listdir(normal_images_dir) if f.lower().endswith(ext)])
    
    # Exclude files from the exclude_dir
    if exclude_dir and os.path.exists(exclude_dir):
        exclude_files = set(os.listdir(exclude_dir))
        image_files = [f for f in image_files if f not in exclude_files]
    
    if not image_files:
        logging.error(f"No images found in {normal_images_dir} after excluding files from {exclude_dir}")
        return []
    
    logging.info(f"Creating {num_anomalies} synthetic anomalies from {len(image_files)} normal images")
    
    # Different anomaly types
    anomaly_types = ['stain', 'scratch', 'debris', 'spot', 'crack']
    
    # Create synthetic anomalies
    created_anomalies = 0
    for i in range(num_anomalies):
        # Select a random image
        img_file = random.choice(image_files)
        img_path = os.path.join(normal_images_dir, img_file)
        
        # Open the image
        try:
            img = Image.open(img_path)
        except Exception as e:
            logging.warning(f"Failed to open image {img_path}: {e}")
            continue
        
        width, height = img.size
        
        # Create a blank mask
        mask = Image.new('L', (width, height), 0)
        draw_mask = ImageDraw.Draw(mask)
        
        # Choose anomaly type
        anomaly_type = random.choice(anomaly_types)
        
        # Create a copy of the image for modification
        anomalous_img = img.copy()
        draw_img = ImageDraw.Draw(anomalous_img)
        
        # Generate anomaly based on type
        try:
            if anomaly_type == 'stain':
                # Create irregular stain
                x, y = random.randint(0, width-1), random.randint(0, height-1)
                radius = random.randint(10, max(20, min(width, height) // 8))
                
                # Draw on mask
                draw_mask.ellipse((x-radius, y-radius, x+radius, y+radius), fill=255)
                
                # Apply stain to image
                for dx in range(-radius, radius+1):
                    for dy in range(-radius, radius+1):
                        if dx*dx + dy*dy <= radius*radius:
                            px, py = x+dx, y+dy
                            if 0 <= px < width and 0 <= py < height:
                                # Darken the pixel
                                r, g, b = anomalous_img.getpixel((px, py))[:3]
                                darkness = random.uniform(0.3, 0.7)
                                anomalous_img.putpixel((px, py), 
                                                     (int(r*darkness), int(g*darkness), int(b*darkness)))
                
            elif anomaly_type == 'scratch':
                # Create a line scratch
                x1, y1 = random.randint(0, width-1), random.randint(0, height-1)
                angle = random.uniform(0, 2*np.pi)
                length = random.randint(20, max(50, min(width, height) // 4))
                thickness = random.randint(2, 6)
                
                x2 = int(x1 + length * np.cos(angle))
                y2 = int(y1 + length * np.sin(angle))
                
                # Draw on mask
                draw_mask.line((x1, y1, x2, y2), fill=255, width=thickness)
                
                # Draw on image
                draw_img.line((x1, y1, x2, y2), fill=(255, 255, 255), width=thickness)
                
            elif anomaly_type == 'debris':
                # Create random debris (small irregular shapes)
                num_debris = random.randint(3, 8)
                for _ in range(num_debris):
                    x, y = random.randint(0, width-1), random.randint(0, height-1)
                    size = random.randint(5, 15)
                    
                    # Draw irregular shape on mask
                    points = []
                    for a in range(0, 360, 45):
                        r = random.randint(size//2, size)
                        px = x + int(r * np.cos(np.radians(a)))
                        py = y + int(r * np.sin(np.radians(a)))
                        points.append((px, py))
                    
                    draw_mask.polygon(points, fill=255)
                    
                    # Draw on image - bright spot
                    for point in points:
                        draw_img.ellipse((point[0]-2, point[1]-2, point[0]+2, point[1]+2), 
                                       fill=(240, 240, 240))
                    
            elif anomaly_type == 'spot':
                # Create a bright/dark spot
                x, y = random.randint(0, width-1), random.randint(0, height-1)
                radius = random.randint(8, 20)
                
                # Draw on mask
                draw_mask.ellipse((x-radius, y-radius, x+radius, y+radius), fill=255)
                
                # Draw bright spot on image
                is_bright = random.choice([True, False])
                for dx in range(-radius, radius+1):
                    for dy in range(-radius, radius+1):
                        if dx*dx + dy*dy <= radius*radius:
                            px, py = x+dx, y+dy
                            if 0 <= px < width and 0 <= py < height:
                                # Adjust the pixel
                                r, g, b = anomalous_img.getpixel((px, py))[:3]
                                factor = 1.5 if is_bright else 0.4
                                anomalous_img.putpixel((px, py), 
                                                     (min(255, int(r*factor)), 
                                                      min(255, int(g*factor)), 
                                                      min(255, int(b*factor))))
                                                      
            elif anomaly_type == 'crack':
                # Create a branching crack
                x, y = random.randint(0, width-1), random.randint(0, height-1)
                
                def draw_branch(x, y, length, angle, depth):
                    if depth <= 0 or length < 5:
                        return
                        
                    # Calculate end point
                    end_x = int(x + length * np.cos(angle))
                    end_y = int(y + length * np.sin(angle))
                    
                    # Keep within bounds
                    end_x = min(max(0, end_x), width-1)
                    end_y = min(max(0, end_y), height-1)
                    
                    # Draw line on mask and image
                    draw_mask.line((x, y, end_x, end_y), fill=255, width=2)
                    draw_img.line((x, y, end_x, end_y), fill=(50, 50, 50), width=2)
                    
                    # Branch out
                    if random.random() < 0.7:  # 70% chance to branch
                        new_angle1 = angle + random.uniform(-0.5, 0.5)
                        new_angle2 = angle + random.uniform(-0.5, 0.5)
                        new_length = length * random.uniform(0.6, 0.9)
                        draw_branch(end_x, end_y, new_length, new_angle1, depth-1)
                        draw_branch(end_x, end_y, new_length, new_angle2, depth-1)
                
                # Start the crack
                start_angle = random.uniform(0, 2*np.pi)
                start_length = random.randint(20, 60)
                draw_branch(x, y, start_length, start_angle, 3)  # 3 levels of branching
        except Exception as e:
            logging.warning(f"Failed to create anomaly {anomaly_type} for image {img_file}: {e}")
            continue
        
        # Apply slight blur to mask for more realistic edges
        mask = mask.filter(ImageFilter.GaussianBlur(1))
        
        # Save anomalous image and mask
        anomaly_dir = os.path.join(output_test_dir, "syn_" + anomaly_type)
        mask_dir = os.path.join(output_mask_dir, "syn_" + anomaly_type)
        
        os.makedirs(anomaly_dir, exist_ok=True)
        os.makedirs(mask_dir, exist_ok=True)
        
        output_filename = f"{created_anomalies:03d}_{os.path.splitext(img_file)[0]}_{anomaly_type}.png"
        try:
            anomalous_img.save(os.path.join(anomaly_dir, output_filename))
            mask.save(os.path.join(mask_dir, output_filename))
            logging.info(f"Created image: {output_filename} in {anomaly_dir}")
            logging.info(f"Created mask: {output_filename} in {mask_dir}")
            created_anomalies += 1
        except Exception as e:
            logging.warning(f"Failed to save anomaly or mask for {img_file}: {e}")
            continue
    
    # Verify file consistency across subdirectories
    for anomaly_type in anomaly_types:
        test_subdir = os.path.join(output_test_dir, "syn_" + anomaly_type)
        mask_subdir = os.path.join(output_mask_dir, "syn_" + anomaly_type)
        
        if os.path.exists(test_subdir) and os.path.exists(mask_subdir):
            test_files = set(f for f in os.listdir(test_subdir) if os.path.isfile(os.path.join(test_subdir, f)))
            mask_files = set(f for f in os.listdir(mask_subdir) if os.path.isfile(os.path.join(mask_subdir, f)))
            
            extra_test_files = test_files - mask_files
            missing_mask_files = mask_files - test_files
            
            if extra_test_files:
                logging.warning(f"Extra files in {test_subdir}: {extra_test_files}")
            if missing_mask_files:
                logging.warning(f"Missing test files for masks in {mask_subdir}: {missing_mask_files}")
            
            if len(test_files) == len(mask_files) and not extra_test_files:
                logging.info(f"✓ Verified {len(test_files)} matching files for {anomaly_type}")
    
    logging.info(f"Created {created_anomalies} synthetic anomalies in {output_test_dir} with masks in {output_mask_dir}")
    return [os.path.join('test', "syn_" + anomaly_type) for anomaly_type in anomaly_types]

def create_synthetic_test_data(train_dir, cache_directory, category, combine_with_real=True):
    """
    Create synthetic test data based on normal training images.
    
    Args:
        train_dir: Directory containing normal training images
        cache_directory: Base directory for caching data
        category: Category name for the dataset
        combine_with_real: If True, combine synthetic with existing real anomaly data
        
    Returns:
        Tuple containing (test_data_available, normal_test_dir, abnormal_dirs, mask_dirs)
    """
    logging.info("Creating synthetic anomalous test data...")
    
    # Create directories if they don't exist
    synthetic_test_dir = os.path.join(cache_directory, category, 'test')
    synthetic_mask_dir = os.path.join(cache_directory, category, 'ground_truth')
    
    # Clear ONLY existing synthetic directories (keep real anomaly data)
    import glob
    for syn_dir in glob.glob(os.path.join(synthetic_test_dir, 'syn_*')):
        if os.path.isdir(syn_dir):
            shutil.rmtree(syn_dir)
            logging.info(f"Cleared existing synthetic directory: {syn_dir}")
    
    for syn_dir in glob.glob(os.path.join(synthetic_mask_dir, 'syn_*')):
        if os.path.isdir(syn_dir):
            shutil.rmtree(syn_dir)
            logging.info(f"Cleared existing synthetic mask directory: {syn_dir}")
    
    os.makedirs(synthetic_test_dir, exist_ok=True)
    os.makedirs(synthetic_mask_dir, exist_ok=True)
    
    # Copy some normal images to test/good directory
    normal_test_dir = os.path.join(synthetic_test_dir, 'good')
    os.makedirs(normal_test_dir, exist_ok=True)
    
    # Get list of normal training images
    normal_images = []
    for ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']:
        normal_images.extend([f for f in os.listdir(train_dir) if f.lower().endswith(ext)])
    
    # Copy a subset of normal images to test/good
    num_normal_test = min(10, len(normal_images))
    for i, img_file in enumerate(random.sample(normal_images, num_normal_test)):
        shutil.copy(
            os.path.join(train_dir, img_file),
            os.path.join(normal_test_dir, f"normal_{i:03d}.png")
        )
    
    # Create synthetic anomalies, excluding files in test/good
    synthetic_abnormal_dirs = create_synthetic_anomalies(
        train_dir,  # Source: normal training images
        synthetic_test_dir,  # Output test directory
        synthetic_mask_dir,  # Output mask directory
        num_anomalies=50,  # Create 50 anomalous images (10 per anomaly type)
        exclude_dir=normal_test_dir  # Exclude files in test/good
    )
    
    # Collect all abnormal and mask directories (synthetic + real if combining)
    abnormal_dirs = []
    mask_dirs = []
    
    if combine_with_real:
        # Include real anomaly directories (non-synthetic, non-good)
        for d in os.listdir(synthetic_test_dir):
            dir_path = os.path.join(synthetic_test_dir, d)
            if os.path.isdir(dir_path) and d != 'good':
                abnormal_dirs.append(os.path.join('test', d))
                logging.info(f"Including test directory: test/{d}")
        
        # Include all mask directories
        for d in os.listdir(synthetic_mask_dir):
            dir_path = os.path.join(synthetic_mask_dir, d)
            if os.path.isdir(dir_path):
                mask_dirs.append(os.path.join('ground_truth', d))
                logging.info(f"Including mask directory: ground_truth/{d}")
    else:
        # Use only synthetic directories
        abnormal_dirs = synthetic_abnormal_dirs
        mask_dirs = [os.path.join('ground_truth', "syn_" + atype) for atype in ['stain', 'scratch', 'debris', 'spot', 'crack']]
    
    logging.info(f"Final abnormal directories: {abnormal_dirs}")
    logging.info(f"Final mask directories: {mask_dirs}")
    
    return True, os.path.join('test', 'good'), abnormal_dirs, mask_dirs
