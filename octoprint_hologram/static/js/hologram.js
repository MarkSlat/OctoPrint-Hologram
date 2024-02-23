$(function() {
    function HologramViewModel(parameters) {
        var self = this;

        var curJobName="";

        self.printerLength = ko.observable();
        self.printerWidth = ko.observable();
        self.printerDepth = ko.observable();
        self.snapshotUrl = ko.observable();
        self.updatedImageUrl = ko.observable(); // Will hold the Base64 image data
        self.displayImageUrl = ko.observable(); // Observable for the dynamically fetched Base64 image
        self.points = ko.observableArray([]);
        self.sliderValues = ko.observableArray([
            ko.observable(90.0), 
            ko.observable(0.0), 
            ko.observable(0.0), 
            ko.observable(1.0), 
            ko.observable(1.0)
        ]);

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
                    self.snapshotUrl(response.url);
                    self.points([]); // Clear previous points
                },
                error: function() {
                    alert("Failed to get snapshot");
                }
            });
        };

        self.recordClick = function(data, event) {
            var offset = $(event.target).offset();
            var x = event.pageX - offset.left;
            var y = event.pageY - offset.top;

            if (self.points().length < 4) {
                self.points.push({ x: Math.round(x), y: Math.round(y) });
            } else {
                // Maximum of 4 points reached
            }
        };

        self.savePoints = function() {
            $.ajax({
                url: API_BASEURL + "plugin/hologram",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify({
                    command: "save_points",
                    points: ko.toJS(self.points)
                }),
                success: function(response) {
                    // Handle success
                },
                error: function(response) {
                    console.error("Failed to save points:", response.responseText);
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

        // self.fetchBase64Image = function() {
        //     $.ajax({
        //         url: API_BASEURL + "plugin/hologram",
        //         type: "POST",
        //         dataType: "json",
        //         contentType: "application/json; charset=UTF-8",
        //         data: JSON.stringify({
        //             command: "get_base64_image"
        //         }),
        //         success: function(response) {
        //             self.displayImageUrl(response.image_data);
        //         },
        //         error: function() {
        //             console.error("Failed to retrieve Base64 image");
        //         }
        //     });
        // };

        self.fromHistoryData = function(data) {
            if(!viewInitialized)
                return;
                curJobName = data.job.file.path;
        };

        self.fromCurrentData = function(data) {
            if(!viewInitialized)
                return;
            curJobName = data.job.file.path;
        }

        // Method to send G-code file information to the backend
        self.fetchRender = function() {
            const filePath = `/downloads/files/local/${curJobName}`; // Adjust if the path is different
            $.ajax({
                url: API_BASEURL + "plugin/hologram",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify({
                    command: "fetchRender",
                    gcodeFilePath: filePath
                }),
                success: function(response) {
                    self.displayImageUrl(response.image_data);
                    console.log("G-code file successfully processed by the backend.", response);
                    // Additional actions based on the response
                },
                error: function(xhr, status, error) {
                    console.error("Failed to send G-code file to the backend:", status, error);
                }
            });
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: HologramViewModel,
        dependencies: ["settingsViewModel", "loginStateViewModel", "printerProfilesViewModel", "controlViewModel"],
        elements: ["#settings_plugin_hologram", "#tab_plugin_hologram"]
    });
});
