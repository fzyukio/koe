const baseConfig = require('./webpack.base.config');
const webpack = require('webpack');
const MiniCssExtractPlugin = require("mini-css-extract-plugin");
const BundleTracker = require('webpack-bundle-tracker');
const path = require('path');
const nodeModulesDir = path.resolve(__dirname, 'node_modules');
const UglifyJsPlugin = require('uglifyjs-webpack-plugin');

// Uncomment next line to enable source-map
// Having source-map in production might not be a good idea - if you're concerned about people stealing your code
// baseConfig[1].devtool = '#source-map';

baseConfig[1].entry = [
    'bootstrap-loader/extractStyles',
    './assets/js/index.js',
];

baseConfig[1].output = {
    path: path.resolve('./assets/bundles/'),
    publicPath: '',
    filename: '[name]-[hash].js',
};

baseConfig[1].optimization = {
    minimizer: [
        new UglifyJsPlugin({
            cache: true,
            parallel: true,
            uglifyOptions: {
                compress: true,
                ecma: 6,
                mangle: true
            },
            sourceMap: false
        })
    ]
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
    new webpack.DefinePlugin({  // removes React warnings
        'process.env': {
            'NODE_ENV': JSON.stringify('production')
        }
    }),
    // new ExtractTextPlugin('[name]-[hash].css', {allChunks: true}),
    new MiniCssExtractPlugin({filename: '[name]-[hash].css', disable: false, allChunks: true}),
    new BundleTracker({
        filename: './webpack-stats.json'
    }),
    new webpack.ProvidePlugin({
        $: "jquery",
        jQuery: "jquery",
        "window.jQuery": "jquery",
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
