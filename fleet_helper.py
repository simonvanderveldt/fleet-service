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


def get_unit_instances(units, unit_name):
    """Get a list of instances for a unit"""
    unit_instances = []
    unit_instance_pattern = re.compile(r"^" + re.escape(unit_name) + r"@[a-zA-Z0-9:_.-]+\.service$")
    for unit in units:
        if unit_instance_pattern.match(unit['name']):
            unit_instances.append(unit.name)

    return unit_instances


class FleetHelper(fleet.Client):
    """Exposes convenience functions wrapping python-fleet"""
    def __init__(self, fleet_uri='http+unix://%2Fvar%2Frun%2Ffleet.sock', timeout=600):
        super(FleetHelper, self).__init__(fleet_uri)
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(NullHandler())
        self.fleet_uri = fleet_uri
        self.timeout = timeout
        self.__attempts = timeout/DEFAULT_SLEEP_TIME

        # Don't show chatty googleapiclient logs
        logging.getLogger('googleapiclient.discovery').setLevel(logging.WARN)

    def get_fleet_units(self):
        """Get a list of all units
        https://coreos.com/fleet/docs/latest/api-v1.html#list-units"""
        try:
            return list(self.list_units())
        except fleet.APIError as error:
            raise SystemExit('Unable to get unit list: ' + format(error))

    def get_systemd_unit_states(self):
        """"Get a list of SystemD states
        https://coreos.com/fleet/docs/latest/api-v1.html#current-unit-state"""
        try:
            return self.list_unit_states()
        except fleet.APIError as error:
            raise SystemExit('Unable to get unit states: ' + format(error))

    def get_fleet_unit_state(self, unit_name):
        """Get a unit's current state"""
        unit_state = None
        fleet_units = self.get_fleet_units()
        fleet_unit = next((unit for unit in fleet_units if unit['name'] == unit_name), None)

        if fleet_unit is not None and 'currentState' in fleet_unit:
            unit_state = fleet_unit['currentState']

        self.logger.debug(str(unit_name) + ' state: ' + str(unit_state))
        return unit_state

    def wait_for_fleet_unit_state(self, unit_name, desired_state):
        """Wait for a unit to reach a desired state, will timeout after #self.__attempts"""
        self.logger.debug('Waiting for unit ' + str(unit_name) + ' to reach fleet state ' + str(desired_state))
        i = 0
        while i < self.__attempts:
            unit_state = self.get_fleet_unit_state(unit_name)

            if unit_state == desired_state:
                break
            time.sleep(DEFAULT_SLEEP_TIME)
            i += 1
        else:
            raise SystemExit('Timed out waiting for unit ' + unit_name + ' to reach state ' + str(desired_state))

    def get_systemd_unit_state(self, unit_name):
        """Get unit's SystemD state
        See https://github.com/coreos/fleet/blob/master/Documentation/states.md#systemd-states
        """
        systemd_state = None
        systemd_unit_states = self.get_systemd_unit_states()
        fleet_unit_systemd_state = next((unit for unit in systemd_unit_states if unit['name'] == unit_name), None)

        if fleet_unit_systemd_state is not None and 'systemdActiveState' in fleet_unit_systemd_state:
            systemd_state = fleet_unit_systemd_state['systemdActiveState']

        self.logger.debug(unit_name + ' SystemD state: ' + str(systemd_state))
        return systemd_state

    def wait_for_systemd_unit_state(self, unit_name, desired_state):
        """Wait for a unit to reach a desired state in SystemD, will timeout after #self.__attempts"""
        self.logger.debug('Waiting for unit ' + str(unit_name) + ' to reach SystemD state ' + str(desired_state))
        i = 0
        while i < self.__attempts:
            unit_systemd_state = self.get_systemd_unit_state(unit_name)

            if unit_systemd_state == desired_state:
                break
            time.sleep(DEFAULT_SLEEP_TIME)
            i += 1
        else:
            raise SystemExit('Timed out waiting for unit ' + unit_name + ' to reach state ' + str(desired_state))

    def wait_for_create_unit(self, unit_name, unit):
        """Submit a new unit"""
        self.logger.debug('Creating new unit ' + unit_name + ' with desired state ' + unit.desiredState)
        try:
            self.create_unit(unit_name, unit)
        except fleet.APIError as error:
            raise SystemExit('Unable to create unit: ' + format(error))
        self.wait_for_fleet_unit_state(unit_name, unit.desiredState)
        if unit.desiredState == 'launched':
            self.wait_for_systemd_unit_state(unit_name, 'active')
        return True

    def wait_for_destroy_unit(self, unit_name):
        """Destroy a unit"""
        self.logger.debug('Destroying unit ' + unit_name)
        try:
            self.destroy_unit(unit_name)
        except fleet.APIError as error:
            raise SystemExit('Unable to destroy unit ' + format(error))
        self.wait_for_fleet_unit_state(unit_name, None)
        self.wait_for_systemd_unit_state(unit_name, None)
        return True

    def wait_for_destroy_and_create_unit(self, unit_name, unit):
        """Do a verified destroy and then a verified create of a unit"""
        self.wait_for_destroy_unit(unit_name)
        self.wait_for_create_unit(unit_name, unit)
        return True
