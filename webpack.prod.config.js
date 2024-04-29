const baseConfig = require("./webpack.base.config");
const webpack = require("webpack");
const ExtractTextPlugin = require("extract-text-webpack-plugin");
const BundleTracker = require("webpack-bundle-tracker");
const path = require("path");
const nodeModulesDir = path.resolve(__dirname, "node_modules");

// Uncomment next line to enable source-map
// Having source-map in production might not be a good idea - if you're concerned about people stealing your code
// baseConfig[1].devtool = '#source-map';

baseConfig[1].entry = [
  "bootstrap-loader/extractStyles",
  "./assets/js/index.js",
];

baseConfig[1].output = {
  path: path.resolve("./assets/bundles/"),
  publicPath: "",
  filename: "[name]-[hash].js",
};

baseConfig[1].module.loaders.push({
  test: /\.jsx?$/,
  exclude: [nodeModulesDir],
  loaders: ["babel?presets[]=react,presets[]=es2015"],
});

baseConfig[1].plugins = [
  new webpack.DefinePlugin({
    // removes React warnings
    "process.env": {
      NODE_ENV: JSON.stringify("production"),
    },
  }),
  new ExtractTextPlugin("[name]-[hash].css", { allChunks: true }),
  new webpack.optimize.UglifyJsPlugin({ comments: false }),
  new BundleTracker({
    filename: "./webpack-stats.json",
  }),
  new webpack.ProvidePlugin({
    $: "jquery",
    jQuery: "jquery",
    "window.jQuery": "jquery",
    "window.Tether": "tether",
    Tether: "tether",
  }),
];

module.exports = baseConfig;
