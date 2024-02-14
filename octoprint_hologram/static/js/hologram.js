$(function() {
    function HologramViewModel(parameters) {
        var self = this;

        self.snapshotUrl = ko.observable();
        self.updatedImageUrl = ko.observable();
        self.points = ko.observableArray([]);
        self.sliderValues = ko.observableArray([50, 50, 50, 50, 50]); // Default slider values

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
                    value1: self.sliderValues()[0],
                    value2: self.sliderValues()[1],
                    value3: self.sliderValues()[2],
                    value4: self.sliderValues()[3],
                    value5: self.sliderValues()[4]
                }),
                success: function(response) {
                    self.updatedImageUrl(response.url);
                },
                error: function() {
                    alert("Failed to update image");
                }
            });
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: HologramViewModel,
        elements: ["#settings_plugin_hologram"]
    });
});
