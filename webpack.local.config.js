const webpack = require("webpack");
const baseConfig = require("./webpack.base.config");
const BundleTracker = require("webpack-bundle-tracker");
const path = require("path");
const nodeModulesDir = path.resolve(__dirname, "node_modules");

const yaml = require("yamljs");

const settings = yaml.load("settings/settings.yaml");
const port = settings.environment_variables.WEBPACK_SERVER_PORT;

// baseConfig[1].devtool = '#source-map';
baseConfig[1].entry = [
  "webpack-dev-server/client?http://localhost:" + port,
  "webpack/hot/only-dev-server",
  "bootstrap-loader",
  "./assets/js/index",
];

baseConfig[0].output.publicPath =
  "http://localhost:" + port + "/assets/bundles/";
baseConfig[0].port = port;
baseConfig[1].output = {
  path: path.resolve("./assets/bundles/"),
  publicPath: "http://localhost:" + port + "/assets/bundles/",
  filename: "[name].js",
};

baseConfig[1].module.loaders.push({
  test: /\.jsx?$/,
  exclude: [nodeModulesDir],
  loaders: ["babel?presets[]=react,presets[]=es2015"],
});

baseConfig[1].plugins = [
  new webpack.HotModuleReplacementPlugin(),
  new webpack.NoErrorsPlugin(), // don't reload if there is an error
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
