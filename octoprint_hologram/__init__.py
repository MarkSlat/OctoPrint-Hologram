import base64
import io
import os
from io import BytesIO
from matplotlib import pyplot as plt
import requests
from PIL import Image
import flask
import octoprint.plugin

from octoprint_hologram import utils, gcode_reader

class HologramPlugin(octoprint.plugin.StartupPlugin,
                     octoprint.plugin.SettingsPlugin,
                     octoprint.plugin.TemplatePlugin,
                     octoprint.plugin.AssetPlugin,
                     octoprint.plugin.SimpleApiPlugin,
                     octoprint.plugin.ProgressPlugin):
    """
    An OctoPrint plugin to enhance 3D printing with holographic projections.
    """
    def __init__(self):
        self.query_position = False
        self.current_position = {"X": 0.0, "Y": 0.0, "Z": 0.0, "E": 0.0}
        self.max_height = 0
        self.max_layer = 0

    def get_settings_defaults(self):
        """Define default settings for the plugin."""
        return {
            "pixels": [],
            "slider_values": [1, 1, 1, 1, 1],  # Default slider values
            "printerLength": 0,
            "printerWidth": 0,
            "printerDepth": 0,
        }

    def on_after_startup(self):
        """Log startup message."""
        self._logger.info("Hologram plugin started!")
        self._storage_interface = self._file_manager._storage("local")
        # self.current_layer = 0

    def get_template_configs(self):
        """Define plugin template configurations."""
        return [
            {"type": "settings", "template": "hologram_settings.jinja2"},
            {"type": "tab", "template": "hologram_tab.jinja2"}
        ]

    def get_assets(self):
        """Define web assets used by the plugin."""
        return {"js": ["js/hologram.js"]}

    def get_api_commands(self):
        """Define API commands the plugin responds to."""
        return {
            'get_snapshot': [],
            'save_points': ['points'],
            'update_image': ['value1', 'value2', 'value3', 'value4', 'value5'],
            'fetchRender': ['gcodeFilePath'],
            'update_printer_dimensions': ['printerLength', 'printerWidth', 'printerDepth']
        }
        
    def on_print_progress(self, storage, path, progress):
        # self._logger.info("New progress {}".format(progress))
        if progress % 5 == 0:
            self.query_position = True
        

    def on_api_command(self, command, data):
        """Route API commands to their respective handlers."""
        if command == "get_snapshot":
            return self.handle_get_snapshot()
        elif command == "update_printer_dimensions":
            return self.update_printer_dimensions(data)
        elif command == "save_points":
            return self.save_points(data)
        elif command == "update_image":
            return self.update_image(data)
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

    def save_points(self, data):
        """Save points data to plugin settings."""
        self._settings.set(["pixels"], data.get("points", []))
        self._settings.save()
        return flask.jsonify({"result": "success"})

    def update_image(self, data):
        """Update the image based on given slider values."""
        # Example logic to update an image based on slider values and save it
        values = [data.get(f'value{i+1}', 50) for i in range(5)]
        self._settings.set(["slider_values"], values)
        self._settings.save()

        # Assuming plot_arrow generates an image based on the printer dimensions and slider values
        printer_dims = [0, int(self._settings.get(["printerLength"])),
                        0, int(self._settings.get(["printerWidth"])),
                        0, int(self._settings.get(["printerDepth"]))]
        
        # Generate an arrow image based on the current settings (this function must be implemented)
        arrow_img, pixel_coords = utils.plot_arrow(printer_dims, *values[:4])

        # Fetch base snapshot for overlay
        data_folder = self.get_plugin_data_folder()  # Replace with the actual method to get the data folder
        snapshot_path = os.path.join(data_folder, 'snapshot.jpg')

        # Open the image file
        

        # Overlay the arrow image onto the base image
        # Assuming overlay_images combines two images into one
        
        points = self._settings.get(["pixels"])
        converted_points = [(point['x'], point['y']) for point in points]
        
        base_anchor = utils.center_of_quadrilateral(converted_points)
        
        snapshot_img = Image.open(snapshot_path).convert("RGBA")
        
        result_image = utils.overlay_images(snapshot_img, arrow_img, base_anchor, pixel_coords, scale=values[4])

        rgb_image = Image.new("RGB", result_image.size)

        rgb_image.paste(result_image, mask=result_image.split()[3])
        result_image = rgb_image
        
        img_byte_arr = BytesIO()
        result_image.save(img_byte_arr, format='JPEG')
        img_byte_arr = img_byte_arr.getvalue()
        
        encoded_string = base64.b64encode(img_byte_arr).decode('utf-8')

        return flask.jsonify(image_data=f"data:image/jpeg;base64,{encoded_string}")

    def fetch_render(self, data):
        """Render a visualization from a G-code file and overlay it onto the snapshot."""
        gcode_path = data.get("gcodeFilePath", "")
        
        if not gcode_path.endswith('.gcode'):
            return flask.make_response("Failed to locate file", 500)
        
        if not self._storage_interface.file_exists(gcode_path):
            return flask.make_response("Failed to locate file", 400)
        
        gcode_path = self._storage_interface.path_on_disk(gcode_path)
        
        flask.current_app.logger.info(f"path: {gcode_path}")       
        
        # Fetch base snapshot for overlay
        # data_folder = self.get_plugin_data_folder()  # Replace with the actual method to get the data folder
        # snapshot_path = os.path.join(data_folder, 'snapshot.jpg')
        
        image_data = self.take_snapshot(save=False)

        # Convert the bytes data to a file-like object
        image_data_io = BytesIO(image_data)

        # Now, you can use this file-like object with PIL as if it was a file
        snapshot_path = Image.open(image_data_io).convert("RGBA")

        # Load G-code and generate a plot
        gcode_R = gcode_reader.GcodeReader(gcode_path)
        
        # Define getter function
        def get_layer(self):
            return self.n_layers + 1

        def get_limits(self):
            return self.xyzlimits
        
        # Inject the getter function
        gcode_reader.GcodeReader.get_layer = get_layer
        
        gcode_reader.GcodeReader.get_limits = get_limits
        
        _, _, _, _, _, self.max_height = gcode_R.get_limits()
        
        self.max_layer = gcode_R.get_layer()
            
        fig, ax = gcode_R.plot_layers(min_layer=1, max_layer=self.max_layer)
        
        v = self._settings.get(["slider_values"])
        v = [float(val) for val in v]
        
        p = self._settings.get(["pixels"])
        
        # Convert pixel information to coordinate pairs
        converted_points = [(point['x'], point['y']) for point in p]
        
        # Calculate the center point for the overlay
        base_anchor = utils.center_of_quadrilateral(converted_points)            

        # Set axis limits and view
        printer_length = int(self._settings.get(["printerLength"]))
        printer_width = int(self._settings.get(["printerWidth"]))
        printer_depth = int(self._settings.get(["printerDepth"]))
        
        # Calculate required aspect ratio for equal scaling
        max_range = max(printer_length, printer_width, printer_depth)
        ax.set_box_aspect([printer_length/max_range, printer_width/max_range, printer_depth/max_range])
        
        ax.set_xlim(0, printer_length)
        ax.set_ylim(0, printer_width)
        ax.set_zlim(0, printer_depth)
        ax.view_init(elev=v[0], azim=v[1], roll=v[2])

        ax.set_proj_type(proj_type='persp', focal_length=v[3])

        x_input = printer_length/2
        y_input = printer_width/2
        z_input = 0

        ax.set_axis_off()

        pixel_coords = utils.get_pixel_coords(ax, x_input, y_input, z_input)
            
        overlay_img = io.BytesIO()
    

        fig.savefig(overlay_img, format='png', transparent=True)
        # fig.canvas.print_png(arrow_img)

        # Rewind the buffer to the beginning
        overlay_img.seek(0)
        
        plt.close()
        
        self.roi_coords = utils.find_non_transparent_roi(overlay_img)
        
        overlay_img.seek(0)

        result_image = utils.overlay_images(snapshot_path, overlay_img, base_anchor, pixel_coords, v[4])
        # result_image.show()
        
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
            self._logger.info("Current position updated: {}".format(self.current_position))
        except Exception as e:
            self._logger.error("Error parsing position: {}".format(e))

        return line

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
