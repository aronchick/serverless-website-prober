# Estuary Probers

In order to test our systems properly, Protocol Labs has developed a number of ['probers'](https://medium.com/dm03514-tech-blog/sre-availability-probing-101-using-googles-cloudprober-8c191173923c). These provide an external view from end user's perspectives.


# Local setup 
The system runs fine locally, and produces open telemetry text without submitting. However, to simplify things, get a honeycomb.io account and API key. Steps:
* After cloning, copy your .env.sample file to .env.
* Update the values with your 