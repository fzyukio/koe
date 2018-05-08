// Webpack dev server
import webpack from 'webpack';
import WebpackDevServer from 'webpack-dev-server';
import config from './webpack.local.config';

const yaml = require('yamljs');

const settings = yaml.load('settings.yaml');
const port = config[0].port;

new WebpackDevServer(webpack(config), {
    publicPath: config[1].output.publicPath,
    hot: true,
    inline: true,
    historyApiFallback: true,
    disableHostCheck: true,
    headers: {
        'Access-Control-Allow-Origin': '*',
    },
}).listen(port, '0.0.0.0', (err) => {
    if (err) {
        console.log(err);
    }

    console.log('Listening at 0.0.0.0:' + port);
});
