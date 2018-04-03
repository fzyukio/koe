const exec = require('child_process').exec;

function log(error, stdout, stderr) {
    console.log(stdout);
    console.error(stderr);
}

const os = require('os');
const osType = os.type();
const productionMode = process.argv[2] == 'production';

const mode = productionMode ? "production": "development";
const configFile = productionMode ? "webpack.prod.config.js": "webpack.local.config.js";

console.log(`Build in ${mode} mode on ${osType} system using ${configFile}`);

if (osType === 'Linux' || osType == 'Darwin')
    exec(`NODE_ENV=${mode} webpack -p --progress --colors --config ${configFile} --bail`, log);
else if (os.type() === 'Windows_NT')
    exec(`set NODE_ENV=${mode} & webpack -p --progress --colors --config ${configFile} --bail`, log);
else
    throw new Error("Unsupported OS found: " + os.type());
