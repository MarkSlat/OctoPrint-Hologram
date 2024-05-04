import base64
import io
import math
import os
import matplotlib; matplotlib.use('Agg')
import numpy as np
from io import BytesIO
from matplotlib import pyplot as plt
from octoprint.events import Events
import requests
from PIL import Image, ImageDraw
import flask
import octoprint.plugin
from scipy.spatial import ConvexHull

from octoprint_hologram import utils, gcode_reader

class HologramPlugin(octoprint.plugin.StartupPlugin,
                     octoprint.plugin.SettingsPlugin,
                     octoprint.plugin.TemplatePlugin,
                     octoprint.plugin.AssetPlugin,
                     octoprint.plugin.SimpleApiPlugin,
                     octoprint.plugin.ProgressPlugin,
                     octoprint.plugin.EventHandlerPlugin,
                     octoprint.plugin.BlueprintPlugin):
    """
    An OctoPrint plugin to enhance 3D printing with holographic projections.
    """
    def __init__(self):
        self.query_position = False
        self.current_position = {"X": 0.0, "Y": 0.0, "Z": 0.0, "E": 0.0}
        self.max_height = 0
        self.max_layer = 0
        self.gcode_path = ""
        self.baseline_ssim = 0
        self.ssim_scores = []
        self.extruder_points = []

    def get_settings_defaults(self):
        """Define default settings for the plugin."""
        return {
            "pixels": [],
            "slider_values": [1, 1, 1, 1, 1],  # Default slider values
            "colorHex": "white",
            "printerLength": 0,
            "printerWidth": 0,
            "printerDepth": 0,
            "extruder_X": [-30, 40],
            "extruder_Y": [-20, 30],
            "extruder_Z": [0, 70]
        }

    def on_after_startup(self):
        """Log startup message."""
        self._logger.info("Hologram plugin started!")
        self._storage_interface = self._file_manager._storage("local")
        
        plt.figure(figsize=(10, 5))
        # With an empty ssim_scores, plot an empty graph with a disabled message
        plt.text(0.5, 0.5, 'Disabled function or print not initiated',
        horizontalalignment='center', verticalalignment='center',
        fontsize=12, color='red', transform=plt.gca().transAxes)
        
        plt.title('SSIM Scores')
        plt.xlabel('Observation Number')
        plt.ylabel('SSIM Score')
        plt.grid(True)

        # Save the figure
        data_folder = self.get_plugin_data_folder()
        snapshot_path = os.path.join(data_folder, 'ssimChart.jpg')
        plt.savefig(snapshot_path, format='jpeg', dpi=300)

        # Close the plot figure to free up memory
        plt.close()

    def get_template_configs(self):
        """Define plugin template configurations."""
        return [
            {"type": "settings", "template": "hologram_settings.jinja2"},
            {"type": "tab", "template": "hologram_tab.jinja2"}
        ]

    def get_assets(self):
        """Define web assets used by the plugin."""
        return {"js": ["js/hologram.js"],
                "css": ["css/hologram.css"]}

    def get_api_commands(self):
        """Define API commands the plugin responds to."""
        return {
            'get_snapshot': [],  # No parameters expected for getting a snapshot
            'save_points': ['points'],  # Expects a list of points
            'fetchRender': ['gcodeFilePath'],  # Expects the path to the G-code file
            'set_color': ['colorHex'],
            'update_printer_dimensions': ['printerLength', 'printerWidth', 'printerDepth'],  # Printer dimensions
            'update_extruder_dimensions': ['extruderXMin', 'extruderXMax', 'extruderYMin', 'extruderYMax', 'extruderZMin', 'extruderZMax'],
            'update_image': ['value1', 'value2', 'value3', 'value4', 'value5'],
            'save_off_set': ['value1', 'value2', 'value3', 'value4', 'value5'],
            'set_enhanced_mode': ['enabled']  # Enhanced mode state toggle
        }

        
    def on_event(self, event, payload):
        # if event == Events.PRINT_STARTED:
        #     self._logger.info("Print started creating render")
            
        if event == Events.FILE_SELECTED:
            self._logger.info("File Selected: {}".format(payload["path"]))
            self.gcode_path = payload["path"]
            
        
    def on_print_progress(self, storage, path, progress):
        if self._storage_interface.file_exists(path):
            self.gcode_path = self._storage_interface.path_on_disk(path)

        if progress % 5 == 0:
            self.query_position = True
            
            if progress == 0:
                self.baseline_ssim = self.simm_compare(layer=-1)
                self.ssim_scores = []
            else:    
                layer = math.ceil(((self.current_position["Z"]) / (self.max_height)) * self.max_layer)
                value = utils.normalize_data(self.simm_compare(layer=layer), self.baseline_ssim, 1)
                self.ssim_scores.append(value)
                
                # self._logger.info("SSIM score:{}".format(value))
                
                # Assuming self.ssim_scores is filled with data

                plt.figure(figsize=(10, 5))
                plt.plot(self.ssim_scores, marker='o', linestyle='-', color='g')
                plt.title(f'SSIM Scores for {path}')
                plt.xlabel('Observation Number')
                plt.ylabel('SSIM Score')
                plt.grid(True)

                # Save the figure
                data_folder = self.get_plugin_data_folder()
                snapshot_path = os.path.join(data_folder, 'ssimChart.jpg')
                plt.savefig(snapshot_path, format='jpeg', dpi=300)

                # Close the plot figure to free up memory
                plt.close()
    
    @octoprint.plugin.BlueprintPlugin.route("/ssim_chart", methods=["GET"])
    def get_ssim_chart(self):
        """Serve the latest SSIM chart image."""
        data_folder = self.get_plugin_data_folder()
        image_path = 'ssimChart.jpg'
        full_path = os.path.join(data_folder, image_path)
        if not os.path.isfile(full_path):
            self._logger.info("Requested SSIM chart not found.")
            flask.abort(404, description="File not found.")
        return flask.send_from_directory(data_folder, image_path, as_attachment=False)

    def on_api_command(self, command, data):
        """Route API commands to their respective handlers."""
        
        self._logger.info(f"Command: {command} Data: {data}")
        
        if command == "get_snapshot":
            return self.handle_get_snapshot()
        elif command == "update_printer_dimensions":
            return self.update_printer_dimensions(data)
        elif command == "update_extruder_dimensions":
            return self.update_extruder_dimensions(data)
        elif command == "save_points":
            return self.save_points(data)
        elif command == "update_image":
            return self.update_image(data)
        elif command == "save_off_set":
            return self.save_off_set(data)
        elif command == "set_color":
            return self.set_color(data)
        elif command == "fetchRender":
            return self.fetch_render(data)
        else:
            self._logger.info(f"Unknown command: {command}")
            return flask.jsonify({"error": "Unknown command"}), 400

    def handle_get_snapshot(self):
        try:
            image_data = self.take_snapshot(save=True)
            if image_data is None:
                raise Exception("No image data returned.")

            encoded_string = base64.b64encode(image_data).decode('utf-8')
            return flask.jsonify(image_data=f"data:image/jpeg;base64,{encoded_string}")
        except Exception as e:
            self._logger.error(f"Failed to encode image: {e}")
            return flask.make_response("Failed to process image", 500)

    def update_printer_dimensions(self, data):
        """Update printer dimensions from API command data."""
        self._settings.set(["printerLength"], data.get('printerLength'))
        self._settings.set(["printerWidth"], data.get('printerWidth'))
        self._settings.set(["printerDepth"], data.get('printerDepth'))
        self._settings.save()
        return flask.jsonify({"result": "success", "message": "Printer dimensions updated successfully"})
    
    def update_extruder_dimensions(self, data):
        """Update extruder dimensions from API command data."""
        # Update X-axis range
        self._settings.set(["extruder_X"], [data.get('extruderXMin'), data.get('extruderXMax')])
        # Update Y-axis range
        self._settings.set(["extruder_Y"], [data.get('extruderYMin'), data.get('extruderYMax')])
        # Update Z-axis range
        self._settings.set(["extruder_Z"], [data.get('extruderZMin'), data.get('extruderZMax')])
        
        self._settings.save()
        return flask.jsonify({"result": "success", "message": "Extruder dimensions updated successfully"})

    def save_points(self, data):
        """Save points data to plugin settings."""
        self._settings.set(["pixels"], data.get("points", []))
        self._settings.save()
        
        points = self._settings.get(["pixels"])

        converted_points = [(point['x'], point['y']) for point in points]
        
        printer_dims = (float(self._settings.get(["printerLength"])),
                        float(self._settings.get(["printerWidth"])),
                        float(self._settings.get(["printerDepth"])))
        
        
        elevation, azimuth, roll, focal_length, scale = utils.optimize_projection(converted_points, printer_dims)
        
        # self._logger.info(f"Values: {elevation} {azimuth} {roll} {focal_length} {scale}")
        
        values = [float(elevation), float(azimuth), float(roll), float(focal_length), float(scale)]
        
        self._settings.set(["slider_values"], values)
        self._settings.save()
        
        return flask.jsonify({"result": "success"})

    def update_image(self, data):
        """Update the image based on given slider values."""
        
        limits = [(-360, 360), (-360, 360), (-179, 179), (0.075, 1), (0.1, 5)]

        # Retrieve current slider values
        current_values = self._settings.get(["slider_values"])

        # Calculate new slider values by adding offsets from the data and clipping them within individual limits
        values = [max(limits[i][0], min(limits[i][1], current_values[i] + float(data.get(f'value{i+1}', 0)))) for i in range(5)]

        # Assuming plot_arrow generates an image based on the printer dimensions and slider values
        printer_dims = [0, int(self._settings.get(["printerLength"])),
                        0, int(self._settings.get(["printerWidth"])),
                        0, int(self._settings.get(["printerDepth"]))]
        
        # Generate an arrow image based on the current settings (this function must be implemented)
        arrow_img, pixel_coords = utils.plot_arrow(printer_dims, *values[:4])

        # Fetch base snapshot for overlay
        data_folder = self.get_plugin_data_folder()  # Replace with the actual method to get the data folder
        snapshot_path = os.path.join(data_folder, 'snapshot.jpg')
        
        points = self._settings.get(["pixels"])
        converted_points = [(point['x'], point['y']) for point in points]
        
        base_anchor = utils.center_of_quadrilateral(converted_points)
        
        snapshot_img = Image.open(snapshot_path).convert("RGBA")
        
        result_image = utils.overlay_images(snapshot_img, arrow_img, base_anchor, pixel_coords, scale=(math.sqrt(2) * values[4]))

        rgb_image = Image.new("RGB", result_image.size)

        rgb_image.paste(result_image, mask=result_image.split()[3])
        result_image = rgb_image
        
        img_byte_arr = BytesIO()
        result_image.save(img_byte_arr, format='JPEG')
        img_byte_arr = img_byte_arr.getvalue()
        
        encoded_string = base64.b64encode(img_byte_arr).decode('utf-8')

        return flask.jsonify(image_data=f"data:image/jpeg;base64,{encoded_string}")
    
    def save_off_set(self, data):        
        limits = [(-360, 360), (-360, 360), (-179, 179), (0.075, 1), (0.1, 5)]

        # Retrieve current slider values
        current_values = self._settings.get(["slider_values"])

        # Calculate new slider values by adding offsets from the data and clipping them within individual limits
        values = [max(limits[i][0], min(limits[i][1], current_values[i] + float(data.get(f'value{i+1}', 0)))) for i in range(5)]
        
        # Update the slider values in settings
        self._settings.set(["slider_values"], values)
        self._settings.save()
        
    def set_color(self, data):
        self._settings.set(["colorHex"], data.get("colorHex", []))
        self._settings.save()
    
    def fetch_render(self, data):
        """Render a visualization from a G-code file and overlay it onto the snapshot."""
        gcode_path = data.get("gcodeFilePath", "")
        
        gcode_path = self.gcode_path
        
        if not gcode_path.endswith('.gcode'):
            return flask.make_response("Failed to locate file", 500)
        
        if not self._storage_interface.file_exists(gcode_path):
            return flask.make_response("Failed to locate file", 400)
        
        gcode_path = self._storage_interface.path_on_disk(gcode_path)
        
        self.gcode_path = gcode_path
        
        # Fetch base snapshot for overlay        
        image_data = self.take_snapshot(save=False)

        # Convert the bytes data to a file-like object
        image_data_io = BytesIO(image_data)

        # Now, you can use this file-like object with PIL as if it was a file
        snapshot_path = Image.open(image_data_io).convert("RGBA")

        # Load G-code and generate a plot
        p = self._settings.get(["pixels"])
        
        # Convert pixel information to coordinate pairs
        converted_points = [(point['x'], point['y']) for point in p]
        
        v = self._settings.get(["slider_values"])
        v = [float(val) for val in v]
        
        # Calculate the center point for the overlay
        base_anchor = utils.center_of_quadrilateral(converted_points)
        
        overlay_img, pixel_coords = self.create_render(layer=-1)

        result_image = utils.overlay_images(snapshot_path, overlay_img, base_anchor, pixel_coords, v[4])
        
        rgb_image = Image.new("RGB", result_image.size)

        rgb_image.paste(result_image, mask=result_image.split()[3])
        result_image = rgb_image
        
        img_byte_arr = BytesIO()
        result_image.save(img_byte_arr, format='JPEG')
        img_byte_arr = img_byte_arr.getvalue()
        
        try:
            encoded_string = base64.b64encode(img_byte_arr).decode('utf-8')
            return flask.jsonify(image_data=f"data:image/jpeg;base64,{encoded_string}")
        except Exception as e:
            self._logger.error(f"Failed to encode image: {e}")
            return flask.make_response("Failed to process image", 500)

    def take_snapshot(self, save=False):
        snapshot_url = self._settings.global_get(["webcam", "snapshot"])
        try:
            response = requests.get(snapshot_url, timeout=10)
            response.raise_for_status()

            if save:
                data_folder = self.get_plugin_data_folder()
                snapshot_path = os.path.join(data_folder, 'snapshot.jpg')
                with open(snapshot_path, 'wb') as f:
                    f.write(response.content)
                return response.content
            else:
                return response.content
        except requests.exceptions.RequestException as e:
            self._logger.error(f"Failed to fetch snapshot: {e}")
            raise Exception(f"Failed to fetch snapshot due to request exception: {e}")
        
    def hook_gcode_queuing(self, comm_instance, phase, cmd, cmd_type, gcode, subcode=None, tags=None, *args, **kwargs):        
        if self.query_position == True:
            self.query_position = False
            return [("M114",), (cmd, cmd_type, tags)]
        
    def hook_gcode_received(self, comm_instance, line, *args, **kwargs):
        # Check if the line contains position information, excluding lines that only include "Count X:..."
        if "X:" not in line or "Count X:" not in line:
            return line

        # Split the line at " Count" to ignore the stepper motor count values
        line = line.split(" Count")[0]

        # Parse the position from the part of the line before "Count"
        try:
            parts = line.split(' ')
            # This creates a dictionary for each coordinate by splitting at ':' and converting the second part to float
            self.current_position = {part.split(':')[0]: float(part.split(':')[1]) for part in parts if ':' in part}
            # self._logger.info("Current position updated: {}".format(self.current_position))
        except Exception as e:
            self._logger.error("Error parsing position: {}".format(e))

        return line
    
    def create_render(self, layer=-1):
        gcode_R = gcode_reader.GcodeReader(self.gcode_path)

        # Inject the getter functions directly into GcodeReader class
        gcode_reader.GcodeReader.get_layer = lambda self: self.n_layers + 1
        gcode_reader.GcodeReader.get_limits = lambda self: self.xyzlimits

        _, _, _, _, _, self.max_height = gcode_R.get_limits()
        self.max_layer = gcode_R.get_layer()

        self._logger.info(f"Max layers {self.max_layer}")

        if layer == -1 or layer > self.max_layer:
            layer = self.max_layer

        self._logger.info(f"Using layer {layer}")

        color = self._settings.get(["colorHex"])
        fig, ax = gcode_R.plot_layers(min_layer=1, max_layer=layer, color=color)

        v = [float(val) for val in self._settings.get(["slider_values"])]

        # Set axis limits and view
        printer_length = int(self._settings.get(["printerLength"]))
        printer_width = int(self._settings.get(["printerWidth"]))
        printer_depth = int(self._settings.get(["printerDepth"]))

        max_range = max(printer_length, printer_width, printer_depth)
        ax.set_box_aspect([printer_length / max_range, printer_width / max_range, printer_depth / max_range])

        ax.set_xlim(0, printer_length)
        ax.set_ylim(0, printer_width)
        ax.set_zlim(0, printer_depth)
        ax.view_init(elev=v[0], azim=v[1], roll=v[2])
        ax.set_proj_type(proj_type='persp', focal_length=v[3])

        ax.set_axis_off()
        pixel_coords = utils.get_pixel_coords(ax, printer_length / 2, printer_width / 2, 0)

        if layer != self.max_layer:  # Skip masking for the maximum layer
            self._logger.info("Applying mask for extruder points")
            self.apply_mask(ax, fig, layer)

        overlay_img = io.BytesIO()
        fig.savefig(overlay_img, format='png', transparent=True)
        plt.close()
        
        overlay_img.seek(0)
        
        self.roi_coords = utils.find_non_transparent_roi(overlay_img)

        overlay_img.seek(0)
        return overlay_img, pixel_coords

    def apply_mask(self, ax, fig, layer):
        extruder_X = [float(x) for x in self._settings.get(["extruder_X"])]
        extruder_Y = [float(y) for y in self._settings.get(["extruder_Y"])]
        extruder_Z = [float(z) for z in self._settings.get(["extruder_Z"])]

        points = [
            (self.current_position["X"] + dx, self.current_position["Y"] + dy, self.current_position["Z"] + dz)
            for dx in extruder_X
            for dy in extruder_Y
            for dz in extruder_Z
        ]

        self.extruder_points = [utils.get_pixel_coords(ax, *point) for point in points]
        
        points = np.array(self.extruder_points)
        hull = ConvexHull(points)
        
        overlay_img = io.BytesIO()
        fig.savefig(overlay_img, format='png', transparent=True)
        overlay_img.seek(0)
        
        image_pil = Image.open(overlay_img).convert("RGBA")
        
        mask_img = Image.new('L', image_pil.size, 0)
        draw = ImageDraw.Draw(mask_img)
        draw.polygon([tuple(points[vertex]) for vertex in hull.vertices], fill=255)
        
        transparent_area = Image.new('RGBA', image_pil.size, (0, 0, 0, 0))
        image_pil.paste(transparent_area, mask=mask_img)
        
        overlay_img_modified = io.BytesIO()
        image_pil.save(overlay_img_modified, format='PNG')
        overlay_img_modified.seek(0)
    
    def simm_compare(self, layer):      
        # Fetch base snapshot for overlay        
        image_data = self.take_snapshot(save=False)
        
        overlay_img, pixel_coords = self.create_render(layer=layer)

        # Convert the bytes data to a file-like object
        image_data_io = BytesIO(image_data)

        # Now, you can use this file-like object with PIL as if it was a file
        snapshot_path = Image.open(image_data_io).convert("RGBA")

        # Load G-code and generate a plot
        p = self._settings.get(["pixels"])
        
        # Convert pixel information to coordinate pairs
        converted_points = [(point['x'], point['y']) for point in p]
        
        v = self._settings.get(["slider_values"])
        v = [float(val) for val in v]
        
        # Calculate the center point for the overlay
        base_anchor = utils.center_of_quadrilateral(converted_points)

        result_image = utils.overlay_images(snapshot_path, overlay_img, base_anchor, pixel_coords, v[4])
        
        # Translate the top-left corner of the ROI
        translated_min_x, translated_min_y = utils.translate_overlay_point(
            self.roi_coords[0], self.roi_coords[1], base_anchor, pixel_coords, v[4])

        # Translate the bottom-right corner of the ROI
        translated_max_x, translated_max_y = utils.translate_overlay_point(
            self.roi_coords[2], self.roi_coords[3], base_anchor, pixel_coords, v[4])

        # Create a new tuple for self.roi_coords with the updated coordinates
        translated_roi_coords = (translated_min_x, translated_min_y, translated_max_x, translated_max_y)

        # Crop the images according to self.roi_coords before SSIM calculation
        cropped_result_image = result_image.crop(translated_roi_coords)
        cropped_snapshot_path = snapshot_path.crop(translated_roi_coords)
        
        # Save the images for debugging
        # debug_folder = "C:\\Users\\mark-\\AppData\\Roaming\\OctoPrint\\data\\hologram\\debug"
        debug_folder = self.get_plugin_data_folder()
        if not os.path.exists(debug_folder):
            os.makedirs(debug_folder)
        cropped_snapshot_path.save(os.path.join(debug_folder, f"snapshot_layer_{layer}.png"), "PNG")
        cropped_result_image.save(os.path.join(debug_folder, f"result_layer_{layer}.png"), "PNG")

        # Calculate SSIM on the cropped images
        score = utils.calculate_ssim(cropped_result_image, cropped_snapshot_path)
        
        self._logger.info("SSIM: {}".format(score))
        
        return score


    def get_update_information(self):
        return {
            "hologram": {
                "displayName": "Hologram Plugin",
                "displayVersion": self._plugin_version,
                "type": "github_release",
                "user": "MarkSlat",
                "repo": "OctoPrint-Hologram",
                "current": self._plugin_version,
                "pip": "https://github.com/MarkSlat/OctoPrint-Hologram/archive/{target_version}.zip"
            }
        }

# Plugin hooks and metadata
__plugin_name__ = "Hologram"
__plugin_pythoncompat__ = ">=3.7,<4"
__plugin_implementation__ = HologramPlugin()
__plugin_hooks__ = {
    "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
    "octoprint.comm.protocol.gcode.received": __plugin_implementation__.hook_gcode_received,
    "octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.hook_gcode_queuing
}
