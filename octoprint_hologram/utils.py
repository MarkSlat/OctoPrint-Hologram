import io
import matplotlib; matplotlib.use('Agg')
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d import proj3d
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from PIL import Image
import numpy as np
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