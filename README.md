# Estuary Probers

## Background

In order to test our systems properly, Protocol Labs has developed a number of ['probers'](https://medium.com/dm03514-tech-blog/sre-availability-probing-101-using-googles-cloudprober-8c191173923c). These provide an external view from end user's perspectives.

## Local setup

The system runs fine locally, and produces open telemetry text without submitting. However, to simplify things, get a honeycomb.io account and API key. Steps:

* After cloning, copy your .env.sample file to .env.
* Update the values with the values from each webservice.

This will enable you to run locally with the following command.

`python3 src/estuary_prober/app.py`

or:

`python3 src/cid_prober/app.py`

These have `__main__` sections in the file (at the bottom) and hand rolled "event" blocks that are necessary for each lambda event to fire.

For ex, for the CID prober:

```python3
{
"runner": "aronchick@localdebugging", # Name of the runner (for debugging)
"timeout": 10, # Length of time before http timeout
"region": "ap-south-1", # Region from which this is being called (for debugging)
"cid": "QmducxoYHKULWXeq5wtKoeMzie2QggYphNCVwuFuou9eWE", # CID to query
"prober": "cid_prober" # Name of the prober (currently must be estuary_prober or cid_prober)
}
```

These can be hand manipulated and run again.

## Muxer simulation

The architecture allows for any number of probers to run inside a single lambda & event.

* src/<prober_name>/app.py <- `lambda_handler(event, context)` function contains all code to run.
* src/util/* <- a number of helper tools
* src/muxer/app.py <- function to take an event with "prober" field in which the `prober` value matches the function in the src directory to call. E.g.

```python3
{
    "prober": "estuary_prober"
}
```

Will call `estuary_prober` function with `event` and `context` provided by the lambda event.

You can run the muxer locally by executing:

```bash
python3 src/muxer/app.py
```

(Reminder, there is a `__main__` function at the bottom which details how it will execute from the command line).

## Deploying to Cloud

This app makes heavy use of terraform and workspaces. In the `tf` folder, there are four workspaces - one for each region. To use a given workspace, execute the following:

```bash
terraform select workspace region-name # e.g. ap-south-1
```

The workspace needs to already have been created, and needs to map 1:1 with an [AWS region](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.RegionsAndAvailabilityZones.html)

To deploy, there are three steps:

1. From the root directory, execute `make build`. This zips the entire directory, and puts it into `tf/build/prober`
1. Execute `make zip` which creates a single zip package and puts it into `tf/package/prober.zip`
1. Execute `cd tf && terraform apply -auto-approve` which deploys the currently selected terraform workspace.

The architecture deploys:

* An s3 bucket with the zip included
* Creates the lambda functions (one per prober type) with all the necessary execution roles, log groups.
* Creates one cloud event per line item in the data sources for the probers (so if there are two estuary endpoints and one cid to test, there will be three cloud events) each of which execute once per minute.

Once they begin executing, all spans are automatically uploaded to Honeycomb.io.
