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
                     octoprint.plugin.SimpleApiPlugin):
    """
    An OctoPrint plugin to enhance 3D printing with holographic projections.
    """

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
        """Fetch a snapshot from the webcam and save it locally."""
        snapshot_url = self._settings.global_get(["webcam", "snapshot"])
        data_folder = self.get_plugin_data_folder()
        snapshot_path = os.path.join(data_folder, 'snapshot.jpg')
        try:
            response = requests.get(snapshot_url, timeout=10)
            response.raise_for_status()
            with open(snapshot_path, 'wb') as f:
                f.write(response.content)
            return flask.jsonify(url=snapshot_url)
        except requests.exceptions.RequestException as e:
            self._logger.error(f"Failed to fetch snapshot: {e}")
            return flask.make_response("Snapshot URL not configured or fetch failed", 404)

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
        
        result_image = utils.overlay_images(snapshot_path, arrow_img, base_anchor, pixel_coords, scale=values[4])

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
        data_folder = self.get_plugin_data_folder()  # Replace with the actual method to get the data folder
        snapshot_path = os.path.join(data_folder, 'snapshot.jpg')

        # Load G-code and generate a plot
        gcode_R = gcode_reader.GcodeReader(gcode_path)
        
        # Define getter function
        def get_layer(self):
            return self.n_layers + 1

        # Inject the getter function
        gcode_reader.GcodeReader.get_layer = get_layer
            
        fig, ax = gcode_R.plot_layers(min_layer=1, max_layer=gcode_R.get_layer())
        
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
    "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
}
