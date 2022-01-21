SERVICE=EstuaryProber
BUCKETNAME=protocol-labs-lambda-benchmarking-functions

build:
	poetry export -f requirements.txt --without-hashes -o requirements.txt
	sam build -m requirements.txt --use-container --build-dir tf/build

run:
	sam local invoke "$(SERVICE)" -e ./events/basic.json

.PHONY: zip
zip:
	./zip.bash $(SERVICE)

apply: build
	cd tf && \
	terraform apply -auto-approve 

update:
	aws lambda update-function-code --s3-bucket s3://$(BUCKETNAME) --s3-key $(SERVICE).zip

clean:
	rm -rf .aws-sam
