from PIL import Image, ImageOps
import os

UPLOAD_FOLDER = 'static/images'
IMAGE_MAX_SIZE = (1200, 1200)
IMAGE_WEBP_QUALITY = 78

def convert_to_webp(image_path):
    """Convert PNG/JPG image to WebP format"""
    if not os.path.exists(image_path):
        return False
    
    stem, ext = os.path.splitext(image_path)
    if ext.lower() == '.webp':
        return True
    
    webp_path = f"{stem}.webp"
    
    # Skip if WebP already exists
    if os.path.exists(webp_path):
        print(f"⏭️  {os.path.basename(image_path)} (WebP exists)")
        return True
    
    try:
        image = Image.open(image_path)
        image = ImageOps.exif_transpose(image)
        image.thumbnail(IMAGE_MAX_SIZE, Image.Resampling.LANCZOS)
        image.save(webp_path, "WEBP", quality=IMAGE_WEBP_QUALITY, method=6)
        print(f"✓ {os.path.basename(image_path)} -> {os.path.basename(webp_path)}")
        return True
    except Exception as e:
        print(f"✗ {os.path.basename(image_path)}: {e}")
        return False

def main():
    print("🔄 Converting images to WebP...\n")
    
    converted = 0
    skipped = 0
    errors = 0
    
    files = sorted(os.listdir(UPLOAD_FOLDER))
    total = len([f for f in files if not f.startswith('.') and os.path.isfile(os.path.join(UPLOAD_FOLDER, f))])
    
    print(f"📁 Found {total} files in {UPLOAD_FOLDER}\n")
    
    for i, filename in enumerate(files, 1):
        if filename.startswith('.'):
            continue
            
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        if not os.path.isfile(filepath):
            continue
        
        stem, ext = os.path.splitext(filename)
        
        # Skip if already WebP
        if ext.lower() == '.webp':
            skipped += 1
            continue
        
        # Convert PNG/JPG to WebP
        if ext.lower() in ['.png', '.jpg', '.jpeg']:
            if convert_to_webp(filepath):
                converted += 1
            else:
                errors += 1
        
        # Progress indicator
        if i % 10 == 0:
            print(f"   ... {i}/{total}")
    
    print(f"\n{'='*60}")
    print(f"✅ Converted: {converted} images")
    print(f"⏭️  Skipped (already WebP): {skipped} images")
    print(f"❌ Errors: {errors}")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()