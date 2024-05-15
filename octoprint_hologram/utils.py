import io
import math
import matplotlib; matplotlib.use('Agg')
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d import proj3d
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from PIL import Image
import numpy as np
from skimage.metrics import structural_similarity as ssim
from skimage.io import imread
from skimage.color import rgb2gray
from scipy.optimize import basinhopping

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

def overlay_images(base_path, overlay_path, base_anchor, overlay_anchor, scale):
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
    result_image = Image.new('RGBA', base_path.size)
    result_image.paste(base_path, (0, 0))  # Paste the base image first
    result_image.paste(overlay_image_scaled, (int(paste_x), int(paste_y)), overlay_image_scaled)  # Paste the scaled overlay
        
    return result_image

def translate_overlay_point(x_overlay, y_overlay, base_anchor, overlay_anchor, scale):
    """
    Translates a point from the overlay image to the final image, considering scaling and anchor point alignment.

    Args:
    - x_overlay, y_overlay: Coordinates of the point on the overlay image.
    - base_anchor: The anchor point on the base image (tuple of x, y).
    - overlay_anchor: The anchor point on the overlay image before scaling (tuple of x, y).
    - scale: The scaling factor applied to the overlay image.

    Returns:
    - Tuple of (x_final, y_final): The translated coordinates of the point on the final image.
    """

    # Adjust the scale to consider diagonal scaling
    scale_adjusted = math.sqrt(scale ** 2 / 2)
    # scale_adjusted = scale

    # Calculate the scaled anchor position
    overlay_anchor_scaled_x = overlay_anchor[0] * scale_adjusted
    overlay_anchor_scaled_y = overlay_anchor[1] * scale_adjusted

    # Calculate the displacement needed to align the overlay's scaled anchor with the base anchor
    displacement_x = base_anchor[0] - overlay_anchor_scaled_x
    displacement_y = base_anchor[1] - overlay_anchor_scaled_y

    # Scale the point coordinates
    x_overlay_scaled = x_overlay * scale_adjusted
    y_overlay_scaled = y_overlay * scale_adjusted

    # Translate the scaled point based on the overlay's displacement
    x_final = displacement_x + x_overlay_scaled
    y_final = displacement_y + y_overlay_scaled

    return (int(x_final), int(y_final))

def calculate_ssim(image1, image2):
    # Convert PIL Images to numpy arrays
    image1_np = np.array(image1)
    image2_np = np.array(image2)
    
    # If the images have an alpha channel, discard it (assuming RGBA format)
    if image1_np.shape[-1] == 4:
        image1_np = image1_np[..., :3]
    if image2_np.shape[-1] == 4:
        image2_np = image2_np[..., :3]

    # Convert the images to grayscale
    image1_gray = rgb2gray(image1_np)
    image2_gray = rgb2gray(image2_np)

    # Ensure data_range is specified for floating point image data
    data_range = max(image1_gray.max(), image2_gray.max()) - min(image1_gray.min(), image2_gray.min())

    # Compute SSIM between the two images
    ssim_index = ssim(image1_gray, image2_gray, data_range=data_range)

    # Return the SSIM index
    return ssim_index

def normalize_data(value, min_value, max_value):
    normalized_value = (value - min_value) / (max_value - min_value)
    return normalized_value

def find_non_transparent_roi(image_path):
    # Load the image
    image = Image.open(image_path)
    
    # Ensure the image is in RGBA format for processing
    if image.mode != 'RGBA':
        raise ValueError("Image does not contain an alpha channel")

    image_np = np.array(image)

    # Separate the alpha channel
    alpha_channel = image_np[:, :, 3]

    # Find where the image is not transparent
    non_transparent = np.where(alpha_channel != 0)
    min_y, min_x = np.min(non_transparent, axis=1)
    max_y, max_x = np.max(non_transparent, axis=1)

    # Calculate the additional 5% for width and height
    additional_width = int((max_x - min_x) * 0.05)
    additional_height = int((max_y - min_y) * 0.05)

    # Adjust the ROI coordinates to add 5%, ensuring it does not exceed image bounds
    min_x = max(0, min_x - additional_width)
    min_y = max(0, min_y - additional_height)
    max_x = min(image_np.shape[1] - 1, max_x + additional_width)
    max_y = min(image_np.shape[0] - 1, max_y + additional_height)

    # The coordinates of the Region of Interest, adjusted
    roi_coords = (min_x, min_y, max_x, max_y)

    return roi_coords

def optimize_projection(converted_quad, printer_dimensions):
    # Define bounds and initial parameters
    bounds = [(-30, 120), (-180, 180), (-15, 15), (0.075, 1), (0.2, 4)]
    initial_params = [90, -90, 0, 1, 1]

    # Set up the 3D plot
    fig = plt.figure()
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111, projection='3d')
    
    # Unpack printer dimensions
    printer_length, printer_width, printer_depth = printer_dimensions
    
    # Set 3D box aspect and axis limits
    max_range = np.max([printer_length, printer_width, printer_depth])
    ax.set_box_aspect([printer_length/max_range, printer_width/max_range, printer_depth/max_range])
    ax.set_xlim(0, printer_length)
    ax.set_ylim(0, printer_width)
    ax.set_zlim(0, printer_depth)

    # Define the error computation function
    def compute_error(params):
        elevation, azimuth, roll, focal_length, scale = np.clip(params, [b[0] for b in bounds], [b[1] for b in bounds])
        
        ax.set_proj_type(proj_type='persp', focal_length=focal_length)
        ax.view_init(elev=elevation, azim=azimuth, roll=roll)

        canvas.draw()

        # Compute pixel coordinates
        corner_pixels = []
        corners = [(0, printer_length, 0), (printer_width, printer_length, 0), (printer_width, 0, 0), (0, 0, 0)]
        base_anchor = center_of_quadrilateral(converted_quad)
        center_pixel = get_pixel_coords(ax, printer_length/2, printer_width/2, 0)

        displacement_x = base_anchor[0] - center_pixel[0]
        displacement_y = base_anchor[1] - center_pixel[1]

        for corner in corners:
            pixel = get_pixel_coords(ax, *corner)
            x_final = displacement_x + pixel[0]
            y_final = displacement_y + pixel[1]

            scaled_x = base_anchor[0] + scale * (x_final - base_anchor[0])
            scaled_y = base_anchor[1] + scale * (y_final - base_anchor[1])
            scaled_point = (scaled_x, scaled_y)
            corner_pixels.append(scaled_point)

        # Calculate the error metric (sum of squared distances)
        error = 0
        for cp, gq in zip(corner_pixels, converted_quad):
            error += (cp[0] - gq[0])**2 + (cp[1] - gq[1])**2

        return error

    # Callback function to stop optimization when the error is less than 1
    def callback(x, f, accept):
        if f < 1:
            return True

    # Execute basinhopping with the callback
    minimizer_kwargs = {"method": "L-BFGS-B", "bounds": bounds}
    result = basinhopping(compute_error, initial_params, minimizer_kwargs=minimizer_kwargs, niter=5, stepsize=0.5, callback=callback)
    
    plt.close(fig)
    
    # Extract optimized parameters
    elevation, azimuth, roll, focal_length, scale = result.x
    return elevation, azimuth, roll, focal_length, scale