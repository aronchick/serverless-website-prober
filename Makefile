SERVICE=EstuaryProber

build:
	poetry export -f requirements.txt --without-hashes -o requirements.txt
	sam build -m requirements.txt --use-container

run:
	sam local invoke "$(SERVICE)" -e ./events/basic.json

zip:
	./zip.bash $(SERVICE)

clean:
	rm -rf .aws-sam
