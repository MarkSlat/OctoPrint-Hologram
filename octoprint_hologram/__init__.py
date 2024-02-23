import base64
import io
import json
import octoprint.plugin
import flask
import os
from PIL import Image
from io import BytesIO
from octoprint_hologram import utils, gcode_reader
import requests
from matplotlib import pyplot as plt

class HologramPlugin(octoprint.plugin.StartupPlugin,
                     octoprint.plugin.SettingsPlugin,
                     octoprint.plugin.TemplatePlugin,
                     octoprint.plugin.AssetPlugin,
                     octoprint.plugin.SimpleApiPlugin):

    def get_settings_defaults(self):
        return {
            "pixels": [],  # Default empty list to store pixel values
            "slider_values": [50, 50, 50, 50, 50]  # Default values for sliders
        }

    def on_after_startup(self):
        self._logger.info("Hologram plugin started!")

    def get_template_configs(self):
        return [
            dict(type="settings", template="hologram_settings.jinja2"),
            dict(type="tab", template="hologram_tab.jinja2")
        ]

    def get_assets(self):
        return dict(js=["js/hologram.js"])

    def get_api_commands(self):
        return {
            'get_snapshot': [],
            'save_points': ['points'],
            'update_image': ['value1', 'value2', 'value3', 'value4', 'value5'],  # New command
            'get_base64_image': []
        }

    def on_api_command(self, command, data):
        # flask.current_app.logger.info(f"Received command: {command} with data: {data}")
       
        if command == "get_snapshot":
            snapshot_url = self._settings.global_get(["webcam", "snapshot"])
            
                # Get the plugin's data folder
            data_folder = self.get_plugin_data_folder()
            # Define the path to the snapshot file within the plugin's data folder
            snapshot_path = os.path.join(data_folder, 'snapshot.jpg')
            
            snapshot_url = self._settings.global_get(["webcam", "snapshot"])
                
                
            # Try to fetch the snapshot
            try:
                response = requests.get(snapshot_url, timeout=10)  # Adjust the timeout as needed
                response.raise_for_status()  # Raise an error for bad responses
                
                # Save the fetched snapshot locally for future use
                with open(snapshot_path, 'wb') as f:
                    f.write(response.content)
                
                # Return the path to the newly saved snapshot
                return flask.jsonify(url=snapshot_url)
            except requests.exceptions.RequestException as e:
                self._logger.error(f"Failed to fetch snapshot from URL, attempting to create a default snapshot: {e}")

            return flask.make_response("Snapshot URL not configured", 404)
        
        elif command == "save_points":
            points = data.get("points", [])
            self._settings.set(["pixels"], points)
            self._settings.save()
            return flask.jsonify({"result": "success"})
        
        elif command == "update_image":
            # Store slider values in settings
            values = [data.get(f'value{i+1}', 50) for i in range(5)]
            self._settings.set(["slider_values"], values)
            self._settings.save()
            
            v = self._settings.get(["slider_values"])
            p = self._settings.get(["pixels"])
            
            # Convert slider values to float
            v = [float(val) for val in v]
            
            flask.current_app.logger.info(f"slider_values: {v}")  # Corrected to log slider values instead of pixels
            
            # Generate arrow image and get pixel coordinates
            arrow_img, pixel_coords = utils.plot_arrow([0, 230, 0, 230, 0, 250], *v[:4])
            
            # Fetch the base snapshot
            base_path = self.fetch_snapshot()
            overlay_path = arrow_img  # Assuming this is a path; adjust if it's an image object
            
            # Convert pixel information to coordinate pairs
            converted_points = [(point['x'], point['y']) for point in p]
            
            # Calculate the center point for the overlay
            base_anchor = utils.center_of_quadrilateral(converted_points)
            scale = v[4]  # Scale for overlay
            
            # Combine the base image with the overlay
            result_image = utils.overlay_images(base_path, overlay_path, base_anchor, pixel_coords, scale)
            
            # Before saving the result_image, convert it from RGBA to RGB if necessary
            if result_image.mode == 'RGBA':
                result_image = result_image.convert('RGB')

            
            # Save the updated image to the plugin's data folder and create a URL for it
            result_image_path = os.path.join(self.get_plugin_data_folder(), 'updated_image.jpg')
            result_image.save(result_image_path)  # Make sure result_image is a PIL image object
            
            img_byte_arr = BytesIO()
            result_image.save(img_byte_arr, format='JPEG')  # Or PNG, depending on your needs
            img_byte_arr = img_byte_arr.getvalue()

            # Encode the byte stream in Base64
            img_base64 = base64.b64encode(img_byte_arr).decode('utf-8')

            # Return the Base64-encoded image as part of the JSON response
            return flask.jsonify(image_data=f"data:image/jpeg;base64,{img_base64}")

        elif command == "get_base64_image":
            # Path to your image. Replace 'your_image.jpg' with your actual image path
            image_path = os.path.join(self.get_plugin_data_folder(), 'snapshot.jpg')
            # gcode_path = os.path.join(self.get_plugin_data_folder(), 'octo.gcode')
            gcode_path = os.path.join(os.path.dirname(__file__), "static", "data", "octo.gcode")
            
            gcode_R = gcode_reader.GcodeReader(filename=gcode_path)
            
            fig, ax = gcode_R.plot()
            
            v = self._settings.get(["slider_values"])
            v = [float(val) for val in v]
            
            p = self._settings.get(["pixels"])
            
            # Convert pixel information to coordinate pairs
            converted_points = [(point['x'], point['y']) for point in p]
            
            # Calculate the center point for the overlay
            base_anchor = utils.center_of_quadrilateral(converted_points)            

            # Set axis limits and view
            ax.set_xlim(0, 230)
            ax.set_ylim(0, 230)
            ax.set_zlim(0, 250)
            ax.view_init(elev=v[0], azim=v[1], roll=v[2])

            # ax.set_proj_type(proj_type='persp', focal_length=1.234)
            ax.set_proj_type(proj_type='persp', focal_length=v[3])

            # Example usage:
            x_input = 115
            y_input = 115
            z_input = 0

            ax.set_axis_off()

            pixel_coords = utils.get_pixel_coords(ax, x_input, y_input, z_input)
            # print("Pixel Coordinates:", pixel_coords)
            
            overlay_img = io.BytesIO()
    

            fig.savefig(overlay_img, format='png', transparent=True)
            # fig.canvas.print_png(arrow_img)

            # Rewind the buffer to the beginning
            overlay_img.seek(0)
            
            plt.close()

            result_image = utils.overlay_images(image_path, overlay_img, base_anchor, pixel_coords, v[4])
            # result_image.show()
            
            rgb_image = Image.new("RGB", result_image.size)
            # Paste the result_image onto rgb_image to effectively remove the alpha channel
            rgb_image.paste(result_image, mask=result_image.split()[3])  # 3 is the index of the alpha channel
            result_image = rgb_image  # Use this RGB image for further operations
            
            img_byte_arr = BytesIO()
            result_image.save(img_byte_arr, format='JPEG')  # Save the image as JPEG to the BytesIO object
            img_byte_arr = img_byte_arr.getvalue()  # Get the binary image data from the BytesIO object

            # Encode the binary data to Base64
            
            # Format the Base64 string and return it in a JSON respons
            
            try:
                # Open the image, convert it to a Base64 string
                encoded_string = base64.b64encode(img_byte_arr).decode('utf-8')  # Decode the Base64 bytes to a string
                # Return the Base64-encoded string
                return flask.jsonify(image_data=f"data:image/jpeg;base64,{encoded_string}")
            except Exception as e:
                self._logger.error(f"Failed to encode image: {e}")
                return flask.make_response("Failed to process image", 500)

        elif command == "process_gcode":
            gcode_path = data.get("gcodeFilePath", "")
            # Here you can add the logic to process the G-code file
            # For simplicity, this example just logs the file path
            self._logger.info(f"Processing G-code file at: {gcode_path}")
            # Implement your G-code processing logic here
            # After processing, you can return a success message or any result of the processing
            return flask.jsonify({"result": "success", "message": "G-code file processed successfully"})


        else:
            self._logger.info(f"Unknown command: {command}")
            return flask.jsonify({"error": "Unknown command"}), 400


    def fetch_snapshot(self):
        # Get the plugin's data folder
        data_folder = self.get_plugin_data_folder()
        # Define the path to the snapshot file within the plugin's data folder
        snapshot_path = os.path.join(data_folder, 'snapshot.jpg')
        
        # Check if the snapshot file exists locally in the plugin's data folder
        if os.path.isfile(snapshot_path):
            self._logger.info("Using local snapshot from plugin data folder.")
            # If the file exists, return the path to the local file
            return snapshot_path
        else:
            # If the file does not exist locally, proceed to fetch from the configured URL
            snapshot_url = self._settings.global_get(["webcam", "snapshot"])
            if snapshot_url:
                # Try to fetch the snapshot
                try:
                    response = requests.get(snapshot_url, timeout=10)  # Adjust the timeout as needed
                    response.raise_for_status()  # Raise an error for bad responses
                    
                    # Save the fetched snapshot locally for future use
                    with open(snapshot_path, 'wb') as f:
                        f.write(response.content)
                    
                    # Return the path to the newly saved snapshot
                    return snapshot_path
                except requests.exceptions.RequestException as e:
                    self._logger.error(f"Failed to fetch snapshot from URL, attempting to create a default snapshot: {e}")
            
            # If URL is not configured or fetching failed, create a default image and save it
            try:
                from PIL import Image
                # Create a default image (you can customize this as per your needs)
                img = Image.new('RGB', (640, 480), color = (73, 109, 137))
                img.save(snapshot_path)
                self._logger.info("Created a default snapshot.")
                return snapshot_path
            except Exception as e:
                self._logger.error(f"Failed to create a default snapshot: {e}")
                return None
            
# Uncomment the below if you have update information
    def get_update_information(self):
        return {
            "hologram": {
                "displayName": "Hologram Plugin",
                "displayVersion": self._plugin_version,
                "type": "github_release",
                "user": "MarkSlat",
                "repo": "OctoPrint-Hologram",
                "current": self._plugin_version,
                # "pip": "https://github.com/MarkSlat/OctoPrint-Hologram/archive/{target_version}.zip"
            }
        }

__plugin_name__ = "Hologram Plugin"
__plugin_pythoncompat__ = ">=3.7,<4"
__plugin_implementation__ = HologramPlugin()
__plugin_hooks__ = {
    "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
}
