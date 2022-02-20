
var chart = c3.generate({
    data: {
        columns: [
            ['Accuracy', 86.25]
        ],
        type: 'gauge',

    },
    color: {
        pattern: ['#FF0000', '#F97600', '#F6C600', '#60B044'], // the three color levels for the percentage values.
        threshold: {
            values: [30, 60, 85, 100]
        }
    },
    size: {
        height: 250,
    }
});