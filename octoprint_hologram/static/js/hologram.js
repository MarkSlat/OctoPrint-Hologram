$(function() {
    function HologramViewModel(parameters) {
        var self = this;

        self.snapshotUrl = ko.observable();
        self.updatedImageUrl = ko.observable(); // Will hold the Base64 image data
        self.displayImageUrl = ko.observable(); // Observable for the dynamically fetched Base64 image
        self.points = ko.observableArray([]);
        // Initialize sliderValues as an array of observable floats
        self.sliderValues = ko.observableArray([
            ko.observable(90.0), 
            ko.observable(0.0), 
            ko.observable(0.0), 
            ko.observable(1.0), 
            ko.observable(1.0)
        ]);

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
                alert("Maximum of four points have been recorded.");
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
                    alert("Points saved successfully.");
                },
                error: function(response) {
                    console.error("Failed to save points:", response.responseText);
                    alert("Failed to save points: " + response.responseText);
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
                    // Update the observable to be the Base64 data URI received from the server
                    self.updatedImageUrl(response.image_data); // Assuming 'image_data' is the key in the response JSON
                },
                error: function() {
                    alert("Failed to update image");
                }
            });
        };

        // New function to fetch a Base64-encoded image
        self.fetchBase64Image = function() {
            $.ajax({
                url: API_BASEURL + "plugin/hologram",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify({
                    command: "get_base64_image"
                }),
                success: function(response) {
                    // Assuming the response contains Base64 data under the key 'image_data'
                    self.displayImageUrl(response.image_data);
                },
                error: function() {
                    alert("Failed to retrieve Base64 image");
                }
            });
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: HologramViewModel,
        elements: ["#settings_plugin_hologram", "#tab_plugin_hologram"]
    });
});
