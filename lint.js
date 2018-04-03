const exec = require('child_process').exec;

function log(error, stdout, stderr) {
    console.log(stdout);
    console.error(stderr);

    if (error) {
        let code = error.code;
        console.log('Error checking Python standard. Exit code is', code);
    }
}

console.log('Checking Python coding standard...');
exec(`pycodestyle --max-line-length=120 --exclude=.venv,node_modules,migrations .`, log);


console.log('Checking Javascript coding standard...');
exec(`eslint assets`, log);

