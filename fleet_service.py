import re
import fleet.v1 as fleet
import fleet_helper
from pkg_resources import get_distribution, DistributionNotFound


__version__ = None  # required for initial installation
try:
    __version__ = get_distribution('fleet-service').version
except DistributionNotFound:
    __version__ = 'Please install this project with setup.py'


class FleetService(fleet_helper.FleetHelper):
    """Service based zero-downtime deployment for CoreOS fleet"""
    def __init__(self, fleet_uri, timeout):
        super(FleetService, self).__init__(fleet_uri, timeout)
        self.new_instances = []
        self.existing_service_instances = []
        self.our_existing_service_instances = []
        self.wrong_instance_units = []


    def create_service(self, service_name, unit_file, count=3):
        """Create a service"""
        template_unit_name = service_name + '@.service'
        template_unit = fleet.Unit(from_file=unit_file, desired_state='inactive')
        instance_unit = fleet.Unit(from_file=unit_file, desired_state='launched')

        self.logger.info('Creating service ' + service_name)
        self.logger.info('Desired instance count: ' + str(count))

        # Create list of new instances of this service
        for i in range(0, count):
            instance = i + 1
            instance_unit_name = service_name + '@' + str(instance) + '.service'
            self.new_instances.append(instance_unit_name)
        self.logger.info('Desired instances: ' + str(self.new_instances))

        # Get all units so we can find old template and instances of this service
        self.get_units()

        # Get existing instances of this service
        self.existing_service_instances = sorted(self.get_unit_instances(service_name))
        self.logger.info('Existing instance count: ' + str(len(self.existing_service_instances)))
        self.logger.info('Existing instances: ' + str(self.existing_service_instances))

        # Get existing instances we manage
        our_unit_instance_pattern = re.compile(r"^" + re.escape(service_name) + r"@(\d+)\.service")
        self.our_existing_service_instances = sorted([unit for unit in self.existing_service_instances if our_unit_instance_pattern.match(unit)])
        self.logger.info('Existing instances managed by us: ' + str(self.our_existing_service_instances))

        # Destroy non-instanced unit if it exists
        non_instanced_unit_name = service_name + '.service'
        if any(unit['name'] == non_instanced_unit_name for unit in self.fleet_units):
            self.logger.warning('Destroying non-instance unit ' + non_instanced_unit_name)
            self.destroy_unit(non_instanced_unit_name)

        # Destroy instances we don't manage
        self.wrong_instance_units = sorted(set(self.existing_service_instances) - set(self.our_existing_service_instances))
        if len(self.wrong_instance_units) > 0:
            self.logger.warning('Destroying non-matching instance units ' + str(self.wrong_instance_units))
        for unit in self.wrong_instance_units:
            self.destroy_unit(unit)

        # Destroy old template if it exists
        if any(unit['name'] == template_unit_name for unit in self.fleet_units):
            self.logger.info('Destroying old template ' + template_unit_name)
            self.destroy_unit(template_unit_name)

        # Submit new template to fleet
        self.logger.info('Submitting new template ' + template_unit_name)
        self.create_unit(template_unit_name, template_unit)

        # Create new instances that don't exist yet
        instances_to_create = sorted(set(self.new_instances) - set(self.our_existing_service_instances))
        if len(instances_to_create) > 0:
            self.logger.info('Creating new instances: ' + str(instances_to_create))
        for instance in instances_to_create:
            self.create_unit(instance, instance_unit)

        # Update instances that already exist
        instances_to_update = sorted(set(self.our_existing_service_instances) & set(self.new_instances))
        if len(instances_to_update) > 0:
            self.logger.info('Updating existing instances: ' + str(instances_to_update))
        for instance in instances_to_update:
            self.destroy_and_create_unit(instance, instance_unit)

        # Destroy existing instances that should no longer exist
        instances_to_destroy = sorted(set(self.our_existing_service_instances) - set(self.new_instances))
        if len(instances_to_destroy) > 0:
            self.logger.info('Destroying existing instances: ' + str(instances_to_destroy))
        for instance in instances_to_destroy:
            self.destroy_unit(instance)


    def destroy_service(self, service_name):
        """Destroy a service"""
        template_unit_name = service_name + '@.service'

        # Get all units so we can find the template and instances of this service
        self.get_units()

        # Destroy old template if it exists
        if any(unit['name'] == template_unit_name for unit in self.fleet_units):
            self.logger.info('Destroying old template ' + template_unit_name)
            self.destroy_unit(template_unit_name)

        # Get existing instances of this service
        self.existing_service_instances = sorted(self.get_unit_instances(service_name))
        if not self.existing_service_instances:
            self.logger.info('There are no instances for this service, exiting')
            raise SystemExit()
        self.logger.info('Existing instance count: ' + str(len(self.existing_service_instances)))
        self.logger.info('Existing instances: ' + str(self.existing_service_instances))

        # Get existing instances we manage
        our_unit_instance_pattern = re.compile(r"^" + re.escape(service_name) + r"@(\d+)\.service")
        self.our_existing_service_instances = sorted([unit for unit in self.existing_service_instances if our_unit_instance_pattern.match(unit)])
        self.logger.info('Existing instances managed by us: ' + str(self.our_existing_service_instances))

        # Destroy non-instanced unit if it exists
        non_instanced_unit_name = service_name + '.service'
        if any(unit['name'] == non_instanced_unit_name for unit in self.fleet_units):
            self.logger.warning('Destroying non-instance unit ' + non_instanced_unit_name)
            self.destroy_unit(non_instanced_unit_name)

        # Destroy instances we don't manage
        self.wrong_instance_units = sorted(set(self.existing_service_instances) - set(self.our_existing_service_instances))
        if len(self.wrong_instance_units) > 0:
            self.logger.warning('Destroying non-matching instance units ' + str(self.wrong_instance_units))
        for unit in self.wrong_instance_units:
            self.destroy_unit(unit)

        # Destroy instances we manage
        if len(self.our_existing_service_instances) > 0:
            self.logger.info('Destroying instances: ' + str(self.our_existing_service_instances))
        for instance in sorted(self.our_existing_service_instances, reverse=True):
            self.destroy_unit(instance)


    def ps(self):
        """Return service state"""
        instances = {}
        try:
            for unit_state in self.fleet_client.list_unit_states():
                instances.setdefault(unit_state.name, []).append({'machineID':unit_state.machineID,'state':unit_state.systemdSubState})
        except fleet.APIError as exc:
            raise SystemExit('Unable to list units: ' + str(exc))

        self.logger.debug(instances)
        return sorted(instances.items())
