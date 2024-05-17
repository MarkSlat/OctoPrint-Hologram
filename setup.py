# coding=utf-8

# Adjust these variables to match your plugin's information
plugin_identifier = "hologram"
plugin_package = "octoprint_%s" % plugin_identifier
plugin_name = "OctoPrint-Hologram"
plugin_version = "1.1.0"
plugin_description = "An OctoPrint plugin for generating and displaying holographic renders based on real-time parameters."
plugin_author = "Mark"
plugin_author_email = ""
plugin_url = "https://github.com/MarkSlat/OctoPrint-Hologram"
plugin_license = "AGPLv3"
plugin_requires = ["Pillow",
                   "matplotlib",
                   "numpy",
                   "pandas",
                   "seaborn",
                   "scikit-image",
                   "scipy"]

# Additional package data to install for this plugin. The subfolders "templates", "static" and "translations" will
# already be installed automatically if they exist.
plugin_additional_data = []

from setuptools import setup

try:
    import octoprint_setuptools
except:
    print("Could not import OctoPrint's setuptools, are you sure you are running that under "
          "the same python installation that OctoPrint is installed under?")
    import sys
    sys.exit(-1)

setup(**octoprint_setuptools.create_plugin_setup_parameters(
    identifier=plugin_identifier,
    package=plugin_package,
    name=plugin_name,
    version=plugin_version,
    description=plugin_description,
    author=plugin_author,
    mail=plugin_author_email,
    url=plugin_url,
    license=plugin_license,
    requires=plugin_requires,
    additional_data=plugin_additional_data
))
