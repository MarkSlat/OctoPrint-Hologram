import io
import math
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d import proj3d
from PIL import Image
from skimage.metrics import structural_similarity as ssim
from skimage.io import imread
from skimage.color import rgb2gray

def get_pixel_coords(ax, x, y, z):
    # Transform 3D point to 2D screen coordinates
    x_proj, y_proj, _ = proj3d.proj_transform(x, y, z, ax.get_proj())

    # Get the pixel coordinates
    pixel_coords = ax.transData.transform((x_proj, y_proj))

    # Invert the y-component of pixel_coords
    pixel_coords = (pixel_coords[0], ax.figure.bbox.height - pixel_coords[1])

    return pixel_coords

def plot_arrow(grid_limits, elev, azim, roll, focal_length):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    # Define the coordinates of the arrow tail (center of the XY plane)
    x_tail, y_tail, z_tail = grid_limits[0] + 0.5 * (grid_limits[1] - grid_limits[0]), \
                             grid_limits[2] + 0.5 * (grid_limits[3] - grid_limits[2]), \
                             grid_limits[4]

    # Define the coordinates of the arrow head (origin of the grid)
    x_head, y_head, z_head = grid_limits[0], grid_limits[2], grid_limits[4]

    # Compute the components of the arrow vector
    U = x_head - x_tail
    V = y_head - y_tail
    W = z_head - z_tail

    # Plot the arrow
    ax.quiver(x_tail, y_tail, z_tail, U, V, W, color='r', arrow_length_ratio=0.2, pivot='tail')

    # Calculate required aspect ratio for equal scaling
    x_range = grid_limits[1] - grid_limits[0]
    y_range = grid_limits[3] - grid_limits[2]
    z_range = grid_limits[5] - grid_limits[4]
    max_range = max(x_range, y_range, z_range)
    ax.set_box_aspect([x_range/max_range, y_range/max_range, z_range/max_range])

    # Set plot limits
    ax.set_xlim([grid_limits[0], grid_limits[1]])
    ax.set_ylim([grid_limits[2], grid_limits[3]])
    ax.set_zlim([grid_limits[4], grid_limits[5]])

    # Plot lines for xy limits
    ax.plot([grid_limits[0], grid_limits[1]], [grid_limits[2], grid_limits[2]], [grid_limits[4], grid_limits[4]], color='b')
    ax.plot([grid_limits[0], grid_limits[0]], [grid_limits[2], grid_limits[3]], [grid_limits[4], grid_limits[4]], color='b')
    ax.plot([grid_limits[1], grid_limits[1]], [grid_limits[2], grid_limits[3]], [grid_limits[4], grid_limits[4]], color='b')
    ax.plot([grid_limits[0], grid_limits[1]], [grid_limits[3], grid_limits[3]], [grid_limits[4], grid_limits[4]], color='b')

    ax.set_axis_off()

    ax.set_proj_type(proj_type='persp', focal_length=focal_length)

    x_input = grid_limits[1]/2
    y_input = grid_limits[3]/2
    z_input = 0
    
    ax.view_init(elev=elev, azim=azim, roll=roll)

    pixel_coords = get_pixel_coords(ax, x_input, y_input, z_input)

    arrow_img = io.BytesIO()
    fig.savefig(arrow_img, format='png', transparent=True)
    arrow_img.seek(0)

    plt.close()
    
    return arrow_img, pixel_coords

def center_of_quadrilateral(points):
    if len(points) != 4:
        raise ValueError("A quadrilateral must have exactly 4 points.")
    
    x1, y1 = points[0]
    x2, y2 = points[2]
    x3, y3 = points[1]
    x4, y4 = points[3]
    
    # Slopes of the diagonals
    m1 = (y2 - y1) / (x2 - x1)
    m2 = (y4 - y3) / (x4 - x3)
    
    # Intercept of the lines
    c1 = y1 - m1 * x1
    c2 = y3 - m2 * x3
    
    # Calculate the intersection point
    intersection_x = (c2 - c1) / (m1 - m2)
    intersection_y = m1 * intersection_x + c1
    
    return (intersection_x, intersection_y)

def overlay_images(base_path, overlay_path, base_anchor, overlay_anchor, scale=1.0):
    scale = math.sqrt(scale ** 2 / 2)
    
    # Load the base image in RGBA mode for transparency handling
    base_image = Image.open(base_path).convert("RGBA")
    
    # Load the overlay image and scale it, ensuring it is in RGBA mode
    overlay_image_original = Image.open(overlay_path).convert("RGBA")
    overlay_width_scaled, overlay_height_scaled = [int(scale * s) for s in overlay_image_original.size]
    overlay_image_scaled = overlay_image_original.resize((overlay_width_scaled, overlay_height_scaled), Image.Resampling.LANCZOS)
    
    # Calculate the new position for the overlay image to align the anchor points after scaling
    # The idea is to calculate the top-left position where the overlay image should be pasted
    overlay_anchor_scaled = (overlay_anchor[0] * scale, overlay_anchor[1] * scale)
    paste_x = base_anchor[0] - overlay_anchor_scaled[0]
    paste_y = base_anchor[1] - overlay_anchor_scaled[1]

    # Create a new image for the result to ensure transparency is handled correctly
    result_image = Image.new('RGBA', base_image.size)
    result_image.paste(base_image, (0, 0))  # Paste the base image first
    result_image.paste(overlay_image_scaled, (int(paste_x), int(paste_y)), overlay_image_scaled)  # Paste the scaled overlay
    
    # If the original base image was not in RGBA, convert the result back to its original mode
    if base_image.mode != "RGBA":
        result_image = result_image.convert("RGB")
    
    return result_image

def calculate_ssim(image_path1, image_path2):
    # Load the images
    image1 = imread(image_path1)
    image2 = imread(image_path2)

    # Convert the images to grayscale
    image1_gray = rgb2gray(image1)
    image2_gray = rgb2gray(image2)

    # Ensure data_range is specified for floating point image data
    data_range = max(image1_gray.max(), image2_gray.max()) - min(image1_gray.min(), image2_gray.min())

    # Compute SSIM between the two images
    ssim_index, _ = ssim(image1_gray, image2_gray, data_range=data_range, full=True)

    # Return the SSIM index
    return ssim_index

def normalize_data(value, min_value, max_value):
    normalized_value = (value - min_value) / (max_value - min_value)
    return normalized_value