import os
from PIL import Image

images_dir = 'static/images'
converted = 0
skipped = 0
errors = 0

# Get all image files
image_files = [f for f in os.listdir(images_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

for img_file in image_files:
    img_path = os.path.join(images_dir, img_file)
    webp_file = os.path.splitext(img_file)[0] + '.webp'
    webp_path = os.path.join(images_dir, webp_file)
    
    # Skip if webp already exists
    if os.path.exists(webp_path):
        skipped += 1
        continue
    
    try:
        # Open and convert to webp
        img = Image.open(img_path)
        
        # Convert RGBA to RGB if necessary (webp doesn't support transparency well)
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            # Create white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Save as webp with good quality
        img.save(webp_path, 'WEBP', quality=90, method=6)
        converted += 1
        print(f"✓ Converted: {img_file} -> {webp_file}")
    except Exception as e:
        errors += 1
        print(f"✗ Error converting {img_file}: {e}")

print(f"\n{'='*50}")
print(f"Total images: {len(image_files)}")
print(f"Converted: {converted}")
print(f"Skipped (already exists): {skipped}")
print(f"Errors: {errors}")
print(f"{'='*50}")