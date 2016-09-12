#!/usr/bin/env python2

import click
import logging
import click_log
import fleet_service

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
def restart(ctx, service_name):
    """Restart a service without downtime"""
    logger.info("Not implemented yet ;)")


@cli.command()
@click.argument('service-name', type=str)
@click.pass_obj
def destroy(ctx, service_name):
    """Destroy a service"""
    ctx.destroy_service(service_name)


@cli.command()
@click.pass_obj
def ps(ctx):
    """Show status of all services"""
    services = ctx.ps()
    for key, value in services:
        print(key + ": " + str(len(value)))


if __name__ == "__main__":
    cli()
