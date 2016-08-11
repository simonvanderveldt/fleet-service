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

    def create_service(self, service_name, unit_file, count=3):
        """Create a service"""
        template_unit_name = service_name + '@.service'
        template_unit = fleet.Unit(from_file=unit_file, desired_state='inactive')
        instance_unit = fleet.Unit(from_file=unit_file, desired_state='launched')

        self.logger.info('Creating service ' + service_name)
        self.logger.info('Desired instance count: ' + str(count))

        # Get all units so we can find old template and instances of this service
        fleet_units = self.get_units()

        # Get list of old instances of this service
        existing_unit_instances = self.get_unit_instances(fleet_units, service_name)
        self.logger.info('Existing instance count: ' + str(len(existing_unit_instances)))

        # Destroy non-instanced unit if it exists
        non_instanced_unit_name = service_name + '.service'
        if any(unit['name'] == non_instanced_unit_name for unit in fleet_units):
            self.logger.warning('Destroying non-instance unit ' + non_instanced_unit_name)
            self.destroy_unit(non_instanced_unit_name)

        # Destroy old template if it exists
        if any(unit['name'] == template_unit_name for unit in fleet_units):
            self.logger.info('Destroying template ' + template_unit_name)
            self.destroy_unit(template_unit_name)

        # Submit new template to fleet
        self.logger.info('Submitting new template ' + template_unit_name)
        self.create_unit(template_unit_name, template_unit)

        # Update old instances/start new instances
        maximum_instances = max(len(existing_unit_instances), count)
        self.logger.debug('Maximum instances: ' + str(maximum_instances))
        for i in range(0, maximum_instances):
            instance = i + 1
            self.logger.debug('Current instance: ' + str(instance))
            instance_unit_name = service_name + '@' + str(instance) + '.service'

            # Destroy the old instance if it exists
            if any(unit['name'] == instance_unit_name for unit in fleet_units):
                self.destroy_instance(instance_unit_name)

            # Create and start the new instance if we're still at or below the desired count
            if instance <= (count):
                self.create_instance(instance_unit_name, instance_unit)


    def ps(self):
        """Return service state"""
        instances = {}
        try:
            for unit_state in self.fleet_client.list_unit_states():
                instances.setdefault(unit_state.name, []).append({'machineID':unit_state.machineID,'state':unit_state.systemdSubState})
        except fleet.APIError as exc:
            self.logger.error('Unable to list units: ' + str(exc))
            raise SystemExit

        self.logger.debug(instances)
        return sorted(instances.items())
