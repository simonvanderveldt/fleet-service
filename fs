#!/usr/bin/env python2

import click
import logging
import click_log
import fleet_service
from tabulate import tabulate
from collections import OrderedDict

logger = logging.getLogger(__name__)


@click.group()
@click.option('--fleetctl-endpoint', envvar='FLEETCTL_ENDPOINT', type=str, default='http+unix://%2Fvar%2Frun%2Ffleet.sock', help='Fleetctl endpoint')
@click.option('--timeout', type=int, default=600, help='Maximum allowed time in seconds an instance has to change state. Default 600s (10m)')
@click.version_option(fleet_service.__version__)
@click_log.simple_verbosity_option()
@click_log.init()
@click.pass_context
def cli(ctx, fleetctl_endpoint, timeout):
    """Service based zero-downtime deployment for CoreOS fleet"""
    ctx.obj = fleet_service.FleetService(fleetctl_endpoint, timeout)


@cli.command()
@click.argument('service-name', type=str)
@click.argument('unit-file', type=click.Path(exists=True))
@click.option('--count', type=int, default=3)
@click.pass_obj
def create(ctx, service_name, unit_file, count):
    """Start a service"""
    ctx.create_service(service_name, unit_file, count)


@cli.command()
@click.argument('service-name', type=str)
@click.pass_obj
def destroy(ctx, service_name):
    """Destroy a service"""
    ctx.destroy_service(service_name)


@cli.command()
@click.pass_obj
def ls(ctx):
    """List all services"""
    services = ctx.list_services()
    services_table = []
    for service_name, service_instances in sorted(services.iteritems()):
        # States from https://github.com/systemd/systemd/blob/493fd52f1ada36bfe63301d4bb50f7fd2b38c670/src/basic/unit-name.c#L867
        service_systemd_active_states = {
            'active': 0,
            'failed': 0,
            'inactive': 0,
            'activating': 0,
            'deactivating': 0,
            'reloading': 0
        }
        for service_instance in service_instances:
            service_systemd_active_states[service_instance['systemdActiveState']] += 1
        services_table.append(OrderedDict([
            ['NAME', service_name],
            ['ACTIVE', service_systemd_active_states['active']],
            ['FAILED', service_systemd_active_states['failed']],
            ['INACTIVE', service_systemd_active_states['inactive']],
            ['ACTIVATING', service_systemd_active_states['activating']],
            ['DEACTIVATING', service_systemd_active_states['deactivating']],
            ['RELOADING', service_systemd_active_states['reloading']]
        ]))
    click.echo(tabulate(services_table, headers="keys", tablefmt="plain"))


@cli.command()
@click.pass_obj
def lm(ctx):
    """Show all machines"""
    machines = ctx.list_machines()
    machines_table = []
    for machine in machines:
        machine_id_short = machine['id'][:8] + '...'
        machine_unit_count = len(machine['units'])
        machine_metadata = ','.join("%s=%s" % (key, str(val)) for (key, val) in machine['metadata'].iteritems())
        machines_table.append(OrderedDict([
            ['ID', machine_id_short],
            ['IP', machine['ip']],
            ['UNITS', machine_unit_count],
            ['METADATA', machine_metadata]
        ]))
    click.echo(tabulate(machines_table, headers="keys", tablefmt="plain"))

if __name__ == "__main__":
    cli()
