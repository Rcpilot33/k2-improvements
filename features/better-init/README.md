# Better Init

Replaces key K2 Plus service scripts with versions that track running
processes correctly.

The stock scripts do not provide normal PID and service-management behavior.
That prevents Moonraker and Fluidd from reliably reporting or controlling
services. Better Init adds the required tracking and wrapper scripts so those
services can be managed from Fluidd.
