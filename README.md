# Fleet Service
Library and command line tool to enable service based zero-downtime deployment strategies for CoreOS fleet.


## Design choices
- Only instance based deployments are supported, non-instanced units will be removed
- Only indexed instances are supported, all other instances will be removed
- Expects the unit to do it's own health-checking/only exit with return `0`/running when the application is actually running
- Will timeout if a unit doesn't reach it's desired state within the timeout limit. Overriding the default timeout is possible

## Limitations
- Only does initial creates and updates using the `fs create command`, no other commands implemented yet
- Only 1 update strategy supported: stop 1st instance, start 1st instance, stop 2nd instance, start 2nd instance, etc
- Only Python 2.7 is supported because of http://click.pocoo.org/5/python3 and https://github.com/coreos/bugs/issues/112
- Defaults are declared in both `fs` as well the `fleet_helper` module because of https://github.com/pallets/click/issues/627
- Tries to adhere to the rule that [instances and templates are homogenous](https://coreos.com/fleet/docs/latest/unit-files-and-scheduling.html#template-unit-files), but it's not 100% compliant to it yet


## How to use
```
pip install fleet-service
fs --help
```


## How to develop
```
# Create a virtualenv with python 2.7
 virtualenv -p python2.7 .venv
# Activate the virtualenv
source .venv/bin/activate
# Install the dependencies
pip install -r requirements.txt -r requirements-build.txt
# Install fleet-service so you can work on it
pip install -e .
```

### Building the single binary
```
# Make sure the frozen dependency versions are installed
pip install -r requirements-frozen.txt
# native build
pyinstaller --onefile fs.spec
# containerized Linux build
docker-compose -f docker-compose.build.yml run --rm builder
```
The `fs` binary can be found under the `dist` directory


## References
- https://coreos.com/fleet/docs/latest/api-v1.html
- https://github.com/coreos/fleet/blob/master/Documentation/states.md
