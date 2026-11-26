# Better Init

Replaces printer service scripts with versions that track running
processes correctly.

The stock scripts do not provide normal PID and service-management behavior.
That prevents Moonraker and Fluidd from reliably reporting or controlling
services. Better Init adds the required tracking and wrapper scripts so those
services can be managed from Fluidd.

Service discovery reads the init-script directory directly and does not depend
on Moonraker's PID file. Status checks use PID files and a single procfs
snapshot instead of launching one process per service. This prevents a startup
race from leaving Moonraker with an empty recurring status command and reduces
the steady polling cost on the printer's two-core host.
