import json
import octoprint.plugin
import flask
import os
from PIL import Image
from io import BytesIO
from octoprint_hologram import utlis
import requests

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
            dict(type="settings", custom_bindings=True)
        ]

    def get_assets(self):
        return dict(js=["js/hologram.js"])

    def get_api_commands(self):
        return {
            'get_snapshot': [],
            'save_points': ['points'],
            'update_image': ['value1', 'value2', 'value3', 'value4', 'value5']  # New command
        }


    def on_api_command(self, command, data):
        flask.current_app.logger.info(f"Received command: {command} with data: {data}")
        
        if command == "get_snapshot":
            snapshot_url = self._settings.global_get(["webcam", "snapshot"])
            if snapshot_url:
                return flask.jsonify(url=snapshot_url)
            else:
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
            
            v = self._settings.get(["update_image"])
            
            flask.current_app.logger.info(f"update_image: {v}")
            flask.current_app.logger.info(f"update_image 1: {v[1]}")
            
            
            arrow_img, pixel_coords = utlis.plot_arrow([0, 230, 0, 230, 0, 250], -8, -90, 0, 0.13)
            
            base_path = self.fetch_snapshot()
            overlay_path = arrow_img
            
            overlay_anchor = pixel_coords
            
            base_anchor = 4
            
            scale = 1.45
            
            result_image = utlis.overlay_images(base_path, overlay_path, base_anchor, overlay_anchor, scale)
            
            # Here you would add your logic to update the image based on slider values
            # For now, let's just respond with a placeholder image URL
            updated_image_url = result_image
            return flask.jsonify(url=updated_image_url)
        
        else:
            self._logger.info(f"Unknown command: {command}")
            return flask.jsonify({"error": "Unknown command"}), 400


    def fetch_snapshot(self):
        # Get the snapshot URL from the global settings
        snapshot_url = self._settings.global_get(["webcam", "snapshot"])
        if not snapshot_url:
            self._logger.error("Snapshot URL is not configured.")
            return None
        
        # Try to fetch the snapshot
        try:
            response = requests.get(snapshot_url, timeout=10)  # Adjust the timeout as needed
            response.raise_for_status()  # Raise an error for bad responses
            return response.content  # Return the content of the response (the image)
        except requests.exceptions.RequestException as e:
            self._logger.error(f"Failed to fetch snapshot: {e}")
            return None       

# Uncomment the below if you have update information
#     def get_update_information(self):
#         return {
#             "hologram": {
#                 "displayName": "Hologram Plugin",
#                 "displayVersion": self._plugin_version,
#                 "type": "github_release",
#                 "user": "YourGithubUsername",
#                 "repo": "OctoPrint-Hologram",
#                 "current": self._plugin_version,
#                 "pip": "https://github.com/YourGithubUsername/OctoPrint-Hologram/archive/{target_version}.zip"
#             }
#         }

__plugin_name__ = "Hologram Plugin"
__plugin_pythoncompat__ = ">=2.7,<4"
__plugin_implementation__ = HologramPlugin()
# __plugin_hooks__ = {
#     "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
# }
