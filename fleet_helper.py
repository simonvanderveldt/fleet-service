import fleet.v1 as fleet
import re
import time
import logging
from logging import NullHandler
from pkg_resources import get_distribution, DistributionNotFound


__version__ = None  # required for initial installation
try:
    __version__ = get_distribution('fleet-service').version
except DistributionNotFound:
    __version__ = 'Please install this project with setup.py'

DEFAULT_SLEEP_TIME = 0.5


class FleetHelper(object):
    """Exposes convenience functions wrapping python-fleet"""
    def __init__(self, fleet_uri='http+unix://%2Fvar%2Frun%2Ffleet.sock', timeout=600):
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(NullHandler())
        self.fleet_uri = fleet_uri
        self.timeout = timeout
        self.__attempts = timeout/DEFAULT_SLEEP_TIME
        self.fleet_units = None
        self.fleet_systemd_states = None

        # Don't show chatty googleapiclient logs
        logging.getLogger('googleapiclient.discovery').setLevel(logging.WARN)

        try:
            self.fleet_client = fleet.Client(fleet_uri)
        except ValueError as error:
            self.logger.error('Unable to discover fleet: ' + format(error))
            raise SystemExit


    def get_units(self):
        """Get a list of all units
        https://coreos.com/fleet/docs/latest/api-v1.html#list-units"""
        try:
            self.fleet_units = list(self.fleet_client.list_units())
        except fleet.APIError as error:
            self.logger.error('Unable to get unit list: ' + format(error))
            raise SystemExit


    def get_systemd_states(self):
        """"Get a list of SystemD states
        https://coreos.com/fleet/docs/latest/api-v1.html#current-unit-state"""
        try:
            self.fleet_systemd_states = self.fleet_client.list_unit_states()
        except fleet.APIError as error:
            print('Unable to get unit states: ' + format(error))
            raise SystemExit


    def get_unit_instances(self, unit_name):
        """Get a list of instances for a unit"""
        unit_instances = []
        unit_instance_pattern = re.compile(r"^" + re.escape(unit_name) + r"@[a-zA-Z0-9:_.-]+\.service$")
        for unit in self.fleet_units:
            if unit_instance_pattern.match(unit['name']):
                unit_instances.append(unit.name)

        return unit_instances


    def get_unit_fleet_state(self, unit_name):
        """Get a unit's current state"""
        unit_state = None
        self.get_units()
        fleet_unit = next((unit for unit in self.fleet_units if unit['name'] == unit_name), None)

        if fleet_unit != None:
            unit_state = fleet_unit.currentState

        self.logger.debug(str(unit_name) + ' state: ' + str(unit_state))
        return unit_state


    def wait_for_unit_state(self, unit_name, desired_state):
        """Wait for a unit to reach a desired state, will timeout after #self.__attempts"""
        self.logger.debug('Waiting for unit ' + str(unit_name) + ' to reach state ' + str(desired_state))
        i = 0
        while i < self.__attempts:
            unit_state = self.get_unit_fleet_state(unit_name)

            if unit_state == desired_state:
                break
            time.sleep(DEFAULT_SLEEP_TIME)
            i = i + 1
        else:
            self.logger.error('ERROR: Timed out waiting for unit ' + unit_name + ' to reach state ' + str(desired_state))
            raise SystemExit


    def get_unit_systemd_state(self, unit_name):
        """Get unit's SystemD state
        See https://github.com/coreos/fleet/blob/master/Documentation/states.md#systemd-states
        """
        systemd_state = None
        self.get_systemd_states()
        fleet_unit_systemd_state = next((unit for unit in self.fleet_systemd_states if unit['name'] == unit_name), None)

        if fleet_unit_systemd_state != None:
            systemd_state = fleet_unit_systemd_state['systemdActiveState']

        self.logger.debug(unit_name + ' SystemD state: ' + str(systemd_state))
        return systemd_state


    def wait_for_unit_systemd_state(self, unit_name, desired_state):
        """Wait for a unit to reach a desired state in SystemD, will timeout after #self.__attempts"""
        self.logger.debug('Waiting for unit ' + str(unit_name) + ' to reach SystemD state ' + str(desired_state))
        i = 0
        while i < self.__attempts:
            unit_systemd_state = self.get_unit_systemd_state(unit_name)

            if unit_systemd_state == desired_state:
                break
            time.sleep(DEFAULT_SLEEP_TIME)
            i = i + 1
        else:
            self.logger.error('ERROR: Timed out waiting for unit ' + unit_name + ' to reach state ' + str(desired_state))
            raise SystemExit


    def create_unit(self, unit_name, unit):
        """Submit a new unit"""
        self.logger.debug('Creating new unit: ' + unit_name + ' with desired state ' + unit.desiredState)
        try:
            self.fleet_client.create_unit(unit_name, unit)
        except fleet.APIError as error:
            self.logger.error('Unable to create new unit: ' + format(error))
            raise SystemExit
        self.wait_for_unit_state(unit_name, unit.desiredState)
        if unit.desiredState == 'launched':
            self.wait_for_unit_systemd_state(unit_name, 'active')


    def destroy_unit(self, unit_name):
        """Destroy a unit"""
        self.logger.debug('Destroying unit: ' + unit_name)
        try:
            self.fleet_client.destroy_unit(unit_name)
        except fleet.APIError as error:
            self.logger.error('Unable to destroy old unit ' + format(error))
            raise SystemExit
        self.wait_for_unit_state(unit_name, None)
        self.wait_for_unit_systemd_state(unit_name, None)


    def destroy_and_create_unit(self, unit_name, unit):
        """Do a verified destroy and then a verified create of a unit"""
        self.destroy_unit(unit_name)
        self.create_unit(unit_name, unit)
