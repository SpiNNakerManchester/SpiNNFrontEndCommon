from spinn_front_end_common.utilities import helpful_functions

# The number of bytes in the header region
HEADER_REGION_BYTES = 12


def simulation_reserve_header(self, spec, region_id):
    """ Reserve space for the default header region

    :param spec: The spec writer to write values to
    :param region_id: The region id to use for the header
    """
    spec.reserve_memory_region(region=region_id, size=HEADER_REGION_BYTES,
                               label="simulation_header")


def simulation_write_header(
        self, spec, region_id, application_name, machine_time_step,
        timescale_factor, no_machine_time_steps):
    """ Write a default header region for this simulation that can be read by\
        the simulation.h simulation_read_header function in C
    :param spec: the spec writer to write values to
    :param region_id: the region id to use for the header
    :param application_name: The name of the application being run
    :param machine_time_step: The duration of a time step in the simulation
    :param timescale_factor: The amount by which the simulation is to be\
                slowed down with respect to real-time
    :param no_machine_time_steps: The number of timesteps in the\
                simulation, or None for no limit
    :return: None
    """

    # Write this to the timings region (to be picked up by the simulation):
    spec.switch_write_focus(region=region_id)
    spec.write_value(data=helpful_functions.get_hash(application_name))
    spec.write_value(data=machine_time_step * timescale_factor)
    if no_machine_time_steps is not None:
        spec.write_value(data=no_machine_time_steps)
    else:
        spec.write_value(data=0xFFFFFFFF)
