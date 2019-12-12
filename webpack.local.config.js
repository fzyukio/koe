const webpack = require('webpack');
const baseConfig = require('./webpack.base.config');
const BundleTracker = require('webpack-bundle-tracker');
const path = require('path');
const nodeModulesDir = path.resolve(__dirname, 'node_modules');

const yaml = require('yamljs');

const settings = yaml.load('settings.yaml');
const port = settings.environment_variables.WEBPACK_SERVER_PORT;

// baseConfig[1].devtool = '#source-map';
// baseConfig[0].mode = 'development';
// baseConfig[1].mode = 'development';
// baseConfig[2].mode = 'development';

baseConfig[1].entry = [
    'webpack-dev-server/client?http://localhost:' + port,
    'webpack/hot/only-dev-server',
    'bootstrap-loader',
    './assets/js/index',
];

baseConfig[0].output['publicPath'] = 'http://localhost:' + port + '/assets/bundles/';
// baseConfig[0].port = port;
baseConfig[1].output = {
    path: path.resolve('./assets/bundles/'),
    publicPath: 'http://localhost:' + port + '/assets/bundles/',
    filename: '[name].js',
};

baseConfig[1].module.rules.push({
    test: /\.jsx?$/,
    exclude: [nodeModulesDir],
    use: {
        loader: 'babel-loader',
        options: {
            presets: ['@babel/preset-env'],
        },
    },
});

baseConfig[1].plugins = [
    new webpack.HotModuleReplacementPlugin(),
    new webpack.NoEmitOnErrorsPlugin(),  // don't reload if there is an error
    new BundleTracker({
        filename: './webpack-stats.json'
    }),
    new webpack.ProvidePlugin({
        $: "jQuery",
        jQuery: "jQuery",
        "window.jQuery": "jQuery",
        "window.Tether": 'tether',
        "Tether": 'tether',
        // Alert: "exports-loader?Alert!bootstrap/js/dist/alert",
        // Button: "exports-loader?Button!bootstrap/js/dist/button",
        // Carousel: "exports-loader?Carousel!bootstrap/js/dist/carousel",
        // Collapse: "exports-loader?Collapse!bootstrap/js/dist/collapse",
        // Dropdown: "exports-loader?Dropdown!bootstrap/js/dist/dropdown",
        // Modal: "exports-loader?Modal!bootstrap/js/dist/modal",
        // Popover: "exports-loader?Popover!bootstrap/js/dist/popover",
        // Scrollspy: "exports-loader?Scrollspy!bootstrap/js/dist/scrollspy",
        // Tab: "exports-loader?Tab!bootstrap/js/dist/tab",
        // Tooltip: "exports-loader?Tooltip!bootstrap/js/dist/tooltip",
        // Util: "exports-loader?Util!bootstrap/js/dist/util",
    })
];


module.exports = baseConfig;
