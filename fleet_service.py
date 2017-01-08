import logging
from logging import NullHandler
import re
import fleet.v1 as fleet
from pkg_resources import get_distribution, DistributionNotFound
from collections import defaultdict
from fleet_helper import FleetHelper, get_unit_instances

__version__ = None  # required for initial installation
try:
    __version__ = get_distribution('fleet-service').version
except DistributionNotFound:
    __version__ = 'Please install this project with setup.py'


def get_service_name_from_unit_name(unit_name):
    service_name = None
    service_name_pattern = re.compile(r"^([a-zA-Z0-9:_.@-]+)@\d+.service$")
    service_name_search = re.search(service_name_pattern, unit_name)
    if service_name_search:
        service_name = service_name_search.group(1)

    return service_name


class FleetService(object):
    """Service based zero-downtime deployment for CoreOS fleet"""
    def __init__(self, fleet_uri, timeout):
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(NullHandler())

        # Don't show chatty googleapiclient logs
        logging.getLogger('googleapiclient.discovery').setLevel(logging.WARN)

        try:
            self.fleet_client = FleetHelper(fleet_uri, timeout)
        except ValueError as error:
            raise SystemExit('Unable to discover fleet: ' + format(error))

    def create_service(self, service_name, unit_file, count=3):
        """Create a service"""
        self.logger.info('Creating service ' + service_name + ' with ' + str(count) + ' instances')
        template_unit_name = service_name + '@.service'
        template_unit = fleet.Unit(from_file=unit_file, desired_state='inactive')
        instance_unit = fleet.Unit(from_file=unit_file, desired_state='launched')

        # Create list of new instances for this service
        new_instances = []
        for i in range(0, count):
            instance = i + 1
            instance_unit_name = service_name + '@' + str(instance) + '.service'
            new_instances.append(instance_unit_name)
        self.logger.debug('Desired instances: ' + str(new_instances))

        # Get the currently existing units from fleet
        existing_units = self.fleet_client.get_fleet_units()

        # Get existing instances of this service
        existing_service_instances = sorted(get_unit_instances(existing_units, service_name))
        self.logger.debug('Existing instances: ' + str(existing_service_instances))

        # Get existing instances we manage
        our_unit_instance_pattern = re.compile(r"^" + re.escape(service_name) + r"@(\d+)\.service")
        our_existing_service_instances = sorted([unit for unit in existing_service_instances if our_unit_instance_pattern.match(unit)])
        self.logger.debug('Existing instances managed by us: ' + str(our_existing_service_instances))

        # Destroy non-instanced unit if it exists
        non_instanced_unit_name = service_name + '.service'
        if any(unit['name'] == non_instanced_unit_name for unit in existing_units):
            self.logger.warning('Destroying non-instance unit ' + non_instanced_unit_name)
            self.fleet_client.destroy_unit_and_wait_for(non_instanced_unit_name)

        # Destroy instances we don't manage
        wrong_instance_units = sorted(set(existing_service_instances) - set(our_existing_service_instances))
        if len(wrong_instance_units) > 0:
            self.logger.warning('Destroying instances not created by us: ' + str(wrong_instance_units))
        for unit in wrong_instance_units:
            self.fleet_client.destroy_unit_and_wait_for(unit)

        # Update/create template
        if any(unit['name'] == template_unit_name for unit in existing_units):
            self.logger.info('Updating template ' + template_unit_name)
            if self.fleet_client.destroy_and_create_unit(template_unit_name, template_unit):
                self.logger.info('Updating template ' + template_unit_name + ' done')
        else:
            self.logger.info('Creating template ' + template_unit_name)
            if self.fleet_client.create_unit_and_wait_for(template_unit_name, template_unit):
                self.logger.info('Creating template ' + template_unit_name + ' done')

        # Create new instances that don't exist yet
        instances_to_create = sorted(set(new_instances) - set(our_existing_service_instances))
        if len(instances_to_create) > 0:
            self.logger.info('Creating new instances')
            self.logger.debug('New instances to create: ' + str(instances_to_create))
        for instance in instances_to_create:
            self.logger.info('Creating instance ' + instance)
            if self.fleet_client.create_unit_and_wait_for(instance, instance_unit):
                self.logger.info('Creating instance ' + instance + ' done')

        # Update instances that already exist
        instances_to_update = sorted(set(our_existing_service_instances) & set(new_instances))
        if len(instances_to_update) > 0:
            self.logger.info('Updating existing instances')
            self.logger.debug('Instances to update: ' + str(instances_to_update))
        for instance in instances_to_update:
            self.logger.info('Updating instance ' + instance)
            if self.fleet_client.destroy_and_create_unit(instance, instance_unit):
                self.logger.info('Updating instance ' + instance + ' done')

        # Destroy existing instances that should no longer exist
        instances_to_destroy = sorted(set(our_existing_service_instances) - set(new_instances))
        if len(instances_to_destroy) > 0:
            self.logger.info('Destroying instances we no longer need')
            self.logger.debug('Destroying existing instances: ' + str(instances_to_destroy))
        for instance in instances_to_destroy:
            self.logger.info('Destroying instance ' + instance)
            if self.fleet_client.destroy_unit_and_wait_for(instance):
                self.logger.info('Destroying instance ' + instance + ' done')

        self.logger.info('Creating service ' + service_name + ' with ' + str(count) + ' instances done')
        return True

    def destroy_service(self, service_name):
        """Destroy a service"""
        self.logger.info('Destroying service ' + service_name)
        template_unit_name = service_name + '@.service'

        # Get the currently existing units from fleet
        existing_units = self.fleet_client.get_fleet_units()

        # Get existing instances of this service
        existing_service_instances = sorted(get_unit_instances(existing_units, service_name))
        if not existing_service_instances:
            self.logger.info('There are no instances for this service, exiting')
            raise SystemExit()
        self.logger.debug('Existing instances: ' + str(existing_service_instances))

        # Get existing instances we manage
        our_unit_instance_pattern = re.compile(r"^" + re.escape(service_name) + r"@(\d+)\.service")
        our_existing_service_instances = sorted([unit for unit in existing_service_instances if our_unit_instance_pattern.match(unit)])
        self.logger.debug('Existing instances managed by us: ' + str(our_existing_service_instances))

        # Destroy non-instanced unit if it exists
        non_instanced_unit_name = service_name + '.service'
        if any(unit['name'] == non_instanced_unit_name for unit in existing_units):
            self.logger.warning('Destroying non-instance unit ' + non_instanced_unit_name)
            self.fleet_client.destroy_unit_and_wait_for(non_instanced_unit_name)

        # Destroy instances we don't manage
        wrong_instance_units = sorted(set(existing_service_instances) - set(our_existing_service_instances))
        if len(wrong_instance_units) > 0:
            self.logger.warning('Destroying instances not created by us: ' + str(wrong_instance_units))
        for unit in wrong_instance_units:
            self.fleet_client.destroy_unit_and_wait_for(unit)

        # Destroy old template if it exists
        if any(unit['name'] == template_unit_name for unit in existing_units):
            self.logger.info('Destroying template ' + template_unit_name)
            self.fleet_client.destroy_unit_and_wait_for(template_unit_name)

        # Destroy instances we manage
        if len(our_existing_service_instances) > 0:
            self.logger.debug('Destroying instances: ' + str(our_existing_service_instances))
        for instance in sorted(our_existing_service_instances, reverse=True):
            self.logger.info('Destroying instance ' + instance)
            if self.fleet_client.destroy_unit_and_wait_for(instance):
                self.logger.info('Destroying instance ' + instance + ' done')

        self.logger.info('Destroying service ' + service_name + ' done')
        return True

    def list_services(self):
        """Return info for all services"""
        fleet_unit_states = []
        try:
            for unit in self.fleet_client.list_unit_states():
                fleet_unit_states.append(unit.as_dict())
        except fleet.APIError as exc:
            raise SystemExit('Unable to list unit states: ' + str(exc))
        self.logger.debug('Fleet unit states: ' + str(fleet_unit_states))

        services = defaultdict(list)
        for unit in fleet_unit_states:
            service_name = get_service_name_from_unit_name(unit['name'])
            if service_name:
                services[service_name].append(unit)
        self.logger.debug('Fleet services: ' + str(services.items()))

        return services

    def list_machines(self):
        """Return info for all machines"""
        try:
            fleet_units = list(self.fleet_client.list_unit_states())
        except fleet.APIError as exc:
            raise SystemExit('Unable to list units: ' + str(exc))
        self.logger.debug('Fleet units: ' + str(fleet_units))

        try:
            fleet_machines = list(self.fleet_client.list_machines())
        except fleet.APIError as exc:
            raise SystemExit('Unable to list machines: ' + str(exc))
        self.logger.debug('Fleet machines: ' + str(fleet_machines))

        machines = []
        for machine in fleet_machines:
            machine_units = []
            for unit in fleet_units:
                if unit['machineID'] == machine.id:
                    machine_units.append(unit.as_dict())
            machines.append({'id': machine.id, 'ip': machine.primaryIP, 'units': machine_units, 'metadata': machine.metadata})
        self.logger.debug('Fleet machines and their units: ' + str(machines))

        return machines
