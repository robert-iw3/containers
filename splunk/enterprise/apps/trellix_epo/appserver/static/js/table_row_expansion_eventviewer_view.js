require.config({
    paths: {
        layer: '../app/mvision_splunk/js/layer',
        JSONFormatter: '../app/mvision_splunk/js/json-formatter.umd'
    },
});

require([
    'splunkjs/mvc/tableview',
    'splunkjs/mvc',
    'underscore',
    'jquery',
    'JSONFormatter',
    'layer',
    'splunkjs/mvc/simplexml/ready!'
], function(
    TableView,
    mvc,
    _,
    $,
    JSONFormatter,
    layer
) {
    var pageDetails = [];

    var MyCustomCellRenderer = TableView.BaseCellRenderer.extend({
        canRender: function(cellData) {
            // Required
            return cellData.field === 'Details';
        },
        render: function($td, cellData) {
            // Required
            if (cellData.value) {
                pageDetails.push(cellData.value);
                $td.html(_.template("<input id='details' type='button' class='table-button btn-primary' data-index='<%- index %>' value='<%- b_str %>'></input>", {
                    index: pageDetails.length - 1,
                    b_str: 'View'
                })).on("click", function(e) {
                    callLogincOnButtonClick(e)
                });;
            } else {
                $td.text("No details!");
            }
        }
    });
    mvc.Components.getInstance("tableWithDrilldown").getVisualization(function(tableView) {
        tableView.addCellRenderer(new MyCustomCellRenderer());
    });

    function callLogincOnButtonClick(e) {
        var index = $(e.target).data("index");
        try {
            var pageData = JSON.parse(pageDetails[index]);
        } catch (e) {}
        // console.log(pageData);
        layer.open({
            type: 1,
            title: false,
            skin: 'layer-ext-skin',
            area: '800px',
            offset: '200px',
            shade: [0.8, '#393D49'],
            shadeClose: true,
            content: $('#json-tree'),
            success: function(layero, index) {
                var formatter = new JSONFormatter(pageData, 1, {
                    theme: 'dark',
                });
                $('#json-tree').append(formatter.render());
            },
            end: function() {
                $('#json-tree').empty();
            }
        });
    }
});