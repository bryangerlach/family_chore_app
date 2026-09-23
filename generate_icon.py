from PIL import Image, ImageDraw

def create_app_icon(output_path="icon-192x192.png", size=192):
    # Create a transparent base image
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # 1. Draw rounded squircle background (App Icon Shape)
    margin = int(size * 0.05)
    corner_radius = int(size * 0.22)
    bg_box = [margin, margin, size - margin, size - margin]
    
    # Soft shadow/depth effect (optional outer backing)
    shadow_box = [margin, margin + 8, size - margin, size - margin + 8]
    draw.rounded_rectangle(shadow_box, radius=corner_radius, fill=(20, 100, 160, 100))
    
    # Main vibrant blue background gradient look (solid tone here for simplicity)
    draw.rounded_rectangle(bg_box, radius=corner_radius, fill=(33, 150, 243, 255))
    
    # Inner subtle highlight border
    highlight_box = [margin + 4, margin + 4, size - margin - 4, size - margin - 4]
    draw.rounded_rectangle(highlight_box, radius=corner_radius - 2, outline=(77, 182, 241, 255), width=4)

    # 2. Draw Checklist Bars (White rounded rectangles)
    bar_width = int(size * 0.38)
    bar_height = int(size * 0.09)
    start_x = int(size * 0.48)
    start_y = int(size * 0.22)
    spacing = int(size * 0.13)
    
    for i in range(3):
        y = start_y + (i * spacing)
        # Background track for list item
        draw.rounded_rectangle(
            [start_x, y, start_x + bar_width, y + bar_height],
            radius=int(bar_height / 2),
            fill=(255, 255, 255, 255)
        )
        
        # Checkboxes / icons inside the list rows
        box_x = start_x - int(size * 0.11)
        draw.rounded_rectangle(
            [box_x, y, box_x + bar_height, y + bar_height],
            radius=int(bar_height * 0.3),
            fill=(255, 255, 255, 220)
        )
        
        # Draw a tiny green checkmark on the first two, star on the third
        if i < 2:
            # Simple checkmark representation
            chk_x = box_x + int(bar_height * 0.25)
            chk_y = y + int(bar_height * 0.5)
            draw.line([chk_x, chk_y, chk_x + 6, chk_y + 8], fill=(76, 175, 80, 255), width=5)
            draw.line([chk_x + 6, chk_y + 8, chk_x + 16, chk_y - 6], fill=(76, 175, 80, 255), width=5)
        else:
            # Star accent for the last item
            star_center = (box_x + int(bar_height / 2), y + int(bar_height / 2))
            # Draw a simple dot/star substitute for code simplicity
            draw.ellipse(
                [star_center[0]-6, star_center[1]-6, star_center[0]+6, star_center[1]+6],
                fill=(255, 193, 7, 255)
            )

    # 3. Draw a stylized Cleaning/Chore Spray Bottle on the left side
    bottle_x = int(size * 0.16)
    bottle_y = int(size * 0.35)
    
    # Bottle body
    draw.rounded_rectangle(
        [bottle_x, bottle_y + 40, bottle_x + 65, bottle_y + 140],
        radius=12,
        fill=(255, 255, 255, 255)
    )
    # Bottle neck & nozzle
    draw.rectangle([bottle_x + 22, bottle_y + 15, bottle_x + 43, bottle_y + 40], fill=(255, 255, 255, 255))
    draw.rectangle([bottle_x + 10, bottle_y + 15, bottle_x + 30, bottle_y + 25], fill=(255, 255, 255, 255))

    # Save output
    image.save(output_path, "PNG")
    print(f"Icon successfully generated and saved to {output_path}")

if __name__ == "__main__":
    create_app_icon()