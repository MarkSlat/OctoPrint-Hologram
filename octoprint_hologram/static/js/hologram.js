$(function() {
    function HologramViewModel(parameters) {
        var self = this;

        self.printerStateViewModel = parameters[4];

        // Observables related to printer dimensions and images
        self.printerLength = ko.observable();
        self.printerWidth = ko.observable();
        self.printerDepth = ko.observable();
        self.snapshotUrl = ko.observable();
        self.displayImageUrl = ko.observable();
        self.updatedImageUrl = ko.observable();

        // Extruder dimensions
        self.extruderXMin = ko.observable(-20); // Default value for -X
        self.extruderXMax = ko.observable(20);  // Default value for +X
        self.extruderYMin = ko.observable(-20); // Default value for -Y
        self.extruderYMax = ko.observable(20);  // Default value for +Y
        self.extruderZMin = ko.observable(0);   // Default value for -Z
        self.extruderZMax = ko.observable(40);  // Default value for +Z

        // Observable array to manage points on the canvas
        self.points = ko.observableArray([
            { x: ko.observable(50), y: ko.observable(50) },
            { x: ko.observable(550), y: ko.observable(50) },
            { x: ko.observable(550), y: ko.observable(350) },
            { x: ko.observable(50), y: ko.observable(350) }
        ]);

        // To handle the selected point for moving
        self.selectedPoint = null;

        self.sliderValues = ko.observableArray([
            ko.observable(0.0), 
            ko.observable(0.0), 
            ko.observable(0.0), 
            ko.observable(0.0), 
            ko.observable(0.0)
        ]);

        // Enhanced mode toggle
        self.enhancedMode = ko.observable(false);

        // Observable for the color hex code
        self.colorHex = ko.observable("#ffffff"); // Default color

        // New observable for the SSIM chart image URL
        self.ssimChartUrl = ko.observable();

        // New observable for the SSIM chart image URL
        self.ssimChartUrl = ko.observable();

        // Periodic update function for the SSIM chart
        self.updateSsimChart = function(forceUpdate) {
            // Update if printing is true or if force update is specified
            if (self.printerStateViewModel.isPrinting() || forceUpdate) {
                var timestamp = new Date().getTime(); // Cache busting
                var newUrl = `/plugin/hologram/ssim_chart?time=${timestamp}`;
                self.ssimChartUrl(newUrl);
            }
        };

        // Initialize the periodic update for the SSIM chart
        setInterval(function() {
            self.updateSsimChart(false); // Regular updates without forcing
        }, 120000); // Update every 120 seconds

        // Initial update on load
        self.updateSsimChart(true); // Force update on load

        // Send printer dimensions to the server
        self.sendPrinterDimensions = function() {
            $.ajax({
                url: API_BASEURL + "plugin/hologram",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify({
                    command: "update_printer_dimensions",
                    printerLength: self.printerLength(),
                    printerWidth: self.printerWidth(),
                    printerDepth: self.printerDepth()
                }),
                success: function(response) {
                    console.log("Printer dimensions updated successfully.");
                },
                error: function() {
                    console.error("Failed to update printer dimensions.");
                }
            });
        };

        // Function to send extruder dimensions
        self.sendExtruderDimensions = function() {
            $.ajax({
                url: API_BASEURL + "plugin/hologram",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify({
                    command: "update_extruder_dimensions",
                    extruderXMin: self.extruderXMin(),
                    extruderXMax: self.extruderXMax(),
                    extruderYMin: self.extruderYMin(),
                    extruderYMax: self.extruderYMax(),
                    extruderZMin: self.extruderZMin(),
                    extruderZMax: self.extruderZMax()
                }),
                success: function(response) {
                    console.log("Extruder dimensions updated successfully.");
                },
                error: function() {
                    console.error("Failed to update extruder dimensions.");
                }
            });
        };

        // Fetch a snapshot from the server
        self.getSnapshot = function() {
            $.ajax({
                url: API_BASEURL + "plugin/hologram",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify({
                    command: "get_snapshot"
                }),
                success: function(response) {
                    self.snapshotUrl(response.image_data); // Set the new image URL from the response
                    $("#hologram-snapshot").one("load", function() {
                        self.initializeCanvas(); // Initialize the canvas once the image is loaded
                    }).each(function() {
                        if (this.complete) $(this).trigger('load');
                    });
                },
                error: function() {
                    alert("Failed to get snapshot");
                }
            });
        };

        // Initialize the canvas dimensions based on the loaded image
        self.initializeCanvas = function() {
            var img = document.getElementById('hologram-snapshot');
            var canvas = document.getElementById('overlay-canvas');
            canvas.width = img.clientWidth;
            canvas.height = img.clientHeight;
            self.drawQuadrilateral();
            $(canvas).css('pointer-events', 'auto'); // Make sure canvas is interactive
        };

        // Draw the quadrilateral based on the defined points
        self.drawQuadrilateral = function() {
            var canvas = document.getElementById('overlay-canvas');
            var ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.beginPath();
            self.points().forEach(function(point, index) {
                ctx[index === 0 ? 'moveTo' : 'lineTo'](point.x(), point.y());
            });
            ctx.closePath();
            ctx.strokeStyle = 'red';
            ctx.lineWidth = 2;
            ctx.stroke();
        };

        // Event handlers for mouse actions on the canvas
        self.mouseDown = function(data, event) {
            var canvas = document.getElementById('overlay-canvas');
            var rect = canvas.getBoundingClientRect();
            var mouseX = event.clientX - rect.left;
            var mouseY = event.clientY - rect.top;
            self.points().forEach(function(point) {
                if (Math.abs(point.x() - mouseX) < 10 && Math.abs(point.y() - mouseY) < 10) {
                    self.selectedPoint = point;
                }
            });
        };

        self.mouseMove = function(data, event) {
            if (self.selectedPoint) {
                var rect = event.target.getBoundingClientRect();
                var mouseX = event.clientX - rect.left;
                var mouseY = event.clientY - rect.top;
                self.selectedPoint.x(mouseX);
                self.selectedPoint.y(mouseY);
                self.drawQuadrilateral();
            }
        };

        self.mouseUp = function(data, event) {
            self.selectedPoint = null;
        };

        // Save the points back to the server
        self.savePoints = function() {
            var pointsData = ko.toJS(self.points).map(function(point) {
                return { x: point.x, y: point.y };
            });

            $.ajax({
                url: API_BASEURL + "plugin/hologram",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify({
                    command: "save_points",
                    points: pointsData
                }),
                success: function(response) {
                    console.log("Points saved successfully:", response);
                    alert("Points saved successfully!");
                },
                error: function(xhr) {
                    console.error("Failed to save points:", xhr.responseText);
                    alert("Failed to save points!");
                }
            });
        };

        // Fetch render based on the current G-code
        self.fetchRender = function() {
            $.ajax({
                url: API_BASEURL + "plugin/hologram",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify({
                    command: "fetchRender",
                    gcodeFilePath: "JobName"
                }),
                success: function(response) {
                    self.displayImageUrl(response.image_data);
                    console.log("G-code file successfully processed by the backend.", response);
                },
                error: function(xhr, status, error) {
                    console.error("Failed to send G-code file to the backend:", status, error);
                    alert("Failed to get render plase make sure you have slected a job");
                }
            });
        };

        self.updateImage = function() {
            $.ajax({
                url: API_BASEURL + "plugin/hologram",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify({
                    command: "update_image",
                    value1: self.sliderValues()[0](),
                    value2: self.sliderValues()[1](),
                    value3: self.sliderValues()[2](),
                    value4: self.sliderValues()[3](),
                    value5: self.sliderValues()[4]()
                }),
                success: function(response) {
                    self.updatedImageUrl(response.image_data); // Assuming 'image_data' is the key in the response JSON
                },
                error: function() {
                    console.error("Failed to update image");
                }
            });
        };

        self.sendOffSets = function() {
            $.ajax({
                url: API_BASEURL + "plugin/hologram",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify({
                    command: "save_off_set",
                    value1: self.sliderValues()[0](),
                    value2: self.sliderValues()[1](),
                    value3: self.sliderValues()[2](),
                    value4: self.sliderValues()[3](),
                    value5: self.sliderValues()[4]()
                }),
                success: function(response) {
                    console.log("Printer dimensions updated successfully.");
                },
                error: function() {
                    console.error("Failed to update printer dimensions.");
                }
            });
        };

        // Toggle enhanced mode state and send it to the server
        self.sendEnhancedMode = function() {
            $.ajax({
                url: API_BASEURL + "plugin/hologram",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify({
                    command: "set_enhanced_mode",
                    enabled: self.enhancedMode()
                }),
                success: function(response) {
                    console.log("Enhanced mode state sent successfully to server.");
                },
                error: function() {
                    console.error("Failed to send enhanced mode state.");
                }
            });
        };

        // Function to update color on the server
        self.updateColor = function() {
            $.ajax({
                url: API_BASEURL + "plugin/hologram",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify({
                    command: "set_color",
                    colorHex: self.colorHex()
                }),
                success: function(response) {
                    console.log("Color updated successfully:", response);
                    alert("Color updated successfully!");
                },
                error: function(xhr, status, error) {
                    console.error("Failed to update color:", error);
                    alert("Failed to update color!");
                }
            });
        };

    }
    
    // Register the ViewModel with OctoPrint's ViewModel system
    OCTOPRINT_VIEWMODELS.push({
        construct: HologramViewModel,
        dependencies: ["settingsViewModel", "loginStateViewModel", "printerProfilesViewModel", "controlViewModel", "printerStateViewModel"],
        elements: ["#settings_plugin_hologram", "#tab_plugin_hologram"]
    });
});
