const autoprefixer = require('autoprefixer');
const path = require('path');
const nodeModulesDir = path.resolve(__dirname, 'node_modules');
const BundleTracker = require('webpack-bundle-tracker');

module.exports = [
    {
        entry: [
            './assets/js/jquery-index.js',
        ],
        output: {
            path: path.resolve('./assets/bundles/'),
            filename: 'bundle-jquery.js',
        },
        module: {
            rules: [
                {
                    test: /\.jsx?$/,
                    exclude: [nodeModulesDir],
                    use: {
                        loader: 'babel-loader',
                        options: {
                            presets: ['@babel/preset-env'],
                        },
                    },
                },
                {
                    test: /jquery\/dist\/jquery\.js$/,
                    loader: 'expose-loader?$',
                },
                {
                    test: /jquery\/dist\/jquery\.js$/,
                    loader: 'expose-loader?jQuery',
                },
                {
                    test: /tether\.js$/,
                    loader: "expose-loader?Tether"
                }
            ],
        },
        plugins: [
            new BundleTracker({
                filename: './jquery-webpack-stats.json',
            })
        ]
    },
    {
        context: __dirname,
        entry: [
            // defined in local or prod
        ],
        output: {
            // defined in local or prod
        },
        module: {
            rules: [
                {
                    test: /\.css$/,
                    loaders: [
                        'style-loader',
                        'css-loader',
                        // 'postcss-loader',
                    ],
                },
                {
                    test: /\.scss$/,
                    loaders: [
                        'style-loader',
                        'css-loader',
                        // 'postcss-loader',
                        'sass-loader',
                    ],
                },
                {
                    test: /\.woff(2)?(\?v=[0-9]\.[0-9]\.[0-9])?$/,
                    loader: "url-loader?limit=10000&mimetype=application/font-woff"
                },
                {
                    test: /\.(ttf|eot|svg)(\?v=[0-9]\.[0-9]\.[0-9])?$/,
                    loader: "url-loader?limit=10000"
                },
                {
                    test: /\.(jpg|png)?$/,
                    loaders: [
                        'file-loader?name=i-[hash].[ext]',
                    ],
                },
            ],
        },
        // postcss: [autoprefixer],
        plugins: [
            // defined in local or prod
        ],
        resolve: {
            modules: ['assets/js', 'node_modules', 'bower_components'],
            extensions: ['.js', '.jsx'],
        },
        node: {
            fs: "empty",
            child_process: "empty"
        }
    },
    // {
    //     entry: [
    //         './assets/js/error-tracking.js',
    //     ],
    //     output: {
    //         path: path.resolve('./assets/bundles/'),
    //         filename: 'error-tracking.js',
    //     },
    //     module: {
    //         rules: [
    //             {
    //                 test: /\.jsx?$/,
    //                 exclude: [nodeModulesDir],
    //                 use: {
    //                     loader: 'babel-loader',
    //                     options: {
    //                         presets: ['@babel/preset-env'],
    //                     },
    //                 },
    //             },
    //             {
    //                 test: /jquery\/dist\/jquery\.js$/,
    //                 loader: 'expose-loader?$',
    //             },
    //             {
    //                 test: /jquery\/dist\/jquery\.js$/,
    //                 loader: 'expose-loader?jQuery',
    //             },
    //             {
    //                 test: /tether\.js$/,
    //                 loader: "expose-loader?Tether"
    //             }
    //         ],
    //     },
    //     plugins: [
    //         new BundleTracker({
    //             filename: './error-checking-stats.json',
    //         })
    //     ]
    // },
];
