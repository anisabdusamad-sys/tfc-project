"""Convert all .png and .jpg images to .webp format in static/images"""
import os
from PIL import Image

IMAGES_DIR = os.path.join(os.path.dirname(__file__), 'static', 'images')

def convert_to_webp(filepath):
    """Convert image to .webp format, delete original if successful"""
    try:
        img = Image.open(filepath).convert('RGB')
        webp_path = os.path.splitext(filepath)[0] + '.webp'
        
        # Skip if webp already exists
        if os.path.exists(webp_path):
            print(f"  ⏭️  Already exists: {os.path.basename(webp_path)}")
            return True
        
        # Save as webp with quality 80 (good balance of quality/size)
        img.save(webp_path, 'WEBP', quality=80)
        print(f"  ✅ Converted: {os.path.basename(filepath)} → {os.path.basename(webp_path)}")
        return True
    except Exception as e:
        print(f"  ❌ Error converting {os.path.basename(filepath)}: {e}")
        return False

def main():
    if not os.path.exists(IMAGES_DIR):
        print(f"Directory not found: {IMAGES_DIR}")
        return
    
    print("=" * 60)
    print("🖼️  Converting images to WebP format")
    print("=" * 60)
    
    converted = 0
    skipped = 0
    errors = 0
    
    for filename in os.listdir(IMAGES_DIR):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            # Skip TFC.jpg (favicon)
            if filename.upper() == 'TFC.JPG':
                print(f"  ⏭️  Skipping favicon: {filename}")
                skipped += 1
                continue
            
            filepath = os.path.join(IMAGES_DIR, filename)
            if convert_to_webp(filepath):
                converted += 1
            else:
                errors += 1
    
    print("=" * 60)
    print(f"📊 Results: {converted} converted, {skipped} skipped, {errors} errors")
    print("=" * 60)

if __name__ == '__main__':
    main()