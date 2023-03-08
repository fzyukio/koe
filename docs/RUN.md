# Run checklist:
    * [ ] Activate the virtual environment
    * [ ] Run the static server
    * [ ] Run the app

## Activate the environment
On Windows:
```shell
.venv\Scripts\activate.bat
```

On Mac or Linux using virtualenv:
```shell
.venv/bin/activate
```

On Mac using conda:
```shell
conda activate py39
```

## Run the static server
```bash
npm start
```

## Run the app
```bash
python manage.py runserver 8001
```

## Run celery
```bash
mkdir -p logs && celery -A koe worker -l info -c 1 --logfile=logs/celery.log
```