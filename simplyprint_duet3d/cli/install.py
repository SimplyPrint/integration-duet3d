"""Installscript of the Duet SimplyPrint Connector."""

import click


@click.command()
def install_as_service():
    """Install the SimplyPrint Connector as a systemd service."""
    import os
    import getpass
    import grp
    import subprocess
    import sys
    import tempfile

    # Get the path of the service file
    parent_folder = os.path.dirname(os.path.abspath(__file__))
    service_file = os.path.join(parent_folder, "../../simplyprint-duet3d.service")

    # Read the content of the service file
    with open(service_file, "r") as file:
        service_content = file.read()

    # Replace User and Group with the current user and group
    current_user = getpass.getuser()
    current_group = grp.getgrgid(os.getgid()).gr_name
    service_content = service_content.replace("User=ubuntu", f"User={current_user}", 1)
    service_content = service_content.replace(
        "Group=ubuntu",
        f"Group={current_group}",
        1,
    )

    click.echo(f"Installing the service as user/group: {current_user}/{current_group}")

    # Save the modified content to a temp file
    with tempfile.NamedTemporaryFile("wt+") as tmp_file:
        tmp_file.write(service_content)
        tmp_file.flush()

        # Copy the service file to /etc/systemd/system
        subprocess.check_output([
            "sudo",
            "cp",
            tmp_file.name,
            "/etc/systemd/system/simplyprint-duet3d.service",
        ])

    executable_file = os.path.join(sys.prefix, "bin/simplyprint-duet3d")

    # Make the simplyprint command available outside the venv
    subprocess.run(["sudo", "ln", "-s", executable_file, "/usr/local/bin/simplyprint-duet3d"])

    # Reload the systemd daemon
    subprocess.run(["sudo", "systemctl", "daemon-reload"])

    # Enable the service
    subprocess.run(["sudo", "systemctl", "enable", "simplyprint-duet3d"])

    # Start the service
    subprocess.run(["sudo", "systemctl", "start", "simplyprint-duet3d"])

    print("The SimplyPrint Connector has been installed as a systemd service.")
