ARG := $(word 2, $(MAKECMDGOALS) )


clean:
	@find . -name "*.pyc" -exec rm -rf {} \;
	@find . -name "__pycache__" -delete
	rm -rf static
	rm -rf assets/bundle

bundle:
	npm start

test:
	python manage.py test $(ARG) --parallel --keepdb

testreset:
	python manage.py test $(ARG) --parallel
