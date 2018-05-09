const autoprefixer = require('autoprefixer');
const path = require('path');
const nodeModulesDir = path.resolve(__dirname, 'node_modules');
const BundleTracker = require('webpack-bundle-tracker');

module.exports = [{
    entry: [
        './assets/js/jquery-index.js',
    ],
    output: {
        path: path.resolve('./assets/bundles/'),
        filename: 'bundle-jquery.js',
    },
    module: {
        loaders: [
            {
                test: /\.jsx?$/,
                exclude: [nodeModulesDir],
                loader: 'babel?presets[]=es2015',
            },
            {
                test: /jquery\/dist\/jquery\.js$/,
                loader: 'expose?$',
            },
            {
                test: /jquery\/dist\/jquery\.js$/,
                loader: 'expose?jQuery',
            },
            {
                test: /tether\.js$/,
                loader: "expose?Tether"
            }
        ],
    },
    plugins: [
        new BundleTracker({
            filename: './jquery-webpack-stats.json',
        })
    ]
}, {
    context: __dirname,
    entry: [
        // defined in local or prod
    ],
    output: {
        // defined in local or prod
    },
    module: {
        loaders: [
            {
                test: /\.css$/,
                loaders: [
                    'style',
                    'css',
                    'postcss',
                ],
            },
            {
                test: /\.scss$/,
                loaders: [
                    'style',
                    'css',
                    'postcss',
                    'sass',
                ],
            },
            {
                test: /\.woff(2)?(\?v=[0-9]\.[0-9]\.[0-9])?$/,
                loader: "url-loader?limit=10000&mimetype=application/font-woff"
            },
            {
                test: /\.(ttf|eot|svg)(\?v=[0-9]\.[0-9]\.[0-9])?$/,
                loader: "file-loader"
            },
            {
                test: /\.(jpg|png)?$/,
                loaders: [
                    'file?name=i-[hash].[ext]',
                ],
            },
        ],
    },
    postcss: [autoprefixer],
    plugins: [
        // defined in local or prod
    ],
    resolve: {
        modulesDirectories: ['assets/js', 'node_modules', 'bower_components'],
        extensions: ['', '.js', '.jsx'],
    },
    node: {
        fs: "empty",
        child_process: "empty"
    }
}];
